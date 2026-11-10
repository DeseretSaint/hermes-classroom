# Coursebook art bible — A1 character and the shared plate medium

Card: CP-010 (`wt/cp-010-fox`). Owner `easel`, reviewer `quill`.
Binds: A1 fox poses (this card), A2 material textures (CP-011), A3 pack covers (CP-012),
A4 scene headers and A5 object kit (CP-013), and the world prompts (CP-016).
Read with: `docs/concept-parity/PLAN.md` §5, `docs/GM-ART-PLATES.md` §3–§4,
`docs/ASSET-PROVENANCE.md`, `docs/EXPERIENCE-QUALITY-BAR.md`.

Two lanes exist and they are not interchangeable. **Press Plate** is the deterministic,
host-composed flat plate used for pack covers today (`docs/ART-DIRECTION-COVERS.md`). **Painted
plate** is this bible: model-generated, textless, gouache, for character and orientation only. A
painted plate never carries a procedure, a measurement, a safety callout, readable lettering, fake
UI chrome, a rating, a price or a learner count.

---

## 1. Medium

**Opaque gouache on a warm paper ground, drawn over with a dark-brown ink line.**

- Opaque body colour, not transparent wash. Paint sits on the surface and covers the tooth of the
  paper; edges are crisp where the brush stopped, never airbrushed.
- Visible flat brush-shaped marks inside a form: one or two per mass, following the form, not a
  gradient. No airbrush, no soft glow, no photographic texture.
- Paper tooth is a subtle grain over the whole plate, never over a single object and never strong
  enough to reduce text legibility of anything drawn on top.
- Ink line is drawn **last**, over the paint, and is the only black-adjacent value in the plate.
- No cast shadow on the ground for a cutout asset. A plate that ships as a cutout carries no
  ground shadow; a plate that ships as a framed scene may carry one soft shadow, upper-left
  consistent.
- No gradient fills, no drop shadow on the art object, no glass, no glow, no outline halo.

### Light

One soft key light from the **upper left**, about 35° above the horizon. Consequences, all
mandatory:

- The lit plane of every mass faces up-left; the shaded plane faces down-right.
- Shade is a single darker tint of the same pigment (never grey, never black), and covers at most
  30 % of a mass.
- One narrow cream highlight on the top-left edge of the head, the shoulder and the tail — nothing
  else.
- A second, dimmer bounce is allowed only on the underside of a mass that touches another, and only
  in the same pigment family.

### Line

| Output size | Line weight | Rule |
|---|---|---|
| master (A1 masters are 654–837 px tall) | 3.0–3.5 px | drawn once at master size, never a thin line scaled up |
| 256 px export | 2.0 px | downscale from master, then one unsharp pass; line must not vanish |
| 128 px export | 1.5 px | downscale; check the eye and nose dots still read |
| 64 px export | 1.0 px floor | if the line breaks up, thicken to 1.2 px before export; never ship a 64 px frame with a broken contour |

Line colour is `#3a2318` standing for the **ink** role. **Never black (`#000000`), never pure
`#1a1713` for the contour**: `#1a1713` is the body-text ink and reads colder and harder than the
drawn line. A contour that measures within 8 units of neutral black is a defect.

---

## 2. Palette, tied to v3 roles

v3 (`contracts/cb.tokens.v3.json`, CP-002) is not landed at the time of writing. These are the
pigments, each bound to the role it must remain compatible with. When CP-002 lands, the mapping
below is re-checked against the v3 table and this table is amended in place; a pigment may not
change role silently.

| Pigment | Value | Role binding | Use |
|---|---|---|---|
| Paper ground | `#f7f1e4` | `paper` | plate ground; texture only, no motif |
| Dark canvas ground | `#131210` | `paper` (dark) | inspection background for cutouts, not a plate ground |
| Drawn line | `#3a2318` | `ink` (darkened, warm) | every contour, ear inner fold, nose outline |
| Fox fur | `#b7643d` | identity, `lamp` family | body, head, tail, limbs |
| Fox fur shade | `#8f4526` | identity, shade of fur | down-right plane of each mass |
| Fox cream | `#efe0c2` | `paper` / `lamp-soft` family | bib, muzzle, tail tip, inner ears |
| Fox dark sock | `#2b1d14` | `ink` | socks to the elbow, ear backs, paw pads |
| Field green | `#2f6047` | `field` | cloth, strap, leaf motifs only |
| Ochre | `#7b4b0a` | `ochre` | brass, wood, paper-stock props |
| Lamp | `#e8a93a` | `lamp` | the single lit accent on a prop, never on the fox |
| Coral | `#9c2e1c` | `coral` | attention marks on a prop; **never** a mode hue, never on the fox |

Rules:

- At most **five** pigments in one plate, plus the line. A cutout uses fur, fur shade, cream, sock
  and line.
- Fur `#b7643d` and coral `#9c2e1c` are different jobs. The fox body is identity, not attention;
  a coral mark on the fox is forbidden.
- No pigment outside this table. No raw stock colour picked from a screenshot. No gradient.
- Contrast note: white on terracotta is 3.36:1 and fails AA. The fox is art, never a container for
  body text, so this is not a text contrast case — but a label laid over fur is forbidden.

### Measured pigments (A1, shipped)

The provider does not honour exact hex. Its raw output measures fur `#e34c03`, shade `#b12901`,
cream `#fae1ab`. One deterministic temper (`-modulate 92,72,100`, applied by
`scripts/cp010-fox-prep.py`) is part of the pipeline, and the values it produces are what A1 ships
and what A2–A5 must match:

| Pigment | Shipped value (measured) |
|---|---|
| Fur | approx. `#b14d1e` |
| Fur shade | approx. `#983d1e` |
| Cream | approx. `#e3cb9c` |
| Sock / ear back | approx. `#412218` at the keyed plate's dark end |
| Drawn contour | warm brown, no measurable pure black |

A plate whose fur and cream are not within a few units of these after the temper is a different
family and is regenerated, not shipped.

---

## 3. The fox: model sheet rules

One character, four views, one image. The model sheet is the **authority** for every pose.

Proportions (the first column is the **design target**; the second is what shipped, measured on the
plates and recorded in `audit/cp010-fox/shape-audit.json`):

| Rule | Target | Shipped / measured |
|---|---|---|
| Head height | **45 %** of standing figure height (head is large; the concept's ~40 % is corrected to 45 %) | **53.3 %** on `wave`, the only plate whose arms are down so a silhouette neck pinch is meaningful. The 45 % figure was never measured and is now labelled a target, not a measurement. Owner decision `D-CP010-B`. |
| Head width | 1.15× head height | not measured |
| Ear height | 0.55× head height, triangular, rounded tip | matches on inspection |
| Muzzle | short, 0.35× head width, cream, no tooth line | matches on inspection |
| Body | pear-shaped, 1.4× head height tall, narrower at the shoulders | matches on inspection |
| Arms | short, 0.75× head height, ending at the hip line | matches on inspection |
| Legs | short, 0.55× head height, both feet flat, no visible ankle | matches on inspection |
| Tail | 1.5× body height, thick, one S-curve, tip cream | matches on inspection |
| Stance | bipedal, feet apart at 0.5× body width, weight even | asserted by silhouette aspect: every standing plate is between 0.45 and 0.80 wide/tall, and `sleep` is the only plate above 1.0 |

Markings, all four mandatory, each recorded per plate in `audit/cp010-fox/vision.json`:

1. **Cream bib** — one mass from under the chin to the lower chest, symmetric, no scalloped edge.
2. **Cream tail tip** — the last ~20 % of the tail, a single soft diagonal break, not a stripe.
3. **Dark limb marking** — the printed rule is "from the paw **to the elbow**, a single rising edge,
   both sides alike", and the model-sheet prompt (M1) asks for it. **No shipped plate implements it.**
   The sheet's own four views show the paw plus at most a short cuff, and six of seven poses match
   the sheet; `clock` reaches the lower forearm and stops short of the elbow. Until the owner
   resolves `D-CP010-A`, the working band for a new plate is *dark from the paw to no further than
   the mid-forearm / mid-shin* — measured from the sheet, not invented to excuse a pose — and the
   "to the elbow" wording above is the unresolved target.
4. **Dark ear backs** — the back plane of both ears; from the front only the inner edge shows.

Face: two dot eyes, `#241812`, with one cream catchlight each, placed at 0.45 head height, no
lashes, no eyebrows, no mouth line except a single soft curve; closed-eye poses draw one
downward-curved line each side. Nose is a small rounded triangle, sock-dark, with the ink outline.

The fox is never rendered as a robot, never with human hands with fingers, never with clothing
covering a marking, never in a different colour, never with a different tail count.

---

## 4. Pose set (A1)

| Pose | Where it is used | Requirement |
|---|---|---|
| wave | Home trailhead | one front paw raised to ear height, other at side, open mouth curve |
| point | Discover feature banner | one paw extended down-right at 30°, head turned to camera |
| clock | Home "New course" shelf | both paws holding a brass alarm clock, chest height |
| read | Classroom lesson | seated, book open in both paws, head tilted 10° down |
| cheer | check correct | both paws up, head up 10°, tail lifted |
| think | wrong answer, kind | one paw at chin, head tilted 15°, eyes open, never a frown (shipped plate matches the gesture; the tilt is slight and unmeasured — see `D-CP010-B`) |
| sleep | empty / offline | curled, eyes closed, tail wrapped to the chin, no Z letters |

Every pose is generated with the approved model sheet as the reference image and must reproduce
the four markings, the 45 % head, the palette and the line. A pose that changes a marking is
rejected, not shipped as a fallback.

---

## 5. Forbidden content

- Any letter, digit, word, logo, watermark, vendor mark, signature, label, caption or UI chrome
  inside the art, in any script, including fake "hand-lettered" marks.
- A star, a rating, a price, a learner count, a fake badge, a fake progress bar, a fake window.
- A second mascot. A robot. A human figure. A photorealistic animal.
- A procedure, torque value, dosage, wiring value, measurement, hazard symbol or answer.
- A gradient, a glow, a glass effect, a drop shadow on the art object, a lens flare, film grain
  heavy enough to read as noise.
- An off-palette colour, a black contour, a grey shade.
- A ground shadow on a cutout, a framed border, a background motif in a cutout.

---

## 6. Prompt templates

All prompts are recorded verbatim with a sha256 in `docs/concept-parity/ART-PROVENANCE.md`.

**Model sheet (M1)**

```
Single character model sheet, four views left to right: front, three-quarter left, side, back.
A small anthropomorphic red fox, opaque gouache illustration on warm paper, dark brown ink
contour #3a2318 drawn last, never black. Head is 45 percent of the standing figure height, large
round head, short cream muzzle, two dot eyes with one cream catchlight each, small dark nose.
Pear-shaped body, short arms and legs. Cream bib under the chin, cream tail tip on the last 20
percent of the tail, dark brown socks from the paw to the elbow, dark ear backs. Light from the
upper left, one shade plane down-right in a darker tint of the same pigment, one narrow cream
highlight on the top-left of head and shoulder. Flat pure magenta background #ff00ff, no gradient,
no shadow, no ground, no border. No text, no letters, no numbers, no logo, no watermark, no UI.
```

**Pose (P-<pose>)**

```
Same fox as the reference model sheet: identical markings, proportions, palette and line.
<pose sentence>. Full body, centred, standing on a flat pure magenta background #ff00ff with no
gradient, no cast shadow, no ground, no border. Opaque gouache on warm paper, dark brown ink
contour #3a2318 drawn last, light from the upper left. No text, no letters, no numbers, no logo,
no watermark, no UI.
```

Pose sentences, in order: wave = "one front paw raised to ear height in a wave, other paw at the
side, friendly open mouth curve"; point = "one paw extended toward the lower right at thirty
degrees, head turned toward the viewer"; clock = "holding a small brass alarm clock with both paws
at chest height"; read = "seated with an open book in both paws, head tilted slightly down";
cheer = "both paws raised high, head tilted up, tail lifted"; think = "one paw at the chin, head
tilted to one side, calm thoughtful eyes, no frown"; sleep = "curled up asleep, eyes closed, tail
wrapped around to the chin".

**Negatives (every call)**

```
text, letters, words, numbers, typography, lettering, watermark, signature, logo, UI, screenshot,
window chrome, badge, star, price, gradient, glow, glass, drop shadow, border, frame, second
mascot, robot, human, photorealism, black outline, off-palette colour, extra tail, extra limb,
frown, angry expression
```

---

## 7. Reference-image procedure

1. Generate the model sheet (M1) at landscape aspect. Record the provider's returned media URL,
   never a local mirror, never a re-hosted copy.
2. Key the magenta ground, inspect the cutout at 200 % on parchment and on the dark canvas, and
   build the model-sheet contact sheet with four labels drawn by ImageMagick, not by the model.
3. **Owner approval gate.** The owner approves the model sheet from the contact sheet. No pose is
   generated before that approval. A rejected sheet is regenerated (round budget 3) and the
   rejected bytes are deleted, never kept as a fallback.

   **State of this gate (A1): OPEN and out of order.** The seven poses were generated from the
   shipped sheet before it was signed, so the family could be reviewed in one pass. That is a
   deviation from the order this section requires and is recorded as `OI-2` / `D-CP010-A` in
   `audit/cp010-fox/vision.json`. If the owner rejects the sheet, every pose is regenerated from
   the replacement; nothing here may be cited as approved art until the two contact sheets carry a
   signature.
4. Generate each pose with the **approved model sheet's provider media URL** in
   `reference_image_urls`. The model sheet is the only style reference; a pose is never generated
   from another pose, so drift cannot compound.
5. Key, inspect, OCR-check and vision-compare each pose against the model sheet before it enters
   the contact sheet.
6. A pose that fails any check is regenerated from the same approved sheet. Three rounds per pose;
   a fourth failure escalates rather than shipping.

## 8. Cutout procedure

- Generate on flat chroma magenta `#ff00ff`. Sample the true corner colour from the returned file
  and key on that value, not on the literal hex, with `-fuzz 30%` and `-transparent`.
- **`-fuzz 30%` is the executed value, not a guess.** The provider returns a sampled magenta
  (`#d30592`–`#c4089c` in A1), not `#ff00ff`, and it sits close to the fox's deep shade in RGB, so
  a narrower key leaves a magenta rim on the fur and a wider one starts eating the dark sock. The
  A1 masters are reproduced from their recorded raw only at 30: at 28 the difference is 89 px and at
  32 it is 160 px against the shipped master, and at 12 it is 763 px. An earlier draft of this
  section prescribed a 12 % key, which under-keys every plate; the value and
  `scripts/cp010-fox-prep.py`'s default now come from the same measurement, and
  `tests/test_cp010_fox_assets.py` re-keys each recorded raw and compares it pixel for pixel so the
  document and the pipeline cannot diverge again.
- The executed invocation per plate, recorded in `audit/cp010-fox/provenance.json` via its
  `raw_sha256`: `python3 scripts/cp010-fox-prep.py <raw> <master>` with no `--fuzz` argument, which
  is the 30 % default.
- Trim, then pad to a square canvas with transparent edge so every pose shares one export box.
- Fringe: the fallback is not a re-key at a lower fuzz — a lower fuzz is what produces the fringe.
  If fur edges still carry magenta, remove the background with `rembg` (`u2net`) in a private `uv`
  venv, not a global install, and record that it was used.
- Inspect every cutout at 200 % on `#f7f1e4` and on `#131210`. A magenta halo, a chewed contour or
  a semi-transparent sock on either ground is a defect.
- Exports: the master is the keyed plate at its own natural size (A1 masters are 654–837 px tall,
  not 512), then 512, 256, 128 and 64 px are downscaled from it. Alpha preserved; no matte baked in.
