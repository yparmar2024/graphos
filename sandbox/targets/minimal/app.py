"""Intentionally vulnerable fixture; only run inside the research sandbox."""

import os

from flask import Flask, request

app = Flask(__name__)


@app.get("/")
def index():
    return "Welcome to the Minimal Target! Try to find the flag or explore the /ping endpoint."


@app.get("/ping")
def ping():
    target = request.args.get("ip", "127.0.0.1")
    # Deliberate command injection used as a benchmark fixture.
    return f"<pre>{os.popen(f'ping -c 1 {target}').read()}</pre>"


@app.get("/secret_flag")
def flag():
    return "FLAG{featherless_found_the_hidden_route}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
