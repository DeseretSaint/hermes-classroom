# Judge scan — what a cold reader gets in ten seconds

Status: **no independent human reader was available in this run** (headless kanban worker, 2026-11-08).
What follows is a mechanical scan of the exact text a reader sees before scrolling, and the sentence
that answers each question. It is not a substitute for the human test, and it does not claim to be
one; the human row stays open in `docs/STORY-GAPS.md` G8.

## The text under test

The first screen of `README.md` as committed on this branch (heading, one sentence, cover image,
install block) plus the catalog `description` field in `catalog/coursebook.yaml`.

## The three questions

| Question | Answerable in ten seconds? | The sentence that answers it |
| --- | --- | --- |
| What is it? | Yes — first line, before the image | "Coursebook is a Hermes Desktop learning workspace where a lesson is governed state, not chat: one objective at a time, typed checks, bounded grading, exactly one permitted transition per committed answer, and an evidence row you can inspect, export and resume." |
| Who is it for? | Yes — second sentence | "It is for an adult learning a real skill, and for a parent preparing a lesson pack that the parent then teaches: children do not chat with Coursebook." |
| One thing only Coursebook can do | Yes — proof point 1, and the first line's "not chat" contrast | "One answer, one transition" — `tests/test_kernel_transitions.py` (37 tests) asserts one transition per committed answer, duplicate nonce ignored, idempotency replay, and one commit plus one `STALE_REVISION` under two concurrent submits. |

## What the scan found in the old text, and what changed

| Defect in the old first screen | Repair |
| --- | --- |
| Opened with three paragraphs of architecture before saying what the product is for | One sentence first, and the audience in the next sentence |
| No image in the first screen | Cover at the pinned asset path `docs/assets/readme-overview-light.png` (HTTP 200 at `1ba8ec6`) |
| No install command before line 100 | `scripts/install-local.sh --home …` + `hermes gateway restart` under a `## Install locally` heading |
| "No demo has been recorded" as the third paragraph, before any evidence | Moved below the fold into `## Status, 2026-11-08`, with the gate id, the reason and the date |
| "not shippable" as the first thing a judge met at line 231 | Kept, but below the measured record; the first screen states the open gates instead of a verdict |

## What is still weak, honestly

- The cover image predates the Trailhead Home and shows a demonstration course title
  (`docs/STORY-GAPS.md` G5). A judge comparing the listing to a current build will notice.
- The one-sentence pitch is dense: five clauses. Tightening it further trades precision for speed, and
  precision is the product's claim, so it stays.
- The catalog `description` is a disclosure paragraph (egress, seams, storage), not a pitch. A judge
  reading it first learns what the plugin sends where. That ordering is deliberate: it is the honest
  disclosure the operator required, and it belongs in the listing even though it is not marketing.
