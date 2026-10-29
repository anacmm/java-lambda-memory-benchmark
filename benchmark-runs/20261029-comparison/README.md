# 29 October 2026: AWS and LocalStack timings

Both environments completed the full 11-memory matrix sequentially: LocalStack first, then AWS in `eu-west-2`. Each ran 1,452 valid calls, with two repetitions, three warmups and 30 collected calls per workload/memory/repetition. Every workload/memory configuration has 60 valid warm collected samples; no failed or invalid calls were recorded. AWS memory was restored to 1024 MB. The AWS stack remains deployed.

## Timing files

- [AWS aggregate JSON](../20261029T222046565791Z/summary.json) and [CSV](../20261029T222046565791Z/summary.csv): mean, p50, p95 and p99 REPORT duration and Java handler timing, separated by workload, memory, phase and cold/warm classification.
- [AWS repetition JSON](../20261029T222046565791Z/summary-by-repetition.json) and [CSV](../20261029T222046565791Z/summary-by-repetition.csv).
- [AWS final counts and restoration](../20261029T222046565791Z/final-summary.json).
- [LocalStack matrix summary](../../localstack/results/20261029T220247105945Z-full-matrix/matrix-summary.public.json): per-memory and per-repetition mean, p50 and p95 for `handlerMs`, `s3Ms`, `cpuMs` and caller timing. Individual summaries are linked below.

Raw invocation logs, responses and `invocations.jsonl` remain local in each source run directory and are ignored by Git. LocalStack raw files are under the memory subdirectories. An earlier [1024 MB local run](../../localstack/results/20261029T215819381410Z/summary.json) is separate from this matrix.

## Warm collected timings

All values below are milliseconds. AWS REPORT duration is broader than Java handler time. Compare environments using `handlerMs`; local configured memory does not reproduce AWS CPU allocation. LocalStack measurements do not establish AWS latency, billing or memory sizing. Percentiles use nearest rank.

| Memory MB | Workload | AWS REPORT p50 | AWS REPORT p95 | AWS handler p50 | AWS handler p95 | Local handler p50 | Local handler p95 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [256](../../localstack/results/20261029T220247105945Z-full-matrix/256/summary.json) | cpu | 707.600 | 738.440 | 675.042 | 705.219 | 85.841 | 162.474 |
| [256](../../localstack/results/20261029T220247105945Z-full-matrix/256/summary.json) | io | 64.110 | 74.000 | 33.868 | 54.695 | 7.970 | 21.660 |
| [512](../../localstack/results/20261029T220247105945Z-full-matrix/512/summary.json) | cpu | 409.690 | 436.410 | 380.308 | 432.718 | 87.867 | 175.046 |
| [512](../../localstack/results/20261029T220247105945Z-full-matrix/512/summary.json) | io | 44.260 | 58.150 | 33.445 | 53.907 | 6.502 | 16.022 |
| [1024](../../localstack/results/20261029T220247105945Z-full-matrix/1024/summary.json) | cpu | 188.690 | 204.500 | 183.107 | 203.178 | 86.737 | 106.742 |
| [1024](../../localstack/results/20261029T220247105945Z-full-matrix/1024/summary.json) | io | 32.810 | 39.190 | 31.542 | 38.104 | 6.817 | 15.586 |
| [1536](../../localstack/results/20261029T220247105945Z-full-matrix/1536/summary.json) | cpu | 145.030 | 153.140 | 141.630 | 151.362 | 87.835 | 143.183 |
| [1536](../../localstack/results/20261029T220247105945Z-full-matrix/1536/summary.json) | io | 34.820 | 42.530 | 33.477 | 40.654 | 6.944 | 22.297 |
| [1769](../../localstack/results/20261029T220247105945Z-full-matrix/1769/summary.json) | cpu | 136.340 | 148.200 | 134.076 | 147.008 | 87.255 | 186.855 |
| [1769](../../localstack/results/20261029T220247105945Z-full-matrix/1769/summary.json) | io | 32.830 | 39.090 | 31.619 | 38.039 | 7.561 | 16.848 |
| [2048](../../localstack/results/20261029T220247105945Z-full-matrix/2048/summary.json) | cpu | 124.720 | 136.430 | 121.414 | 128.825 | 88.065 | 141.522 |
| [2048](../../localstack/results/20261029T220247105945Z-full-matrix/2048/summary.json) | io | 34.220 | 38.830 | 32.931 | 37.541 | 6.793 | 24.916 |
| [3072](../../localstack/results/20261029T220247105945Z-full-matrix/3072/summary.json) | cpu | 112.830 | 120.230 | 111.425 | 118.844 | 86.944 | 151.189 |
| [3072](../../localstack/results/20261029T220247105945Z-full-matrix/3072/summary.json) | io | 33.870 | 40.430 | 32.532 | 39.180 | 6.933 | 18.833 |
| [4096](../../localstack/results/20261029T220247105945Z-full-matrix/4096/summary.json) | cpu | 114.290 | 123.350 | 112.983 | 122.017 | 87.067 | 127.484 |
| [4096](../../localstack/results/20261029T220247105945Z-full-matrix/4096/summary.json) | io | 34.230 | 40.630 | 33.064 | 39.361 | 7.364 | 23.596 |
| [6144](../../localstack/results/20261029T220247105945Z-full-matrix/6144/summary.json) | cpu | 112.430 | 118.980 | 111.183 | 117.612 | 87.056 | 120.035 |
| [6144](../../localstack/results/20261029T220247105945Z-full-matrix/6144/summary.json) | io | 33.480 | 40.400 | 32.175 | 39.164 | 7.599 | 16.586 |
| [8192](../../localstack/results/20261029T220247105945Z-full-matrix/8192/summary.json) | cpu | 113.710 | 118.890 | 112.337 | 117.573 | 85.956 | 105.920 |
| [8192](../../localstack/results/20261029T220247105945Z-full-matrix/8192/summary.json) | io | 34.730 | 39.750 | 33.497 | 38.561 | 7.084 | 17.734 |
| [10240](../../localstack/results/20261029T220247105945Z-full-matrix/10240/summary.json) | cpu | 111.870 | 118.950 | 110.443 | 117.745 | 88.599 | 188.736 |
| [10240](../../localstack/results/20261029T220247105945Z-full-matrix/10240/summary.json) | io | 33.510 | 38.990 | 32.282 | 37.791 | 7.505 | 17.734 |
