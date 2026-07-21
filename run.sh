#!/bin/bash

# Initialize variables
OPERATOR=""
TARGET=""
LOG_NAME=""

# Parse CLI arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --operator) OPERATOR="$2"; shift ;;
        --target) TARGET="$2"; shift ;;
        --log) LOG_NAME="$2"; shift ;;
        -h|--help)
            echo "Usage: $0 --operator <name> --target <name> [--log <filename>]"
            exit 0
            ;;
        *) 
            echo "Error: Unknown parameter passed: $1"
            echo "Usage: $0 --operator <name> --target <name> [--log <filename>]"
            exit 1 
            ;;
    esac
    shift
done

# Validate required arguments
if [[ -z "$OPERATOR" || -z "$TARGET" ]]; then
    echo "Error: Both --operator and --target arguments are required."
    echo "Usage: $0 --operator <name> --target <name> [--log <filename>]"
    exit 1
fi

# Set default log name if not provided
if [[ -z "$LOG_NAME" ]]; then
    LOG_NAME="test_$(date +%Y%m%d_%H%M%S).txt"
elif [[ "$LOG_NAME" != *".txt" ]]; then
    LOG_NAME="${LOG_NAME}.txt"
fi

echo "[*] Running Graphos Sandbox Factory"
echo "  - Operator: $OPERATOR"
echo "  - Target: $TARGET"
echo "  - Log File: $LOG_NAME"
echo ""

cd sandbox || exit 1

# Run with --abort-on-container-exit so that when the agent script finishes (os._exit),
# Docker automatically stops the rest of the containers in the cluster.
TARGET=$TARGET OPERATOR=$OPERATOR LOG_NAME=$LOG_NAME docker-compose up --build --abort-on-container-exit

echo ""
echo "[*] Agent execution finished. Cleaning up dangling containers..."
TARGET=$TARGET OPERATOR=$OPERATOR LOG_NAME=$LOG_NAME docker-compose down -v

echo "[*] Sandbox shutdown complete."
echo "View logs in: sandbox/tests/${OPERATOR}/${LOG_NAME}"
