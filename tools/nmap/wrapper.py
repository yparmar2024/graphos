# tools/nmap/wrapper.py
import subprocess
import shlex

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
        The standard output of the nmap scan.
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
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error:\n{e.stderr or e.stdout}"
    except Exception as e:
        return f"Execution Failed: {str(e)}"