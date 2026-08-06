import os
import importlib.util
from fastmcp import FastMCP

host = os.environ.get("HOST", "0.0.0.0")
port = os.environ.get("PORT", "8000")

# FastMCP requires environment variables to be set before import in some versions
os.environ["FASTMCP_HOST"] = host
os.environ["FASTMCP_PORT"] = str(port)

# Initialize the MCP Server
mcp = FastMCP("Graphos Security Operators")

toolsDir = os.path.dirname(os.path.abspath(__file__))

# Dynamically discover and register tools
for toolName in os.listdir(toolsDir):
    wrapperPath = os.path.join(toolsDir, toolName, "wrapper.py")
    if not os.path.isfile(wrapperPath):
        continue
        
    # Dynamically load the wrapper module
    spec = importlib.util.spec_from_file_location(f"tool_{toolName}", wrapperPath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    if hasattr(module, "execute"):
        module.execute.__name__ = toolName
        mcp.add_tool(module.execute)

if __name__ == "__main__":
    mcp.run(transport="sse", host=host, port=int(port))
