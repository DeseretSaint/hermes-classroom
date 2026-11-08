# H-91 — the two H-85 gate blockers, fixed and re-measured

Status: fixes applied on top of the shipped `7d0f9cf` (the commit the H-85 gate failed).
Owner: Quill. Nothing published, tagged or submitted.

The gate's verdict and its P2/P3 debt live in `docs/UX-VERIFICATION-V2.md` on `h85-gate`; this file
records only what changed and what was measured afterwards.

## V2-1 (P0) — the section route no longer crashes on a null runtime

`SectionPage` renders the no-chat sentence unconditionally (H-86), but `data-cb-detached` still read
`runtime.binding_status`. `page.runtime` is `null` whenever the section has no runtime read, so the
render threw and the host replaced the whole route with its error boundary.

The attribute now degrades exactly like the rest of the component:

```js
'data-cb-detached': (runtime && runtime.binding_status) || 'detached',
```

The sentence stays unconditional and the one live action stays `start` (never `resume`) when there is
no chat.

Regression test: `tests/test_desktop_lesson_views.py::
LessonViewRenderTest::test_a_section_with_a_null_runtime_renders_instead_of_throwing`.
It mounts the shipped module through `react-dom/server` with `page.runtime === null`, so a throw is a
non-zero exit. Reverting the guard makes that test fail with
`Cannot read properties of null (reading 'binding_status')` — checked, not assumed.

## V2-2 (P1) — the Library header no longer clips

The route header's action group was `flex shrink-0 flex-wrap …`: `flex-shrink: 0` meant the group
kept its 239 px content width inside a 174 px header at a 460 px window, so the route overflowed by
19 px at 900 and 45 px at 460 (the `sw 239 / cw 174` row in the gate's `crash-lib.log`).

The group is now shrinkable (`flex min-w-0 flex-wrap …`), so the two actions wrap onto their own rows
instead of pushing the route wider than its pane.

## V2-4 (P2, fixed because it was cheap) — one primary on Parent Studio

The route header repeated the "New lesson plan" primary that the studio landing plate already
carries. The header copy is removed; the in-page primary remains, and the empty state still has one.

V2-3 (no `h1`), V2-5 (desk stat strip), V2-6 (type scale) and the host-owned V2-7/V2-8 are untouched
and remain named debt for Atlas to accept.

## Measurements after the fix

Live Hermes Desktop window on CDP 9337, plugin served from this tree through the dedicated test rig
(`~/.hermes/coursebook-test/home/plugins/coursebook`), widths 1049 / 900 / 460 CSS px (`innerWidth`
1048 / 899 / 459). Driver: `scripts/h91-verify.mjs`; frames and per-frame JSON:
`audit/ux/round3/h91/`.

| check | 1049 | 900 | 460 |
|---|---|---|---|
| section route renders, no error boundary, `[data-cb-section-actions]` present | PASS | PASS | PASS |
| Library `route.scrollWidth − clientWidth` | 0 | 0 | 0 |
| Library body overflow | 0 | 0 | 0 |

Both themes were run separately (`--dark` emulates `prefers-color-scheme: dark` and adds the host
`dark` class); both are PASS on every row above. Parent Studio reports exactly one primary
(`New lesson plan`).

Before/after on the same harness: pointing the rig at the untouched `7d0f9cf` tree makes the same
script fail all three section widths with `failed to render` and no section controls
(`audit/ux/round3/h91-before/`), so the pass is caused by the fix, not by the harness.

## Static gates

- `node --check desktop/plugin.js` — OK
- `python3 -m unittest discover -s tests -t .` — 1674 tests, OK (skipped=1)
- `bash scripts/validate-plugin.sh` — 3/3 on the committed HEAD
- `python3 scripts/m4v-audit.py` — 15 PASS, 0 not PASS; M4 re-pinned to the new plugin sha
- `python3 scripts/m4v-repro-check.py` — two runs, 62/62 identical frames and screenshots
