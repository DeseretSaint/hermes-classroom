# Wave 2 — what happens next, and why

Written against `origin/master` = `24a4d73d` (gate 4/4 on 4,573 files, full suite 4,172 tests /
0 failures / 13 skipped). This document is the plan, the adversarial review of that plan, and the
triage of every card the freeze left parked. Cards are created from it, not instead of it.

## What already shipped, so it is not replanned

Slice 1 and 2 of `docs/CREATE-EXPERIENCE-SPEC.md`: the end-goal question composed into the brief,
the plan-time capability derived from the performance requirement, a typed exit performance that must
end in a real performance objective, zero-coverage refusal, the goal reaching the lesson author, prose
rendered in the default lesson modes, real wrong-answer feedback, next-section navigation, need-based
media demand, language pronunciation audio, a built textless illustration prompt, and role geometry.

## What is actually left

The queue in the spec has 42 items; 14 landed. What remains sorts into four buckets, and the sort is
the plan:

1. **The harness still loses work** (items 18-24). A lesson can be cut off mid-answer and kill a unit
   that already paid for earlier sections; a validator is asked to judge ten bare criterion names;
   an honest `unknown` is a rejection; the author and its validator can see different fitted ledgers.
2. **The first ten minutes are still dishonest** (items 2-6, 35). The plan screen says "being written"
   with no stage or clock; a learner can only approve or abandon; nobody sees what a course will cost
   before pressing Create; the tutor's "Ask" pill never renders because the route does not pass its
   handler.
3. **The lesson surface stops one step short** (items 37, 41). Figures are capped at 380px and sit
   below the prose; a finished lesson cannot be printed.
4. **Two deferrals and a hole**: the label overlay that would let generated figures carry readable
   text drawn by the UI (item 28b), the required sourced reference that always degrades to text
   (item 31), and a recorded audit packet skipped by name because its full-course scenario predates
   the procedure rule.

## Triage of the parked board

Thirteen cards were parked at the submission freeze. A park reason ages; the acceptance does not, so
each was re-read against the current tree.

| Card | Verdict | Why |
| --- | --- | --- |
| `t_09b46fad` pack re-export ships pre-edit bytes | **keep** | `pack.export` still rebuilds from the installed manifest; nothing in slice 1 or 2 touches it |
| `t_e22f072e` four courses wear the same room | **keep, low** | asset/composition work; no slice 1/2 change to covers |
| `t_7f0ddb44` 96x96 vignette painted with `cover` | **keep** | measured on `e0930a31`; `desktop/src/76-v3-scope.js` is untouched since |
| `t_ff8f9ebc` tag plate squashed to 164x88 | **keep, low** | same file, composition defect, cosmetic |
| `t_23009397` desktop contract tests miss the share route | **keep, assign** | no assignee, so it could never dispatch; the gap is real |
| `t_4d9e6724` independence is a model-name compare | **keep** | integrity defect: two aliases of one model read as two opinions |
| `t_f3b7be3e` a pack can assert its own trust label | **keep** | `packs.trust_labels` still reads author-supplied fields |
| `t_3d735846` validation pool threads lose profile scope | **keep** | infrastructure defect with a measured log |
| `t_3e8b07ba` isolated backend cannot read the search key | **keep** | blocks live plan evidence for every later card |
| `t_1c668a8d` default deadlines below real latency | **keep** | measured 204 s against a 180 s default |
| `t_b28115be` "Session length could not be read" | **re-measure, then keep** | the string is still the error state of the course plate (`desktop/src/30-home.js:1389`); whether it still fails needs a live read, not a rewrite |
| `t_c9df995c` five learner doors stop one control short (blocked) | **fold into W2-3** | two of its five doors — review.action and the tutor — are the same work as the trust pass; the card's block must be read before it is unblocked |
| `t_d2cbff9a` check screen repeats the prompt, graded line reads as a fragment | **narrow** | the fragment half is fixed: `70-learning.js` now composes the choice and suppresses grader strings. What remains is the triple prompt; the body must say so or the worker will re-fix shipped code |

## The wave

Seven cards. Every one is assigned, every one names its acceptance, and the parent edges are in the
same create call so none of them lands runnable by accident.

| Card | Lane | Covers | Depends on |
| --- | --- | --- | --- |
| **W2-1** The validator is told what each criterion means, and an honest unknown is recorded not refused (`t_26869e65`) | quill | 18, 19 | — |
| **W2-2** A truncated lesson is re-asked, and attempt 2 repairs the draft instead of rewriting it (`t_38275890`) | quill | 20, 21, 22, 23 | W2-1 (same file) |
| **W2-3** The plan screen tells the truth: stage, clock, cost; and the plan can be adjusted (`t_167495f6`) | cinder | 3, 4, 5 | — |
| **W2-4** The tutor is beside the check, and the hint is a hint (`t_5c6bf0b0`) | vellum | 35 | W2-3 (same surfaces) |
| **W2-5** A figure is big enough to teach, and a finished lesson prints (`t_00725aad`) | vellum | 37, 41 | W2-4 |
| **W2-6** Labels are drawn over a label-free figure (the overlay half of 28) (`t_468f861a`) | easel | 28b | — |
| **W2-7** A required sourced reference is delivered or flagged (`t_0a47320b`) | sable | 31 | — |
| **W2-8** Re-record the full-course audit packet (`t_c5caa0f1`) | cbqa | the skipped module | — |

Two more actions are not cards: `t_23009397` gets an assignee in this pass, and `t_d2cbff9a` is
narrowed to the defect that is still real. `t_c9df995c` is read before it is unblocked — a block
carries a ruling nobody has made yet, and unblocking without answering it produces the same block
again.

## The adversarial review

The plan above is the second draft. These are the objections that changed it.

**1. "Slice 3 first" was wrong as a wave order.** The harness defects cost money and lost lessons,
but they are invisible until a lesson is long enough to be cut off. The plan screen is wrong for
every learner on every course. W2-3 and W2-4 take priority 5 and 10; the harness cards take 20 and 25.
*Resolution: trust pass first, harness second, and both run concurrently because they touch disjoint
files.*

**2. Four cards on two lanes is token contention.** `quill` owning W2-1 and W2-2 sequentially is one
worker; `vellum` owning W2-4 and W2-5 is another. The board's cap is `max_in_progress`, but the real
limit is one worker per profile. *Resolution: W2-2 is parented to W2-1, W2-5 to W2-4, so each lane
runs one card at a time rather than two half-finished ones.*

**3. Every generation card edits `coursebook/generation.py`.** W2-1 and W2-2 are the same file, and so
is the media lane's prompt contract. *Resolution: the parent edge is the file lock. W2-7 touches
`media.py` and `artifacts.py` only and is explicitly forbidden from `generation.py` except the one
media-spec line that already landed.*

**4. "Adjust the plan" is not a UI change.** `plan.edit` and `plan.replan` exist on the backend, but
the learner surface hides them behind `!learner` (`95-studio.js:5738`, `:5762`). Exposing them
without an undo or a version note would let a learner rewrite an approved plan silently. *Resolution:
W2-3's acceptance requires the edit path to leave a plan revision and to keep Approve as the single
primary; a bare toggle is not acceptance.*

**5. The tutor card could re-do work that is already done.** Slice 1 fixed next-section navigation
and wrong-answer copy. A worker told "make the tutor work and fix next" would re-open shipped code.
*Resolution: W2-4's body names what shipped at `24a4d73d` and restricts the card to the `onAskTutor`
handler, the hint request, and a regression test for the shipped behaviour.*

**6. Overlay labels are a schema change wearing a UI costume.** Item 28b needs a `labels` field on the
media block, a renderer that positions them, and a rule that a label may not restate the answer.
Doing it as "draw some labels" would ship unstyled absolute positioning. *Resolution: W2-6 owns the
lesson-document field, the renderer geometry and the answer-leak scan for labels; the image prompt
stays textless, so the two halves cannot drift.*

**7. The sourced-reference card is the most likely to stall.** `media.py:594` raises for every
`sourced_technical` spec, and the honest paths are "adopt a permissioned asset" or "fail the stage
with a named state". The first needs a source policy nobody has written. *Resolution: W2-7 may land
the named `media_incomplete` state alone, and is forbidden from inventing a permission model; if it
chooses adoption it must cite an existing permission record.*

**8. Re-recording the audit packet is the least valuable card and the most tempting to skip.** It
proves a recorded replay, not the product. But a skipped module is a hole in the suite, and the card
is the only thing that closes it. *Resolution: keep it, priority 50, one lane (`cbqa`), and its
acceptance is "the module runs and passes", not "new scenarios".*

**9. Unpausing the supervisor is itself a risk.** The freeze paused it; the night watch promotes but
never dispatches. Unpausing with seven ready cards and a stale prompt could dispatch a card whose
premise moved. *Resolution: unpause only after every card body names the commit it is measured
against, and after the two stale cards are rewritten. The night watch keeps its promote-only role.*

**10. "Create cards, the workers are idle" must not become "dispatch eight cards now."** The board's
own skill says a CLI dispatch from an interactive session can claim under a transient lock and
auto-block. *Resolution: cards are created and assigned; the gateway's scheduled supervisor does the
dispatching on its tick. No `dispatch` from this session.*

## Non-goals for this wave

- No new visual direction, no new screens beyond the two the trust pass touches.
- **One** contract version bump, and only item 28b's: `cb.rpc` v27 adds the optional
  `lesson_document_media.labels` array so a textless figure can carry readable annotations drawn by
  the UI. Everything else in this wave fits the v26 surface, and `course.create.outcome` is not
  folded in — an accepted request field no handler reads is a silent drop. It takes the next bump.
- No rewrite of the recorded harness scenarios beyond re-recording what exists.
- No image-model pin (item 29) — that is a host setting, not plugin code, and it stays an owner
  action until the fork takes a `model` parameter.

## Order of work, and who does what

1. This session: write the cards, narrow the two stale ones, assign the orphan, unpause the
   supervisor, verify a run row exists.
2. `cinder` starts W2-3 (trust pass) first because it needs no backend change and every course
   benefits. `quill` starts W2-1 in parallel on the backend.
3. `easel` and `sable` take the two media cards; `vellum` follows W2-3 with W2-4.
4. `cbqa` takes the packet last.
5. This session verifies each landing: rebuild `desktop/plugin.js`, regenerate proof pages and the
   M4 audit, run the focused modules, then the full suite, then move the catalog pin and PR body.
