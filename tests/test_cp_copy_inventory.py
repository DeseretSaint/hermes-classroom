"""CP-031: every source in the copy inventory resolves, and every cited enum is covered.

Closing gate for review round 1 on card ``t_a7ca4538``. The inventory under
``docs/concept-parity/copy/`` exists so a UI maker never invents a string. That only works if:

* a source cell names something the frozen contracts can actually serve, so a maker copying it
  renders real state instead of a condition that never matches;
* every ``== <value>`` claim on a contract field is a member of that field's own enum;
* every enum the inventory cites has a row for every member, so no value silently drops off the
  surface (a previewed pack, a parent-reported attempt).

The resolver is the one ``tests/test_cp_spec.py`` already uses for ``COPY.md``; this module applies
it to the CP-031 inventory and adds the enum-claim checks the deck never needed.

Grammar this test enforces for a ``GAPS.md`` proposed-row source cell (the column a deck author
copies into ``COPY.md``): one or more of

* ``deck`` — authored wording;
* ``field:<path>`` — a contract value, resolved here;
* ``computed:<rule>`` — arithmetic over contract values;
* ``pack:<path>`` — a packaged asset path;
* ``art:<path>`` — provenance, never a learning claim;
* ``host:<request>`` — a host SDK read (``pet.info``), never a contract field.

joined by `` + ``. A bare dotted read (``course.mode``) is not a source: setters and method names
are not values. That is the shape review round 1 rejected.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.test_cp_spec import resolve_field

ROOT = Path(__file__).resolve().parent.parent
COPY_DIR = ROOT / "docs" / "concept-parity" / "copy"
GAPS = COPY_DIR / "GAPS.md"
VOCAB = ROOT / "contracts" / "vocabulary.v1.json"
RPC = ROOT / "contracts" / "rpc.v24.json"

VOCAB_REF = "https://contracts.coursebook.hermes/vocabulary/v1#/"

FIELD_TOKEN = re.compile(r"field:`([^`]+)`")
# A `field:` mention only counts as a source when it has a value path. Prose such as
# "every `field:` cell" must not be mistaken for a source cell.
FIELD_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\[\]]*(?:\.[A-Za-z0-9_.\[\]]+)+$")
# `field:<path>` == `value`, or a bare `<path>` == `value`.
ENUM_CLAIM = re.compile(r"`(?:field:)?([A-Za-z0-9_.\[\]-]+)`\s*==\s*`([a-z0-9_]+)`")

SOURCE_PART = re.compile(r"^(?:deck|`(?:field|computed|pack|art|host):[^`]+`)$")

# The two enums the inventory keys a visible surface off. Every member needs a row somewhere in
# the file named here, because a value with no row is a maker inventing wording at build time.
CITED_ENUMS = {
    "attempt_summary.evidence_class": ("evidence_class", COPY_DIR / "CP-023-classroom.md"),
    "takehome.read.pack.state": ("takehome.read.pack.state", COPY_DIR / "CP-025b-studio.md"),
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def copy_docs() -> list[Path]:
    return sorted(COPY_DIR.glob("*.md"))


def _deref(node: dict, rpc: dict, vocab: dict) -> dict:
    """Follow local ``#/`` refs and absolute vocabulary refs until a real schema node."""
    hops = 0
    while isinstance(node, dict) and "$ref" in node:
        ref = str(node["$ref"])
        if ref.startswith("#/"):
            target: object = rpc
            for part in ref[2:].split("/"):
                target = target[part]  # type: ignore[index]
        elif ref.startswith(VOCAB_REF):
            target = vocab
            for part in ref.split("#/", 1)[1].split("/"):
                target = target[part]  # type: ignore[index]
        else:
            return node
        node = target  # type: ignore[assignment]
        hops += 1
        if hops > 20:
            raise KeyError("cyclic $ref")
    return node


def field_node(token: str) -> dict:
    return _deref(resolve_field(token), json.loads(read(RPC)), json.loads(read(VOCAB)))


def enum_claims(text: str) -> list[tuple[str, str]]:
    return ENUM_CLAIM.findall(text)


def proposed_rows(text: str) -> list[tuple[int, str]]:
    """(line number, source cell) for every row under a ``| proposed id |`` header."""
    rows: list[tuple[int, str]] = []
    in_table = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("| proposed id"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append((number, cells[2]))
    return rows


class TestEveryFieldSourceResolves(unittest.TestCase):
    def test_inventory_files_exist(self):
        self.assertGreaterEqual(len(copy_docs()), 6, "the CP-031 inventory is missing files")

    def test_every_field_token_resolves_against_the_frozen_contracts(self):
        failures: list[str] = []
        for path in copy_docs():
            for token in FIELD_TOKEN.findall(read(path)):
                if not FIELD_PATH.match(token):
                    continue
                # CP-005 forward fields are the deck's own allowlist; resolve_field rejects them.
                if token in {
                    "library_item.subject_label",
                    "library_item.sections_done",
                    "library_item.sections_total",
                    "library_item.is_new",
                }:
                    continue
                # A resolved method may also be named without its response path; those rows cite
                # a read, so they must name a field. Everything else is a hard failure.
                try:
                    field_node(token)
                except (KeyError, TypeError) as error:
                    failures.append(f"{path.name}: field:`{token}` -> {error}")
        self.assertEqual(failures, [], "sources no contract can serve:\n" + "\n".join(failures))

    def test_no_gap_proposal_cites_a_bare_dotted_read(self):
        bad: list[str] = []
        for number, source in proposed_rows(read(GAPS)):
            # A row may add the enum value a predicate tests, e.g. `field:x` == `cold`.
            base, _, rhs = source.partition("==")
            if rhs.strip() and not re.fullmatch(r"`[a-z0-9_]+`", rhs.strip()):
                bad.append(f"GAPS.md:{number}: {rhs.strip()!r} is not a contract enum value")
            for part in (piece.strip() for piece in base.replace(" over ", " + ").split("+")):
                if not part:
                    continue
                if not SOURCE_PART.match(part):
                    bad.append(f"GAPS.md:{number}: {part!r} is not a source form")
        self.assertEqual(
            bad,
            [],
            "a proposed row must name `field:`/`computed:`/`pack:`/`art:`/`host:` or `deck`; "
            "a method or setter name is not a value:\n" + "\n".join(bad),
        )


class TestEnumClaimsAreMembers(unittest.TestCase):
    def test_every_enum_claim_is_a_member_of_its_own_enum(self):
        vocab = json.loads(read(VOCAB))
        rpc = json.loads(read(RPC))
        failures: list[str] = []
        for path in copy_docs():
            for token, value in enum_claims(read(path)):
                try:
                    node = _deref(resolve_field(token), rpc, vocab)
                except (KeyError, TypeError) as error:
                    failures.append(f"{path.name}: `{token}` does not resolve -> {error}")
                    continue
                members = node.get("enum")
                if members is None:
                    failures.append(f"{path.name}: `{token}` has no enum, so `== {value}` claims nothing")
                    continue
                if value not in members:
                    failures.append(
                        f"{path.name}: `{token}` == `{value}` is not in {members} (contracts/rpc.v24.json)"
                    )
        self.assertEqual(failures, [], "\n".join(failures))

    def test_every_member_of_each_cited_enum_has_a_row(self):
        missing: list[str] = []
        for token, (enum_name, path) in CITED_ENUMS.items():
            declared = field_node(token).get("enum")
            self.assertTrue(declared, f"{token} declares no enum in the contract")
            members = list(declared or [])
            values = {value for claimed, value in enum_claims(read(path)) if claimed == token}
            for member in members:
                if member not in values:
                    missing.append(f"{path.name}: no row for `{token}` == `{member}` ({enum_name})")
        self.assertEqual(missing, [], "a contract value has no copy row:\n" + "\n".join(missing))

    def test_evidence_class_rows_cite_the_vocabulary(self):
        gaps = read(GAPS)
        self.assertIn("contracts/vocabulary.v1.json:20", gaps)
        self.assertNotIn("== `independent`", gaps, "`independent` is not an evidence_class value")

    def test_the_cited_enum_sources_are_the_contract_fields(self):
        vocab = json.loads(read(VOCAB))
        evidence = vocab["$defs"]["evidence_class"]["enum"]
        self.assertEqual(
            evidence,
            ["cold", "hinted", "answer_shown", "self_reported", "parent_reported", "override"],
            "the vocabulary enum changed; the inventory rows must be re-derived",
        )


class TestPartialInventoryIsLabelled(unittest.TestCase):
    """Review round 1 F2: a sample must not be presented as the complete shipped-string list."""

    def test_cp025b_declares_its_tables_a_partial_sample(self):
        text = read(COPY_DIR / "CP-025b-studio.md")
        self.assertIn("partial sample", text.lower())
        self.assertIn("GAP-30", text)
        self.assertNotIn("copy not extracted here", text)

    def test_cp025b_covers_the_regions_review_round_1_named(self):
        text = read(COPY_DIR / "CP-025b-studio.md")
        for marker in (
            "95-studio.js:70-92",
            "95-studio.js:603",
            "95-studio.js:1270-1383",
            "95-studio.js:731-940",
            "95-studio.js:6781-6818",
            "95-studio.js:2998",
            "95-studio.js:3326",
        ):
            self.assertIn(marker, text, f"CP-025b still omits the region at {marker}")
        for string in (
            "Approve these pages",
            "Export the print-ready PDF",
            "Choose this course",
            "Preview this lesson",
            "All parent courses",
            "Unsaved section changes",
            "Discard and leave",
            "Keep editing",
            "no child persona",
        ):
            self.assertIn(string, text, f"CP-025b omits the visible string {string!r}")


class TestCountsAndClarifications(unittest.TestCase):
    def test_cp025b_names_the_previewed_pack_state(self):
        self.assertIn("previewed", read(COPY_DIR / "CP-025b-studio.md").lower())

    def test_gap21_is_a_hard_code_rule_not_a_body_defect(self):
        gaps = read(GAPS)
        section = " ".join(gaps.split("### GAP-21", 1)[1].split("\n### ", 1)[0].split())
        self.assertIn("must not hard-code", section)
        self.assertNotIn("body is wrong", section)

    def test_readme_counts_match_the_deck(self):
        readme = read(COPY_DIR / "README.md")
        self.assertIn("| CP-022 | Home (R-HOME) | 25 |", readme)
        self.assertIn("| CP-023 | Classroom (R-CLASS) | 46 |", readme)


class TestRound2DocsCorrections(unittest.TestCase):
    """Review round 2: a shipped row may only claim shipped words, and a headline count must be
    derivable from the table it summarises. Both drifted on ``3000ba0``."""

    STUDIO = ROOT / "desktop" / "src" / "95-studio.js"

    def shipped_pack_state_words(self) -> list[tuple[str, str]]:
        """``(key, word)`` pairs straight out of ``CB_TAKEHOME_STATE_WORD``."""
        lines = read(self.STUDIO).splitlines()
        start = next(
            index
            for index, line in enumerate(lines)
            if line.startswith("const CB_TAKEHOME_STATE_WORD = {")
        )
        pairs: list[tuple[str, str]] = []
        for line in lines[start + 1 :]:
            if line.strip().startswith("}"):
                break
            match = re.match(r"\s*([a-z_]+):\s*'([^']+)'", line)
            if match:
                pairs.append((match.group(1), match.group(2)))
        return pairs

    def test_cp025b_shipped_pack_state_row_lists_only_shipped_words(self):
        text = read(COPY_DIR / "CP-025b-studio.md")
        rows = [line for line in text.splitlines() if "pack states shipped" in line]
        self.assertEqual(len(rows), 1, "expected exactly one shipped pack-state row")
        row = rows[0]
        self.assertIn("`95-studio.js:572-575`", row)
        cell = row.strip().strip("|").split("|")[0].strip()
        listed = [part.split(" (")[0].strip() for part in cell.split(" / ")]
        expected = self.shipped_pack_state_words()
        self.assertEqual(len(expected), 4, "CB_TAKEHOME_STATE_WORD no longer has four entries")
        self.assertEqual(listed, [word for _, word in expected])
        self.assertNotIn("Previewed", listed, "`previewed` has no shipped v2 word")
        # A contract value with no shipped word is stated as such, and its proposal row stays.
        self.assertIn("`previewed` has no v2 word", text)
        self.assertIn("| Previewed | GAP-28 `studio.pack.previewed` |", text)

    def test_readme_cp023_missing_strings_are_derivable_from_the_table(self):
        gap_rows: list[list[str]] = []
        for line in read(COPY_DIR / "CP-023-classroom.md").splitlines():
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 6:
                continue
            if "gap" in cells[5].lower():
                gap_rows.append(cells)
        gap_ids = sorted(
            {match for cells in gap_rows for match in re.findall(r"GAP-\d+", cells[2])},
            key=lambda gap: int(gap.split("-")[1]),
        )
        self.assertEqual(
            len(gap_rows), 12, "the CP-023 gap-row count changed; re-derive the README verdict"
        )
        self.assertEqual(gap_ids, [f"GAP-{number}" for number in range(11, 18)])

        row = next(
            line for line in read(COPY_DIR / "README.md").splitlines() if line.startswith("| CP-023 |")
        )
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        gaps_cell, verdict = cells[3], cells[5]
        self.assertNotRegex(
            verdict,
            r"\b\d+\s+strings?\b",
            "an un-derivable string count; derive it from the CP-023 table or drop it",
        )
        self.assertRegex(gaps_cell, rf"\b{len(gap_ids)}\b")
        span = f"`{gap_ids[0]}`–`{gap_ids[-1]}`"
        self.assertIn(span, gaps_cell)
        self.assertIn(span, verdict)


if __name__ == "__main__":
    unittest.main()
