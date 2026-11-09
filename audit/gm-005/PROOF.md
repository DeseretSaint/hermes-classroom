# GM-005 take-home pack PDF proof

- pack: `thp_ae1ec24285d84058802c50e5bbca1086` state `exported`
- source lesson: `lsn_pln_fcb2e9dd22894f51b344548a84135fb1:v1` hash `sha256:5e5bd1647d35b69e62c8f9cead1aa221af4f8787cc6f7c924e83bc0f9696a549`
- exported artifact: `art_cfbab1b829524264ac803c6b05118c5a` (4111 bytes, application/pdf)
- learner page contains the answer: False
- answer guide contains the answer: True
- diagram authority: deterministic
- world plates: 0

| Paper | File | Pages | MediaBox | Part start pages | Extracted chars |
|---|---|---|---|---|---|
| letter | `audit/gm-005/gm-005-takehome-proof-letter.pdf` | 4 | 612x792, 612x792, 612x792, 612x792 | cover@0, parent_guide@1, learner_page@2, answer_guide@3 | 1982 |
| a4 | `audit/gm-005/gm-005-takehome-proof-a4.pdf` | 4 | 595x842, 595x842, 595x842, 595x842 | cover@0, parent_guide@1, learner_page@2, answer_guide@3 | 1982 |

## Method

Real course.create + plan.approve + staged validated gen_lessons; takehome.preview/create/approve/export through api.dispatch; render_pdf over the stored pages; pypdf text extraction; MediaBox measured per page; each composed page's text compared whitespace-insensitively against its extracted page.
