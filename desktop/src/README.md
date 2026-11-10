# `desktop/src` — the source of the one shipped Desktop module

`desktop/plugin.js` is **generated**. The Hermes Desktop runtime loads exactly one uncompiled
module per plugin and will not resolve relative imports (see the banner at the top of
`00-header.js`), so the source is split into ordered segments here and concatenated, byte for
byte, by `scripts/build_plugin.py`.

```
python3 scripts/build_plugin.py           # rewrite desktop/plugin.js from this directory
python3 scripts/build_plugin.py --check   # verify only; exit 1 if the module drifted
```

No header, separator or trailing newline is added: every byte of `desktop/plugin.js` belongs to
exactly one segment, and `tests/test_plugin_build.py` fails when the committed module is not the
exact concatenation of the committed segments. Editing `desktop/plugin.js` by hand is therefore
always a suite failure — edit a segment and rebuild.

## Segment map

Positions are the file-name prefix; they were cut from `desktop/plugin.js` at master `5bd6074`
(sha256 `4d34c7a0…c34e4`) at existing top-level banners or at a top-level declaration boundary.
The line ranges below are provenance for that split, not a live index; the segment files are the
authority. A cut may only be added where the original module already had a top-level boundary, so
the module keeps one flat top-level scope.

| Segment | Source in master `5bd6074` | What lives there | Usual owner |
|---|---|---|---|
| `00-header.js` | 1–1126 | file banner, the only `import` block, contract-vocabulary mirrors, home preferences, plugin context, `cb.rpc`/`/rest` transport, backend wire, session binding, recovery hooks | sable |
| `10-primitives.js` | 1127–1545 | shell primitives: `EmptyState`, `StatusRow`, `WarningBadge`, `EvidenceLine`, `ErrorLine`, `PageBody`, `SkipToContent`, `BackendUnavailable`, `DegradedBody`, `FirstRun` | vellum |
| `20-packs.js` | 1546–2457 | CB-010 pack intake, trust/rights review, import/export/delete, `CourseMenu`, `CourseRow` | vellum |
| `30-home.js` | 2458–6494 | M2 Field Desk home: home cards, shelf, path, companion, settings, Game header/journal | vellum |
| `32-desk.js` | 6495–7175 | `FieldDeskHome` (pure geometry) and `FieldDesk` (container reads) | vellum |
| `40-courses.js` | 7176–8109 | `CoursesView` and `LibraryView` | vellum |
| `50-create.js` | 8110–9336 | learner create → plan job → plan review | vellum |
| `60-syllabus.js` | 9337–10057 | H-27 syllabus intake/parse/alignment model and controls | vellum |
| `62-syllabus-surfaces.js` | 10058–11141 | the syllabus surfaces (`SyllabusValue` … `SyllabusEntry`) | vellum |
| `70-learning.js` | 11142–14073 | CB-009 workspace core: evidence chips, verdicts, parent observation, practice, attempts, notebook save | vellum |
| `75-tokens.js` | 14074–14671 | Atlas Lamp token layer: `CB_TOKENS_JSON`, type scale, breakpoints, motion ceilings (contract-bound, not a place to invent colours) | sable |
| `80-components.js` | 14672–19387 | v3 primitives and lesson rendering: `CbAction`, `RouteSpine`, `MediaFrame`, pronunciation, block views, Field Quest, procedure, `LessonPlayer`, `SectionPage` | vellum |
| `90-course.js` | 19388–22707 | `OverviewView`, `CourseDetail`, textbook/notebook/quizzes/plan/evidence/sources/export, `LessonPaneBody` | vellum |
| `95-studio.js` | 22708–29638 | Parent Studio, take-home, homework, plan/blueprint/export views, `StudioDetail` | vellum |
| `96-workshop.js` | 29639–31454 | H-196 Workshop: Discover, Library, Provenance (CP-021) | vellum |
| `97-world.js` | 31455–32551 | GM-004 course world and World Studio | vellum |
| `98-page.js` | 32552–33130 | `CoursebookPage` and route composition | vellum |
| `99-tutor.js` | 33131–35443 | GM-012 tutor rail and pane, settings, and the module's single `export {}` test seam | vellum |

## Rules

1. **One writer per segment.** Two cards never edit the same segment file. The generated
   `desktop/plugin.js` is never hand-edited by anyone; it is resolved at merge by regeneration.
2. **Merge by regeneration.** After merging another branch, run
   `python3 scripts/build_plugin.py`, then `python3 -m unittest tests.test_plugin_build`. A
   conflict inside `desktop/plugin.js` is settled by rerunning the build, not by editing hunks.
3. **Cut only at a top-level boundary.** A new segment starts on a banner comment or on a top-level
   declaration/doc comment. `tests/test_plugin_build.py` refuses a segment that starts
   mid-expression.
4. **One import block, one export block.** Static `import` declarations live in `00-header.js`
   only; the named test seam `export {}` stays at the end of `99-tutor.js`.
5. **No behaviour change in a mechanical move.** When moving code between segments, the
   concatenation must stay byte-identical; a behaviour change is its own commit with its own test.
6. **A segment is a fragment, not a module.** Individual segments do not parse on their own
   (`node --check desktop/src/99-tutor.js` fails by design: it exports names that are bound in
   earlier segments). `node --check` and the plugin validator run against the built
   `desktop/plugin.js`; that is the only artifact the runtime loads.
