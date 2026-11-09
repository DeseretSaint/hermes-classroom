# GM-005 take-home pack PDF proof

- pack: `thp_9ee29ce55d1c45f299e88c388b356b6b` state `exported`
- source lesson: `lsn_pln_7c93f9cd59474eb49acea71d369cb97d:v1` hash `sha256:e66d27180bbe70674cf697cb61a76519a53d380acee793197f43794b6143058a`
- exported artifact: `art_502d5e3820d94c3e8b6a26c1d961cb0a` (5568 bytes, application/pdf)
- learner page contains the answer: False
- answer guide contains the answer: True
- diagram authority: deterministic
- world plates: 0

| Paper | File | Pages | MediaBox | Part start pages | Extracted chars |
|---|---|---|---|---|---|
| letter | `audit/gm-005/gm-005-takehome-proof-letter.pdf` | 5 | 612x792, 612x792, 612x792, 612x792, 612x792 | cover@0, parent_guide@1, learner_page@2, plate@3, answer_guide@4 | 2053 |
| a4 | `audit/gm-005/gm-005-takehome-proof-a4.pdf` | 5 | 595x842, 595x842, 595x842, 595x842, 595x842 | cover@0, parent_guide@1, learner_page@2, plate@3, answer_guide@4 | 2053 |

## Learner-audience sheet (answer-free)

| Paper | File | Pages | Answer guide printed | Reference answer printed |
|---|---|---|---|---|
| letter | `audit/gm-005/gm-005-learner-sheet-letter.pdf` | 3 | False | False |
| a4 | `audit/gm-005/gm-005-learner-sheet-a4.pdf` | 3 | False | False |

## Method

Real course.create + plan.approve + staged validated gen_lessons; takehome.preview/create/approve/export through api.dispatch; render_pdf over the stored pages; pypdf text extraction; MediaBox measured per page; each composed page's text compared whitespace-insensitively against its extracted page.
