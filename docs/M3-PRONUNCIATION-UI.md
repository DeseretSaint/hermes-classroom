# M3-U1 — Pronunciation Studio, in the lesson

Card `t_873b4137`. Branch `wt/m3-pronunciation-ui` (base `4a33f2d`; merged `wt/m2-field-notes`
at `3634c9b`, `wt/m3-pronunciation-backend` was already an ancestor). Nothing here is merged to
`master`, pushed, tagged or published.

## What the learner sees

The studio is a child of a **lesson block**, not a second chat and not a new route. A block that
carries a narration media child (authored transcript + reference audio artifact) seats one studio;
a block without one gets none, because the target phrase and its reference both come from that
authored narration — neither is invented here.

- **Listen** — the lesson's own narration artifact, loaded through the one media route
  (`/media/{artifact_id}`) that `MediaSegment` already uses. The loader was extracted into
  `useArtifactPreview` and shared, so there is one audio source in the module and nothing
  autoplays. A `Listen` button calls `play()` on that same element; native controls stay as the
  fallback.
- **Record** — an explicit press opens the microphone, `MediaRecorder` captures one take, and the
  UI auto-stops at 30 s (the backend's bound). **Stop** ends capture. The take is deleted after
  comparison; Coursebook retains no audio.
- **Compare** — `POST /api/plugins/coursebook/pronunciation/attempt` with the bounded data URL, the
  block's transcript as `target`, the enrollment locale, `expected_revision` and one
  `idempotency_key`. The result is rendered as it came back: verdict, per-unit comparison
  (`expected` / `heard` / matched), the recogniser's own mean `confidence`, the matched count, the
  provider/model provenance, and the `model_assessed` label.
- **Delete take and result** clears the surface. **Save result to notebook** writes one
  `personal_note` entry with block/artifact/source provenance through `notebook.source_ref`.
- Disclosure names the configured recognition provider before the first take
  (`coursebook_local_whisper`, local-only, model name when reported) and says the take is deleted
  after comparison.

## Honesty rules the component is built around

| Rule | Where it lives |
|---|---|
| No recogniser → "Practice only, not graded" and **Record disabled** | `pronunciationAvailabilityCopy` + `canRecord` |
| Status probe fails → same practice-only copy, naming the read failure | same |
| `status: empty` → "did not catch any speech", no evidence | result branch |
| `status: unavailable` → typed reason mapped to plain copy, no verdict | `PRONUNCIATION_REASON_COPY` |
| Contract refusal → `error.code` + "No evidence was recorded." | error branch |
| Transport failure → `HOST_UNAVAILABLE`, never a score | error branch |
| The Desktop never reads `word_accuracy`/`phoneme_accuracy` or computes a percentage of its own | `tests/test_desktop_pronunciation.py::test_the_desktop_never_recomputes_accuracy_and_never_autoplays`; the only percent on screen is the backend's `confidence`, and `pronPercent` refuses anything that is not a real 0..1 number |
| No autoplay | `preload="metadata"`, no `autoplay` attribute; asserted in the same test and in the rendered DOM |
| Keyboard + reduced motion | every action is an SDK `Button`; `aria-live` status on the disclosure, timer and result; `useCbMotion` writes `data-cb-pronunciation-motion` |

The studio appears in Textbook, Guided and Field Quest at the same block id. Role-play stays in the
existing bound lesson chat — no chat, composer or transcript was rebuilt.

## Evidence

- `tests/test_desktop_pronunciation.py` — 15 tests. Placement renders the real module through
  `react-dom/server`; the loop mounts the exported component in **jsdom** with a stub
  `@hermes/plugin-sdk`, a fake `MediaRecorder`/`FileReader` and a fake `ctx.rest`, then clicks
  Record → Stop → Save → Delete and asserts the exact POST body (target, locale,
  `expected_revision`, `attempt_nonce`, data URL, idempotency key) and every rendered state.
- `audit/visual/m3-pronunciation/` — 14 frames from `scripts/m3p-frames.py` (the component's own
  states) + `scripts/m2fn-shot.mjs`: available, recording, assessed, saved, unavailable, empty
  speech, refusal, no recorder, 460 px, 200 % text, reduced motion, and the studio inside Textbook
  (1280) and Guided (dark, 460). `scripts/m2fn-shot.mjs` measured `overflow=false` on all 14.
  `evidence.json` records each state's buttons and calls.
- `audit/visual/m3-pronunciation/live/` — `scripts/m3p-shot.mjs` against the isolated window with
  **this** `plugin.js` materialised: `#/coursebook` mounts, the Field Desk paints, the sidebar nav
  is present, zero console errors, `scrollWidth == innerWidth` at both widths.

## The live gap, stated plainly

The studio cannot be walked live on this machine right now, and the reason is data, not code:

1. No section in the isolated home has a narration media child (`gen_lessons.media_json` has zero
   narration entries; all 13 artifacts are pack zip/pdf). Without one there is no model phrase,
   so no block seats the studio. Generating one is provider TTS spend, which this card does not
   authorise.
2. The window's isolated backend is an older build (wire v7, no `/pronunciation/*` routes), so the
   status probe is not demonstrated live here either. Standing up a v9 backend for this branch is
   a separate rig action.

The renderer states are therefore proven by the component-driven frames plus the jsdom
interaction tests, not by a live capture. No seeded fixture was used to manufacture a live claim.

## Next action for the live proof

Start the backend from this branch (`scripts/cb013-live-backend.sh` with a fresh isolated home),
then either author a section whose media carries `role: "narration"` (with the operator's TTS
approval) or run the same sequence in Parent Studio's media step. Until then the studio is inert
on every existing section, by design.
