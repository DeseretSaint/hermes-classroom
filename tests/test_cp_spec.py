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
RPC = ROOT / "contracts" / "rpc.v24.json"
PACK_MANIFEST = ROOT / "contracts" / "pack-manifest.v2.json"

V3_SCREENS = ["home.v3", "discover.v3", "classroom.v3", "course-home.v3", "lab.v3"]
V3_FRAMES = {
    "home.v3": "home.png",
    "discover.v3": "discover.png",
    "classroom.v3": "classroom.png",
    "course-home.v3": "map.png",
    "lab.v3": "system.png",
}
ROUTE_WIDTHS = ("1049", "900", "460")

# The five public-claim words the v3 copy may not contain, in any form.
BANNED_WORDS = ("stars", "star", "rating", "ratings", "reviews", "learners", "mastery")

ID_TOKEN = re.compile(
    r"`((?:home|discover|classroom|course|lab|nav)\.[a-z0-9_]+(?:\.[a-z0-9_]+)*)`"
)
SHA_ROW = re.compile(r"^- (R-[A-Z]+): ([0-9a-f]{64})$", re.MULTILINE)

# COPY.md source grammar. A `field:` source must name a real value path; a bare def or method name
# is not a value. The only names outside the frozen contracts are CP-005's forward fields.
FIELD_SOURCE = re.compile(r"field:`([^`]+)`")
FIELD_WITHOUT_PATH = re.compile(r"field:(?!`)")
PACK_SOURCE = re.compile(r"pack:`([^`]+)`")
ART_SOURCE = re.compile(r"art:`([^`]+)`")
CONTRACT_SOURCE = re.compile(r"contract:`([^`]+)`")
COMPUTED_SOURCE = re.compile(r"computed:`([^`]+)`")

CP005_FORWARD = frozenset(
    {
        "library_item.subject_label",
        "library_item.sections_done",
        "library_item.sections_total",
        "library_item.is_new",
    }
)

# The exact source cells atlas rejected in review round 1. They must never resolve again.
LEGACY_FIELD_SOURCES = (
    ("classroom.line.jp", "lesson_block"),
    ("discover.shelf.count", "count"),
    ("classroom.check.question", "lesson.page"),
    ("classroom.check.correct", "check"),
)


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
        for source in ("`library_item.next_step.label`", "`evidence_summary", "`pack.inspect", "`check.get`", "`library_item.title`"):
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


def copy_source_rows() -> list[tuple[str, str]]:
    """(id, source cell) for every COPY.md row whose first cell is a backticked id."""
    rows: list[tuple[str, str]] = []
    row = re.compile(r"^\|\s*`([a-z0-9]+\.[a-z0-9._]+)`\s*\|([^|]*)\|([^|]*)\|")
    for line in read(COPY).splitlines():
        match = row.match(line)
        if match:
            rows.append((match.group(1), match.group(3).strip()))
    return rows


def _follow(node: dict, doc: dict) -> tuple[dict, bool]:
    """Follow a local ``#/$defs/...`` ref. ``local`` is False at an external ref."""
    hops = 0
    while isinstance(node, dict) and "$ref" in node:
        ref = str(node["$ref"])
        if not ref.startswith("#/"):
            return node, False
        target: object = doc
        for part in ref[2:].split("/"):
            target = target[part]  # type: ignore[index]
        node = target  # type: ignore[assignment]
        hops += 1
        if hops > 20:
            raise KeyError("cyclic $ref")
    return node, True


def _walk(node: dict, parts: list[str], doc: dict) -> dict:
    node, local = _follow(node, doc)
    for part in parts:
        if not local:
            raise KeyError("path continues past an external $ref")
        array = part.endswith("[]")
        key = part[:-2] if array else part
        if not key:
            raise KeyError("empty path segment")
        props = node.get("properties")
        if not isinstance(props, dict) or key not in props:
            raise KeyError(f"no property {key!r}")
        node = props[key]
        node, local = _follow(node, doc)
        if array:
            if not local or "items" not in node:
                raise KeyError(f"{key!r} is not a local array")
            node = node["items"]
            # `items` is often a local ``$ref`` (e.g. ``outline_objective``); follow it so the
            # next segment can read the element's own properties. Without this an array of `$ref`
            # elements is untraversable and real fields report "no property".
            node, local = _follow(node, doc)
    return node


def resolve_field(token: str) -> dict:
    """Resolve a COPY.md ``field:`` token against the frozen contracts.

    Raises ``KeyError`` when the token names nothing a surface could render. A bare ``$defs`` name
    or a bare method name is not a value and is rejected: the token must end at a field.
    """
    rpc = json.loads(read(RPC))
    manifest = json.loads(read(PACK_MANIFEST))
    if token in CP005_FORWARD:
        raise KeyError("CP-005 forward field is allowlisted, not frozen")
    if token.startswith("pack.inspect.manifest."):
        rest = token[len("pack.inspect.manifest.") :]
        wrapper = {"properties": manifest["properties"]}
        return _walk(wrapper, [p for p in rest.split(".") if p], {"$defs": {}, "properties": manifest["properties"]})
    parts = [part for part in token.split(".") if part]
    methods = rpc["$defs"]["methods"]["properties"]
    for cut in range(len(parts) - 1, 0, -1):
        name = ".".join(parts[:cut])
        if name in methods:
            return _walk(methods[name]["response"], parts[cut:], rpc)
    if parts and parts[0] in rpc["$defs"]:
        if len(parts) < 2:
            raise KeyError(f"{token!r} names a definition, not a field")
        return _walk(rpc["$defs"][parts[0]], parts[1:], rpc)
    raise KeyError(token)


class TestCopySourcesResolve(unittest.TestCase):
    """The closing gate for review round 1: a copy source that cannot be read is a defect.

    Every ``field:`` token in COPY.md must resolve in ``contracts/rpc.v24.json`` (or, for
    ``pack.inspect.manifest.*``, in ``contracts/pack-manifest.v2.json``). Only CP-005's forward
    fields, pack content and art provenance are outside the frozen contracts, and each of those
    has its own check below.
    """

    def setUp(self):
        self.rows = copy_source_rows()
        self.copy = read(COPY)
        self.spec = read(SPEC)

    def test_every_ledger_row_has_a_source_cell(self):
        self.assertGreaterEqual(len(self.rows), 80)

    def test_no_field_source_omits_its_path(self):
        bad = [row_id for row_id, source in self.rows if FIELD_WITHOUT_PATH.search(source)]
        self.assertEqual(
            bad,
            [],
            f"these rows write `field:` without a backticked path: {bad}",
        )

    def test_every_field_source_resolves(self):
        failures: list[str] = []
        for row_id, source in self.rows:
            for token in FIELD_SOURCE.findall(source):
                if token in CP005_FORWARD:
                    continue
                try:
                    resolve_field(token)
                except (KeyError, TypeError) as error:
                    failures.append(f"{row_id}: field:`{token}` -> {error}")
        self.assertEqual(failures, [], "COPY.md sources that no contract can serve:\n" + "\n".join(failures))

    def test_every_pack_source_is_a_real_file(self):
        for row_id, source in self.rows:
            for token in PACK_SOURCE.findall(source):
                path = token.split("#", 1)[0]
                self.assertTrue(
                    (ROOT / path).is_file(),
                    f"{row_id} cites a pack file that does not exist: {path}",
                )

    def test_art_sources_are_provenance_rows_not_learning_claims(self):
        manifest = json.loads(read(PACK_MANIFEST))
        for row_id, source in self.rows:
            for token in ART_SOURCE.findall(source):
                self.assertTrue(
                    token.startswith("license.per_artifact"),
                    f"{row_id} cites art {token!r}; a credit is a licence/per-artifact row",
                )
                node = manifest["properties"]["license"]["properties"]["per_artifact"]["items"]
                self.assertIn("attribution", node["properties"], f"{row_id}: no attribution field")

    def test_token_and_computed_sources_are_declared_forward(self):
        # CP-002 owns the values; until it lands, the spec must say so and the tokens must be
        # role/size or arithmetic, never a fabricated backend field.
        self.assertIn("contracts/cb.tokens.v3.json", self.spec)
        for row_id, source in self.rows:
            for token in CONTRACT_SOURCE.findall(source):
                # CP-001r-b (t_342e4a2e) removed the dead `type.<step>` sources from COPY.md: only
                # `type.scale.<step>` and `type.line_height.<step>` exist in the v3 contract. This
                # grammar is widened to the real paths, not relaxed — the paths are resolved against
                # the contract by tests/test_tokens_v3_contract.py's COPY.md parity test.
                self.assertRegex(
                    token,
                    r"^(color\.[a-z][a-z-]*|type\.(?:scale|line_height)\.[a-z]+)$",
                    f"{row_id}: unexpected contract token {token!r}",
                )
            for token in COMPUTED_SOURCE.findall(source):
                self.assertRegex(
                    token,
                    r"^(count\(|sum\(|contrast\()",
                    f"{row_id}: computed rule {token!r} is not one of the named rules",
                )

    def test_the_resolver_rejects_the_sources_atlas_rejected(self):
        for row_id, token in LEGACY_FIELD_SOURCES:
            with self.subTest(row=row_id, token=token):
                with self.assertRaises(KeyError):
                    resolve_field(token)

    def test_the_classroom_check_rows_cover_all_three_formats(self):
        spec = self.spec.split("### 5.3 R-CLASS", 1)[1].split("\n### ", 1)[0]
        for format_name in ("`text`", "`selection`", "`verification`"):
            self.assertIn(format_name, spec, f"SPEC-V3 C7 omits the {format_name} answer surface")
        self.assertIn("classroom.check.item", spec)
        for quiet in ("classroom.check.edit", "classroom.check.clear_choice", "classroom.check.clear_ticks"):
            self.assertIn(quiet, spec, f"C7 has no quiet control row for {quiet}")


if __name__ == "__main__":
    unittest.main()
