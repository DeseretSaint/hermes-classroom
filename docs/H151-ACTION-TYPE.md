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
| courses | New course | 44 px | 44 px | lamp / on-lamp |

**H-160 correction.** At `fc16813` this table's Courses row read `none — primaryCount: 0`, and the
section below argued the catalog had no single next step to fill. That was the wrong reading of
UX_SPEC §4, which names the Courses page-header primary explicitly ("Courses: **New course**
primary; Import pack in Library/overflow"). H-151 had left the call site at `variant: 'secondary'`,
and "at most one primary" cannot catch a defect of omission. On `wt/h160-h151-followups` the button
is `variant: 'primary'` behind the same eligibility check (`!coursesEmpty && !openCourse`), so the
catalog carries exactly one lamp and the welcome still owns the only one on an empty profile.
Measured: `courses primaryCount: 1` at 1049/900/460 (§8).


The render contract lives in `tests/test_desktop_h151_action_type.py` (17 tests on this branch; 14 at
`fc16813`, `Ran 14 tests`, `OK`). The hand-counted claims, by method name:

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
| route overflow | `routeOverflowX: 53` at H-151 → **`0` after H-160** (§8) |

That last number is real and was not a pass at `fc16813`: at a 32 px root in a 460 px window the
section surface measured 53 px wider than its own client box
(`route.scrollWidth - route.clientWidth`), i.e. the pane scrolled horizontally. The document itself
does not overflow, so a `body`-level check would have missed it. H-160 fixed it at the source and
re-measured `0`; §8 names the three unbreakable tokens and their replacements.


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
- **The 200% residual.** `routeOverflowX: 53` on the section route at 460 / 32 px root was recorded
  and unfixed at `fc16813`; H-160 fixed it at the source and re-measured `0` (§8). What H-160 does
  *not* fix: at a 32 px root the reading column itself (`[data-cb-main]`, `overflow: auto`) still
  scrolls sideways by 163 px for tabular evidence rows and nowrap chips. At 100% text at 460 px that
  column fits exactly (`185 / 185`). The route-level claim — the number this card accepts — is `0`.
- **Courses had no primary** at `fc16813` (§3); H-160 made the UX_SPEC §4 "New course" action the
  catalog's one lamp and pinned it in the render test.
- **No before-frames.** `docs/h151-shots/` is the after-state only. The before numbers in this
  document are source counts from `git show 6f43cc4`; no before pixels were captured, so no claim
  here about how the old route *looked* is measured.

## Gates at `fc16813`

- `python3 -m unittest tests.test_desktop_h151_action_type` → `Ran 14 tests in 5.041s`, `OK`.
- `node --check desktop/plugin.js` → clean (unchanged by this doc commit).
- Working tree clean at `fc16813` before this document was added; this digest is the only change in
  its own commit.

## 8. H-160 follow-up: the two measured defects

Both numbers below are from the isolated rig (`~/.hermes/coursebook-test-h151`, CDP 9371) running
this branch's `desktop/plugin.js`, re-captured with `scripts/h151-action-capture.mjs` after the fix.
The script now prints `routeOverflowX` for every surface and for the 200% frame, so the acceptance
number is read from the tool rather than from this table. The unedited capture output is
`docs/h160-shots/h160-facts.json` (provenance in that directory's `README.md`); it is a second bundle
so the `fc16813` before-state in `docs/h151-shots/` stays intact.

| fact | before (`fc16813`) | after (H-160) |
|---|---|---|
| Courses `primaryCount` at 1049 / 900 / 460 | 0 / 0 / 0 | **1 / 1 / 1** (`New course`) |
| section route `text200.routeOverflowX` at 460 / 32 px root | **53** | **0** |
| section reading column `[data-cb-main]` at 460 / 16 px root | scrolled (breadcrumb 790 px) | **0** (`185 / 185`) |
| every other surface `routeOverflowX` (15 frames) | 0 | 0 |

**What actually overflowed.** The route pane at a 460 px window is 215 px wide (170 px of content);
three unbreakable tokens were wider than that:

1. the header wordmark, `COURSEBOOK` at 28 px + `0.14em` tracking = **239 px** — it alone accounts
   for the 53 px (`22.4` px padding + 239 = 261 vs 215);
2. the page title, `Course` at the display step = 72 px at a 32 px root ≈ 220 px;
3. the section breadcrumb, the course title in a host `variant: 'text'` button whose own classes are
   `shrink-0 whitespace-nowrap` = **790 px** — it made the reading column scroll at 460 px even at a
   16 px root.

The fixes are at the source, not masks: the two header tokens now declare
`overflowWrap: 'anywhere'` + `minWidth: 0` (and the title `maxWidth: '100%'`), and the breadcrumb is
a `CbAction tertiary` that declares `whiteSpace: 'normal'`, `flexShrink: 1`, `maxWidth: '100%'`.
There is no `overflow-x: hidden` anywhere in the change; the only clipping element is the reading
column's own `overflow: auto`.

**Tests that now pin it** (`tests/test_desktop_h151_action_type.py`, `Ran 17 tests`, `OK`):

| claim | method |
|---|---|
| Courses carries exactly one primary, `New course`, lamp fill, 44 px, at 1049/900/460 | `test_courses_carries_exactly_its_new_course_primary` |
| an empty catalog keeps exactly one primary (the welcome's) and drops the header action | `test_the_empty_catalog_keeps_exactly_one_primary` |
| the section route's widest tokens declare wrapping (wordmark + title `anywhere`; breadcrumb is a wrapping `CbAction`) | `test_the_section_route_wraps_its_widest_tokens_at_460_200_percent` |

`tests/test_desktop_h86_wayfinding.py::test_new_course_is_the_catalog_primary_and_yields_to_a_course`
is the same acceptance read from the other direction: it used to assert `variant: 'secondary'` and
now asserts the primary while keeping the "an open course owns the only primary" yield rule.

**Acceptance changed, not pixels:** no. UX_SPEC §4 already named "New course" the Courses primary;
H-151's "there is no single next step" note was wrong and is corrected in §3 above.

**Known suite state.** `tests/test_m4_visual_audit.py::test_evidence_is_not_stale_against_the_shipped_module`
now fails by design on this branch: `plugin.js` changed (`71017857…`) and this card must not
regenerate `audit/visual/m4-visual/`. H-158 (`t_9f20ed21`) re-pins M4 once after the batch union; that
failure is expected here and is not a regression in any surface.

