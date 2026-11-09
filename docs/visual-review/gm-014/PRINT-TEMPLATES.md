# GM-014 print templates

Four print roles, one technical sheet, two paper sizes. The templates are implemented once in
`coursebook/homework_print.py`; the PDFs beside this file are printed from them by
`scripts/gm014_print_proof.py`.

## Page inventory

| role | pages | audience | carries | never carries |
|---|---|---|---|---|
| parent guide | 2 | parent / adult operator | objective, materials, preparation, four steps, what to notice, expected responses, sources, fixture lesson block binding | child data, attempts, tutor turns, a grade |
| learner page | 1 | learner | one target with reading and romaji, one context, at most three steps, one success criterion, task-appropriate completion line | answer guide, expected responses, common errors, grade, XP |
| answer guide | 1 | parent only | target, expected responses, common errors, next step | learner identity, attempts, a score |
| one-page homework | 1 | learner | condensed task card with a task-appropriate completion record | answer guide, expected responses, grade, XP |
| technical sheet | 2 | learner / operator | typed procedure, hazards, stop condition, structured torque rows, text equivalent, cited source | generated images, AI art as procedure |

The cover copy is chosen by task kind, not copied across packs: a label task gets label-specific
"What to notice", "Common errors" and "Next step" text and a `Day 1 / Day 2` completion record; a
mealtime greeting task gets before-meal/after-meal text and `breakfast / lunch / dinner`. The
label pack prints all six lesson labels in every one of its four documents, because its task lets
the learner choose any three.

## Paper and margins

| paper | page box | sheet padding | folio |
|---|---|---|---|
| A4 | 210 × 297 mm | 18 mm top, 16 mm sides, 16 mm bottom | `Page n of N` at 9 mm from the foot |
| Letter | 8.5 × 11 in | 0.70 in top, 0.65 in sides, 0.62 in bottom | `Page n of N` at 9 mm from the foot |

Every page is an explicit `<section class="sheet">` at the paper's exact size with
`break-after: page` and zero `@page` margin, so the margins are the template's, not the print
dialog's. The folio is part of the page, not a running header the engine may drop.

## Type

- Body: Noto Serif / Iowan Old Style / Georgia fallback, 10.5 pt, 1.45 line height.
- Headings: same serif at 21 pt (h1) and 13 pt (h2), 600 weight.
- Eyebrow and folio: sans, 8–8.5 pt, 0.14 em tracking, uppercase.
- Japanese: Noto Sans CJK JP (system font when installed), target display 30 pt, reading 13 pt.
- Romaji: italic, 12 pt. Romaji is a scaffold that fades; the lesson says so.

## Ink

- Paper `#ffffff`; ink `#1a1713`; secondary text `#4a443a`; rules `#d7cbb4`.
- No filled colour panels, no gradients, no shadows in print.
- No meaning is carried by colour alone. Every state is a word: `PARENT ONLY · ANSWER GUIDE`,
  `You are done when`, `Stop condition`, `Deterministic schematic`.
- The black-and-white proof under `bw/` is rasterised in grayscale at 150 dpi; text and rules
  remain legible because nothing depends on hue or fill.

## Alt text, language and captions

The only figure in the set is the label-task line drawing. It ships as inline SVG with
`role="img"`, an accessible title and description, and a visible `<figcaption>` that says the
drawing is orientation only and states no word or reading. The technical sheet deliberately has
no figure: the structured torque rows are the diagram.

Japanese runs in the HTML carry `lang="ja"` (the document itself is `lang="en"`), including
inline Japanese quoted inside English running copy, table cells and list items: each run is
wrapped in its own `class="jp" lang="ja"` element, so an HTML consumer reads いただきます and
ドア as Japanese even inside a sentence like "say いただきます (itadakimasu) out loud".
`test_japanese_runs_declare_their_language` parses every rendered document and fails on any kana
or ideograph text node that is not inside a `lang="ja"` element. **PDF tagging is not claimed:**
the Chromium export is untagged, so the SVG's accessible name and the `lang` attributes do not
survive into the PDF. Selectable text is claimed and proven by extracting it back with
`pdftotext`; PDF accessibility tagging is not.

## Page numbers

Each sheet prints its own folio (`Coursebook · <role>` on the left, `Page n of N` on the right).
The proof checks the last folio of every document is present in the extracted PDF text.

## What is in this directory

- `MANIFEST.json` — machine-readable list of every PDF/PNG, its paper, role, page count, page
  size, SHA-256, required text and whether that text was found in the PDF.
- `PRINT-PROOF.md` — human-readable proof summary generated from the manifest.
- `CONTENT-CHECKLIST.md` — the one-target/one-context/one-criterion gates.
- `SOURCE-PROVENANCE.md` — fixture lesson block hash and phrase provenance.
- `a4/`, `letter/` — the PDFs.
- `bw/` — grayscale PNGs for the black-and-white legibility check.
- `*.png` beside each PDF in `a4/` and `letter/` — colour page images for review.
