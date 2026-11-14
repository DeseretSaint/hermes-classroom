"""The frame rig refuses in words when its gitignored renderer deps are absent.

`scripts/cb-frame.py` spawns the shot script with `NODE_PATH=<repo>/visual/node_modules`, and that
directory is gitignored. On a fresh clone, after `git clean`, or in a pruned scratch worktree the
first frame used to die inside Node with `Cannot find module 'playwright'` and a stack trace, which
reads as a code bug rather than a missing install. Preflight now answers first and names the fix.

These tests mock the visual directory: they never move, delete or install the real
`visual/node_modules`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cb-frame.py"


def _load_frame_module():
    spec = importlib.util.spec_from_file_location("cb_frame_for_tests", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrameDepsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frame = _load_frame_module()

    def test_missing_deps_report_names_npm_ci_and_no_node_stack(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            ok, lines = self.frame.deps_report(Path(empty))
        text = "\n".join(lines)
        self.assertFalse(ok, "an empty visual dir must not pass preflight")
        self.assertIn("npm ci", text)
        self.assertIn("cd visual", text)
        for name in ("playwright", "pngjs", "pixelmatch", "axe-core"):
            self.assertIn(name, text, f"the report must say which dep is missing: {name}")
        self.assertNotIn("Cannot find module", text)
        self.assertNotIn("    at ", text, "no Node stack frames in an operator message")

    def test_partial_install_names_only_the_missing_package(self) -> None:
        with tempfile.TemporaryDirectory() as visual:
            for name, version in (("axe-core", "4.14.0"), ("pixelmatch", "6.0.0"), ("pngjs", "7.0.0")):
                pkg = Path(visual) / "node_modules" / name
                pkg.mkdir(parents=True)
                (pkg / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
            ok, lines = self.frame.deps_report(Path(visual))
        text = "\n".join(lines)
        self.assertFalse(ok)
        self.assertIn("npm ci", text)
        self.assertIn("missing: playwright", text)
        self.assertNotIn("missing: pngjs", text)

    def test_complete_install_reports_the_four_versions(self) -> None:
        with tempfile.TemporaryDirectory() as visual:
            expected = {"axe-core": "4.14.0", "pixelmatch": "6.0.0", "pngjs": "7.0.0", "playwright": "1.65.0"}
            for name, version in expected.items():
                pkg = Path(visual) / "node_modules" / name
                pkg.mkdir(parents=True)
                (pkg / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
            ok, lines = self.frame.deps_report(Path(visual))
        text = "\n".join(lines)
        self.assertTrue(ok)
        for name, version in expected.items():
            self.assertIn(f"{name} {version}", text)

    def test_a_directory_without_a_manifest_counts_as_missing(self) -> None:
        # A half-extracted package (dir exists, package.json gone) must not pass: the shot step
        # would still fail inside Node.
        with tempfile.TemporaryDirectory() as visual:
            (Path(visual) / "node_modules" / "playwright").mkdir(parents=True)
            ok, lines = self.frame.deps_report(Path(visual))
        self.assertFalse(ok)
        self.assertIn("npm ci", "\n".join(lines))


class PreflightCliTest(unittest.TestCase):
    """End to end through the real CLI, against a throwaway home, never the operator's.

    `--preflight` exits 1 when the *installed* plugin is not this checkout's build, and that
    refusal is the NO LIVE WINDOW rule's teeth. But the suite is forbidden to install the
    branch, so a test that reads the operator's `~/.hermes/desktop-plugins/coursebook/` is
    red on every branch that is correctly not installed. The script resolves
    `INSTALLED` from `Path.home()` (which honours `HOME`), so each test gets its own home
    and populates — or deliberately does not populate — the plugin dir itself. No new env
    var, and the printed block is the one the docs quote.
    """

    def _run_preflight(self, home: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--preflight"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
            env={**os.environ, "HOME": str(home)},
        )

    def _installed_plugin(self, home: Path) -> Path:
        return home / ".hermes" / "desktop-plugins" / "coursebook" / "plugin.js"

    def test_preflight_prints_four_versions_when_installed(self) -> None:
        visual = ROOT / "visual" / "node_modules"
        installed = all((visual / name / "package.json").is_file() for name in
                        ("axe-core", "pixelmatch", "pngjs", "playwright"))
        if not installed:
            self.skipTest("visual/node_modules is absent in this checkout; run `cd visual && npm ci`")
        with tempfile.TemporaryDirectory() as home:
            target = self._installed_plugin(Path(home))
            target.parent.mkdir(parents=True)
            target.write_bytes((ROOT / "desktop" / "plugin.js").read_bytes())
            run = self._run_preflight(Path(home))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        branch_sha = hashlib.sha256((ROOT / "desktop" / "plugin.js").read_bytes()).hexdigest()
        self.assertIn(f"installed plugin   {branch_sha}", run.stdout,
                      "preflight must read the temp home's install, not the operator's")
        for name in ("axe-core", "pixelmatch", "pngjs", "playwright"):
            self.assertRegex(run.stdout, rf"{name} \d+\.\d+", f"preflight must print the {name} version")

    def test_preflight_still_refuses_when_the_installed_build_is_stale(self) -> None:
        # The human path: a branch that is not installed must still refuse loudly, or a
        # window review would photograph a different module. Only the *test* installs a
        # build, and it installs it into its own temp home.
        visual = ROOT / "visual" / "node_modules"
        installed = all((visual / name / "package.json").is_file() for name in
                        ("axe-core", "pixelmatch", "pngjs", "playwright"))
        if not installed:
            self.skipTest("visual/node_modules is absent in this checkout; run `cd visual && npm ci`")
        with tempfile.TemporaryDirectory() as home:
            target = self._installed_plugin(Path(home))
            target.parent.mkdir(parents=True)
            target.write_bytes(b"// some other build\n")
            run = self._run_preflight(Path(home))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("REFUSE a window review", run.stdout)
        self.assertIn("the installed module is not this checkout's build.", run.stdout)
        self.assertIn("cp desktop/plugin.js ~/.hermes/desktop-plugins/coursebook/plugin.js", run.stdout)
        branch_sha = hashlib.sha256((ROOT / "desktop" / "plugin.js").read_bytes()).hexdigest()
        self.assertIn(f"branch plugin.js   {branch_sha}", run.stdout)
        self.assertRegex(run.stdout, r"installed plugin   [0-9a-f]{64}\n")
        self.assertNotIn(branch_sha, run.stdout.split("installed plugin")[1].split("\n")[0])
        for name in ("axe-core", "pixelmatch", "pngjs", "playwright"):
            self.assertRegex(run.stdout, rf"{name} \d+\.\d+", f"the refusal must still print {name}")


if __name__ == "__main__":
    unittest.main()
