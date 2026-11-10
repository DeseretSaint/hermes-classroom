# GM-018 take-home print follow-ups proof

- pack: `thp_d52011c5e4774b6295ba9f2121037f9e` state `exported`
- exported PDF artifact: `art_f55e07aec038488fb8f1b25263b5e31e` (sha256:e1d3eecd843042789699beecace7473ac75f21f310d7df430e87f8fb4cbd1102), source of the Letter file
- pack content language: `en-US` (from the stored `content_json`)
- HTML document: `audit/gm-018/gm-018-takehome.html` (4007 bytes, `sha256:e2b79e2cddb165ea6f182d41439c0122d8c771e224d1a707a54cededaccb0172`)

## Tagged PDF (measured, not assumed)

The Letter file is the exported artifact byte-for-byte (`artifacts.path`); the A4 file is a labelled re-render of the same bound pages, because `takehome.export` writes Letter only. Both carry the pack's stored language.

| Paper | File | Source | Pages | MediaBox | qpdf | /Lang | /Marked | Info /Title | H1 / H2 / P | MCIDs | ParentTree keys |
|---|---|---|---|---|---|---|---|---|---|---|---|
| letter | `audit/gm-018/gm-018-takehome-letter.pdf` | exported artifact bytes (artifacts.path) | 5 | 612x792, 612x792, 612x792, 612x792, 612x792 | ok | `en-US` | True | `Take-home: searing ribs` | 6 / 19 / 74 | 99 | [0, 1, 2, 3, 4] |
| a4 | `audit/gm-018/gm-018-takehome-a4.pdf` | re-render of the same bound pages at A4 with the pack's stored language | 5 | 595x842, 595x842, 595x842, 595x842, 595x842 | ok | `en-US` | True | `Take-home: searing ribs` | 6 / 19 / 74 | 99 | [0, 1, 2, 3, 4] |

`pdftotext -layout` extracted the authored learner sentence and the answer-guide reference answer from both files (selectable text, no image of text).

## Cover line

| Paper | Page-1 `Take-home:` count | First line | Longest line (chars, bound 72) |
|---|---|---|---|
| letter | 1 | `Take-home: searing ribs` | 70 |
| a4 | 1 | `Take-home: searing ribs` | 70 |

## HTML document

- doctype `<!doctype html>`, `lang` from the authored course locale, 5 pages
- page roles in PDF order: cover, parent_guide, learner_page, plate, answer_guide
- no `<script>`, `<link>`, `src=`, `href=`, `@import`, `url()`, iframe, object or embed
- the diagram page keeps its text alternative as an accessible region label
- the HTML is returned as content and never adopted into the artifact store: `artifact.get` remains the only download handle

## Red evidence (captured before the fix)

- `audit/gm-018/red-evidence-three-tests.txt` — the three named tests run against `e1f8e6e` (the GM-005 merge, before any GM-018 source) with this branch's `tests/test_gm_takehome.py` copied in: `PYTHONPATH=. python3 -m unittest tests.test_gm_takehome.TakeHomePrintFollowUpTest.test_takehome_exports_standalone_html tests.test_gm_takehome.TakeHomePrintFollowUpTest.test_takehome_pdf_is_tagged tests.test_gm_takehome.TakeHomePrintFollowUpTest.test_takehome_cover_is_single_line` → `Ran 3 tests` / `FAILED (failures=3)`: the v23 method enum has no `takehome.html`; the PDF carries no `/MarkInfo`; page 1 prints `Take-home: searing - take-home pack` and `Take-home: Section 1: the sear` (two prefixes).
- `audit/gm-018/red-evidence-language.txt` — the review's language defect reproduced before the fix: the new `fr-FR` assertion on the **exported artifact** failed with `AssertionError: 'en' != 'fr-FR'` because `export` built the render pack without the stored `content_json["language"]`. The same command is green after the fix.

## Method

Real `course.create` + `plan.approve` + staged validated `gen_lessons`; `takehome.preview/create/approve/export` through `api.dispatch`; `takehome.html` for the document; the Letter PDF is the exported artifact's own bytes and the A4 PDF a labelled re-render of the same pages at A4 with the pack's stored language; `qpdf --check`, `pdftotext` and an independent pypdf walk of `/StructTreeRoot` and `/ParentTree`.
