# Minimal reconnaissance operator

This is the single-agent baseline. It discovers MCP tool schemas, performs reconnaissance, and writes JSON event logs, metrics, and a final report into `LOG_DIR`.

Model settings and resource limits come from the selected profile under `tests/profiles/`, mounted at `/app/profile.json`. `AGENT_MODEL`, `AGENT_TEMP`, and `AGENT_CONTEXT` are profile keys, not shell environment overrides. Runtime addresses and credentials use `TARGET_URL`, `MCP_SERVER_URL`, and `FEATHERLESS_API_KEY`.

Only recent completed exchanges are resent to the model. Scan observations are automatically persisted by tools and can be retrieved through memory. Repeated identical non-memory requests are limited to two executions. Errors, timeouts, exhausted completion budgets, and turn limits produce nonzero exit statuses; they are not successful trials.

Runs are isolated but are not deterministic: provider behavior, sampling, and environment timing can vary. Compare repeated trials with saved profiles and repository revisions.
