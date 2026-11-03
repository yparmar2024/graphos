import asyncio
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.curl import wrapper as curl
from tools.ffuf import wrapper as ffuf
from tools.nmap import wrapper as nmap


class ToolTests(unittest.TestCase):
    def test_registration_uses_one_shared_memory_module(self):
        from tools.main import mcp

        self.assertEqual(set(asyncio.run(mcp.get_tools())), {"curl", "ffuf", "nmap", "memory"})
        self.assertIs(ffuf.memory_tool, nmap.memory_tool)

    def test_nmap_batches_findings_and_removes_temporary_output(self):
        paths = []

        def run(command, **kwargs):
            self.assertEqual(kwargs["timeout"], 180)
            path = Path(command[command.index("-oX") + 1])
            paths.append(path)
            path.write_text(
                '<nmaprun><host><address addr="target"/><ports><port protocol="tcp" portid="80"><state state="open"/><service name="http"/></port></ports></host></nmaprun>'
            )

        with (
            patch.object(nmap.subprocess, "run", side_effect=run),
            patch.object(nmap.memory_tool, "store_findings") as store,
        ):
            self.assertIn("80/tcp", nmap.execute("target"))
            self.assertEqual(len(store.call_args.args[0]), 1)
        self.assertFalse(paths[0].exists())

    def test_ffuf_batches_and_filters_fallbacks(self):
        paths = []

        def run(command, **kwargs):
            self.assertIn("-ac", command)
            path = Path(command[command.index("-o") + 1])
            paths.append(path)
            path.write_text(
                json.dumps({"results": [{"url": "http://target/admin", "status": 200}]})
            )

        with (
            patch.object(ffuf.subprocess, "run", side_effect=run),
            patch.object(ffuf.memory_tool, "store_findings") as store,
        ):
            self.assertIn("1 endpoints", ffuf.execute("http://target"))
            store.assert_called_once()
        self.assertFalse(paths[0].exists())

    def test_scan_failures_propagate_and_cleanup(self):
        for module, target, flag in ((ffuf, "http://target", "-o"), (nmap, "target", "-oX")):
            paths = []

            def fail(command, **kwargs):
                paths.append(Path(command[command.index(flag) + 1]))
                raise subprocess.TimeoutExpired(command, 180)

            with (
                patch.object(module.subprocess, "run", side_effect=fail),
                self.assertRaises(subprocess.TimeoutExpired),
            ):
                module.execute(target)
            self.assertFalse(paths[0].exists())

    def test_curl_does_not_hide_network_errors(self):
        with (
            patch.object(
                curl.subprocess, "run", side_effect=subprocess.CalledProcessError(7, "curl")
            ),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            curl.execute("http://target")
