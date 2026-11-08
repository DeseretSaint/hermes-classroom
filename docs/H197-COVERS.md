# H-197 — the illustration lane: Press Plate covers

Branch `wt/h197-illustration`, based on master `179880d` plus a `--no-ff` merge of the completed
Workshop branch `wt/t_5ef6be7f` (H-196a, tip `e3d01f7`). This pass is additive: no H-196/H-196a
commit, frame or audit file was rewritten.

## What changed

1. **Policy.** `docs/COURSEBOOK-VISUAL-IDENTITY-V2.md` §9 now carries the amended refusal clause (the
   old “No external asset, illustration pipeline, icon font or second icon set.” bullet is gone) and
   §4.13 keeps `Icons: sdk.Codicon only` unchanged with the one-lane ornament sentence appended. The
   no-gradient, no-shadow, no-progress-ring and no-second-icon gates are untouched, and a test
   asserts all of it.
2. **One lane, implemented: Press Plate** (`docs/ART-DIRECTION-COVERS.md`). One broad flat form, one
   hard-edged `lamp-soft` flood, one `lamp` band full bleed at y=518, one ink cut edge, five flat
   inks, no text, no object. Printed by `bundled/packs/build_demo_packs.py`.
3. **Two files per pack.** `content/cover-16x9.png` (1024x576 master) and `content/cover-3x2.png`
   (864x576, the master's mechanical centre crop). Both are declared in `files[]`, both carry a
   `CC0-1.0` per-artifact licence record, and only the master is linked through `media[]`.
4. **Pack releases.** Japanese `2.0.0 → 2.1.0` (additive cover; wording, checks and sources
   unchanged). Technical `1.0.0 → 2.0.0`, moving to `cb.pack` v2 so it can carry the plate. The
   parent pack stays `cb.pack` v1 and keeps the typographic cover — see below.
5. **Cover lookup.** `coursebook/workshop.py` now prefers the artifact whose own provenance says
   `pack_file == <the catalogue's cover path>`, instead of “the first visual in lesson order”, and
   `_cover_problems` refuses a catalogue whose cover is not the pack's first linked visual (or names
   a file that no route could serve). The storefront can no longer show a different figure as the
   cover.
6. **Provenance.** `docs/ASSET-PROVENANCE.md` records both files per pack with sizes and sha256, the
   generator, the licence and the accuracy position.

## Which covers are what

| pack | cover | kind | why |
| --- | --- | --- | --- |
| `japanese-affection-context-l0` 2.1.0 | `content/cover-16x9.png` + `cover-3x2.png` | **press plate, host-printed** (five inks; CC0-1.0, our own work) | was cabling the relationship schematic as its cover — off-ratio and a README diagram, not a plate. The schematic stays in the pack as the lesson's factual visual. |
| `technical-demo-pack` 2.0.0 | `content/cover-16x9.png` + `cover-3x2.png` | **press plate, host-printed** (five inks; CC0-1.0) | new fixture, no v1 role, so it can carry a media artifact. |
| `parent-measurement-practice` 1.0.0 | *(none)* | **typographic fallback** | cb.pack v1 is the repository's only v1 fixture and the gate that proves a v1 import behaves byte-for-byte as before; a v1 document may not carry `media[]`, so it cannot adopt a cover artifact. Converting it would delete that gate, so the fallback is stated rather than hidden. |

**No model-generated cover ships.** The art direction measured the host image pipeline (1024x576;
4,851–34,692 unique colours against a five-ink request; added grain and a keyline frame; invented an
object for a jug prompt) and recommended Press Plate as material, not depiction. The prompts P1–P3,
the finish recipe and the acceptance block are recorded verbatim in `docs/ART-DIRECTION-COVERS.md`
for a host that exposes `image_generate`; nothing here claims a model made these bytes.

**No CC0 human set ships.** One set is permitted (Open Peeps only: `peep-92.svg` cameo,
`peep-sitting-1.svg` empty state). This pass ships none: the card forbids network access, so no CC0
SVG could be fetched, hash-recorded or visually verified, and the cameo is optional. Humaaans is
held for its unresolved CC0/CC BY provenance; Open Doodles and the rest of the rejected list stay
out.

## Evidence actually run

- `python3 scripts/h197-cover-accept.py` → `Press Plate acceptance: PASS`; 1024x576 masters of
  3,804 B and 3,784 B, 864x576 crops of 3,153 B and 3,162 B, exactly five inks each, left 4% clear,
  centroid inside the middle 84%, band at y=518 covering 10.1%.
- `python3 -m unittest tests.test_h197_covers tests.test_workshop tests.test_packs_fixtures` →
  `Ran 102 tests … OK`.
- Full suite: `python3 -m unittest discover -s tests -t .` → `Ran 2487 tests in 447.461s — OK`.
- Release gate: `bash scripts/validate-plugin.sh` → `Release gate passed: 4/4 checks (2440 files)`
  on the code commit before this documentation touch.
- `python3 scripts/h197-cover-frames.py` → 12 frames recorded from real install/media payloads;
  `node scripts/h197-cover-shot.mjs .` → 12 PNGs, every frame `overflow=false`, `primary=1`, one
  `h1`; all three cover images in the storefront frames loaded at 1024×576.
- Vision inspection of the finished PNGs at 1:1 and at 240×160: the first Japanese plate was
  rejected by inspection (a deep arc read as an arch/bridge, i.e. a recognisable thing), which is why
  the final Japanese form is a slanted plane. The technical plate passed first time. Both final
  plates are clean at 240 px and carry no legible mark, object, gradient, shadow, frame or text. The
  H-197 storefront, detail and fallback frames were inspected the same way (see the frames section).

## What this pass does not claim

- No native-speaker, expert or human review of any kind; no cover is “verified”, “safe” or “true”
  because it carries a hash.
- No rights verdict beyond authorship: both plates are CC0-1.0 because they are our own work.
- **Frames are a new pass, not a rewrite.** `scripts/h197-cover-frames.py` installs both
  cover-bearing packs through the real `workshop.install()` gate on a throwaway home, records the
  real catalogue envelope, the real Library rows and the real `media.preview_artifact` bytes, and
  renders 12 frames through the shipped module in jsdom; `scripts/h197-cover-shot.mjs` paints them in
  Chromium and records what the layout did. Output lives in `audit/visual/h197-covers/` (PNGs,
  `html/`, `frames.json`, `recorded.json`, `evidence.json`). `audit/visual/h196-workshop/` and
  `audit/visual/m4-visual/audit.json` were **not** touched or hand-edited: `desktop/plugin.js` is
  unchanged (`c8e98f29b6ac2270…`, the same hash H-196a recorded), and H-196's frames remain the
  record of the surface before this lane existed.

  What the frames measured (all 12: `horizontal_overflow=false`, `primary_count=1`, one `h1`):

  | frame | cover kinds painted | images loaded |
  | --- | --- | --- |
  | 01–08 storefront at 1049/900/460 light+dark, 200 % text, reduced motion | `artifact`, `artifact`, `typographic`, `artifact` | 3 × 1024×576, `loaded=true` |
  | 09–11 cover detail at 1049 light, 900 dark, 460 light | `artifact` | 1 × 1024×576, `loaded=true` |
  | 12 parent pack detail | `typographic` | none |

  The featured hero paints the catalogue's own plate at 541×304 (1049), 459×258 (900) and 439×293
  (460 card); the detail plate paints 1049×590, 900×506 and 460×259. Every image carries the
  human-written alt, and the caption is present in every frame. The 200 % text frame grows the page
  to 4932 px with no clipping or horizontal overflow. The dark frames mount the bright plate on the
  dark paper field with the existing rule, no glow or gradient.

  Vision inspection (this branch, the actual PNGs above): the storefront's two plates read as flat
  composed fields, not photographs, objects or diagrams; the parent row reads as a composed
  typographic plate; the captions are legible. That is an inspection of the finished files, not a
  claim of review by anyone else.
- **No accessibility or safety claim beyond what was measured.** Contrast, alt presence, no
  overflow, one primary per view and the 200 %/reduced-motion postures are asserted; no screen-reader
  session and no human accessibility audit was run.
