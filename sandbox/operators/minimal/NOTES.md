# Minimal Reconnaissance Operator

## Goal
The goal of this operator is to serve as a baseline for LLM reconnaissance. It uses a minimal system prompt and dynamically discovers tools exposed by the MCP server to map out a target's attack surface.

## Injected Variables
The following environment variables control this operator:
- `OPENROUTER_API_KEY`: API key for model inference.
- `TARGET_URL`: The URL of the target application (e.g., http://target-app:80).
- `MCP_SERVER_URL`: The endpoint of the tool server.
- `LOG_DIR`: Directory where output logs are persisted.

## Instructions / A/B Testing
To test different behaviors, you can modify the `AGENT_MODEL` inside `agent.py` or inject variables like `TEMPERATURE` directly into the docker-compose environment block. Since the agent has no persistent memory between runs, each execution is completely isolated and deterministic based on the model.
