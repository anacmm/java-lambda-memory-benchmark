# How much memory does a Java Lambda really need? CPU vs I/O

A controlled experiment using Java 21, Quarkus Native/Mandrel, ARM64, AWS SDK for
Java v2, Maven, and Java CDK. The research question is: **Does the optimal AWS
Lambda memory configuration depend on what a Java Lambda actually does?**

Compare CPU-heavy and S3 I/O-heavy workload profiles in the same environment at
256, 512, 1024, 1536, 2048, 3072, and 4096 MB. Within each workload, memory allocation
is the only intended variable. Across workloads, workload type is intentionally
the second experimental dimension. The article uses the 9, 14 and 19 October AWS
runs and corresponding LocalStack experiments as its evidence.
A separate [LocalStack experiment](localstack/README.md) tests the same native
application locally, with evidence kept under `localstack/results/`.

The **28 October 2026 results are under investigation** due to unexpected
variability, particularly in LocalStack I/O performance. Their raw measurements,
graphs and run documentation are preserved unchanged for comparison with future
runs. Graphs and summaries remain in Git; raw evidence stays local and is ignored
for commits. These results are excluded from the main article and its conclusions
until additional benchmarks support reassessment. See the preserved
[28 October comparison](benchmark-runs/20261028-two-runs/README.md).

## Architecture and layout

One handler accepts `{workload, bucket, key}`. Both paths fully GET the same S3
object and compare the received byte count against S3's Content-Length. A missing
or mismatched length fails the invocation. The SDK v2 synchronous S3 client is
managed by the Quarkus S3 extension and retained in a CDI bean between invocations.
The object is fetched every time; no object or result caching occurs.

| Workload | Processing after S3 GET | Response |
| --- | --- | --- |
| `cpu` | Jackson deserialization, then the original fixed integer calculation | Records processed, original checksum, status |
| `io` | One lightweight CRC32 pass over the bytes; no JSON parsing or calculation rounds | Object bytes, `crc32:` checksum, status |

Omitting `workload` or sending JSON `null` preserves the original CPU behavior.
Only the exact strings `cpu` and `io` are accepted; blank/unknown values fail before
S3 access. CPU responses retain their original JSON shape. I/O responses omit
`recordsProcessed` because no records are deserialized.

### Why one selectable function?

One function keeps the deployed native ZIP, configuration, runtime, execution
role, client lifecycle, and logging identical for both paths. It also keeps the
infrastructure small. Two functions built from the same ZIP would isolate warm
state and memory high-water marks, but introduce independent execution environments,
initialization histories, and configuration that must be kept in sync. We choose
one selectable function for this POC and account for its shared state in trial design.

Run each workload in separate batches, warm the selected path before collecting
warm samples, and balance/repeat batch order across trials. A first I/O call after
a CPU call in the same process is **not** an I/O cold start. Cold observations
must come from actual first-process invocations of the selected workload, as
identified by logs. Do not infer a cold start merely from switching workloads or
waiting for a configuration update. Keep the invocation pattern/concurrency fixed.

| Path | Purpose |
| --- | --- |
| `lambda/` | Selectable handler, JSON records, S3 reader, unchanged CPU calculation, CRC32 verification, and offline tests |
| `infra/` | Java CDK app: bucket, Lambda execution role, function, and log group |
| `sample/dataset.json` | Fixed 4,000-record dataset (191,961 bytes) |
| `scripts/build-native.sh` | Linux ARM64 build and HTTPS trust-store packaging |

### CPU-heavy workload

The unchanged calculation performs 8,192 dependent rotate/XOR/multiply rounds per record
(32,768,000 for the sample), then folds results into an order-sensitive checksum.
Signed 64-bit overflow is intentional. All inputs influence the result. There
are no sleeps, parallel execution, memory-dependent branches, SnapStart, or
provisioned concurrency. The workload is synthetic CPU work, not a business algorithm.
Actual CPU/transfer proportions must be confirmed in AWS; the small dataset limits
transfer size but S3 latency can still dominate fast invocations.

### I/O-heavy workload and object size

Reuse `sample/dataset.json`: 191,961 bytes (about 187.5 KiB), with the exact same
bytes, format, bucket, and key as CPU trials. Removing JSON parsing and 32.8 million
calculation rounds leaves one S3 GET plus a single CRC32 pass over a small buffer.
This intentionally tests **S3 request latency**, rather than sustained large-object
transfer bandwidth. The payload makes a real full-body download and correctness
check possible without increasing storage/transfer volume or adding another dataset.

The hypothesis is that S3 time will dominate this minimal processing path; verify
that using `s3Ms` and `cpuMs` on AWS before describing it as empirically I/O-bound.
TLS, signing, SDK buffering, and CRC32 still use CPU, so this is not a pure network
test and does not predict results for large S3 transfers or other I/O services.
If measurements do not show sufficient separation, revise the experiment's fixed
object before starting a new full matrix; never adapt object size by memory setting.

CRC32 provides a cheap correctness check, not cryptographic integrity. It covers
**every received byte**, including JSON whitespace and the trailing newline. The
Content-Length comparison detects incomplete transfers; comparing the returned CRC32
against the known fixture detects unintended object changes. Do not resave/reformat
the sample between trials. Its expected results are:

- CPU: 4,000 records, checksum `b1e029a3d2d7974c`.
- I/O: 191,961 bytes, checksum `crc32:1c396adb`.
- Object SHA-256: `2939695c8e099f3d73ea84e17069dc7cbae9304be72972d0be0f5f1b698fa10e`.

Quarkus builds a GraalVM/Mandrel native executable ahead of time, so Lambda starts
the binary without loading a JVM. This makes native startup and memory footprint
part of the experiment. Dependencies are pinned to Quarkus 3.27.6 (a Java 21
compatible release) and CDK 2.272.0; this is an experiment baseline, not an automatic
latest-version selection. Quarkus's platform BOM also pins the SDK/extension versions.

## Prerequisites

- JDK 21 and Maven 3.9+ (`java -version`, `mvn -version`).
- Docker Desktop running with Linux containers. Allow roughly 8 GB of Docker RAM
  for native compilation; it can take several minutes.
- AWS CLI v2, AWS credentials, and an AWS account/region where you can deploy.
- A supported Node.js LTS release, AWS CDK CLI v2 (`npm install -g aws-cdk`), and `jq`.
  Use a current CLI compatible with the pinned CDK library.
- `bash`, `file`, and `unzip` (available on macOS).

Import the root `pom.xml` into IntelliJ as a Maven project. The original generated
`src/Main.java` has been replaced by the Lambda handler.

## Tests and builds

From the repository root:

```bash
# Offline tests: both workload results, selection, legacy requests, JSON,
# cold/warm and failure logging, and complete/invalid S3 transfers.
mvn test

# Build both modules normally (also runs tests).
mvn clean package

# Native Lambda ZIP, including tests. Docker Desktop must be running.
bash scripts/build-native.sh
```

Normal packaging creates a **JVM** `lambda/target/function.zip`; do not deploy it
to `provided.al2023`. The native build replaces it with a ZIP containing `bootstrap`,
`runner`, and `cacerts`. CDK refuses a JVM ZIP or a non-ARM64 executable.

The native Maven profile forces `linux/arm64` and a Java 21 UBI 9 Mandrel builder.
On Apple Silicon this builds Linux ARM64 directly in Docker, rather than a macOS
binary. Lambda uses `Architecture.ARM_64` and `Runtime.PROVIDED_AL2023`. UBI 9's
glibc baseline is compatible with AL2023; do not switch to a UBI 10 builder without
checking binary compatibility. `march=compatibility` avoids host-specific CPU tuning.
The script extracts the builder's CA trust store for S3 HTTPS and verifies the ELF
architecture. A native Linux binary cannot be executed directly on macOS.

The builder's `jdk-21` tag can change. Build the updated two-workload application
**once**, then use that exact same ZIP for both workloads and every memory trial.
The old CPU-only ZIP does not contain the I/O path; do not mix it into this matrix.
Keep the ZIP unchanged and record its SHA-256 and resolved builder digest:

```bash
shasum -a 256 lambda/target/function.zip | tee lambda/target/artifact.sha256
shasum -a 256 sample/dataset.json | tee lambda/target/object.sha256
docker image inspect quay.io/quarkus/ubi9-quarkus-mandrel-builder-image:jdk-21 \
  --format '{{json .RepoDigests}}' | tee lambda/target/builder-digests.json
```

Archive those identity files with the ZIP and trial notes before starting the
experiment; `mvn clean` removes `target/`. Before each memory trial, verify the
ZIP and object with `shasum -a 256 -c lambda/target/artifact.sha256` and
`shasum -a 256 -c lambda/target/object.sha256` from the repository root.

JVM unit tests do not establish native/AWS compatibility. A successful native
build and the S3 invocation below are the deployment smoke test.

The earlier CPU-only implementation was locally validated on Apple Silicon with
an ARM64 native build, AL2023 container invocations against local Lambda/S3 stubs,
and CDK synthesis. That validation does not establish the revised I/O path's native
behavior. Current two-workload validation is recorded after the checks complete.
Real AWS deployment, S3 HTTPS access, and Lambda measurements remain to be verified
with the commands below. Local container timings are not AWS benchmark results.

## Deploy

Choose one region and keep it fixed. All following AWS commands use that region.

```bash
export AWS_REGION=eu-west-2
export AWS_DEFAULT_REGION="$AWS_REGION"
aws sts get-caller-identity

cd infra
# Once per account/region; omit if already bootstrapped.
cdk bootstrap
cdk synth
cdk deploy JavaBenchmarkStack --parameters MemorySize=1024 --outputs-file outputs.json
cd ..
```

The stack creates a private, encrypted S3 bucket, one ARM64 native Lambda with a
60-second timeout, an execution role with bucket read and logging permissions,
and a CloudWatch log group with seven-day retention. There is no VPC or API Gateway.

## Upload and invoke

Run from the repository root, after deployment:

```bash
BENCHMARK_BUCKET=$(jq -r '.JavaBenchmarkStack.BucketName' infra/outputs.json)
BENCHMARK_FUNCTION=$(jq -r '.JavaBenchmarkStack.FunctionName' infra/outputs.json)
BENCHMARK_LOG_GROUP=$(jq -r '.JavaBenchmarkStack.LogGroupName' infra/outputs.json)

aws s3 cp sample/dataset.json "s3://$BENCHMARK_BUCKET/dataset.json" \
  --content-type application/json
jq -n --arg bucket "$BENCHMARK_BUCKET" --arg key dataset.json \
  '{workload: "cpu", bucket: $bucket, key: $key}' > request.json
aws lambda invoke --function-name "$BENCHMARK_FUNCTION" \
  --invocation-type RequestResponse --cli-binary-format raw-in-base64-out \
  --payload file://request.json --log-type Tail response.json > invoke-result.json
cat invoke-result.json
cat response.json
aws logs tail "$BENCHMARK_LOG_GROUP" --since 10m
```

Expected CPU response:

```json
{"recordsProcessed":4000,"checksum":"b1e029a3d2d7974c","status":"OK"}
```

Invoke I/O using the same bucket/key and invocation method:

```bash
jq -n --arg bucket "$BENCHMARK_BUCKET" --arg key dataset.json \
  '{workload: "io", bucket: $bucket, key: $key}' > request.json
aws lambda invoke --function-name "$BENCHMARK_FUNCTION" \
  --invocation-type RequestResponse --cli-binary-format raw-in-base64-out \
  --payload file://request.json --log-type Tail response.json > invoke-result.json
cat invoke-result.json
cat response.json
```

Expected I/O response (JSON property order is irrelevant):

```json
{"checksum":"crc32:1c396adb","status":"OK","objectBytes":191961}
```

Inspect `FunctionError` in `invoke-result.json`: HTTP `StatusCode: 200` alone does
not mean the handler succeeded. Invalid workload/request fields, bad dataset JSON
on the CPU path, incomplete objects, and S3 errors fail the invocation instead of
returning an `OK` response. Repeat the same invoke command
for warm trials; AWS may still choose a new execution environment.

## Automated trials

After native build and deployment (with `--outputs-file outputs.json` from `infra/`),
run from the repository root using Python 3 and AWS CLI v2:

```bash
python3 scripts/run-benchmark.py --region eu-west-2
```

Use the region where you deployed. The runner uses your existing AWS CLI profile
(`AWS_PROFILE`), verifies the local ZIP matches deployed code, uploads the fixed
sample once, and changes memory directly through the Lambda API. It does not
build, deploy, or destroy resources. Deployment outputs must refer to a live stack;
redeploy after cleanup before running. The identity needs permission to upload the
object, read/update Lambda configuration, invoke Lambda, and call STS.

Defaults: seven memory sizes, two repetitions, three warmup calls and 30 collected
calls per workload/memory/repetition (924 total invocations: 7 × 2 workloads × 66 calls). Calls are sequential;
`--interval` sets a fixed pause. Memory and workload batch order reverse on the
second repetition. For a quick smoke test:

```bash
python3 scripts/run-benchmark.py --region eu-west-2 --memories 1024 --samples 2 --warmups 1 --repetitions 1
```

The runner defaults to `eu-west-2`; keep `--region` consistent with the live
stack. It checks the returned function ARN before modifying resources. Old local
CDK outputs may describe a different region; they do not establish the live region.
Before any AWS calls, it prints the region, function, memory configurations,
workloads, expected invocation count, and safety limits. Type `yes` to confirm,
or pass `--yes` for unattended execution.

Safety controls:

- A fixed maximum of **1,000 invocation attempts per execution** includes warmups,
  collected calls and failed attempts. Over-limit configurations are rejected before
  AWS calls. AWS CLI automatic retries are disabled; no replacement calls are added.
  Any future runner retries must use the same guarded invocation path.
- `--max-duration SECONDS` sets total benchmark duration (default **1800 seconds**,
  or 30 minutes), starting after confirmation and including preflight/configuration.
  The runner stops scheduling calls at the deadline and bounds AWS CLI calls by the
  remaining duration. A Lambda already accepted by AWS can continue and be billed
  after the local CLI stops.
- **Five consecutive AWS API/invocation errors** stop invocation collection.
  Successful AWS calls reset the error streak; invalid measurements remain recorded
  separately. Configuration/preflight failures stop immediately rather than proceeding
  with an unverified configuration.
- Press **Ctrl+C** to cancel. Collected results are retained and the runner attempts
  to restore the original Lambda memory in `finally`, before writing summaries.
  Restoration is exempt from the benchmark deadline/error limit; Ctrl+C is ignored
  during restoration so cleanup can finish. Wait for the restoration message and
  results path. Failures are explicitly reported as `RESTORATION FAILED` and in
  `final-summary.json`; check and restore memory manually if needed. A forced kill,
  machine shutdown, or lost AWS permissions can prevent restoration.

The final summary also records the stop reason, invocation attempt count, and any
restoration error. An incomplete run or restoration failure exits with a nonzero
status. These controls limit benchmark activity but **do not enforce a monetary
AWS spending cap**. Other AWS activity, S3, logs, storage and running resources can
still incur charges. AWS Budgets can provide additional billing alerts, but they
are **not immediate hard limits**.

Run local safety tests without AWS access or deployment:

```bash
python3 -m unittest discover -s tests -v
```

Each run writes a new directory under `benchmark-runs/`: identity/configuration
metadata, raw invocation responses and decoded log tails, an append-only
`invocations.jsonl`, and JSON/CSV summaries. Errors are retained in individual rows
and excluded from successful summaries. Summaries separate warmups, collected
samples, cold/warm calls, workload, and memory; percentiles use nearest rank.
Small sample counts, especially for p95/p99, are not sufficient evidence of an optimum.
New runs explicitly describe metrics in `metadata.json` and `final-summary.json`.
The primary AWS summary metric is `durationMs` from AWS REPORT, not Java
`handlerMs`. Existing mean/percentile fields retain their REPORT definitions;
additive `meanHandlerMs`, `p50HandlerMs`, `p95HandlerMs`, `p99HandlerMs` and
`handlerSamples` expose the Java timing separately. Missing handler timings in
older input rows produce null handler statistics, not zero-duration observations.
Combined JSON/CSV summaries remain in their existing files. Additional
`summary-by-repetition.json` and `.csv` files use the same grouping by memory,
workload, phase and cold/warm classification, with a `repetition` field.
Neither summary mixes collected samples with warmups or cold with warm calls.
Percentiles use nearest rank; for even sample counts p50 is the lower middle
observation, not the average of the two middle observations.

For AWS/LocalStack comparisons, use `handlerMs` on both sides, the same memory
setting, and valid warm collected samples from identified runs. LocalStack does
not summarize its emulated REPORT duration as AWS execution duration. The local
default is 132 calls at one memory setting (60 collected per workload plus six
warmups); AWS defaults to the full seven-memory matrix of 924 calls. Both reverse
workload order in repetition two. See the [local measurement guide](localstack/README.md#comparing-measurements-with-aws)
for timer boundaries and Docker resource metadata. Previous results are never
regenerated by running either runner: each execution creates a new results directory.
An unexpected cold call during collection remains classified as cold. This runner
does not force or provide balanced cold-start trials. Log tails may be truncated;
missing application/report measurements are recorded as errors.

The final terminal summary, `final-summary.json`, and `configuration-counts.csv`
report every requested workload/memory configuration, including configurations with
zero calls after an interrupted run. `collected` counts all attempted sample calls;
`warm` and `cold` count only valid successful collected samples; `warmup` counts all
attempted warmup calls. `failed` counts AWS CLI/invocation errors and Lambda
FunctionError responses across both phases. `invalid` counts returned calls with
unusable logs/reports, missing cold/warm classification, or unexpected responses
across both phases. `collectedFailed` and `collectedInvalid` isolate sample-phase
errors, so collected = warm + cold + collectedFailed + collectedInvalid.
Each configuration with fewer than 55 valid warm collected samples gets a warning,
including intentionally small smoke tests. No replacement calls are made and no
controlled cold-start testing is added.

Billed GB-seconds provide a compute-cost basis. Optionally supply the selected
region's ARM64 price with `--gb-second-price` and, if needed, `--request-price`
(USD per request) to add estimated Lambda cost per 1,000 successful calls for each
group. Estimates exclude free allowances, S3, logs, discounts, and other charges.
Caller timing includes local CLI startup. Mixed workload execution environments
still affect memory high-water marks; raw logs preserve AWS memory reports.

The runner restores original memory on completion or normal interruption; forced
termination or AWS errors can prevent restoration. Direct memory updates cause
CloudFormation drift during the run; restoration returns memory to its starting
value. It leaves the uploaded dataset and AWS resources in place. Running trials
incurs AWS usage charges. Keep the ZIP and dataset unchanged throughout.

## Change only memory

For each workload, keep the exact same ZIP, workload value, object bytes/key,
architecture, runtime (`provided.al2023`), region, timeout (60 seconds), invocation
method/pattern, and S3 configuration fixed. Keep SDK retries, bucket encryption,
storage class, and region fixed too; record failures and retries rather than changing
settings for one memory trial. Both workload types use the same ZIP and object.
Do not run a package/native build between memory trials: packaging overwrites the ZIP.
Check the recorded artifact and object SHA-256 before each trial. Change only memory.

```bash
cd infra
cdk deploy JavaBenchmarkStack --parameters MemorySize=256 --outputs-file outputs.json
cd ..
aws lambda wait function-updated-v2 --function-name "$BENCHMARK_FUNCTION"
```

Allowed values are `256`, `512`, `1024`, `1536`, `2048`, and `3072`; the default is
`1024`. These are the CDK parameter values; the Python runner additionally tests
4096 MB through direct Lambda configuration updates. This updates the same function. Wait for each update to finish before
collecting a new trial. Memory changes also change CPU allocation, which is the
intended experimental variable. Separate initial invocations from warm samples.
CPU allocation scales with configured memory ([AWS memory configuration](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html));
that does not establish whether either workload will be faster or cheaper at a
particular setting. The calculation remains sequential and does not add threads
at larger memory sizes.

## Measurements and cost

Each entered handler invocation emits one JSON log with `event=benchmark_invocation`,
request ID, `workload`, `coldStart`, configured `memoryMb`, `objectBytes`, record
count where applicable, checksum, status, error type, and `s3Ms`, `jsonMs`, `cpuMs`,
`handlerMs`. The existing `datasetBytes` field remains an alias for `objectBytes`.
`jsonMs` and logged `recordsProcessed` are `null` on I/O calls, not measurements of
zero duration or zero processed records. On CPU calls, `cpuMs` times the unchanged
calculation; on I/O calls it times only CRC32 verification. `s3Ms` covers the full
SDK GET, byte-array buffering/copy, and Content-Length check, including any SDK
retry time; it is not a pure network-time measurement. Timings use a monotonic
clock. `handlerMs` excludes framework request decoding, response serialization,
log emission, and initialization; it is not Lambda's full duration. `coldStart`
marks the first handler call in that process, not a measurement of startup time.
Requests that fail before entering the handler will only have runtime logs.

Use AWS `REPORT` lines for `Duration`, `Billed Duration`, `Init Duration` (when
reported), and `Max Memory Used`. Join them by request ID to the application logs.
`Init Duration` measures initialization, not the entire caller-observed cold-start
latency. `Max Memory Used` can reflect the execution environment's high-water mark
across warm calls, not independent per-call memory consumption. Heap usage alone
would miss native memory, so the handler deliberately does not label it as total memory.
With a selectable function, a warm I/O call can inherit the high-water mark of
earlier CPU calls in that process. Use log streams to identify execution environments
and record mixed-workload histories when interpreting memory results. Do not compare
a mixed-environment high-water mark as if it were I/O-only memory usage.

Later, compute p50/p95/p99 separately for **each workload and memory size** over a
sufficiently large set of like-for-like samples, separating cold and warm observations
and reporting errors/timeouts separately. Record sample counts and variation; an
individual invocation or outlier does not establish an optimum.
For end-to-end latency, time the synchronous invoke at the caller; it also includes
network/API overhead. A few manual invokes are only a smoke test.

Estimate Lambda on-demand cost using the region's **ARM64** prices:

```text
compute cost = sum((memory_MB / 1024) * (billed_duration_ms / 1000)) * price_per_GB_second
request cost = invocation_count * price_per_request
estimated Lambda cost = compute cost + request cost
estimated Lambda cost per N calls = N * (mean compute cost per call + price_per_request)
```

Apply this separately to each workload/memory group with a stated cold/warm mix.
Cost per N invocations uses the mean billed compute cost, not p50/p95/p99 duration.

Use billed duration, which includes billable initialization, rather than adding
`Init Duration` again. This estimate excludes free tier, tiered pricing, discounts,
S3, CloudWatch, and other account charges. Check [Lambda pricing](https://aws.amazon.com/lambda/pricing/)
for the selected region and [initialization billing](https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/).

Charges can arise from Lambda requests/compute, S3 storage/PUT/GET requests,
CloudWatch log ingestion/storage/queries, and deployment artifacts in the CDK
bootstrap bucket. CDK/CloudFormation/IAM have no separate workload usage fee.
Bootstrap also provisions tooling resources such as an ECR repository; this POC
does not publish images to it. There is no NAT gateway or provisioned concurrency.

### Planned research output (no AWS results yet)

For a stated statistic (for example, warm p50 duration) and a stated cost basis
(for example, mean cost per 1,000 warm invocations), populate:

| Memory | CPU-heavy duration | CPU-heavy cost | I/O-heavy duration | I/O-heavy cost |
| --- | ---: | ---: | ---: | ---: |
| 256 MB | — | — | — | — |
| 512 MB | — | — | — | — |
| 1024 MB | — | — | — | — |
| 1536 MB | — | — | — | — |
| 2048 MB | — | — | — | — |
| 3072 MB | — | — | — | — |

Keep p95, p99, cold-start observations, memory usage, and errors alongside this
summary. Evaluate whether increasing memory materially changes each profile's
duration, identify each workload's fastest and cheapest settings, and assess a
cost/performance trade-off using a stated latency requirement (such as a p95 target).
Only then discuss whether one default memory size is sensible for these profiles.
Do not generalize two synthetic paths to all Java Lambda applications. The 1024 MB
deployment default is a starting point, not a recommendation established by data.

## Cleanup

Stop invoking first. The bucket has versioning disabled. Empty **this stack's**
bucket, then destroy the stack, which deletes the function, execution role, bucket,
bucket policy, and log group. Log data is deleted too.

```bash
BENCHMARK_BUCKET=$(jq -r '.JavaBenchmarkStack.BucketName' infra/outputs.json)
aws s3 rm "s3://$BENCHMARK_BUCKET" --recursive
cd infra
cdk destroy JavaBenchmarkStack
cd ..
```

The stack will fail to delete a nonempty bucket. Keep the native ZIP available
until `cdk destroy` finishes because CDK runs the app to synthesize the stack.

CDK bootstrap resources are shared account/region tooling and are not removed by
`cdk destroy`. On a **dedicated experiment account/region with no other CDK users**,
you can additionally remove the bootstrap artifacts and stack (for the default
`CDKToolkit` name):

```bash
BENCHMARK_TOOLKIT_BUCKET=$(aws cloudformation describe-stacks --stack-name CDKToolkit \
  --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue | [0]' --output text)
aws s3 rm "s3://$BENCHMARK_TOOLKIT_BUCKET" --recursive
# Bootstrap buckets are versioned: remove historical versions and delete markers too.
while true; do
  aws s3api list-object-versions --bucket "$BENCHMARK_TOOLKIT_BUCKET" \
    --max-keys 1000 --no-paginate --output json | \
    jq '{Objects: ([.Versions[]?, .DeleteMarkers[]?] | map({Key, VersionId})), Quiet: true}' \
    > /tmp/benchmark-toolkit-versions.json
  jq -e '.Objects | length > 0' /tmp/benchmark-toolkit-versions.json >/dev/null || break
  aws s3api delete-objects --bucket "$BENCHMARK_TOOLKIT_BUCKET" \
    --delete file:///tmp/benchmark-toolkit-versions.json > /tmp/benchmark-toolkit-delete.json
  jq -e '(.Errors // []) | length == 0' /tmp/benchmark-toolkit-delete.json >/dev/null || break
done
aws cloudformation delete-stack --stack-name CDKToolkit
aws cloudformation wait stack-delete-complete --stack-name CDKToolkit
```

Check for deletion errors before proceeding. If other projects share that bootstrap stack, retain it and manage old assets
through your account's CDK asset lifecycle instead. Do not delete shared assets.

References: [Quarkus Lambda/native packaging](https://quarkus.io/guides/aws-lambda/),
[Quarkus S3 SDK v2 integration](https://docs.quarkiverse.io/quarkus-amazon-services/dev/amazon-s3.html),
[Lambda execution lifecycle](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html).
