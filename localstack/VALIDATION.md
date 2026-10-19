# Validation performed on 14 October 2026

## Passed

- Docker Desktop reports `aarch64`; Docker Compose is v5.5.0.
- The pinned LocalStack `2026.09.0` manifest includes `linux/arm64`.
  Manifest digest:
  `sha256:801a3dff7f6a23857e7310b7602e67d52a29dfdcb03e09f7c608d5c57d24b792`.
- Compose configuration validation passed using a placeholder token for parsing
  only. That placeholder was not used to start or activate LocalStack.
- Seven local runner isolation/validation tests passed.
- All 10 existing AWS runner tests passed.
- The unchanged native executable resolves its required `libz`, `libc` and ARM64
  ELF loader inside the cached `public.ecr.aws/lambda/provided:al2023` image.
- The exact native ZIP was extracted to a temporary directory and mounted read-only
  in an ARM64 AL2023 container. Using AWS's Runtime Interface Emulator and a
  temporary HTTP S3 stub serving the unchanged fixture, CPU and I/O invocations
  returned exactly the expected response shapes and checksums. The existing native
  application accepted the S3 endpoint override, path-style setting and region
  through environment variables. The temporary container was removed afterwards.
- A SHA-256 preservation check covered 5,583 existing files, including AWS run
  evidence, Java sources, CDK sources, build/runner scripts, article and native ZIP.
  None changed. No Git commit or push was performed, and no real AWS API was called.

Artifact SHA-256:
`37705d0f1a88a3cc222e3a5f0853be8dc1855f68620e3c6ad49dd4a37f0737b8`.

Dataset SHA-256:
`2939695c8e099f3d73ea84e17069dc7cbae9304be72972d0be0f5f1b698fa10e`.

## Full LocalStack run passed

After activation was configured, the pinned ARM64 LocalStack container became
healthy and the default experiment completed successfully on 14 October 2026.

- 24 valid invocations; no failed calls or cleanup errors.
- 10 warm collected samples per workload; no collected cold starts.
- Original dataset uploaded and downloaded with matching SHA-256.
- Unchanged native ZIP deployed as ARM64 `provided.al2023`; code hash verified.
- Both workload response shapes and checksums matched the AWS fixture expectations.
- Run-owned local Lambda and S3 resources were removed successfully.

Evidence: [run summary](results/20261014T094858131639Z/summary.json),
[metadata](results/20261014T094858131639Z/metadata.public.json), and raw responses/logs in
that same directory. Local warm mean handler times were 85.73 ms for CPU and
10.44 ms for I/O. These are small-sample local observations, not AWS duration,
memory-sizing or billing results.

The earlier missing-token startup attempt created no containers. The AL2023/stub
check described above remains separate from this actual LocalStack validation.
