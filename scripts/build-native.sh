#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
builder='quay.io/quarkus/ubi9-quarkus-mandrel-builder-image:jdk-21'
docker info >/dev/null
# Extract the builder's trust store for S3 HTTPS in the Lambda OS-only runtime.
container=$(docker create --platform linux/arm64 "$builder")
trap 'docker rm "$container" >/dev/null' EXIT
docker cp "$container:/opt/mandrel/lib/security/cacerts" lambda/src/main/zip.native/cacerts
mvn -pl lambda -am clean package -Pnative "$@"
# Fail early if someone changes the build to a JVM ZIP or the wrong architecture.
unzip -p lambda/target/function.zip runner > lambda/target/runner-check
file lambda/target/runner-check | tee lambda/target/native-architecture.txt
if ! file lambda/target/runner-check | grep -q 'ELF 64-bit.*ARM aarch64'; then
  echo 'Expected a Linux ARM64 executable' >&2
  exit 1
fi
rm lambda/target/runner-check
