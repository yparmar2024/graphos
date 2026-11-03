"""Discover tool wrappers once, using canonical module names."""

import importlib
import os
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("Graphos Security Operators")
for wrapper in sorted(Path(__file__).parent.glob("*/wrapper.py")):
    module = importlib.import_module(f"tools.{wrapper.parent.name}.wrapper")
    mcp.tool(name=wrapper.parent.name)(module.execute)

if __name__ == "__main__":
    mcp.run(
        transport="sse",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
