# GM approved textless art plates and provenance rules

Card: GM-013. Binds GM-003 (plate generation and cache), GM-004 (World Studio), GM-006/GM-014
(pack and print) and GM-016 (final parity).

Two lanes exist in this product. They are not interchangeable:

| Lane | Owner | Output | Used for |
|---|---|---|---|
| **Press Plate** (existing) | pack builder, `bundled/packs/build_bundled_packs.py` | one flat plate per pack cover | pack and catalogue covers; rules unchanged in `docs/ART-DIRECTION-COVERS.md` |
| **World plate** (this card) | `WorldPolicy` + world media job | hero, cover, section, optional scene | a course's world, its course home, its shelf card, a captioned print plate |

Both lanes are **textless**. A world plate is never a screenshot, never UI chrome, never a diagram of
the course.

---

## 1. The approved plates in this card

`docs/gm-visual/manifest.json` is the machine record. These five are the reference set; each is
host-composed from the Atlas Lamp palette by `scripts/build_gm_visual_assets.py` — no model call, no
stock imagery, no third-party asset.

| Plate | File | Role | Use | sha256 (first 16) |
|---|---|---|---|---|
| Japanese L0 — lantern district / cafe | `docs/gm-visual/boards/japanese-lantern-district.svg` | orientation | Japanese course world reference; print specimen page 2/5 | `05eb83c0d820914f` |
| Head gasket — service bay / workshop manual | `docs/gm-visual/boards/head-gasket-service-bay.svg` | orientation | technical course world reference | `87f7cfb069f345d3` |
| Astronomy — observatory | `docs/gm-visual/boards/astronomy-observatory.svg` | orientation | science course world reference | `2670d8a2539b4e10` |
| Sourdough — kitchen table | `docs/gm-visual/boards/sourdough-kitchen-table.svg` | orientation | cooking course world reference | `2e489b92bdb1eee3` |
| Anti-generic swap instrument | `docs/gm-visual/boards/anti-generic-swap.svg` | review instrument | reviewer's swap check; labels allowed here only | `f80714e03fde69ea` |

**These plates are reference material, not course content.** GM-004 renders its own approved plates;
it may reuse the motifs and the palette path, not the file as a lesson image. A course's shipped
plate must carry its own provenance row.

Mechanical properties (asserted by `tests/test_gm_visual_spec.py`): no `<text>` element, no `<image>`
reference, no `filter`/`gradient`, only token colours from `contracts/cb.tokens.v2.json`, and none of
`ochre`, `coral`, `plum`.

---

## 2. What a plate may be

| Allowed | Condition |
|---|---|
| Host-composed deterministic SVG | the default for anything instructional or procedural; drawn from structured facts |
| A sourced figure with permission | carries creator, source URL, licence and access date; a technical figure only when the source grants reuse |
| A model-generated illustration | orientation only; textless; provenance row; never in a procedure, measurement or safety role |
| A mechanical crop of an approved master | one crop of one master; never a second drawing |

## 3. What a plate may never be

- Text, letters of any script, digits, logos, watermarks, vendor marks, rating stars, fake badges,
  fake UI chrome, fake window bars.
- A screenshot, a mockup of the product, or a composed UI.
- A procedure, torque sequence, clearance, dosage, wiring value, measurement, hazard callout, or
  answer.
- A photograph or model image presented as "verified", "accurate", "official", "manual" or "the
  learner's own device".
- A stock-photo aesthetic that could serve any course.
- A second mascot. The fox is the only Coursebook mascot; a plate may contain the fox only as the
  textless companion mark, and never a robot.

---

## 4. Provenance record (per plate, mandatory)

A plate cannot be approved, cached or printed without this row. Missing fields fail the approval,
not the render.

| Field | Source | Rule |
|---|---|---|
| `plate_id` | generated | stable, course + role + section scoped |
| `role` | generated | `hero` / `cover` / `section` / `scene` / `reference`; every shipped plate is `orientation` in effect |
| `provider` | job | model vendor, or `host` for a deterministic SVG |
| `model` | job | exact model id, or `none` |
| `prompt_hash` | job | sha256 of the exact prompt text; absent when `model = none` |
| `style_hash` | job | sha256 of the selected style board |
| `course_hash` | plan | sha256 of the approved plan the motifs came from |
| `generated_at` | job | ISO-8601 UTC |
| `palette` | job | `contracts/cb.tokens.v2.json` + the one optional subject accent |
| `licence` | job | `CC0-1.0`, `MIT`, `ISC`, `Apache-2.0`, `BSD`, `CC-BY-4.0` (with visible attribution) — else rejected |
| `text_check` | job | `none` for host SVG; `ocr:<result>` for model output; a positive hit rejects the plate |
| `alt_text` | author | one sentence, no interpretation beyond the plate |
| `text_equivalent` | author | one sentence a screen reader or a print caption can stand on |
| `caption` | author | fixed wording, §5 |

A plate with `model = none` records the generator path and the palette source instead of a provider
and prompt. **Never record a provider or a prompt for a plate that had no model call**, and never
record a model call for a plate that was drawn.

## 5. Caption and label wording

The caption is fixed and appears beside every plate in a primary surface and in print:

> World visual — generated plate; orientation only, not a diagram of the course.

For a host-composed plate the same sentence applies with `host-composed plate` in place of
`generated plate`. The full wording, alt text and text-equivalent template is
`docs/gm-visual/print/CAPTION-SHEET.md`.

Forbidden caption words: `verified`, `accurate`, `official`, `manual`, `diagram of`, `photo of`,
`your`, `real`.

## 6. Approval and cache rules

1. A plate is approved only in the World Studio's **world check**, with real UI text over it, by the
   learner; or in print, by the parent's explicit page approval.
2. Approval is hash-fenced: `plate_id + style_hash + course_hash + role + section_id`. A changed
   plan that alters the section set marks the world `stale`; an unchanged plan reuses the cache and
   never pays twice.
3. A failed provider leaves **named missing roles** and no file. It never writes a placeholder image
   and never silently retries with spend.
4. A rejected plate is recorded with its reason (`text found`, `swap test failed`, `safety role`,
   `provenance incomplete`) so the retry can change the prompt instead of repeating it.
5. Print may omit a plate for low ink; it may not substitute one.

## 7. Print rules for a plate

- ≤90 × 60 mm, framed by a 0.5 pt rule, on white, with caption and text equivalent beneath it.
- Omitted entirely when `low_ink = true`; the caption and text equivalent stay.
- Never the only carrier of a fact: no number, no sequence, no arrow that means "then".
- A technical diagram in a pack is deterministic SVG or a sourced figure — never a model plate.

## 8. What the reviewer checks

For each plate: the manifest row exists and matches the bytes; no `<text>`; palette tokens only; the
subject-swap test rejects it for an unrelated course; the caption wording is exact; alt text and text
equivalent exist; if `model != none`, an OCR/text check is recorded as clean and the plate is not in
a procedure, measurement or safety role.
