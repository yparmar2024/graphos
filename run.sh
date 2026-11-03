#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OPERATOR=""
TARGET=""
RUN_NAME=""
PROFILE="default"
usage() { echo "Usage: $0 --operator <name> --target <name> [--run <name>] [--profile <name>]"; }
fail() { echo "Error: $*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --operator|--target|--run|--profile)
            (($# >= 2)) || fail "Missing value for $1"
            case "$1" in
                --operator) OPERATOR="$2" ;;
                --target) TARGET="$2" ;;
                --run) RUN_NAME="$2" ;;
                --profile) PROFILE="$2" ;;
            esac
            shift 2 ;;
        *) fail "Unknown argument: $1" ;;
    esac
done
[[ -n "$OPERATOR" && -n "$TARGET" ]] || { usage; exit 1; }
RUN_NAME="${RUN_NAME:-run_$(date -u +%Y%m%d_%H%M%S)_$$}"
for value in "$OPERATOR" "$TARGET" "$PROFILE" "$RUN_NAME"; do
    [[ "$value" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || fail "Names may contain only letters, numbers, underscores and hyphens"
done
[[ -f "$ROOT/sandbox/operators/$OPERATOR/Dockerfile" ]] || fail "Unknown operator: $OPERATOR"
[[ -f "$ROOT/sandbox/targets/$TARGET/Dockerfile" ]] || fail "Unknown target: $TARGET"
[[ -f "$ROOT/tests/profiles/$PROFILE.json" ]] || fail "Unknown profile: $PROFILE"
export ENV_FILE="${ENV_FILE:-$ROOT/.env}"
[[ -f "$ENV_FILE" ]] || fail "Copy .env.example to .env and configure your API key"
command -v python3 >/dev/null || fail "python3 is required to validate profiles"
python3 -m json.tool "$ROOT/tests/profiles/$PROFILE.json" >/dev/null
command -v docker >/dev/null || fail "Docker is required"
docker compose version >/dev/null
docker info >/dev/null
TARGET_PORT=80
if [[ -f "$ROOT/sandbox/targets/$TARGET/config.env" ]]; then
    while IFS='=' read -r key value || [[ -n "$key" ]]; do
        if [[ "$key" == TARGET_PORT ]]; then
            value="${value%$'\r'}"
            value="${value#\"}"
            value="${value%\"}"
            value="${value#\'}"
            TARGET_PORT="${value%\'}"
        fi
    done < "$ROOT/sandbox/targets/$TARGET/config.env"
fi
if [[ ! "$TARGET_PORT" =~ ^[0-9]+$ ]]; then
    fail "Invalid TARGET_PORT"
fi
if ((10#$TARGET_PORT < 1 || 10#$TARGET_PORT > 65535)); then
    fail "Invalid TARGET_PORT"
fi
export OPERATOR TARGET PROFILE TARGET_PORT
RUN_UID="$(id -u)"
RUN_GID="$(id -g)"
export RUN_UID RUN_GID
export RUN_DIR="$ROOT/tests/runs/$RUN_NAME"
mkdir -p "$ROOT/tests/runs"
mkdir "$RUN_DIR" || fail "Run directory already exists: $RUN_DIR"
mkdir "$RUN_DIR/memory"
cp "$ROOT/tests/profiles/$PROFILE.json" "$RUN_DIR/profile.json"
git -C "$ROOT" rev-parse HEAD > "$RUN_DIR/revision.txt"
COMPOSE=(docker compose --project-directory "$ROOT/sandbox" -f "$ROOT/sandbox/docker-compose.yml" -p "graphos-$(printf '%s' "$RUN_NAME" | tr '[:upper:]_' '[:lower:]-')")
cleanup() {
    result=$?
    trap - EXIT
    "${COMPOSE[@]}" logs --no-color > "$RUN_DIR/containers.log" 2>&1 || true
    "${COMPOSE[@]}" down --volumes --remove-orphans || true
    echo "Results: $RUN_DIR"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"${COMPOSE[@]}" config --no-env-resolution > "$RUN_DIR/compose.yaml"
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up --abort-on-container-exit --exit-code-from operator
