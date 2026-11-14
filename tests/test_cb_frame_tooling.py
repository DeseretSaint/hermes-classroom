"""The frame rig refuses in words when its gitignored renderer deps are absent.

`scripts/cb-frame.py` spawns the shot script with `NODE_PATH=<repo>/visual/node_modules`, and that
directory is gitignored. On a fresh clone, after `git clean`, or in a pruned scratch worktree the
first frame used to die inside Node with `Cannot find module 'playwright'` and a stack trace, which
reads as a code bug rather than a missing install. Preflight now answers first and names the fix.

These tests mock the visual directory: they never move, delete or install the real
`visual/node_modules`.
"""

from __future__ import annotations

import importlib.util
import json
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
    """End to end through the real CLI, against whatever this checkout actually has installed."""

    def test_preflight_prints_four_versions_when_installed(self) -> None:
        visual = ROOT / "visual" / "node_modules"
        installed = all((visual / name / "package.json").is_file() for name in
                        ("axe-core", "pixelmatch", "pngjs", "playwright"))
        if not installed:
            self.skipTest("visual/node_modules is absent in this checkout; run `cd visual && npm ci`")
        run = subprocess.run(
            [sys.executable, str(SCRIPT), "--preflight"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=300,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        for name in ("axe-core", "pixelmatch", "pngjs", "playwright"):
            self.assertRegex(run.stdout, rf"{name} \d+\.\d+", f"preflight must print the {name} version")


if __name__ == "__main__":
    unittest.main()
