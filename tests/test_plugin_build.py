"""`desktop/plugin.js` is generated; the committed file must equal its segments byte for byte.

The Desktop runtime loads exactly one module, so the source is split into ordered segments under
`desktop/src/NN-<name>.js` and `scripts/build_plugin.py` concatenates them back into
`desktop/plugin.js`. These tests are the guard that makes that safe:

- the committed module is the exact concatenation of the committed segments (so a hand edit of the
  generated file, or a segment edit shipped without a rebuild, fails here);
- the build is deterministic and rewrites an identical file;
- the segment set is ordered, uniquely named, and cut only at a top-level boundary;
- static imports live in the header segment only, and the module's export block stays last.

A failing test means the generated file and its source disagree. Regenerate, never patch the ship
artifact by hand.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "desktop" / "src"
PLUGIN = ROOT / "desktop" / "plugin.js"
BUILD = ROOT / "scripts" / "build_plugin.py"

NAME_RE = re.compile(r"^(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.js$")
#: A segment may only start where the original file had a top-level boundary: a banner comment, a
#: doc comment for a top-level declaration, or the declaration itself.
BOUNDARY_RE = re.compile(r"^(//|/\*|function\s|async\s+function\s|const\s|let\s|var\s|export\s)")


def _load_build_module():
    """Import `scripts/build_plugin.py` without requiring `scripts` to be a package."""
    spec = importlib.util.spec_from_file_location("cb_build_plugin", BUILD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _segments() -> list[Path]:
    return sorted(path for path in SRC.glob("*.js") if path.is_file())


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PluginBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = _load_build_module()
        cls.segments = _segments()

    def test_segments_exist_and_are_ordered(self) -> None:
        self.assertTrue(self.segments, "desktop/src has no segments")
        orders = []
        for path in self.segments:
            match = NAME_RE.match(path.name)
            self.assertIsNotNone(match, f"{path.name} is not NN-<name>.js")
            assert match is not None
            orders.append(int(match.group(1)))
        self.assertEqual(orders, sorted(orders), "segment prefixes are not in build order")
        self.assertEqual(len(orders), len(set(orders)), "two segments share a position prefix")
        self.assertEqual(self.segments[0].name, "00-header.js", "00-header.js must own the file banner")

    def test_every_segment_starts_at_a_top_level_boundary(self) -> None:
        for path in self.segments:
            first = path.read_bytes().split(b"\n", 1)[0].decode("utf-8")
            self.assertRegex(
                first,
                BOUNDARY_RE,
                f"{path.name} starts mid-expression: {first[:80]!r}",
            )

    def test_only_the_header_segment_has_static_imports(self) -> None:
        for path in self.segments[1:]:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r"^import\s", text, re.MULTILINE),
                f"{path.name} has a static import; imports belong in 00-header.js so the built "
                "module keeps one import block",
            )

    def test_committed_plugin_is_the_concatenation_of_the_segments(self) -> None:
        rebuilt = self.build.build_bytes(ROOT)
        committed = PLUGIN.read_bytes()
        self.assertEqual(
            hashlib.sha256(rebuilt).hexdigest(),
            hashlib.sha256(committed).hexdigest(),
            "desktop/plugin.js is not the concatenation of desktop/src; "
            "run `python3 scripts/build_plugin.py` and commit the result",
        )

    def test_generated_assets_are_concatenated_after_the_header(self) -> None:
        # CP-020a: CB_ASSETS must be bound before any component body can read it, and the
        # generated segment must reach the one module the runtime loads.
        built = self.build.build_bytes(ROOT).decode("utf-8")
        header = (SRC / "00-header.js").read_text(encoding="utf-8")
        assets = built.index("const CB_ASSETS = Object.freeze(") if "const CB_ASSETS = Object.freeze(" in built else -1
        self.assertIn("const CB_ASSETS = Object.freeze(", built)
        self.assertGreaterEqual(assets, len(header), "CB_ASSETS is not concatenated after the header")
        self.assertLess(assets, built.index("const CB_TOKENS_JSON"), "CB_ASSETS is after the module body")

    def test_module_has_one_trailing_newline_and_the_export_block_is_last(self) -> None:
        committed = PLUGIN.read_bytes()
        self.assertTrue(committed.endswith(b"\n"))
        self.assertFalse(committed.endswith(b"\n\n"))
        self.assertTrue(self.segments[-1].read_bytes().rstrip().endswith(b"}"))
        self.assertIn(b"export {", self.segments[-1].read_bytes())

    def test_build_check_passes_on_the_clean_tree(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUILD), "--check", "--quiet"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_direct_edit_of_the_generated_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._copy_tree(Path(temporary))
            plugin = root / "desktop" / "plugin.js"
            plugin.write_bytes(plugin.read_bytes() + b"\n// hand edit of the generated file\n")
            result = subprocess.run(
                [sys.executable, str(BUILD), "--check", "--root", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("desktop/plugin.js", result.stderr)

    def test_segment_edit_without_a_rebuild_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._copy_tree(Path(temporary))
            segment = sorted((root / "desktop" / "src").glob("*.js"))[3]
            segment.write_bytes(segment.read_bytes() + b"\n// unbuilt segment edit\n")
            result = subprocess.run(
                [sys.executable, str(BUILD), "--check", "--root", str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1, result.stdout)

    def test_build_rewrites_the_generated_file_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._copy_tree(Path(temporary))
            plugin = root / "desktop" / "plugin.js"
            expected = plugin.read_bytes()
            plugin.write_bytes(b"stale\n")
            result = subprocess.run(
                [sys.executable, str(BUILD), "--root", str(root), "--quiet"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(plugin.read_bytes(), expected)

    def test_duplicate_or_misnamed_positions_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._copy_tree(Path(temporary))
            src = root / "desktop" / "src"
            first = sorted(src.glob("*.js"))[0]
            (src / "00-again.js").write_bytes(first.read_bytes())
            with self.assertRaises(self.build.SegmentError):
                self.build.segment_paths(root)
            (src / "00-again.js").unlink()
            (src / "scratch copy.js").write_bytes(b"// not a segment\n")
            with self.assertRaises(self.build.SegmentError):
                self.build.segment_paths(root)

    def _copy_tree(self, destination: Path) -> Path:
        """A minimal checkout: the generated module, its segments and the build script."""
        (destination / "desktop").mkdir(parents=True)
        (destination / "scripts").mkdir(parents=True)
        shutil.copy2(PLUGIN, destination / "desktop" / "plugin.js")
        shutil.copytree(SRC, destination / "desktop" / "src")
        # CP-020a: the generated CB_ASSETS segment is a build input concatenated after the header.
        shutil.copy2(ROOT / "desktop" / "cb-assets.generated.js",
                     destination / "desktop" / "cb-assets.generated.js")
        shutil.copy2(BUILD, destination / "scripts" / "build_plugin.py")
        return destination


if __name__ == "__main__":
    unittest.main()
