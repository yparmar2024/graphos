# Graphos

**Graphos** is an autonomous agentic framework for research-grade penetration testing. It leverages multi-agent orchestration, knowledge graphs, and persistent memory to map network topologies and identify vulnerabilities with human-like reasoning.

## 🚀 Research Focus
* **Autonomous Orchestration:** Using agentic workflows to chain security tasks (recon, exploitation, verification).
* **Graph-Based Memory:** Utilizing graph databases to maintain network state and reduce LLM context reliance.
* **Reproducible Lab Environment:** A containerized "Cyber Range" enabling programmatic resets for consistent benchmarking.

## 📂 Repository Structure
- `run.sh`: The main factory script used to orchestrate tests.
- `sandbox/operators/`: Contains LLM agents ("the brain"). Each folder (e.g. `minimal/`) is an isolated agent configuration.
- `sandbox/targets/`: Contains intentionally vulnerable web apps ("the target"). Each folder is an isolated environment to exploit.
- `tools/`: The centralized Model Context Protocol (MCP) server ("the hands"). Agents execute all commands here.

## 🛠️ Usage

### 1. Configuration
Copy the `.env.example` to `.env` and insert your OpenRouter API key.
```bash
cp .env.example .env
```

### 2. Running a Test
We use the `run.sh` factory script to dynamically combine different operators and targets for A/B testing:

```bash
./run.sh --operator minimal --target minimal
```

This spins up three containers:
1. **target**: The vulnerable application on `graphos_net`.
2. **tools**: The MCP server that dynamically exposes the contents of `tools/` as callable JSON schemas.
3. **operator**: The AI agent executing your tests.

### 3. Adding New Components
- **To add a tool:** Create a new folder in `tools/` with a `wrapper.py` containing an `execute` function. It is instantly auto-discovered.
- **To add an operator:** Duplicate `sandbox/operators/minimal`, modify the `agent.py` logic, and run `./run.sh --operator new_name`.

*(For detailed explanations of the design choices in each environment, see the `NOTES.md` file within their respective folders.)*

## ⚖️ Ethical Research Notice
Graphos is developed for **educational and authorized security research purposes only.** This framework must only be used within controlled, containerized environments or on systems where you have explicit, written permission to conduct penetration testing. Unauthorized use is illegal and unethical.