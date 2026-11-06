"""The Desktop half must stay inside the plugin SDK surface (catalog rule 8).

Uses the same lint the CLI runs at admission, so this test fails for the same reasons
``hermes plugins validate`` would.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from hermes_cli.plugin_validate_desktop import (
    desktop_review_findings,
    desktop_surface_findings,
)

ROOT = Path(__file__).resolve().parent.parent
DESKTOP_DIR = ROOT / "desktop"


def desktop_sources() -> list[Path]:
    return sorted(DESKTOP_DIR.rglob("*.js"))


class DesktopSurfaceTest(unittest.TestCase):
    def test_desktop_half_exists(self) -> None:
        self.assertTrue((DESKTOP_DIR / "plugin.js").is_file())

    def test_no_forbidden_constructs(self) -> None:
        sources = desktop_sources()
        self.assertTrue(sources, "no desktop JS files found")
        for source in sources:
            with self.subTest(file=source.name):
                findings = desktop_surface_findings(source.read_text(encoding="utf-8"))
                self.assertEqual(findings, [], f"{source.name}: {findings}")

    def test_no_review_cues(self) -> None:
        for source in desktop_sources():
            with self.subTest(file=source.name):
                cues = desktop_review_findings(source.read_text(encoding="utf-8"))
                self.assertEqual(cues, [], f"{source.name}: {cues}")

    def test_single_module_only(self) -> None:
        # A runtime plugin is one file: relative imports and extra modules do not resolve.
        self.assertEqual([p.name for p in desktop_sources()], ["plugin.js"])

    def test_imports_are_limited_to_the_sdk_and_react(self) -> None:
        import re

        source = (DESKTOP_DIR / "plugin.js").read_text(encoding="utf-8")
        specifiers = re.findall(r"^import\s[^'\"]*['\"]([^'\"]+)['\"]", source, flags=re.MULTILINE)
        allowed = {"@hermes/plugin-sdk", "react", "react/jsx-runtime"}
        self.assertTrue(specifiers, "no imports found")
        for specifier in specifiers:
            self.assertIn(specifier, allowed, f"unsupported import {specifier!r}")

    def test_no_jsx_syntax(self) -> None:
        # The disk door loads the file uncompiled, so JSX would fail to parse at load time.
        source = (DESKTOP_DIR / "plugin.js").read_text(encoding="utf-8")
        self.assertIn("jsx(", source)
        for tag in ("<div", "<span", "<button", "</"):
            self.assertNotIn(tag, source, f"JSX-looking markup {tag!r} in a runtime plugin")


if __name__ == "__main__":
    unittest.main()
