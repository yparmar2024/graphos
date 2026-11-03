import subprocess
import unittest
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
