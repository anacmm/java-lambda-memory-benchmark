# Published evidence and private local files

This repository includes the application, infrastructure source, runners, article,
dataset, and recorded invocation results and summaries from AWS and LocalStack.

Original run `metadata.json` files stay on the author's machine and are ignored by
Git. They contain deployment identifiers or absolute workstation paths. Each run
includes a `metadata.public.json` copy with AWS caller identity/resource identifiers
removed and project paths made relative. Artifact and dataset hashes, configuration,
sample counts, timing definitions, runtime information and available Docker resource
metadata remain available. Some historical reports refer to `metadata.json`; use
the adjacent `metadata.public.json` in the published repository.

The original legacy text logs, first-trial binary archive, build outputs, deployment
outputs, Python caches and credential files are also ignored. They are preserved
locally rather than edited or deleted. Raw response/log-tail evidence for the dated
runs is included; request IDs identify invocations and are not credentials.

`localstack/.env` contains a private LocalStack activation token and must never be
committed. Copying its token into source code or documentation is unnecessary.
The `test` AWS credentials used by the local runner are deliberate emulator-only
placeholders. The native bootstrap's `changeit` value is the conventional Java
CA trust-store password, not an AWS or application account password.

New runs create fresh evidence directories. Before publishing a future run, create
a reviewed redacted metadata copy and repeat the secret scan; `.gitignore` is not
a substitute for reviewing new files. Keep the original local metadata for private
reproducibility and audit purposes.
