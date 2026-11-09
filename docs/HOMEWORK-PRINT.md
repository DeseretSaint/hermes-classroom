# Homework print pack (GM-014 content and print seam)

This document describes the content fixture and the print path that produce the take-home pages.
It is the developer note for the module GM-008 consumes. The real proof lives in
`docs/visual-review/gm-014/`; this file explains how to rebuild it.

## What this owns

| piece | path |
|---|---|
| fixture (phrases, labels, tasks, sources) | `bundled/homework/japanese-l0-mealtime/fixture.json` |
| print templates and renderer | `coursebook/homework_print.py` |
| proof builder | `scripts/gm014_print_proof.py` |
| proof set | `docs/visual-review/gm-014/` |
| content rules and print rules | `tests/test_homework_content_print.py` |
| fixture lesson block hash and phrase provenance | `docs/visual-review/gm-014/SOURCE-PROVENANCE.md` |
| content checklist | `docs/visual-review/gm-014/CONTENT-CHECKLIST.md` |

It does not own a homework table, an RPC method, an enrollment, a job or a send. Those belong to
GM-007/GM-008. This module is pure content plus HTML/PDF rendering.

## Fixture shape

`fixture.json` carries a `lesson` block and a `tasks` array.

- `lesson.targets[]` — phrase targets with `display`, `reading`, `romaji`, `meaning`, `register`,
  `use` and `source_ids`.
- `lesson.labels[]` — household words with the same fields minus register.
- `lesson.sources[]` — the citation ledger: `source_id`, `title`, `url`, `accessed`, `quote`,
  `supports`.
- `tasks[]` — `task_id`, `task_kind`, `audience`, `title`, `target_id`, one `context` sentence,
  1–3 `steps`, one `success_criterion`, `estimated_minutes` (3–10) and `completion`
  (`self_reported` or `parent_reported`).
- `target_sets[]` — the one bounded label set; it suggests three labels, lists three alternates, and
  all six are printed in every label-pack document.

The fixture lesson block hash is `sha256` over the canonical JSON of the fixture's own `lesson`
block:

```
coursebook.homework_print.lesson_hash(fixture["lesson"])
coursebook.homework_print.binding(fixture)
# {"source_course_id", "source_objective_id", "source_lesson_version", "source_lesson_hash"}
```

Change a printed form, reading, romaji or gloss and the hash changes. A pack that prints these
pages can therefore record exactly which fixture lesson text it printed. The four ids name fields
inside the fixture; no live course with those ids exists in this repository, and the parent guide
says so instead of implying a published lesson.

## API

```python
from coursebook import homework_print as hp

fixture = hp.load_fixture()
assert hp.validate_fixture(fixture) == []

pages = hp.render_documents(fixture, "hw_premeal", paper="A4")   # or "Letter"
pages["parent_guide"]     # complete HTML, 2 sheets
pages["learner_page"]     # complete HTML, 1 sheet, no answer key
pages["answer_guide"]     # complete HTML, 1 sheet, PARENT ONLY
pages["homework_sheet"]   # complete HTML, 1 sheet

pdf = hp.write_pdf(pages["learner_page"], "learner.pdf")          # Chromium, selectable text
hp.pdf_info(pdf); hp.pdf_text(pdf); hp.pdf_to_png(pdf, "learner", gray=True)
```

`render_technical_document(document, paper="A4")` renders a validated procedure lesson
(`coursebook.lesson_document` shape, e.g. `tests.test_procedure_document.head_gasket_document()`).
It prints typed steps and the structured schematic rows. It never embeds an image.

## Rebuild the proof

```bash
python3 scripts/gm014_print_proof.py
python3 -m unittest tests.test_homework_content_print -v
```

The script prints every page with headless Chromium, rasterises PNGs, extracts the PDF text back
and refuses to write `MANIFEST.json` if any page loses its last body sentence. It needs
`chromium`, `pdfinfo`, `pdftotext` and `pdftoppm` on `PATH`, and a system font with Japanese
coverage (`Noto Sans CJK JP` is used when present). Nothing is uploaded or sent.

Re-running rewrites each PDF's creation timestamp, so the recorded SHA-256 changes even when the
pages are identical. Regenerate and commit the whole set together; do not mix old and new files
under one manifest.

## Print rules encoded in the template

- A4 (210 × 297 mm) and Letter (8.5 × 11 in) page boxes with zero `@page` margin and an explicit
  sheet padding, so margins do not depend on the print dialog.
- White paper, near-black ink, hairline rules. No filled colour panels, no gradients, no
  colour-only meaning. State labels are words: `PARENT ONLY`, `You are done when`, `Stop condition`.
- Serif body text for reading, a small sans eyebrow, Noto Sans CJK JP for Japanese. The Japanese
  is embedded as text, not rasterised.
- Every sheet prints `Page n of N` in a folio at the foot of the page.
- The learner page and the one-page homework sheet never carry the answer guide; the answer guide
  is a separate document marked `PARENT ONLY · ANSWER GUIDE`.
- Any figure carries `role="img"`, an accessible title and description, and a visible caption
  that says it is orientation only.
- Japanese runs carry `lang="ja"` in the HTML, including inline runs quoted inside English
  sentences; a test parses every rendered document and fails on any kana/ideograph text node
  outside a `lang="ja"` element. The exported PDF is untagged, so PDF accessibility tagging is
  not claimed; selectable text is claimed and proven by `pdftotext`.

## Limitations

- The fixture is demo content, not a published course. No native-speaker review is recorded and
  none is claimed.
- The `demo-japanese-l0-mealtime` course and `obj_mealtime_greetings` objective are fixture-local
  ids. They are not a live course lesson, and the printed binding table says so.
- Register for いただきます is recorded as "polite (ます form; author's analysis)"; the
  cited Jisho entry does not label it. ごちそうさまでした is recorded as "polite (teineigo; Jisho label)".
- Only one Japanese lesson is covered: two mealtime greetings and six household labels. The
  labels are recorded against Jisho entries; the fixture does not claim a curriculum sequence.
- The technical sheet prints the lesson's structured rows. The source manual remains the
  authority for torque values and safety; the page says so.
- The proof is static. Interaction, screen view and responsive states are GM-008's card, not this
  one.
