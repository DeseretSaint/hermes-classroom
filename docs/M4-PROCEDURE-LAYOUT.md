# M4-V2 — Procedure lesson layout and deterministic technical schematic

Status: product-line card (not 0.1.0 release evidence). Implementation for
`docs/VISUAL_MEDIA_PLAN.md` §8 on `wt/m4-procedure-renderer`.

## What this adds

A procedure lesson is the *same* block document as every other lesson, plus one optional,
typed `procedure` header. Nothing about the teaching text, the single check or the view lenses
changes.

```
lesson_document
  blocks[]                     ← unchanged: the step actions are these blocks
  check_id                     ← unchanged: one check, attached to one block
  procedure:
    tools[]                    ← typed header facts
    parts[]
    hazards[]                  ← required: name the hazards or state none apply
    stop_condition             ← required
    steps[]: { block_id, check? }   ← ordered references, not a second copy of the prose
    schematic|null:
      { title, text_equivalent, artifact_id|null, source_id, rows[{label,value,row}] }
    source: { source_id, permission }   ← required; permission public_domain|licensed|linked
```

Why this shape:

- **No second text authority.** A step's action is the referenced block's own `deep` prose, so
  the procedure cannot drift from the lesson. `steps[].check` is a per-step verification cue, not
  the section check.
- **No second check.** `check_id` still attaches to exactly one block; the procedure layout
  prints that check once, as the verification checklist.
- **No invented values.** A torque/clearance/sequence value can only appear in
  `schematic.rows`, which are typed facts checked against the document source ledger
  (`schematic.source_id` must be a cited document source). An illustration cannot carry one.
- **Honest provenance.** `source` is required and `permission` may not be `unknown`, so a
  technical procedure is never taught beside an unlicensed reference.

## Validation (`coursebook/lesson_document.py`)

`_procedure()` normalises and validates the header; the document hash and `document_id` include
it when present, so the layout is content-bound. `validate_document()` re-validates a served
document. `narrative_text()` includes every procedure string, so the existing answer-leak check
covers the header too. Refusals (non-exhaustive): unknown fields, empty stop condition, no
hazards, a step pointing at a block that is not in the document, a repeated step, an empty
schematic, a schematic source not in `source_ids`, an unknown permission.

The read projection carries an authored procedure from a stored page (`document.author[.
procedure]` or `page.procedure`); every existing document is byte-identical because the key is
omitted when absent.

## Contract

`contracts/rpc.v9.json` gains an optional `procedure` property on `lesson_document` plus
`lesson_procedure_step`, `lesson_procedure_schematic` and `lesson_procedure_source` definitions.
It is additive and optional: no existing required field changed, and the wire version stays 9
(this is a read-shape extension, not a new method; a version bump is a release decision).

`coursebook/media.py`'s `/media` preview now also returns the artifact's stored `permission` and
`source_ids`, so a sourced reference can display real provenance in the renderer.

## Desktop (`desktop/plugin.js`)

`LessonDocumentView` renders the procedure lens in Textbook when `document.procedure` is present:

- `ProcedureHeader` — tools and parts as typed lists;
- `ProcedureHazardCallout` — `role="note"`, coral rule and a literal **Do not proceed** label,
  hazards plus the stop condition; never an illustration;
- `ProcedureSchematic` — the rows, sorted by the backend's `row` then label rule, as a table;
  the attached SVG (when one was produced) is shown through the same single `MediaSegment`
  preview, and the rows remain if bytes cannot be reached;
- numbered step cards — `01…NN`, the block's headline and `deep` prose, its media, the step
  check cue, source chips, save actions and, on the one block that carries it, the check;
- one **Verification checklist** heading over that check;
- `ProcedureSourceCard` — source title, URL, and the permission status in words
  ("Licensed for this course" / "Public domain" / "Linked — not reproduced");
- blocks the author did not place in `steps` still render under "Also in this lesson".

Illustration labels are explicit: "Context illustration — not a specification, measurement,
sequence or safety authority." Guided and Field Quest keep their existing single-block lenses
over the same document.

## Evidence

- `tests/test_procedure_document.py` — 15 tests: shape, hash binding, determinism, step/block
  integrity, hazards/stop condition, source permission, schematic ledger check, answer-leak
  visibility, deterministic SVG bytes, projection round-trip.
- `tests/test_desktop_procedure.py` — 13 render tests in real React via the shipped module.
- `tests/test_media_generation.py` — preview carries permission/source_ids.
- Full suite: `python3 -m unittest discover -s tests -t .` → 1028 tests.
- `node --check desktop/plugin.js`.
- `audit/visual/m4-procedure/` — light/dark, 460 px, 200% text, reduced motion; DOM
  measurements in `evidence.json` (5 steps, 4 schematic rows, hazard present, no overflow).

## Honest limits

- The frames are a static render of the shipped module in headless Chromium, not a live Desktop
  capture: no backend, no `lesson.page` RPC, no artifact bytes. The schematic image therefore
  shows the module's "Loading media" state; the rows above it are the authority.
- No live backend authors `procedure` today. This card proves the validator, contract and
  renderer against a contract-valid fixture; authoring the header in the lesson prompt is a
  separate backend card.
- The workspace is scoped to the section; no chat, transcript or composer was touched.
- Not merged to master, not pushed, no tag, no publish, no catalog PR.
