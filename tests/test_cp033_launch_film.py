"""CP-033: the launch film's documents, its animatic and its driver stay tied to the build.

These tests exist because a launch film is the easiest place in a repository to drift: a caption
gets a number nobody recorded, a driver keeps a selector that was renamed, an animatic outlives the
grid it was cut to. Each assertion below reads the shipped artefact, not a copy of it.

What this does not prove: that any frame is a capture of the product. Frames in the animatic are
reference plates and say so; parity evidence still comes only from ``scripts/cp-capture.mjs`` and its
stamp. That gap is the card's known gap, not something a test can close.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCH = ROOT / "docs" / "launch"
ANIMATIC = LAUNCH / "animatic"
BEATS = ANIMATIC / "beats.json"
MANIFEST = ANIMATIC / "manifest.json"
STEPS = LAUNCH / "cp-demo.steps.json"
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

PLACEHOLDER_WORDS = ("PLACEHOLDER", "NOT THE BUILD")
STEP_KINDS = {"navigate", "click", "type", "wait", "hover-sweep", "marker", "assert"}
# Markers that are not shot boundaries.
TAKE_MARKERS = {"take-start", "take-end"}
# Shots whose picture is a live window state. The word cards and the end card are cut in the edit.
DRIVEN_FRAMES = {
    "S2-reveal",
    "S3-proof1-shelf",
    "S4a-proof2-answer",
    "S4b-proof2-row",
    "S5a-proof3-close",
    "S5b-proof3-resume",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LaunchDocuments(unittest.TestCase):
    def test_brief_is_a_brief(self):
        text = (LAUNCH / "brief.md").read_text(encoding="utf-8")
        self.assertIn("A chat answers. Coursebook makes the next step depend on what you did.", text)
        self.assertIn("Crafted film", text)
        for word in ("Audience", "Runtime", "proofs"):
            self.assertIn(word, text)
        # The event rules the cut is built to, from the preflight checklist.
        self.assertIn("strictly under 90 s", text)
        self.assertIn("@NousResearch", text)

    def test_brief_refuses_the_claims_the_product_cannot_make(self):
        text = (LAUNCH / "brief.md").read_text(encoding="utf-8").lower()
        for refused in ("coppa", "native-speaker-reviewed", "proven to improve learning"):
            self.assertIn(refused, text)
        # A refusal must never read as an assertion.
        self.assertNotIn("we are coppa", text)
        self.assertNotIn("is coppa compliant", text)

    def test_script_has_a_table_and_a_beat_sheet(self):
        text = (LAUNCH / "SCRIPT.md").read_text(encoding="utf-8")
        self.assertIn("| # | In → out (s) | Picture", text)
        self.assertIn("## 2. Beat sheet", text)
        self.assertIn("75.00 s", text)

    def test_animatic_document_names_every_placeholder(self):
        text = (ANIMATIC.parent / "ANIMATIC.md").read_text(encoding="utf-8")
        self.assertIn("PLACEHOLDER", text)
        spec = json.loads(BEATS.read_text(encoding="utf-8"))
        for frame in spec["frames"]:
            if frame.get("plate"):
                self.assertIn(frame["id"], text, f"{frame['id']} is a plate frame and must be listed")


class BeatGrid(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(BEATS.read_text(encoding="utf-8"))

    def test_cut_is_the_target_length_and_under_the_ceiling(self):
        total = sum(frame["seconds"] for frame in self.spec["frames"])
        self.assertEqual(total, 75.0)
        self.assertLess(total, self.spec["ceiling_seconds"])
        self.assertLess(75.0, 90)

    def test_every_frame_starts_on_its_beat(self):
        beat = 0
        for frame in self.spec["frames"]:
            self.assertEqual(frame["start_beat"], beat, frame["id"])
            self.assertEqual(frame["seconds"], frame["seconds"] * 2 / 2)
            self.assertEqual(
                round(frame["seconds"] / self.spec["seconds_per_beat"]),
                frame["seconds"] / self.spec["seconds_per_beat"],
                f"{frame['id']} is not a whole number of beats",
            )
            beat += round(frame["seconds"] / self.spec["seconds_per_beat"])
        self.assertEqual(beat, 150)

    def test_hook_problem_reveal_and_end_are_where_the_brief_says(self):
        frames = {frame["id"]: frame for frame in self.spec["frames"]}
        self.assertEqual(frames["S0-hook"]["seconds"], 3)
        self.assertEqual(frames["S2-reveal"]["start_beat"], 18)
        self.assertEqual(self.spec["frames"][-1]["kind"], "end")
        self.assertTrue(frames["S8-end"]["repo"].startswith("github.com/"))


class PlateProvenance(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(BEATS.read_text(encoding="utf-8"))

    def test_plate_frames_carry_a_visible_placeholder_chip(self):
        for frame in self.spec["frames"]:
            if not frame.get("plate"):
                continue
            chip = frame.get("chip", "")
            for word in PLACEHOLDER_WORDS:
                self.assertIn(word, chip, f"{frame['id']} chip must say {word}")

    def test_plate_bytes_match_the_pinned_prefix(self):
        for frame in self.spec["frames"]:
            if not frame.get("plate"):
                continue
            path = ROOT / frame["plate"]
            self.assertTrue(path.exists(), f"{frame['id']} plate missing: {frame['plate']}")
            digest = sha256(path)
            self.assertTrue(
                digest.startswith(frame["plate_sha256_prefix"]),
                f"{frame['id']}: {frame['plate']} is {digest[:16]}, pinned {frame['plate_sha256_prefix']}",
            )


class AnimaticArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MANIFEST.exists():
            raise unittest.SkipTest("animatic not built: run node scripts/cp-animatic.mjs")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_matches_the_spec(self):
        spec = json.loads(BEATS.read_text(encoding="utf-8"))
        self.assertEqual(self.manifest["total_seconds"], 75.0)
        self.assertEqual(
            [frame["id"] for frame in self.manifest["frames"]],
            [frame["id"] for frame in spec["frames"]],
        )
        self.assertEqual(self.manifest["spec_sha256"], sha256(BEATS))

    def test_every_frame_file_is_the_one_that_was_hashed(self):
        for frame in self.manifest["frames"]:
            path = ANIMATIC / frame["png"]
            self.assertTrue(path.exists(), f"{frame['id']} frame missing")
            self.assertEqual(sha256(path), frame["png_sha256"], frame["id"])

    def test_the_video_is_the_cut_it_claims(self):
        video = ANIMATIC / "animatic.mp4"
        self.assertTrue(video.exists())
        self.assertEqual(sha256(video), self.manifest["video"]["sha256"])
        if not shutil.which("ffprobe"):
            self.skipTest("ffprobe not installed")
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "default=nw=1", str(video)],
            check=True, capture_output=True, text=True,
        )
        values = dict(line.split("=") for line in probe.stdout.strip().splitlines())
        self.assertAlmostEqual(float(values["duration"]), 75.0, places=2)
        self.assertLess(float(values["duration"]), 90)
        self.assertEqual(int(values["size"]), self.manifest["video"]["probed_bytes"])


class DriverSteps(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(STEPS.read_text(encoding="utf-8"))
        self.plugin = PLUGIN_JS.read_text(encoding="utf-8")
        self.animatic = json.loads(BEATS.read_text(encoding="utf-8"))

    def test_step_shapes(self):
        for index, step in enumerate(self.spec["steps"]):
            self.assertIn(step["kind"], STEP_KINDS, f"step {index}")
            if step["kind"] == "navigate":
                self.assertTrue(step.get("hash") or step.get("url"), f"step {index}")
            if step["kind"] == "click":
                self.assertTrue(step.get("selector") or step.get("text_any"), f"step {index}")
            if step["kind"] == "type":
                self.assertTrue(step.get("selector"), f"step {index}")
                self.assertIsInstance(step.get("text"), str)
            if step["kind"] == "wait":
                self.assertTrue(step.get("ms") or step.get("for"), f"step {index}")
            if step["kind"] == "marker":
                self.assertTrue(step.get("id"), f"step {index}")

    def test_every_selector_is_an_attribute_the_module_actually_renders(self):
        for step in self.spec["steps"]:
            for token in step.get("selector", "").split(",") + [step.get("for", "")]:
                for attr in _attributes(token):
                    self.assertTrue(
                        attr in self.plugin,
                        f"{attr} is not rendered by desktop/plugin.js",
                    )

    def test_markers_cover_every_window_driven_shot(self):
        frame_ids = {frame["id"] for frame in self.animatic["frames"]}
        markers = [step["id"] for step in self.spec["steps"] if step["kind"] == "marker"]
        for marker in markers:
            self.assertTrue(marker in frame_ids or marker in TAKE_MARKERS, f"unknown marker {marker}")
        # Word cards and the end card are cut in the edit; the rest are window states.
        for shot in sorted(DRIVEN_FRAMES):
            self.assertIn(shot, markers, f"{shot} has no marker, so the editor cannot cut to it")
        for shot in sorted(frame_ids - DRIVEN_FRAMES):
            self.assertNotIn(shot, markers, f"{shot} is editorial and must not pretend to be driven")

    def test_driver_and_renderer_are_syntactically_intact(self):
        for script in ("cp-demo.mjs", "cp-animatic.mjs"):
            if not shutil.which("node"):
                self.skipTest("node not installed")
            result = subprocess.run(
                ["node", "--check", str(ROOT / "scripts" / script)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


def _attributes(selector: str) -> list[str]:
    out = []
    for part in selector.split(","):
        for chunk in part.split():
            if chunk.startswith("[data-cb-"):
                name = chunk[1:chunk.index("]")].split("=")[0]
                out.append(name)
    return out


if __name__ == "__main__":
    unittest.main()
