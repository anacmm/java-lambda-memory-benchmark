# Third AWS run: results (19 October 2026)

The full seven-memory matrix was repeated in `eu-west-2` with the same native ZIP and dataset SHA-256 values as both earlier runs. Reporting now explicitly distinguishes Java handler time from AWS REPORT duration and includes separate repetition summaries; the application and workload algorithms were unchanged.

All **924 invocations were valid**, with no failed or invalid measurements. Each workload/memory configuration had **60 warm collected samples and six warmups**. All **14 cold starts** occurred during warmup. The runner restored the original **1024 MB** memory configuration successfully.

Sources: [combined AWS summary](summary.json), [per-repetition summary](summary-by-repetition.json), [raw measurements](invocations.jsonl), and [completion/restoration record](final-summary.json).

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

Sources: [local combined and repetition summaries](../../localstack/results/20261019T082816425083Z/summary.json), [raw measurements](../../localstack/results/20261019T082816425083Z/invocations.jsonl), and [environment metadata](../../localstack/results/20261019T082816425083Z/metadata.json).

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

