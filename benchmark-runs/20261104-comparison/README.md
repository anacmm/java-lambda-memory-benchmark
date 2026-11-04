# 4 November 2026: four sequential LocalStack/AWS pairs

Every pair ran LocalStack to completion before AWS in `eu-west-2`. Each environment/run completed 1,452 valid calls: 11 memory settings, two workloads, two repetitions, three warmups and 30 collected calls per workload/memory/repetition. Each configuration has 60 warm collected samples and six warmups. There were no failed or invalid calls, all local cleanup succeeded, and AWS memory was restored to 1024 MB after every run.

These are four runs on one day, not four independent days or 240 independent execution environments. Calls share warm environments; keep run and repetition identities when interpreting variability. The native ZIP and dataset hashes match across all eight matrices. The 28 October results remain under investigation.

## Sources

| Pair | AWS | LocalStack |
| --- | --- | --- |
| 1 | [20261104T145606566518Z](../20261104T145606566518Z/final-summary.json) | [20261104T142005953270Z-full-matrix](../../localstack/results/20261104T142005953270Z-full-matrix/matrix-summary.public.json) |
| 2 | [20261104T154654746990Z](../20261104T154654746990Z/final-summary.json) | [20261104T153706366094Z-full-matrix](../../localstack/results/20261104T153706366094Z-full-matrix/matrix-summary.public.json) |
| 3 | [20261104T173911446464Z](../20261104T173911446464Z/final-summary.json) | [20261104T172931495595Z-full-matrix](../../localstack/results/20261104T172931495595Z-full-matrix/matrix-summary.public.json) |
| 4 | [20261104T220003251163Z](../20261104T220003251163Z/final-summary.json) | [20261104T215023846818Z-full-matrix](../../localstack/results/20261104T215023846818Z-full-matrix/matrix-summary.public.json) |

AWS source folders include combined and per-repetition JSON/CSV summaries, configuration counts and `metadata.public.json`. Local source folders include a public matrix summary and per-memory summaries/public metadata. Original metadata, raw invocation logs/responses, JSONL and downloaded fixtures remain local.

## Warm AWS REPORT means

All durations are milliseconds. Each cell is a separate 60-sample mean. Billed compute is reported separately below.

| Memory MB | CPU 1 | CPU 2 | CPU 3 | CPU 4 | I/O 1 | I/O 2 | I/O 3 | I/O 4 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 256 | 709.71 | 685.04 | 773.84 | 772.08 | 62.39 | 58.20 | 66.28 | 68.46 |
| 512 | 398.43 | 368.00 | 367.85 | 368.18 | 44.27 | 39.77 | 41.04 | 42.03 |
| 1024 | 195.11 | 195.65 | 197.16 | 195.13 | 31.40 | 30.69 | 31.69 | 33.42 |
| 1536 | 142.02 | 141.75 | 159.26 | 142.95 | 32.42 | 31.76 | 32.22 | 31.97 |
| 1769 | 136.54 | 135.52 | 142.21 | 135.45 | 31.92 | 31.12 | 33.49 | 31.32 |
| 2048 | 145.38 | 124.70 | 123.36 | 124.97 | 35.36 | 32.45 | 32.12 | 31.29 |
| 3072 | 112.97 | 111.36 | 110.24 | 106.68 | 32.28 | 30.44 | 31.81 | 30.89 |
| 4096 | 111.05 | 110.36 | 106.54 | 111.46 | 31.60 | 32.62 | 30.86 | 31.12 |
| 6144 | 109.54 | 124.34 | 131.06 | 111.40 | 32.10 | 32.86 | 32.16 | 31.84 |
| 8192 | 110.37 | 110.13 | 107.52 | 110.70 | 32.63 | 33.14 | 32.09 | 31.87 |
| 10240 | 107.75 | 110.90 | 110.65 | 109.58 | 30.51 | 31.49 | 30.92 | 31.43 |

## Compute and variation

| Pair | CPU 256 MB GB-s | CPU 512 MB GB-s | CPU 1024 MB GB-s | CPU 1536 MB GB-s | 1024→1536 change |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.177533 | 0.199450 | 0.195633 | 0.213875 | +9.3% |
| 2 | 0.171379 | 0.184217 | 0.196150 | 0.213375 | +8.8% |
| 3 | 0.193579 | 0.184133 | 0.197633 | 0.239575 | +21.2% |
| 4 | 0.193146 | 0.184358 | 0.195617 | 0.215225 | +10.0% |

256 MB had the lowest CPU billed compute in pairs 1–2; 512 MB did in pairs 3–4. The I/O minimum remained 256 MB in all four pairs. These are warm billed GB-seconds, not a full cost estimate. CPU latency improved from 1024 to 1536 MB in every pair, but billed compute increased in every pair.

CPU mean REPORT duration at 3072 MB was 106.68–112.97 ms; raising memory to 10240 MB produced 107.75–110.90 ms. Extra configured memory did not give a consistent further speedup. At 6144 MB, pairs 2 and 3 were slower (124.34 and 131.06 ms), so the plateau is approximate, not monotonic. I/O means across all settings at or above 1024 MB were 30.44–35.36 ms.

## Compare handler time at 1024 MB

Both sides below use Java `handlerMs`, not AWS REPORT or LocalStack emulated billing.

| Pair | AWS CPU mean | Local CPU mean | AWS I/O mean | Local I/O mean | Local I/O p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 189.25 | 87.48 | 30.13 | 6.45 | 7.92 |
| 2 | 190.12 | 85.78 | 29.39 | 6.19 | 8.18 |
| 3 | 191.49 | 86.82 | 30.40 | 6.39 | 7.92 |
| 4 | 190.25 | 86.45 | 31.98 | 6.33 | 8.37 |

Local configured memory does not reproduce AWS CPU allocation. Public metadata retains Docker resource observations: these are snapshots, not continuous utilisation measurements. Local HTTP S3 and shared host resources differ from AWS HTTPS and regional infrastructure. These new successful runs do not resolve the cause of the 28 October variability.

[All means and percentiles](measurements.csv) · [Run identities and hashes](sources.json)

Percentiles use nearest rank within each run/configuration, without pooling runs. Metrics include AWS REPORT, handler, S3 phase, CPU phase and billed compute; LocalStack contributes handler and phase timings only.
