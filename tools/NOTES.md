# MCP tool server

The tools image executes curl, Nmap, ffuf, and graph/vector memory through FastMCP over SSE. It has no published host port in Compose. The server imports each wrapper using its canonical `tools.NAME.wrapper` module name so all callers share one memory instance and lock.

Add a typed `execute()` in `tools/NAME/wrapper.py` to register a new tool. Add binaries to `tools/Dockerfile` and Python dependencies to `tools/requirements.txt`. Tools should raise exceptions for execution failures so MCP marks the response as an error. Keep outputs bounded and preserve evidence in run memory.

Nmap and ffuf batch their findings through `tools.memory.wrapper.store_findings()`, avoiding one embedding invocation and GraphML rewrite per finding. Repeated IDs update existing records. Graph checkpoints use an atomic file replacement. The lock protects in-process writers; run one tools process per trial.

Memory lives in `/app/run/memory` (or `MEMORY_DIR`). Semantic search queries Chroma, graph reads have a result limit, and explicit relationships connect existing nodes. Corrupt graph files fail visibly rather than being silently overwritten. Chroma and GraphML are separate persistence layers; interrupted writes can require reconciliation.

Tools execute as the invoking host UID/GID to keep bind-mounted artifacts writable on Linux. Root-only Nmap features are unavailable by default. Container separation does not itself enforce target authorization or prohibit network egress.
