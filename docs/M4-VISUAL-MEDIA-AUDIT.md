# M4 visual, accessibility and media truth gate

Status: independent gate for the product-line claims in `docs/VISUAL_MEDIA_PLAN.md` §3, §6.4 and
§11 ("M4 — visual identity and polish"). The audit was first written on `wt/m4v-landing` (base
`1fc0542`, post-H-38 UX union) and is regenerated on every module change since; this revision was
regenerated on merged `master` `625c939` — the H-105 + `cb.rpc` v16 union merge `39659b7` plus the
H-120b conversation-practice surface (`wt/h120b-practice-ui` @ `9aa2e6a`), re-landed on the
H-155 engagement audit `ac301a1` — and is pinned to the
module that ships from that commit: `desktop/plugin.js` sha256
`0312a9ea6535debd9d649e2ccc467274168e8420fd42870f3a959df62b3f8543`.

That module is the one that ships from `625c939`, the commit this audit was regenerated on, so this
is the audit of the shipping module, not of a branch. The previous
pin, `desktop/plugin.js` sha256
`71fc4c3f57c8b296dbe7d50694151055f6ca7fc00ae4b01b0e90b91f2c5981a5`, is history for the H-91 tree;
the two `audit.json` files differ only in `generated_at`, the recorded branch name and the plugin pin.

This is **not** release evidence. Nothing here was published, tagged, pushed or merged, and the
audit makes no claim that Coursebook is installable.

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

The check is part of the evidence, not a convenience: two independent audit runs (separate render
pass, separate browser, separate output tree) must agree on every measurement and every screenshot.
Run back to back on this pin (`0312a9ea…`), verbatim (scratch roots elided):

```
$ python3 scripts/m4v-repro-check.py
run A → …/cb-m4v-repro-k205uyh8/run-a
run B → …/cb-m4v-repro-k205uyh8/run-b
PASS: two independent runs produced identical audit.json (62 frames, modulo generated_at) and 62 identical screenshots
  plugin_sha256: 0312a9ea6535debd9d649e2ccc467274168e8420fd42870f3a959df62b3f8543
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
| C-02 Contrast at least the F-01 floor (4.5:1 / 3:1 large) | **PASS** | 0 plugin-authored failures over 56 non-forced frames and 2,282 measured text nodes; worst authored ratio **5.93:1** (procedure, dark), up to 21:1 |
| C-03 No clipped text, no horizontal overflow | **PASS** | 0 clipped nodes in 62 frames; 0 frames overflow; includes 460 px at 200 % text |
| C-04 Every control named and keyboard reachable | **PASS** | 0 unnamed of 364 AX controls across the 32 measured frames; 304 distinct Tab stops, 0 unreachable, 0 without a visible focus ring; 86 audio UA shadow-part stops recorded separately, never counted as Coursebook controls; 0 positive `tabindex` |
| C-05 No autoplay | **PASS** | 0 of 22 painted `<audio>` elements autoplay or play on load |
| C-06 Every instructional image has a text equivalent | **PASS** | 60 images, 0 without `alt`, 0 of 106 media frames without a caption/text equivalent |
| C-07 Every audio has a transcript | **PASS** | 22 audio elements, 0 without an accessible transcript/`aria-label` |
| C-08 Reduced motion respected | **PASS** (trivial) | 0 animated/transitioned nodes in reduced **and** full frames — the module paints no motion to suppress; the preference is read and recorded |
| C-09 Forced colors stays readable | **PASS** | 6 forced-colors frames, 0 authored failures, 0 clipped, 0 overflow |
| C-10 Media-unavailable leaves the lesson readable | **PASS** | 6 frames: 0 images, 0 audio, honest message + caption retained |
| C-11 Text-only path renders media as text | **PASS** | 6 frames: 0 players, 0 broken frames, text equivalent retained |
| C-12 Image player renders the real artifact | **PASS** | 60 decoded images, natural widths 1024 (committed gate PNG) and 640 (deterministic SVG) |
| C-13 Audio player is explicit, not autoplay | **PASS** | `controls`, `preload=metadata`, `data:` source, no autoplay attribute |
| C-14 Illustration fixture is context, not procedure authority | **PASS** | label/alt carry "generated for context only" on every image media frame; independent review below |
| C-15 Every media item has a label and provenance line | **PASS** | 106 media frames, 0 without a label; provenance line present in the frame |

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
- Not merged, not pushed, no tag, no publish, no catalog PR, no video recorded.
