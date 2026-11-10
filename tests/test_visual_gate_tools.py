"""The binding visual gate (docs/concept-parity/VISUAL-GATE.md) must be runnable from a fresh worktree.

The gate was announced to every screen card before its tools were on master: the doc, the CDP finder
and the comparison script existed only as untracked files in the operator checkout, so a card that
followed the instructions from its own worktree hit "no such file". This test pins the three files the
gate names, so the instruction and the repository cannot drift apart again.
"""

import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_DOC = ROOT / "docs" / "concept-parity" / "VISUAL-GATE.md"


class VisualGateToolsTest(unittest.TestCase):
    def test_gate_doc_exists(self):
        self.assertTrue(GATE_DOC.is_file(), "the binding gate doc is missing")

    def test_gate_doc_named_tools_exist(self):
        text = GATE_DOC.read_text(encoding="utf-8")
        named = set(re.findall(r"\b(?:node|bash)\s+([\w./-]+\.(?:mjs|sh))", text))
        self.assertTrue(named, "the gate doc names no tools")
        for name in sorted(named):
            for base in (ROOT / "visual", ROOT):
                candidate = base / name
                if candidate.is_file():
                    break
            else:
                self.fail(f"gate doc names {name}, which is not in the repository")

    def test_compare_ref_is_executable(self):
        path = ROOT / "scripts" / "compare-ref.sh"
        self.assertTrue(path.is_file(), "scripts/compare-ref.sh is missing")
        self.assertTrue(os.access(path, os.X_OK), "scripts/compare-ref.sh is not executable")

    def test_compare_ref_parses(self):
        path = ROOT / "scripts" / "compare-ref.sh"
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash not available")
        result = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cdp_finder_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not available")
        for name in ("find-cdp.mjs", "find.mjs"):
            path = ROOT / "visual" / name
            self.assertTrue(path.is_file(), f"visual/{name} is missing")
            result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
