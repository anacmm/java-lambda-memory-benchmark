# Full benchmark comparison

AWS region: eu-west-1. Both environments: 1,452 valid calls across 11 memory sizes; 60 valid warm collected samples per workload and memory setting. AWS configuration restored to 1024 MB. Local temporary resources cleaned up.

Means below use handlerMs on both sides. LocalStack timing and configured memory do not establish equivalent AWS compute allocation or billing. The earlier interrupted run and earlier default LocalStack run are excluded.

| Memory (MB) | AWS CPU (ms) | Local CPU (ms) | AWS I/O (ms) | Local I/O (ms) |
|---:|---:|---:|---:|---:|
| 256 | 810.53 | 96.92 | 47.37 | 6.32 |
| 512 | 414.43 | 98.06 | 43.43 | 9.84 |
| 1024 | 192.95 | 130.79 | 30.66 | 7.86 |
| 1536 | 158.87 | 118.99 | 32.21 | 12.19 |
| 1769 | 133.83 | 114.42 | 32.06 | 9.27 |
| 2048 | 122.19 | 100.22 | 35.28 | 8.85 |
| 3072 | 111.30 | 101.99 | 31.49 | 19.85 |
| 4096 | 126.87 | 101.88 | 32.34 | 8.23 |
| 6144 | 142.31 | 124.38 | 32.75 | 17.66 |
| 8192 | 130.19 | 122.63 | 32.51 | 11.24 |
| 10240 | 126.63 | 141.46 | 32.38 | 13.15 |
