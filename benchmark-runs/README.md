# Benchmark evidence index

[Back to the project](../README.md#start-here) · [Publishing and privacy](../PUBLISHING.md)

## Latest validated comparison

Start with [4 November 2026: four sequential LocalStack/AWS pairs](20261104-comparison/README.md).
Each pair completed LocalStack before AWS in `eu-west-2`. There are 60 valid warm
collected samples per workload/memory/run. These are four runs on the same day;
do not treat them as four independent days or pool their percentiles.

The comparison links to completion counts, combined and per-repetition timings,
public metadata and local per-memory summaries. Its [measurements CSV](20261104-comparison/measurements.csv)
keeps each run, memory, workload and metric separate; [sources](20261104-comparison/sources.json)
record the exact source directories and artifact/dataset hashes.

## Historical experiments

These records are preserved in place. Read each run's scope and sample counts before
comparing it with the latest matrix.

| Date (2026) | Evidence | Scope / status |
| --- | --- | --- |
| 9 October | [AWS summary](20261009T160821922550Z/summary.csv), [completion](20261009T160821922550Z/final-summary.json) | Original seven-memory AWS matrix |
| 14 October | [AWS replication](20261014T091601316296Z/comparison.md), [local summary](../localstack/results/20261014T094858131639Z/summary.json), [local validation notes](../localstack/VALIDATION.md) | AWS replication and smaller local experiment; distinct sample counts |
| 19 October | [AWS replication](20261019T081929658746Z/comparison.md), [local summary](../localstack/results/20261019T082816425083Z/summary.json) | Seven-memory AWS matrix; local experiment at 1024 MB |
| 28 October | [Preserved comparison and graphs](20261028-two-runs/README.md) | **Under investigation:** unexpected variability; excluded from validated findings |
| 29 October | [AWS/LocalStack timing comparison](20261029-comparison/README.md) | Separate full 11-memory comparison; not part of the four November pairs |

The [extended research notes](../aws-lambda-memory-article.md) discuss the original
October evidence and the November extension. They are not the final LinkedIn article.

## Root-level historical files

These small early measurement files are not the latest full matrix and are retained
at their existing paths for compatibility. Their filenames do not establish a run
date or the full methodology; use the dated run folders above for complete trials.

| Root file | Contents |
| --- | --- |
| [benchmark-invocations.json](../benchmark-invocations.json) | 23 application measurement rows |
| [benchmark-reports.json](../benchmark-reports.json) | 23 AWS REPORT timing rows |
| [benchmark-results.json](../benchmark-results.json) | 23 combined application/REPORT rows |
| [benchmark-warm-summary.json](../benchmark-warm-summary.json) | 12 workload/memory groups, with only 1–2 warm samples per group |
| [benchmark-identities.sha256](../benchmark-identities.sha256) | Native ZIP and dataset hash record; the ZIP is a local build output |

## Reading the measurements

- **AWS REPORT duration** covers more than Java `handlerMs`. Cross-environment
  comparisons use handler time on both sides; LocalStack REPORT is emulated.
- **Mean, p50 and p95** are different statistics. Published tables label which they
  use; percentiles use nearest rank within a configuration/run.
- **Billed GB-seconds** measure Lambda compute consumption, not a full monetary bill.
- Matching checksums and responses show **functional parity**, not performance parity
  or equivalent CPU allocation at the same configured memory.
- Older tracked runs include raw invocation responses and decoded/base64 log tails.
  New raw evidence remains local. Published metadata uses `metadata.public.json`;
  see [privacy guidance](../PUBLISHING.md) before sharing additional files.
