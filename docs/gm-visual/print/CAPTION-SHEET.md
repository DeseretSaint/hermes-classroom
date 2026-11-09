# Print caption sheet — fixed wording

Used by GM-006 preview, GM-014 print proof and any pack that carries a plate. The wording is fixed;
a reviewer checks it verbatim.

## Caption

> World visual — generated plate; orientation only, not a diagram of the course.

For a host-composed plate (no model call):

> World visual — host-composed plate; orientation only, not a diagram of the course.

## Alternative text (screen reader, image alt)

One sentence naming what is in the plate and what it is not:

> Plate: a lantern street with a cafe counter, a noren doorway panel and a cup. Orientation only.

## Text equivalent (print and images-disabled)

Two sentences: what is depicted, then what the plate does not carry.

> A lantern district at dusk: three paper lanterns, a cafe counter with two stools, a noren doorway
> panel, a cup with steam. Nothing in the plate carries a word, number, instruction, measurement or
> rating.

## Provenance line

Model-generated:

> Generated · <provider> · <model> · prompt <hash8> · style <hash8> · role: orientation · <licence>.

Host-composed:

> Host-composed · <generator path> · no model call · <licence> · role: orientation.

Reference plates in this card:

> Host-composed · scripts/build_gm_visual_assets.py · no model call · CC0-1.0 · role: orientation.

## Forbidden words in any caption

`verified`, `accurate`, `official`, `manual`, `diagram of`, `photo of`, `your`, `real`, `authentic`.

A missing licence means the plate does not print. A missing access date prints `access date not
recorded`; it is never filled in by guessing.
