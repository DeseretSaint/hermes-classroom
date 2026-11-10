# Copy and state inventory for the v3 screens

Card: **CP-031**. Scope: CP-021, CP-022, CP-023, CP-024, CP-025a, CP-025b. Docs only.

This directory answers one question per screen: **for every string that screen is told to render,
where does the words come from, and has that source got a row in the copy deck?**
It does not change product copy. `docs/concept-parity/COPY.md` is owned by CP-001; every proposal
here is a request to that card.

## Sources, in precedence order

1. `docs/concept-parity/COPY.md` — the only source of product wording (177 rows).
2. `docs/concept-parity/SPEC-V3.md` §5.1–§5.5 — region and state maps that reference deck ids.
3. `contracts/rpc.v24.json` — `$defs.methods.properties.<method>.response` and `$defs.<def>` for
   every `field:` source; `contracts/pack-manifest.v2.json` for `pack.inspect.manifest.*`.
4. `docs/concept-parity/cards/CP-0NN.md` — the card body, which is what a maker actually reads.
5. `desktop/src/*.js` — the shipped v2 strings, cited only where a v3 card adopts a surface that
   already exists (CP-025a, CP-025b) and the deck has no row to read.

Where the deck and a card body disagree, **the deck wins** (`COPY.md` line 3: "It is the only
source of product wording"). Those are reported as conflicts, not silently corrected.

## How to read a table

| Column | Meaning |
|---|---|
| `string` | the words the surface renders, or `{placeholder}` when the surface fills a field |
| `copy id` | the deck row, or `GAP-nn` (see `GAPS.md`) |
| `deck row` | `COPY.md` file:line |
| `value` | the `field:`/`pack:`/`computed:` source the deck names, resolved against the contract |

Status tags: **ok** (row exists and resolves), **conflict** (body wording differs from the row),
**gap** (no row exists), **unresolved** (row exists but its source cannot be read).

## Verification performed for this inventory

All machine-checked, reproducible from the docs tree:

1. **Deck ↔ spec id parity.** Every copy id in `COPY.md` is referenced by `SPEC-V3.md` and every
   copy id `SPEC-V3.md` names exists in the deck. Zero orphans in either direction (177/177).
2. **Every `field:` source resolves.** All `field:` cells in `COPY.md` were walked against
   `contracts/rpc.v24.json` (method responses and `$defs`) and `contracts/pack-manifest.v2.json`,
   following local `$ref` chains. Every path resolves. The only non-contract names are the four
   CP-005 forward fields the deck already allowlists (`library_item.subject_label`,
   `sections_done`, `sections_total`, `is_new`).
3. **Destination labels match.** `nav.home`/`nav.courses`/`nav.workshop`/`nav.parent` equal
   `DESTINATIONS` in `desktop/src/00-header.js:129-136`, including `Parent Studio`.
4. **Row-level gaps are what remain.** The deck and the spec agree with each other because they
   were written together; they do not cover every string a card body tells a maker to paint.
   That is the entire GAPS list.
5. **The inventory is machine-checked.** `tests/test_cp_copy_inventory.py` resolves every `field:`
   path in this directory against the frozen contracts, rejects a proposed source that names a
   method or setter instead of a value, checks every `== <value>` predicate against its contract
   enum, and requires a row for every member of every enum the inventory cites.

## Result

| Card | Screen | Deck rows used (screen-specific; +4 shared nav) | Gaps | Conflicts | Verdict |
|---|---|---|---|---|---|
| CP-021 | Discover / Workshop (R-DISC) | 29 | 1 (`GAP-07`) | 3 (`GAP-08`, `GAP-09`, `GAP-10`) | shippable after 4 decisions |
| CP-022 | Home (R-HOME) | 25 | 3 (`GAP-03`, `GAP-04`, `GAP-05`) | 1 (`GAP-06`) | shippable after 4 decisions |
| CP-023 | Classroom (R-CLASS) | 46 | 7 (`GAP-11`–`GAP-17`) | 1 (`GAP-18`) | **not shippable** — 8 strings have no row (`GAP-17` covers all six `evidence_class` values) |
| CP-024 | Course home (R-MAP) | 30 | 3 (`GAP-19`, `GAP-20`, `GAP-22`) | 1 clarify (`GAP-21`) | shippable after 4 decisions |
| CP-025a | Homework + Game | 2 | 3 (`GAP-23`–`GAP-25`, plus `GAP-30` scope) | body defect (`GAP-26`) | **blocked** — deck has no section for these surfaces |
| CP-025b | World Studio + Parent Studio | 0 | 2 (`GAP-27`, `GAP-28`, plus `GAP-30` scope) | body defect (`GAP-29`) | **blocked** — deck has no section for these surfaces |

Shell-level rows (`GAP-01` settings sheet, `GAP-02` companion line) are needed by every screen that
paints the rail or the companion.

## The one-line version

CP-021 to CP-024 are close: their state copy is fully written, and the gaps are **component
labels** (a card title, a node label, the answer-surface words, the level line, the evidence
class words) that a maker would otherwise invent. CP-025a and CP-025b are not close: the deck ends
at the design-system lab, so every visible string on the homework, Game, World Studio and Parent
Studio surfaces has no deck row. Those two cards cannot start until CP-001 gains `hw.*` and
`studio.*` sections.

## Files

- `CP-021-discover.md`, `CP-022-home.md`, `CP-023-classroom.md`, `CP-024-course-home.md`
- `CP-025a-homework-game.md`, `CP-025b-studio.md` — each carries a **partial sample** of the shipped
  strings the deck section would be built from, with `desktop/src` file:line citations. `GAP-30`
  records that the sweep is incomplete; neither file is a licence to author the whole section.
- `GAPS.md` — every gap as a proposed deck row, with the source form, the cap, and the card that
  needs it. Proposals only.
