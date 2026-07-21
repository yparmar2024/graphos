import os
import time
import json
import asyncio
import httpx
from datetime import datetime
import openai
from openai import OpenAI

# MCP client imports
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# Load configurations from Environment Variables
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TARGET_URL = os.environ.get("TARGET_URL", "http://localhost")
# FastMCP SSE endpoints default to /sse
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://tools-server:8000/sse")
LOG_DIR = os.environ.get("LOG_DIR", "/app/tests")

# Setup logging
os.makedirs(LOG_DIR, exist_ok=True)
logName = os.environ.get("LOG_NAME")

if not logName:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logName = f"test_{timestamp}.txt"

LOG_FILE = os.path.join(LOG_DIR, logName)

# Clear the log file at the start of each run if it already exists
with open(LOG_FILE, "w") as f:
    pass

def log(message: str):
    """Helper to print to console and write to the log file."""
    print(message)
    with open(LOG_FILE, "a") as f:
        f.write(message + "\n")

# Load profile
PROFILE_PATH = "/app/profile.json"
profile_data = {}
if os.path.exists(PROFILE_PATH):
    try:
        with open(PROFILE_PATH, "r") as f:
            profile_data = json.load(f)
    except Exception as e:
        log(f"[!] Warning: Failed to parse {PROFILE_PATH}: {e}")

AGENT_MODEL = profile_data.get("AGENT_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
try:
    AGENT_TEMP = float(profile_data.get("AGENT_TEMP", 0.2))
except (ValueError, TypeError):
    AGENT_TEMP = 0.2
AGENT_CONTEXT = profile_data.get("AGENT_CONTEXT", "")

OPERATOR_NAME = os.environ.get("OPERATOR_NAME", "Unknown")
TARGET_NAME = os.environ.get("TARGET_NAME", "Unknown")
PROFILE_NAME = os.environ.get("PROFILE_NAME", "Unknown")

log("="*50)
log("Test Configuration:")
log(f"  Operator: {OPERATOR_NAME}")
log(f"  Target: {TARGET_NAME}")
log(f"  Profile: {PROFILE_NAME}")
log(f"  Model: {AGENT_MODEL}")
log(f"  Temperature: {AGENT_TEMP}")
log(f"  Context: {AGENT_CONTEXT}")
log("="*50 + "\n")

INSTRUCTIONS = f"""
You are the Minimal Reconnaissance Operator, an authorized security auditor operating in a controlled sandbox.
Your target is {TARGET_URL}.
Your goal is to discover open ports and basic service information about the target.
You have access to security tools via an external MCP server.

{f'PRIOR KNOWLEDGE / CONTEXT:\\n{AGENT_CONTEXT}\\n' if AGENT_CONTEXT else ''}
CRITICAL TOOL RULES:
- ONLY use the tools you are explicitly given.

Analyze the output of your tools. Once you have enough information, output a final summary and declare "TASK_COMPLETE".
"""

async def main():
    if not OPENROUTER_API_KEY:
        log("[!] Error: OPENROUTER_API_KEY is not set.")
        return

    log(f"[*] Starting Minimal Agent targeting {TARGET_URL}...")
    log(f"[*] Logging output to {LOG_FILE}...")
    
    log(f"[*] Connecting to MCP Server at {MCP_SERVER_URL}...")
    
    try:
        # Retry loop to handle the race condition where the tools-server Uvicorn 
        # takes a few seconds to actually bind to the port and accept connections.
        max_retries = 5
        for attempt in range(max_retries):
            try:
                # Establish the asynchronous SSE connection to the tools-server
                async with sse_client(MCP_SERVER_URL) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        # Initialize the MCP connection payload
                        await session.initialize()
                        log("[*] Successfully initialized MCP Session. Brain is now connected to Hands!")
                        
                        # Discover available tools on the server
                        toolsResponse = await session.list_tools()
                        log("\n[*] Available Tools from MCP Server:")
                        
                        toolConfig = []
                        for tool in toolsResponse.tools:
                            log(f"  - {tool.name}: {tool.description}")
                            
                            # Convert MCP JSON schema to OpenAI tool schema
                            toolConfig.append({
                                "type": "function",
                                "function": {
                                    "name": tool.name,
                                    "description": tool.description or "",
                                    "parameters": tool.inputSchema
                                }
                            })

                        client = OpenAI(
                            base_url="https://openrouter.ai/api/v1",
                            api_key=OPENROUTER_API_KEY
                        )
                
                        history = [
                            {"role": "system", "content": INSTRUCTIONS}
                        ]
                
                        def generate_next_response():
                            try:
                                response = client.chat.completions.create(
                                    model=AGENT_MODEL,
                                    messages=history,
                                    tools=toolConfig,
                                    temperature=AGENT_TEMP
                                )
                                choice = response.choices[0]
                                history.append(choice.message)
                                return choice.message
                            except Exception as e:
                                log(f"[!] Fatal Error on {AGENT_MODEL}: {e}")
                                raise e

                        log("[*] Sending initial prompt...")
                        history.append({"role": "user", "content": "Begin your reconnaissance."})
                        responseMessage = generate_next_response()
                
                        while True:
                            if responseMessage.content:
                                log(f"\n[Agent]: {responseMessage.content}")
                        
                            if "TASK_COMPLETE" in (responseMessage.content or ""):
                                log("\n[*] Agent has completed its task. Exiting loop.")
                                break
                        
                            if responseMessage.tool_calls:
                                for call in responseMessage.tool_calls:
                                    argsDict = json.loads(call.function.arguments)
                                    toolName = call.function.name
                                    log(f"\n[System]: Agent requested tool execution: {toolName} -> {argsDict}")
                            
                                    try:
                                        log(f"[*] Sending execution request to real MCP Server...")
                                
                                        # Call the specific tool by name
                                        mcpResult = await session.call_tool(toolName, arguments=argsDict)
                                
                                        if mcpResult.isError:
                                            toolResult = f"MCP Tool Error: {mcpResult.content}"
                                        else:
                                            toolResult = "".join([c.text for c in mcpResult.content if getattr(c, 'type', '') == "text"])
                                    
                                    except BaseException as e:
                                        import traceback
                                        toolResult = f"Error communicating with MCP server:\n{traceback.format_exc()}"
                            
                                    log(f"[System]: Result from MCP Server ->\n{toolResult}\n")
                            
                                    history.append({
                                        "role": "tool",
                                        "tool_call_id": call.id,
                                        "name": toolName,
                                        "content": toolResult
                                    })
                        
                                responseMessage = generate_next_response()
                            else:
                                time.sleep(2)
                                history.append({"role": "user", "content": "Continue your analysis or execute your next step."})
                                responseMessage = generate_next_response()

                        # If we successfully completed the loop without breaking due to connection error, 
                        # we break out of the retry loop.
                        break
                
            except httpx.ConnectError as e:
                if attempt < max_retries - 1:
                    log(f"[!] Connection failed, retrying in 3 seconds... (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(3)
                else:
                    raise e
                    
    except BaseException as e:
        import traceback
        log(f"[!] Fatal Connection Error with MCP Server:\n{traceback.format_exc()}")

if __name__ == "__main__":
    # Start the asyncio event loop
    asyncio.run(main())
    
    # Force exit to ensure no hanging background networking threads from MCP/httpx 
    # prevent the container from cleanly shutting down.
    os._exit(0)
