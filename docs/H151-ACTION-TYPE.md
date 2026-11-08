# H-151 — action and type system: before/after digest

Branch `wt/h151-action-type`. Before: `6f43cc4` (merge of H-145 into this branch).
After: `fc16813` — "H-151: CbAction primitive, one type hierarchy and the H-151 render contract".
`sha256sum desktop/plugin.js` at `fc16813` =
`ee7010ebef8498b157e8405cf1864faf8b21ffb7e042b5a5f5acc0eb6642590d`.

Live evidence: `docs/h151-shots/` — 20 PNG plus `h151-facts.json`, captured by
`scripts/h151-action-capture.mjs` from the isolated Electron rig on CDP port 9371 against
`http://127.0.0.1:5174/#/coursebook`, dark scope, at 1049 / 900 / 460 px, plus a 200% text frame and
one keyboard frame. Every number below is either a `git show` count run on those two commits, a
field in `h151-facts.json`, or a line of the 14-test output.

The question this card answers is the one the parent asked: did the Coursebook route stop
inheriting the settings-page control language, and is there now one type hierarchy instead of six
ad-hoc sizes?

## 1. Default-variant call sites: 44 → 1

The host accent fill is `variant: 'default'` on `sdk.Button`. Counted with
`git show <rev>:desktop/plugin.js | grep -o "variant: 'default'" | wc -l`:

| rev | occurrences | lines |
|---|---|---|
| `6f43cc4` (before) | **44** | 44 |
| `fc16813` (after) | **1** | 1 |

The single survivor is line 9354 of the shipped module, inside `CB_ACTION_STYLES.primary`. It is not
a call site a surface can reach: `CbAction` reads `CB_ACTION_STYLES[kind].variant` and passes it to
`sdk.Button` itself, so no view names a host variant.

What the wrapper does with it, from the `CbAction` body at `fc16813`:

- `CB_ACTION_VARIANTS` is frozen to exactly `['primary', 'secondary', 'tertiary', 'row']`.
- Any unrecognised `variant` falls back to `secondary` — a typo cannot silently become a host button.
- `delete rest.size` removes the host size knob, so a caller cannot shrink a primary.
- For `primary` it keeps the host `default` slot (so the SDK's own pressed/disabled wiring still
  applies) but overrides the paint with `--cb-lamp` / `--cb-on-lamp`, `minHeight: '44px'` and
  `fontSize: CB_TYPE.body`.
- A disabled primary is repainted to `--cb-paper` / `--cb-ink-soft` / `1px var(--cb-rule)` — a
  disabled primary must not still look like an invitation.

Variant inventory in the shipped module, `git show fc16813:desktop/plugin.js | grep -oE "variant: '[a-z]+'" | sort | uniq -c`:
`primary 42`, `secondary 87`, `tertiary 19`, `row 1`, `default 1`, plus host-level `outline 22`,
`muted 21`, `text 54`, `ghost 6`, `warn 4`, `destructive 1`. Only the Coursebook four are reachable
from a Coursebook view.

## 2. One display h1, PlateHead at heading

`h151-facts.json`, dark, six core surfaces at three widths. h1 is `CB_TYPE.display`
(clamp 2.25–2.5 rem) and PlateHead h2 is the heading step; both are rem-derived, so they move with
the root font.

| surface | h1 text | h1 @1049 | h1 @900 | h1 @460 | PlateHead h2 | PlateHead text |
|---|---|---|---|---|---|---|
| home | Home | 37.7485 px | 36.702 px | 36 px | 24 px | "H103 live reject check" |
| courses | Courses | 37.7485 px | 36.702 px | 36 px | 24 px | "All courses" |
| course-detail | Course | 37.7485 px | 36.702 px | 36 px | 24 px | "1 section", "Recent evidence" |
| library | Library | 37.7485 px | 36.702 px | 36 px | 24 px | "Packs on this profile" |
| section | Course | 37.7485 px | 36.702 px | 36 px | — (none) | — |
| studio | Parent Studio | 37.7485 px | 36.702 px | 36 px | 24 px | "Plans for your child" |

h1 count is 1 on every one of the 18 measured surfaces; `zeroSizedControls` is `[]` everywhere.

The 37.75 px is root-relative, not a magic number: 37.7485 / 16 = 2.359 rem, 36.702 / 16 = 2.294 rem,
36 / 16 = 2.25 rem — the clamp's floor. Set the root to 32 px and the same token renders 72 px, which
is exactly what the 200% frame measures (§4). The plate h2 stays 24 px = 1.5 rem at a 16 px root and
48 px at a 32 px root. Nothing between the two is display-sized.

Course Detail and Section both read "Course": Course Detail keeps the course name at h2, so the page
label never repeats a card title.

## 3. Actions: one lamp per surface, four targets

Measured primaries in `h151-facts.json` (`primaries[]`, `primaryCount`):

| surface | primary | measured height | minHeight | paint |
|---|---|---|---|---|
| home | Review the plan | 44 px | 44 px | `rgb(239, 192, 107)` on `rgb(19, 18, 16)` |
| course-detail | Start a fresh run | 44 px | 44 px | lamp / on-lamp |
| library | Import pack | 44 px | 44 px | lamp / on-lamp |
| section | Record observation | 44 px | 44 px | lamp / on-lamp |
| studio | New lesson plan | 44 px | 44 px | lamp / on-lamp |
| courses | **none** — `primaryCount: 0` | — | — | — |

Two honest deviations from a flat reading of "one primary per core surface":

- **Courses renders zero primaries.** The catalog's only actions are row and tertiary controls;
  there is no single next step to fill. The live frames and the render test agree, because the test
  pins *at most* one, not *exactly* one.
- "one per surface" is therefore a property of the five task surfaces, not of the catalog. If the
  catalog is supposed to grow a primary (e.g. "Add course"), that is a design decision for the
  owning card, not something H-151 can assert today.

The render contract lives in `tests/test_desktop_h151_action_type.py` (14 tests, `Ran 14 tests`,
`OK`). The hand-counted claims, by method name:

| claim | test method |
|---|---|
| exactly four variants, frozen | `ActionSourceTest.test_one_wrapper_with_exactly_four_variants` |
| exactly one `variant: 'default'`, and the table precedes the wrapper | `ActionSourceTest.test_the_wrapper_is_the_only_place_a_host_default_button_is_built` |
| primary fill is `--cb-lamp` / `--cb-on-lamp` at `minHeight: 44px` | `ActionSourceTest.test_primary_fill_is_the_lamp_and_never_the_host_accent` |
| at most one primary per surface, at 1049/900/460 | `ActionRenderTest.test_no_core_surface_carries_two_primaries` |
| the primary is the lamp field at 44 px (disabled → `--cb-paper`) | `ActionRenderTest.test_the_primary_is_the_lamp_field_at_44_px` |
| 44 / 44 / 24 / 44 floors for primary / secondary / tertiary / row | `ActionRenderTest.test_every_variant_meets_its_target` |
| nothing authored below the 24 px absolute floor | `ActionRenderTest.test_every_authored_action_stays_above_the_24_px_floor` |
| row is full-width and left-aligned | `ActionRenderTest.test_the_row_variant_is_full_width_and_left_aligned` |
| no control measures 0×0 / every action declares a target | `ActionRenderTest.test_no_measurement_is_zero_by_zero` |
| Codicon is 16 px (`CB_ICON_UI`) or 20 px (`CB_ICON_PLATE`) only | `ActionSourceTest.test_codicon_sizes_are_16_or_20_only`, `ActionRenderTest.test_every_codicon_is_sixteen_or_twenty` |

The sizes appear once in the table above and once in the test; the screenshots are not offered as a
second proof of the same number.

Type claims, same file: `ActionRenderTest.test_the_route_h1_is_the_only_display_heading` (source
count of `fontSize: CB_TYPE.display` is 1, every surface has 0 or 1 h1, the h1 carries
`data-cb-page-title`, and no non-h1 heading reaches 36 px) and
`ActionRenderTest.test_plate_heads_are_heading_not_display` (every `plateHead` heading is exactly
24 px).

## 4. 460 px and 200% text

Nine `*-460.png` frames exist (one per core surface; 18 frames total across the three widths), so
narrow width is captured, not inferred: `home`, `courses`, `course-detail`, `library`, `section`,
`studio` at 460, 900 and 1049 in dark.

200% text **was** captured live — `docs/h151-shots/text200-dark-460.png`, measured in
`h151-facts.json` under `text200`. Method, from `scripts/h151-action-capture.mjs`: set
`documentElement.style.fontSize = '32px'` (a doubled root, i.e. text scaling — not browser zoom),
calibrate the window to `innerWidth: 460`, re-measure.

| field | value |
|---|---|
| destination measured | section route (h1 "Course", primary "Record observation"), 460 px |
| h1 | 72 px (2.25 rem × 32 px root) |
| primaries | 1, "Record observation", 58.2 px tall, `minHeight: 44px`, 32 px label |
| `zeroSizedControls` | `[]` — no control collapses |
| `documentElement` overflow | `overflowX: 0` |
| route overflow | **`routeOverflowX: 53`** |

That last number is real and is not a pass: at a 32 px root in a 460 px window the section surface is
53 px wider than its own client box (`route.scrollWidth - route.clientWidth`), i.e. the pane scrolls
horizontally. The document itself does not overflow, so a `body`-level check would have missed it.
Recorded here rather than smoothed over; it needs its own fix card, and H-152 (motion/responsive) is
the natural owner. Before it is claimed fixed, re-capture this frame and expect `routeOverflowX: 0`.

What the tests assert about scaling instead of a live frame: the H-151 render test does not run at a
doubled root. The root-relative half is pinned in `tests/test_desktop_tokens.py` by
`test_the_reading_typography_scales_with_the_root_font`, which refuses any `font-size: <n>px` in the
shipped CSS (`assertNotRegex(html, r"font-size:\s*\d+px")`) — the route's type has to be rem-derived
or that test fails. Between the two: the token test guarantees the scale *can* follow the root, the
live frame shows it *does*, and the same frame records the 53 px residual.

## 5. Keyboard and focus

`docs/h151-shots/keyboard-dark-1049.png`, from the keyboard step of the capture script (Tab until a
Coursebook action takes `:focus-visible`, measured on the Home route at 1049):

- focused control: `Retry`, a `tertiary` action, 36 × 24 px, transparent background,
  `color: rgb(245, 239, 225)` — it keeps its quiet paint while focused;
- `focusVisible: true`, and the capture's `ring: true`;
- computed `outline: none 1.1156px rgb(238, 238, 238)` — the host's `focus-visible:outline-hidden`
  is in force, so the outline is *not* what is visible;
- the visible ring is the 3 px shadow in the box-shadow stack,
  `oklab(0.638022 -0.0233847 -0.190333 / 0.5) 0px 0px 0px 3px` — the SDK's
  `focus-visible:ring-[0.1875rem] ring-ring/50`, translated into the Coursebook palette.

Honest limit on "what the test pins": **the H-151 render test does not assert focus.** It pins
targets, fill and type only. Focus evidence for this control is the live capture; the suite's
focus assertions are elsewhere (`tests/test_desktop_a11y_structure.py` pins the skip link as the
first focus stop, and `test_m4_visual_audit.test_the_keyboard_walk_counts_controls_not_key_presses`
counts focusable controls). A jsdom assertion for this ring would be a fair follow-up, not something
to claim today.

## 6. The token rule still holds

Two tests, different scopes:

- `tests/test_desktop_tokens.py::test_no_colour_literal_outside_the_token_table` removes the token
  table from `desktop/plugin.js` and then fails on any `#[0-9a-fA-F]{3,8}` left behind: raw hex
  outside the table is a suite failure, on every surface, not just a style preference. The same file
  keeps `test_no_decorative_gradients` (no `gradient(` in the module) and
  `test_the_shipped_table_equals_the_contract` (the shipped table must equal
  `coursebook/tokens.json`).
- `tests/test_desktop_h151_action_type.py::ActionRenderTest.test_no_core_surface_renders_a_host_blue_default_button`
  renders all six surfaces at 1049/900/460 and fails on any `variant: 'default'` button that has no
  Coursebook `action` — i.e. any host-accent button the wrapper did not paint. `hostDefaultCount` is
  `0` on all 18 measured live surfaces as well, so the render test and the rig agree.

## 7. What this does not prove

- **Installed-Desktop pixels.** Everything here comes from the isolated Electron rig on CDP 9371
  (`~/.hermes/coursebook-test-h151`), rendering the same module. It is not the operator's installed
  Desktop profile with its own plugin copy, its own window chrome and its own zoom. The render test
  says the same thing in its docstring. Confirming the painted result in the installed app is a
  separate check.
- **The M4 pin is branch-local.** The M4 captures were regenerated in this worktree and
  `audit/visual/m4-visual/audit.json` `plugin_sha256` points at `fc16813`'s module. That pin is valid
  on `wt/h151-action-type` only; it is superseded by the batch union (H-158) and must be regenerated
  there, not carried forward.
- **The 200% residual.** `routeOverflowX: 53` on the section route at 460 / 32 px root is recorded
  and unfixed by this card.
- **Courses has no primary** (§3) — the "one primary per surface" target is met on five surfaces and
  is vacuously true (not "met") on the catalog.
- **No before-frames.** `docs/h151-shots/` is the after-state only. The before numbers in this
  document are source counts from `git show 6f43cc4`; no before pixels were captured, so no claim
  here about how the old route *looked* is measured.

## Gates at `fc16813`

- `python3 -m unittest tests.test_desktop_h151_action_type` → `Ran 14 tests in 5.041s`, `OK`.
- `node --check desktop/plugin.js` → clean (unchanged by this doc commit).
- Working tree clean at `fc16813` before this document was added; this digest is the only change in
  its own commit.
