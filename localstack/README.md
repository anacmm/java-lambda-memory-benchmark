# LocalStack development experiment

This is a separate integration experiment using the existing Quarkus Native ARM64
ZIP and the exact AWS dataset. The AWS Java sources, CDK stack, build process,
native artifact, article and existing `benchmark-runs/` remain unchanged. Runner
reporting is additive; invocation and workload behaviour are preserved.

## Repository findings and adaptations

The handler selects `cpu` or `io` from the request. Both download the complete S3
object through the same retained SDK v2 synchronous client and validate its
Content-Length. CPU parses Jackson JSON and executes the fixed calculation; I/O
computes CRC32. Dependencies and algorithms are unchanged.

The existing build produces a Linux ARM64 ELF in `lambda/target/function.zip`,
alongside `bootstrap` and `cacerts`. The bootstrap launches `runner` in `/var/task`;
Quarkus supplies the Lambda Runtime API client. The artifact already targets
`provided.al2023`, so no custom Dockerfile, alternate binary or native rebuild is
needed. LocalStack launches the ARM64 Lambda runtime container; Compose runs the
ARM64 emulator. Both containers share `java-benchmark-local` so the function can
reach S3 at `http://localstack:4566`. `localhost` inside Lambda would point to the
Lambda container itself.

Local-only runtime environment variables select the S3 endpoint, region and
path-style bucket addressing. They do not change application code or the ZIP.
The host AWS CLI always uses `http://127.0.0.1:4566` and dummy credentials; it does
not read your AWS profile or deployment outputs. No CDK deployment is performed.
The local role ARN is a placeholder for emulation, not an IAM-policy test.

The AWS CDK bucket requires TLS. This separate local bucket uses HTTP within the
Docker network, so this experiment does not verify real S3 TLS or bucket policies.

## Start and run

Requirements: Docker Desktop running Linux containers, Docker Compose, AWS CLI v2,
Python 3, the existing native ZIP, and a LocalStack auth token with Lambda/S3 access.
The image is pinned to release `2026.09.0` and its multi-platform manifest digest.
Current LocalStack releases require activation; no paid signup is performed here.

Set `LOCALSTACK_AUTH_TOKEN` in your terminal, or put it in `localstack/.env`
(ignored by this directory's `.gitignore`). Do not put the token in tracked files.
The LocalStack token activates the emulator; AWS API calls still use dummy `test`
credentials. Compose reads `.env`; the Python runner does not need the token.

From the repository root:

```bash
docker compose -f localstack/compose.yaml up -d --wait --wait-timeout 180
python3 localstack/run.py
```

The default is **132 sequential invocations**: two workloads, two repetitions,
and three warmups plus 30 collected calls per batch. This gives **60 collected
calls and six warmups per workload**, matching AWS's per-memory methodology.
Workload order reverses on repetition two. All invocations are validated,
including warmups. Unexpected collected cold calls remain classified separately,
so 60 collected calls do not guarantee 60 valid warm samples. For one call per workload:

```bash
python3 localstack/run.py --samples 1 --warmups 0 --repetitions 1
```

The explicit equivalent of the defaults is:

```bash
python3 localstack/run.py --samples 30 --warmups 3 --repetitions 2
```

`--memory` defaults to 1024 MB. It sets local Lambda configuration only. It does
not recreate AWS's CPU-to-memory relationship; a local sweep cannot establish AWS
right-sizing. Runs use unique local bucket/function names. The runner deletes
only its own local resources afterwards, including on normal failures. Raw results
remain on disk. Cleanup errors are reported in the summary and produce a nonzero
exit. A forced kill can leave local resources until Compose is stopped.

Stop the separate environment:

```bash
docker compose -f localstack/compose.yaml down
```

The environment is ephemeral (`PERSISTENCE=0`); stopping it discards local cloud
state. It does not delete the recorded results or contact the AWS deployment.

## Checks and evidence

Each run writes a new `localstack/results/<UTC timestamp>/` directory:

- Source artifact/dataset SHA-256, LocalStack health/version, host and arguments.
- Explicit host architecture and OS; Docker client/server versions and daemon CPU
  count/total memory. With local Docker Desktop, these describe resources visible
  to its Linux VM, rather than physical Mac RAM or observed container utilization.
- Compose LocalStack container image reference, image ID, architecture and repository
  digests. The existing LocalStack health metadata retains the emulator version.
- Lambda container snapshots associated by exact `AWS_LAMBDA_FUNCTION_NAME`, taken
  after the first invocation of each batch, outside the invocation timer. Snapshots
  record image ID/reference, NanoCPUs, CPU quota/period, CPU shares, CPU affinity,
  memory limit/reservation and swap settings. They observe those containers at those
  instants; they are not continuous resource monitoring or utilization measurements.
- A downloaded copy of the local S3 object, checked against the original SHA-256.
- Raw request, response, invocation metadata and decoded log tail for each call.
- Append-only invocation rows and a final summary, including errors and cleanup,
  combined `workloads` and separate `repetitions[].workloads` statistics.

Docker collection is best-effort: missing permissions, absent containers or query
failures are explicitly recorded as warnings/unavailable fields without failing
the experiment. Full container environments are never archived. Keep competing
host activity and Docker resource allocation fixed when comparing future runs.
The current Docker context selects the daemon; a remote daemon's values do not
describe your Mac's VM.

Interpret resource fields using Docker semantics: `nanoCpus / 1e9` gives a CPU
limit when positive; a positive `cpuQuota / cpuPeriod` gives a quota in CPUs.
Zero NanoCPUs and zero/negative quota mean no explicit limit from those fields,
not unlimited physical CPU. CPU shares are relative weights, not a hard quota.
Zero memory bytes means no explicit container memory cap; VM/host constraints
still apply. A zero reservation is no reservation, not zero available memory.
See [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/).

CPU must return exactly 4,000 records, checksum `b1e029a3d2d7974c`, and status `OK`.
I/O must return exactly 191,961 bytes, checksum `crc32:1c396adb`, and status `OK`.
The dataset SHA-256 must be
`2939695c8e099f3d73ea84e17069dc7cbae9304be72972d0be0f5f1b698fa10e`.
HTTP 200 alone is not success: `FunctionError`, response shape, application log
configuration, checksums and timing fields are validated. The ZIP is checked for
Linux ARM64 before any local AWS API call and compared to the deployed code hash.

Warm summaries exclude warmups, failed calls and collected cold invocations.
They describe `s3Ms`, `cpuMs`, `handlerMs` and CLI round-trip `callerMs`. LocalStack
REPORT/billing fields are not treated as real AWS execution duration or cost.
Cold flags describe first invocation of this application process; they do not
establish production cold-start latency.

## Comparing measurements with AWS

Both runners now include `measurementMetrics` descriptions in run metadata and
final summaries. Local summary `primaryMetric` is `handlerMs`; AWS summary rows
identify `durationMs` as primary and retain their original REPORT-based mean and
percentile fields. AWS also adds `meanHandlerMs`, `p50HandlerMs`, `p95HandlerMs`,
`p99HandlerMs` and `handlerSamples`, so comparisons can use handler time on both
sides without confusing it with REPORT duration.

| Metric | Boundary and interpretation |
| --- | --- |
| `handlerMs` | Java handler entry to the timestamp before measurement-log construction/emission; excludes framework request decoding, response serialization and pre-handler initialization |
| `s3Ms` | Complete SDK GET, buffering/copying and Content-Length check, including any SDK retries; not pure network time |
| `jsonMs` | Dataset JSON deserialization; null for I/O because the phase is not performed |
| `cpuMs` | Elapsed calculation or CRC32 phase, not CPU utilization |
| AWS `durationMs` | Parsed AWS REPORT Duration; broader than the Java handler timer |
| AWS `billedMs` | Parsed REPORT Billed Duration; includes applicable initialization and billing rounding |
| `callerMs` | Python elapsed time including AWS CLI startup, invocation and local file/log processing; local also writes its request file inside this timer |

Use the same metric, memory setting, phase and cold/warm classification when
comparing runs. `Init Duration` remains in raw logs, separate from handler time.
LocalStack REPORT/billing/memory values are emulated and are not production cost
or measured AWS resource evidence. Matching configured memory does not establish
matching CPU allocation; use the new container metadata to describe local limits.

Percentiles use nearest rank: `p50` selects the lower middle observation for even
sample counts, rather than averaging the two middle observations. Separate
repetition statistics expose batch variation; calls within a shared process are
not independent execution-environment replications. Both runners keep existing
combined summaries and add repetition reporting without rewriting earlier runs.

The local CLI uses a fixed loopback endpoint, dummy credentials, empty AWS config
files and no inherited AWS endpoint/profile/container-credential settings. Proxy
variables are removed and the health check refuses redirects. The Lambda uses
the explicit local S3 endpoint. There is no option to substitute a real AWS endpoint.

Run the local isolation/validation tests without Docker or AWS:

```bash
python3 -m unittest discover -s localstack -p 'test_*.py' -v
python3 -m unittest discover -s tests -v
```

## What this can answer

This tests native startup, Lambda request/response serialization, S3 endpoint
configuration, container networking, full-object retrieval and unchanged workload
results. It can expose packaging and integration problems and provide repeatable
local development feedback. Timing proportions may differ because local S3 has
no AWS network path and containers share the Mac's CPU and Docker VM resources.

It cannot establish AWS latency, memory optima, billing, IAM enforcement, TLS policy,
production scaling or infrastructure parity. The AWS results remain the evidence
for those performance questions. Keep all local data distinct from `benchmark-runs/`.

## Troubleshooting ARM64 and activation

Use `docker compose -f localstack/compose.yaml logs localstack` for startup failures
and inspect activation before interpreting errors as native incompatibility.
If Lambda fails initialization, check its raw response/logs and reported state.
The runtime must be `provided.al2023`, architecture `arm64`, and the ZIP must contain
an executable bootstrap and runner. The Lambda container must join the named network.

`exec format error` points to executable/platform mismatch; missing ELF interpreter
or shared libraries points to runtime OS compatibility. A failure reaching S3 is
a different problem: inspect the endpoint/network and path-style setting. Do not
rebuild or overwrite the AWS artifact merely because local deployment fails.
Any genuinely necessary alternative artifact should be built in a separate copied
project/output location and identified as a different build in the results.

## Sources

- [LocalStack ARM64 support](https://docs.localstack.cloud/aws/customization/advanced/arm64-support/)
- [LocalStack Lambda execution](https://docs.localstack.cloud/aws/services/lambda/)
- [LocalStack installation and activation](https://docs.localstack.cloud/aws/getting-started/installation/)
- [LocalStack 2026.09.0 release](https://blog.localstack.cloud/localstack-for-aws-release-2026-09-0/)
- [Quarkus S3 configuration](https://docs.quarkiverse.io/quarkus-amazon-services/3.23.x/amazon-s3.html)
