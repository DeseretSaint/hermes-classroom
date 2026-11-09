# H-179 — Create: choose the shape of the course

Evidence for `docs/FINAL-POLISH-SPEC.md` §6. Plugin pin for this evidence:
`sha256(desktop/plugin.js) = c61cece72c5d01bbd176aa36a827edb0f4acbc2ad8195902e3dfbaf3f5b2902c`
— the same file the M4 audit in `audit/visual/m4-visual/audit.json` is pinned to, and the same
bytes that were installed into the isolated Desktop rig that produced `after/`.

## What changed

- **Step 1 Goal** — one question, four real examples, the honest character help. The course name
  moved behind `Name (optional)` and follows the goal until edited; Continue is enabled by a
  non-empty goal alone (`canAdvance = step === 1 ? goal.trim().length > 0 : Boolean(scope)`).
- **Step 2 Shape** — three route cards (`One lesson`, `Short course`, `Full course`), each with a
  schematic trail (`CbShapeTrail`), a plain consequence, and the facts the plan will honour:
  section band + research depth floor + the existing timing copy. The band is the backend's own
  `SCOPE_EXPECTATIONS[key]["blueprint_objectives"]` (1/1, 3–6, 12–40); a test re-reads
  `coursebook/generation.py` so the copy cannot drift. Selecting a card selects the scope.
  `How you will use it` is one choice (segmented track, or a 2×2 pressed-button block under a
  380px route) with the recipe's own description underneath; `Help me tune it` stays collapsed.
- **Step 3 Review** — a trailhead preview (suggested title, chosen shape, sections, depth, first
  stop) and one sentence about the draft plan and the approval gate. No `StatusRow` wall.
- One primary per step; Back secondary; Cancel tertiary in the same row on every step.
- H-170 preserved: title follows goal until edited, no auto-submit, a rejected seed reopens on the
  first missing answer, `course.create` → `enrollment.create` → one draft plan job under one
  idempotency key, no lesson before approval.
- **Motion setting now has a reader.** `publishCbMotion()` sends the route's effective choice into
  `useCbMotion()`, so the settings sheet's `Reduce motion` reaches every `CbAction` instead of only
  painting `data-cb-motion`. Measured on the rig (CDP, OS media at no-preference): setting
  `Follow system` → `data-cb-motion="full"`, computed `transition: transform, border-color 0.1s`;
  setting `Reduce motion` → `data-cb-motion="reduced"`, computed `transition: none`, `0s`.
  `audit/visual/h179-create/motion.json` holds the two reads.

## How this was produced

Rig: isolated Desktop profile `~/.hermes/coursebook-test-h179/home`, plugin installed at
`desktop-plugins/coursebook/plugin.js` (sha above), CDP on `127.0.0.1:9391`, app shell at
`127.0.0.1:5174`.

```
CB013_CDP_PORT=9391 H179_PHASE=after  node scripts/h179-live.mjs --submit   # after/
CB013_CDP_PORT=9391 H179_PHASE=before node scripts/h179-live.mjs            # before/
```

`before/` is the same driver against the pre-H-179 flow (spine `Goal / Size / Review`, no cards).
`after/h179-live.json` holds every measured state; the PNGs are the same frames.

## Measured in `after/h179-live.json` (fresh run, 34 states)

| fact | value |
| --- | --- |
| spine | `1 Goal · 2 Shape · 3 Review` |
| route widths at 1049/900/460 windows | 407 / 257 / 214 px; `overflowX = 0` on every step, at 200% text too |
| step 1 empty | Continue disabled, `aria-describedby="cb-goal-help"`, title inside the disclosure |
| step 1 goal | Continue enabled, suggested title shown in `Name (optional) — …` |
| step 2 cards | 3 cards, bands `1 section` / `3–6 sections` / `12–40 sections`, depth floor + "several minutes" |
| keyboard | focus on a card, two `ArrowRight` presses moved the selection and the focus ring (`aria-selected="true"` on the new card) |
| reduced motion | `animations: 0`, Coursebook controls with a transition: 0, with an animation: 0 |
| motion setting | `Follow system` → `full` / `0.1s transform`; `Reduce motion` → `reduced` / `none 0s` (see `motion.json`) |
| primary count | 1 per step (`Continue`, then `Create course`); after submit 0 |
| submit | `Create course` → receipt in 1708 ms: "Your plan is being researched…", "Approve the plan to start the first lesson; no lesson is written before that." |

## Gates

```
node --check desktop/plugin.js                                              OK
python3 -m unittest tests.test_desktop_create_flow tests.test_desktop_h174_empty_textbook \
                    tests.test_desktop_h94_single_primary tests.test_desktop_contracts   89 OK
python3 -m unittest tests.test_desktop_control_paths tests.test_desktop_h28_copy \
                    tests.test_desktop_h86_wayfinding tests.test_desktop_h152_motion    83 OK
python3 -m unittest discover -s tests -p 'test_desktop_*.py'              769 OK
python3 scripts/m4v-audit.py  → audit/visual/m4-visual/audit.json         15 claims PASS
                                          pinned to plugin_sha256 c61cece7…, branch wt/h179-create-shape
```

(`tests.test_desktop_h170_goal_first` does not exist in this tree; H-170's rules are carried by
`test_desktop_create_flow` and `test_desktop_control_paths`.)

## Known limits

- The section numbers are the backend's blueprint-objective bands, not a per-run section count:
  the exact count only exists after the plan job returns, so the card states the band it enforces.
- Frames are route-only crops (the window chrome and the terminal panel are the host's).
- The `before/` set shows the same widths/states for comparison; it is not a claim that every
  pre-change state matched one-to-one (the old step 2 had no cards, so its "chosen" frames are the
  selected row).
