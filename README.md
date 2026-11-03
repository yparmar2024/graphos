# Graphos

Graphos is a research framework for autonomous reconnaissance in a containerized security lab. A single LLM operator calls a shared MCP tool server containing curl, Nmap, ffuf, and run-scoped graph/vector memory. Multi-agent orchestration is a future research direction.

## Run a trial

Requirements: Docker with Compose v2, Python 3.11+ for development (Python 3 is sufficient for the launcher), and a Featherless API key.

```bash
cp .env.example .env
# Set FEATHERLESS_API_KEY in .env.
./run.sh --operator minimal --target minimal
./run.sh --operator minimal --target juiceshop --profile default
```

The launcher works from any directory. Optional `--run NAME` selects a fresh results directory; existing run names are rejected to prevent accidental reuse. `ENV_FILE=/absolute/path/to/file` selects an alternative credentials file. The target is available at `http://127.0.0.1:8080`; set `TARGET_HOST_PORT` to change the host port. The MCP server is available only inside the Docker network.

The launcher waits for target/tool readiness, propagates the operator's exit status, and removes its containers and volumes on exit. Results remain in `tests/runs/NAME/`:

- `profile.json`, `revision.txt`, `compose.yaml`: configuration snapshots; credentials are not expanded into the Compose snapshot.
- `events.jsonl`: model/tool events, token usage, and per-call timing.
- `metrics.json`: trial status, elapsed/model/tool time, token totals, and errors.
- `report.md`: final report, written only when the operator declares completion.
- `containers.log`: container logs, including startup failures.
- `memory/`: persisted Chroma records and `graph.graphml`.

These replace the previous `log.txt` and `data.txt` outputs. `completed` means the operator finished its investigation, not that an independent evaluator verified its findings. Failed, timed-out, and turn-limited runs return a nonzero exit status.

## Configure the operator

Profiles live in `tests/profiles/`. The default profile controls the model, temperature, task context, and these budgets:

| Setting | Default | Meaning |
| --- | --- | --- |
| `MAX_TURNS` | 24 | Maximum model requests |
| `HISTORY_TURNS` | 8 | Completed exchanges retained in model context |
| `MAX_COMPLETION_TOKENS` | 2048 | Per-response completion budget; provider reasoning may consume this budget |
| `MODEL_TIMEOUT_SECONDS` | 120 | Timeout for a model request |
| `TRIAL_TIMEOUT_SECONDS` | 600 | Whole operator budget, including MCP connection and cleanup |

Older exchanges remain in the event log; observations stored in memory remain retrievable after conversation history is trimmed. A response that exhausts its completion budget stops the run as failed rather than treating truncated output as a successful investigation. Raise the budget if a model needs more tokens. These limits bound resource use; they do not guarantee faster successful trials.

## Memory and tools

Scan wrappers automatically upsert findings in batches and checkpoint the graph. The memory tool supports:

- `store_finding`: store or update text under a stable ID.
- `semantic_search`: retrieve relevant text using a query and bounded `limit`.
- `get_graph`: retrieve a bounded graph overview or a node's immediate neighborhood.
- `add_relation`: connect two stored nodes using a named relationship.

Relations are explicit; scan findings do not automatically become an attack graph. Chroma's default embedding model downloads on first use, which can add cold-start latency. Each trial has separate memory. GraphML and Chroma are separate stores and do not provide a shared transaction.

Tools run without root privileges. Nmap options requiring raw sockets or OS detection may fail; ordinary TCP reconnaissance works without those privileges. HTTP, scans, model requests, and trials have finite timeouts. ffuf uses automatic baseline calibration to reduce generic fallback-page matches.

## Repository layout

```text
run.sh                         Trial launcher
sandbox/docker-compose.yml     Lab services and readiness checks
sandbox/operators/minimal/     Operator source, image, and dependencies
sandbox/targets/minimal/       Small intentionally vulnerable Flask fixture
sandbox/targets/juiceshop/     Versioned Juice Shop target
tools/                        MCP server and tool wrappers
tests/profiles/               Experiment profiles
tests/unit/                   Offline regression tests
tests/integration/            Real MCP smoke client
tests/smoke.sh                Container integration test without an LLM
```

To add a tool, create `tools/NAME/wrapper.py` with a typed `execute()` function and install its dependencies in the tools image. The server discovers wrappers by their canonical Python module names. To add an operator or target, add a directory under the corresponding `sandbox/` folder. Targets must define an image health check; operators must write into `LOG_DIR` and return a meaningful exit status.

Direct Python dependencies, Juice Shop, and the wordlist revision are pinned. Base-image tags, OS packages, and transitive Python dependencies can still change; builds are not fully hermetic.

## Validate changes

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r tools/requirements.txt -r sandbox/operators/minimal/requirements.txt ruff==0.17.3
.venv/bin/python -m unittest discover -s tests/unit -v
.venv/bin/ruff check .
.venv/bin/ruff format --check .
bash -n run.sh tests/smoke.sh
shellcheck run.sh tests/smoke.sh
bash tests/smoke.sh
```

The smoke test uses placeholder credentials and never calls an LLM. It checks real MCP discovery, HTTP, Nmap, ffuf, memory search, relationship persistence, and retrieval after restarting the server. CI runs these checks on pull requests.

Use Graphos only in controlled labs or against systems you are explicitly authorized to assess. The target applications are intentionally vulnerable. Container separation provides operational isolation, not a complete authorization or network-egress boundary.
