# Fox asset audit — the approved character does not exist in the repo

Evidence image: `docs/concept-parity/art/fox-audit-three-up.png` (left to right: Home concept,
R-SYS character sheet, shipped asset).

## What the three images show

- **Home concept (R-HOME):** a painted fox sitting in side/three-quarter view beside a separate
  mantel clock. Soft shading, bushy white-tipped tail, long muzzle, dark lower legs, white chest.
- **R-SYS character sheet:** the same character family. Sitting/waving fox in three-quarter view,
  bushy tail, same face, ears, chest and leg markings; a second standing fox with hands clasped and
  a detached tail study.
- **Shipped asset (`assets/art/fox/fox-clock-512.png`, `...-256.png`, and the SVG master):** a
  different design. Front-facing, larger round head, shorter muzzle, different ear interiors,
  different tail, dark gloves, holding a pocket watch. Flat vector shading, not the painted style.

The design file `design/home-scene.html` renders the shipped vector at 208×208. That is why the
composition can score 0.866 on a grey metric and still look wrong: the character is wrong.

## Asset facts

| file | size | sha256 (head) | role |
|---|---|---|---|
| `assets/art/fox/fox-clock-256.png` | 256×256 | `32312f0504cd2eea` | used by the design file at 208 |
| `assets/art/fox/fox-clock-512.png` | 512×512 | `9186a7c3f3acd0e4` | same vector design |
| `assets/fox/fox-clock-128.webp` | 128×128 | `3d057e10d4138a08` | product FoxPose export |
| `assets/masters/fox/fox-clock.svg` | 512×512 | `18a9cc8675b6caa3` | vector master of the wrong design |

There is no production asset of the painted character shown in R-SYS or R-HOME. The SVG masters are
the flat vector design; the painted fox exists only inside the reference images, at roughly 200–250
px tall. It cannot be upscaled to 208 at 2× without visible loss, and it has no alternate poses.

## Consequence

No amount of UI code, token compliance, DOM geometry or model direction turns the right-hand vector
into the left-hand painted character. This is an art-production gap, not a layout gap. Until it is
closed, any Home "parity" claim is false, and any checklist that says "fox present" passes a
different character.

## Art brief (the correct Home fox)

Sitting fox, side/three-quarter view facing the hero or the clock, bushy white-tipped tail curled
behind, long muzzle, dark lower legs, white chest, soft painted shading with visible fur texture.
No pocket watch, no gloves; the clock is a separate object on the shelf. Render at 512 or 1024,
alpha, with a clean cutout.

## Pose matrix (proposed)

| surface | pose | angle | state |
|---|---|---|---|
| Home hero | sit beside clock, tail curled | side / 3-4 | default |
| Home empty | sleep, curled | side | empty |
| Discover / Workshop | point toward the card grid | 3-4 front | default |
| Course home | wave or stand-clasp | 3-4 front | default |
| Classroom lesson | read (book) or think (hand to chin) | 3-4 front | default |
| Lesson complete | cheer, arms up | front | success |
| Parent Studio | stand-clasp, attentive | 3-4 front | default |
| Rail / compact | head-and-tail peek, or none | side | optional |

Rules: one pose per surface, no repeated pose in the same viewport, no arbitrary mirroring that
breaks the tail or lighting, no CSS-drawn substitute. State changes may crossfade between poses in
150 ms; continuous idle animation is forbidden by the motion tokens (no loops).

## Feasibility test (run 2026-11-10)

Two generations were made from the R-SYS and Home crops with the configured image model.

- **Pass 1** produced the right character family and painted style, but with a duplicated tail
  (two tails). That is a hard fail and exactly the sort of drift a presence check misses.
- **Pass 2**, with "exactly one tail, no second tail" in the prompt, produced a clean sitting
  three-quarter fox: one bushy white-tipped tail, the right face, ears, chest and leg markings,
  painted shading. It still needs cleanup: the output is 992×1024 RGB with a baked checkerboard,
  not alpha; the ears are slightly tall; the palette needs a nudge toward the sheet.

Evidence: `docs/concept-parity/art/fox-art-test-1.png` and `fox-art-test-2.png`.

Conclusion: the art pipeline is viable in hours, not weeks, but it is not one-shot without review.
The pose sheet needs a feature check (tails, ears, markings, palette) and a keying/cleanup pass
before any hash is locked.

## Production route

1. Build a high-resolution model sheet from the R-SYS and R-HOME crops: front 3-4, side, face
   close-up, palette, markings.
2. Generate the missing poses with an image model using the sheet as reference (max three
   references), on a flat chroma background; key to alpha and inspect edges at 200%.
3. Compare every pose to the sheet on the feature checklist: ears, muzzle, eyes, chest, legs, tail,
   palette, line weight. Reject drift.
4. Owner approves one contact sheet of all poses; then hash-lock the exports at 512/1024.
5. UI cards place the locked assets; they never draw a character.

If generation cannot hold the character after two passes, drop the pose from the release or
commission it. Do not ship a bad fox to keep a date.
