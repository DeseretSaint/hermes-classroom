# Fox sign-off — A1 painted set is canonical

Date: 2026-11-10
Owner: DeseretSaint
Reference: `docs/concept-parity/art/fox-signoff-2up.png` (M1 model sheet + A1 seven-pose sheet)

## Decision

The painted A1 fox is the Coursebook mascot and is canonical across the product. The seven poses are
`wave`, `point`, `clock`, `read`, `cheer`, `think`, `sleep`, with the surface assignments printed on
the A1 sheet. The assets are the 660×660 RGBA masters and the 512/256/128/64 exports under
`assets/art/fox/`.

## What this closes

- No new model sheet, pose generation or character re-approval is needed.
- The procedural SVG fox under `assets/masters/fox/` and the WebP derivatives under `assets/fox/` are
  placeholders, not the character. They must not be used for a parity gate.
- The remaining work is adoption: wire the painted set into the brand-asset segment, lift `FoxPose`
  past 128, and render Home at 208. See `FOX-ASSET-AUDIT.md`.

The signature lines on the 2-up are blank; this record captures the owner's explicit in-session
approval of the A1 set on the date above.
