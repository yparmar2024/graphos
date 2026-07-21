# tools/nmap/wrapper.py
import subprocess

def execute(target: str) -> str:
    """
    Executes a basic nmap scan against the specified target.
    
    Args:
        target (str): The IP address or hostname to scan.
        
    Returns:
        str: The standard output of the nmap scan, or the error message.
    """
    try:
        # Executes the most basic nmap scan without extra flags
        result = subprocess.run(
            ["nmap", target], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout
        
    except subprocess.CalledProcessError as e:
        return f"Error:\n{e.stderr or e.stdout}"
    except Exception as e:
        return f"Execution Failed: {str(e)}"