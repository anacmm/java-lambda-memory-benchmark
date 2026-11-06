# Published evidence and private local files

This repository includes the application, infrastructure source, runners, article,
dataset, and recorded invocation results and summaries from AWS and LocalStack.

Original run `metadata.json` files stay on the author's machine and are ignored by
Git. They contain deployment identifiers or absolute workstation paths. Where
available, a run includes a `metadata.public.json` copy with AWS caller identity/resource identifiers
removed and project paths made relative. Artifact and dataset hashes, configuration,
sample counts, timing definitions, runtime information and available Docker resource
metadata remain available. Some historical reports refer to `metadata.json`; use
the adjacent `metadata.public.json` in the published repository.

The original legacy text logs, first-trial binary archive, build outputs, deployment
outputs, Python caches and credential files are also ignored. They are preserved
locally rather than edited or deleted. Historical tracked runs include raw
response/log-tail evidence; request IDs identify invocations and are not credentials.
The 28 October graphs, summaries, aggregate measurements and run documentation
remain in the repository. Raw per-invocation measurements, JSONL evidence and
downloaded datasets are preserved locally and ignored for commits. Private
deployment metadata remains local, with redacted public copies as above.

`localstack/.env` contains a private LocalStack activation token and must never be
committed. Copying its token into source code or documentation is unnecessary.
The `test` AWS credentials used by the local runner are deliberate emulator-only
placeholders. The native bootstrap's `changeit` value is the conventional Java
CA trust-store password, not an AWS or application account password.

New runs create fresh evidence directories. Before publishing a future run, create
a reviewed redacted metadata copy and repeat the secret scan; `.gitignore` is not
a substitute for reviewing new files. Keep the original local metadata for private
reproducibility and audit purposes.

The 28 October full matrices keep private orchestration `*.log` files locally.
LocalStack matrices publish `*.public.log` and `matrix-summary.public.json` copies
with relative project paths. The plotting script accepts these published copies
and each invocation run's `metadata.public.json`. Nested AWS batch metadata follows
the same private-original/public-copy convention.

The comparison CSV contains every plotted mean and p95 value. Regenerating graphs
with `scripts/plot-benchmark-runs.py` requires the raw evidence preserved locally;
those per-invocation files are excluded from commits.

The 28 October 2026 results are under investigation due to unexpected variability,
particularly in LocalStack I/O performance. They are retained for comparison with
future runs and are excluded from the main benchmark article and its conclusions.
The article retains the 9, 14 and 19 October evidence and now separately analyses
four complete LocalStack/AWS pairs from 4 November. The 29 October matrix remains
a separate recorded comparison. The November repetitions do not resolve the cause
of the 28 October variability; those results remain excluded from conclusions.

## Public documentation review — 6 November 2026

The current tracked tree was reviewed for credential patterns, real AWS account
identifiers, email addresses and absolute home-directory paths. Historical base64
Lambda log tails were decoded for the same checks; tracked invocation responses
contained the expected CPU/I/O benchmark output fields. No suspicious matches
were found in this review. The all-zero account ARN in the local runner and its
historical snapshot is an intentional emulator placeholder, not a real account.
Request IDs in historical evidence identify invocations and are not credentials.

This is a review of the current tracked files, not a guarantee about all secret
formats, remote branches or previous Git history. The research notes intentionally
retain named contributors and LinkedIn links, including links labelled as profile
searches; verify attribution before using them in the final article. Raw evidence
was not edited or deleted during this documentation review.

[Repository navigation](README.md#start-here) · [Evidence index](benchmark-runs/README.md)
