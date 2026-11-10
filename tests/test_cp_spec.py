"""CP-001: the v3 spec, the copy deck, the matrix and the scoring instrument agree.

These tests read the documents this card ships and the pinned reference frames. They do not prove
that a screen looks like Coursebook — that is the reviewer's job, and ``docs/GM-CONCEPT-PARITY-RUBRIC.md``
§7 is the instrument. They prove the instrument is not arbitrary:

* every v3 screen in ``docs/visual-review/matrix.json`` has a named frame that exists on disk with
  the sha256 ``REFS.md`` pins, a concept region, named states, and a forced-colors cell;
* every string id in ``docs/concept-parity/COPY.md`` is used by ``SPEC-V3.md`` and every id the
  spec names has a copy row, so no screen can render an authored string or a dangling id;
* no copy string claims a public score, a crowd opinion, a headcount or a competence percentage;
* the spec carries a region map at the three required route widths, a better-than list per screen,
  the honesty table, and the Codicon-only rule;
* the rubric has a tenth dimension (Craft) and the redefined A3 anchor, and the quality bar carries
  the v3 owner amendment.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARITY = ROOT / "docs" / "concept-parity"
SPEC = PARITY / "SPEC-V3.md"
COPY = PARITY / "COPY.md"
REFS = PARITY / "refs" / "REFS.md"
RUBRIC = ROOT / "docs" / "GM-CONCEPT-PARITY-RUBRIC.md"
BAR = ROOT / "docs" / "EXPERIENCE-QUALITY-BAR.md"
MATRIX = ROOT / "docs" / "visual-review" / "matrix.json"

V3_SCREENS = ["home.v3", "discover.v3", "classroom.v3", "course-home.v3", "lab.v3"]
V3_FRAMES = {
    "home.v3": "home.png",
    "discover.v3": "discover.png",
    "classroom.v3": "classroom.png",
    "course-home.v3": "map.png",
    "lab.v3": "system.png",
}
REQUIRED_STATES = {"default", "loading", "empty", "error"}
ROUTE_WIDTHS = ("1049", "900", "460")

# The five public-claim words the v3 copy may not contain, in any form.
BANNED_WORDS = ("stars", "star", "rating", "ratings", "reviews", "learners", "mastery")

ID_TOKEN = re.compile(
    r"`((?:home|discover|classroom|course|lab|nav)\.[a-z0-9_]+(?:\.[a-z0-9_]+)*)`"
)
SHA_ROW = re.compile(r"^- (R-[A-Z]+): ([0-9a-f]{64})$", re.MULTILINE)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def pinned_hashes() -> dict[str, str]:
    text = read(REFS)
    return {ref: digest for ref, digest in SHA_ROW.findall(text)}


def matrix_screens() -> list[dict]:
    return json.loads(read(MATRIX))["screens"]


def copy_rows() -> list[tuple[str, str, str]]:
    """(id, text, cap) for every row in COPY.md whose first cell is a backticked id."""
    rows: list[tuple[str, str, str]] = []
    row = re.compile(r"^\|\s*`([a-z0-9]+\.[a-z0-9._]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|")
    for line in read(COPY).splitlines():
        match = row.match(line)
        if match:
            rows.append((match.group(1), match.group(2).strip(), match.group(4).strip()))
    return rows


class TestReferencePins(unittest.TestCase):
    def test_every_pinned_frame_exists_with_its_recorded_bytes(self):
        pins = pinned_hashes()
        self.assertGreaterEqual(len(pins), 6, "REFS.md must pin all six frames")
        for ref, digest in pins.items():
            name = {
                "R-HOME": "home.png",
                "R-BOARD": "board.png",
                "R-DISC": "discover.png",
                "R-CLASS": "classroom.png",
                "R-SYS": "system.png",
                "R-MAP": "map.png",
            }[ref]
            path = PARITY / "refs" / name
            self.assertTrue(path.is_file(), f"{ref} frame missing: {path}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, actual, f"{ref} bytes changed; the spec cites a stale frame")

    def test_spec_names_the_five_scored_frames(self):
        spec = read(SPEC)
        for ref in ("R-HOME", "R-DISC", "R-CLASS", "R-MAP", "R-SYS"):
            self.assertIn(ref, spec, f"SPEC-V3 never names {ref}")


class TestMatrixEntries(unittest.TestCase):
    def setUp(self):
        self.screens = {screen["id"]: screen for screen in matrix_screens()}

    def test_every_v3_screen_has_a_matrix_entry(self):
        for screen in V3_SCREENS:
            self.assertIn(screen, self.screens, f"matrix.json has no entry for {screen}")

    def test_each_entry_names_its_frame_region_states_and_cells(self):
        required = {
            "home.v3": ({"default", "loading", "empty", "error", "first-use", "overflow", "offline"}, 7),
            "discover.v3": ({"default", "loading", "empty", "error", "rejected"}, 6),
            "classroom.v3": ({"default", "loading", "error", "correct", "wrong", "no-chat"}, 8),
            "course-home.v3": ({"default", "loading", "error", "plan-in-review", "course-end"}, 8),
            "lab.v3": ({"default", "loading", "error", "forced-colors", "reduced-motion", "text-200"}, 6),
        }
        for screen_id in V3_SCREENS:
            screen = self.screens[screen_id]
            self.assertTrue(screen.get("card"), f"{screen_id} names no card")
            frame = screen.get("concept_frame") or ""
            self.assertTrue(frame.endswith(V3_FRAMES[screen_id]), f"{screen_id} frame {frame!r}")
            self.assertTrue((ROOT / frame).is_file(), f"{screen_id} frame does not exist: {frame}")
            self.assertTrue(screen.get("concept_region"), f"{screen_id} names no concept region")
            states = screen.get("states") or []
            wanted, floor = required[screen_id]
            self.assertTrue(wanted <= set(states), f"{screen_id} states missing {wanted - set(states)}")
            self.assertGreaterEqual(len(states), floor, f"{screen_id} names too few states to score")
            self.assertEqual(len(states), len(set(states)), f"{screen_id} repeats a state")
            cells = screen.get("cells") or []
            self.assertIn(
                "forced-colors@1049/light/100",
                cells,
                f"{screen_id} has no forced-colors cell",
            )
            for width in ROUTE_WIDTHS:
                self.assertTrue(
                    any(f"@{width}/" in cell for cell in cells),
                    f"{screen_id} has no cell at route width {width}",
                )
            for state in states:
                if state == "default":
                    continue
                self.assertTrue(
                    any(cell.startswith(f"{state}@") for cell in cells),
                    f"{screen_id} names state {state} with no capture cell",
                )

    def test_v2_matrix_cells_are_untouched(self):
        data = json.loads(read(MATRIX))
        self.assertEqual(data["version"], 1)
        self.assertGreaterEqual(len(data["required_cells"]), 8)
        self.assertNotIn("forced-colors@1049/light/100", data["required_cells"])

    def test_entries_are_additive(self):
        ids = [screen["id"] for screen in matrix_screens()]
        self.assertEqual(len(ids), len(set(ids)), "matrix.json repeats a screen id")
        for legacy in ("home.global", "home.course", "course.world", "tutor.rail"):
            self.assertIn(legacy, ids, "a v2 screen entry was removed or renamed")


class TestCopyDeck(unittest.TestCase):
    def setUp(self):
        self.rows = copy_rows()
        self.spec = read(SPEC)
        self.copy = read(COPY)

    def test_the_deck_has_rows(self):
        self.assertGreaterEqual(len(self.rows), 80, "COPY.md is missing most of the screens")

    def test_no_duplicate_ids(self):
        ids = [row[0] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)), "COPY.md repeats an id")

    def test_every_copy_id_is_used_by_the_spec(self):
        missing = [row[0] for row in self.rows if row[0] not in self.spec]
        self.assertEqual(missing, [], f"ids nothing builds: {missing}")

    def test_every_id_the_spec_names_has_a_row(self):
        known = {row[0] for row in self.rows}
        named = {match.group(1) for match in ID_TOKEN.finditer(self.spec)}
        dangling = sorted(named - known)
        self.assertEqual(dangling, [], f"SPEC-V3 names ids with no copy row: {dangling}")

    def test_every_row_has_text_and_a_cap(self):
        for string_id, text, cap in self.rows:
            self.assertTrue(text, f"{string_id} has no text")
            self.assertTrue(text.startswith("`") is False, string_id)
            self.assertRegex(cap, r"^\d+$", f"{string_id} has no integer char cap")
            literal = re.sub(r"\{[^}]*\}", "", text)
            self.assertLessEqual(
                len(literal),
                int(cap),
                f"{string_id} exceeds its own cap before any value is filled",
            )

    def test_copy_claims_no_public_score_or_crowd_opinion(self):
        lowered = self.copy.lower()
        found = [word for word in BANNED_WORDS if re.search(rf"\b{word}\b", lowered)]
        self.assertEqual(found, [], f"COPY.md contains banned claim words: {found}")

    def test_no_internal_code_value_is_shown_as_copy(self):
        for string_id, text, _cap in self.rows:
            self.assertNotRegex(
                text,
                r"\b(resolve_review_due|resume_lesson|start_lesson|needs_review|review_due|"
                r"single_home_host|binding|projection)\b",
                f"{string_id} shows an internal value",
            )


class TestSpecCompleteness(unittest.TestCase):
    def setUp(self):
        self.spec = read(SPEC)

    def test_region_maps_cover_all_three_route_widths(self):
        for width in ROUTE_WIDTHS:
            count = len(re.findall(rf"\b{width}\b", self.spec))
            self.assertGreaterEqual(count, 5, f"the spec barely mentions route width {width}")
        self.assertIn("route width", self.spec.lower())
        self.assertIn("useCbViewportWidth", self.spec)

    def test_each_screen_has_a_region_map_states_and_a_better_than_list(self):
        sections = re.split(r"\n### 5\.\d ", self.spec)
        by_ref = {}
        for section in sections[1:]:
            for ref in ("R-HOME", "R-DISC", "R-CLASS", "R-MAP", "R-SYS"):
                if section.lstrip().startswith(ref):
                    by_ref[ref] = section
        for ref in ("R-HOME", "R-DISC", "R-CLASS", "R-MAP", "R-SYS"):
            body = by_ref.get(ref)
            if body is None:
                self.fail(f"{ref} section is missing")
            self.assertIn("Region map", body, f"{ref} has no region map")
            self.assertIn("| State |", body, f"{ref} has no state table")
            self.assertIn("Better than the concept", body, f"{ref} has no better-than list")
            self.assertIn("**One primary:**", body, f"{ref} names no primary")
            for width in ROUTE_WIDTHS:
                self.assertIn(width, body, f"{ref} region map skips route width {width}")

    def test_discover_beats_the_concept_on_the_five_named_points(self):
        body = self.spec.split("### 5.2 R-DISC", 1)[1].split("\n### ", 1)[0]
        for phrase in (
            "Grid aligned to the banner edges",
            "No dead zone right of the grid",
            "Labelled rail",
            "Fox inside the safe area",
            "One metadata pattern",
        ):
            self.assertIn(phrase, body, f"R-DISC is missing its own improvement: {phrase}")

    def test_icons_are_codicon_only(self):
        self.assertIn("`sdk.Codicon` only", self.spec)
        for glyph in ("home", "library", "compass", "person", "settings-gear", "arrow-left"):
            self.assertIn(f"`{glyph}`", self.spec, f"no Codicon named for {glyph}")

    def test_the_spec_carries_no_colour_value(self):
        self.assertIsNone(
            re.search(r"#[0-9a-fA-F]{6}\b", self.spec),
            "SPEC-V3 carries a colour literal; values belong to the v3 contract",
        )

    def test_honesty_table_covers_every_flagged_element(self):
        table = self.spec.split("## 6. Honesty table", 1)[1].split("## 7.", 1)[0]
        rows = [line for line in table.splitlines() if line.startswith("|") and "---" not in line]
        self.assertGreaterEqual(len(rows) - 2, 24, "the honesty table lost rows")
        for concept in ("Star row", "`NEW`", "240 XP", "proofs collected", "leaderboard", "Padlock"):
            self.assertIn(concept, table, f"honesty table does not cover {concept}")
        for source in ("`next_step.label`", "`evidence_summary", "`pack.inspect", "`lesson_block`"):
            self.assertIn(source, table, f"honesty table never names the source {source}")

    def test_the_fox_has_a_safe_area_rule_and_a_pose_per_screen(self):
        for pose in ("wave", "point", "clock", "read", "cheer", "think", "sleep"):
            self.assertIn(f"`{pose}`", self.spec, f"pose {pose} is never placed")
        self.assertIn("safe area", self.spec.lower())
        self.assertIn("aria-hidden", self.spec)

    def test_navigation_is_one_system(self):
        self.assertIn("D3", self.spec)
        self.assertIn("top tab strip", self.spec)
        self.assertIn("No fifth destination is created", self.spec)


class TestScoringInstrument(unittest.TestCase):
    def setUp(self):
        self.rubric = read(RUBRIC)
        self.bar = read(BAR)

    def test_rubric_has_a_v3_section_with_a_tenth_dimension(self):
        v3 = self.rubric.split("## 7.", 1)[-1] if "## 7." in self.rubric else ""
        self.assertIn("v3", v3)
        self.assertIn("Craft", v3, "the tenth dimension is missing")
        for dimension in (
            "Focal hierarchy",
            "Composition",
            "Type",
            "Palette",
            "Illustration",
            "Card / game system",
            "State coverage",
            "Responsiveness",
            "Truth",
            "Craft",
        ):
            self.assertIn(dimension, v3, f"v3 dimension missing: {dimension}")

    def test_anchor_a3_is_redefined_for_material_world(self):
        flattened = " ".join(self.rubric.split())
        self.assertIn(
            "a lit paper world with physical objects and contact shadows", flattened
        )

    def test_pass_rule_is_unchanged(self):
        v3 = self.rubric.split("### 7.3 Pass rule", 1)[-1]
        self.assertIn("Every dimension ≥ 4 and all five anchors present", v3)
        self.assertIn("A single 3 is a `request-changes`", self.rubric)

    def test_quality_bar_carries_the_v3_owner_amendment(self):
        amendment = self.bar.split("concept v3", 1)[-1] if "concept v3" in self.bar else ""
        self.assertTrue(amendment, "EXPERIENCE-QUALITY-BAR.md has no v3 amendment")
        for lifted in ("elevation", "wood", "Fraunces", "pill", "radius"):
            self.assertIn(lifted, amendment, f"amendment does not lift {lifted}")
        for kept in ("glass", "gradient", "fake data", "one primary", "Codicon"):
            self.assertIn(kept, amendment, f"amendment does not keep {kept}")
        self.assertNotIn("status: frozen", amendment.lower())


if __name__ == "__main__":
    unittest.main()
