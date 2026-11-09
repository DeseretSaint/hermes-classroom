# GM print pack spec and proof

Card: GM-013. Design authority for GM-005 (take-home pack backend), GM-006 (Parent Studio surfaces),
GM-008 (homework sheet) and GM-014 (print content fixtures and print proof).

A take-home pack is a **rendered artifact of a validated lesson**, not a second course. It reuses the
source lesson's exact text and check content, binds to `source_course_id`, `source_objective_id`,
`source_lesson_version` and `content_hash`, and never regenerates the lesson to print it.

Proof artifacts in this card:
- `docs/gm-visual/print/pack-specimen.html` — the print stylesheet and page anatomy, as source.
- `docs/gm-visual/print/pack-specimen-a4.pdf`, `…-letter.pdf` — built by
  `scripts/build_gm_print_proof.py` through headless Chromium.
- `docs/gm-visual/print/page-{1..5}.png` — A4 renders at 110 dpi for review.
- `docs/gm-visual/print/proof.json` — page counts, page boxes, extracted-text sentinel locations,
  hashes.
- `docs/gm-visual/print/CAPTION-SHEET.md` — the caption and provenance wording a pack carries.

The specimen is **labelled as a specimen** on page 1 and uses `⟨…⟩` slot markers where real lesson
content goes. It proves page anatomy, margin, low-ink and answer-key separation. It is not a lesson,
and no value in it is a course fact.

---

## 1. Page grammar

Five page roles, in this order. A pack may omit the optional pages, never reorder them.

| # | Page | Audience | Contains | Never contains |
|---|---|---|---|---|
| 1 | **Parent guide** | parent/operator | objective, level, materials, preparation, the script in order, questions to ask, what to notice, one success criterion | answer key, child persona, XP/level/streak, a grade |
| 2 | **Learner page** | learner, at the table | one activity, one target, at most three steps, one success criterion, optional caption for one plate | answer key, expected responses, grading, a score, a fake completion claim |
| 3 | **Answer guide** | parent only | expected responses, accepted alternatives, common errors, next step | learner-facing reuse; it is a separate page **and** a separate file in export |
| 4 | **Sources and provenance** | parent, and the record | per source: title, publisher, URL, publication date, access date, support label (`supports` / `partial` / `contradicts` / `unverified`); per plate: provider or generator, prompt/style hash, generation time, licence, `role = orientation` | unrecorded links, invented citations, a support claim the ledger does not hold |
| 5 | **Visual caption sheet** (optional) | parent | one plate at ≤90×60 mm, its caption, its text equivalent | any plate carrying a procedure, measurement, torque, dosage, wiring value or answer |

Page 3 carries a 24 pt top-right label `PARENT ONLY` and a 1 pt tear rule under the header. In the
PDF export it is its own file: `pack.pdf` (pages 1–2, 4–5) and `answer-guide.pdf` (page 3).

**No answer key on a learner page** is a hard rule, not a layout preference. It is enforced by a
sentinelled text check: the answer guide carries `⟨answer-key⟩`; the learner page and the exported
learner PDF must not contain that token or the expected-response strings it indexes (§6).

---

## 2. Page box, margins and grid

| Property | A4 | US Letter |
|---|---|---|
| Page | 210 × 297 mm | 8.5 × 11 in |
| Margin, all sides | 18 mm | 0.70 in (17.8 mm) |
| Live area | 174 × 261 mm | 7.10 × 9.60 in |
| Content box | 174 × 259 mm (2 mm bottom slack so a page box never lands on the printable edge) | 7.10 × 9.52 in (0.08 in slack) |
| Header baseline | 12 mm from trim | 0.47 in |
| Footer baseline | 12 mm from trim | 0.47 in |
| Text column | live width, max 96 mm for prose (≈ 72 characters at 10.5 pt) | live width, max 3.78 in |
| Column grid | one column; a 12 mm side note column may sit at the right on pages 1 and 4 only | same |
| Minimum hairline | 0.25 pt | 0.25 pt |
| Bleed | none — no element bleeds | none |

Margins are identical in value, not proportion, so a pack does not reflow between paper sizes. Page
breaks are explicit (`break-after: page`) at page-role boundaries; a role never splits across pages
unless it exceeds one page, in which case the continuation repeats the header and adds `(continued)`.

---

## 3. Print type scale

Paper has no root font size, so the six UI steps are mapped once. **This is a mapping of the same six
roles, not a seventh type system**: any new role must reuse a row.

| Role (UI step) | Size | Leading | Weight | Use |
|---|---|---|---|---|
| Display (`display`) | 20 pt | 22 pt | 600 | pack title on page 1 only |
| Heading (`heading`) | 15 pt | 18 pt | 600 | page title, section title |
| Lead (`lead`) | 12 pt | 16 pt | 400/600 | objective, success criterion, next-stop line |
| Body (`body`) | 10.5 pt | 15.5 pt | 400 | prose, scripts, steps |
| Meta (`meta`) | 9 pt | 12 pt | 400/600 | field rows, source rows, dates |
| Caption (`caption`) | 8 pt | 10.5 pt | 400 | captions, provenance, axis-free labels |

All serif for prose, sans for field rows and captions — the same two OS stacks. Black on white only;
no reversed type, no coloured body text.

---

## 4. Low-ink rules

1. **White ground.** `paper` is not printed as a flood: the sheet is white, and the parchment tone is
   a screen identity, not an ink cost.
2. **Ink text, one hue.** Body and headings are black. At most one accent is printed, at ≤10% of the
   page area, as a 2 pt rule or a 1 pt box edge.
3. **No full-bleed plate.** A plate is ≤90 × 60 mm, framed by a 0.5 pt rule, and is omitted entirely
   in `low_ink = true`, which keeps its caption and text equivalent.
4. **No solid dark fills.** A filled block larger than 30 × 30 mm is forbidden.
5. **One rule weight per intent**: 0.5 pt structure, 0.25 pt hairline, 2 pt page accent only.
6. **No background images, no gradients, no shadows, no colour-only meaning.** Every state is a word
   plus, at most, a 1 pt box.
7. **Page 2 is designed to be the cheapest page**: no image by default, one rule, one activity.

A pack that prints a full-page illustration is out of spec even if it is beautiful.

---

## 5. Page anatomy

### Page 1 — Parent guide

```
┌ 18mm ───────────────────────────────────────────────────────────── 18mm ┐
│ ⟨pack title⟩  ·  display 20pt                          Take-home pack   │  12mm
│ ─────────────────────────────────────────────── 1pt rule ────────────── │
│ SOURCE  ⟨course title⟩ · ⟨section⟩ · lesson v⟨n⟩                       │  9pt meta
│                                                                        │
│ Objective            ⟨the source lesson's objective, verbatim⟩         │  12pt lead
│ Level and audience   ⟨level⟩ · adult operator                          │
│ Materials            ⟨list, or "none"⟩                                  │
│ Preparation          ⟨what to set up, 1-3 lines⟩                       │
│                                                                        │
│ SCRIPT                                   1. ⟨step⟩  2. ⟨step⟩  3. …    │  10.5pt body
│ ASK                ⟨question⟩  ⟨question⟩                              │
│ WHAT TO NOTICE     ⟨observable behaviour⟩                              │
│ Success criterion  ⟨one observable sentence⟩                           │  12pt lead
│                                                                        │
│ Answers: see the separate answer guide.                                │  8pt caption
└────────────────────────────────────────────────────────────────────────┘
```

### Page 2 — Learner page

```
┌ 18mm ───────────────────────────────────────────────────────────── 18mm ┐
│ ⟨activity title⟩  ·  heading 15pt                                      │
│ ONE THING TO DO TODAY                                                  │  8pt caption
│ ⟨target: the exact word, phrase, concept or action⟩                     │ 12pt lead
│                                                                        │
│ 1 ⟨step⟩   2 ⟨step⟩   3 ⟨step⟩                                          │ 10.5pt body
│                                                                        │
│ You have done it when: ⟨one observable sentence⟩                        │ 12pt lead
│ ───────────────────────────── 0.5pt rule ─────────────────────────────  │
│ ⟨optional plate, ≤90×60mm⟩  ⟨caption, 8pt⟩  ⟨text equivalent, 8pt⟩      │
└────────────────────────────────────────────────────────────────────────┘
```

No answer, no expected response, no score line, no checkbox that claims a grade. A completion mark,
if printed, says `Done (self-reported)`.

### Page 3 — Answer guide (parent only)

```
│ PARENT ONLY                                              (24pt label)  │
│ ⟨activity title⟩ — answer guide · heading 15pt                          │
│ ─────────────────────────── 1pt tear rule ───────────────────────────  │
│ Expected response      ⟨answer-key⟩ ⟨verbatim expected response⟩        │
│ Accepted alternatives  ⟨list from the check's accepted_alternatives⟩    │
│ Common errors          ⟨error⟩ → ⟨what to say⟩                          │
│ Next step              ⟨the next objective or a retrieval check⟩        │
```

### Page 4 — Sources and provenance

One row per source and per plate, `9 pt meta`, with the four support labels used verbatim. A source
with no recorded access date is printed `access date not recorded` — never a guess. A plate row
reads `generated plate · ⟨provider or generator⟩ · ⟨prompt/style hash⟩ · role: orientation · not a
diagram of the course`.

### Page 5 — Visual caption sheet (optional)

One plate, one caption, one text equivalent, one provenance line. The caption wording is fixed in
`docs/gm-visual/print/CAPTION-SHEET.md`; it never says `verified`, `accurate`, `official` or
`manual`.

---

## 6. The proof path

```
python3 scripts/build_gm_print_proof.py
  ├─ writes docs/gm-visual/print/pack-specimen.html          (print stylesheet, @page rules)
  ├─ chromium --headless --print-to-pdf=A4   → pack-specimen-a4.pdf
  ├─ chromium --headless --print-to-pdf=Letter→ pack-specimen-letter.pdf
  ├─ pdftoppm -r 110                          → page-1..5.png
  ├─ pdfinfo                                  → page count + page box (asserted)
  ├─ pdftotext -f N -l N                      → per-page text (sentinel locations)
  └─ writes proof.json                        → sizes, counts, sentinels, sha256
```

`tests/test_gm_print_spec.py` re-runs the checkable half without a browser: it asserts the PDF exists,
has 5 pages, is A4 and Letter at the named boxes, that `⟨answer-key⟩` occurs only on page 3, that the
learner page contains no expected-response string, that every page carries a caption or a header, and
that the print CSS declares the A4 and Letter margins from §2.

**What the proof does not claim.** Chromium does not emit a tagged PDF here, so this pack does not
claim PDF/UA conformance or a certified reading order; it claims selectable text, real margins,
explicit page roles, non-colour-only states and a working answer-key separation. A tag tree is a
GM-014 task with its own proof, not an assumption in this spec.

---

## 7. Refusals

- A learner page with an answer, an expected response, a score or a grade.
- A pack that regenerates lesson prose to fill a page.
- Any plate in a procedure, measurement or safety role.
- A number in art: temperature, time, torque, clearance, dosage, hydration, ratio.
- A fake completion: `completed` without a `self_reported` or `parent_reported` record.
- Colour-only meaning, reversed type, a solid dark block, a full-bleed image.
- A source row without a URL and access date, or with a support label the ledger does not hold.
- Exporting without a preview of the actual pages and an explicit approval of those pages.
