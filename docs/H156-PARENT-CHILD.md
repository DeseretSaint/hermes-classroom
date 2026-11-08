# H-156 — Parent and child defaults

Branch `wt/h156-parent-child`, based on H-147's tip `9244c69` (the settings sheet and the
per-profile preference document). Evidence: `docs/h156-shots/` (14 frames plus the 200% pair and
`h156-facts.json`), captured from the isolated Electron rig
(`~/.hermes/coursebook-test-h156`, CDP 9382, remote backend `127.0.0.1:44219`, window pid 1123137)
with `scripts/h156-capture.mjs`.

## What the card asked for, and what shipped

| Card requirement | Shipped behaviour |
|---|---|
| Parent Studio stays separate from the learner home | Unchanged and now tested: `hubSlots` drops `recipe: 'parent'` rows before ranking, so a parent plan can never be a classroom slot, a Continue card, or the selected classroom even when it is the newest row. A parent-only profile gets the existing "Parent Studio holds your lesson plans." state, never a first-run plate. |
| Child-safe defaults: no loss-framed reminders, no public leaderboard, no loot/variable reward, no XP/streak pressure | A **Child-safe defaults** section in the one settings sheet lists the four mechanics with the state **Never**. They are stated as facts about this build, not as switches: Coursebook has no reminder scheduler, ranking, random payout or XP store to turn on, and a test scans the shipped copy so the floor cannot quietly become a feature. |
| Session length available | `sessionMinutes` in the same per-profile document: **10 / 15 / 20 / 30 min**, default **15**. It applies on change (no Save), persists, and its own section Reset returns 15. It is named on Home and in Parent Studio, and described as a plan the parent writes, not a countdown. |
| Reduced motion available | Already in the sheet (H-147); unchanged, and still the only motion control. |
| Parent view reports evidence, not XP | The Parent Studio plan header now says *"Parent view · what your child did and what you observed, never points, levels or rankings."* (`data-cb-parent-evidence="parent_reported"`). The observation lane already records `parent_reported`, so the copy matches the data. |
| Parent Studio copy says "prepare a lesson for a child", not "chat as the child" | The landing caption and the brief form's note both open with **Prepare a lesson for a child**; the brief note keeps "no child chat, no child persona and no grading of the child". A copy test refuses `chat as (a\|the) child` and the refused mechanic phrases. |
| No new child profile, COPPA flow or per-child evidence model | None added. The settings are the existing device document keyed by Hermes profile; no account, no second profile id, no backend call. |
| Keep existing parent brief/blueprint/reflection surfaces | Untouched: `StudioBriefView`, `StudioPlanView`, `StudioBlueprintView`, `StudioExportPanel`, `StudioReflectionView` all still render from their own reads. |

## Where the child-safe floor is visible

Two places, so a parent does not have to hunt for Settings:

1. **Home**, in the defaults line under the title:
   `Default view · Textbook · Child-safe defaults · Session · 15 min  [Settings]`
2. **Parent Studio**, under the landing caption, with the same line and the same Settings trigger.

Both mount the same `HomeSettingsSheet`; because only one destination is mounted at a time, the
route's single trigger ref belongs to whichever line is on screen, and Escape/Close returns focus
to that line's own Settings button (proved live from Parent Studio).

## Live facts (rig run)

| frame | painted scope | CSS width | inner width | sheet width | h-overflow (route/sheet/studio) |
|---|---|---|---|---|---|
| h156-home-light-1049 | light | 1049 | 1049 | – | 0 |
| h156-home-light-460 | light | 460 | 460 | – | 0 |
| h156-home-dark-1049 | dark | 1049 | 1049 | – | 0 |
| h156-home-dark-460 | dark | 460 | 460 | – | 0 |
| h156-child-safe-* | light/dark | 1049 / 460 | 1049 / 460 | 460 | 0 / 0 |
| h156-studio-* | light/dark | 1049 / 460 | 1049 / 460 | – | 0 |

PNG size is the window surface at the host's zoom (941 px for a 1049 CSS viewport, 413 px for 460);
the measured CSS widths above come from `window.innerWidth` after calibration, not from the file
size.

Interaction, from the same run:

- Home line before opening: `Default view · Textbook · Child-safe defaults · Session · 15 min`.
- Settings trigger: `aria-haspopup="dialog"`, `aria-label="Open Coursebook settings"`, **44 px**.
- Sheet sections in order: `appearance, default-view, classroom, child-safe, sound, haptics,
  reduced-motion`; every `aria-labelledby` resolves to its own `h3` id; every section Reset **44 px**.
- Child-safe rules: `reminders, leaderboard, rewards, xp`, each `data-cb-child-safe-state="never"`
  and reading *Never*; no colour-only state.
- Session control: four options (10/15/20/30 min) measured **40 px** high, all four inside the
  419 px control at the 460 CSS pane with no wrap or clip.
- Session change: `session-length` 15 → 20 writes
  `hermes.plugin.coursebook.home-preferences.default.sessionMinutes = 20` in the same render; the
  section Reset returns `15`.
- Contrast in the child-safe section (token colours, computed): heading **17.41:1** light /
  **15.01:1** dark; description **7.35:1** / **7.85:1**.
- Parent Studio landing: *"Prepare a lesson for a child. Each brief you write is kept as its own
  plan…"*, then the child-safe line and Settings.
- Keyboard: opening the sheet from Parent Studio focuses its first stop (`Close`); one Tab lands on
  the first section Reset, still inside the sheet (`focusInSheet: true`); Escape closes and focus
  returns to `button[aria-label="Open Coursebook settings"]`.
- Opening a real parent plan (`Open plan`) shows the evidence line above the plan body.
- 200% text at 460 CSS: the Home line and the child-safe section still measure
  `horizontalOverflow: 0`; the four options and four *Never* labels remain inside the sheet
  (`h156-text200-*-dark-460.png`).
- Route line on every frame: `Default view · Textbook · Child-safe defaults · Session · 15 min`
  (Textbook because the preference from the earlier H-147 run survived in this rig's store).

## Tests

- `tests/test_desktop_h156_parent_child.py` — **16 tests OK**:
  - `hubSlots` drops parent rows even when newest, never selects a parent row, leaves a parent-only
    profile with zero slots but `rowTotal > 0`;
  - Home renders the learner classroom and not the parent plan; a parent-only profile gets the
    Parent Studio state;
  - the child-safe section, its four rules and the session choice; the session change and Reset;
  - Parent Studio copy, its child-safe line, the Settings sheet from Studio with focus return, and
    the evidence-not-points line on a real plan;
  - a copy scan that refuses loss/leaderboard/loot/XP phrasing and "chat as the child".
- `tests/test_desktop_h147_home_settings.py` — **18 tests OK** after the additive harness fields
  (`childSafe`, `sessionMinutes`, `childSafeRules`, `parentEvidence`, `bodyText`, `destination`,
  `destination`/`text-click` actions) and the two assertions that name the settings surface's
  contents (section order now includes `child-safe`; the defaults document now includes
  `sessionMinutes: 15`).
- Regression batch — **147 tests OK**: home_hub, field_desk, a11y_structure, lesson_views, h94,
  h144, contracts, jsx_key_props.
- Full `test_desktop_*.py` discover — **517 run, 515 OK, 2 failures**, both reproduced on the base
  commit `9244c69` without this card's changes: `test_desktop_h86_wayfinding`'s
  `role: 'dialog'` ban (H-147's sheet) and `test_desktop_tokens`' exact route-style string
  (H-147's `cbHostVars` spread). They belong to H-147, not to this card.

## Limits

- The session length is a stored intention shown on Home and in Parent Studio; no lesson timer,
  lock or automatic stop reads it. That is deliberate — a countdown would be pressure, and the
  card asked for a default, not a gate.
- The four rules are unswitchable facts, so "child-safe defaults" is not a mode that can be turned
  off. Turning it off would not restore a leaderboard that does not exist, and offering the switch
  would be the lie.
- The M4 visual-audit pins are not re-derived here; any card that changes `desktop/plugin.js`
  leaves the pin test stale until `python3 scripts/m4v-audit.py` runs. That pass belongs to the
  evidence card.
- The rig's PNG scale is the host zoom (see above); the CSS measurements are the calibrated
  `innerWidth` values.
