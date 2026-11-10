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
import os
import re
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
REFS = ROOT / "docs" / "concept-parity" / "refs" / "REFS.md"

PLACEHOLDER_WORDS = ("PLACEHOLDER", "NOT THE BUILD")
STEP_KINDS = {"navigate", "click", "type", "wait", "hover-sweep", "marker", "assert", "snapshot", "reconnect"}
# Phrases that claim a measured change or continuity. Presence checks cannot support them, so a step
# note or a launch document may only use them where a snapshot comparison does the measuring.
VALUE_CLAIM_PHRASES = (
    "count moves", "count moved", "the tally changed", "nothing rebuilt",
    "nothing to reconstruct", "went unchanged", "never rebuilt",
)
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
# The owner's own words in REFS.md; the Home plate is outside this scope.
RATIFICATION_SCOPE = "outside of the home page, these images were ratified"
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refs_plate_status() -> dict[str, bool]:
    """Map every image in ``REFS.md`` to whether the owner ratified it.

    The pack states the scope in prose ("outside of the home page, these images were ratified") and
    marks the approved rows with ``(ratified)`` in the role column. A row without that marker is not
    ratified, whatever else its description says.
    """
    status: dict[str, bool] = {}
    for line in REFS.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| R-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        path = cells[1].strip("`")
        status[path] = "(ratified)" in cells[4].lower()
    return status


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

    def test_ratification_status_is_read_from_the_reference_pack(self):
        self.assertIn(RATIFICATION_SCOPE, REFS.read_text(encoding="utf-8"))
        status = refs_plate_status()
        self.assertFalse(status["docs/concept-parity/refs/home.png"], "REFS.md excludes the Home page")
        self.assertTrue(status["docs/concept-parity/refs/classroom.png"])
        for frame in self.spec["frames"]:
            if frame.get("plate"):
                self.assertIn(
                    frame["plate"], status,
                    f"{frame['id']} uses {frame['plate']}, which REFS.md does not list",
                )

    def test_no_launch_document_calls_a_non_ratified_plate_ratified(self):
        unratified = {path for path, ratified in refs_plate_status().items() if not ratified}
        negations = ("not ratified", "unratified", "excluded", "outside of the home page", "target")
        for doc in sorted(LAUNCH.glob("*.md")):
            for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
                low = line.lower()
                if "ratified" not in low:
                    continue
                names = [path for path in unratified if Path(path).name in line]
                if not names:
                    continue
                self.assertTrue(
                    any(negation in low for negation in negations),
                    f"{doc.name}:{number} calls a non-ratified plate ratified: {line.strip()}",
                )

    def test_no_launch_document_generalises_ratification_to_every_plate(self):
        # The class-level overclaim that started this test: "the owner-ratified reference plates".
        for doc in sorted(LAUNCH.glob("*.md")):
            self.assertNotIn(
                "owner-ratified reference plates",
                doc.read_text(encoding="utf-8").lower(),
                f"{doc.name} generalises ratification to plates the owner excluded",
            )

    def test_each_launch_document_states_the_status_of_the_plate_it_names(self):
        for name in ("brief.md", "ANIMATIC.md"):
            text = (LAUNCH / name).read_text(encoding="utf-8")
            home = [line for line in text.splitlines() if "refs/home.png" in line]
            self.assertTrue(home, f"{name} names no Home plate")
            self.assertTrue(
                any("not ratified" in line.lower() for line in home),
                f"{name} must say the Home plate is not ratified",
            )
            classroom = [line for line in text.splitlines() if "refs/classroom.png" in line]
            self.assertTrue(classroom, f"{name} names no Classroom plate")
            self.assertTrue(
                any("ratified" in line.lower() and "not ratified" not in line.lower() for line in classroom),
                f"{name} must say the Classroom plate is ratified",
            )

    def test_stated_plate_count_equals_the_number_of_plate_frames(self):
        plates = [frame for frame in self.spec["frames"] if frame.get("plate")]
        text = (LAUNCH / "ANIMATIC.md").read_text(encoding="utf-8")
        stated = re.findall(
            r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+plate frames\b",
            text, re.IGNORECASE,
        )
        self.assertTrue(stated, "ANIMATIC.md must state how many plate frames it holds")
        for word in stated:
            value = int(word) if word.isdigit() else NUMBER_WORDS.get(word.lower())
            self.assertIsNotNone(value, f"unreadable plate count {word!r}")
            self.assertEqual(
                value, len(plates),
                f"ANIMATIC.md says {word} plate frames; beats.json holds {len(plates)}",
            )
        yes_rows = [line for line in text.splitlines() if line.startswith("| ") and "| **yes**" in line]
        self.assertEqual(
            len(yes_rows), len(plates),
            "§2 must mark exactly the plate frames 'yes'",
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
            if step["kind"] == "snapshot":
                self.assertTrue(step.get("id"), f"step {index}")
                self.assertTrue(step.get("selector"), f"step {index}")
            if step["kind"] == "assert" and step.get("snapshot"):
                self.assertNotEqual(
                    bool(step.get("changed")), bool(step.get("equals")),
                    f"step {index}: a comparison expects exactly one of changed or equals",
                )

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

    def test_driven_markers_fire_after_the_state_they_name(self):
        """A marker stamped before its state names the wrong frame, and the log is what is cut to."""
        steps = self.spec["steps"]

        def first(predicate, label, after=-1):
            for index in range(after + 1, len(steps)):
                if predicate(steps[index]):
                    return index
            self.fail(f"no {label} after step {after}")

        def marker(marker_id):
            return first(
                lambda step: step.get("kind") == "marker" and step.get("id") == marker_id,
                f"marker {marker_id}",
            )

        shelf = first(
            lambda step: step.get("kind") == "wait" and step.get("for") == '[data-cb-home-shelf="ready"]',
            "shelf-settled wait",
        )
        s2 = marker("S2-reveal")
        self.assertGreater(s2, shelf, "S2-reveal fires before the shelf has settled")

        sweep = first(lambda step: step.get("kind") == "hover-sweep", "card-row hover sweep")
        s3 = marker("S3-proof1-shelf")
        self.assertGreater(s3, sweep, "S3-proof1-shelf fires before the card row has been travelled")

        open_course = first(
            lambda step: step.get("kind") == "click" and step.get("wait_for") == "[data-cb-block-check]",
            "course-open click",
        )
        answer = first(
            lambda step: step.get("kind") == "click" and "data-cb-choice" in (step.get("selector") or ""),
            "served-answer click",
            after=open_course,
        )
        s4a = marker("S4a-proof2-answer")
        self.assertGreater(s4a, open_course, "S4a fires before the course has opened on the check")
        self.assertGreater(s4a, answer, "S4a fires before the served answer is entered")

        submit = first(
            lambda step: step.get("kind") == "click" and step.get("wait_for") == "[data-cb-verdict]",
            "submit click",
            after=answer,
        )
        evidence = first(
            lambda step: step.get("kind") == "assert" and "data-cb-evidence-chip" in (step.get("selector") or ""),
            "evidence-chip assert",
            after=submit,
        )
        s4b = marker("S4b-proof2-row")
        self.assertGreater(s4b, submit, "S4b fires before the verdict is on screen")
        self.assertGreater(s4b, evidence, "S4b fires before the recorded row is on screen")

        s5a = marker("S5a-proof3-close")
        self.assertGreater(s5a, s4b, "S5a fires before the verdict state it cuts from")

        resume_nav = first(lambda step: step.get("kind") == "navigate", "resume navigate", after=s5a)
        resume_wait = first(
            lambda step: step.get("kind") == "wait" and "data-cb-block-check" in (step.get("for") or ""),
            "resume wait",
            after=resume_nav,
        )
        s5b = marker("S5b-proof3-resume")
        self.assertGreater(s5b, resume_nav, "S5b fires before the reopened window is navigated")
        self.assertGreater(s5b, resume_wait, "S5b fires before the same pending check is on screen")

    def test_no_two_driven_markers_share_a_cut_point(self):
        steps = self.spec["steps"]
        indexes = [
            index for index, step in enumerate(steps)
            if step.get("kind") == "marker" and step.get("id") in DRIVEN_FRAMES
        ]
        self.assertEqual(len(indexes), len(DRIVEN_FRAMES), "every driven shot needs exactly one marker")
        for left, right in zip(indexes, indexes[1:]):
            self.assertGreater(
                right - left, 1,
                f"driven markers at steps {left} and {right} are consecutive; nothing establishes the second",
            )

    # -- the window transition: a closed window cannot keep one socket, so the take is split in acts

    def test_every_step_belongs_to_an_act_that_runs_in_order(self):
        acts = [step.get("act") for step in self.spec["steps"]]
        self.assertTrue(
            all(isinstance(act, int) and act >= 1 for act in acts),
            f"every step needs a positive integer act, got {acts}",
        )
        self.assertEqual(acts, sorted(acts), "acts must run in file order; a step may not drift back")
        self.assertEqual(
            sorted(set(acts)), list(range(1, max(acts) + 1)),
            f"acts must be contiguous from 1, got {sorted(set(acts))}",
        )

    def test_no_act_holds_both_the_close_and_the_resume(self):
        where = {
            step["id"]: step.get("act") for step in self.spec["steps"]
            if step.get("kind") == "marker" and step.get("id") in {"S5a-proof3-close", "S5b-proof3-resume"}
        }
        self.assertEqual(set(where), {"S5a-proof3-close", "S5b-proof3-resume"})
        self.assertNotEqual(
            where["S5a-proof3-close"], where["S5b-proof3-resume"],
            "one act cannot both close the window and stamp the resume frame; the socket would be dead",
        )

    def test_a_window_transition_sits_between_the_close_and_the_resume(self):
        steps = self.spec["steps"]
        close = next(
            index for index, step in enumerate(steps)
            if step.get("kind") == "marker" and step.get("id") == "S5a-proof3-close"
        )
        resume = next(
            index for index, step in enumerate(steps)
            if step.get("kind") == "marker" and step.get("id") == "S5b-proof3-resume"
        )
        between = steps[close + 1:resume]
        self.assertTrue(
            any(step.get("kind") == "reconnect" for step in between),
            "nothing between the close and the resume step re-attaches to a reopened window",
        )
        # Act two must open with the transition: run on its own with --act 2, it cannot inherit
        # act one's socket, so the first thing it does is attach to the page that was reopened.
        self.assertEqual(steps[close + 1].get("kind"), "reconnect", "act two must open with the transition")

    # -- the answer format: a click into a textarea types nothing, so the take names the format

    def test_the_driven_answer_names_the_selection_format(self):
        steps = self.spec["steps"]
        answer = next(
            index for index, step in enumerate(steps)
            if step.get("kind") == "click" and "data-cb-choice" in (step.get("selector") or "")
        )
        self.assertNotIn(
            "textarea", steps[answer]["selector"],
            "a click into the textarea only focuses it; the take must drive the selection format",
        )
        after = steps[answer + 1]
        target = f"{after.get('selector') or ''} {after.get('for') or ''}"
        self.assertIn(
            '[data-cb-answer-kind="selection"]', target,
            "the step after the answer click must assert the check is the selection format",
        )
        self.assertIn(after.get("kind"), {"assert", "wait"})

    def test_no_document_claims_the_driver_fills_a_text_answer(self):
        phrases = ("whatever its format", "fills a text answer", "types the answer")
        for name in ("SCRIPT.md", "ANIMATIC.md"):
            text = (LAUNCH / name).read_text(encoding="utf-8").lower()
            for phrase in phrases:
                self.assertNotIn(phrase, text, f"{name} claims a format the driver cannot fill: {phrase}")
        for step in self.spec["steps"]:
            note = (step.get("note") or "").lower()
            for phrase in phrases:
                self.assertNotIn(phrase, note, f"step note claims {phrase!r}")
        script = (LAUNCH / "SCRIPT.md").read_text(encoding="utf-8")
        row = next(line for line in script.splitlines() if line.startswith("| `S4a-proof2-answer` |"))
        self.assertIn("selection", row.lower(), "SCRIPT.md §4 must name the selection format for S4a")

    # -- value comparisons: presence is not a comparison, so the marks that claim one measure it

    def test_every_comparison_reads_a_value_the_take_already_measured(self):
        steps = self.spec["steps"]
        taken = {}
        for index, step in enumerate(steps):
            if step.get("kind") == "snapshot":
                self.assertNotIn(step["id"], taken, f"snapshot {step['id']} is taken twice")
                taken[step["id"]] = index
            if step.get("kind") == "assert" and step.get("snapshot"):
                self.assertIn(
                    step["snapshot"], taken,
                    f"step {index} compares {step['snapshot']}, which nothing read before it",
                )
                self.assertLess(taken[step["snapshot"]], index)

    def test_the_two_proofs_that_claim_a_value_compare_it(self):
        steps = self.spec["steps"]

        def window(marker_id):
            end = next(
                index for index, step in enumerate(steps)
                if step.get("kind") == "marker" and step.get("id") == marker_id
            )
            start = 0
            for index in range(end - 1, -1, -1):
                if steps[index].get("kind") == "marker":
                    start = index + 1
                    break
            return start, end

        # S4b: the evidence chip must go from preview to record, measured, before the marker.
        start, end = window("S4b-proof2-row")
        reads = [
            step for step in steps[start:end]
            if step.get("kind") == "snapshot"
            and "data-cb-evidence-chip" in (step.get("selector") or "")
            and step.get("attribute") == "data-cb-evidence-pending"
        ]
        self.assertTrue(reads, "S4b claims the chip became a record but nothing reads its pending state")
        compares = [
            step for step in steps[start:end]
            if step.get("kind") == "assert" and step.get("snapshot") == reads[0]["id"] and step.get("changed")
        ]
        self.assertTrue(compares, "S4b stamps a value change the take never compares")

        # S5b: the check block's identity must be read before the close and compared after the reopen.
        start, end = window("S5b-proof3-resume")
        compares = [
            step for step in steps[start:end]
            if step.get("kind") == "assert" and step.get("equals")
            and "data-cb-block-check" in (step.get("selector") or "")
        ]
        self.assertTrue(compares, "S5b claims the same check survived the reopen but compares nothing")
        taken = next(
            (index for index, step in enumerate(steps)
             if step.get("kind") == "snapshot" and step["id"] == compares[0]["snapshot"]),
            -1,
        )
        close = next(
            index for index, step in enumerate(steps)
            if step.get("kind") == "marker" and step.get("id") == "S5a-proof3-close"
        )
        self.assertGreaterEqual(taken, 0, "S5b compares a snapshot nothing took")
        self.assertLess(taken, close, "S5b's comparison value must be read before the window closes")

    def test_no_document_claims_a_comparison_the_take_does_not_make(self):
        for name in ("SCRIPT.md", "ANIMATIC.md", "brief.md"):
            text = (LAUNCH / name).read_text(encoding="utf-8").lower()
            for phrase in VALUE_CLAIM_PHRASES:
                self.assertNotIn(
                    phrase, text,
                    f"{name} claims {phrase!r}; the step list does not measure that",
                )
        for index, step in enumerate(self.spec["steps"]):
            note = (step.get("note") or "").lower()
            for phrase in VALUE_CLAIM_PHRASES:
                self.assertNotIn(phrase, note, f"step {index} note claims {phrase!r}")
        script = (LAUNCH / "SCRIPT.md").read_text(encoding="utf-8")
        for marker, word in (("S4b-proof2-row", "compare"), ("S5b-proof3-resume", "equals")):
            row = next(line for line in script.splitlines() if line.startswith(f"| `{marker}` |"))
            self.assertIn(word, row.lower(), f"SCRIPT.md §4 must say what {marker} measures")

    def test_setup_names_the_unanswered_check_and_the_reset_between_takes(self):
        setup = " ".join(self.spec.get("setup", [])).lower()
        self.assertIn("unanswered", setup, "setup must require an unanswered check")
        self.assertIn("reset", setup, "setup must say the home is reset between takes")
        script = (LAUNCH / "SCRIPT.md").read_text(encoding="utf-8").lower()
        self.assertIn("unanswered", script, "SCRIPT.md §4 must repeat the unanswered-check precondition")
        self.assertIn("reset", script, "SCRIPT.md §4 must repeat the reset between takes")


class DriverTransitionSelfTest(unittest.TestCase):
    """Execute the driver's own proof that act two lands on a page act one never held."""

    def test_act_two_attaches_to_a_different_page_target(self):
        if not shutil.which("node"):
            self.skipTest("node not installed")
        chromium = os.environ.get("CHROMIUM", "chromium")
        if not shutil.which(chromium):
            self.skipTest(f"{chromium} not installed; the driver's transition proof needs a browser")
        result = subprocess.run(
            ["node", "scripts/cp-demo.mjs", "--selftest"],
            cwd=ROOT, capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(result.returncode, 0, f"{result.stdout}\n{result.stderr}")
        self.assertIn("selftest ok:", result.stdout)
        self.assertIn("transition ok:", result.stdout)
        self.assertIn("(different)", result.stdout)
        # The third leg reopens a page while the second is still open; the driver must skip it.
        self.assertIn("fresh target: true", result.stdout)
        # A value that never moved must stop the take before it stamps anything.
        self.assertIn("snapshot ok:", result.stdout)
        self.assertIn("before its marker", result.stdout)


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
