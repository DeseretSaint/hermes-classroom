"""UP-49 — the accessibility audit answers page rules and cannot swallow its own crash.

`visual/audit.mjs` ran axe against `[data-cb-route]`, so the page-level rules
(`html-has-lang`, `landmark-one-main`, `page-has-heading-one`) were never evaluated, and an
exception during injection was recorded as `{violations: []}` — a green report that measured
nothing.

These tests drive the shipped audit script headlessly against the committed fixture page. The
plugin only paints inside the Desktop app, so a fixture page is the headless seam; the fixture
run and the live route loop share the same `runAxe()` helper, and the static test pins that the
live loop still calls it.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "visual" / "audit.mjs"
FIXTURES = ROOT / "visual" / "fixtures"
AXE = ROOT / "visual" / "node_modules" / "axe-core" / "axe.min.js"


def run_audit(*args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(AUDIT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@unittest.skipUnless(
    shutil.which("node") and shutil.which("chromium"),
    "needs node and the system chromium the visual tooling already requires",
)
@unittest.skipUnless(
    AXE.is_file(),
    "visual/node_modules is gitignored and absent — run `cd visual && npm ci`",
)
class AxeDocumentScopeTest(unittest.TestCase):
    def test_a_fixture_without_lang_fails_naming_html_has_lang(self) -> None:
        fixture = FIXTURES / "axe-page.html"
        source = fixture.read_text(encoding="utf-8")
        self.assertIn('<html lang="en">', source, "the fixture must start with a language")
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "no-lang.html"
            page.write_text(source.replace('<html lang="en">', "<html>"), encoding="utf-8")
            proc = run_audit("--fixture", str(page))
        output = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, f"a page without lang must fail the audit:\n{output}")
        self.assertIn("html-has-lang", output, f"the failure must name the rule:\n{output}")
        self.assertNotIn("PASS", output.splitlines()[-1:], f"the audit must not end on PASS:\n{output}")

    def test_a_throwing_injection_fails_the_audit_not_an_empty_pass(self) -> None:
        proc = run_audit("--fixture", str(FIXTURES / "axe-injection-blocked.html"))
        output = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, f"a crashed injection must fail the audit:\n{output}")
        self.assertIn("axe could not run", output, f"the crash must be reported:\n{output}")
        self.assertNotIn("violations: []", output, f"an empty violation list must not stand in for a pass:\n{output}")

    def test_the_shipped_fixture_passes(self) -> None:
        proc = run_audit("--fixture", str(FIXTURES / "axe-page.html"))
        output = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, f"the committed fixture must be axe-clean:\n{output}")
        self.assertIn("violations=0", output)

    def test_the_live_route_loop_runs_axe_on_the_document(self) -> None:
        source = AUDIT.read_text(encoding="utf-8")
        self.assertIn("window.axe.run(document", source, "axe must be scoped to the document")
        self.assertIn("await runAxe(frame)", source, "the live route loop must use the shared helper")
        self.assertNotIn(
            "document.querySelector('[data-cb-route]') || document.body",
            source,
            "the route-scoped axe call is the bug this card removes",
        )
        self.assertNotIn("{ violations: [], error:", source, "a crash must not be recorded as zero violations")


if __name__ == "__main__":
    unittest.main()
