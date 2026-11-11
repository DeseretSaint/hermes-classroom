# Adversarial review v2 — what the advisor prompt still leaves on the table

Verdict: v2 fixes the architecture (one writer, advisor gates, rubric) but it is still not
buildable as written. The approved composition violates the token system it is required to obey,
the surface it is measured on is undefined, its context pack contains numbers I invented rather than
measured, and it has no landing path. Those are not polish issues; they are the reasons the last
attempt was reverted.

## Evidence

- **Element-level failure is the norm in design-to-code.** DCGen's motivating study finds three
  failure classes: element omission, distortion and misarrangement; segment-aware prompting buys up
  to 14% visual similarity. (https://arxiv.org/abs/2406.16386)
- **Self-correction against the rendered page is the biggest lever.** DesignCoder reports +37.63%
  MSE, +9.52% CLIP and +12.82% SSIM from hierarchical decomposition plus self-correction.
  (https://arxiv.org/abs/2506.13663)
- **Automated visual feedback beats human-feedback-free training.** UICoder filters and scores
  self-generated UI code with compilers and multimodal models, then fine-tunes; it approaches
  proprietary models. (https://arxiv.org/abs/2406.07739)
- **A single VLM judge is noisy.** VL-RewardBench: the best commercial judges score 62.4–62.5% on
  fine-grained visual preference; open models sit at 43–54%, near chance.
  (https://vl-rewardbench.github.io/)
- **The architecture evidence from review v1 still stands**: Anthropic's warning about shared-context
  work, Cognition's single-writer rule, MAST's ~66% failure rate, and the advisor-pattern numbers.

## Findings

### F1 — Fatal: the reference composition cannot pass the token gates

Measured from `wt/cp-053-home-scene:design/home-scene.html` against the v3 type scale:

| element | reference | nearest token step | delta |
|---|---|---|---|
| hero h1 | 72 px | display max 64 px (4 rem) | 8 px |
| brand | 34 px | heading max 36 px / lead 20 px | off-scale |
| hero subline | 32 px | heading clamp 24–36 px | off-scale as a fixed size |
| nav / studio | 17 px | body 16 px / lead 20 px | 1 px |
| card title | 15 px | meta 14 px / body 16 px | 1 px |
| tag | 23 px | heading 24 px | 1 px |

Seven selectors (six distinct sizes) are outside the six-step scale, and the headline is larger than
the scale's ceiling. That
is exactly what the first scene did — literal 72 px, literal 34 px — and the gates refused it with
23 failures. v2 still says "match the reference" and "no literal font sizes" in the same breath. A
worker cannot satisfy both. **This is the central unresolved contradiction, and no amount of
delegation skill fixes it.**

Fix: Gate 0 must produce a signed token reconciliation. Either extend the scale with explicit new
steps (`display-xl` 4.5 rem, `brand` 2.125 rem, `nav` 1.0625 rem, `card-title` 0.9375 rem,
`tag` 1.4375 rem), update the gate and the DESIGN.md, or accept the nearest steps and the small
composition shift. The owner decides; the advisor records it; workers implement the decision.

### F2 — Fatal: the surface and the header are undefined

The reference is a full 1344×768 application frame with an 86 px header (brand, nav, studio). The
plugin usually renders in a ~560 px docked pane where the host owns the chrome. v2 says "1344×768"
and "the tab must read as the same product" but never says who owns the header or which surface is
authoritative. If the plugin cannot draw its own header, the top 86 px can never match, and the
composition must be re-anchored. If it can, that is a plugin-route decision with host-contract
consequences.

Fix: Gate 0 surface decision — full-window plugin route that owns the full frame (parity target), or
docked pane with the reference header explicitly out of scope and the stage re-anchored. One answer,
written down, before Gate 1.

### F3 — High: the pack's numbers are wrong because I wrote them by hand

I checked the pack against the branch. It says cards 278 px, covers 170 px, plank at 640/714, tag at
886/626, clock 152 px, fox 196 px. The design file says cards **176×175**, covers **106 px**, planks
at **559** and **684**, tag at **880/606 (164×88)**, clock **118 px**, fox **208 px**. Every geometry
number in the pack was invented. A manager delegating from that pack would specify a composition
that does not exist.

Fix: the pack is generated, never hand-written. A script reads the design HTML, emits the geometry
table, the type inventory and the asset inventory, and stamps the source commit and a hash. If the
pack and the source disagree, the pack is regenerated before any card is created.

### F4 — High: measurement is delegated to a 62%-reliable judge when DOM math is exact

v2's Gate 4 asks one VLM to score five dimensions. VLMs are moderate at fine-grained visual
preference and self-prefer work built to their own spec. Meanwhile the reference's boxes, type,
colours and spacing are all measurable exactly from the live DOM at 1344×768 with
`getBoundingClientRect()` and `getComputedStyle()`. Geometry parity should be a numeric audit with a
±2 px tolerance, not a judgement call.

Fix: measurement stack in this order — DOM geometry audit, computed-style audit, token gates, axe,
masked SSIM, element checklist, then the rubric only for material and illustration. Two independent
judges for the rubric (different model families), calibrated on one known-good and one known-bad
frame. Owner spot-checks the final frame.

### F5 — High: there is no landing path

v2 ends at a branch. The previous scene was merged and then reverted within the hour because the
gates failed at merge time. Nothing in v2 prevents a repeat: no merge card, no full-suite run on the
merge commit, no install-and-capture of the installed build, no rollback.

Fix: a land card after Gate 4 — rebase, full suite, merge, build, install, relaunch, capture the
installed plugin, compare against the branch capture, and a named rollback commit. The screen is not
done until the installed build shows it.

### F6 — High: the vision path is assumed, not verified

The worker runs on DeepSeek. This session's own images arrive pre-described in text, which suggests
the main model is text-only in this harness. If the worker cannot see the frame, "self-correction
against the render" (DesignCoder's biggest lever) does not exist; it will implement numeric deltas
blind and plateau.

Fix: every card declares its vision path: `native` (multimodal model), `tool` (scripted capture →
`vision_analyze` on crops → delta JSON), or `none` (numeric deltas only, and then the card is not
allowed to claim visual convergence). Prefer a vision-capable implementer for the visual phase, or a
cheap VLM in the loop for coarse feedback, with the advisor doing the fine judgement.

### F7 — Medium: anti-cheat is missing

A worker optimising similarity can set the reference PNG as a background or an `<img>` and score
near 1.0 with an empty DOM. The gates, axe and font checks can all pass.

Fix: audit the built route — no reference asset hash in the bundle, hero text is a live text node,
expected element count and selectors present, screenshot taken from the live DOM, and the cover
images resolve to pack artifacts rather than the concept file.

### F8 — Medium: data and asset divergences are not recorded

The concept shows star ratings; the product has none and the design file uses progress bars. The
concept's covers differ from the pack covers in the repo. Both are legitimate divergences, but v2
neither records nor masks them, so the similarity score and the rubric will punish the correct
implementation.

Fix: a divergence ledger signed at Gate 0 — stars → `sections_done/sections_total`, concept covers →
pack cover art, host chrome if applicable — with the masked regions excluded from SSIM and the
rubric's illustration score judged against the agreed asset set.

### F9 — Medium: states and reduced motion are asserted, not evidenced

Gate 1 lists five states; the evidence list only requires the default frame. A screen that only
works in its hero state is not studio grade.

Fix: captures for default, hover, focus-visible, loading and empty, plus reduced-motion. One sheet.

### F10 — Low: cost is capped in calls, not tokens; Fable's verdict is redundant

Six 500-word advisor calls are noise next to the worker's context and iterations. Fable as a third
judge after Opus and a second family adds little unless the two disagree.

Fix: a token/dollar cap per phase and per screen, a gain-based stop, and Fable only as tie-breaker.

### F11 — Low: no arbiter and no decision log

Atlas and cbqa can disagree; the advisor can be wrong; the owner is the only tie-breaker. Without a
log, the same decision is relitigated.

Fix: one arbiter (the advisor), one decisions file with date, decision, evidence and owner sign-off.

## What v2 gets right

The advisor inversion, one writer, explicit gates, the element checklist and the rubric are all
supported by the evidence and should survive into v3. The failures above are about
buildability, measurement and landing, not about the operating model.

## v3

`docs/launch/OPUS-UI-MANAGER-PROMPT-V3.md` adds Gate 0 (reconciliation and signed decisions), a
generated pack, a DOM-first measurement stack, a vision declaration per card, an anti-cheat audit,
and a land card.
