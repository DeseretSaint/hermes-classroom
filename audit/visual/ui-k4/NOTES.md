# UI-K4 evidence — the approved kit on Workshop and Courses

Module: `desktop/plugin.js` sha256 `b66a40e0caf8a71ea81470d2c8a7d59af0136dd1b79bfa8234ba2ad861398dc4`
(commit `654aaaab`, branch `wt/ui-k4-workshop-kit`). Light scope, device scale factor 1.

| frame | file | sha256 |
|---|---|---|
| Workshop / Discover at 1344x768 | `workshop-1344.png` | `9c982dc701c65bf392cb373e788358706fdf6f3878635884949bed39a6ccb2be` |
| Courses at 1344x768 | `courses-1344.png` | `afa9e47544b3705dc2c1bcf8eb322e8e13baf268b8103846414c15c04331a218` |

## How the frames were made

The shipped module was mounted in jsdom through `scripts/h196-workshop-render.mjs` (the shipped
components, hooks and click handling), then painted in Chromium through Playwright at a 1344x768
viewport. The transport is replayed, not live: `/runtime`, `/workshop/catalog`, `/media/:id` and the
`library.list` envelope come from `audit/visual/h196-workshop/recorded.json`, which
`scripts/h196-workshop-frames.py` records from a real migrated profile database, a real
`pack.import`, and the real media route. So the catalogue, the installed state, the pack covers and
the enrolled course are the product's own data; only the socket is stubbed.

`CoursesView` is now in the module's export list so the frame lane photographs the shipped Courses
route instead of a hand-built shelf.

## What the frames show (measured in the same page, not eyeballed)

- Workshop: three cards, each `data-cb3-cover="art"`, each serving a 1200x800 WebP whose `src`
  begins `data:image/webp;base64,UklGR…`; zero `data-cb3-cover="type"`. Card plates render 303x202.
- Courses: one enrolled course, cover field `data-cb-cover-kind="kit"`,
  `data-cb-cover-plate="japanese-cover-3x2"`, field 1344x120 (the shipped 16:9 field capped at
  7.5rem), `object-fit: cover`; zero `data-cb-cover-kind="letter"`.

The three-pack claim is proved by the unit suites, not by this one-profile capture:
`tests/test_cp_021_workshop_v3.py::test_no_typographic_cover_for_the_three_seeded_packs` and
`tests/test_desktop_course_shelf.py::test_courses_card_serves_the_seeded_packs_own_plate`.

## Not done, on purpose

- `WorkshopHero` did not get a `home-hero` backdrop: it renders `WorkshopCover` as its art column,
  not a flat field, so the card's third scope item does not apply.
- The screens are live only after merge, install and an app restart; the supervisor installs
  `desktop/plugin.js` after merge.
