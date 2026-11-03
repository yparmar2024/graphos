import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LauncherTests(unittest.TestCase):
    def test_help_works_outside_repository(self):
        result = subprocess.run(
            [str(ROOT / "run.sh"), "--help"], cwd="/tmp", capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--profile", result.stdout)

    def test_missing_arguments_and_unsafe_names_fail_before_docker(self):
        for arguments in (
            ["--operator"],
            ["--wat"],
            ["--operator", "../minimal", "--target", "minimal"],
            ["--operator", "unknown", "--target", "minimal"],
        ):
            result = subprocess.run(
                [str(ROOT / "run.sh"), *arguments], capture_output=True, text=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Error:", result.stderr)

    def test_quoted_target_ports_and_failure_cleanup(self):
        for target, port in (("minimal", "80"), ("juiceshop", "3000")):
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                docker = directory / "docker"
                docker.write_text(
                    "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$DOCKER_TEST_LOG\"\ncase \"$*\" in *' up '*) exit 7;; *' config '*) printf 'port=%s\\n' \"$TARGET_PORT\";; esac\n"
                )
                docker.chmod(0o755)
                name = "launcher_test_" + uuid.uuid4().hex
                artifacts = ROOT / "tests/runs" / name
                self.addCleanup(shutil.rmtree, artifacts, True)
                environment = {
                    **os.environ,
                    "PATH": temporary + os.pathsep + os.environ["PATH"],
                    "ENV_FILE": str(ROOT / ".env.example"),
                    "DOCKER_TEST_LOG": str(directory / "calls"),
                }
                result = subprocess.run(
                    [
                        str(ROOT / "run.sh"),
                        "--operator",
                        "minimal",
                        "--target",
                        target,
                        "--run",
                        name,
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertIn("down --volumes --remove-orphans", (directory / "calls").read_text())
                self.assertEqual((artifacts / "compose.yaml").read_text().strip(), "port=" + port)
