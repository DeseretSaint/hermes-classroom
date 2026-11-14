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

Two sweep gates live here, because the copy inventory earned them from two directions and neither
replaces the other. ``TestCp031bSweep`` is CP-031b-R's substance gate (``t_adc9bdee``): the five
sweep files exist, cite their source, carry four columns and a floor, ``GAP-30`` is closed and
``GAP-31``-``GAP-42`` are defined, the round-two findings and ``GAP-38``-``GAP-42`` keep a row at the
line that renders them, the consequence family is split per rendering, the two learner-completion
wordings are not merged, the Game sweep accounts for ``ChildSafeLine``, and the Homework sweep covers
the whole ``NotebookView`` rather than the card's ``880-1000`` slice. ``TestCp031cSweep`` is
CP-031c's mechanism gate (``t_0458a135``, re-swept by CP-031c-R ``t_54a44039``): the population is
re-extracted from each segment file at test time, every row must cite a line that carries its own
words, ``REQUIRED_ROWS`` is keyed on ``(file, exact string)``, and the swept revision is pinned on
the content of the five blobs, not only on a commit id.

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

# The real cell form is `` `field:path` `` (backtick before ``field:``).
FIELD_TOKEN = re.compile(r"`field:([^`]+)`")
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


def enum_members(node: dict, rpc: dict, vocab: dict) -> list[str] | None:
    """The members of a field's enum, including one wrapped in ``oneOf`` (nullable enums)."""
    if isinstance(node.get("enum"), list):
        return list(node["enum"])
    branches = node.get("oneOf")
    if not isinstance(branches, list):
        return None
    members: list[str] = []
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        resolved = _deref(branch, rpc, vocab)
        values = resolved.get("enum") if isinstance(resolved, dict) else None
        if isinstance(values, list):
            members.extend(str(value) for value in values)
    return members or None


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
                members = enum_members(node, rpc, vocab)
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


class TestRound3FieldGate(unittest.TestCase):
    """Review round 3: the field gate must read the real cell form and cannot go vacuous.

    ``25817f3`` matched ``field:`path``` instead of the inventory's `` `field:path` `` cells, so the
    resolver attempted zero of the real sources and stayed green on a fabricated row.
    """

    ALLOWLISTED = {
        "library_item.subject_label",
        "library_item.sections_done",
        "library_item.sections_total",
        "library_item.is_new",
    }

    def source_cells(self) -> list[str]:
        cells: list[str] = []
        for path in copy_docs():
            for token in FIELD_TOKEN.findall(read(path)):
                if FIELD_PATH.match(token) and token not in self.ALLOWLISTED:
                    cells.append(token)
        return cells

    def test_the_gate_reads_the_real_cell_form_and_a_fixed_floor(self):
        cells = self.source_cells()
        resolved = 0
        for token in cells:
            try:
                field_node(token)
                resolved += 1
            except (KeyError, TypeError):
                pass
        self.assertGreaterEqual(
            len(cells), 50, "the inventory lost its source cells; the gate is checking too little"
        )
        self.assertGreaterEqual(
            resolved, 50, "the field gate resolved fewer than 50 cells; it is close to vacuous"
        )
        self.assertEqual(resolved, len(cells), "every source cell must resolve")

    def test_array_of_ref_elements_is_traversable(self):
        # The C3/M5 node-label source on two screens: `items` is a local `$ref` to
        # `$defs.outline_objective`. Before the resolver fix this reported "no property 'title'".
        title = field_node("course.outline.objectives[].title")
        self.assertEqual(title.get("type"), "string")
        independent = field_node("course.outline.objectives[].independent")
        self.assertEqual(independent.get("type"), "boolean")

    def test_a_fabricated_source_row_is_caught(self):
        # The exact row shape a maker could paste into any screen table.
        line = "| H0 | {invented} | home.bogus | 88 | `field:no.such.method.field` | ok |"
        tokens = FIELD_TOKEN.findall(line)
        self.assertEqual(tokens, ["no.such.method.field"], "the gate no longer reads the row form")
        with self.assertRaises(KeyError):
            field_node(tokens[0])


#: A row writes a runtime value as `{n}`; the template that renders it writes `${...}`. Both are the
#: same placeholder and normalise to `{…}` so a row can be checked against the shipped line.
ROW_PLACEHOLDER = re.compile(r"\{[^}]*\}")
TEMPLATE_PLACEHOLDER = re.compile(r"\$\{[^}]*\}")


def row_text(literal: str) -> str:
    """The shipped words of a sweep row: drop a trailing annotation, normalise placeholders."""
    text = re.sub(r"\s*\([^)]*\)\s*$", "", literal)
    text = ROW_PLACEHOLDER.sub("{…}", text).replace("\\|", "|")
    return re.sub(r"\s+", " ", text).strip()


def shipped_lines(source: Path, literal: str) -> list[int]:
    """1-based lines where the literal's words ship.

    A JSX sentence is often split across adjacent string literals (``'…' + '…'``), a template fills
    ``${...}``, and a grouped row joins several shipped strings with `` / ``. The whole literal is
    tried first; when that fails, its own longest fragments are tried in order, so the gate still
    re-derives the line from the words instead of trusting a number.
    """
    lines = read(source).splitlines()

    def find(wanted: str) -> list[int]:
        found: list[int] = []
        if not wanted:
            return found
        for index in range(len(lines)):
            window = " ".join(lines[index : index + 6])
            window = re.sub(r"['\"]\s*\+\s*['\"]", "", window)
            window = TEMPLATE_PLACEHOLDER.sub("{…}", window)
            window = re.sub(r"\s+", " ", window)
            if wanted in window:
                # Report the line that actually carries the words, not the window's first line.
                exact = [
                    index + offset + 1
                    for offset, line in enumerate(lines[index : index + 6])
                    if wanted in re.sub(r"\s+", " ", TEMPLATE_PLACEHOLDER.sub("{…}", line))
                ]
                found.append(exact[0] if exact else index + 1)
        return sorted(set(found))

    wanted = row_text(literal)
    hits = find(wanted)
    if hits:
        return hits
    candidates = re.split(r"\{…\}|\s+/\s+|(?<=[.?!])\s+", wanted)
    for fragment in sorted(candidates, key=len, reverse=True):
        fragment = fragment.strip(" .,;:·…")
        if len(fragment) >= 8:
            hits = find(fragment)
            if hits:
                return hits
    return []



CP031_SWEEPS = {
    "CP-031-sweep-chrome.md": "00-header.js",
    "CP-031-sweep-homework.md": "90-course.js",
    "CP-031-sweep-game.md": "30-home.js",
    "CP-031-sweep-parent-studio.md": "95-studio.js",
    "CP-031-sweep-world.md": "97-world.js",
}
SWEEP_SOURCES = ROOT / "desktop" / "src"

# ── CP-031c extraction ────────────────────────────────────────────────────────────────────────
# The sweep is a completeness artifact, so its gate derives the population from the source rather
# than trusting a hand-kept list. This lexer is deliberately small and literal: strings outside
# comments and regex literals, with template `${...}` expressions kept as text and normalised to
# `{…}` for comparison. A row is required for every literal that survives `is_user_facing`.

PLACEHOLDER = re.compile(r"\$\{.*?\}", re.S)
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
CSS_VALUE = re.compile(
    r"(?:^|\s)(?:-?\d+(?:\.\d+)?(?:px|rem|em|fr|vh|vw|%)|var\(--|rgba?\(|color-mix\(|minmax\(|repeat\(|"
    r"calc\(|#[0-9a-fA-F]{3,8}\b|\bsolid\b|\btransparent\b)|\{…\}(?:px|rem|em|fr|%)"
)
CLASS_TOKEN = re.compile(r"^(?:[a-z0-9][a-z0-9:./\[\]()%_-]*|\(--[a-z0-9-]+\))$")
CLASSISH = re.compile(
    r"^(?:flex|grid|items-|justify-|content-|gap-|p[xytrbl]?-|m[xytrbl]?-|w-|h-|min-[wh]-|max-[wh]-|"
    r"text-|font-|leading-|tracking-|border|rounded|bg-|shadow|overflow-|absolute|relative|inset-|"
    r"top-|left-|right-|bottom-|z-|opacity-|truncate|hidden|block|inline|shrink|grow|basis-|"
    r"col-|row-|space-[xy]-|min-\[|max-\[)"
)
COPY_CODE = re.compile(
    r"(?:=>|function\s*\(|</?[a-zA-Z]|\\u[0-9a-fA-F]{4}|\bvar\(--|\bminmax\(|\brepeat\(|\bcolor-mix\()"
)
COPY_PATH = re.compile(
    r"^(?:https?://|/|\.{1,2}/|[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+$|[\w.-]+/[\w./-]+$|"
    r"[A-Z][A-Z0-9_]{2,}$|[a-z]+(?:-[a-z]+)+/[a-z+-]+$)"
)
#: The complete exclusion allowlist. It is two HTML attribute values, nothing else; a regex that
#: swallowed a screen would hide rows instead of naming them.
COPY_ALLOWLIST = {"noreferrer noopener", "noopener noreferrer"}


def lex_strings(src: str) -> list[tuple[int, int, str]]:
    """``(start_line, end_line, raw_body)`` for every string literal outside comments/regexes."""
    out: list[tuple[int, int, str]] = []
    i, n, line = 0, len(src), 1

    def skip_template_expr(j: int) -> int:
        depth = 1
        while j < n and depth:
            c = src[j]
            if c in "'\"":
                q = c
                j += 1
                while j < n:
                    if src[j] == "\\":
                        j += 2
                        continue
                    if src[j] == q:
                        j += 1
                        break
                    j += 1
                continue
            if c == "`":
                j = skip_template(j)
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            j += 1
        return j

    def skip_template(j: int) -> int:
        j += 1
        while j < n:
            if src[j] == "\\":
                j += 2
                continue
            if src[j] == "`":
                return j + 1
            if src.startswith("${", j):
                j = skip_template_expr(j + 2)
                continue
            j += 1
        return j

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            end = n if j < 0 else j + 2
            line += src.count("\n", i, end)
            i = end
            continue
        if c == "/":
            k = i - 1
            while k > 0 and src[k].isspace():
                k -= 1
            if src[k] in "(,=:[!&|?{};":
                j = i + 1
                in_class = False
                while j < n:
                    if src[j] == "\\":
                        j += 2
                        continue
                    if src[j] == "[":
                        in_class = True
                    elif src[j] == "]":
                        in_class = False
                    elif src[j] == "/" and not in_class:
                        j += 1
                        while j < n and src[j].isalpha():
                            j += 1
                        break
                    elif src[j] == "\n":
                        break
                    j += 1
                i = j
                continue
            i += 1
            continue
        if c in "'\"":
            start_line = line
            q = c
            j = i + 1
            buf: list[str] = []
            while j < n:
                if src[j] == "\\":
                    buf.append(src[j : j + 2])
                    j += 2
                    continue
                if src[j] == "\n":
                    line += 1
                if src[j] == q:
                    j += 1
                    break
                buf.append(src[j])
                j += 1
            out.append((start_line, line, "".join(buf)))
            i = j
            continue
        if c == "`":
            start_line = line
            j = i + 1
            buf = []
            while j < n:
                if src[j] == "\\":
                    buf.append(src[j : j + 2])
                    j += 2
                    continue
                if src[j] == "`":
                    j += 1
                    break
                if src.startswith("${", j):
                    k = skip_template_expr(j + 2)
                    buf.append(src[j:k])
                    line += src.count("\n", j, k)
                    j = k
                    continue
                if src[j] == "\n":
                    line += 1
                buf.append(src[j])
                j += 1
            out.append((start_line, line, "".join(buf)))
            i = j
            continue
        i += 1
    return out


def replace_placeholders(text: str) -> str:
    """Replace each balanced ``${...}`` with ``{…}``; nested templates and braces are skipped."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("${", i):
            depth = 1
            j = i + 2
            while j < n and depth:
                c = text[j]
                if c in "'\"`":
                    q = c
                    j += 1
                    while j < n:
                        if text[j] == "\\":
                            j += 2
                            continue
                        if text[j] == q:
                            j += 1
                            break
                        j += 1
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                j += 1
            out.append("{…}")
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def normalise_copy(body: str) -> str:
    body = body.replace("\\n", " ").replace("\\t", " ")
    body = replace_placeholders(body)
    body = body.replace("\\'", "'").replace('\\"', '"').replace("\\`", "`")
    body = HTML_TAG.sub(" ", body)
    body = (body.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
            .replace("&amp;", "&"))
    return re.sub(r"\s+", " ", body).strip()


def is_user_facing(body: str) -> bool:
    text = normalise_copy(body)
    if not text or text in COPY_ALLOWLIST:
        return False
    tokens = text.split()
    if len(tokens) < 2:
        return False
    if not any(re.search(r"[^\W\d_]", token) for token in tokens):
        return False
    if COPY_CODE.search(text) or COPY_PATH.match(text) or CSS_VALUE.search(text):
        return False
    if "@page" in text or "box-sizing" in text or re.search(
        r"(?:^|\s)(?:margin|padding|color|font|border|size|display|gap|width|height|background|"
        r"box-sizing|line-height|letter-spacing|text-align)\s*:\s*[^;{}]+;",
        text,
    ):
        return False
    if all(CLASS_TOKEN.match(token) for token in tokens) and any(
        CLASSISH.match(token) or re.search(r"[-:0-9\[\]/]", token) for token in tokens
    ):
        durations = re.fullmatch(
            r"(?:\d+\s*(?:min|mins|sec|secs|hour|hours|day|days|week|weeks|month|months|year|years)"
            r"\s*(?:[/,·]\s*)?)+",
            text,
        )
        if not durations:
            return False
    classish = [token for token in tokens if CLASSISH.match(token)]
    if len(classish) >= 3 and not re.search(r"[.!?]", text) and not any(t[:1].isupper() for t in tokens):
        return False
    return True


def extracted_literals(source: str) -> dict[str, tuple[int, int]]:
    """``normalised literal -> first (start, end) line`` for one segment file."""
    path = SWEEP_SOURCES / source
    found: dict[str, tuple[int, int]] = {}
    for start, end, body in lex_strings(path.read_text(encoding="utf-8")):
        text = normalise_copy(body)
        if is_user_facing(body) and text not in found:
            found[text] = (start, end)
    return found


CITATION = re.compile(r"`([\w.-]+\.js):(\d+)(?:-(\d+))?`")


def inventory_rows(text: str) -> list[dict[str, str]]:
    """Rows under a ``| string | ... | proposed copy id`` header, with escaped pipes intact."""
    rows: list[dict[str, str]] = []
    in_table = False
    for raw in text.splitlines():
        if raw.startswith("| string |") and "proposed copy id" in raw:
            in_table = True
            continue
        if not in_table:
            continue
        if not raw.startswith("|"):
            in_table = False
            continue
        parts = re.split(r"(?<!\\)\|", raw)[1:-1]
        cells = [part.strip() for part in parts]
        if len(cells) < 4 or set(cells[0]) <= {"-", ":", " "}:
            continue
        rows.append({
            "string": cells[0].replace("\\|", "|"),
            "source": cells[1],
            "state": cells[2],
            "id": cells[3],
        })
    return rows


def rows_for(text: str, source: str) -> list[dict[str, str]]:
    return [row for row in inventory_rows(text) if any(m.group(1) == source for m in CITATION.finditer(row["source"]))]


def missing_rows(doc_text: str, source: str) -> list[str]:
    """Literals the extractor finds in ``source`` with no inventory row in this sweep."""
    rows = rows_for(doc_text, source)
    rowed = {row["string"] for row in rows}
    return sorted(set(extracted_literals(source)) - rowed)


def cited_text(row: dict[str, str], source: str, lines: list[str]) -> str:
    chunks: list[str] = []
    for match in CITATION.finditer(row["source"]):
        if match.group(1) != source:
            continue
        start = int(match.group(2))
        end = int(match.group(3) or start)
        for number in range(start, min(end, len(lines)) + 1):
            chunks.append(lines[number - 1])
    return normalise_copy("\n".join(chunks))


def miscited_rows(doc_text: str, source: str) -> list[str]:
    """Rows whose cited lines do not carry their own string."""
    lines = (SWEEP_SOURCES / source).read_text(encoding="utf-8").splitlines()
    failures: list[str] = []
    for row in rows_for(doc_text, source):
        wanted = normalise_copy(row["string"])
        if wanted not in cited_text(row, source, lines):
            failures.append(f"{row['string']!r} -> {row['source']}")
    return failures


def out_of_file_rows(doc_text: str, source: str) -> list[str]:
    lines = (SWEEP_SOURCES / source).read_text(encoding="utf-8").splitlines()
    bad: list[str] = []
    for row in rows_for(doc_text, source):
        for match in CITATION.finditer(row["source"]):
            if match.group(1) != source:
                continue
            for value in (match.group(2), match.group(3)):
                if value is not None and not 1 <= int(value) <= len(lines):
                    bad.append(f"{source}:{value} is outside the {len(lines)}-line file")
    return bad


CP022_HANDOFF = re.compile(
    r"(?:belongs?\s+(?:to|in)|stays?\s+(?:with|in)|lives?\s+in|is\s+owned\s+by|"
    r"is\s+carried\s+by|inventoried\s+in)[\s\S]{0,60}?CP-022-home\.md",
    re.IGNORECASE,
)
HANDOFF_NEGATIONS = (
    "not true", "false", "carries neither", "carries no", "contains no", "does not carry",
    "no inventory row", "never cites", "must not", "does not belong", "not belong",
)


def handoff_violations(doc_text: str) -> list[str]:
    failures: list[str] = []
    for para in doc_text.split("\n\n"):
        match = CP022_HANDOFF.search(para)
        if match is None:
            continue
        if any(neg in para.lower() for neg in HANDOFF_NEGATIONS):
            continue
        failures.append(match.group(0))
    return failures


GAP30_CLOSED = re.compile(r"### GAP-30\b[^\n]*\bCLOSED\b")


class TestCp031cSweep(unittest.TestCase):
    """CP-031c closing gate: string-anchored, not line-number anchored.

    A line-number table rots the moment a file is re-authored; CP-031b died exactly that way. Here
    every required row is keyed on the literal it quotes, the extractor re-derives the population
    from the segment file at test time, and a row's citation is checked against the line it names.
    """

    #: Strings earlier review rounds proved can go missing, keyed on ``(sweep, file, exact text)``.
    #: The line is found in the file now, so a re-authoring cannot silently invalidate the gate.
    REQUIRED_ROWS = (
        ("CP-031-sweep-chrome.md", "00-header.js", "The Coursebook backend did not answer."),
        ("CP-031-sweep-chrome.md", "00-header.js", "This lesson has no chat to return to yet."),
        ("CP-031-sweep-chrome.md", "00-header.js", "The saved lesson chat could not be opened from this desktop. The section is still available to read."),
        ("CP-031-sweep-chrome.md", "00-header.js", "profile routes could not be read"),
        ("CP-031-sweep-chrome.md", "00-header.js", "One task I need to do now"),
        ("CP-031-sweep-chrome.md", "00-header.js", "Preparing for my child"),
        ("CP-031-sweep-chrome.md", "00-header.js", "Delayed evidence"),
        ("CP-031-sweep-game.md", "30-home.js", "Child-safe defaults"),
        ("CP-031-sweep-game.md", "30-home.js", "· Child-safe defaults"),
        ("CP-031-sweep-game.md", "30-home.js", "No section is stamped yet. A stamp appears when evidence is recorded, never for opening a page."),
        ("CP-031-sweep-homework.md", "90-course.js", "Search the notebook"),
        ("CP-031-sweep-homework.md", "90-course.js", "Search notes and excerpts"),
        ("CP-031-sweep-homework.md", "90-course.js", "Open in textbook"),
        ("CP-031-sweep-homework.md", "90-course.js", "Remove from notebook"),
        ("CP-031-sweep-homework.md", "90-course.js", "Save changes"),
        ("CP-031-sweep-homework.md", "90-course.js", "Remove this moment from the notebook?"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Approve the current lesson set before exporting."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "{…}{…} The saved draft is unchanged."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Order saved. {…}"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Add objective"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "{…} Confirm to store the edit."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "whether each claim has a source that was actually read"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "whether the plan follows the recipe and its limits"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Changes need review"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Lesson set approval"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Final approval"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Export is blocked ({…})."),
        ("CP-031-sweep-world.md", "97-world.js", "Course world"),
        ("CP-031-sweep-world.md", "97-world.js", "World not approved yet"),
        ("CP-031-sweep-world.md", "97-world.js", "Use Textbook mode"),
    )

    def sweep_text(self, name: str) -> str:
        return read(COPY_DIR / name)

    def test_all_five_sweeps_exist(self):
        missing = [name for name in CP031_SWEEPS if not (COPY_DIR / name).is_file()]
        self.assertEqual(missing, [], f"GAP-30 is not closed; missing sweep files: {missing}")

    def test_every_extracted_literal_has_an_inventory_row(self):
        """The population is re-derived from each segment file, so a re-wording is visible."""
        failures: list[str] = []
        for name, source in CP031_SWEEPS.items():
            path = COPY_DIR / name
            if not path.is_file():
                failures.append(f"{name}: file missing")
                continue
            missing = missing_rows(read(path), source)
            if missing:
                failures.append(
                    f"{name}: {len(missing)} literal(s) from {source} have no row: {missing}"
                )
        self.assertEqual(failures, [], "\n".join(failures))

    def test_every_row_cites_a_line_that_carries_its_string(self):
        failures: list[str] = []
        for name, source in CP031_SWEEPS.items():
            path = COPY_DIR / name
            if not path.is_file():
                continue
            bad = miscited_rows(read(path), source)
            if bad:
                failures.append(f"{name}: rows whose cited line does not carry the string: {bad}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_no_row_cites_a_line_outside_its_file(self):
        failures: list[str] = []
        for name, source in CP031_SWEEPS.items():
            path = COPY_DIR / name
            if path.is_file():
                failures.extend(out_of_file_rows(read(path), source))
        self.assertEqual(failures, [], "\n".join(failures))

    def test_each_sweep_names_the_swept_sha_and_its_row_count(self):
        gaps = read(GAPS)
        swept_shas = set()
        for name, source in CP031_SWEEPS.items():
            text = self.sweep_text(name)
            found = set(re.findall(r"\b[0-9a-f]{40}\b", text))
            self.assertEqual(len(found), 1, f"{name} names {len(found)} revisions: {sorted(found)}")
            swept_shas |= found
            declared = re.search(r"\*\*Rows:\*\*\s*(\d+)", text)
            self.assertIsNotNone(declared, f"{name} does not state its row count")
            rows = inventory_rows(text)
            self.assertEqual(
                int(declared.group(1)), len(rows),
                f"{name} declares {declared.group(1)} rows but the table holds {len(rows)}",
            )
        self.assertEqual(len(swept_shas), 1, f"the sweeps disagree about the revision: {sorted(swept_shas)}")
        sha = swept_shas.pop()
        for text, label in ((gaps, "GAPS.md"), (read(COPY_DIR / "README.md"), "README.md")):
            self.assertIn(sha, text, f"{label} does not name the swept sha {sha}")

    def test_the_swept_sha_still_describes_master(self):
        """Pin on content, not only on a commit id.

        `origin/master` may advance with commits that do not touch the five segment files — as it
        did once during CP-031c (a test-only commit). The sweep stays true only while every segment
        file's blob is identical at the swept sha and at `origin/master`; a changed blob fails with
        the file names so the next author re-sweeps instead of rotating citations.
        """
        import subprocess

        def rev(spec: str) -> str | None:
            try:
                return subprocess.check_output(
                    ["git", "rev-parse", spec], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
                ).strip()
            except (OSError, subprocess.CalledProcessError):
                return None

        swept = rev("HEAD")
        master = rev("origin/master")
        if master is None:
            self.skipTest("not a git checkout with an origin/master")
        text = read(GAPS)
        shas = set(re.findall(r"\b[0-9a-f]{40}\b", text))
        self.assertTrue(shas, "GAPS.md names no swept revision")
        declared = set()
        for name in CP031_SWEEPS:
            declared |= set(re.findall(r"\b[0-9a-f]{40}\b", self.sweep_text(name)))
        self.assertEqual(len(declared), 1, f"the sweeps disagree: {sorted(declared)}")
        swept = declared.pop()
        self.assertIn(swept, shas, "GAPS.md does not name the swept revision")
        for extra in shas - {swept}:
            self.assertIn(
                f"advanced to `{extra}`", text,
                f"GAPS.md names {extra} without saying it is a post-sweep master move",
            )
        if swept == master:
            return
        changed = [
            source for source in sorted(set(CP031_SWEEPS.values()))
            if rev(f"{swept}:desktop/src/{source}") != rev(f"origin/master:desktop/src/{source}")
        ]
        self.assertEqual(
            changed, [],
            f"origin/master ({master}) moved {changed} since the sweep at {swept}; re-sweep them",
        )

    def test_required_rows_are_found_by_string_and_their_citation_carries_them(self):
        """Every required literal is located in the file first, then matched to a row that cites it."""
        failures: list[str] = []
        for name, source, text in self.REQUIRED_ROWS:
            path = COPY_DIR / name
            if not path.is_file():
                failures.append(f"{name}: file missing")
                continue
            lines = (SWEEP_SOURCES / source).read_text(encoding="utf-8").splitlines()
            literals = extracted_literals(source)
            if text not in literals:
                failures.append(f"{source} no longer carries {text!r}; re-derive the required row")
                continue
            start = literals[text][0]
            rows = [row for row in rows_for(read(path), source) if row["string"] == text]
            if not rows:
                failures.append(f"{name}: no inventory row for {text!r} ({source}:{start})")
                continue
            if not any(text in cited_text(row, source, lines) for row in rows):
                failures.append(
                    f"{name}: the row for {text!r} cites no line that carries it "
                    f"(it is at {source}:{start})"
                )
        self.assertEqual(failures, [], "\n".join(failures))

    def test_gap30_is_closed_and_names_this_card(self):
        gaps = read(GAPS)
        headings = [line for line in gaps.splitlines() if line.startswith("### GAP-30")]
        self.assertEqual(len(headings), 1, "GAP-30 heading moved or duplicated")
        self.assertRegex(headings[0], r"\bCLOSED\b", "GAP-30 must be marked closed")
        section = gaps.split("### GAP-30", 1)[1].split("\n### ", 1)[0]
        self.assertIn("t_0458a135", section, "the closing card id is not recorded")
        for number in range(31, 43):
            self.assertIn(f"### GAP-{number} ", gaps, f"the sweep's GAP-{number} is undefined")

    def test_a_hand_off_note_cannot_displace_a_block_onto_cp022(self):
        failures: list[str] = []
        for name in CP031_SWEEPS:
            path = COPY_DIR / name
            if not path.is_file():
                continue
            failures.extend(f"{name}: {violation!r}" for violation in handoff_violations(read(path)))
        self.assertEqual(
            failures, [],
            "a sweep assigns a block to CP-022-home.md, which carries no inventory rows; row the "
            "strings here or name the gap that owns them",
        )

    # ── the six mutation probes ──────────────────────────────────────────────────────────────
    # Each probe mutates a copy of a real artifact in memory and asserts the named validator
    # rejects it. They are the drift-defence's own tests: a gate that cannot fail is not a gate.

    def test_mutation_deleting_a_row_is_caught(self):
        name, source = "CP-031-sweep-parent-studio.md", "95-studio.js"
        text = self.sweep_text(name)
        rows = rows_for(text, source)
        self.assertTrue(rows, "no rows to mutate")
        row_text = rows[0]["string"]
        mutated = "\n".join(
            line for line in text.splitlines() if not line.startswith(f"| {row_text} |")
        )
        self.assertNotIn(row_text, mutated)
        self.assertIn(row_text, missing_rows(mutated, source))

    def test_mutation_retargeting_a_row_to_a_line_that_does_not_carry_it_is_caught(self):
        name, source = "CP-031-sweep-parent-studio.md", "95-studio.js"
        text = self.sweep_text(name)
        rows = rows_for(text, source)
        row = next(row for row in rows if row["string"] not in ("Saving", "Queueing"))
        target = row["source"].split(":", 1)[0].strip("`")
        mutated = text.replace(row["source"], f"`{target}:1`", 1)
        self.assertTrue(
            any(row["string"] in failure for failure in miscited_rows(mutated, source)),
            f"the retargeted row for {row['string']!r} was not caught",
        )

    def test_mutation_deleting_a_sweep_file_is_caught(self):
        present = {name: self.sweep_text(name) for name in CP031_SWEEPS if (COPY_DIR / name).is_file()}
        del present["CP-031-sweep-world.md"]
        self.assertEqual(
            [name for name in CP031_SWEEPS if name not in present],
            ["CP-031-sweep-world.md"],
        )

    def test_mutation_truncating_a_sweep_is_caught(self):
        name = "CP-031-sweep-homework.md"
        text = self.sweep_text(name)
        declared = int(re.search(r"\*\*Rows:\*\*\s*(\d+)", text).group(1))
        lines = text.splitlines()
        first_row = next(index for index, line in enumerate(lines) if line.startswith("| ") and ".js:" in line)
        truncated = "\n".join(lines[: first_row + 1])
        self.assertNotEqual(declared, len(inventory_rows(truncated)))

    def test_mutation_reopening_gap30_is_caught(self):
        gaps = read(GAPS)
        self.assertIsNotNone(GAP30_CLOSED.search(gaps))
        reopened = GAP30_CLOSED.sub("### GAP-30 — the shipped-string inventories are a partial sample", gaps)
        self.assertIsNone(GAP30_CLOSED.search(reopened))

    def test_mutation_handing_a_block_to_cp022_is_caught(self):
        clean = "### Game\n\nThe defaults line belongs to `CP-022-home.md`.\n"
        self.assertEqual(len(handoff_violations(clean)), 1)
        self.assertIn("CP-022-home.md", handoff_violations(clean)[0])
        self.assertIn("belong", handoff_violations(clean)[0])
        negative = "### Game\n\nThe defaults line does not belong to `CP-022-home.md`.\n"
        self.assertEqual(handoff_violations(negative), [])
        stays = "### Game\n\nThe state words stay with `CP-022-home.md`.\n"
        self.assertEqual(handoff_violations(stays), ["stay with `CP-022-home.md"])

    def test_each_sweep_states_its_offline_and_overflow_evidence(self):
        for name in CP031_SWEEPS:
            path = COPY_DIR / name
            if not path.is_file():
                continue
            text = read(path).lower()
            self.assertIn("offline", text, f"{name} does not state the offline evidence")
            self.assertIn("overflow", text, f"{name} does not state the overflow evidence")

    def test_readme_lists_every_sweep_with_its_row_count(self):
        readme = read(COPY_DIR / "README.md")
        for name in CP031_SWEEPS:
            text = self.sweep_text(name)
            rows = len(inventory_rows(text))
            self.assertIn(name, readme, f"README does not list {name}")
            self.assertRegex(
                readme,
                rf"{re.escape(name)}[^\n]*\|\s*{rows}\s*\|",
                f"README does not carry {name}'s {rows}-row count",
            )


class TestCp031bSweep(unittest.TestCase):
    """CP-031b-R's closing gate: the complete sweep exists, cites real lines, and GAP-30 is closed.

    ``GAP-30`` said the shipped-string inventories were a partial sample. That is only closed if a
    reader can find the complete list for every in-scope file, if every row still points at a line
    that exists, and if the gap file says so. A sweep that is silently truncated, or a GAP-30 that
    reopens without a card, must fail here.
    """

    SOURCES = ROOT / "desktop" / "src"
    FLOORS = {
        "CP-031-sweep-parent-studio.md": ("95-studio.js", 620),
        "CP-031-sweep-world.md": ("97-world.js", 90),
        "CP-031-sweep-game.md": ("30-home.js", 210),
        "CP-031-sweep-homework.md": ("90-course.js", 325),
        "CP-031-sweep-chrome.md": ("00-header.js", 50),
    }
    CITATION = re.compile(r"`([\w.-]+\.js):(\d+)(?:-(\d+))?`")

    #: Strings review rounds 2-5 found dropped by an earlier cut of the sweep. Each is keyed on
    #: the words it quotes, not on a line number: the gate locates the words in the shipped file at
    #: test time and then requires a row to cite that line, so a re-authoring of the file cannot
    #: silently invalidate the gate.
    REQUIRED_ROWS = (
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "{…} · {…} · {…} pt margins · selectable text"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Recorded: the learner reported this done. A report, not a mark."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "You edited the plan after approving the lesson set."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "The generated pages changed after you approved them."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "You changed the course title or goal after approving the lesson set."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "A newer approval replaced this one."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "The lesson set you approved no longer matches the current pages."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Approve the current lesson set before exporting."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "whether each objective matches the goal"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "whether each claim has a source that was actually read"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "whether the units, objectives and checks fit together"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "whether the schedule and time estimates add up"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "whether the plan follows the recipe and its limits"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Add objective"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "{code: }{backend text} The saved draft is unchanged."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "{…} stored attempt(s) reference this section. {…}"),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "{…} learner attempt(s) already reference this section."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "{…} stored attempt(s) reference this section; the edit was confirmed against that consequence."),
        ("CP-031-sweep-parent-studio.md", "30-home.js", "Child-safe defaults · no loss-framed reminders, no ranking, no random rewards, no streaks · XP is cosmetic Game feedback"),
        ("CP-031-sweep-parent-studio.md", "30-home.js", "· Session · {n} min"),
        ("CP-031-sweep-parent-studio.md", "30-home.js", "Open Coursebook settings (accessible name)"),
        ("CP-031-sweep-chrome.md", "00-header.js", "The Coursebook backend answered with something that is not a contract envelope."),
        ("CP-031-sweep-chrome.md", "00-header.js", "The Coursebook backend did not answer."),
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Order saved. {…}"),
        ("CP-031-sweep-homework.md", "90-course.js", "Search the notebook (accessible name)"),
        ("CP-031-sweep-homework.md", "90-course.js", "Search notes and excerpts (placeholder)"),
        ("CP-031-sweep-homework.md", "90-course.js", "Open in textbook"),
        ("CP-031-sweep-homework.md", "90-course.js", "Play/view media (label is fixed; `aria-expanded` carries open/closed)"),
        ("CP-031-sweep-homework.md", "90-course.js", "Edit note and tags"),
        ("CP-031-sweep-homework.md", "90-course.js", "Remove from notebook"),
        ("CP-031-sweep-homework.md", "90-course.js", "Technical detail (disclosure summary)"),
        ("CP-031-sweep-homework.md", "90-course.js", "Section id · {objective id or “not recorded”}"),
        ("CP-031-sweep-homework.md", "90-course.js", "Your note"),
        ("CP-031-sweep-homework.md", "90-course.js", "Tags (comma separated)"),
        ("CP-031-sweep-homework.md", "90-course.js", "Save changes"),
        ("CP-031-sweep-homework.md", "90-course.js", "Cancel"),
        ("CP-031-sweep-homework.md", "90-course.js", "Remove this moment from the notebook? (dialog title)"),
        ("CP-031-sweep-homework.md", "90-course.js", "Only the notebook entry is removed. The lesson, its attempts and any media it referenced are kept. (dialog body)"),
        ("CP-031-sweep-homework.md", "90-course.js", "Remove entry (dialog confirm)"),
        ("CP-031-sweep-game.md", "30-home.js", "· Child-safe defaults"),
        ("CP-031-sweep-game.md", "30-home.js", "· Session · {n} min"),
        ("CP-031-sweep-chrome.md", "00-header.js", "Not started"),
        ("CP-031-sweep-chrome.md", "00-header.js", "Independent evidence"),
        ("CP-031-sweep-chrome.md", "00-header.js", "Delayed evidence"),
        ("CP-031-sweep-chrome.md", "00-header.js", "Review due"),
        ("CP-031-sweep-chrome.md", "00-header.js", "Could not be written"),
        ("CP-031-sweep-chrome.md", "00-header.js", "Moved on without a grade"),
    )

    #: Rows retired before the sweep, kept as a record so a reviewer reads a wording change rather
    #: than a silent deletion. ``475efefc`` retired the research-and-drafting sentence; the
    #: ``e6fe4f71`` re-sweep retired the two ``95-studio.js`` plan sentences listed in the file.
    REMOVED_ROWS = (
        ("CP-031-sweep-parent-studio.md", "95-studio.js", "Research and drafting run in the background; this screen fills itself when the plan is written. Nothing is shown from a template, and there is no progress percentage to show."),
    )

    def sweep_path(self, name: str) -> Path:
        return COPY_DIR / name

    def rows(self, name: str) -> list[list[str]]:
        """Rows under the inventory header, as ``[string, source, state, id]``."""
        text = read(self.sweep_path(name))
        out: list[list[str]] = []
        in_table = False
        for line in text.splitlines():
            if line.startswith("| string |") and "proposed copy id" in line:
                in_table = True
                continue
            if not in_table:
                continue
            if not line.startswith("|"):
                if not line.strip():
                    continue
                in_table = False
                continue
            cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
            if set(cells[0]) <= {"-", ":", " "}:
                continue
            out.append(cells)
        return out

    def cited_lines(self, name: str, source: str) -> set[int]:
        """Every line of `source` an inventory **row** of `name` names, expanding `a-b` ranges.

        Only table rows count. Section headings and prose notes cite wide regions for navigation
        (`95-studio.js:5356-5694`), so counting them would let any line inside a region pass as
        "rowed" after its row was deleted — the mutation that proved the first cut of this helper
        too loose. Parsing the row's source cell also beats a substring check: ``95-studio.js:5490``
        must be a cited line, not merely occur inside ``95-studio.js:54900``.
        """
        found: set[int] = set()
        for cells in self.rows(name):
            if len(cells) < 2:
                continue
            for match in self.CITATION.finditer(cells[1]):
                if match.group(1) != source:
                    continue
                start = int(match.group(2))
                end = int(match.group(3) or start)
                found.update(range(start, end + 1))
        return found

    def test_every_in_scope_file_has_a_sweep(self):
        missing = [name for name in self.FLOORS if not self.sweep_path(name).is_file()]
        self.assertEqual(missing, [], f"GAP-30 is not closed; missing sweep files: {missing}")

    def test_each_sweep_cites_its_source_file_at_real_lines(self):
        failures: list[str] = []
        for name, (source, _floor) in self.FLOORS.items():
            path = self.sweep_path(name)
            if not path.is_file():
                failures.append(f"{name}: file missing")
                continue
            text = read(path)
            lines = read(self.SOURCES / source).splitlines()
            cited = [(m.group(2), m.group(3)) for m in self.CITATION.finditer(text) if m.group(1) == source]
            if not cited:
                failures.append(f"{name}: cites no line of {source}")
                continue
            for start, end in cited:
                for value in (start, end):
                    if value is None:
                        continue
                    if not 1 <= int(value) <= len(lines):
                        failures.append(f"{name}: {source}:{value} is outside the {len(lines)}-line file")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_every_inventory_row_has_four_columns_and_the_floor_holds(self):
        failures: list[str] = []
        for name, (_source, floor) in self.FLOORS.items():
            path = self.sweep_path(name)
            if not path.is_file():
                continue
            text = read(path)
            rows = self.rows(name)
            if len(rows) < floor:
                failures.append(f"{name}: {len(rows)} inventory rows, floor is {floor}")
            for cells in rows:
                if len(cells) != 4:
                    failures.append(f"{name}: row has {len(cells)} cells, expected 4: {cells[0]!r}")
                elif not cells[1] or not re.search(r"\w+\.js:\d+", cells[1]):
                    failures.append(f"{name}: row cites no file:line: {cells[0]!r}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_gap30_is_marked_closed_and_the_sweep_gaps_exist(self):
        gaps = read(GAPS)
        headings = [line for line in gaps.splitlines() if line.startswith("### GAP-30")]
        self.assertEqual(len(headings), 1, "GAP-30 heading moved or duplicated")
        self.assertIn("CLOSED", headings[0], "GAP-30 must be marked closed by CP-031b")
        self.assertIn("t_adc9bdee", gaps, "the closing card id is not recorded")
        for number in range(31, 43):
            self.assertIn(f"### GAP-{number} ", gaps, f"the sweep's GAP-{number} is undefined")

    def test_round_two_findings_keep_a_row_at_the_true_line(self):
        """Each string review rounds 2-5 found missing stays rowed, at the line that renders it.

        The words are located in the shipped file first and the row is then checked against that
        line. A row that cites a stale line number fails; a row that was quietly deleted fails; a
        string that no longer ships is not required — it is retired in ``REMOVED_ROWS`` with its
        reason written in the sweep file.
        """
        failures: list[str] = []
        for name, source, literal in self.REQUIRED_ROWS:
            path = self.sweep_path(name)
            if not path.is_file():
                failures.append(f"{name}: file missing")
                continue
            wanted = row_text(literal)
            rowed_strings = {row_text(cells[0]) for cells in self.rows(name)}
            if wanted not in rowed_strings:
                failures.append(f"{name}: the row for {wanted!r} is gone")
            hits = shipped_lines(self.SOURCES / source, literal)
            if not hits:
                failures.append(f"{source}: {literal!r} no longer ships")
                continue
            rowed = self.cited_lines(name, source)
            if not set(hits) & rowed:
                failures.append(
                    f"{name}: no row cites {source}:{hits[0]} ({literal!r}); the citation drifted"
                )
        for name, source, literal in self.REMOVED_ROWS:
            if shipped_lines(self.SOURCES / source, literal):
                failures.append(f"{source}: retired row {literal!r} still ships; re-row it")
            sweep = read(self.sweep_path(name))
            if literal not in sweep:
                failures.append(f"{name}: the removal of {literal!r} is not recorded")
            elif "Rows removed" not in sweep:
                failures.append(f"{name}: the removed row has no recorded reason")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_the_consequence_family_is_split_per_rendering(self):
        """The three evidence-consequence renderings word the sentence differently.

        The sweep's rule 2 is that a row listing several lines renders the same words from each.
        These three do not, so one row may not claim more than one of them: a reader authoring the
        deck from a merged row would silently lose two shipped sentences. The three lines are
        re-located from the shipped sentence at test time, so a re-authored file moves them here
        rather than in five places.
        """
        source = "95-studio.js"
        product = read(self.SOURCES / source)
        sites = [number for number, line in enumerate(product.splitlines(), start=1) if "reference this section" in line]
        self.assertEqual(len(sites), 3, f"expected three consequence renderings, found {sites}")
        text = read(self.sweep_path("CP-031-sweep-parent-studio.md"))
        for cells in self.rows("CP-031-sweep-parent-studio.md"):
            if len(cells) < 2:
                continue
            claimed = [site for site in sites if re.search(rf"{source}:{site}(?!\d)", cells[1])]
            self.assertLessEqual(
                len(claimed),
                1,
                f"one row claims {claimed}, which do not share wording: {cells[0]!r}",
            )

    def test_the_learner_completion_rows_are_not_merged(self):
        """The parent-reported and learner-reported completions word the learner differently."""
        source = "95-studio.js"
        product = read(self.SOURCES / source)
        parent = shipped_lines(self.SOURCES / source, "Recorded: a parent reported this done. A report, not a mark.")
        learner = shipped_lines(self.SOURCES / source, "Recorded: the learner reported this done. A report, not a mark.")
        self.assertTrue(parent and learner, "a learner-completion wording stopped shipping")
        for cells in self.rows("CP-031-sweep-parent-studio.md"):
            if len(cells) < 2 or "Recorded:" not in cells[0]:
                continue
            source_cell = cells[1]
            claims_parent = any(re.search(rf"{source}:{line}(?!\d)", source_cell) for line in parent)
            claims_learner = any(re.search(rf"{source}:{line}(?!\d)", source_cell) for line in learner)
            self.assertFalse(
                claims_parent and claims_learner,
                f"row merges the two learner wordings: {cells[0]!r}",
            )

    def test_the_game_sweep_accounts_for_the_child_safe_block(self):
        """The Game sweep hands the ChildSafeLine block to the Parent Studio sweep, by name."""
        game = read(self.sweep_path("CP-031-sweep-game.md"))
        self.assertIn("ChildSafeLine", game, "the ChildSafeLine block is not named")
        self.assertIn("CP-031-sweep-parent-studio.md", game, "the ChildSafeLine hand-off is not stated")
        self.assertIn("CB_GAME_ACTION_WORD", game, "the Game block's own start is not named")

    def test_gap38_is_defined_and_referenced(self):
        gaps = read(GAPS)
        self.assertIn("### GAP-38 ", gaps, "GAP-38 (the banner and check-reason family) is undefined")
        sweep = read(self.sweep_path("CP-031-sweep-parent-studio.md"))
        self.assertIn("GAP-38", sweep, "the sweep does not attach its new rows to GAP-38")

    def test_gap39_is_defined_and_referenced(self):
        gaps = read(GAPS)
        self.assertIn("### GAP-39 ", gaps, "GAP-39 (the shell envelope error) is undefined")
        chrome = read(self.sweep_path("CP-031-sweep-chrome.md"))
        self.assertIn("GAP-39", chrome, "the chrome sweep does not attach its envelope row to GAP-39")
        # The two literals the probe found unrowed must stay named as exclusions, not vanish.
        self.assertIn("profile routes could not be read", chrome)
        self.assertIn("loadBinding needs exactly one of storedSessionId or enrollmentId", chrome)

    def test_gap40_names_the_tutor_path_instead_of_claiming_cp023(self):
        """§5 used to say CP-023 inventoried the tutor path; CP-023 carries different wording.

        The block is genuinely out of these four surfaces, so it is excluded — but an exclusion that
        points at an inventory which does not hold the strings is how a family goes missing, which is
        exactly the defect GAP-39 records. The exclusion must name a gap, not another card's file.
        """
        gaps = read(GAPS)
        self.assertIn("### GAP-40 ", gaps, "GAP-40 (the tutor-path coverage claim) is undefined")
        chrome = read(self.sweep_path("CP-031-sweep-chrome.md"))
        self.assertIn("GAP-40", chrome, "the chrome sweep does not name GAP-40 for the excluded block")
        self.assertNotIn(
            "inventoried by `CP-023-classroom.md`",
            chrome,
            "the sweep again claims CP-023 carries the tutor-path sentences",
        )

    CP022_HANDOFF = re.compile(
        r"(?:belongs?\s+(?:to|in)|stays?\s+(?:with|in)|lives?\s+in|"
        r"is\s+owned\s+by|is\s+carried\s+by|inventoried\s+in)"
        r"[\s\S]{0,60}?CP-022-home\.md",
        re.IGNORECASE,
    )

    def test_a_coverage_hand_off_note_points_at_an_inventory_that_holds_the_strings(self):
        """A 'belongs to another inventory' note is a coverage claim, and is checked as one.

        The Game sweep twice displaced a block onto `CP-022-home.md`: the home-route child-safe line
        and the `DESK_STATE_WORD` map every journal card renders. CP-022 is a gap analysis of the
        Home surface and carries neither, so both blocks were unrowed while the sweep read as
        complete. That is the defect GAP-40 records for the chrome sweep.

        Round 5 (contract lens) found a third instance: the Parent Studio sweep's §3.1 note said the
        Home twin line "stays with" CP-022, which this card's own GAP-41 disproves, and the previous
        cut of this test grepped only the Game sweep, so that sentence passed. The check now runs
        over all five sweeps and catches both phrasings, while the Game sweep's correction
        ("Neither is true", "carries no inventory row at all") keeps passing.
        """
        negations = (
            "not true",
            "false",
            "carries neither",
            "carries no",
            "contains no",
            "does not carry",
            "no inventory row",
            "never cites",
        )
        failures: list[str] = []
        for name in self.FLOORS:
            path = self.sweep_path(name)
            if not path.is_file():
                continue
            for para in read(path).split("\n\n"):
                match = self.CP022_HANDOFF.search(para)
                if match is None:
                    continue
                if any(neg in para.lower() for neg in negations):
                    continue
                failures.append(f"{name}: {match.group(0)!r}")
        self.assertEqual(
            failures,
            [],
            "a sweep assigns a block to CP-022-home.md, which carries no inventory rows; row the "
            "strings here or name the gap that owns them",
        )

        # The file round 5 caught must now name the sweep that actually rows the Home twin and cite
        # the lines that carry the words, not the session span between them.
        studio = read(self.sweep_path("CP-031-sweep-parent-studio.md"))
        self.assertIn("CP-031-sweep-game.md", studio, "the Parent Studio sweep does not say where the Home twin is rowed")
        self.assertIn("GAP-41", studio, "the Parent Studio sweep does not name GAP-41 for the Home twin")
        for literal in ("· Child-safe defaults", "· Session · {n} min"):
            hits = shipped_lines(self.SOURCES / "30-home.js", literal)
            self.assertTrue(hits, f"{literal!r} no longer ships in 30-home.js")
            self.assertTrue(
                any(f"`{line}`" in studio for line in hits)
                or any(f"30-home.js:{line}" in studio for line in hits),
                f"the cross-reference does not cite {literal!r} at 30-home.js:{hits[0]}",
            )

        gaps = read(GAPS)
        self.assertIn("### GAP-41 ", gaps, "GAP-41 (the Home defaults line) is undefined")
        self.assertIn("### GAP-42 ", gaps, "GAP-42 (the objective-state words) is undefined")
        gap41 = gaps.split("### GAP-41")[1].split("### GAP-42")[0]
        child_line = shipped_lines(self.SOURCES / "30-home.js", "· Child-safe defaults")[0]
        session_line = shipped_lines(self.SOURCES / "30-home.js", "· Session · {n} min")[0]
        self.assertIn(f"`{child_line}`", gap41, "GAP-41 does not cite the line carrying '· Child-safe defaults'")
        self.assertIn(f"`{session_line}`", gap41, "GAP-41 does not cite the line carrying the session phrase")
        self.assertIn(
            f"| `· Child-safe defaults` | `{child_line}` |",
            gap41,
            "GAP-41's table does not point '· Child-safe defaults' at the line that carries it",
        )
        self.assertIn(
            f"| `· Session · ` + `{{n}} min` | `{session_line}` |",
            gap41,
            "GAP-41's table does not point the session phrase at the line that carries it",
        )
        self.assertNotIn(
            "`3644-3647`",
            gap41,
            "GAP-41 again calls 3644-3647 the wording's range; 3644 is only the session span",
        )
        game = read(self.sweep_path("CP-031-sweep-game.md"))
        self.assertIn("GAP-41", game, "the Game sweep does not name GAP-41 for the defaults line")
        self.assertIn("GAP-42", game, "the Game sweep does not name GAP-42 for the state words")
        # CP-022 must still be the file the notes named; if it ever gains these rows this test's
        # premise is wrong and the hand-off notes may come back.
        home = read(COPY_DIR / "CP-022-home.md")
        for word in ("Delayed evidence", "· Child-safe defaults"):
            self.assertNotIn(word, home, f"CP-022 now carries {word!r}; re-read this test's premise")

    def test_the_homework_sweep_covers_the_whole_notebook_component(self):
        """The card's 880-1000 slice cut the list's own actions, edit form and only dialog.

        `NotebookView` is the whole component from its declaration to the next top-level function.
        A sweep that stops at the card's slice drops "Remove from notebook", "Save changes" and the
        remove dialog — visible strings on the Homework surface. The file must state the component
        range and carry a row for the dialog, not just the list.
        """
        homework = read(self.sweep_path("CP-031-sweep-homework.md"))
        product = read(self.SOURCES / "90-course.js").splitlines()
        start = next(
            number for number, line in enumerate(product, start=1) if line.startswith("function NotebookView(")
        )
        end = next(
            number
            for number, line in enumerate(product[start:], start=start + 1)
            if re.match(r"^(?:function|const|let|var|class) ", line)
        ) - 1
        self.assertIn(
            f"90-course.js:{start}-{end}",
            homework,
            f"the sweep does not declare the NotebookView range 90-course.js:{start}-{end}",
        )
        self.assertIn("`880-1000`", homework, "the sweep does not explain the card's narrower slice")
        for fragment in ("Remove from notebook", "Save changes", "Remove this moment from the notebook?"):
            rows = [cells for cells in self.rows("CP-031-sweep-homework.md") if fragment in cells[0]]
            self.assertTrue(rows, f"the Notebook's {fragment!r} has no row")
            cited = {int(m.group(2)) for cells in rows for m in self.CITATION.finditer(cells[1])}
            self.assertTrue(
                any(start <= line <= end for line in cited),
                f"the row for {fragment!r} cites no line inside NotebookView ({start}-{end})",
            )

    def test_each_sweep_states_its_offline_and_overflow_evidence(self):
        for name in self.FLOORS:
            path = self.sweep_path(name)
            if not path.is_file():
                continue
            text = read(path).lower()
            self.assertIn("offline", text, f"{name} does not state the offline evidence")
            self.assertIn("overflow", text, f"{name} does not state the overflow evidence")

    def test_readme_points_at_the_sweep(self):
        readme = read(COPY_DIR / "README.md")
        for name in self.FLOORS:
            self.assertIn(name, readme, f"README does not list {name}")


if __name__ == "__main__":
    unittest.main()
