# Visual gate — binding on every screen card

A card that changes a v3 screen may not request review until it has run the gate and pasted the
result. A reviewer may not score a card whose summary lacks it. This exists because tokens, tests and
hashes all passed while the rendered pages were wrong.

## Run it

```
cd visual
node find-cdp.mjs                      # prints the CDP port showing Coursebook
node audit.mjs --port <port>            # frames/, diffs/, report.html, report.json
cd ..
scripts/compare-ref.sh visual/frames/<route>.png docs/concept-parity/refs/<ref>.png visual/compare <route>
```

## Paste into the review summary

- route **width × height** as rendered, and the `data-cb-scope` value (light or dark);
- **fonts**: `CB Display` and `CB UI` loaded (true/false);
- **axe**: serious/critical violation ids, or `none`;
- **pixel diff** against the baseline, and **similarity** against the approved reference;
- the path to `visual/compare/<route>-sheet.png`.

## The reviewer's rules

1. **Geometry must match the reference.** The approved frames are 1344×768 landscape. A frame
   captured in a 341–744 px pane is a different breakpoint; it can be *correct for that width* but it
   cannot be scored as parity with the reference. Record the width; if it is not the reference's, say
   so and score the composition dimensions only against the pane's own approved state.
2. **Theme must match.** The references are light. A dark-scope frame is a different palette; if the
   card claims parity, the evidence must be light-scope.
3. **A face that did not load is a fail**, even if the computed family looks right.
4. **No text, stars or badges inside an image.** OCR a cover with `tesseract cover.png -`; any word is
   a fail.
5. **A frame whose stamped `plugin_sha256` is not the commit under review is not evidence.**

## Why this exists

The first run of the audit found the display font unloaded on all four routes while every token and
contract test passed, and the owner's capture showed AI-painted titles ("Asttomamy") and painted star
ratings that no code renders. Tests cannot see pixels; this gate can.
