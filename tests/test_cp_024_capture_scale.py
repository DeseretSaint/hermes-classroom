"""CP-024 review round 3 — evidence scale integrity.

Round 3 was rejected because 14 of 15 captured frames were shot at a 32 px root font while every
cell name said ``--100--``: the capture door only *set* the root font for the 200 % cell and never
restored it, and the verifier only checked the root font when the name's scale was not 100. These
tests pin both halves of the fix:

* ``scripts/cp-capture.mjs`` sets the root font explicitly for every live cell (default ``16px``),
  records the requested value, and restores the page's prior inline value in its ``finally``;
* ``verify_stamps.check_packet`` asserts the root font for *every* cell, checks the frame bytes
  against the stamp, and refuses two cells that share one frame hash.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "scripts" / "cp-capture.mjs"
VERIFY = ROOT / "docs" / "visual-review" / "cp-024" / "verify_stamps.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("cp024_verify_stamps", VERIFY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VERIFY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stamp(name: str, *, sha: str, width: int, theme: str, root_px: str, requested: str, frame_sha: str) -> dict:
    return {
        "name": name,
        "ok": True,
        "gates": {"module_sha": True, "route_present": True},
        "plugin": {"window_sha256": sha},
        "route": {
            "width": width,
            "theme": theme,
            "text_scale_root_px": root_px,
            "course_detail": "overview",
            "word_wraps": [],
        },
        "capture": {"sha256": frame_sha, "root_font": {"requested": requested, "prior_inline": None}},
    }


class CaptureScaleSourceTests(unittest.TestCase):
    def test_capture_door_sets_and_restores_the_root_font_for_every_cell(self) -> None:
        source = CAPTURE.read_text(encoding="utf-8")
        # Default is explicit: a cell without --root-font is a 100 % cell, not "whatever the last
        # cell left behind" on a shared --no-reload page.
        self.assertIn("const rootFont = rootFontArg && rootFontArg !== true ? String(rootFontArg) : '16px'", source)
        self.assertIn("document.documentElement.style.fontSize = ${JSON.stringify(rootFont)}", source)
        self.assertIn("rootFontPrior", source)
        self.assertIn("removeProperty('font-size')", source)
        self.assertIn("root_font: rootFont ?", source)
        # The restore must live in the live-capture finally, after the screenshot, not in the
        # happy path where a refusal would skip it.
        finally_at = source.index("// Restore the page's own root font")
        self.assertGreater(finally_at, source.index("return finishStamp({ probe, gate, png"))

    def test_capture_matrix_passes_the_scale_explicitly_for_baseline_cells(self) -> None:
        script = (ROOT / "docs" / "visual-review" / "cp-024" / "capture.sh").read_text(encoding="utf-8")
        self.assertIn("--root-font 16px", script)
        self.assertIn("--root-font 32px", script)


class VerifyStampsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = load_verifier()
        self.sha = "a" * 64
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_cell(self, name: str, record: dict, png_bytes: bytes) -> None:
        (self.out / f"{name}.stamp.json").write_text(json.dumps(record), encoding="utf-8")
        (self.out / f"{name}.png").write_bytes(png_bytes)

    def test_a_100_cell_shot_at_32px_is_rejected(self) -> None:
        name = "course-home--1049--light--100--default"
        png = b"frame-default"
        self.write_cell(
            name,
            stamp(name, sha=self.sha, width=1049, theme="light", root_px="32px", requested="32px",
                  frame_sha=hashlib.sha256(png).hexdigest()),
            png,
        )
        _, problems = self.verifier.check_packet(self.out, self.sha)
        self.assertTrue(any("rendered root font 32px != 16px" in problem for problem in problems), problems)
        self.assertTrue(any("capture requested root font '32px' != 16px" in problem for problem in problems), problems)

    def test_a_clean_100_cell_passes(self) -> None:
        name = "course-home--1049--light--100--default"
        png = b"frame-default"
        self.write_cell(
            name,
            stamp(name, sha=self.sha, width=1049, theme="light", root_px="16px", requested="16px",
                  frame_sha=hashlib.sha256(png).hexdigest()),
            png,
        )
        names, problems = self.verifier.check_packet(self.out, self.sha)
        self.assertEqual(names, [name])
        self.assertEqual(problems, [])

    def test_a_200_cell_must_record_32px(self) -> None:
        name = "course-home--460--light--200--text-200"
        png = b"frame-text-200"
        self.write_cell(
            name,
            stamp(name, sha=self.sha, width=460, theme="light", root_px="16px", requested="32px",
                  frame_sha=hashlib.sha256(png).hexdigest()),
            png,
        )
        _, problems = self.verifier.check_packet(self.out, self.sha)
        self.assertTrue(any("rendered root font 16px != 32px" in problem for problem in problems), problems)

    def test_two_cells_sharing_one_frame_are_rejected(self) -> None:
        png = b"identical-frame"
        frame_sha = hashlib.sha256(png).hexdigest()
        for width, theme, state in [(1049, "light", "default"), (1049, "light", "course-end")]:
            name = f"course-home--{width}--{theme}--100--{state}"
            self.write_cell(
                name,
                stamp(name, sha=self.sha, width=width, theme=theme, root_px="16px", requested="16px",
                      frame_sha=frame_sha),
                png,
            )
        _, problems = self.verifier.check_packet(self.out, self.sha)
        duplicate = [problem for problem in problems if "byte-identical" in problem]
        self.assertEqual(len(duplicate), 1, problems)

    def test_a_frame_whose_bytes_do_not_match_its_stamp_is_rejected(self) -> None:
        name = "course-home--1049--light--100--default"
        self.write_cell(
            name,
            stamp(name, sha=self.sha, width=1049, theme="light", root_px="16px", requested="16px",
                  frame_sha="f" * 64),
            b"different-bytes",
        )
        _, problems = self.verifier.check_packet(self.out, self.sha)
        self.assertTrue(any("frame sha" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
