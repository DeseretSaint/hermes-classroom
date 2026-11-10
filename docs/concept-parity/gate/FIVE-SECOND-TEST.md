# FIVE-SECOND-TEST — first-screen comprehension protocol

Card: CP-028. Satisfies EXPERIENCE-QUALITY-BAR **Q1** (5 of 5 first-time testers can say what to
press and what happens next within 5 seconds) and supplies the naming half of anchor **A4** in
`RUBRIC-V3.md` §3.

This is a protocol, not a result. GM-016 runs it after the screens land. Do not pre-fill answers.

---

## 1. What is tested, and what is not

- **Tested:** whether a person who has never seen Coursebook can, from one screenshot alone, say
  what the screen is for, which control they would press first, and what that press does.
- **Not tested:** visual taste, copy quality in detail, accessibility (axe/keyboard live in Q9),
  and whether the product is fun. Those are other gates.
- **The testers are fresh agent sessions**, five per screen, each with no repo context. Agent
  sessions are an acceptable proxy for *screen clarity* and are the reproducible version. They are
  **not** Q12 human proof: Q12 still needs a human to complete the primary task end to end, and the
  packet says so.

---

## 2. Materials

1. The route capture from `scripts/cp-capture.mjs` at **1049 light**, state `default`, cut to the
   route box (stamp `crop_mode: "route"`). Pass the PNG only.
2. **No filename, caption, stamp, commit id, ticket id or board** is shown to the tester. Rename the
   file to `screen.png` in a scratch directory before the session so the name cannot leak the screen.
3. A fresh session per tester: a new chat with no system prompt describing Coursebook, no repo
   mounted, no prior turns. The same five names and the same prompt for every screen.
4. The answer key, written **before** any session runs (§5). A key written after the answers is not a
   key.

---

## 3. The exact prompt (copy-paste; do not edit per screen)

```text
You are shown one screenshot of a software screen. Answer from the image only.

1. In one sentence: what is this screen for?
2. Name the one control you would press first.
3. In one sentence: what happens when you press it?
4. Name any mark, seal, badge or illustration on this screen whose meaning you can state plainly.
   If you cannot say what one means, write "none".

Reply in exactly four numbered lines, one sentence each. Do not ask questions. If the screen does
not make something clear, write "unclear" for that line.
```

Attach the image. Do not add "this is Coursebook", do not add the screen name, do not add a
follow-up turn, and do not re-ask with a friendlier prompt. A retry is a new session and counts as a
tester.

---

## 4. How to run one screen (repeat 5×)

1. Copy the capture to `$HERMES_SCRATCH/5s/<screen>/tester-N/screen.png`.
2. Open a fresh session; send the prompt from §3 with only that file attached.
3. Record verbatim: session id, timestamp, the four lines. Do not clean up the wording.
4. If the tester asks a question or asks for more context, record `asked-for-context` and score the
   session as a fail for Q1 — a screen that needs a question has not answered it.
5. Stop at five sessions per screen. A sixth session is only allowed if one of the five produced no
   answer at all (crash, empty reply), and the reason is recorded.

Screens to run: `home.v3`, `discover.v3`, `classroom.v3`, `course-home.v3`, `lab.v3`. The lab is
scored only on Q1-line 2 (it is a read-only sheet: "Back" or "nothing" is correct) and on A4; Q2's
one-primary rule is N/A there by SPEC §3.10.

---

## 5. Answer key (fill from SPEC before sessions; one row per screen)

| Screen | L1 expected (screen's question, SPEC §5) | L2 expected first press (SPEC §3.10) | L3 expected outcome |
|---|---|---|---|
| `home.v3` | which course do I open next, and how do I start a new one | `Start a course` (`home.primary`) | opens the new-course wizard, first step asks the goal |
| `discover.v3` | which pack can I learn from, and what is inside it | `Preview this pack` (`discover.feature.primary`) | opens the pack preview/provenance for the featured pack |
| `classroom.v3` | what is this line, and can I answer the check | `Check answer` (`classroom.check.primary`) | submits the answer and returns a verdict |
| `course-home.v3` | where am I in this course, and what is the next section | the backend's `next_step.label` plate (`Continue <section>`) | opens the next section |
| `lab.v3` | what are the product's parts, and what may a screen use | `Back` (documented N/A for Q2) | returns to the previous screen |

L4 key (A4 subject mark), per screen where one exists: `course-home.v3` — the course's own subject
plate; `classroom.v3` — the deck-authored mark, if any; `lab.v3` — the pose/medallion names as
labels, not as seals; `home.v3` / `discover.v3` — expected answer is often `none` (a fox is not a
mark with a meaning; "study companion" is the only acceptable naming).

---

## 6. Scoring (binary, no partial credit)

| Question | Correct when | Fail when |
|---|---|---|
| L1 | the sentence matches the screen's question in §5 without naming a different job | describes the chrome, names another screen, or `unclear` |
| L2 | names the control that is the screen's one primary (§3.10) by its own visible label | names a different control, names two controls, or says "the button" without which |
| L3 | names the documented outcome, not a generic "opens it" | wrong destination, invented outcome, `unclear` |
| L4 | states a meaning the product actually assigns, or correctly says `none` where there is no mark | invents meaning for a decorative mark (counts as a Truth finding, not just a miss), or names a mark that does not exist |

- **Q1 passes** only when **5 of 5** sessions are correct on L1 **and** L2 **and** L3. One session
  that names a wrong primary fails Q1 for that screen; the screen goes back with the verbatim answer.
- **A4 passes** when ≥ **4 of 5** sessions can state the mark's meaning (or all five answer `none`
  on a screen that has no mark, which is the correct answer and not a miss).
- A wrong primary is a **focal-hierarchy defect** (RUBRIC dimension 1), not a tester error. Do not
  coach the tester and re-run.

---

## 7. Result record (one block per screen)

```
Screen: ____________  matrix id: __________  Capture: ____________________  Stamp sha: __________
Run by: ____________  Date: __________  Sessions: 5  Fresh sessions (no repo context): YES / NO
Prompt used: FIVE-SECOND-TEST.md §3 verbatim: YES / NO

Tester  Session id / time                     L1  L2  L3  L4      Verbatim L2
1       _______________________________       P/F P/F P/F P/F/none  ______________________
2       _______________________________       P/F P/F P/F P/F/none  ______________________
3       _______________________________       P/F P/F P/F P/F/none  ______________________
4       _______________________________       P/F P/F P/F P/F/none  ______________________
5       _______________________________       P/F P/F P/F P/F/none  ______________________

Q1 verdict (5/5 on L1+L2+L3): PASS / FAIL    A4 naming (>=4/5): PASS / FAIL
Wrong primary named: ______________________________  (dimension 1 finding if any)
Notes / tester questions asked: ____________________________________________________
```

Store the five verbatim transcripts beside the record; a result table without transcripts is not
reproducible.

---

## 8. Honest limits

- Five agent sessions are a reproducibility device and a clarity proxy. They do not replace Q12's
  human walkthrough, and they do not measure fun or trust.
- The test measures the **first screen** per screen. It does not test a flow; the flow gates are Q3,
  Q6 and Q12.
- A pass here does not raise any rubric score by itself. It satisfies Q1 and one half of A4.
- If a screenshot cannot be shown without leaking the screen name (e.g. the title contains it), that
  is expected — the tester is allowed to read the screen; what is forbidden is the *file name* and
  any text the harness adds.
