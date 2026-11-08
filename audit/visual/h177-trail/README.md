# H-177 visual evidence — the trail

Generated from the module under test, not hand-made frames.

- `before/` — the base module at `80eecce` (`git show 80eecce:desktop/plugin.js`), same pipeline.
- `after/` — this branch's `desktop/plugin.js`.
- `live/` — the isolated Desktop rig (`~/.hermes/coursebook-test-h177`, CDP 9381) driving the real
  backend.

Each frame set is produced and measured by the same two commands:

```bash
python3 scripts/h177-path-frames.py --plugin <plugin.js> --out <dir>
node scripts/h177-path-shot.mjs <dir>
```

`<dir>/evidence.json` carries marker centres, marker boxes, segment boxes, stroke widths,
line-to-marker alignment, gate/halo/detail counts, focus state and overflow. `shots/*.png` are the
painted frames.

`live/`:

```bash
COURSEBOOK_TEST_STATE=$HOME/.hermes/coursebook-test-h177 CB013_CDP_PORT=9381 \
  bash scripts/cb013-live-window.sh --restart
CB009_CDP_PORT=9381 node scripts/h177-live-check.mjs
```

`live/live-check.json` records the route width, layout, centres, sizes, alignment, gates, halo,
detail lines, keyboard Tab order, the Enter destination and the reduced-motion posture.

Frame list (both sets): 1049/900/460 light and dark, 200% text at 460 and dark 1049, state matrix
(light 1049, dark 460), no-estimate header, keyboard frame, reduced-motion frame.

The module sha pinned by this evidence: `6aeca2214aed058aec08688fdd12eeb73003c18fa0bc8f9b122564ec1fbf6d4f`.
