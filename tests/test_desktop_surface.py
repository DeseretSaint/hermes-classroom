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
SRC_DIR = DESKTOP_DIR / "src"


def desktop_sources() -> list[Path]:
    """The modules the runtime may load: exactly one, at the top of `desktop/`."""
    return sorted(DESKTOP_DIR.glob("*.js"))


def build_sources() -> list[Path]:
    """Ordered build inputs concatenated into `plugin.js` (CP-006); never loaded as modules."""
    return sorted(SRC_DIR.glob("*.js"))


def all_desktop_js() -> list[Path]:
    """Every Desktop JS file, for the content lints (generated module plus its build inputs)."""
    return sorted(DESKTOP_DIR.rglob("*.js"))


class DesktopSurfaceTest(unittest.TestCase):
    def test_desktop_half_exists(self) -> None:
        self.assertTrue((DESKTOP_DIR / "plugin.js").is_file())

    def test_no_forbidden_constructs(self) -> None:
        sources = all_desktop_js()
        self.assertTrue(sources, "no desktop JS files found")
        for source in sources:
            with self.subTest(file=source.name):
                findings = desktop_surface_findings(source.read_text(encoding="utf-8"))
                self.assertEqual(findings, [], f"{source.name}: {findings}")

    def test_no_review_cues(self) -> None:
        for source in all_desktop_js():
            with self.subTest(file=source.name):
                cues = desktop_review_findings(source.read_text(encoding="utf-8"))
                self.assertEqual(cues, [], f"{source.name}: {cues}")

    def test_single_module_only(self) -> None:
        # A runtime plugin is one file: relative imports and extra modules do not resolve. Since
        # CP-006 the source lives in ordered segments under desktop/src that are concatenated into
        # plugin.js; they are build inputs, not loadable modules, so only plugin.js may sit on the
        # module path.
        self.assertEqual([p.name for p in desktop_sources()], ["plugin.js"])
        stray = [p for p in DESKTOP_DIR.rglob("*.js") if p.parent not in (DESKTOP_DIR, SRC_DIR)]
        self.assertEqual(stray, [], "Desktop JS outside plugin.js and desktop/src would ship as a module")

    def test_build_inputs_live_only_in_desktop_src(self) -> None:
        segments = build_sources()
        self.assertTrue(segments, "desktop/src has no build inputs")
        for segment in segments:
            self.assertNotEqual(segment.name, "plugin.js", "the generated module is not a build input")
            self.assertEqual(segment.parent, SRC_DIR)

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
