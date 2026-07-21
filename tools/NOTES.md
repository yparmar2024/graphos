# Centralized MCP Tools Server

## Goal
The goal of this server is to act as the hands (execution environment) for the LLM agents. By isolating the tools into a separate container using the Model Context Protocol (MCP), we ensure that the agents cannot break out of their container or execute unauthorized commands locally. 

## Dynamic Tool Registration
This server automatically scans the `tools/` directory on startup.
If you want to add a new tool:
1. Create a new folder (e.g., `tools/curl/`).
2. Add a `wrapper.py` file inside it with a single `execute()` function.
3. Add any necessary binary dependencies to the `Dockerfile`.

The MCP server will auto-discover it, generate a JSON schema based on its type hints and docstring, and expose it to any connecting agents.
