import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mcp.types import CallToolResult, TextContent, Tool
from openai.types.chat import ChatCompletion

spec = importlib.util.spec_from_file_location(
    "operator_agent", Path(__file__).resolve().parents[2] / "sandbox/operators/minimal/agent.py"
)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


def response(content=None, calls=None, finish_reason="stop"):
    return ChatCompletion.model_validate(
        {
            "id": "test",
            "object": "chat.completion",
            "created": 0,
            "model": "test",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": finish_reason,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": calls,
                    },
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )


def tool_call(identifier="call_1", arguments='{"url":"http://target"}'):
    return {
        "id": identifier,
        "type": "function",
        "function": {"name": "curl", "arguments": arguments},
    }


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.profile = agent.load_profile(self.path / "missing.json")
        self.session = AsyncMock()
        self.session.list_tools.return_value = SimpleNamespace(
            tools=[Tool(name="curl", inputSchema={"type": "object"})]
        )
        self.session.call_tool.return_value = CallToolResult(
            content=[TextContent(type="text", text="HTTP result")]
        )
        self.client = AsyncMock()
        self.metrics = dict(
            status="failed",
            turns=0,
            model_seconds=0,
            prompt_tokens=0,
            completion_tokens=0,
            tool_calls=0,
            tool_errors=0,
            tool_seconds=0,
        )

    async def run_trial(self, responses):
        self.client.chat.completions.create.side_effect = responses
        await agent.run_agent(
            self.session,
            self.client,
            self.profile,
            "http://target",
            self.path,
            self.metrics,
            lambda *args, **kwargs: None,
        )

    async def test_mcp_fields_and_final_report(self):
        await self.run_trial([response(calls=[tool_call()]), response("Findings\nTASK_COMPLETE")])
        self.session.call_tool.assert_awaited_once_with("curl", arguments={"url": "http://target"})
        self.assertEqual(self.metrics["status"], "completed")
        self.assertEqual((self.path / "report.md").read_text(), "Findings\n")
        self.assertEqual(self.metrics["prompt_tokens"], 20)

    async def test_history_keeps_complete_tool_exchanges(self):
        self.profile["HISTORY_TURNS"] = 1
        await self.run_trial(
            [
                response(calls=[tool_call("one")]),
                response(calls=[tool_call("two")]),
                response("Done\nTASK_COMPLETE"),
            ]
        )
        history = self.client.chat.completions.create.call_args_list[2].kwargs["messages"]
        self.assertEqual(
            [item["role"] for item in history], ["system", "user", "assistant", "tool"]
        )
        self.assertEqual(history[-1]["tool_call_id"], "two")

    async def test_errors_are_counted(self):
        self.session.call_tool.return_value = CallToolResult(
            isError=True, content=[TextContent(type="text", text="Failure")]
        )
        await self.run_trial([response(calls=[tool_call()]), response("Done\nTASK_COMPLETE")])
        self.assertEqual(self.metrics["tool_errors"], 1)

    async def test_duplicate_tool_requests_are_bounded(self):
        await self.run_trial(
            [response(calls=[tool_call(str(i))]) for i in range(3)]
            + [response("Done\nTASK_COMPLETE")]
        )
        self.assertEqual(self.session.call_tool.await_count, 2)
        self.assertEqual(self.metrics["tool_errors"], 1)

    async def test_turn_limit_stops_continuation_loop(self):
        self.profile["MAX_TURNS"] = 2
        await self.run_trial([response("Thinking"), response("Still thinking")])
        self.assertEqual(self.metrics["status"], "turn_limit")
        self.assertFalse((self.path / "report.md").exists())

    async def test_truncated_completion_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError, "completion budget"):
            await self.run_trial([response("TASK_COMPLETE", finish_reason="length")])
        self.assertNotEqual(self.metrics["status"], "completed")

    async def test_main_preserves_metrics_for_missing_credentials(self):
        with patch.dict(
            agent.os.environ,
            {"LOG_DIR": str(self.path), "PROFILE_PATH": str(self.path / "missing.json")},
            clear=True,
        ):
            self.assertEqual(await agent.main(), 1)
        self.assertEqual(json.loads((self.path / "metrics.json").read_text())["status"], "failed")

    async def test_main_records_timeout_without_claiming_success(self):
        with (
            patch.dict(
                agent.os.environ,
                {
                    "LOG_DIR": str(self.path),
                    "FEATHERLESS_API_KEY": "test",
                    "PROFILE_PATH": str(self.path / "missing.json"),
                },
                clear=True,
            ),
            patch.object(agent, "connect", side_effect=TimeoutError),
        ):
            self.assertEqual(await agent.main(), 1)
        self.assertEqual(json.loads((self.path / "metrics.json").read_text())["status"], "timeout")

    def test_profile_rejects_invalid_budgets(self):
        for value in (0, -1, True, "ten"):
            path = self.path / "profile.json"
            path.write_text(json.dumps({"MAX_TURNS": value}))
            with self.assertRaises(ValueError):
                agent.load_profile(path)
