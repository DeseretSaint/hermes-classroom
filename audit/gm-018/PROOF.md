# GM-018 take-home print follow-ups proof

- pack: `thp_e513352ccc44400bb1aedae496f7722b` state `exported`
- exported PDF artifact: `art_626299642efa434d818bd60e7083c3c4`
- HTML document: `audit/gm-018/gm-018-takehome.html` (4007 bytes, `sha256:eb22adae3faa342ac7b4a5462ca2cc32f6a792a374177867c05d2b11ef0b899d`)

## Tagged PDF (measured, not assumed)

| Paper | File | Pages | MediaBox | qpdf | /Lang | /Marked | Info /Title | H1 / H2 / P | MCIDs | ParentTree keys |
|---|---|---|---|---|---|---|---|---|---|---|
| letter | `audit/gm-018/gm-018-takehome-letter.pdf` | 5 | 612x792, 612x792, 612x792, 612x792, 612x792 | ok | `en-US` | True | `Take-home: searing ribs` | 6 / 19 / 74 | 99 | [0, 1, 2, 3, 4] |
| a4 | `audit/gm-018/gm-018-takehome-a4.pdf` | 5 | 595x842, 595x842, 595x842, 595x842, 595x842 | ok | `en-US` | True | `Take-home: searing ribs` | 6 / 19 / 74 | 99 | [0, 1, 2, 3, 4] |

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

## Method

Real `course.create` + `plan.approve` + staged validated `gen_lessons`; `takehome.preview/create/approve/export` through `api.dispatch`; `takehome.html` for the document; `takehome.render_pdf` at Letter and A4; `qpdf --check`, `pdftotext` and an independent pypdf walk of `/StructTreeRoot` and `/ParentTree`.
