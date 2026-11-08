# Art direction — the one cover lane (Press Plate)

Card: H-197. Scope: covers and the one optional CC0 human/empty-state lane. This is art direction
and a provenance record; the identity's icon rule is untouched.

## The decision

**Press Plate is the lane.** Every pack is one sheet off the same press: a printed *field*, not a
picture. One broad flat form, one hard-edged `lamp-soft` flood, one `lamp` band full bleed at a
fixed y, and one heavy ink rule. Illustration buys **material** (paper tone, ink bite, plate edge),
never **depiction**. The press is identical on every pack, so the storefront reads as one imprint
instead of a stock-art grid, and the exact geometry that matters stays in the plugin.

Why not the alternatives, measured rather than guessed:

- Four probes of the host image pipeline at landscape returned 1024x576 (1344x768 with a reference
  image) and **every one ignored "exactly five flat inks"** — 4,851 / 9,119 / 34,692 / 6,011 unique
  colours, plus paper grain, an unrequested gold keyline frame, and in one case an invented vertical
  bar. Posterising removed the gradients but left speckle, and anything finer than ~8–10px at 1024
  did not survive.
- Precise topology does not survive: a three-circle-plus-square request came back as an arch, two
  circles, a square and a frame.
- Object-led covers are semantically unstable: "a measuring jug" rendered as a coffee pot, and the
  reference-locked version read as a cargo ship at 240px. A wrong object is a wrong claim about a
  course, which the accuracy gate forbids.

## Composition rules (16:9 master)

- Paper ground edge to edge. One form only (a wide arc segment, a single plane edge, or a solid
  block) occupying 45–60% of the frame and bleeding off one edge.
- One `lamp-soft` flood behind it with a hard straight edge, at most 45% of the plate.
- One `lamp` band, 8–12% of the frame height, full bleed, at one fixed y for the whole imprint.
- One or two ink rules at least 8px thick at 1024.
- The outer 3% stays clear; **the left 4% stays clear of anything meaningful** because
  `WorkshopCover` paints a 6px lamp spine over the image's left edge.
- The form's centroid sits inside the middle 84% so the 3:2 card crop keeps it.
- At most three inks plus paper: no `field`, `ochre` or `coral` — those are state hues, and a cover
  must never look like a state. One arena hue at most: `accent` for learner packs, `plum` for parent
  packs, none for technical/reference packs.
- **No objects, no symbols, no arrows, no letters, no numbers, no glyph-like marks.** No people,
  hands, faces, scenes, tools, documents, landscapes, horizons, suns, charts, bars of varying
  height, grids or page furniture.
- No text of any script in the raster: it breaks i18n, breaks the one-display-plate rule, cannot
  follow dark mode, and garbles in diffusion.

## Prompts (for a host that has `image_generate`)

These are recorded verbatim so the lane can be run on the host without re-deriving the brief. They
were **not** run by the branch that implemented H-197: no image-generation tool was exposed to it
and the card forbids network access. The committed plates are printed by the pack builder to the
same composition and acceptance rules, so nothing in this repository claims a model made them.

**P1 · PRESS PLATE · Japanese L0.** Landscape printed plate, completely flat. Warm off-white paper
ground. One broad form only: a wide shallow arc rising from the left edge to the right edge, like
the top edge of a very large circle whose centre lies below the frame, drawn as a solid indigo band
of even thickness about one eighth of the frame height, hard edges, no outline. A pale gold
rectangular field with a hard straight edge fills the lower half behind the arc. One solid gold
horizontal bar, one tenth of the frame height, runs edge to edge along the bottom. Nothing else. No
text, no letters, no numbers, no symbols, no objects, no people, no horizon, no sun, no landscape,
no border, no frame, no drop shadow, no gradient, no glow, no vignette, no texture, no grain, no
perspective. Five flat inks only: warm off-white #F7F1E4, near-black #1A1713, indigo #2C4A8C, pale
gold #FBEBCB, gold #E8A93A. Print-like, hard edges, no shading.

**P2 · PRESS PLATE · Parent measurement.** Landscape printed plate, completely flat. Warm off-white
paper ground. One broad form only: a single straight vertical edge dividing the frame at two thirds,
the left side filled solid plum and the right side bare paper, with one narrow plum horizontal band
crossing the entire frame at one third height, hard edges throughout. One gold bar one tenth of the
frame height runs edge to edge along the bottom. No jug, no vessel, no cup, no tools, no kitchen, no
table, no hand, no child, no text, no letters, no numbers, no measurement marks, no scale, no
border, no frame, no drop shadow, no gradient, no glow, no texture, no grain, no perspective. Five
flat inks only: warm off-white #F7F1E4, near-black #1A1713, plum #6A3E74, pale gold #FBEBCB, gold
#E8A93A. Print-like, hard edges, no shading.

**P3 · PRESS PLATE · Technical demo.** Landscape printed plate, completely flat. Warm off-white
paper ground. One broad form only: a solid near-black rectangle covering the entire left half of the
frame from top edge to bottom edge, with one pale grey band along its right edge; the right half
stays bare warm paper. One gold bar one tenth of the frame height runs edge to edge along the
bottom. Nothing else. No text, no letters, no numbers, no code, no lines of writing, no table, no
grid, no bars of varying height, no document, no page, no border, no frame, no drop shadow, no
gradient, no glow, no texture, no grain, no perspective. Five flat inks only: warm off-white
#F7F1E4, near-black #1A1713, pale grey #D7CBB4, pale gold #FBEBCB, gold #E8A93A. Print-like, hard
edges, no shading.

## Finish recipe (mandatory if the prompts are ever run)

Every probe ignored the ink count, so a raw return is never shippable. Build the palette once as a
5x1 PNG from the token hexes, then:

- line-and-mass plates: `magick raw.png -statistic Median 3 -dither None -remap palette.png -strip out.png`
- flood-and-band plates where grain must vanish: `magick raw.png -colorspace Gray -statistic Median 5
  -threshold 60% +level-colors '#1A1713','#F7F1E4' -strip out.png`, then remap the hue band from a
  second, separately drawn layer.
- verify with `magick out.png -format '%k' info:` and **fail the build unless it prints 5**. No
  Floyd–Steinberg dithering.
- never upscale the 1024 master beyond 1.5x.

The committed plates are printed with exactly five inks by construction, so no remap is needed;
`scripts/h197-cover-accept.py` is the same acceptance check applied to the finished files.

## Acceptance block

Machine (run `python3 scripts/h197-cover-accept.py`): 16:9 master at 1024x576, no alpha, under
40 KB, exactly five inks all inside the token table, left 4% free of the form, form centroid inside
the middle 84%, one full-bleed `lamp` band at y=518 (+/-2px) covering 8–12% of the height,
`lamp-soft` flood at most 45%, and the 3:2 file proven to be the master's centre crop.

Human, recorded in `docs/H197-COVERS.md`: no legible mark, object, gradient, shadow, frame or text
at 1:1; the plate still reads at a 240x160 card.

## The one CC0 lane (not shipped in this pass)

One CC0 human set is allowed, and only one: **Open Peeps** (`CC0-1.0`). `peep-92.svg` is the
permitted optional cover cameo (lower right, at most 38% of the width, ink only, no background,
recoloured into the paper/ink language) and `peep-sitting-1.svg` is the permitted no-courses
empty-state spot. Never both on one cover, and never as a second cover style.

Held: **Humaaans** (the current site says CC0 but the 2019 mirror is CC BY 4.0; provenance
unresolved). Rejected for this lane: Open Doodles (this pass keeps the lane to one set), Kenney,
Game-icons, Health Icons, Reactome, unDraw, DrawKit, Fresh Folk, Illlustrations, Simple Icons, and
every icon-family source. No NC/SA/custom-licence asset and no stock-photo hotlink may enter.

Nothing from that lane ships in H-197: the card forbids network access, so no CC0 SVG can be fetched
or verified today, and a cameo is optional. When it is used, its upstream URL, creator, licence,
changes, commit and file hash go in `docs/ASSET-PROVENANCE.md`, and a CC BY asset would also need
visible credits in About/third-party notices.

## Provenance fields for a generated cover

A generated cover is first-party model output, not an open-source asset. Record: provider, the
actual model id, the prompt text (or its hash), the date, the sha256 of the finished file, and the
C2PA manifest if the provider emits one. No artist names, studio, movement, brand or franchise
reference goes in a prompt; no real people, mascots or seals; no claim of copyright, uniqueness or
human review.
