# How Much Memory Does a Java Lambda Really Need?

## CPU-heavy vs S3-heavy workloads on AWS Lambda

> **Evidence status (22 October 2026):** Three complete AWS benchmark runs (9, 14 and 19 October) and two LocalStack experiments (14 and 19 October). The findings below concern warm execution and billed Lambda compute consumption; they are not a full pricing analysis or universal production-sizing recommendation.

## Why I started this

Attending AWS Community Summit Birmingham and Manchester in 2026 left me wanting to build something practical. The enthusiasm of [🐔 Guilherme Dalla Rosa](https://www.linkedin.com/in/guidr/), [Matheus das Mercês](https://www.linkedin.com/search/results/people/?keywords=Matheus%20das%20Merc%C3%AAs), [Robin Ford](https://www.linkedin.com/search/results/people/?keywords=Robin%20Ford%20AWS%20Accenture) and [Yan Cui](https://www.linkedin.com/search/results/people/?keywords=Yan%20Cui%20AWS) was particularly infectious. It encouraged me to revisit [Johannes Geiger](https://www.linkedin.com/search/results/people/?keywords=Johannes%20Geiger%20AWS)'s [*AWS Lambdas with Java, revisited*](https://medium.com/@johannesfloriangeiger/aws-lambdas-with-java-revisited-f74e7ed214d5) and ask a slightly different question: **how much memory does a Java Lambda actually need for different workloads?**

Johannes compared ways to run Java on Lambda, including native Quarkus. I wanted to keep the deployment model fixed and explore a different variable: the memory configuration, tested against two distinct workloads.

That became the experiment.

------------------------------------------------------------------------

## Why memory is more interesting than it sounds

Memory configuration in AWS Lambda is not only about how much memory the
application can consume. Increasing the configured memory also increases
the compute resources available to the function.

That means changing a Lambda from 512 MB to 1 GB, for example, can make
it finish faster. But the higher-memory function also has a higher
compute rate while it is running.

So the fastest configuration is not automatically the cheapest one.

And there is another question: does extra compute help every workload
equally?

A function spending most of its execution time performing calculations
may react very differently from one spending most of its time waiting
for S3 or another external service.

That is what I want to measure.

------------------------------------------------------------------------

## A real serverless use case

This is not only a benchmark problem.

Event-driven data processing is a common Lambda pattern. AWS has
published examples of organisations such as Encored Technologies using
Amazon S3 events to trigger Lambda functions that ingest and process
incoming data files.

A simplified version of that pattern looks like:

``` text
S3
 ↓
Lambda
 ↓
read data
 ↓
process / transform
 ↓
result
```

Once this kind of workload runs frequently or at scale, Lambda
configuration becomes a business decision as well as a technical one.

If two functions both process data from S3, should they receive the same
memory configuration simply because they belong to the same application?

My hypothesis is that the nature of the work matters.

The experiment is designed to test that rather than assume it.

------------------------------------------------------------------------

## The experiment

The POC uses:

-   Java 21
-   Quarkus
-   GraalVM/Mandrel native compilation
-   AWS Lambda on ARM64
-   Amazon S3
-   AWS CDK
-   Maven

The same native Lambda artifact is tested at several memory
configurations:

``` text
256 MB
512 MB
1024 MB
1536 MB
2048 MB
3072 MB
4096 MB
```

Instead of comparing frameworks or runtimes, those remain fixed.

The variable is Lambda memory.

The second dimension is the type of workload.

### Workload A: CPU-heavy

The Lambda:

1.  Reads the test dataset from S3.
2.  Deserialises the JSON.
3.  Processes the records.
4.  Performs a deterministic CPU-intensive calculation.
5.  Produces a checksum that can be validated by the benchmark runner.

The calculation performs 8,192 dependent rotate/XOR/multiply rounds per
record. With the current 4,000-record sample dataset, that produces
32,768,000 calculation rounds per invocation.

There are no artificial sleeps, memory-specific branches or deliberate
parallelism.

### Workload B: I/O-heavy

The second workload uses the same general Lambda/S3 architecture but
performs minimal CPU processing after retrieving the object.

The purpose is to create a workload where time spent interacting with S3
is much more significant than computation.

The important point is that I am not going to label either workload CPU-
or I/O-dominated based only on its implementation. The timing
instrumentation will show how much time is actually spent in S3 access,
JSON processing and CPU work in AWS.

------------------------------------------------------------------------

## What is being measured

Each invocation records enough information to separate the major parts
of the handler:

-   S3 time
-   JSON processing time
-   CPU calculation time
-   total handler time
-   configured memory
-   cold-start status
-   records processed
-   checksum
-   workload type

AWS Lambda REPORT data provides the authoritative execution
measurements, including duration, billed duration, initialization
duration where applicable and maximum memory used.

The final comparison will consider:

-   mean/median duration
-   p50 / p95 / p99 (with appropriate caution about sample size)
-   billed duration
-   GB-seconds
-   estimated Lambda compute cost
-   maximum memory used
-   CPU vs S3 contribution to execution time

The goal is not simply to identify the fastest Lambda.

I want to distinguish between:

**fastest**, **cheapest**, and **best performance/cost trade-off**.

------------------------------------------------------------------------

## Benchmark methodology

For each combination of workload and memory configuration, the automated
runner currently performs:

-   6 warm-up calls
-   60 collected calls

The calls are split across two repetitions.

Warm-up calls are not included in the primary warm benchmark.

Every invocation is classified using the application's `coldStart` flag.
If AWS creates a new execution environment during the collected batch,
that invocation is classified separately as a cold start rather than
silently mixing it into the warm measurements.

The experiment does **not** deliberately manufacture cold starts.

This means the experiment is primarily a warm-execution
memory/right-sizing benchmark. Cold starts observed naturally during the
run will be retained and reported separately, but this is not intended
to be a controlled cold-start study.

With seven memory settings and two workloads, the default benchmark is
expected to make:

``` text
66 calls × 2 workloads × 7 memory settings
= 924 Lambda invocations
```

The runner also validates checksums, saves raw results and logs,
alternates workload order, and restores the original Lambda memory
configuration after the experiment.

------------------------------------------------------------------------

## Why Quarkus Native?

Java on Lambda has an obvious topic hanging over it: startup time.

Johannes' experiment explored several approaches to Java Lambda
deployment, including plain Java, SnapStart, container-based deployment
and native Quarkus.

For this experiment I deliberately do not want framework/startup
differences to become another independent variable.

Using a native Quarkus Lambda gives me one consistent Java deployment
model while I vary memory and workload.

That keeps the main question focused:

> **Given the same Java Lambda implementation, how does memory
> allocation behave when the work changes?**

------------------------------------------------------------------------

## What do I expect?

A reasonable expectation is that the CPU-heavy workload may continue
benefiting from additional Lambda memory for longer because additional
memory also brings additional compute capacity.

The I/O-heavy workload may reach a point where more compute provides
little improvement because the Lambda is predominantly waiting on S3.

But those are hypotheses.

The measurements need to decide whether they are actually true, where
any plateau occurs, and whether the fastest configuration is
economically sensible.

------------------------------------------------------------------------

# First complete AWS benchmark: results (9 October 2026)

> **Preliminary findings from one full run, not final conclusions.** These values are from the benchmark runner summary supplied after execution. The raw logs and full results archive should be retained alongside this article for reproducibility.

Latency statistics in this first-run section use AWS REPORT Duration, not Java handler time.

The runner reported **924 valid invocations**, no failed or invalid responses, and valid checksums throughout. Every one of the 14 memory/workload combinations had **60 warm collected samples and six warmups**. The 14 cold starts all occurred during warmup. The original Lambda memory setting (1024 MB) was restored successfully.

## CPU-heavy workload

| Memory | Warm samples | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Mean billed GB-seconds |
|---:|---:|---:|---:|---:|---:|---:|
| 256 MB | 60 | 772.23 | 799.29 | 836.05 | 877.58 | 0.193179 |
| 512 MB | 60 | 399.82 | 407.66 | 440.48 | 475.90 | 0.200142 |
| 1024 MB | 60 | 230.08 | 228.87 | 244.32 | 254.90 | 0.230567 |
| 1536 MB | 60 | 143.80 | 142.25 | 155.99 | 159.38 | 0.216475 |
| 2048 MB | 60 | 125.36 | 124.64 | 133.94 | 141.06 | 0.251667 |
| 3072 MB | 60 | 112.40 | 112.14 | 119.27 | 131.86 | 0.338800 |
| 4096 MB | 60 | 112.10 | 112.08 | 118.86 | 122.67 | 0.450467 |

**Initial observation:** Moving from 1024 to 1536 MB reduced mean CPU-heavy latency by approximately **37.5%**, while reducing billed GB-seconds by approximately **6.1%**. This is an example where more memory delivered both lower latency and lower billed compute consumption. However, 1536 MB is **not** the absolute cheapest setting: 256 MB had the lowest billed GB-seconds, at much higher latency. Between 3072 and 4096 MB, mean execution time barely changed.

## I/O-heavy workload

| Memory | Warm samples | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Mean billed GB-seconds |
|---:|---:|---:|---:|---:|---:|---:|
| 256 MB | 60 | 69.93 | 65.79 | 95.62 | 133.83 | 0.017613 |
| 512 MB | 60 | 43.52 | 42.67 | 60.07 | 69.55 | 0.022017 |
| 1024 MB | 60 | 35.39 | 35.14 | 43.28 | 49.55 | 0.035900 |
| 1536 MB | 60 | 33.34 | 32.95 | 39.31 | 58.04 | 0.050775 |
| 2048 MB | 60 | 31.69 | 31.89 | 40.50 | 43.32 | 0.064467 |
| 3072 MB | 60 | 34.64 | 33.14 | 40.81 | 75.81 | 0.105500 |
| 4096 MB | 60 | 32.28 | 31.16 | 40.68 | 51.52 | 0.131133 |

**Initial observation:** I/O-heavy mean latency largely flattened after 1024 MB. Moving from 1024 to 4096 MB reduced mean latency by about **8.8%**, while increasing billed GB-seconds by approximately **265%**. The run report indicates that S3 reads dominate this workload; the detailed handler timing breakdown should be checked before publication. The fastest mean observed here was at 2048 MB, but 1024 MB looks like a plausible latency/cost compromise, depending on service requirements.

## What does this mean?

The two workloads reacted differently to the same memory settings. The CPU-heavy workload continued benefiting materially from additional compute resources over a wider range. The I/O-heavy workload reached diminishing returns sooner.

**Working interpretation, not a final recommendation:**

- Lowest billed compute consumption: **256 MB** for both workloads, but with greater latency.
- CPU-heavy latency/cost compromise worth examining: **1536 MB**.
- I/O-heavy latency/cost compromise worth examining: **1024 MB**.
- Fastest observed mean: **4096 MB CPU** (virtually tied with 3072 MB); **2048 MB I/O**.

Actual dollar costs have **not** yet been calculated. GB-seconds reflect Lambda compute consumption, not the entire AWS bill (requests, S3, logging and other costs are separate). With 60 samples per configuration, p99 values should be treated as descriptive rather than strong tail-latency evidence. The two repetitions reportedly varied noticeably at lower memory settings.

## Before drawing conclusions

1. Repeat the full run, ideally on another day, and compare the runs.
2. Inspect the two repetitions independently, particularly at 256 and 512 MB.
3. Confirm the S3/JSON/CPU timing proportions from detailed handler logs.
4. Calculate compute and request cost using the correct AWS region, architecture, pricing and free-tier assumptions; keep S3 and CloudWatch costs distinct.
5. Preserve raw results, checksums, environment details, deployment artifact hash and runner version.
6. Avoid controlled cold-start claims: the 14 observed cold invocations were warmup calls, not a cold-start benchmark.

# Replication: results (14 October 2026)

The full matrix was repeated in `eu-west-2` with the same native ZIP and dataset hashes as 9 October, using the same sequential invocation pattern, warmups, sample counts and reversed batch order. Raw results are in [the replication run](benchmark-runs/20261014T091601316296Z/summary.csv), with [completion and restoration details](benchmark-runs/20261014T091601316296Z/final-summary.json). The original run is retained separately.

All **924 invocations were valid**, with no failed or invalid responses. Each configuration had **60 warm collected samples and six warmups**. All **14 cold starts** occurred during warmup. The original **1024 MB** memory setting was restored successfully.

The table compares warm means between runs. Percent changes describe the second run relative to the first; p95 and billed GB-seconds are from the replication.

| Workload | Memory (MB) | 9 Oct mean (ms) | 14 Oct mean (ms) | Change | 14 Oct p95 (ms) | Mean billed GB-seconds |
|---|---:|---:|---:|---:|---:|---:|
| cpu | 256 | 772.23 | 688.90 | -10.8% | 722.05 | 0.172367 |
| cpu | 512 | 399.82 | 371.57 | -7.1% | 382.38 | 0.186033 |
| cpu | 1024 | 230.08 | 199.90 | -13.1% | 211.54 | 0.200383 |
| cpu | 1536 | 143.80 | 145.79 | +1.4% | 155.56 | 0.219375 |
| cpu | 2048 | 125.36 | 125.71 | +0.3% | 134.69 | 0.252467 |
| cpu | 3072 | 112.40 | 114.03 | +1.5% | 122.02 | 0.343700 |
| cpu | 4096 | 112.10 | 113.88 | +1.6% | 121.23 | 0.457667 |
| io | 256 | 69.93 | 58.07 | -17.0% | 74.47 | 0.014642 |
| io | 512 | 43.52 | 46.38 | +6.6% | 58.34 | 0.023417 |
| io | 1024 | 35.39 | 35.43 | +0.1% | 42.42 | 0.035883 |
| io | 1536 | 33.34 | 34.54 | +3.6% | 41.02 | 0.052450 |
| io | 2048 | 31.69 | 34.74 | +9.6% | 41.96 | 0.070467 |
| io | 3072 | 34.64 | 34.29 | -1.0% | 42.30 | 0.104450 |
| io | 4096 | 32.28 | 36.58 | +13.3% | 42.97 | 0.148400 |

The broad pattern repeated: CPU execution continued improving up to 3072 MB and barely changed at 4096 MB; I/O mean latency stayed around 34–37 ms from 1024 MB upward. However, the earlier CPU cost improvement from 1024 to 1536 MB **did not repeat**. This time mean latency fell from 199.90 to 145.79 ms (27.1%), while billed compute rose from 0.200383 to 0.219375 GB-seconds (9.5%). The article's first-run observation remains true for that run, but does not establish a repeatable cost saving at 1536 MB.

At 256 MB, CPU mean latency was 10.8% lower and I/O mean latency was 17.0% lower than on 9 October. Within this replication, the two 256 MB I/O repetition means were 49.87 and 66.27 ms. This variation argues for retaining separate repetition results and avoiding a precise optimum based on one batch. At 256 MB, billed compute consumption was again lowest for both workloads.

Detailed warm handler logs support the workload separation. Across memory settings, mean I/O S3 time ranged from 32.93 to 38.99 ms and CRC32 processing averaged about 0.08 ms. S3 accounted for over 99% of mean measured I/O handler time in each configuration. These handler timings exclude some overhead present in AWS's reported duration. On the CPU path, mean calculation time fell from 600.98 ms at 256 MB to 76.20 ms at 3072 MB and 76.12 ms at 4096 MB; mean S3 time remained approximately 32–36 ms.

These are two full runs of this fixed small-object experiment. Dollar-cost analysis and final conclusions remain pending, and the warmup cold starts still do not constitute a controlled cold-start study.

# Third AWS run: results (19 October 2026)

The full seven-memory matrix was repeated in `eu-west-2` with the same native ZIP and dataset SHA-256 values as both earlier runs. Reporting now explicitly distinguishes Java handler time from AWS REPORT duration and includes separate repetition summaries; the application and workload algorithms were unchanged.

All **924 invocations were valid**, with no failed or invalid measurements. Each workload/memory configuration had **60 warm collected samples and six warmups**. All **14 cold starts** occurred during warmup. The runner restored the original **1024 MB** memory configuration successfully.

Sources: [combined AWS summary](benchmark-runs/20261019T081929658746Z/summary.json), [per-repetition summary](benchmark-runs/20261019T081929658746Z/summary-by-repetition.json), [raw measurements](benchmark-runs/20261019T081929658746Z/invocations.jsonl), and [completion/restoration record](benchmark-runs/20261019T081929658746Z/final-summary.json).

The following latency columns all use **AWS REPORT Duration for valid warm collected calls**. They do not use Java `handlerMs`. Each mean represents 60 samples per configuration on that date. Billed GB-seconds are warm-sample compute consumption, not total dollar cost or a cold-inclusive production estimate.

| Workload | Memory (MB) | 9 Oct mean (ms) | 14 Oct mean (ms) | 19 Oct mean (ms) | 19 Oct p95 (ms) | 19 Oct mean billed GB-seconds |
|---|---:|---:|---:|---:|---:|---:|
| cpu | 256 | 772.23 | 688.90 | 717.18 | 743.54 | 0.179413 |
| cpu | 512 | 399.82 | 371.57 | 370.25 | 397.00 | 0.185342 |
| cpu | 1024 | 230.08 | 199.90 | 196.91 | 208.39 | 0.197433 |
| cpu | 1536 | 143.80 | 145.79 | 162.45 | 190.29 | 0.244525 |
| cpu | 2048 | 125.36 | 125.71 | 126.41 | 135.32 | 0.253733 |
| cpu | 3072 | 112.40 | 114.03 | 112.93 | 121.23 | 0.340150 |
| cpu | 4096 | 112.10 | 113.88 | 113.84 | 120.81 | 0.457333 |
| io | 256 | 69.93 | 58.07 | 66.83 | 91.75 | 0.016829 |
| io | 512 | 43.52 | 46.38 | 43.82 | 54.20 | 0.022183 |
| io | 1024 | 35.39 | 35.43 | 33.69 | 39.69 | 0.034150 |
| io | 1536 | 33.34 | 34.54 | 35.43 | 42.04 | 0.053900 |
| io | 2048 | 31.69 | 34.74 | 32.75 | 39.36 | 0.066367 |
| io | 3072 | 34.64 | 34.29 | 33.53 | 42.48 | 0.101950 |
| io | 4096 | 32.28 | 36.58 | 38.49 | 41.02 | 0.156133 |

## What repeated, and what did not

- **The CPU plateau repeated.** CPU mean REPORT duration was 112.93 ms at 3072 MB and 113.84 ms at 4096 MB. These are descriptive batch means, not evidence that one of those nearly tied settings is a universal optimum. The calculation is sequential; additional allocated resources do not make it use multiple calculation threads.
- **The I/O plateau remained broad.** From 1024 MB upward, means ranged from 32.75 to 38.49 ms. At 4096 MB, the mean was 38.49 ms but p95 was 41.02 ms and the maximum was 249.52 ms. That isolated large observation matters for the mean; this is not proof that increasing memory systematically slows S3 access.
- **The 1536 MB cost saving was not robust.** On 19 October, moving CPU from 1024 to 1536 MB reduced mean REPORT duration by 17.5%, but increased mean billed compute by 23.9% (0.197433 to 0.244525 GB-seconds). The two 1536 MB repetition means were 180.84 and 144.05 ms. The cause of that batch difference is not established by the recorded evidence. The first run's 6.1% saving remains an observation from that run, not a repeatable recommendation.
- **256 MB again had the lowest mean billed compute consumption** for both workloads among tested settings, at substantially higher execution latency. This does not establish a production optimum without a latency requirement and workload frequency/cold-start assumptions.

At 1024 MB, the new CPU mean REPORT duration was **196.91 ms**, while the same calls' mean Java handler time was **192.84 ms**. The first run's **230.08 ms** was REPORT duration on 9 October; the earlier LocalStack comparison used **196.08 ms of handler time from 14 October**. Those two historical numbers differed in both run and timing boundary. Like-for-like REPORT means across the three dates are **230.08, 199.90 and 196.91 ms**.

Three separate days strengthen the broad workload-dependent pattern, but do not remove batch/environment variation. Means and percentiles should remain identified by run. With 60 observations, nearest-rank p99 is the sample maximum, so it remains weak tail-latency evidence. Dollar pricing and final production recommendations are still pending.

# LocalStack experiment: functional agreement, different performance conditions

The local S3/Lambda flow has now run successfully twice on Apple Silicon using the **same native ARM64 ZIP and unchanged dataset as AWS**. No alternate Java implementation or LocalStack-specific executable was built. The first local run on 14 October collected ten warm samples per workload. The repeat on 19 October used **two repetitions of 30 collected calls and three warmups per workload**, matching AWS's per-memory sample design.

The 19 October local run completed **132 valid invocations**, with **60 warm collected samples and six warmups per workload**, no failures and no cleanup errors. Its one cold invocation occurred during the first CPU warmup. All response shapes and checksums matched the expected fixture results. The local function and bucket were removed by the runner, and Compose was stopped after collection. All earlier evidence was retained.

Sources: [local combined and repetition summaries](localstack/results/20261019T082816425083Z/summary.json), [raw measurements](localstack/results/20261019T082816425083Z/invocations.jsonl), and [environment metadata](localstack/results/20261019T082816425083Z/metadata.public.json).

## Compare the same timing boundary

Both columns below use **Java handler elapsed time**, not AWS REPORT duration, LocalStack's emulated REPORT fields, or client/CLI elapsed time. All are valid warm collected samples at configured 1024 MB.

| Environment/date | Workload | Warm samples | Mean handler (ms) | p50 handler (ms) | p95 handler (ms) |
|---|---|---:|---:|---:|---:|
| AWS, 19 Oct | cpu | 60 | 192.84 | 192.54 | 206.42 |
| AWS, 19 Oct | io | 60 | 32.41 | 33.10 | 38.48 |
| LocalStack, 19 Oct | cpu | 60 | 87.92 | 88.95 | 94.07 |
| LocalStack, 19 Oct | io | 60 | 6.09 | 5.87 | 8.05 |
| LocalStack, 14 Oct | cpu | 10 | 85.73 | 85.90 | 93.54 |
| LocalStack, 14 Oct | io | 10 | 10.44 | 6.88 | 28.50 |

Percentiles use nearest rank; p50 is the lower middle observation for even sample counts. The first local run had fewer samples and fewer warmups, so differences between the two local runs cannot be attributed solely to the day or an emulator change. The pinned LocalStack release remained the same.

The two new local repetition mean handler times were **87.92 and 87.92 ms for CPU**, and **6.12 and 6.06 ms for I/O**. This batch agreement is useful, but two batches sharing a local execution environment are not independent hardware/environment replications. The first local I/O mean of 10.44 ms came from only ten warm observations and appreciable variation; the new 6.09 ms mean is not evidence of a general LocalStack performance improvement.

The measured phase shares below are sums of phase elapsed times divided by sums of handler elapsed times, over the new warm samples. I/O has no dataset JSON phase; its processing phase is CRC32, not the CPU calculation.

| Environment | Workload | S3 phase | JSON phase | Calculation / CRC32 phase |
|---|---|---:|---:|---:|
| AWS | cpu | 16.69% | 1.73% | 81.58% |
| AWS | io | 99.74% | Not performed | 0.26% |
| LocalStack | cpu | 7.10% | 3.57% | 89.33% |
| LocalStack | io | 98.19% | Not performed | 1.78% |

This supports describing the workloads as **calculation-heavy** and **S3-access-heavy** in both environments. `s3Ms` includes SDK processing, buffering and Content-Length validation as well as transfer and any SDK retries; it is not pure network wait. All phase measurements are elapsed wall time, not CPU-utilization measurements.

## New environment evidence: configured memory was not a matching resource budget

The 19 October metadata records macOS on ARM64, Docker client/server **29.7.2**, and a Docker Desktop Linux daemon with **six CPUs and 4,106,870,784 bytes of memory (about 3.82 GiB)**. LocalStack used the pinned ARM64 `2026.09.0` image, with manifest digest `sha256:801a3dff7f6a23857e7310b7602e67d52a29dfdcb03e09f7c608d5c57d24b792`.

All four Lambda-container snapshots, associated by the exact function name, recorded **zero NanoCPUs, zero CPU quota/period, empty CPU affinity and zero container memory limit**. Docker therefore configured no explicit per-container CPU quota or memory cap through those fields in this experiment. The application still reported configured Lambda memory of **1024 MB**. This is not unlimited hardware: the container shared the Docker VM and host resources, and the snapshots do not measure utilization or all inherited system constraints.

This is direct evidence that matching the configured Lambda memory value did **not** establish equivalent resource constraints. It helps explain why local performance cannot be used for AWS sizing, but does not isolate every cause of the timing difference. The same ARM64 instruction set does not make Apple Silicon and AWS execution hardware identical.

The Lambda used an explicit local HTTP S3 endpoint with path-style addressing, while AWS used the real regional S3 HTTPS path. The local IAM role was a placeholder, and this run did not validate real IAM enforcement, S3 TLS policies, production scaling, S3 event delivery or regional latency. Only one local memory setting was tested. Neither experiment deliberately balanced cold-start trials, so their warmup cold observations are not a production cold-start comparison.

**What the comparison demonstrates:** LocalStack can execute this unchanged native application and exercise the S3/Lambda integration with identical functional results. It reproduced the qualitative distinction between calculation-heavy and S3-access-heavy work. It did not reproduce AWS latency or establish a local predictor for AWS memory/cost decisions. AWS remains necessary for production performance measurements; LocalStack provides useful local functional feedback.

------------------------------------------------------------------------

# What surprised me?

The most useful surprise was the instability of a tempting cost-saving story: 1536 MB reduced CPU billed compute relative to 1024 MB in the first run, but not in either subsequent run. Keeping repetitions separate also exposed a substantial 1536 MB batch difference on 19 October.

The new local metadata was equally useful: the application reported 1024 MB while Docker applied no explicit per-container CPU quota or memory cap through its recorded limit fields. Functional equivalence was real; equivalent resource allocation was not established.

------------------------------------------------------------------------

# Conclusion

The results support **workload-dependent Lambda memory sizing**, but not a universal memory recommendation.

The CPU-heavy path benefited substantially from increasing memory, with mean warm AWS REPORT duration falling sharply from 256 MB to 3072 MB and then levelling off. The S3-heavy path reached diminishing returns much earlier, around 1024 MB. For a small-object S3 read, additional allocated compute did not consistently shorten the external-service-dominated part of the request.

The cost result was less straightforward. Increasing the CPU workload from 1024 to 1536 MB reduced mean duration on all three AWS days, but reduced billed GB-seconds only on 9 October. The 14 and 19 October runs instead recorded increases of 9.5% and 23.9%. Across the tested configurations, 256 MB consumed the fewest mean billed GB-seconds for both workloads, at the expense of substantially higher latency. **The fastest configuration was not necessarily the cheapest, and one promising run was not sufficient evidence of a repeatable saving.**

LocalStack added a different kind of confidence. The unchanged native ARM64 application and dataset produced matching functional results locally, making it useful for checking the Lambda/S3 integration and correctness. But configured memory did not imply equivalent CPU and memory constraints, and local handler timings were not predictive of AWS latency. Performance and cost decisions still need measurements in AWS.

**What I would do next:**

- Define a realistic latency target and invocation volume before choosing a memory configuration.
- Repeat promising memory settings across separate batches and days, retaining per-run variation instead of averaging away differences.
- Calculate full workload cost using region-specific Lambda pricing, requests, S3 and logging, and account for cold-start frequency where relevant.
- Test a larger or more varied dataset, and consider concurrency and controlled cold starts as separate experiments.

**Practical takeaway:** Benchmark the actual workload against both latency requirements and billed compute. Use LocalStack to validate behaviour, and AWS to validate production performance. There is no universal Lambda memory winner.

------------------------------------------------------------------------

## References and further reading

-   [Johannes Geiger, *AWS Lambdas with Java, revisited*](https://medium.com/@johannesfloriangeiger/aws-lambdas-with-java-revisited-f74e7ed214d5)
-   AWS Lambda memory configuration documentation
-   AWS Compute Blog, *Understanding techniques to reduce AWS Lambda
    costs in serverless applications*
-   AWS Compute Blog, *Optimizing your AWS Lambda costs -- Part 1*
-   AWS Compute Blog, *Optimizing AWS Lambda function performance for
    Java*
-   AWS material on Quarkus/GraalVM native Java Lambda
-   Encored Technologies serverless event-driven data pipeline case
    study
-   Relevant Yan Cui material/discussion on local testing of serverless
    applications

> **Scope note:** No total-dollar cost or final production memory optimum is claimed here. The LinkedIn people-search URLs above are search links, not verified individual profile URLs, except for Guilherme Dalla Rosa.
