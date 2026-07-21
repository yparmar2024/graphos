import os
import importlib.util
from mcp.server.fastmcp import FastMCP

host = os.environ.get("HOST", "0.0.0.0")
port = int(os.environ.get("PORT", "8000"))

# Initialize the MCP Server
mcp = FastMCP("Graphos Security Operators", host=host, port=port)

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
        # We rename the function metadata so MCP registers it with the proper name
        # We also convert tool_name to camelCase (e.g. nmap remains nmap, but run_tool would be runTool)
        camelCaseName = "".join(word.capitalize() if i > 0 else word for i, word in enumerate(toolName.split('_')))
        module.execute.__name__ = camelCaseName
        mcp.add_tool(module.execute)

if __name__ == "__main__":
    mcp.run(transport="sse")
