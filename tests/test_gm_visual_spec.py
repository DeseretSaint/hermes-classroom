"""GM-013: the visual spec, the subject boards, the rubric and the matrix agree with the shipped contract.

These tests read the *documents and plates this card ships* and compare them with ground truth that
already exists in the repository: ``contracts/cb.tokens.v2.json`` and ``contracts/cb.tokens.v1.json``.
They do not prove that a screen looks like Coursebook — that is the reviewer's job and
``docs/GM-CONCEPT-PARITY-RUBRIC.md`` is the instrument. They prove the instrument is not arbitrary:
every colour is a shipped token, every plate is textless, every screen has a frame and a state list,
and no document invented a seventh type step.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "GM-VISUAL-SPEC.md"
WORLDS = ROOT / "docs" / "GM-SUBJECT-WORLDS.md"
RUBRIC = ROOT / "docs" / "GM-CONCEPT-PARITY-RUBRIC.md"
PRINT_SPEC = ROOT / "docs" / "GM-PRINT-SPEC.md"
PLATES = ROOT / "docs" / "GM-ART-PLATES.md"
MATRIX_JSON = ROOT / "docs" / "visual-review" / "matrix.json"
MATRIX_MD = ROOT / "docs" / "visual-review" / "MATRIX.md"
MANIFEST = ROOT / "docs" / "gm-visual" / "manifest.json"
TOKENS = ROOT / "contracts" / "cb.tokens.v2.json"
BOARDS = ROOT / "docs" / "gm-visual" / "boards"

COLOUR_ATTR = re.compile(r'(?:fill|stroke)="(#[0-9a-fA-F]{6})"')

# The four worlds this card must specify, with the motifs each section must actually name.
WORLD_MOTIFS = {
    "japanese": ["lantern", "counter", "noren", "steam"],
    "head-gasket": ["lift", "tool wall", "gasket ring", "manual"],
    "astronomy": ["dome", "telescope", "chart", "horizon"],
    "sourdough": ["banneton", "dough", "scraper", "linen"],
}

PLATE_FILES = [
    "japanese-lantern-district.svg",
    "head-gasket-service-bay.svg",
    "astronomy-observatory.svg",
    "sourdough-kitchen-table.svg",
    "anti-generic-swap.svg",
]


def load_tokens() -> dict:
    return json.loads(TOKENS.read_text(encoding="utf-8"))


class TestTokenBinding(unittest.TestCase):
    def test_spec_names_every_shipped_token(self):
        spec = SPEC.read_text(encoding="utf-8")
        for name in load_tokens()["tokens"]:
            self.assertIn(f"`{name}`", spec, f"token {name} is not named in the visual spec")

    def test_spec_adds_no_colour_literal(self):
        spec = SPEC.read_text(encoding="utf-8")
        found = set(COLOUR_ATTR.findall(spec)) | set(
            re.findall(r"#[0-9a-fA-F]{6}\b", spec)
        )
        self.assertEqual(found, set(), f"the spec quotes raw hex: {sorted(found)}")

    def test_plates_use_shipped_tokens_only(self):
        data = load_tokens()
        allowed = {v.lower() for mode in data["modes"].values() for v in mode.values()}
        for name in PLATE_FILES:
            svg = (BOARDS / name).read_text(encoding="utf-8")
            used = {c.lower() for c in COLOUR_ATTR.findall(svg)}
            self.assertTrue(used, f"{name} declares no colour")
            self.assertTrue(
                used <= allowed, f"{name} uses colours outside the contract: {sorted(used - allowed)}"
            )

    def test_plates_never_use_state_hues(self):
        data = load_tokens()
        forbidden = {data["modes"]["light"][h].lower() for h in ("ochre", "coral", "plum")}
        for name in PLATE_FILES:
            if name == "anti-generic-swap.svg":
                continue  # a review instrument, not a plate
            svg = (BOARDS / name).read_text(encoding="utf-8")
            used = {c.lower() for c in COLOUR_ATTR.findall(svg)}
            self.assertFalse(used & forbidden, f"{name} uses a state hue: {sorted(used & forbidden)}")

    def test_type_scale_is_the_shipped_six(self):
        spec = SPEC.read_text(encoding="utf-8")
        contract = load_tokens()
        for step in contract["type_scale"]:
            self.assertIn(f"`{step}`", spec, f"type step {step} missing from the spec")
        self.assertEqual(len(contract["type_scale"]), 6)
        self.assertIn("no seventh", spec.lower())


class TestPlatesAreTextless(unittest.TestCase):
    def test_every_plate_has_no_text_or_image_reference(self):
        for name in PLATE_FILES:
            svg = (BOARDS / name).read_text(encoding="utf-8")
            if name == "anti-generic-swap.svg":
                # the only artifact allowed labels, and it is not a plate
                self.assertIn("<text", svg)
                continue
            self.assertNotIn("<text", svg, f"{name} contains text")
            self.assertNotIn("<tspan", svg, f"{name} contains text")
            self.assertNotIn("<image", svg, f"{name} embeds a raster")
            self.assertNotIn("<use", svg, f"{name} references external art")
            self.assertNotIn("filter", svg, f"{name} uses a filter")
            self.assertNotIn("Gradient", svg, f"{name} uses a gradient")

    def test_manifest_matches_the_bytes(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["boards"]), set(PLATE_FILES))
        for name, row in manifest["boards"].items():
            payload = (BOARDS / name).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), row["sha256"], name)
            self.assertEqual(len(payload), row["bytes"], name)
            self.assertIsNone(row["model"], f"{name} claims a model call it did not make")
            self.assertEqual(row["licence"], "CC0-1.0")
            self.assertIn(row["role"], {"orientation", "review-instrument"})


class TestSubjectWorlds(unittest.TestCase):
    def test_four_worlds_specify_two_motifs_and_a_swap_check(self):
        text = WORLDS.read_text(encoding="utf-8")
        sections = re.split(r"\n## ", text)
        by_name = {}
        for chunk in sections:
            for key in WORLD_MOTIFS:
                if f"boards/{key}" in chunk:
                    by_name[key] = chunk
        self.assertEqual(set(by_name), set(WORLD_MOTIFS), "a world section is missing or unnamed")
        for key, motifs in WORLD_MOTIFS.items():
            chunk = by_name[key].lower()
            present = [m for m in motifs if m in chunk]
            self.assertGreaterEqual(len(present), 2, f"{key} names fewer than two motifs: {present}")
            self.assertIn("anti-generic swap check", chunk, f"{key} has no swap check")
            self.assertIn("must never become", chunk, f"{key} does not say what a motif must not become")

    def test_no_world_borrows_a_state_hue(self):
        text = WORLDS.read_text(encoding="utf-8").lower()
        for hue in ("`ochre`", "`coral`", "`plum`"):
            self.assertIn(hue, text)  # named as forbidden
        self.assertIn("state hues never", text)


class TestRubric(unittest.TestCase):
    def test_nine_dimensions_and_the_threshold(self):
        text = RUBRIC.read_text(encoding="utf-8")
        for name in (
            "Focal hierarchy",
            "Composition",
            "Type",
            "Palette and texture",
            "Illustration",
            "Card / game system",
            "State coverage",
            "Responsiveness",
            "Truth",
        ):
            self.assertIn(name, text, f"rubric dimension {name} missing")
        self.assertIn("Composition anchor check", text)
        for anchor in ("A1", "A2", "A3", "A4", "A5"):
            self.assertIn(anchor, text)

    def test_every_matrix_screen_has_a_comparison_frame(self):
        matrix = json.loads(MATRIX_JSON.read_text(encoding="utf-8"))
        rubric = RUBRIC.read_text(encoding="utf-8")
        for screen in matrix["screens"]:
            sid = screen["id"]
            stem = ".".join(sid.split(".")[:2])
            self.assertTrue(
                sid in rubric or stem in rubric,
                f"screen {sid} has no comparison frame in the rubric",
            )


class TestMatrix(unittest.TestCase):
    def test_screens_have_frames_and_states(self):
        matrix = json.loads(MATRIX_JSON.read_text(encoding="utf-8"))
        self.assertEqual(len(matrix["required_cells"]), 8)
        self.assertEqual(len(matrix["screens"]), 16)
        cards = set()
        seen = set()
        for screen in matrix["screens"]:
            sid = screen["id"]
            self.assertNotIn(sid, seen, f"duplicate screen {sid}")
            seen.add(sid)
            self.assertTrue(screen["concept_frame"], f"{sid} has no concept frame")
            self.assertTrue(screen["concept_region"], f"{sid} has no concept region")
            self.assertTrue(screen["states"], f"{sid} has no state list")
            self.assertEqual(len(screen["states"]), len(set(screen["states"])), f"{sid} duplicates a state")
            cards.add(screen["card"])
        for card in ("GM-002", "GM-004", "GM-006", "GM-008", "GM-010", "GM-012", "GM-014"):
            self.assertIn(card, cards, f"{card} has no screen in the matrix")

    def test_matrix_markdown_lists_every_screen(self):
        matrix = json.loads(MATRIX_JSON.read_text(encoding="utf-8"))
        md = MATRIX_MD.read_text(encoding="utf-8")
        for screen in matrix["screens"]:
            self.assertIn(f"`{screen['id']}`", md, f"{screen['id']} missing from MATRIX.md")

    def test_visual_review_template_is_complete(self):
        for name in ("README.md", "MATRIX.md", "SCORECARD-TEMPLATE.md", "matrix.json"):
            self.assertTrue((ROOT / "docs" / "visual-review" / name).is_file(), name)
        readme = (ROOT / "docs" / "visual-review" / "README.md").read_text(encoding="utf-8")
        for rule in ("running app", "1049", "900", "460", "200", "reduced motion", "concept frame"):
            self.assertIn(rule, readme.lower(), f"README does not state {rule}")


class TestPrintAndArtDocs(unittest.TestCase):
    def test_print_spec_has_five_roles_and_the_answer_key_rule(self):
        text = PRINT_SPEC.read_text(encoding="utf-8")
        for role in ("Parent guide", "Learner page", "Answer guide", "Sources and provenance", "Visual caption"):
            self.assertIn(role, text, f"print role {role} missing")
        self.assertIn("18 mm", text)
        self.assertIn("0.70 in", text)
        self.assertIn("No answer key on a learner page", text)
        self.assertIn("low-ink", text.lower())
        self.assertIn("proof path", text.lower())

    def test_art_plate_doc_lists_every_plate_and_provenance_field(self):
        text = PLATES.read_text(encoding="utf-8")
        for name in PLATE_FILES:
            self.assertIn(name, text, f"{name} is not listed")
        for field in (
            "`plate_id`",
            "`role`",
            "`provider`",
            "`model`",
            "`prompt_hash`",
            "`style_hash`",
            "`licence`",
            "`text_check`",
            "`alt_text`",
            "`text_equivalent`",
        ):
            self.assertIn(field, text, f"provenance field {field} missing")
        self.assertIn("orientation only", text)
        self.assertIn("never in a procedure", text)


if __name__ == "__main__":
    unittest.main()
