#!/bin/bash

# Initialize variables
OPERATOR=""
TARGET=""
RUN_NAME=""
PROFILE="default"

# Parse CLI arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --operator) OPERATOR="$2"; shift ;;
        --target) TARGET="$2"; shift ;;
        --run) RUN_NAME="$2"; shift ;;
        --profile) PROFILE="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 --operator <name> --target <name> [--run <name>] [--profile <name>]"
            exit 0
            ;;
        *) 
            echo "Error: Unknown parameter passed: $1"
            echo "Usage: $0 --operator <name> --target <name> [--log <filename>] [--profile <name>]"
            exit 1 
            ;;
    esac
    shift
done

# Validate required arguments
if [[ -z "$OPERATOR" || -z "$TARGET" ]]; then
    echo "Error: Both --operator and --target arguments are required."
    echo "Usage: $0 --operator <name> --target <name> [--run <name>] [--profile <name>]"
    exit 1
fi

if [[ -z "$RUN_NAME" ]]; then
    RUN_NAME="run_$(date +%Y%m%d_%H%M%S)"
fi

RUN_DIR="$(pwd)/tests/runs/${RUN_NAME}"
mkdir -p "$RUN_DIR"
mkdir -p "$RUN_DIR/memory"

# Copy the profile into the run directory to snapshot it
cp "$(pwd)/tests/profiles/${PROFILE}.json" "$RUN_DIR/profile.json"

# Source target-specific configuration if it exists
TARGET_DIR="$(pwd)/sandbox/targets/${TARGET}"
TARGET_PORT="80" # Default

if [ -f "${TARGET_DIR}/config.env" ]; then
    echo "[*] Loading target configuration from ${TARGET_DIR}/config.env"
    source "${TARGET_DIR}/config.env"
fi

echo "[*] Running Graphos Sandbox Factory"
echo "  - Operator: $OPERATOR"
echo "  - Target: $TARGET (Port: $TARGET_PORT)"
echo "  - Profile: $PROFILE"
echo "  - Run Directory: $RUN_DIR"
echo ""

cd sandbox || exit 1

# Run with --abort-on-container-exit so that when the agent script finishes (os._exit),
# Docker automatically stops the rest of the containers in the cluster.
TARGET=$TARGET TARGET_PORT=$TARGET_PORT OPERATOR=$OPERATOR RUN_DIR=$RUN_DIR docker-compose up --build --abort-on-container-exit

echo ""
echo "[*] Agent execution finished. Cleaning up dangling containers..."
TARGET=$TARGET TARGET_PORT=$TARGET_PORT OPERATOR=$OPERATOR RUN_DIR=$RUN_DIR docker-compose down -v

echo "[*] Sandbox shutdown complete."
echo "View results in: $RUN_DIR"
