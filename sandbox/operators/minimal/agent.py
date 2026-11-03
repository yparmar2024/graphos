"""Bounded reconnaissance operator with per-step timing and durable run metrics."""

import asyncio
import json
import os
import time
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from openai import AsyncOpenAI

INSTRUCTIONS = """You are an authorized reconnaissance operator in a controlled sandbox.
Target: {target}
Discover open ports, services, and relevant web endpoints using only supplied tools.
Tools automatically store scan findings. Do not store those observations again.
Use memory(action='semantic_search', query=...) for relevant findings and
memory(action='get_graph') for a bounded overview. Record novel observations with
memory(action='store_finding'). Distinguish observations from verified vulnerabilities.
Avoid repeated scans. Finish after scanning ports, discovering endpoints, and inspecting
interesting results. End your final report with TASK_COMPLETE on its own line.
{context}
"""


def load_profile(path):
    profile = json.loads(path.read_text()) if path.exists() else {}
    defaults = {
        "MAX_TURNS": 24,
        "HISTORY_TURNS": 8,
        "MAX_COMPLETION_TOKENS": 2048,
        "MODEL_TIMEOUT_SECONDS": 120,
        "TRIAL_TIMEOUT_SECONDS": 600,
    }
    for key, default in defaults.items():
        value = profile.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{key} must be a positive integer")
        profile[key] = value
    temperature = float(profile.get("AGENT_TEMP", 0.2))
    if not 0 <= temperature <= 2:
        raise ValueError("AGENT_TEMP must be between 0 and 2")
    profile["AGENT_TEMP"] = temperature
    return profile


async def connect(stack, url):
    for attempt in range(5):
        candidate = AsyncExitStack()
        try:
            read, write = await candidate.enter_async_context(sse_client(url))
            session = await candidate.enter_async_context(ClientSession(read, write))
            await session.initialize()
            await stack.enter_async_context(candidate)
            return session
        except Exception:
            await candidate.aclose()
            if attempt == 4:
                raise
            await asyncio.sleep(2)


async def run_agent(session, client, profile, target, run_dir, metrics, event):
    available = await session.list_tools()
    tool_config = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in available.tools
    ]
    initial = [
        {
            "role": "system",
            "content": INSTRUCTIONS.format(target=target, context=profile.get("AGENT_CONTEXT", "")),
        },
        {"role": "user", "content": "Begin your reconnaissance."},
    ]
    turns = []
    repeated = {}
    for _ in range(profile["MAX_TURNS"]):
        history = initial + [
            message for turn in turns[-profile["HISTORY_TURNS"] :] for message in turn
        ]
        started = time.monotonic()
        response = await client.chat.completions.create(
            model=profile.get("AGENT_MODEL", "moonshotai/Kimi-K3"),
            messages=history,
            tools=tool_config,
            temperature=profile["AGENT_TEMP"],
            max_tokens=profile["MAX_COMPLETION_TOKENS"],
        )
        duration = time.monotonic() - started
        metrics["model_seconds"] += duration
        metrics["turns"] += 1
        usage = response.usage
        if usage:
            metrics["prompt_tokens"] += usage.prompt_tokens
            metrics["completion_tokens"] += usage.completion_tokens
        choice = response.choices[0]
        message = choice.message
        event(
            "model",
            seconds=duration,
            usage=usage.model_dump() if usage else None,
            finish_reason=choice.finish_reason,
            message=message.model_dump(exclude_none=True),
        )
        if choice.finish_reason == "length":
            raise RuntimeError(
                "Model exhausted its completion budget; trial stopped without claiming success"
            )
        turn = [message.model_dump(exclude_none=True)]
        turns.append(turn)
        if not message.tool_calls:
            if (message.content or "").strip().splitlines()[-1:] == ["TASK_COMPLETE"]:
                (run_dir / "report.md").write_text(
                    message.content.rsplit("TASK_COMPLETE", 1)[0].strip() + "\n"
                )
                metrics["status"] = "completed"
                return
            turn.append(
                {
                    "role": "user",
                    "content": "Execute the next necessary tool, or give your final report ending with TASK_COMPLETE.",
                }
            )
            continue
        for call in message.tool_calls:
            metrics["tool_calls"] += 1
            started = time.monotonic()
            try:
                arguments = json.loads(call.function.arguments)
                signature = (call.function.name, json.dumps(arguments, sort_keys=True))
                repeated[signature] = repeated.get(signature, 0) + 1
                if call.function.name != "memory" and repeated[signature] > 2:
                    raise ValueError(
                        "Identical tool request already executed twice; use existing evidence"
                    )
                result = await session.call_tool(call.function.name, arguments=arguments)
                output = "\n".join(item.text for item in result.content if item.type == "text")
                if result.isError:
                    metrics["tool_errors"] += 1
            except Exception as exc:
                metrics["tool_errors"] += 1
                output = f"Tool error: {exc}"
            duration = time.monotonic() - started
            metrics["tool_seconds"] += duration
            event(
                "tool",
                name=call.function.name,
                arguments=call.function.arguments,
                seconds=duration,
                output=output,
            )
            turn.append({"role": "tool", "tool_call_id": call.id, "content": output[:24000]})
    metrics["status"] = "turn_limit"


async def main():
    run_dir = Path(os.environ.get("LOG_DIR", "/app/run"))
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics = {
        "status": "failed",
        "turns": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "tool_calls": 0,
        "tool_errors": 0,
        "model_seconds": 0,
        "tool_seconds": 0,
        "operator": os.environ.get("OPERATOR_NAME", "minimal"),
        "target": os.environ.get("TARGET_NAME", "unknown"),
        "profile": os.environ.get("PROFILE_NAME", "default"),
    }
    started = time.monotonic()

    def event(kind, **data):
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "kind": kind, **data}
        with (run_dir / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)

    try:
        profile = load_profile(Path(os.environ.get("PROFILE_PATH", "/app/profile.json")))
        key = os.environ.get("FEATHERLESS_API_KEY")
        if not key or key == "your_featherless_api_key_here":
            raise ValueError("Set FEATHERLESS_API_KEY in .env before running trials")
        async with asyncio.timeout(profile["TRIAL_TIMEOUT_SECONDS"]):
            async with AsyncExitStack() as stack:
                session = await connect(
                    stack, os.environ.get("MCP_SERVER_URL", "http://tools:8000/sse")
                )
                client = await stack.enter_async_context(
                    AsyncOpenAI(
                        base_url="https://api.featherless.ai/v1",
                        api_key=key,
                        timeout=profile["MODEL_TIMEOUT_SECONDS"],
                        max_retries=0,
                    )
                )
                await run_agent(
                    session,
                    client,
                    profile,
                    os.environ.get("TARGET_URL", "http://target:80"),
                    run_dir,
                    metrics,
                    event,
                )
    except TimeoutError:
        metrics["status"] = "timeout"
        event("error", message="Trial exceeded its wall-clock budget")
    except Exception as exc:
        metrics["status"] = "failed"
        event("error", message=str(exc))
    finally:
        metrics["total_seconds"] = time.monotonic() - started
        (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return 0 if metrics["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
