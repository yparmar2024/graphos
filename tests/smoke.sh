#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/tests/runs/smoke_$(date +%s)_$$"
export RUN_DIR
RUN_UID="$(id -u)"
RUN_GID="$(id -g)"
export RUN_UID RUN_GID
export ENV_FILE="$ROOT/.env.example" TARGET=minimal OPERATOR=minimal TARGET_PORT=80
# Use an ephemeral host port so smoke tests do not conflict with an existing lab.
export TARGET_HOST_PORT=0
mkdir -p "$RUN_DIR/memory"
cp "$ROOT/tests/profiles/default.json" "$RUN_DIR/profile.json"
COMPOSE=(docker compose -f "$ROOT/sandbox/docker-compose.yml" -p "graphos-smoke-$$")
cleanup() {
    result=$?
    trap - EXIT
    "${COMPOSE[@]}" logs --no-color > "$RUN_DIR/containers.log" 2>&1 || true
    "${COMPOSE[@]}" down --volumes --remove-orphans
    exit "$result"
}
trap cleanup EXIT
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d --wait --wait-timeout 180 target tools
"${COMPOSE[@]}" run --rm --no-deps -v "$ROOT/tests/integration/smoke.py:/app/smoke.py:ro" operator python /app/smoke.py
"${COMPOSE[@]}" restart tools
"${COMPOSE[@]}" up -d --wait --wait-timeout 60 tools
"${COMPOSE[@]}" run --rm --no-deps -v "$ROOT/tests/integration/smoke.py:/app/smoke.py:ro" operator python /app/smoke.py --verify-only
# Placeholder credentials must fail before any paid model request and preserve metrics.
if "${COMPOSE[@]}" run --rm --no-deps operator; then
    echo "Operator unexpectedly succeeded with placeholder credentials" >&2
    exit 1
fi
python3 -c 'import json, os; from pathlib import Path; assert json.loads((Path(os.environ["RUN_DIR"]) / "metrics.json").read_text())["status"] == "failed"'
