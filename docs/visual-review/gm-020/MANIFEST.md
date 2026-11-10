# GM-020 — the three invariant repairs: H-149 footer, H-151 wrapper, JSX key contract

Branch `wt/gm-020-fix-invariants`, based on `wt/gm-010-engagement-ui` tip `7412917`
(the tip already carries GM-008 `52e5075`). The worktree the card was dispatched with had been
cut from `master` `00751f0` and did **not** contain GM-008 or GM-010; the branch was moved onto
`7412917` before any edit, which is what the card's base requirement asks for.

- **module**: `desktop/plugin.js`
- **plugin sha256 (implementation)**: `cd45d64781fdb0b54d96f5eefe6fea407c445d58461ea3425881edffa1174563`
- **frames**: `player-footer--1049--dark.png`, `player-footer--1049--light.png` (1049 x 1000 each, verified from each PNG's IHDR)
- **machine-readable**: `live-evidence.json`

## What was red, and is now green

| assertion | before | now |
|---|---|---|
| `test_desktop_h149_lesson_player.PlayerFooterTest.test_the_player_has_exactly_one_footer_primary` | `1 != 0` section footers beside the player | player footer 1, section footer 0 |
| `test_desktop_h151_action_type.ActionSourceTest.test_the_wrapper_is_the_only_place_a_host_default_button_is_built` | `2 != 1` `variant: 'default'` | `1` |
| `test_desktop_jsx_key_props.JsxKeySpreadGuardTest.test_the_plugin_never_puts_key_inside_a_jsx_props_object` | 27 lines | `[]` |

## The fixes

1. **H-149.** The shared section footer is gated on **`page && pageReadable && !playerOnScreen`**
   (`desktop/plugin.js:19327`), so a rendered player never ships `data-cb-section-footer`; its
   `Back to the section index` control is no longer conditional (the gate already excludes that
   case). The take-with-you action did not disappear — it moved into the player's own footer row
   (`data-cb-player-footer`: `Continue | Enter does the same. | Take this with you`). `SectionPage`
   passes it as `player.takeHome`; `LessonDocumentView` forwards it; `LessonPlayer` renders it in
   the footer. Textbook, Guided and Field Quest keep it through the section footer they already
   render, so the action is reachable in every lesson mode with exactly one footer on screen.

   **Why `!playerOnScreen` and not the card's literal `!playerSurface`.** Master gated the section
   footer on `page && document && !playerSurface`; this branch had loosened it to
   `page && pageReadable`. Restoring the literal `!playerSurface` would have fixed the guard by
   deleting the action on every non-`player`-named surface that renders no player footer at all —
   exactly the surfaces (`parentLed` courses, and a page whose block document is empty) where the
   section footer is the *only* place `Take this with you` can live. `playerOnScreen`
   (`playerSurface && !parentLed && document.blocks.length > 0`, `:18886`) is true **iff** a player
   actually mounts: `LessonDocumentView` renders `EmptyState` and `LessonPlayer` returns `null`
   when no step renders, and `player` is `null` for a parent-led course. So the narrower gate
   cannot co-render `data-cb-section-footer` with `data-cb-player-footer`, and it cannot strand
   the action either. This is a deliberate deviation from the card's fix direction, recorded here
   so the merge gate is not told a gate exists that the file does not have.

2. **H-151.** The `I did it` report control is built by `CbAction` with `variant: 'secondary'`
   instead of `sdk.Button` with the host accent. `secondary` matches the same action in
   `HomeworkRecord` and keeps the sheet quiet; `primary` would claim the screen's one lamp field.
   `variant: 'default'` now appears exactly once in the file, in `CB_ACTION_STYLES.primary`
   (`:15080`).

3. **JSX keys.** All 27 sites move `key` out of the props object into the third positional argument
   of `jsx()`/`jsxs()`. No exception list was added to the guard. Where a map call already passed a
   third argument (the source-span `jsxs`), the props key was simply removed.

`tests/test_desktop_gm008_homework_ui.py::test_homework_action_available_in_all_modes` now also
asserts the player-footer mount and the `!playerOnScreen` section gate, so its name no longer
overstates the player case (quill's note on the parent). It is still a source-window assertion for
that case; the behavioural witness for the player is the live frame below.

## Frames: what moved on screen

The player footer row gained one quiet text action at its end. That is a visible composition
change, so two frames are committed rather than a "nothing moved" note.

Captured from an isolated Desktop window (`~/.hermes/coursebook-test-gm020h-014550`, CDP 9372)
against a real `cb.rpc` backend on `127.0.0.1:44219`, never the operator's window or profile.
Driven, not mocked: Coursebook Home → the demonstration course → **Section 2** → **Game** view.
The DOM the captures were taken from reported:

- `[data-cb-player-footer]` count `1`, `[data-cb-section-footer]` count `0`
- `[data-cb-homework-action]` present, `data-variant="text"`, and `footer.contains(action)` true
- exactly one visible `data-variant="default"` control (`Continue`)
- `window.innerWidth` `1049`, route client width `1022`, page overflow `0`, route overflow `0` in both palettes
- painted route background `rgb(19, 18, 16)` (dark) / `rgb(247, 241, 228)` (light)

**Capture geometry.** This disposable window's native widget surface is 941 px wide, so the first
packet's frames measured 941 x 1000 while the DOM and the file names said 1049 — an artifact of
`Page.captureScreenshot` returning the native surface under an emulated layout, not a different
layout. The captures were retaken with
`Emulation.setDeviceMetricsOverride(1049x1000)` plus
`Page.captureScreenshot{clip: 0,0,1049,1000, captureBeyondViewport: true}`, and each PNG's IHDR is
asserted to be exactly 1049 x 1000 after the write (`live-evidence.json` → `capture`). Nothing in
the content changed; only the pixel width of the artifact now matches its label.

| frame | px | root text | palette | player footer | md5 |
|---|---|---|---|---|---|
| player-footer--1049--dark.png | 1049 x 1000 | 16px | dark (host and plugin agree) | `Continue · Enter does the same. · Take this with you` | `5bbbdd0d347b535de1193850026755a4` |
| player-footer--1049--light.png | 1049 x 1000 | 16px | light (explicit Appearance = Light) | same | `e2b9da1cee76f73693db1ee9106180e1` |

### Declared limits

- The light frame is an **explicit** Appearance = Light inside a dark host. The plugin paint is
  light; the quiet host `text` buttons keep host tokens there, so `Take this with you` reads fainter
  than in the dark frame. This is the host-token mapping limit GM-008 already declared (its live
  packet was dark-only for the same reason), not a pixel introduced by this card.
- The backend on 44219 was restarted from the current checkout before capturing: the process that
  was serving that disposable home predated `homework.*`, so the action was `null` there. The
  player-capable home and the homework methods now come from the same live backend; no data was
  fabricated and no fixture stands in for the action.
- No 460 / 200% frames: the card asks for 1049 light and dark only. `docs/visual-review/gm-008/`
  already carries the 460 and 460@200 sheet frames.
- `audit/visual/m4-visual/audit.json` was regenerated with `python3 scripts/m4v-audit.py` because
  any `plugin.js` edit invalidates its `plugin_sha256` pin; verdicts stayed 15 PASS.

## Round 2 corrections (review round 1, quill)

1. The H-149 paragraph named `!playerSurface`; the shipped gate is `!playerOnScreen`. The real
   gate, its definition site and the reason for the deliberate narrowing are now stated above.
2. The frames were 941 px wide under a 1049 label. They are now genuinely 1049 x 1000 and the
   capture method is recorded. No `desktop/plugin.js` change was made in this round — the plugin
   sha256 is unchanged from the reviewed implementation.
