# GM-005 take-home pack PDF proof

- pack: `thp_9e1f23b21b32466abb1e3785b9d0a258` state `exported`
- source lesson: `lsn_pln_0c92454587064ba8baefb4cd53971700:v1` hash `sha256:b6e0a32579313f761b5886b079015300bd132001b19d3af29c9b5cb4b818020f`
- exported artifact: `art_04978eacf7a54e5e94ffc0e6e0bf7a97` (5622 bytes, application/pdf)
- learner page contains the answer: False
- answer guide contains the answer: True
- diagram authority: deterministic
- world plates: 0

| Paper | File | Pages | MediaBox | Part start pages | Extracted chars |
|---|---|---|---|---|---|
| letter | `audit/gm-005/gm-005-takehome-proof-letter.pdf` | 5 | 612x792, 612x792, 612x792, 612x792, 612x792 | cover@0, parent_guide@1, learner_page@2, diagram@3, answer_guide@4 | 2053 |
| a4 | `audit/gm-005/gm-005-takehome-proof-a4.pdf` | 5 | 595x842, 595x842, 595x842, 595x842, 595x842 | cover@0, parent_guide@1, learner_page@2, diagram@3, answer_guide@4 | 2053 |

## Learner-audience sheet (answer-free)

| Paper | File | Pages | Answer guide printed | Reference answer printed |
|---|---|---|---|---|
| letter | `audit/gm-005/gm-005-learner-sheet-letter.pdf` | 3 | False | False |
| a4 | `audit/gm-005/gm-005-learner-sheet-a4.pdf` | 3 | False | False |

## Long title (200 characters) — no clipping

| Paper | File | Page width | Printable right | Widest word xMax |
|---|---|---|---|---|
| letter | `audit/gm-005/gm-005-long-title-letter.pdf` | 612 pt | 556 pt | 463.232 pt |
| a4 | `audit/gm-005/gm-005-long-title-a4.pdf` | 595 pt | 539 pt | 463.232 pt |

## Non-ASCII text

- `audit/gm-005/gm-005-accented-proof-letter.pdf` (letter): café True, naïf True, em dash True
- `audit/gm-005/gm-005-accented-proof-a4.pdf` (a4): café True, naïf True, em dash True
- Japanese preview exact: True; export refusal `POLICY_VIOLATION` / `print_font_cannot_render_text` (characters 'こちにはん日本語'); artifact written: False; pack left `approved` with no artifact.

## Method

Real course.create + plan.approve + staged validated gen_lessons; takehome.preview/create/approve/export through api.dispatch; render_pdf over the stored pages; pypdf text extraction; MediaBox measured per page; each composed page's text compared whitespace-insensitively (NFC) against its extracted page; a 200-character title measured with pdftotext -bbox against the printable right edge; accented WinAnsi text extracted exactly; a Japanese lesson previewed exactly and refused at export as POLICY_VIOLATION/print_font_cannot_render_text with no artifact written.
