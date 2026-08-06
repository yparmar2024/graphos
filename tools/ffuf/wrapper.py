# tools/ffuf/wrapper.py
import subprocess
import json
import tempfile
import os
import sys

# We append the parent tools/ directory to sys.path so we can import the memory wrapper.
# This allows us to pipe outputs directly to the DB without blowing up the agent's context.
tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if tools_dir not in sys.path:
    sys.path.append(tools_dir)
import memory.wrapper as memory_tool

def execute(target_url: str, extensions: str = "", wordlist: str = "common") -> str:
    """
    Executes a directory fuzzing scan using ffuf against the specified target.
    
    Args:
        target_url: The base URL to scan (e.g., "http://target:80"). Do not include /FUZZ, it will be added automatically.
        extensions: Optional comma-separated list of extensions to append (e.g., ".php,.html,.txt").
        wordlist: The wordlist to use. Options: 'common' (default, 4.6k words), 'quick' (fast hits, 2.5k words), 'api' (api endpoints only).
        
    Returns:
        A JSON string containing the discovered endpoints, their status codes, and sizes.
    """
    # Ensure the URL is properly formatted for ffuf
    target_url = target_url.rstrip("/")
    fuzz_url = f"{target_url}/FUZZ"
    
    if wordlist not in ["common", "quick", "api"]:
        wordlist = "common"
        
    wordlist_path = f"/app/tools/wordlists/{wordlist}.txt"
    
    # We use a temporary file to store the JSON output so we can parse it cleanly
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out_file = tmp.name
        
    cmd = [
        "ffuf",
        "-w", wordlist_path,
        "-u", fuzz_url,
        "-o", out_file,
        "-of", "json",
        "-s" # Silent mode to suppress standard terminal output
    ]
    
    if extensions:
        cmd.extend(["-e", extensions])
        
    try:
        # We don't check=True because ffuf returns non-zero exit codes if some requests fail (which is normal in fuzzing)
        subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse the JSON output file
        if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
            with open(out_file, "r") as f:
                data = json.load(f)
                
            results = data.get("results", [])
            if not results:
                return "Fuzzing complete. No hidden endpoints found."
                
            discovered = []
            for item in results:
                discovered.append({
                    "url": item.get("url"),
                    "status": item.get("status"),
                    "words": item.get("words"),
                    "lines": item.get("lines"),
                    "content-type": item.get("content-type")
                })
                
            # Store in memory directly to prevent LLM context overflow
            for ep in discovered:
                url_clean = ep['url'].replace('http://', '').replace('/', '_').replace(':', '_')
                node_id = f"endpoint_{url_clean}"
                content = f"Fuzzing discovered endpoint: {ep['url']} (Status {ep['status']}, Content-Type: {ep['content-type']})"
                memory_tool.execute(action="store_finding", content=content, node=node_id)
                
            # Clean up the temp file
            os.remove(out_file)
            
            return f"Fuzzing complete. Discovered {len(discovered)} endpoints and stored them directly in the memory Knowledge Graph. Use the 'memory' tool with 'semantic_search' to find specific endpoints (e.g. search for 'admin' or 'api')."
        else:
            return "Fuzzing complete. No results returned."
            
    except Exception as e:
        if os.path.exists(out_file):
            os.remove(out_file)
        return f"Execution Failed: {str(e)}"
