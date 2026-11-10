# CP-033 — launch film brief

Status: brief agreed for build; **no frame of final video exists**. This card ships the brief, the
script, the flat animatic and the re-recordable driver. It does not record, post or claim parity.

## 1. The event rules this cut is built to

Taken from the event's own preflight checklist, not from announcement prose:

| Rule | Value | Where it bites in this cut |
|---|---|---|
| Runtime | **strictly under 90 s** | target 75.00 s; the animatic is already 75.00 s so there is no slack to discover late |
| Content | **the actual plugin working** | every proof beat is a live surface; reference plates appear only in this animatic, never in the final take |
| Publication | **posted on X tagging @NousResearch** | out of scope here — a separate owner gate (`docs/SUBMISSION.md` §0) |
| Resolution / captions | 1080p, burned-in, sound-off legible | 1920×1080, one message per card |

## 2. Audience

Primary: the judges of the Hermes plugin hackathon — developers who know what an agent loop is and
will notice a fake screen within a second.

Secondary: people scrolling X with sound off. They see the middle third of the video before they
read anything.

Tertiary: the owner's existing audience of Hermes Desktop users, who will install something only if
the video does not promise what the product refuses to do.

## 3. The one claim

> **A chat answers. Coursebook makes the next step depend on what you did.**

It is the same claim the README makes in its first sentence — *"a lesson is governed state, not
chat"* — restated for someone who has never seen the product. Every beat either shows that sentence
happening or is cut. Nothing in the film claims learning outcomes; the claim is about where the
product puts authority over the next state.

## 4. Register

**Crafted film.** Not a raw screen recording (that reads as a tutorial and would lose the feed), not
a manifesto (there is no room in 75 seconds to argue and prove). Crafted means: one message per
card, hard cuts on a beat grid, the product's own type and palette, real captures inside.

The captures stay real. Craft lives in the cut, the captions and the sound, never in the pixels of
the UI. Animated UI is not generated: if a state cannot be captured, the beat is cut.

## 5. Runtime and grid

| Parameter | Value |
|---|---|
| Target runtime | **75.00 s** (ceiling 90 s) |
| Tempo | 120 BPM → `0.5 s` per beat, 150 beats, 37.5 bars of 4/4 |
| Cut points | every shot boundary is on a beat; the reveal lands on beat 18 (9.00 s) |
| Picture | 1920×1080, 30 fps, H.264, burned captions, no audio track in the animatic |
| Final take | same grid; music bed and UI sound effects added under the captions, ducked below any voice |

## 6. The three proofs

Each proof is a thing only this build can show, and each is checked by an existing test or by a
capture of a real state.

1. **The shelf carries evidence, not sentiment.** Home renders, per course, a real sections-done
   tally and the backend's own next-step label (`home.card.meta`, `home.card.next` in
   `docs/concept-parity/COPY.md`). No stars, no progress bar, no invented count. The concept art has
   all three; SPEC-V3 §6 refuses them. First frame of proof: Home.
2. **One answer produces exactly one durable row.** Submitting a check writes one transition and one
   evidence row, and the screen says so: the verdict line appears and the evidence chip stops being an
   `if you submit now` preview (`data-cb-evidence-pending` `true` → `false`, a value the take reads
   before the submit and compares after the verdict). The kernel test
   `tests/test_kernel_transitions.py` asserts the single-commit behaviour; the video shows the
   consequence. The v3 deck's `{n} of {total} checks recorded` caption (`COPY.md:157`) is the design
   target and is not rendered by this branch's module, so the film does not caption a count. First
   frame of proof: Classroom.
3. **It resumes.** Close the window, open it, and the same objective and the same check block are
   there — the take compares the block id against the one act one closed on, in a page target that is
   genuinely new. That is the quiet proof that the state is durable rather than a chat transcript
   being re-read. What is *not* compared: the evidence chip's class across the reopen (the take
   asserts its presence only), and whether the reopened check is pending or already graded. First
   frame of proof: Classroom, after a labelled cut.

## 7. What this film will not do

- **No parity claim.** The v3 screens it is built to (`SPEC-V3.md` §5) do not exist on this branch
  yet. The animatic uses pinned plates from `docs/concept-parity/refs/REFS.md`, each stamped
  `PLACEHOLDER · REFERENCE PLATE, NOT THE BUILD`. Their status is **not uniform** — calling them
  "the ratified plates" as a class would be a provenance claim the reference pack contradicts:

  | Plate | Animatic frames | Status |
  |---|---|---|
  | `refs/home.png` (`fd75bed3…`) | `S2`, `S3` | the Home **target** — **not ratified** (`REFS.md`: "outside of the home page, these images were ratified") |
  | `refs/classroom.png` (`ee0c1a66…`) | `S4a`, `S4b`, `S5b` | ratified |

  The Home plate is the shape the Home screen has to take, not an approved image. `ANIMATIC.md` §3
  repeats this per plate so the two documents cannot drift apart.
- **No invented proof.** No user counts, ratings, prices, testimonials, logos, scores or learning
  outcomes. No XP outside Game mode. No leaderboard, ever.
- **No generated UI.** No video model touches a product pixel; a diffusion model garbles on-screen
  text, which is most of a software demo.
- **No precomputed beat presented as live.** If a beat is generated before recording (for example a
  long plan-research pass), the caption says so for the whole beat, and the narration says
  "generated earlier in this build", never "generating now".
- **No unsupported compliance language.** Not COPPA compliant, not child-safe, not
  native-speaker-reviewed, not proven to improve learning. None of those is true and none appears.

## 8. Known gaps at the time of this brief

| Gap | Effect on the cut | What closes it |
|---|---|---|
| v3 Home / Classroom / Course home are not built on this branch | every product frame is a reference plate | CP-022, CP-023, CP-024 landing, then `cp-capture.mjs` stills |
| No CDP window on port 9411 in this card | the driver is written and self-tested, not run against the product | the accepted-commit rig the recording card will start |
| No music or UI sound effects are licensed yet | the animatic is silent | choose a bed and effects under a clear licence before the final take |
| Deferred versus pending replay of long generation | affects whether a plan beat can be live | the recording card decides; if it stays, the caption is on screen for the whole beat |

## 9. Owner gates not touched by this card

Recording, posting to X, and any catalog submission remain closed until DeseretSaint signs off in
chat. This card produces documents, a driver and an animatic MP4; nothing here is published.
