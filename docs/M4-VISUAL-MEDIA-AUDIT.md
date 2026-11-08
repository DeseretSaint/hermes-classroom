# M4 visual, accessibility and media truth gate

Status: independent gate for the product-line claims in `docs/VISUAL_MEDIA_PLAN.md` §3, §6.4 and
§11 ("M4 — visual identity and polish"). The audit was first written on `wt/m4v-landing` (base
`1fc0542`, post-H-38 UX union) and is regenerated on every module change since; this revision was
regenerated on the H-158 UI batch union (`h158-union` @ `c41ee83`: H-145/146/147/148/149/150/153/154/156/157
merged onto merged `master` `71b01b8`) and is pinned to the module that union produces:
`desktop/plugin.js` sha256
`8347331f969d1dc39661d2cdbb6e8b90fe9fbbaa7c96c78f019976a8f096711d`.

That module is the one that ships from the union merge `b7c53e4`, the commit this audit was regenerated
for, so this is the audit of the shipping module, not of a branch. The previous
pin, `desktop/plugin.js` sha256
`0312a9ea6535debd9d649e2ccc467274168e8420fd42870f3a959df62b3f8543` (`625c939`), is history for the
H-120b tree, as is
`71fc4c3f57c8b296dbe7d50694151055f6ca7fc00ae4b01b0e90b91f2c5981a5` for the H-91 tree;
those `audit.json` files differ only in `generated_at`, the recorded branch name and the plugin pin.

This is **not** publication evidence. Nothing here was published, tagged or opened as a catalog PR;
the union it measures is merged to `master` (`b7c53e4`) and the audit makes no claim that Coursebook
is installable.

One command regenerates every number and every screenshot; a second proves the result is not a
one-off:

```
python3 scripts/m4v-audit.py           # regenerate audit/visual/m4-visual/
python3 scripts/m4v-repro-check.py     # two independent runs, byte-compare them
```

`scripts/m4v-repro-check.py` runs the whole audit twice in isolated scratch/out trees (separate
render pass, browser and screenshots) and fails on any difference except `generated_at`; it prints
both runs' plugin sha and reference time on success.

Output: `audit/visual/m4-visual/audit.json` (62 frames, per-frame measurements, 15 claims,
1 defect — D-1, fixed in this tree) and `audit/visual/m4-visual/*.png` (62 frames). The evidence
records the fixture clock it rendered against (`reference_time: 2026-11-07T10:00:00.000Z`), so
"Last touched 17 hr ago" is a property of the fixture, not of the day the audit ran.

### Reproducibility

**Re-pin at `8347331f` (H-158 union, commit `c41ee83`, merged as `b7c53e4`).** `desktop/plugin.js`
moved again with the UI batch union, so the audit was regenerated on the union tree:
`python3 scripts/m4v-audit.py` → 15 PASS, 0 not PASS, 62 frames,
`plugin_sha256: 8347331f969d1dc39661d2cdbb6e8b90fe9fbbaa7c96c78f019976a8f096711d`. The 56
non-forced frames now measure **2,416** text nodes and the 32 frames with an accessibility tree
measure **298** AX controls — fewer controls than the `625c939` record's 364. That difference, and
the Field Quest and Field Desk movement that carries the text total, is now attributed per frame and
per hunk in [Per-frame delta attribution (H-161)](#per-frame-delta-attribution-h-161) below;
minimum authored contrast is
unchanged at 5.93:1 with 0 plugin-authored failures, 0 clipped text and 0 px horizontal overflow. The
reproducibility pair quoted below was re-run at this pin as part of the same pass.

The check is part of the evidence, not a convenience: two independent audit runs (separate render
pass, separate browser, separate output tree) must agree on every measurement and every screenshot.
Run back to back on this pin (`8347331f…`), verbatim (scratch roots elided):

```
$ python3 scripts/m4v-repro-check.py
run A → …/cb-m4v-repro-gz4l7rsm/run-a
run B → …/cb-m4v-repro-gz4l7rsm/run-b
PASS: two independent runs produced identical audit.json (62 frames, modulo generated_at) and 62 identical screenshots
  plugin_sha256: 8347331f969d1dc39661d2cdbb6e8b90fe9fbbaa7c96c78f019976a8f096711d
  reference_time: 2026-11-07T10:00:00.000Z
```

Earlier runs at the `71fc4c3…`, `80725f6` and `635b706…` modules reported the same 62/62 result at
their own pins; those are history for their commits. Every run measured the module that ships from
the commit it was made on; the `plugin_sha256` line is what makes that traceable.

#### The one frame that used to drift (H-90)

At the previous pin (`635b7061…`) this check failed on exactly one frame,
`quest-light-1280-16.png`: `audit.json` matched modulo `generated_at` and 61 of 62 screenshots were
byte-identical. Every number the claims assert comes from the measurements, so the verdicts were
unaffected — but one painted frame was not deterministic, which is not acceptable for evidence.

The cause was in the audit's paint stage, not in the module. `scripts/m4v-audit.mjs` walks each
1280 px frame with real `Tab` key events before it screenshots. That walk necessarily ends inside
the last control it reaches, and Field Quest's last control is the native `<audio controls>`; its
UA shadow parts all report the host as `document.activeElement`. Chromium paints a focused media
control's volume/timeline widget differently from an unfocused one, and which internal part holds
focus depends on the media element's own internal readiness — so the captured pixels depended on
the walk's last press rather than on the artifact. The difference was a 9×4 px segment at
(670, 1078) inside the control bar, with identical layout, tokens and text everywhere else. A
second race of the same family sat next to it: Chromium grows the control bar as audio metadata
arrives, so a screenshot taken before metadata lands captures a half-built widget.

Both are fixed at the render/audit layer, with no product change:

- `settle()` now waits for `readyState >= HAVE_METADATA` (or a definitive error) on every
  `audio`/`video` element and for image decode, on top of `document.fonts.ready`.
- a new `rest()` blurs the active element back to the body-focus baseline the keyboard walk starts
  from and settles again, and it runs immediately before every `Page.captureScreenshot`. Keyboard
  claims are read from the walk's per-stop records, not from the screenshot, so nothing is weakened.

Evidence that the fix holds, not just that it passed once: before it, a six-frame probe of the
Field Quest 1280 px renders produced two distinct `quest-light-1280-16.png` hashes in 2 of 8 runs
(and drift in 4 of the 6 frames); after it, 10 repetitions produced one hash per frame, two full
62-frame paint passes compared with **0 drifting frames**, and the two repro-check runs above are
62/62 each. Eight committed frames changed as a result — they had been captured with a focused
media control — and were regenerated by `python3 scripts/m4v-audit.py`, never hand-edited.

## Method

Two stages, both black-box against the shipped `desktop/plugin.js`:

1. **Render** (`scripts/m4v-render.mjs`). The shipped components are mounted with
   `react-dom/client` in jsdom, so effects run: `useArtifactPreview` actually calls a stubbed
   `ctx.rest`, and the real `<img>`, `<audio>` and media frame are mounted. The transport is the
   only stub; it serves the committed media fixtures in `tests/fixtures/media/` — a real 1024×576
   PNG and a real 4.66 s MP3 of the documented utterance `こんにちは。今日はいい天気ですね。`
   (neither is the M0 host-probe artifact; see `tests/fixtures/media/README.md`) — and a
   deterministic schematic built by the shipped
   `artifacts.make_schematic_svg` from the procedure document's own rows. The module is rendered
   once per (surface × light/dark × 1280/460 host viewport × motion), because the module reads
   `host.state.viewport` at render time — the 460 px layout is a real narrow render, not a
   scaled screenshot.
2. **Paint / measure** (`scripts/m4v-audit.mjs`). Each render is opened in headless Chromium,
   the variant is emulated (CSS width, root font 16 px / 32 px, `forced-colors`,
   `prefers-reduced-motion`), the painted DOM is measured and the frame is screenshotted. Every
   number comes from Chromium: computed styles, layout, the accessibility tree and real `Tab`
   key events.

Surfaces: Textbook, Guided, Field Quest, Field Desk, Procedure, plus the text-only and
media-unavailable Textbook variants.
Variants: light/dark, 100 %/200 % text, 1280 px/460 px, forced colors, reduced motion, image +
audio players, text-only, media-unavailable.

## Verdicts

| Claim | Verdict | Evidence (in `audit/visual/m4-visual/audit.json`) |
|---|---|---|
| C-01 Paint only from the `--cb-*` token layer | **PASS** | 62/62 frames carry all ten measured tokens; 0 colour literals in authored inline paint; 0 colour literals in `desktop/plugin.js` outside the embedded table; table equals `contracts/cb.tokens.v2.json` |
| C-02 Contrast at least the F-01 floor (4.5:1 / 3:1 large) | **PASS** | 0 plugin-authored failures over 56 non-forced frames and 2,416 measured text nodes; worst authored ratio **5.93:1** (procedure, dark), up to 21:1 |
| C-03 No clipped text, no horizontal overflow | **PASS** | 0 clipped nodes in 62 frames; 0 frames overflow; includes 460 px at 200 % text |
| C-04 Every control named and keyboard reachable | **PASS** | 0 unnamed of 298 AX controls across the 32 measured frames; 268 distinct Tab stops, 0 unreachable, 0 without a visible focus ring; 60 audio UA shadow-part stops recorded separately, never counted as Coursebook controls; 0 positive `tabindex`. The `625c939` record measured 364 AX controls and 304 Tab stops; the per-frame comparison puts the whole delta on two surfaces — Quest (`images`/`audio` 1→0, text 49→32, AX 21→10) and Field Desk (text 43→81) — and each of those deltas is now attributed to a commit and hunk inside the union in [Per-frame delta attribution (H-161)](#per-frame-delta-attribution-h-161); both verdicts are *intended*, and no control moved from named/reachable to unnamed/unreachable |
| C-05 No autoplay | **PASS** | 0 of 12 painted `<audio>` elements autoplay or play on load |
| C-06 Every instructional image has a text equivalent | **PASS** | 50 images, 0 without `alt`, 0 of 86 media frames without a caption/text equivalent |
| C-07 Every audio has a transcript | **PASS** | 12 audio elements, 0 without an accessible transcript/`aria-label` |
| C-08 Reduced motion respected | **PASS** (trivial) | 0 animated/transitioned nodes in reduced **and** full frames — the module paints no motion to suppress; the preference is read and recorded |
| C-09 Forced colors stays readable | **PASS** | 6 forced-colors frames, 0 authored failures, 0 clipped, 0 overflow |
| C-10 Media-unavailable leaves the lesson readable | **PASS** | 6 frames: 0 images, 0 audio, honest message + caption retained |
| C-11 Text-only path renders media as text | **PASS** | 6 frames: 0 players, 0 broken frames, text equivalent retained |
| C-12 Image player renders the real artifact | **PASS** | 60 decoded images, natural widths 1024 (committed gate PNG) and 640 (deterministic SVG) |
| C-13 Audio player is explicit, not autoplay | **PASS** | `controls`, `preload=metadata`, `data:` source, no autoplay attribute |
| C-14 Illustration fixture is context, not procedure authority | **PASS** | label/alt carry "generated for context only" on every image media frame; independent review below |
| C-15 Every media item has a label and provenance line | **PASS** | 106 media frames, 0 without a label; provenance line present in the frame |

## Per-frame delta attribution (H-161)

The `8347331f` record is smaller than the `625c939` one on three measures and larger on one. This
section names, for each of them, the change inside the UI batch union that produced it, so a reader
looking at the Quest surface does not assume it is unchanged. Nothing here re-verdicts a claim and
nothing here rewrites the committed evidence: the fifteen verdicts, `audit.json` and the 62 frames in
`audit/visual/m4-visual/` are untouched by this card (H-161, `t_0a2720c3`).

### The record chain

Only records that pin a module and were regenerated on that module can locate a delta. The union's
intermediate merges carried a stale `audit.json` from the branch they merged, so each row below
either quotes a committed record (`625c939`, `03ce785`, `c41ee83`) or an attribution run made by this
card — `python3 scripts/m4v-audit.py` into a scratch output tree with that commit's `desktop/plugin.js`
in place, the committed tree left alone. Per-frame values are the `light 1280 px / 16 px` frame of
each surface (`text` / `AX` / `images` / `audio`).

| module sha256 (12) | tree | Quest text/AX/img/audio | Field Desk text |
|---|---|---|---|
| `0312a9ea6535` | `master` @ `625c939` (previous record) | 49 / 21 / 1 / 1 | 43 |
| `687613abde8d` | H-146/H-146b rail @ `03ce785` (committed record) | 49 / 21 / 1 / 1 | **41** |
| `867d241a1ed7` | H-157 branch `6d96263` = base + H-148, **no** rail | 49 / 21 / 1 / 1 | **82** |
| `b12322f1ff27` | union `434ddc3` = rail + H-148 | 49 / 21 / 1 / 1 | **81** |
| `8347331f969d` | union @ `c41ee83` (this record) | **32 / 10 / 0 / 0** | 81 |

Two readings follow from the chain and are the whole attribution:

- Quest moves **once**, between `867d241a` and the H-157 commit `38adb99` (module `1c46d6df`), i.e.
  inside H-157's own diff and in no other union card.
- Field Desk moves **twice**: `43 → 41` with the H-146 rail, then `41 → 82` with H-148's checkpoint
  path. The union's `81` is not a third change — it is those two on one tree (the branch row at `82`
  is the same path with the old all-courses side card still on the page).

### Attribution, per delta

Frame multiplication closes each measure exactly, which is why no unaccounted frame is hiding here:
Quest has 10 painted frames and 6 AX-measured frames; Field Desk has 10 painted frames, 8 of them
non-forced.

| Measure | Delta | Attribution | Hunk |
|---|---|---|---|
| Quest `images` 1→0 (60→50 overall) | −1 × 10 frames | H-157 `38adb99` | `@@ -11336,85 +11407,92 @@ function QuestMission` — the per-block media map that rendered `BlockMedia` is removed |
| Quest `audio` 1→0 (22→12 overall) | −1 × 10 frames | H-157 `38adb99` | same hunk — `BlockMedia` was the only media painter on this surface, so the `<audio controls>` goes with it |
| Quest text 49→32 (490→320, −170) | −17 × 10 frames | H-157 `38adb99` | `@@ -11462,34 +11546,20 @@ function FieldQuestView` (the `HeroFacts` fact row, the "What these counts mean" `<details>` and the "Missions are the reading path" paragraph are replaced by a count caption and one evidence line under the section title) and `@@ -11246,53 +11330,41 @@` / `@@ -11336,85 +11407,92 @@ function QuestMission` (full `ProseText` prose → `missionBriefLine`, one sentence) |
| Quest AX 21→10 (364→298) | −11 × 6 frames | H-157 `38adb99` | `@@ -11246,53 +11330,41 @@` drops `tabIndex: 0`, `role: 'link'`, the `aria-label` and the click/key handlers from the mission `<li>` (4 controls); the media hunks drop the two `Artifact details` buttons (2); the other 5 are the UA parts of the removed `<audio controls>` — the old frame records 21 AX controls against 16 authored Tab stops, and its 7 audio shadow stops are already carried separately |
| Quest Tab stops 16→10 (304→268) | −6 × 6 frames | H-157 `38adb99` | same two hunks: 4 mission `<li>` links + 2 media `Artifact details` buttons |
| Field Desk text 43→41 | −2 × 10 frames | H-146 (`da1d94c`, landed in the union at `03ce785`) | `FieldDeskHome`: `SlotRail` (the classroom rail) replaces `AllCoursesList` as the desk's course list, one card instead of two |
| Field Desk text 41→81 (430→810, +380) | +38 × 10 frames (+304 over the 8 non-forced frames) | H-148 `a27231d`, merged into the union at `434ddc3` | `CheckpointPath` replaces `PathPreview`: each checkpoint gains a state word, a check-state word, a `<summary>` "Details for checkpoint N" disclosure, and — for the current and next checkpoint — four label/value rows (evidence target, committed attempts, last opened, check) |

Sum check: `−170` (Quest) `+380` (Field Desk) = the `+210` the two records differ by across all 62
frames; over the 56 non-forced frames the claim counts, `+304 − 170 = +134`, which is `2,282 → 2,416`.
AX `−11 × 6 = −66` is `364 → 298`; Tab stops `−6 × 6 = −36` is `304 → 268`; images `−1 × 10` and
audio `−1 × 10` are `60 → 50` and `22 → 12`. No other frame moves any of the four measures.

### Verdicts

| Surface | Delta | Verdict | Why |
|---|---|---|---|
| Field Quest | image 1→0, audio 1→0 | **intended** | No media file is unlinked or absent. The Quest frame renders the same document and the same `artifact_id`s as Textbook; both artifacts are served by the same media answers and painted there (Textbook frame: 1 image, 1 audio; C-06/C-07/C-12/C-13 all PASS on those paints). H-157 scoped the surface: the section is the heading, the counts are a caption, each mission is one line, and the full prose, media and audio studio stay in Textbook — stated in `docs/H157-EVIDENCE.md` and reachable by the row's own "Read in Textbook" action. |
| Field Quest | AX 21→10, Tab 16→10 | **intended (a fix)** | 6 of the old 16 authored controls are gone. 4 were a `role="link"` wrapper on each mission row that opened exactly the block that row's visible "Read in Textbook" button opens — a duplicate tab stop per mission; the other 2 were the `Artifact details` buttons of media widgets the surface no longer paints; the 5 AX-only nodes were the UA parts of the audio widget that went with it. 0 unnamed, 0 unreachable and 0 missing focus rings in the new record: no capability was lost, a second way to the same place was. |
| Field Quest | text 49→32 | **intended** | Counts stopped being the hero: three `HeroFacts` values and labels, a disclosure paragraph and a slogan sentence became one caption and one evidence line, and four full-prose blocks became four one-sentence briefs. The prose is not deleted from the product — Textbook renders it for the same document (C-02 measures 30 text nodes there, unchanged). |
| Field Desk | text 43→81 | **intended** | The route now prints checkpoint truth per objective instead of a title-and-state row: state word, check word, and per-checkpoint detail rows for the current and next checkpoint. AX controls stay at 10 and no media is painted, so the growth is information the desk was previously withholding, not new chrome. |

No delta is a defect, so no follow-up card is opened against a surface and the union stays closed.
Had the Quest image been an *unlinked* asset the verdict would be the opposite; the check is that the
same artifact is still painted somewhere in the record, and it is.

## Independent illustration review

Artifact `tests/fixtures/media/cb-media-image.png`, `sha256
e3be1eed6e3881ceb52bf76385ec542e9129728a65a3bf45477f54658f386669`, `image/png`, 1024×576,
49,776 bytes. It is a **committed gate fixture** produced deterministically by
`scripts/make-m4-fixtures.py`, not a generated illustration and not the M0 host-probe image. The M0
image is a `docs/M0-MEDIA-PROBE.md` history record; those bytes are not in the tree. This review
describes the bytes the audit actually serves, and `audit.json` recomputes the same sha256 from the
file on every run.

Independent visual inspection (a look at the committed file, not the generator's source) finds:

- a flat workshop-bench plate: one large circular gasket/hub plate with concentric rings and two
  locating holes, a torque-wrench silhouette to the right, and a mallet and a drift on the bench;
- **no** text, numbers, arrows, bolt order, torque values, clearances or orientation marks;
- the torque wrench has no legible scale — it is a solid silhouette.

Conclusion: it cannot carry a torque value, a sequence, a clearance or a safety instruction. It is
suitable only as labelled context — which is exactly how the renderer presents it (label
"Illustration — generated for context only", the caption says it is not a procedure authority,
and the procedure lens keeps the deterministic schematic rows as the only torque authority).
Verdict **PASS**.

The M0 probe's finding about the original host image — atmospheric, one large bore, no usable
torque authority — still stands as the reason the plan requires a deterministic schematic or a
sourced reference for any procedure, but it is now documented as history in `docs/M0-MEDIA-PROBE.md`
rather than as a claim about the bytes this gate serves.

## Defect found and fixed

**D-1 (low, desktop/product code — fixed on `wt/d1-media-kind`):** when the media route refused,
`MediaSegment` fell back to `kind = 'visual'` because it derived the kind only from the preview
MIME. An audio item whose preview failed was therefore typed `visual` in the frame while its label
and transcript still said narration.

The fix: `BlockMedia` carries the authored `media.kind` into the segment, and `MediaSegment` uses
the served MIME only once the preview is ready; otherwise the authored kind is the fallback. On the
regenerated evidence, `frames[textbook-unavailable-*].media_frames[1]` for `art_audio00000002`
reports `kind: audio`, `label: Narration — the transcript is authoritative`, and the transcript as
its caption in all six media-unavailable frames — unchanged from before except the kind.
`audit.json` derives `defects[].D-1.status` from those frames (so a regression re-opens it), and
`tests/test_m4_visual_audit.py::test_a_failed_audio_preview_keeps_its_authored_kind` guards it.

## Honest limits

- This is a **static render of the shipped module in a stubbed host**, not a live Desktop capture:
  no backend, no chat, no lesson RPC, no real `/api/plugins/coursebook/media` route. The transport
  stub is the only non-shipped piece, and it is limited to `/runtime` and `/media/{id}` answers.
- Host SDK primitives (`Button`, `Badge`, `SegmentedControl`, …) are the test stub's plain
  elements, so their surfaces are the browser's UA paint, not Hermes theme paint. Rows inside a
  host primitive are measured and reported as `contrast_host_primitive_failures` and are **never**
  counted as product contrast evidence. Their real host-theme contrast is F-01's subject, not
  this gate's.
- The audio `<audio>` element is measured for attributes, not playback: headless Chromium cannot
  prove the decoded waveform is audible. The bytes are the committed gate fixture
  `tests/fixtures/media/cb-media-audio.mp3` — real speech of the documented utterance (synthesized
  once with the free Edge speech service and re-encoded to raw MPEG frames; sha256 recorded in
  `audit.json.summary.media_fixtures`), not the M0 MP3 — and they decode as `audio/mpeg`.
- The reduced-motion claim is trivially satisfied: the module has no CSS transition or animation
  at all in any mode. There is no motion theatre to suppress, but this gate also cannot claim a
  suppression that never occurs.
- No user-facing "text-only / reduced data" preference exists in the shipped plugin. The
  text-only variant exercised here is the no-artifact fallback path the plan describes.
- No screen-reader run on a real AT: names come from the Chromium accessibility tree, not NVDA or
  VoiceOver.
- The delta attribution above is measurement, not a new verdict: the intermediate-module runs
  were regenerated into scratch output trees by `scripts/m4v-audit.py` with that commit's module in
  place, and the committed `audit/visual/m4-visual/` was not rewritten by H-161. A reader who wants
  to repeat them checks out the commit named in the table and runs the same command with
  `M4V_OUT` pointing anywhere but the committed tree.
- Not merged, not pushed, no tag, no publish, no catalog PR, no video recorded.
