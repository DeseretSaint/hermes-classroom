# UI manager brief — Coursebook

Read this once. It is the whole context you need; do not go exploring the repository.

## Product and paths

- Repo: `/home/deseretsaint/Projects/hermes-classroom`
- Board: `coursebook` (Kanban). Cards are the only delegation mechanism.
- Plugin built from `desktop/src/*.js` into `desktop/plugin.js`; installed copy at
  `~/.hermes/desktop-plugins/coursebook/plugin.js` (reload requires a Desktop relaunch).
- Reference frames: `docs/concept-parity/refs/` — `home.png`, `discover.png`, `map.png`,
  `board.png`, `classroom.png`, `system.png`, all 1344×768. The owner's annotated Home concept is
  `docs/concept-parity/refs/home-concept-owner.png`.

## Verified state at 2026-11-10 23:00 MST

- The installed module is `4087908c…` (pre-scene). A first `HomeScene` was merged as `471e7c96` and
  reverted at 22:53 by `ed61d708`: it authored raw hex colours, literal font sizes and an inline
  box-shadow, which broke 23 token/gate tests. Master is green again on its parent (`147/147`).
- A token-compliant Home scene is in progress on branch `wt/cp-053-home-scene` (`a07b99ea`, cinder).
  The reference composition exists there as `design/home-scene.html` (0.866 similarity), not on
  master.
- Inside the Desktop tab the Coursebook route is about 560 px wide (left session rail + right tutor
  rail), so Home currently falls back to the compact layout: a heading, two buttons and a list of
  cards with 56 px cover strips. No shelf, no mascot, no paper material.
- The re-land must pass the v3 gates that refused the first attempt: `test_desktop_tokens`,
  `test_desktop_tokens_v3`, `test_desktop_gate_scope`, `test_desktop_type_scale`,
  `test_desktop_h152_motion`, `test_desktop_gm002_home`, `test_desktop_h86_wayfinding`,
  `test_v3_visual_audit`. Concretely: `var(--cb3-*)` only, no literal hex, no literal font sizes,
  no inline `boxShadow`; type from the six-step scale; motion within the contract.
- The owner's verdict: the current screen is "pitiful" next to the reference. UI is the number one
  priority until it is fixed.

## Native vision

Every profile now has `model.supports_vision: true` and `agent.image_input_mode: native`. Before
that, the capability lookup returned unknown and every image was pre-analyzed into text. If a turn
arrives as a description instead of an image part, stop and fix the profile before accepting
evidence. DeepSeek V4.1 Flash is multimodal, but its vision caps a frame at 1,024 tokens; review
crops, not thumbnails.

The fox is the proof case: the reference renders `assets/art/fox/fox-clock-256.png` at 208×208, while
the product's `FoxPose` only ships 128/64 WebP exports derived from the procedural SVG masters. A 128
export upscaled to 208 goes soft, and a CSS-drawn fox is not the character. Use the painted A1 export
at `assets/art/fox/` (256 or 512), pin the hash, and never accept "a fox is present" as quality. The
SVG master under `assets/masters/fox/` is the placeholder, not the character.

## What "done" means for one screen

1. Captured at 1344×768, `data-cb-scope="light"`, from a route that is at least 1344 px wide.
2. A side-by-side sheet against its reference, a difference image, and a similarity number.
3. Similarity ≥ 0.90, or the best of three passes with a written gap list.
4. axe: zero serious/critical; `CB Display` and `CB UI` both loaded.
5. No invented data: no star ratings, no fake counts, no fabricated learners.
6. Owner approves the frame.

## Files you may read (nothing else)

- `docs/concept-parity/VISUAL-GATE.md`
- `design/home-scene.html` on `wt/cp-053-home-scene` (open it at 1344×768; it is the target
  composition). It is not on master.
- `visual/report.json`, `visual/frames/*.png`, `visual/compare/*`
- `scripts/compare-ref.sh` (header only, for usage), `scripts/build_plugin.py` (header only)
- Board state: `hermes kanban --board coursebook list --json`

Do not survey `desktop/src/*.js`, `tests/`, `coursebook/`, `contracts/`, or other docs. You may open
up to three named source files per screen after saying which and why; the generated pack is the
default substitute for the codebase.

## Roles

| profile | role | model |
|---|---|---|
| cinder, quill | implementation | DeepSeek |
| atlas, cbqa | verification (never the builder) | DeepSeek |
| easel | visual production | DeepSeek |
| harbor | capture rig / window door | DeepSeek |
| sentinel | adversarial review | DeepSeek |
| default (you) | UI supervising manager | Opus 5.5 |

Fable 5.2 is a tie-break judge only, when the director's rubric and the verifier disagree. It is
never a writer and never the first judge.

## Non-goals

Course content, packs, copy/wording, contracts, backend, test counts, docs, release notes, and any
card that does not change what a screen looks like. Copy differences found while matching a
reference are recorded for the owner's copy card; they are never edited by a UI card.

## Budget

- At most two cards in flight; only one touches a screen's files.
- Per screen: writer ≤ $5, critic ≤ $1, director ≤ $3; program ≤ $60.
- Three failed passes on one dimension stops that screen and reports the gap list.
