# GM-020 — the three invariant repairs: H-149 footer, H-151 wrapper, JSX key contract

Branch `wt/gm-020-fix-invariants`, based on `wt/gm-010-engagement-ui` tip `7412917`
(the tip already carries GM-008 `52e5075`). The worktree the card was dispatched with had been
cut from `master` `00751f0` and did **not** contain GM-008 or GM-010; the branch was moved onto
`7412917` before any edit, which is what the card's base requirement asks for.

- **module**: `desktop/plugin.js`
- **plugin sha256 (implementation)**: `cd45d64781fdb0b54d96f5eefe6fea407c445d58461ea3425881edffa1174563`
- **frames**: `player-footer--1049--dark.png`, `player-footer--1049--light.png`
- **machine-readable**: `live-evidence.json`

## What was red, and is now green

| assertion | before | now |
|---|---|---|
| `test_desktop_h149_lesson_player.PlayerFooterTest.test_the_player_has_exactly_one_footer_primary` | `1 != 0` section footers beside the player | player footer 1, section footer 0 |
| `test_desktop_h151_action_type.ActionSourceTest.test_the_wrapper_is_the_only_place_a_host_default_button_is_built` | `2 != 1` `variant: 'default'` | `1` |
| `test_desktop_jsx_key_props.JsxKeySpreadGuardTest.test_the_plugin_never_puts_key_inside_a_jsx_props_object` | 27 lines | `[]` |

## The fixes

1. **H-149.** The section footer's gate is `page && pageReadable && !playerSurface` again, so a
   rendered player never ships `data-cb-section-footer`; its `Back to the section index` control is
   no longer conditional (the gate already excludes that case). The take-with-you action did not
   disappear — it moved into the player's own footer row
   (`data-cb-player-footer`: `Continue | Enter does the same. | Take this with you`). `SectionPage`
   passes it as `player.takeHome`; `LessonDocumentView` forwards it; `LessonPlayer` renders it in
   the footer. Textbook, Guided and Field Quest keep it through the section footer they already
   render, so the action is reachable in every lesson mode with exactly one footer on screen.
2. **H-151.** The `I did it` report control is built by `CbAction` with `variant: 'secondary'`
   instead of `sdk.Button` with the host accent. `secondary` matches the same action in
   `HomeworkRecord` and keeps the sheet quiet; `primary` would claim the screen's one lamp field.
3. **JSX keys.** All 27 sites move `key` out of the props object into the third positional argument
   of `jsx()`/`jsxs()`. No exception list was added to the guard. Where a map call already passed a
   third argument (the source-span `jsxs`), the props key was simply removed.

`tests/test_desktop_gm008_homework_ui.py::test_homework_action_available_in_all_modes` now also
asserts the player-footer mount and the `!playerSurface` section gate, so its name no longer
overstates the player case (quill's note on the parent).

## Frames: what moved on screen

The player footer row gained one quiet text action at its end. That is a visible composition
change, so two frames are committed rather than a "nothing moved" note.

Captured from an isolated Desktop window (`~/.hermes/coursebook-test-gm020h-*`, CDP 9372) against
a real `cb.rpc` backend on `127.0.0.1:44219`, never the operator's window or profile. Driven, not
mocked: Coursebook Home → the demonstration course → **Section 2** → **Game** view. The DOM the
captures were taken from reported:

- `[data-cb-player-footer]` count `1`, `[data-cb-section-footer]` count `0`
- `[data-cb-homework-action]` present, `data-variant="text"`, and `footer.contains(action)` true
- exactly one visible `data-variant="default"` control (`Continue`)
- route overflow `0` at 1049 in both palettes

| frame | width | root text | palette | player footer | md5 |
|---|---|---|---|---|---|
| player-footer--1049--dark.png | 1049 | 16px | dark (host and plugin agree) | `Continue · Enter does the same. · Take this with you` | `271dcee24c89deada584fd231e2f817f` |
| player-footer--1049--light.png | 1049 | 16px | light (explicit Appearance = Light) | same | `a4838d2bc8fc0e1212b2029b27218c3c` |

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
