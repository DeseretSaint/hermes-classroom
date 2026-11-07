"""M4 visual / media gate: the committed audit must stay green and stay honest.

This reads `audit/visual/m4-visual/audit.json` — the evidence produced by
`scripts/m4v-audit.py` from the shipped Desktop module — and refuses a tree in which any framed
claim regressed. It does not re-render (the harness does that); it is the cheap guard that makes
the gate enforceable on every run of the suite.

What this does NOT prove: that the committed JSON is fresh. `audit.json` records the commit and
the plugin sha it was generated from; the freshness check below fails when the shipped module has
changed since the evidence was captured, which is the one staleness case a test can see.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit" / "visual" / "m4-visual" / "audit.json"
PLUGIN = ROOT / "desktop" / "plugin.js"
REPORT = ROOT / "docs" / "M4-VISUAL-MEDIA-AUDIT.md"

CLAIM_IDS = [f"C-{index:02d}" for index in range(1, 16)]


class VisualMediaAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not AUDIT.is_file():
            raise unittest.SkipTest("no M4 visual audit evidence committed")
        cls.evidence = json.loads(AUDIT.read_text(encoding="utf-8"))
        cls.frames = cls.evidence["frames"]

    def claim(self, claim_id: str) -> dict:
        for item in self.evidence["claims"]:
            if item["id"] == claim_id:
                return item
        self.fail(f"claim {claim_id} missing from the audit")

    def test_every_named_claim_has_a_verdict(self) -> None:
        self.assertEqual([item["id"] for item in self.evidence["claims"]], CLAIM_IDS)

    def test_every_claim_passes_on_the_committed_evidence(self) -> None:
        failing = {item["id"]: item["verdict"] for item in self.evidence["claims"] if item["verdict"] != "PASS"}
        self.assertEqual(failing, {}, f"visual/media claims not met: {failing}")

    def test_the_evidence_covers_every_required_surface_and_variant(self) -> None:
        summary = self.evidence["summary"]
        self.assertGreaterEqual(summary["frames"], 50)
        self.assertEqual(set(summary["surfaces"]), {
            "textbook", "guided", "quest", "field-desk", "procedure",
            "textbook-textonly", "textbook-unavailable",
        })
        self.assertEqual(set(summary["variants"]["modes"]), {"light", "dark"})
        self.assertEqual(set(summary["variants"]["widths"]), {460, 1280})
        self.assertEqual(set(summary["variants"]["root_font_px"]), {16, 32})
        self.assertGreaterEqual(summary["variants"]["forced_colors_frames"], 4)
        self.assertGreaterEqual(summary["variants"]["reduced_motion_frames"], 2)

    def test_no_plugin_authored_contrast_failure_in_any_frame(self) -> None:
        failing = [frame["id"] for frame in self.frames if frame["contrast_failures"]]
        self.assertEqual(failing, [])
        for frame in self.frames:
            if frame["forced_colors"] or frame["contrast_min_authored"] is None:
                continue
            self.assertGreaterEqual(
                frame["contrast_min_authored"], 4.5,
                f"{frame['id']} paints authored text below the F-01 floor",
            )

    def test_no_clipped_text_or_horizontal_overflow(self) -> None:
        self.assertEqual([frame["id"] for frame in self.frames if frame["clipped_count"]], [])
        self.assertEqual([frame["id"] for frame in self.frames if frame["horizontal_overflow"]], [])

    def test_every_control_is_named_and_no_positive_tabindex(self) -> None:
        self.assertEqual([frame["id"] for frame in self.frames if frame["ax_unnamed"]], [])
        self.assertEqual([frame["id"] for frame in self.frames if frame["keyboard_unnamed"]], [])
        self.assertEqual([frame["id"] for frame in self.frames if frame["positive_tabindex"]], [])

    def test_the_keyboard_walk_counts_controls_not_key_presses(self) -> None:
        """A keyboard count that moves without a code change is not evidence.

        The walk must visit exactly the controls the DOM declares (no duplicates from wrapping
        past the last control, no host-widget stops from the audio player's UA shadow parts),
        leave none unreachable, and paint a focus ring on each.
        """
        walked = [frame for frame in self.frames if frame.get("keyboard_count") is not None]
        self.assertTrue(walked, "no frame carries a keyboard walk")
        for frame in walked:
            self.assertEqual(frame["keyboard_declared"], frame["keyboard_count"],
                             f"{frame['id']} counted {frame['keyboard_count']} stops for "
                             f"{frame['keyboard_declared']} declared controls")
            self.assertEqual(frame["keyboard_unreachable"], [], f"{frame['id']} left controls unreachable")
            self.assertEqual(frame["keyboard_ring_missing"], 0, f"{frame['id']} moved focus with no visible ring")
            shipped = {row["tab"] for row in frame["keyboard_order"]}
            self.assertEqual(shipped, set(range(frame["keyboard_declared"])), frame["id"])

    def test_the_fixture_clock_is_pinned(self) -> None:
        """`Last touched 17 hr ago` must be a property of the fixture, not of the run."""
        reference = self.evidence.get("reference_time")
        self.assertTrue(reference, "the audit does not record the reference time it rendered against")
        self.assertEqual(reference, self.evidence["summary"]["reference_time"])
        touched = {
            row["text"]
            for frame in self.frames for row in frame.get("contrast_rows") or []
            if "Last touched" in row.get("text", "")
        }
        self.assertEqual(touched, {"Last touched 17 hr ago"},
                         "the field desk copy tracked the wall clock instead of the pinned reference time")

    def test_media_never_autoplays_and_always_has_text(self) -> None:
        for frame in self.frames:
            for audio in frame["audios"]:
                self.assertFalse(audio["autoplay_attribute"], frame["id"])
                self.assertFalse(audio["autoplay_property"], frame["id"])
                self.assertFalse(audio["playing"], frame["id"])
                self.assertTrue(audio["controls"], frame["id"])
                self.assertTrue(str(audio["aria_label"]).strip(), frame["id"])
            for image in frame["images"]:
                self.assertTrue(image["has_alt"], frame["id"])
                self.assertGreater(image["naturalWidth"], 0, f"{frame['id']} image did not decode")
            for item in frame["media_frames"]:
                self.assertTrue(item["label"], f"{frame['id']} media frame has no label")
                self.assertTrue(item["caption_is_text_equivalent"], f"{frame['id']} media has no text equivalent")

    def test_media_failure_and_text_only_paths_invent_no_player(self) -> None:
        for surface in ("textbook-unavailable", "textbook-textonly"):
            frames = [frame for frame in self.frames if frame["surface"] == surface]
            self.assertTrue(frames, f"{surface} was not captured")
            for frame in frames:
                self.assertEqual(frame["images"], [], frame["id"])
                self.assertEqual(frame["audios"], [], frame["id"])
                self.assertTrue(frame["media_fallback_text"], f"{frame['id']} lost its honest fallback text")

    def test_a_failed_audio_preview_keeps_its_authored_kind(self) -> None:
        """D-1: a refused media route must not relabel authored narration as visual."""
        unavailable = [frame for frame in self.frames if frame["surface"] == "textbook-unavailable"]
        self.assertTrue(unavailable, "the media-unavailable surface was not captured")
        audio_frames = []
        for frame in unavailable:
            for item in frame["media_frames"]:
                if not str(item.get("artifact") or "").startswith("art_audio"):
                    continue
                audio_frames.append(item)
                self.assertEqual(item["kind"], "audio", f"{frame['id']} typed narration as {item['kind']}")
                self.assertIn("Narration", item["label"], frame["id"])
                self.assertTrue(item["caption_is_text_equivalent"], f"{frame['id']} lost the transcript")
        self.assertTrue(audio_frames, "the media-unavailable surface carried no audio media frame")
        defect = next((item for item in self.evidence.get("defects", []) if item["id"] == "D-1"), None)
        self.assertIsNotNone(defect, "D-1 missing from the audit defect record")
        self.assertEqual((defect or {}).get("status"), "fixed", "D-1 re-opened in the committed evidence")

    def test_tokens_are_the_only_paint_and_match_the_contract(self) -> None:
        scan = self.evidence["source_scan"]
        self.assertEqual(scan["colour_literals_outside_token_table"], 0)
        self.assertTrue(scan["contract_matches_shipped_table"])
        self.assertEqual(scan["contract_gates"]["failures"], [])
        for frame in self.frames:
            self.assertEqual(frame["inline_colour_literals"], [], frame["id"])

    def test_evidence_is_not_stale_against_the_shipped_module(self) -> None:
        shipped = hashlib.sha256(PLUGIN.read_bytes()).hexdigest()
        self.assertEqual(
            self.evidence["summary"]["plugin_sha256"], shipped,
            "desktop/plugin.js changed since the M4 visual evidence was captured; "
            "re-run python3 scripts/m4v-audit.py",
        )

    def test_the_report_exists_and_names_every_claim(self) -> None:
        text = REPORT.read_text(encoding="utf-8")
        for claim_id in CLAIM_IDS:
            self.assertIn(claim_id, text)
        self.assertIn("Not merged, not pushed, no tag, no publish", text)


if __name__ == "__main__":
    unittest.main()
