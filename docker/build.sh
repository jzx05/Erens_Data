#!/usr/bin/env bash
# Build the three blind-solver images in dependency order.
#
# Usage:
#   docker/build.sh
#   DOCKER_CMD='sudo docker' docker/build.sh
#   HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=... docker/build.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_CMD="${DOCKER_CMD:-docker}"
read -r -a DOCKER <<< "$DOCKER_CMD"

BUILD_ARGS=()
for name in HTTP_PROXY HTTPS_PROXY NO_PROXY; do
  value="${!name:-}"
  [ -n "$value" ] && BUILD_ARGS+=(--build-arg "$name=$value")
done

build() {
  local image="$1" context="$2"
  echo "building $image ..."
  "${DOCKER[@]}" build --network host "${BUILD_ARGS[@]}" -t "$image" "$ROOT/$context"
}

build ale-blind-dsh docker/blind-dsh
build ale-blind-dsh-py docker/blind-dsh-py
build ale-blind-dsh-data docker/blind-dsh-data

echo "built: ale-blind-dsh, ale-blind-dsh-py, ale-blind-dsh-data"
