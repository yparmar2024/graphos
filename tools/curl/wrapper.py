# tools/curl/wrapper.py
import subprocess
from typing import Dict, Optional


def execute(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: str = "",
    include_headers: bool = False,
    follow_redirects: bool = True,
) -> str:
    """
    Executes an HTTP request using curl.

    Args:
        url: The full URL to request (e.g., "http://target:80/").
        method: The HTTP method to use (GET, POST, PUT, DELETE, etc.).
        headers: A JSON dictionary of HTTP headers to include (e.g., {"Authorization": "Bearer ...", "Content-Type": "application/json"}).
        data: The body payload to send (useful for POST/PUT requests).
        include_headers: Set to True to include the HTTP response headers in the output (-i).
        follow_redirects: Set to True to automatically follow HTTP redirects (-L).

    Returns:
        The standard output of the curl command, including response headers if requested.
    """
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "10",
        "--max-time",
        "30",
        "--proto",
        "=http,https",
        "--proto-redir",
        "=http,https",
        "--max-redirs",
        "5",
    ]  # -s for silent mode (hide progress bar)

    if method.upper() != "GET":
        cmd.extend(["-X", method.upper()])

    if include_headers:
        cmd.append("-i")

    if follow_redirects:
        cmd.append("-L")

    if headers:
        for key, value in headers.items():
            cmd.extend(["-H", f"{key}: {value}"])

    if data:
        cmd.extend(["-d", data])

    cmd.extend(["--", url])

    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=35)
    out = result.stdout
    if len(out) > 5000:
        out = out[:5000] + "\n...[OUTPUT TRUNCATED FOR LENGTH]..."
    return out
