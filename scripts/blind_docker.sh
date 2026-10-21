#!/usr/bin/env bash
# Run dsh as a blind solver inside a Docker container.
#
# Only the blind workspace is mounted. The factory (including base/reference)
# is not present inside the container.
#
# Usage:
#   scripts/blind_docker.sh <candidate-id> [--build] [--preflight] [--model ID] [--python|--data]
#   scripts/blind_docker.sh --seed <slug> [--build] [--preflight] [--model ID] [--python|--data]
#
# --python selects the Python 3.12 + Node image (ale-blind-dsh-py).
# --data selects Python 3.12 + Node + pandas/pyarrow/numpy/scipy/openpyxl.
# The default image is Node-only.
#
# Docker access:
#   - If the docker group is active, plain `docker` works.
#   - Otherwise run `newgrp docker`, or set DOCKER_CMD="sudo docker" after
#     caching sudo credentials with `sudo -v`.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BLIND_ROOT="${BLIND_ROOT:-$HOME/ale-blind}"
SEED_ROOT="${SEED_ROOT:-}"
DOCKER_CMD="${DOCKER_CMD:-docker}"
read -r -a DOCKER <<< "$DOCKER_CMD"
IMAGE="${IMAGE:-ale-blind-dsh}"

NODE_BIN="$(command -v node || true)"
if [ -z "$NODE_BIN" ]; then
  echo "node not found on PATH" >&2
  exit 1
fi
NODE_PREFIX="$(dirname "$(dirname "$(readlink -f "$NODE_BIN")")")"
HOST_DSH="${HOST_DSH:-$NODE_PREFIX/lib/node_modules/@deepseek-ai/dsh}"
if [ ! -f "$HOST_DSH/lib/bin.js" ]; then
  echo "host dsh package not found: $HOST_DSH" >&2
  exit 1
fi
BUILD=0
PREFLIGHT=0
MODEL=""
SEED=""

usage() {
  sed -n '2,20p' "$0"
  exit 1
}

ID=""
while [ $# -gt 0 ]; do
  case "$1" in
    --build) BUILD=1 ;;
    --preflight) PREFLIGHT=1 ;;
    --python) IMAGE="ale-blind-dsh-py" ;;
    --data) IMAGE="ale-blind-dsh-data" ;;
    --seed) shift; SEED="${1:-}" ;;
    --model) shift; MODEL="${1:-}" ;;
    -h|--help) usage ;;
    -*) echo "unknown option: $1" >&2; usage ;;
    *) ID="$1" ;;
  esac
  shift
done

if [ -n "$SEED" ]; then
  ID="seed-$SEED"
  BLIND="$BLIND_ROOT/$ID"
  if [ ! -d "$BLIND/base/input" ]; then
    echo "preparing blind workspace for seed $SEED"
    PREPARE_ARGS=(--seed "$SEED" --blind-root "$BLIND_ROOT")
    [ -n "$SEED_ROOT" ] && PREPARE_ARGS+=(--seed-root "$SEED_ROOT")
    python3 -I "$ROOT/scripts/blind_prepare.py" "${PREPARE_ARGS[@]}"
  fi
else
  [ -n "$ID" ] || usage
  BLIND="$BLIND_ROOT/$ID"
fi

if [ "$IMAGE" = "ale-blind-dsh-data" ]; then
  BUILD_CONTEXT="$ROOT/docker/blind-dsh-data"
elif [ "$IMAGE" = "ale-blind-dsh-py" ]; then
  BUILD_CONTEXT="$ROOT/docker/blind-dsh-py"
else
  BUILD_CONTEXT="$ROOT/docker/blind-dsh"
fi

if ! "${DOCKER[@]}" info >/dev/null 2>&1; then
  echo "Docker is not available to this shell via: $DOCKER_CMD" >&2
  echo "Run 'newgrp docker' in a new shell, or:" >&2
  echo "  sudo -v" >&2
  if [ -n "$SEED" ]; then
    echo "  DOCKER_CMD='sudo docker' $0 --seed $SEED" >&2
  else
    echo "  DOCKER_CMD='sudo docker' $0 $ID" >&2
  fi
  exit 1
fi

if [ -z "$SEED" ] && [ ! -d "$BLIND/base/input" ]; then
  echo "preparing blind workspace for $ID"
  python3 -I "$ROOT/scripts/blind_prepare.py" "$ID" --blind-root "$BLIND_ROOT"
fi

if [ ! -f "$BLIND/TASK.md" ]; then
  if [ -n "$SEED" ]; then
    echo "missing $BLIND/TASK.md; run scripts/blind_prepare.py --seed $SEED" >&2
  else
    echo "missing $BLIND/TASK.md; run scripts/blind_prepare.py $ID" >&2
  fi
  exit 1
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  DEEPSEEK_API_KEY="$(
    python3 -I - "$HOME/.dsh/.credentials.yaml" <<'PY'
import re, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_file():
    text = path.read_text(encoding="utf-8")
    match = re.search(r"DEEPSEEK_API_KEY:\s*([^\s]+)", text)
    if match:
        print(match.group(1))
PY
  )"
  export DEEPSEEK_API_KEY
fi
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "DEEPSEEK_API_KEY is not set and could not be read from ~/.dsh/.credentials.yaml" >&2
  exit 1
fi

mkdir -p "$BLIND/run" "$BLIND/eval"
date -u +%Y-%m-%dT%H:%M:%SZ > "$BLIND/run/started_at.txt"
printf '%s\n' "${MODEL:-default}" > "$BLIND/run/model.txt"
printf '%s\n' "$IMAGE" > "$BLIND/run/image.txt"

if [ "$BUILD" -eq 1 ] || ! "${DOCKER[@]}" image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "building $IMAGE ..."
  BUILD_ARGS=()
  for name in HTTP_PROXY HTTPS_PROXY NO_PROXY; do
    value="${!name:-}"
    [ -n "$value" ] && BUILD_ARGS+=(--build-arg "$name=$value")
  done
  "${DOCKER[@]}" build --network host "${BUILD_ARGS[@]}" -t "$IMAGE" "$BUILD_CONTEXT"
fi

PROFILE_ARGS=(--profile blind)
if [ ! -f "$BLIND/.dsh-home/profiles/blind/package.json" ]; then
  PROFILE_ARGS+=(--from-default-profile headless)
fi

PATCH_ARGS=(--patch /workspace/blind.patch.yml)
if [ -n "$MODEL" ]; then
  cat > "$BLIND/model.patch.yml" <<EOF
- id: agent-default-model
  config:
    provider: deepseek-official
    model: $MODEL
EOF
  PATCH_ARGS+=(--patch /workspace/model.patch.yml)
fi

run_dsh() {
  "${DOCKER[@]}" run --rm -i \
    --user "$(id -u):$(id -g)" \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,exec,size=256m \
    --network host \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --pids-limit 512 \
    --memory 8g \
    -v "$BLIND:/workspace:rw" \
    -v "$HOST_DSH:/opt/dsh:ro" \
    -e HOME=/workspace \
    -e DSH_HOME=/workspace/.dsh-home \
    -e DEEPSEEK_API_KEY \
    -e HTTP_PROXY -e HTTPS_PROXY -e ALL_PROXY -e NO_PROXY \
    -w /workspace \
    "$IMAGE" \
    "${PROFILE_ARGS[@]}" "${PATCH_ARGS[@]}" --json -
}

if [ "$PREFLIGHT" -eq 1 ]; then
  echo "preflight: asking dsh for OK ..."
  if ! printf 'Reply with exactly: OK\n' | run_dsh \
      > "$BLIND/run/preflight.ndjson" 2> "$BLIND/run/preflight.err"; then
    echo "preflight failed; see $BLIND/run/preflight.err" >&2
    tail -20 "$BLIND/run/preflight.err" >&2 || true
    exit 1
  fi
  tail -5 "$BLIND/run/preflight.ndjson" || true
  # The preflight initializes the profile in the workspace. The solve must not
  # pass --from-default-profile again, or dsh rejects the existing profile.
  PROFILE_ARGS=(--profile blind)
fi

echo "running blind solve for $ID ..."
if ! run_dsh < "$BLIND/TASK.md" \
    > "$BLIND/run/events.ndjson" 2> "$BLIND/run/stderr.log"; then
  echo "blind run failed; see $BLIND/run/stderr.log" >&2
  tail -30 "$BLIND/run/stderr.log" >&2 || true
  exit 1
fi

echo "blind run finished"
echo "outputs:"
find "$BLIND/base/output" -type f -printf '  %s %p\n' | sort || true
echo "events: $BLIND/run/events.ndjson"
if [ -n "$SEED" ]; then
  if [ -n "$SEED_ROOT" ]; then
    echo "score with: SEED_ROOT='$SEED_ROOT' python3 -I $ROOT/scripts/blind_seed_score.py --seed $SEED"
  else
    echo "score with: python3 -I $ROOT/scripts/blind_seed_score.py --seed $SEED"
  fi
else
  echo "score with: python3 -I $ROOT/scripts/blind_score.py $ID"
fi
