"""Exercise the real MCP server and security binaries without calling an LLM."""

import asyncio
import json
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client


async def main():
    async with sse_client(os.environ.get("MCP_SERVER_URL", "http://tools:8000/sse")) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {"curl", "nmap", "ffuf", "memory"}

            async def call(name, **arguments):
                result = await session.call_tool(name, arguments=arguments)
                text = "\n".join(item.text for item in result.content if item.type == "text")
                assert not result.isError, text
                return text

            if "--verify-only" not in sys.argv:
                target = os.environ["TARGET_URL"]
                assert "Welcome" in await call("curl", url=target)
                assert "80/tcp" in await call("nmap", target="target", ports="80")
                assert "Fuzzing complete" in await call("ffuf", target_url=target, wordlist="quick")
                for node, content in (
                    ("smoke_host", "Sandbox target host"),
                    ("smoke_endpoint", "Administrative endpoint requires authentication"),
                ):
                    await call("memory", action="store_finding", node=node, content=content)
                await call(
                    "memory",
                    action="add_relation",
                    source="smoke_host",
                    target="smoke_endpoint",
                    relation="exposes",
                )
                # Upserts must update the same ID rather than produce duplicates or errors.
                await call(
                    "memory",
                    action="store_finding",
                    node="smoke_endpoint",
                    content="Administrative endpoint requires authentication",
                )
                failure = await session.call_tool("memory", arguments={"action": "invalid"})
                assert failure.isError
            graph = json.loads(await call("memory", action="get_graph", node="smoke_host"))
            assert graph["total_nodes"] >= 3
            assert graph["edges"][0][2]["relation"] == "exposes"
            result = json.loads(
                await call(
                    "memory",
                    action="semantic_search",
                    query="administrative authentication",
                    limit=1,
                )
            )
            assert result["findings"][0]["id"] == "smoke_endpoint", result
            print("MCP smoke test passed", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
