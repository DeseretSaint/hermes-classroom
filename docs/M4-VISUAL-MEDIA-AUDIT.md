# M4 visual, accessibility and media truth gate

Status: independent gate for the product-line claims in `docs/VISUAL_MEDIA_PLAN.md` §3, §6.4 and
§11 ("M4 — visual identity and polish"). Branch `wt/m4-visual-regression`, base `master` at
`4a33f2d` with `wt/m4-procedure-renderer` (`5067b35`) merged.

This is **not** release evidence. Nothing here was published, tagged, pushed or merged, and the
audit makes no claim that Coursebook is installable.

One command reproduces every number and every screenshot:

```
python3 scripts/m4v-audit.py
```

Output: `audit/visual/m4-visual/audit.json` (62 frames, per-frame measurements, 15 claims,
1 defect — D-1, fixed in this tree) and `audit/visual/m4-visual/*.png` (62 frames). The evidence,
`plugin_sha256` and all screenshots were regenerated on `wt/d1-media-kind` after the D-1 fix.

## Method

Two stages, both black-box against the shipped `desktop/plugin.js`:

1. **Render** (`scripts/m4v-render.mjs`). The shipped components are mounted with
   `react-dom/client` in jsdom, so effects run: `useArtifactPreview` actually calls a stubbed
   `ctx.rest`, and the real `<img>`, `<audio>` and media frame are mounted. The transport is the
   only stub; it serves the **real M0 artifacts** (PNG and MP3, byte-identical to
   `docs/M0-MEDIA-PROBE.md`) and a deterministic schematic built by the shipped
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
| C-01 Paint only from the `--cb-*` token layer | **PASS** | 62/62 frames carry all ten tokens; 0 colour literals in authored inline paint; 0 colour literals in `desktop/plugin.js` outside the embedded table; table equals `contracts/cb.tokens.v1.json` |
| C-02 Contrast at least the F-01 floor (4.5:1 / 3:1 large) | **PASS** | 0 plugin-authored failures over 56 non-forced frames and 2,102 measured text nodes; worst authored ratio **6.61:1** (procedure, dark), up to 21:1 |
| C-03 No clipped text, no horizontal overflow | **PASS** | 0 clipped nodes in 62 frames; 0 frames overflow; includes 460 px at 200 % text |
| C-04 Every control named and keyboard reachable | **PASS** | 0 unnamed of 340 AX controls across the 32 measured frames; 0 unnamed in the 6–14 step keyboard walks; 0 positive `tabindex` |
| C-05 No autoplay | **PASS** | 0 of 22 painted `<audio>` elements autoplay or play on load |
| C-06 Every instructional image has a text equivalent | **PASS** | 60 images, 0 without `alt`, 0 of 106 media frames without a caption/text equivalent |
| C-07 Every audio has a transcript | **PASS** | 22 audio elements, 0 without an accessible transcript/`aria-label` |
| C-08 Reduced motion respected | **PASS** (trivial) | 0 animated/transitioned nodes in reduced **and** full frames — the module paints no motion to suppress; the preference is read and recorded |
| C-09 Forced colors stays readable | **PASS** | 6 forced-colors frames, 0 authored failures, 0 clipped, 0 overflow |
| C-10 Media-unavailable leaves the lesson readable | **PASS** | 4 frames: 0 images, 0 audio, honest message + caption retained |
| C-11 Text-only path renders media as text | **PASS** | 4 frames: 0 players, 0 broken frames, text equivalent retained |
| C-12 Image player renders the real artifact | **PASS** | 60 decoded images, natural widths 1024 (generated PNG) and 640 (deterministic SVG) |
| C-13 Audio player is explicit, not autoplay | **PASS** | `controls`, `preload=metadata`, `data:` source, no autoplay attribute |
| C-14 Generated illustration is context, not procedure authority | **PASS** | label/alt carry "generated for context only" on every image media frame; independent review below |
| C-15 Every media item has a label and provenance line | **PASS** | 106 media frames, 0 without a label; provenance line present in the frame |

## Independent illustration review

Artifact `cb-media-image.png`, `sha256 193c10f4…f15036`, `image/png`, 1024×576, 1,137,959 bytes —
byte-identical to the artifact recorded in `docs/M0-MEDIA-PROBE.md` §Image.

Independent visual inspection (not the generator's self-report) finds:

- one large bore on a workshop bench with a torque wrench and hand tools;
- **no** numbers, arrows, bolt order, torque values, clearances, orientation marks or text;
- the torque wrench is present but its scale is not legible, and a general hammer sits in frame.

Conclusion: it cannot carry a torque value, a sequence, a clearance or a safety instruction. It is
suitable only as labelled context — which is exactly how the renderer presents it (label
"Illustration — generated for context only", the caption says it is not a procedure authority,
and the procedure lens keeps the deterministic schematic rows as the only torque authority).
Verdict **PASS**.

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
  prove the decoded waveform is audible. The bytes are the M0 MP3 (verified by sha256) and decode
  as `audio/mpeg`.
- The reduced-motion claim is trivially satisfied: the module has no CSS transition or animation
  at all in any mode. There is no motion theatre to suppress, but this gate also cannot claim a
  suppression that never occurs.
- No user-facing "text-only / reduced data" preference exists in the shipped plugin. The
  text-only variant exercised here is the no-artifact fallback path the plan describes.
- No screen-reader run on a real AT: names come from the Chromium accessibility tree, not NVDA or
  VoiceOver.
- Not merged, not pushed, no tag, no publish, no catalog PR, no video recorded.
