# H-147 — Home settings and the default learning view

Branch `wt/h147-home-settings`, open on the H-146 WIP tip `5bf18e8` (which carries H-145's merged
launcher). Evidence frames: `docs/h147-shots/` (4 PNG, one per mode × width) and
`docs/h147-shots/h147-facts.json`, captured from the isolated Electron rig
(`~/.hermes/coursebook-test-h147`, CDP 9381, remote backend `127.0.0.1:44219`, window pid 1059284)
with `scripts/h147-capture.mjs`. The window's own theme chose the host mode; the plugin's
Appearance control chose the painted mode, and the capture records `data-cb-scope`, not a forced
attribute.

## What changed in `desktop/plugin.js`

- **One persisted document, not a route.** `ctx.storage` (the host's namespaced JSON store, the
  VS Code `globalState` analog) keeps `home-preferences.<hermes-profile>`: appearance, default
  presentation mode, sound, reduced motion and a per-classroom override map. There is no settings
  route, no settings tab in Courses and no new profile; the sheet is mounted over `/coursebook`
  and only while open.
- **The sheet.** `HomeSettingsSheet` is a right-hand `role="dialog" aria-modal="true"` panel,
  28.75 rem (460 px) wide with `max-width: 100%`, six sections in a fixed order — Appearance,
  Default view, This classroom, Sound, Haptics, Reduced motion — each with its own `Reset` that is
  disabled at the default. Every control fires on change; there is no Save.
- **Settings open in one interaction from Home.** `HomeDefaultsLine` sits under the page title on
  Home and reads `Default view · Game` (plus `· This classroom · Guided` when an override exists)
  before anything is opened; the adjacent `Settings` control opens the sheet.
- **Haptics is an honest no-op.** The row is disabled, off, and says *"Not available on desktop.
  This build never claims a haptic response, so the control stays off and does nothing."*
- **Sound is real.** With `sound` on, a check verdict plays one short Web Audio tone
  (`cbPlayCheckCue`); it never narrates and never autoplays a media file. Off by default.
- **Reduced motion** is `follow system` by default and forces `data-cb-motion="reduced"` when set.
- **The default view actually opens lessons in that view.** `CoursebookPage` resolves the
  classroom's override first, else the home default, maps it (`game → field_quest`) and threads it
  through `CourseDetail → TextbookView → SectionPage`, whose initial and re-entered view is that
  choice. Textbook remains the floor when a document cannot render the chosen view.
- **Host palette.** When Appearance differs from the host theme, `cbHostVars` maps the host
  variables the SDK rows/buttons/segments read (`--foreground`, `--muted-foreground`,
  `--ui-text-*`, `--ui-bg-*`, `--border`, `--primary`) onto the scoped `--cb-*` table. Without it
  a light sheet inside a dark app kept dark host text and went unreadable (see the first light
  capture, fixed before the committed frames).

## Live facts

| frame | painted scope | window width (CSS) | sheet width | h-overflow | open | sections |
|---|---|---|---|---|---|---|
| h147-light-1049 | light | 1049 | 460 | 0 | 1 click | 6 |
| h147-light-460 | light | 460 | 460 | 0 | 1 click | 6 |
| h147-dark-1049 | dark | 1049 | 460 | 0 | 1 click | 6 |
| h147-dark-460 | dark | 460 | 460 | 0 | 1 click | 6 |

Section order in every frame: `appearance, default-view, classroom, sound, haptics, reduced-motion`;
each `aria-labelledby` resolves to its own `h3` id.

Interaction, from the same run:

- Home before opening: `data-cb-home-defaults="textbook"` (this value was written by the previous
  window and survived the window restart), line reads `Default view · Textbook`.
- Trigger: `aria-haspopup="dialog"`, `aria-label="Open Coursebook settings"`, measured **44 px**.
- Sheet: `role="dialog"`, `aria-modal="true"`, scope label **"On this device"**, copy *"Stored for
  this Hermes profile on this device. Coursebook does not sync these settings to another
  device."*, `saveButtons: 0`, every section Reset measured **44 px**.
- `default-view → Textbook` applies in the same render (control value `textbook`, Home line
  `textbook`) with no Save.
- `classroom → Guided` gives `data-cb-home-override="guided"` and `data-cb-home-effective="guided"`
  while the home default stays `textbook`; the classroom Reset clears the override
  (`homeOverride: null`, `homeEffective: textbook`).
- `sound` toggles off→on and the section Reset returns it to off.
- `reduced-motion → Reduce motion` paints `data-cb-motion="reduced"`.
- Escape closes the sheet and focus lands back on `button[aria-label="Open Coursebook settings"]`.
- Persisted key observed in the renderer: `hermes.plugin.coursebook.home-preferences.default`.
- Sheet scrolls when its content exceeds the window (`scrollHeight 1231 / clientHeight 739` in the
  probe run); measured text contrast in the dark painted mode: section heading **15.01:1**, section
  description **7.85:1**.

## Tests

- `tests/test_desktop_h147_home_settings.py` — **18 tests OK**. It mounts the shipped route in
  jsdom against a *file-backed* stand-in for the host store, so "survives a reload" is proved by a
  second Node process re-importing the module and re-reading the file; it also proves the sanitizer,
  the override rule, Escape/Close focus return, the Tab trap at both ends, immediate apply with no
  Save, the per-profile key, the no-sync copy, and `SectionPage` opening in `field_quest` / `guided`
  / `textbook` when told to.
- Regression: `test_desktop_home_hub`, `test_desktop_lesson_views`, `test_desktop_field_desk`,
  `test_desktop_a11y_structure`, `test_desktop_h94_single_primary`, `test_desktop_h144_pack_rows`,
  `test_desktop_contracts`, `test_desktop_jsx_key_props` — **129 tests OK**.

## Limits

- The sheet's light/dark frames are the *plugin's* painted palette. The host chrome around it keeps
  the window's own theme, which is the rule (`appearance` is a Coursebook preference, not an app
  theme switch).
- `localStorage`-backed `ctx.storage` is device state; there is no account preference API, so the
  copy says "On this device" and makes no sync claim.
- The M4 visual-audit pins are not re-derived here. Any card that changes `desktop/plugin.js` leaves
  `test_m4_visual_audit.test_evidence_is_not_stale_against_the_shipped_module` failing until
  `python3 scripts/m4v-audit.py` re-pins; that pass belongs to the evidence card, not this one.
- Keyboard proof is split: Escape-to-close-and-return-focus was driven live over CDP, while the
  Tab/Shift+Tab trap at both ends of the sheet is proved in the jsdom mount. A live Tab traversal of
  the sheet is not in this capture.
