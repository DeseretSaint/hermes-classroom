"""Unit tests for the Electron resolution in scripts/cb013-live-window.sh.

pnpm keeps the dev Electron unhoisted (`node_modules/.pnpm/electron@<version>/...`),
so a launcher that only knows the hoisted path fails on a host where the binary is
installed. These tests exercise the resolution order against temp-dir fixtures and
never start a window: they only call the script with `--print-bin`.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cb013-live-window.sh"


def make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class LiveWindowElectronResolutionTest(unittest.TestCase):
    """The four-step resolution order, proven without launching Electron."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        # The script derives its "repo" from its own location, so copy it into a
        # throwaway checkout instead of pointing it at the real one.
        self.repo = base / "repo"
        self.script = self.repo / "scripts" / "cb013-live-window.sh"
        self.script.parent.mkdir(parents=True)
        shutil.copy2(SCRIPT, self.script)
        self.script.chmod(0o755)
        self.home = base / "home"
        self.home.mkdir()
        self.hermes = self.home / ".hermes" / "hermes-agent"

    def run_print_bin(self, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }
        env.pop("ELECTRON_BIN", None)
        if extra_env:
            env.update({k: v for k, v in extra_env.items() if v is not None})
        return subprocess.run(
            ["bash", str(self.script), "--print-bin"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def repo_pnpm_binary(self) -> Path:
        return make_executable(
            self.repo
            / "node_modules/.pnpm/electron@9.9.9/node_modules/electron/dist/electron"
        )

    def agent_pnpm_binary(self) -> Path:
        return make_executable(
            self.hermes
            / "node_modules/.pnpm/electron@8.8.8/node_modules/electron/dist/electron"
        )

    def hardcoded_binary(self) -> Path:
        return make_executable(self.hermes / "node_modules/electron/dist/electron")

    def test_electron_bin_is_printed_verbatim_when_executable(self) -> None:
        fixture = make_executable(Path(self.tmp.name) / "fixture-electron")
        # Higher-priority candidates exist too; ELECTRON_BIN must still win.
        self.repo_pnpm_binary()
        result = self.run_print_bin({"ELECTRON_BIN": str(fixture)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(fixture))

    def test_electron_bin_that_is_not_executable_is_skipped(self) -> None:
        fixture = Path(self.tmp.name) / "not-executable"
        fixture.write_text("nope\n", encoding="utf-8")
        repo_binary = self.repo_pnpm_binary()
        result = self.run_print_bin({"ELECTRON_BIN": str(fixture)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(repo_binary))

    def test_resolution_order_repo_pnpm_then_agent_pnpm_then_hardcoded(self) -> None:
        repo_binary = self.repo_pnpm_binary()
        agent_binary = self.agent_pnpm_binary()
        hardcoded = self.hardcoded_binary()

        result = self.run_print_bin()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(repo_binary))

        repo_binary.unlink()
        result = self.run_print_bin()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(agent_binary))

        agent_binary.unlink()
        result = self.run_print_bin()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(hardcoded))

    def test_missing_electron_fails_closed_without_starting_a_window(self) -> None:
        result = self.run_print_bin()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("no electron binary", result.stderr)
        # --print-bin must resolve and stop; no launcher state may be created.
        state = self.home / ".hermes" / "coursebook-test"
        self.assertFalse((state / "window.pid").exists(), "the test started a window")
        self.assertFalse((state / "window.log").exists(), "the test started a window")


if __name__ == "__main__":
    unittest.main()
