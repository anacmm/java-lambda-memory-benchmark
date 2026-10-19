# Replication: results (14 October 2026)

The full matrix was repeated in `eu-west-2` with the same native ZIP and dataset hashes as 9 October, using the same sequential invocation pattern, warmups, sample counts and reversed batch order. Raw results are in [the replication run](summary.csv), with [completion and restoration details](final-summary.json). The original run is retained separately.

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

## Per-repetition means and handler timings

| Workload | Memory (MB) | Rep 1 mean (ms) | Rep 2 mean (ms) | Mean S3 (ms) | Mean JSON (ms) | Mean processing (ms) | Mean handler (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| cpu | 256 | 667.70 | 710.10 | 35.79 | 14.13 | 600.98 | 650.91 |
| io | 256 | 49.87 | 66.27 | 38.99 | — | 0.08 | 39.07 |
| cpu | 512 | 374.31 | 368.83 | 35.13 | 7.64 | 310.28 | 353.05 |
| io | 512 | 44.40 | 48.36 | 35.84 | — | 0.08 | 35.92 |
| cpu | 1024 | 200.75 | 199.04 | 33.97 | 3.53 | 158.58 | 196.08 |
| io | 1024 | 33.88 | 36.99 | 34.03 | — | 0.08 | 34.12 |
| cpu | 1536 | 145.76 | 145.82 | 33.39 | 3.37 | 106.00 | 142.77 |
| io | 1536 | 33.81 | 35.27 | 33.18 | — | 0.08 | 33.27 |
| cpu | 2048 | 126.31 | 125.11 | 32.09 | 3.47 | 86.37 | 121.93 |
| io | 2048 | 34.38 | 35.11 | 33.34 | — | 0.08 | 33.42 |
| cpu | 3072 | 116.85 | 111.22 | 33.09 | 3.35 | 76.20 | 112.65 |
| io | 3072 | 33.30 | 35.29 | 32.93 | — | 0.08 | 33.02 |
| cpu | 4096 | 115.90 | 111.86 | 33.13 | 3.32 | 76.12 | 112.56 |
| io | 4096 | 34.64 | 38.52 | 35.22 | — | 0.08 | 35.31 |
