# Adversarial review — can native-image DeepSeek plus Opus direction produce the studio UI?

## Verdict

For **layout and code**, yes. DeepSeek V4.1 Flash is a strong coding model and its vision is good
enough to read a spec, a diff and a crop. With Opus writing exact boxes, tokens, assets and states,
it can build the screens.

For **the character and the art**, no. Neither model draws the painted fox. The approved character
has no production asset in the repo, and the shipped vector is a different design. No amount of
direction, iteration or token compliance closes that gap. The quality ceiling is art, then spec,
then QA, then model choice — in that order.

The current plan fails adversarially on exactly this point: it treats the shipped assets as
canonical, so it will build a technically correct frame around the wrong fox and call it parity.

## Evidence

- DeepSeek V4.1 Flash is multimodal, but its vision caps an image at 1,024 tokens and its base
  MMMU-Pro is 56.5. It sees a thumbnail of a 1344×768 page; it is a layout reader, not an art judge.
- The fox audit (`FOX-ASSET-AUDIT.md`): Home concept and R-SYS show a painted, bushy-tailed fox;
  the shipped 512/256/128 assets and the SVG master are a flat, front-facing vector with a pocket
  watch. Same slot, different character. The design file uses the vector at 208 px.
- The board's gates (CP-053, GM-016) measure tokens, geometry, capture and presence. They do not
  measure likeness. A green board can still ship the wrong character.

## Findings against the plan

**1. Asset canon is wrong (fatal).** The prompt says shipped covers, fox sprites and object kit are
canonical. For the fox, the canon is R-SYS/R-HOME, and the production asset does not exist. Fix:
art lock before any Home parity claim; the shipped vector is a placeholder, not the character.

**2. "Owner signs once" is in the wrong place.** The plan signs the final screen. The character must
be signed before UI work: one model-sheet/pose contact sheet, then hash-lock. Otherwise every screen
inherits an unapproved mascot.

**3. Character fidelity by crop SSIM cannot fix a wrong asset.** If the asset is the vector, the crop
score fails forever and the loop grinds. The gate is correct to fail; the fix is upstream art, not
another pass.

**4. "One handoff" cannot include taste.** Opus can art-direct and reject, but it cannot decide what
the owner's mascot should look like. One 10-minute owner approval of the pose sheet is unavoidable.
Everything else can be delegated.

**5. Pose coverage is missing.** The ratified sheet shows two poses; the UI needs six to eight
surfaces. The seven shipped vector poses are the wrong character. Without a pose matrix, the worker
will paste one fox everywhere or invent poses in CSS. Fix: pose matrix, one pose per surface, no
repeats in a viewport.

**6. "Not static/copy-paste" conflicts with the motion tokens.** The design system forbids looping
animation. A living character therefore means state-driven pose swaps (read → cheer on completion,
sleep on empty), not an idle loop. If continuous motion is wanted, it is a design-system amendment,
not a worker decision.

**7. Native vision is on, but it is not art judgment.** DeepSeek sees thumbnails; review crops.
Opus is the art judge at gates; the owner is the final judge of the mascot. Do not let the writer
certify its own character.

**8. The plan has no art-production card, only UI cards.** A screen that needs a missing pose will
block forever. Fix: an art-lock card before the Home spec, with generation/cleanup, a contact sheet,
and a fallback (drop the pose or commission it).

**9. The deadline and the art critical path collide.** It is 23:48; CP-053's checkpoint is 03:00.
Art lock plus Home implementation cannot be guaranteed in three hours. The honest options: Home ships
with the correct fox only if the art lock completes by roughly 02:30; otherwise Home drops from this
release, as the supervisor already planned. Shipping the vector and calling it parity is worse than
dropping the screen.

**10. The plan still measures presence somewhere.** "Element checklist present" survives in the
acceptance list. For characters, replace it entirely with asset identity, natural size, pose-map
compliance and the feature checklist. "Present" is how a bad fox passes.

## Revised one-shot plan

**Phase A — Character lock (parallel, time-boxed 90 minutes).**
A1. Extract the ratified views: Home fox, R-SYS sitting fox, standing fox, tail study.
A2. Build a high-resolution model sheet (front 3-4, side, face, palette, markings).
A3. Generate the pose matrix from the sheet; key to alpha; inspect at 200%.
A4. Owner approves one contact sheet; hash-lock 512/1024 exports. No UI parity claim before this.

**Phase B — UI implementation (writer: DeepSeek; director: Opus).**
B1. Opus writes the exact spec: boxes, tokens, assets, states, pose per surface.
B2. DeepSeek implements; DOM geometry audit ±2 px; computed styles; gates; axe.
B3. Crop-level review; pose-map compliance; no CSS drawings; no upscaling; no repeats.
B4. Land each screen with the installed-build capture.

**Phase C — Quality gate.**
C1. Critical dimensions: character, typography, material; below 4 fails, no averaging.
C2. Character feature checklist against the model sheet; asset hash; natural size; crop comparison.
C3. Owner sees one final contact sheet; then done.

## The narrow answer

DeepSeek with native images plus Opus direction is sufficient **for the build**, not for the **art**.
If the character is produced and locked first, and Opus's spec is machine-precise, the plan can be
one shot. If the plan continues to treat the shipped vector as the fox, no amount of model power
will save it — the output will be a clean layout with the wrong mascot, which is exactly what the
owner has been seeing.
