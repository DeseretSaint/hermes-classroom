# Copy and state inventory for the v3 screens

Card: **CP-031**. Scope: CP-021, CP-022, CP-023, CP-024, CP-025a, CP-025b. Docs only.

**Inventory revision:** the complete sweep and every cited line are re-derived from `origin/master`
at **`14fb14f3e8c5306f973bf98ba270140ca98f0ac5`** (CP-031d, card `t_d20f3f5e`, re-deriving
CP-031c-R's `a11bc0e4` sweep, which re-derived CP-031c's `5d2b303e` sweep and kept CP-031b-R's
`t_adc9bdee` substance). Docs only; no product string changed. The swept revision is pinned on
**content**: `00-header.js` `ab62cbd7`, `30-home.js` `9877b940`, `90-course.js` `a47e7fe2`,
`95-studio.js` `77d8b2ec`, `97-world.js` `00d46dcf`. A master
that moves without touching those five blobs is harmless; one that moves a blob fails the gate by
name, so the next author re-sweeps rather than rotating citations.

This directory answers one question per screen: **for every string that screen is told to render,
where does the words come from, and has that source got a row in the copy deck?**
It does not change product copy. `docs/concept-parity/COPY.md` is owned by CP-001; every proposal
here is a request to that card.

## Sources, in precedence order

1. `docs/concept-parity/COPY.md` — the only source of product wording (387 rows).
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
   copy id `SPEC-V3.md` names exists in the deck. Zero orphans in either direction (387/387).
2. **Every `field:` source resolves.** All `field:` cells in `COPY.md` were walked against
   `contracts/rpc.v24.json` (method responses and `$defs`) and `contracts/pack-manifest.v2.json`,
   following local `$ref` chains. Every path resolves. The only non-contract names are the four
   CP-005 forward fields the deck already allowlists (`library_item.subject_label`,
   `sections_done`, `sections_total`, `is_new`).
3. **Destination labels match.** `nav.home`/`nav.courses`/`nav.workshop`/`nav.parent` equal
   `DESTINATIONS` in `desktop/src/00-header.js:187-194`, including `Parent Studio`.
4. **Row-level gaps are what remain.** The deck and the spec agree with each other because they
   were written together; they do not cover every string a card body tells a maker to paint.
   That is the entire GAPS list.
5. **The inventory is machine-checked.** `tests/test_cp_copy_inventory.py` resolves every `field:`
   path in this directory against the frozen contracts, rejects a proposed source that names a
   method or setter instead of a value, checks every `== <value>` predicate against its contract
   enum, requires a row for every member of every enum the inventory cites, and re-derives from the
   source and the tables two claims that drifted once: the "shipped in v2" pack-state row may only
   list words `CB_TAKEHOME_STATE_WORD` actually defines, and the CP-023 verdict carries no string
   count that the CP-023 gap rows do not produce. Round 3 corrected the gate itself: it now reads
   the real `` `field:path` `` cell form, asserts at least 50 resolved source cells so it cannot go
   vacuous, and rejects a fabricated `field:` row; `tests/test_cp_spec.py` follows an array's
   local-`$ref` `items` so `course.outline.objectives[].title` (the C3/M5 node label) resolves.
6. **The full sweep is gated too (CP-031b-R and CP-031c, united).** `TestCp031bSweep` is the
   substance gate CP-031b-R landed: all five `CP-031-sweep-*.md` files exist, each cites its
   in-scope source file with `file:line`, no cited line is past the end of that file, every table
   row carries all four columns and the per-file floor holds, `GAPS.md` marks `GAP-30` **closed**
   and defines `GAP-31`–`GAP-42`, `GAP-38`–`GAP-42` are defined and referenced by the sweeps that
   own them, the round-two findings keep a row at the line that renders them, the
   consequence family is split per rendering, the two learner-completion wordings are not merged
   into one row, the Game sweep accounts for the `ChildSafeLine` block, and the Homework sweep
   covers the whole `NotebookView` — the card's `880-1000` slice drops the list's own actions,
   edit form and only dialog. Round 3 tightened it: the audit goes through the inventory **rows**
   (a citation in a section heading or a prose note no longer counts), a row citing `a-b` covers
   both ends, and a mutation that deletes a row or points it at a neighbouring line is caught
   rather than absorbed by a region heading. Round 4 added the last class of defect this sweep kept
   producing: a "belongs to another inventory" note is a coverage claim and is asserted against the
   file it names — the Game sweep had displaced the Home defaults line and the `DESK_STATE_WORD`
   map onto `CP-022-home.md`, which carries neither (`GAP-41`, `GAP-42`).
7. **The sweep is string-anchored, not line-anchored (CP-031c).** `TestCp031cSweep` re-derives the
   population from each of the five segment files at test time: it lexes every single-quoted,
   double-quoted and template literal outside comments and regexes, keeps the multi-word
   user-facing ones, and fails with the **missing set** if any literal has no inventory row. It
   checks the other direction too — every row must cite a `file:line` that actually carries the
   row's own words — and it fails if a sweep file disappears, if a declared row count disagrees
   with the table, if `GAP-30` reopens, if any sweep says a block "belongs to" / "stays with"
   `CP-022-home.md` without that file carrying the strings, or if a swept segment blob changes
   under the recorded sha. `REQUIRED_ROWS` is keyed on `(file, exact string)`: the test locates
   the literal in the file at test time instead of trusting a line number, so a re-authored file
   fails loudly rather than rotating the citations. Six named mutation probes prove the gate can
   fail: a deleted row, a retargeted citation, a deleted sweep file, a truncated table, a reopened
   `GAP-30`, and a `CP-022` hand-off are each rejected.

   **Scope of the completeness claim.** The extraction gate covers multi-word user-facing literals.
   Single-word controls (e.g. `Cancel`) are outside that definition; the ones that carry state are
   named in `GAPS.md`. CSS class lists, lengths, colours, identifiers, paths and code fragments are
   excluded by the named classes in the test file, not by a screen-swallowing regex.

## Result

| Card | Screen | Deck rows used (screen-specific; +4 shared nav) | Gaps | Conflicts | Verdict |
|---|---|---|---|---|---|
| CP-021 | Discover / Workshop (R-DISC) | 29 | 1 (`GAP-07`) | 3 (`GAP-08`, `GAP-09`, `GAP-10`) | shippable after 4 decisions |
| CP-022 | Home (R-HOME) | 25 | 3 (`GAP-03`, `GAP-04`, `GAP-05`) | 1 (`GAP-06`) | shippable after 4 decisions |
| CP-023 | Classroom (R-CLASS) | 46 | 7 (`GAP-11`–`GAP-17`) | 1 (`GAP-18`) | **not shippable** — the stepper node label, the answer-surface words, the level line and the six evidence-class words have no deck row (`GAP-11`–`GAP-17`) |
| CP-024 | Course home (R-MAP) | 30 | 3 (`GAP-19`, `GAP-20`, `GAP-22`) | 1 clarify (`GAP-21`) | shippable after 4 decisions |
| CP-025a | Homework + Game | 2 | 3 (`GAP-23`–`GAP-25`, plus `GAP-30` scope) | body defect (`GAP-26`) | **blocked** — deck has no section for these surfaces |
| CP-025b | World Studio + Parent Studio | 0 | 2 (`GAP-27`, `GAP-28`, plus `GAP-30` scope) | body defect (`GAP-29`) | **blocked** — deck has no section for these surfaces |

Shell-level rows (`GAP-01` settings sheet, `GAP-02` companion line) are needed by every screen that
paints the rail or the companion.

## The one-line version

CP-021 to CP-024 are close: their state copy is fully written, and the gaps are **component
labels** (a card title, a node label, the answer-surface words, the level line, the evidence
class words) that a maker would otherwise invent. CP-025a and CP-025b are still not shippable: the
deck has no section for the whole Homework, Game, World Studio or Parent Studio surface
(`GAP-23`, `GAP-24`, `GAP-27`, `GAP-28`), and CP-001g only authored the twelve families the sweep
found without a gap (`GAP-31`–`GAP-42`) — not the surfaces they belong to.

## Files

- `CP-021-discover.md`, `CP-022-home.md`, `CP-023-classroom.md`, `CP-024-course-home.md`
- `CP-025a-homework-game.md`, `CP-025b-studio.md` — each carries a **partial sample** of the shipped
  strings the deck section would be built from, with `desktop/src` file:line citations. `GAP-30`
  records that the sweep is incomplete; neither file is a licence to author the whole section.
- `CP-031-sweep-parent-studio.md`, `CP-031-sweep-world.md`, `CP-031-sweep-game.md`,
  `CP-031-sweep-homework.md`, `CP-031-sweep-chrome.md` — the **complete** literal sweep (CP-031b,
  card `t_adc9bdee`; re-derived whole-file by CP-031c, card `t_0458a135`; re-swept at `a11bc0e4`
  by CP-031c-R, card `t_54a44039`) of the whole of `95-studio.js`, `97-world.js`, `30-home.js`,
  `90-course.js` and `00-header.js`. Every row carries
  `string | source file:line | state | proposed id`. These are the files
  `hw.*` / `game.*` / `world.*` / `studio.*` must be authored from; `GAP-30` is closed.

  | file | source | rows |
  |---|---|---|
  | `CP-031-sweep-chrome.md` | `desktop/src/00-header.js` | 52 |
  | `CP-031-sweep-homework.md` | `desktop/src/90-course.js` | 331 |
  | `CP-031-sweep-game.md` | `desktop/src/30-home.js` | 216 |
  | `CP-031-sweep-parent-studio.md` | `desktop/src/95-studio.js` | 647 |
  | `CP-031-sweep-world.md` | `desktop/src/97-world.js` | 92 |

  CP-001g (`t_4d6d5b56`) rowed by hand the state words the extractor drops — `Started`, `Stamped`,
  `Planned`, `Skipped`, `Expired`, `Plan` and `clipped` — because a single-token word is exactly the
  family member that can vanish between sweeps. Those are the only count changes: 1331 rows became
  1338 (+7: chrome 51→52, game 215→216, parent-studio 642→647), and each row names the deck id it
  feeds.
- `GAPS.md` — every gap as a proposed deck row, with the source form, the cap, and the card that
  needs it. Proposals only.
