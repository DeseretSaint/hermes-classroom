# GM-010 — Game engagement UI: live proof packet

Captured from the isolated Desktop window (`~/.hermes/coursebook-test-gm010`, CDP 9365) against a
real `cb.rpc` v24 backend on `127.0.0.1:44331`, never the operator's window or profile. The window
was restarted with `scripts/cb013-live-window.sh --restart` after the focus-ring edit, so every
frame below is the shipped module, not a cached renderer.

- **plugin**: `desktop/plugin.js`, sha256 `6e22951ee42b761c2432dac3b84a5de6dacd0ed1d58177f9f4d93f61aa93a302`
- **implementation commit**: the commit that carries this packet on `wt/gm-010-engagement-ui`
  (the plugin sha above is the pin; the renderer was restarted on it before capture)
- **capture script**: `scripts/gm010-live-capture.mjs`
- **frames**: 11, each one `Page.captureScreenshot` of the live window
- **claimed surface**: `[data-cb-course-home]` under `#/coursebook` (verified in the DOM, not inferred
  from the screenshot)

## What was driven, not mocked

1. `courses.presentation_mode = 'game'` was set **in the disposable rig's database** for
   *Japanese at home*. The shipped `course.mode.set` requires an approved world and this rig has no
   image provider, so the mode switch itself was staged; every pixel after it is the live read.
2. `engagement.award` was posted over the wire (`action_kind: homework_completed`,
   `action_id: hwt_3d0da31761974075bfbf3e87318b9c2f`) for the homework task the GM-008 run actually
   completed. It answered `awarded: true, points: 25, xp_total: 25, level 1 Curious`.
3. The shelf card for **Japanese at home** was clicked in the live DOM; the course home rendered the
   Game band from the backend's own `engagement.read` answer:
   `25 XP · Level 1 Curious · cosmetic · Game progress 0 of 4 steps · Play progress, not evidence.`
4. The field journal rendered four section cards from `course.outline`. **None is stamped**: this
   rig has no committed passing attempt, so no section carries independent evidence. No evidence row
   was fabricated to make a stamp appear — a stamped card is render-test-only
   (`tests/test_desktop_gm010_engagement_ui.py::test_no_fake_stars_or_ratings`).
5. Three extra objectives (ordinals 2–4, all `not_started`) were **staged in the rig's database** so
   the journal shows a real multi-card shelf and the bar shows `0 of 4`; the backend's own counts
   produced both numbers.
6. **Light palette** was driven through the plugin's own Appearance control (System / Light / Dark)
   and confirmed by `[data-cb-route][data-cb-scope="light"]` plus a light background read
   (`rgb(247, 241, 228)`) with the XP chip still `rgb(26, 23, 19)` ink on `rgb(232, 169, 58)`.
7. **Keyboard**: with the sheet open, `Input.dispatchKeyEvent` Tab reached the
   `button[role="switch"][aria-label="Show Game feedback"]` on the 20th stop, the plugin-owned
   wrapper reported `data-cb-settings-focus="ring"` and `outline: solid 2px rgb(44, 74, 140)`, Space
   set `aria-checked="false"`, and the band left the DOM. Closing the sheet showed the course home
   with no Game band (`game: null`) while Continue, the objective and the check stayed present. A
   second Tab+Space sequence restored the switch (`aria-checked="true"`) and the band returned
   (`game: "ready"`). The rig was left dark, 1049 px, 100% text, feedback on.

## Frames

| frame | scope | width | root text | game | XP | journal cards | overflow |
|---|---|---|---|---|---|---|---|
| game-home--1049--dark.png | dark | 1049 | 16px | ready | 25 | 4 | no |
| game-home--900--dark.png | dark | 900 | 16px | ready | 25 | 4 | no |
| game-home--460--dark.png | dark | 460 | 16px | ready | 25 | 4 | no |
| game-home--460--200--dark.png | dark | 460 | 32px | ready | 25 | 4 | no |
| game-home--1049--light.png | light | 1049 | 16px | ready | 25 | 4 | no |
| game-home--900--light.png | light | 900 | 16px | ready | 25 | 4 | no |
| game-home--460--light.png | light | 460 | 16px | ready | 25 | 4 | no |
| game-home--460--200--light.png | light | 460 | 32px | ready | 25 | 4 | no |
| game-feedback-focus--1049--light.png | light | 1049 | 16px | sheet open, switch ringed | 25 | 4 | no |
| game-feedback-off--1049--light.png | light | 1049 | 16px | absent (`game: null`) | — | 4 | no |
| game-feedback-restored--1049--light.png | light | 1049 | 16px | ready | 25 | 4 | no |

Every frame recorded `continueVisible`, `objectiveVisible` and `checkVisible` as true, and a
forbidden-word scan (`mastery`, `mastered`, `proficien`, `verified skill`, `star rating`,
`5 stars`, `rating`, `out of 5`) over the whole route returned `[]`.

The 460 @ 200% frames keep `continueVisible/objectiveVisible/checkVisible` true in the DOM but the
trail sits below the first viewport at 32px text — that is scroll, not clipping, and the document
reported no horizontal overflow.

md5:

```
0f7f39461b74b91669ccf4abd993245e  game-home--1049--dark.png
739984c539d1dcb742e02b72e242d0a3  game-home--900--dark.png
8892d62a62c1ab3d52c4746100e80039  game-home--460--dark.png
e407c8a5d5aa9f63b2ec809e0b513cd0  game-home--460--200--dark.png
9ecdf36a0fde48b6e2aa4bf73fad7956  game-home--1049--light.png
859de15904c573f766c091618d7c1ecd  game-home--900--light.png
e561138f96bd46a5bedfc134e39aef8c  game-home--460--light.png
d527a7497f8b6a96891acabfafd092bc  game-home--460--200--light.png
9ebf70665079d86dd2face5c3b222611  game-feedback-focus--1049--light.png
6e20d88d27d543f00dc0bc18bf06b8b7  game-feedback-off--1049--light.png
cbee7eeb5edc9089df372b4e7355112d  game-feedback-restored--1049--light.png
```

## Known gaps (declared, not hidden)

- **Stamped cards are render-test-only.** The rig has no committed passing attempt, so all four
  live cards read their true state (`Not started`) and the summary says
  `No section is stamped yet.` The earned-card treatment is proven by
  `test_no_fake_stars_or_ratings`, not by a frame.
- **Textbook, Guided and Parent Studio absence is render-test-only.** `test_game_xp_not_in_textbook`
  scans `TextbookView`, `SectionPage`, `NotebookView` and `QuizzesView` for `GameHeader`,
  `GameJournal`, `engagement.read`, ` XP` and `Game progress`, and `test_game_header_only_in_game`
  pins the two mounts. No live non-Game frame is carried here because this rig's course is Game.
- **Sound is host-owned.** The Game layer plays nothing; the existing `Check cue sound` preference
  is the only audio control and it is untouched by this card.
- **The Game band sits above the course path on this surface.** With the world unapproved the
  reviewer sees the band above the world notice and `CONTINUE THE TRAIL`; the trail, its objective
  and its check remain the largest content and were present in every frame.
- The field journal stays visible when `Game feedback` is off. The switch's own description names
  exactly what it hides — XP, level and the progress bar — and the journal cards record sections,
  not play score, so hiding them would misstate what was turned off.
