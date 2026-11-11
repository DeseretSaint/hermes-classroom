# Visual quality control — native vision, character fidelity, and the fox problem

## 1. Native image input: the bug and the fix

Every profile was resolving `image_input_mode` to **text** because the capability lookup returned
`None` for `nous / deepseek-v4.1-flash-1017`, so `auto` fell back to pre-analysis. The logs confirm
it: `Image routing: text (mode=text). Pre-analyzing N image(s) via vision_analyze.`

Fix applied to `~/.hermes/config.yaml` and all ten profiles:

```yaml
model:
  supports_vision: true
agent:
  image_input_mode: native
```

Verification:

- `decide_image_input_mode("nous", "deepseek/deepseek-v4.1-flash-1017", cfg)` now returns `native`
  for the default profile and every profile.
- A live one-shot with the fox sprite produced
  `Image token cost calibrated from provider usage: 1 images priced 132 tokens each`, which only
  happens when an image part reaches the provider. The old path would have logged a pre-analysis
  line instead.

DeepSeek V4.1 Flash is natively multimodal (552B MoE, text+image, up to 1,024 image tokens, minimum
295,936 px per image). It is not a text model. The remaining limitation is resolution: a full
1344×768 frame is downsampled to the cap, so detailed review must use 600×600 or larger crops.

## 2. Why "a fox is present" is not a quality bar

The reference fox is **an asset**, not a drawing. `design/home-scene.html` renders
`assets/art/fox/fox-clock-256.png` at 208×208. The product's `FoxPose` primitive only ships 128 and
64 px WebP exports (`assets/fox/fox-clock-128.webp`, `...-64.webp`). At 208 px the 128 px export is
upscaled 1.6× and goes soft; if a worker instead draws a fox in CSS or SVG, it will not match the
character sheet at all. Either way, a checklist that asks "is a fox present?" passes.

The SVG master exists at `assets/masters/fox/fox-clock.svg`. The correct fix is an asset export,
not an illustration task: render the master at 256/512, pin the hash, and use it at Home. A character
is never redrawn by a code worker.

## 3. The quality framework

**Signature elements.** Per screen, name the elements that carry the look: Home's fox, clock, shelf,
planks, tag and four covers; Discover's cards and map; Classroom's lesson furniture; the design
system's card anatomy and badges. These are not checklist items; they are gated.

**Characters and covers are assets, never drawings.** The writer may position, scale and crop an
approved asset; it may not approximate a character with CSS shapes, emoji, or a hand-built SVG. If
the needed pose or size is missing, the card is blocked and an asset-export card is created from the
master. A missing asset is not a divergence.

**Resolution rule.** The rendered CSS size may not exceed the asset's natural size. Home's 208 px fox
requires the 256 or 512 export, not the 128. On a 2× display, the 512 is preferred. No upscaling.

**Asset identity.** The rendered `currentSrc` must hash to the approved asset. The audit records the
hash and the natural-vs-rendered size. A CSS-drawn substitute fails, even if it looks fox-like.

**Crop-level fidelity.** Compare the reference crop and the render crop at the same box, at 2×:
SSIM on structure, palette histogram distance, edge density, and a DINO/CLIP embedding distance.
These are diagnostics, not the verdict; a generic "fox" can score well while the character is wrong.

**Feature checklist against the model sheet.** On a 600×600 crop, ask specific binary questions:
same ear shape, same muzzle, same eye style, same scarf/bandana, same tail tip, same line weight,
same palette. Each answer cites the region. Vague "looks good" is rejected.

**Critical dimensions.** Character, typography and material are critical. A screen fails if any
critical dimension scores below 4, regardless of the average. A beautiful layout cannot average out
a bad mascot.

**Owner art sign-off, once.** Put the reference crop and the render crop in a 2-up sheet at 2×. The
owner approves the character once; after that, the asset hash is locked. This is the only art
judgement that is not delegated.

**Mask policy.** Masked SSIM may exclude copy, star ratings and host chrome only. It may never mask
the character or illustration region. Masking the fox is how a bad fox passes.

**Judge discipline.** Top VLM judges are only ~62% on fine-grained visual preference
(VL-RewardBench). Absolute anchored scoring is more robust to distractor features than naive
pairwise preference, which flips about 35% of the time versus 9% for absolute scores
(https://arxiv.org/abs/2504.14716). Use absolute, feature-specific checks; use pairwise only with
randomized sides and a stated feature, never as the sole gate.

## 4. Adversarial review of the current research and prompt

**The research overstates DeepSeek's visual judgment.** Chartography 83.0 and BabyVision 92.5 are
close to Opus, but MMMU-Pro 56.5 and the 1,024-token cap mean it sees a thumbnail of a full page. It
can implement from a spec and a diff; it cannot certify a character's line quality. The director and
the owner must judge, on crops.

**The cost model is illustrative, not measured.** Thirty-six iterations at 12k context is an
assumption. The conclusion (don't use the manager as a per-iteration oracle) rests on fidelity and
latency as much as dollars.

**LiveWorkspace's +1.8/+2.0 is modest and benchmark-specific.** It supports structured diffs as a
direction, not a guarantee of studio quality.

**The prompt's element checklist is presence-only.** It is the exact control that passes a bad fox.
Replace it with signature-element fidelity and asset identity.

**The rubric average is compensatory.** A 5 in composition can hide a 2 in illustration. Critical
dimensions must be non-compensatory.

**The masked SSIM excludes art.** That is precisely where the fox lives. Restrict masks to copy,
ratings and host chrome.

**The divergence ledger can become an excuse.** "Concept art differs" is acceptable for a cover
whose shipped art is approved; it is not acceptable for a missing mascot. Characters are blockers,
not divergences.

**The prompt assumes the shipped fox poses are usable at any size.** They are not: only 128/64 are in
the product. Add the 256/512 export from the master before Home's fox is judged.

## 5. Changes carried into the program prompt

- Native image input is a precondition; if a turn shows a pre-analyzed description, stop and fix the
  profile.
- Characters and covers are assets; no CSS/SVG approximation; hash and natural-size checks.
- Signature elements per screen, with a non-compensatory critical-dimension gate.
- Crop-level feature checklist against R-SYS, owner art sign-off once, asset lock.
- Mask policy limited to copy/ratings/chrome.
- Missing character asset blocks the screen and spawns an export card; it is not a divergence.
