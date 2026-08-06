# tools/nmap/wrapper.py
import subprocess
import shlex
import tempfile
import os
import sys
import xml.etree.ElementTree as ET

# We append the parent tools/ directory to sys.path so we can import the memory wrapper.
# This allows us to pipe outputs directly to the DB without blowing up the agent's context.
tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if tools_dir not in sys.path:
    sys.path.append(tools_dir)
import memory.wrapper as memory_tool

def execute(
    target: str,
    ports: str = "",
    service_version: bool = False,
    os_detection: bool = False,
    timing_template: int = 3,
    extra_args: str = ""
) -> str:
    """
    Executes an nmap scan against the specified target.
    
    Args:
        target: The IP address or hostname to scan (e.g., "192.168.1.1").
        ports: Specific ports to scan (e.g., "80,443" or "1-1000"). Leave empty for default top 1000 ports.
        service_version: Set to True to probe open ports to determine service/version info (-sV).
        os_detection: Set to True to enable OS detection (-O).
        timing_template: Set timing template 0-5. Default is 3 (-T<n>).
        extra_args: Any additional flags (e.g., "-Pn").
        
    Returns:
        A short summary of the scan. The actual open ports and services are automatically stored in the agent's Memory Knowledge Graph.
    """
    cmd = ["nmap"]
    
    if ports:
        cmd.extend(["-p", ports])
    if service_version:
        cmd.append("-sV")
    if os_detection:
        cmd.append("-O")
        
    if 0 <= timing_template <= 5:
        cmd.append(f"-T{timing_template}")
        
    if extra_args:
        cmd.extend(shlex.split(extra_args))
        
    cmd.append(target)
    
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        out_file = tmp.name
        
    cmd.extend(["-oX", out_file])
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse the XML and insert into memory directly to prevent LLM context overflow
        tree = ET.parse(out_file)
        root = tree.getroot()
        
        open_ports = []
        for host in root.findall('host'):
            ip = host.find('address').get('addr') if host.find('address') is not None else target
            ports = host.find('ports')
            if ports is not None:
                for port in ports.findall('port'):
                    state = port.find('state')
                    if state is not None and state.get('state') == 'open':
                        portid = port.get('portid')
                        protocol = port.get('protocol')
                        
                        service = port.find('service')
                        svc_name = service.get('name') if service is not None else "unknown"
                        svc_version = service.get('version') if service is not None else ""
                        svc_product = service.get('product') if service is not None else ""
                        
                        full_service = f"{svc_name} {svc_product} {svc_version}".strip()
                        open_ports.append(f"{portid}/{protocol} ({full_service})")
                        
                        node_id = f"port_{ip}_{portid}_{protocol}"
                        content = f"Nmap scan of {ip} found open port {portid}/{protocol} running {full_service}."
                        memory_tool.execute(action="store_finding", content=content, node=node_id)
        
        os.remove(out_file)
        
        if open_ports:
            return f"Nmap scan complete. Found {len(open_ports)} open ports: {', '.join(open_ports)}. Detailed service information has been automatically stored in your memory Knowledge Graph."
        else:
            return "Nmap scan complete. No open ports found."
            
    except subprocess.CalledProcessError as e:
        if os.path.exists(out_file):
            os.remove(out_file)
        return f"Error:\n{e.stderr or e.stdout}"
    except Exception as e:
        if os.path.exists(out_file):
            os.remove(out_file)
        return f"Execution Failed: {str(e)}"