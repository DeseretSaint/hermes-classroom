# CB-049 — Final visual polish pass against DESIGN.md

Scope: Coursebook route, sidebar entry, lesson pane, Textbook, Notebook, Quizzes, Library and
Parent Studio. Source of truth: `apps/desktop/DESIGN.md` in the Hermes Desktop fork
(`/home/deseretsaint/Projects/hermes-fork/apps/desktop/DESIGN.md`), plus the SDK exports the
plugin is allowed to import.

## Polish changelog (each fix + the token/primitive used)

| # | Fix | Files | DESIGN.md contract |
|---|-----|-------|--------------------|
| 1 | Section-page chat-binding notice was a full bordered box (`border border-(--ui-stroke-tertiary) px-3 py-2`). Replaced with the flat left-hairline callout already used elsewhere in the plugin. | `desktop/plugin.js` §SectionPage | Principle 1 “Flat, not boxed”; `--ui-stroke-secondary` hairline, whitespace instead of a box |
| 2 | Notebook “removed” undo strip was the same bordered box. Same flattening. | `desktop/plugin.js` §NotebookView | `--ui-stroke-secondary` |
| 3 | Lesson-pane detached-binding notice was the same bordered box. Same flattening, so the pane matches the route. | `desktop/plugin.js` §LessonPaneBody | `--ui-stroke-secondary` |
| 4 | Parent Studio egress disclosure and “Changes need review” banner used `border-l-2` (a 2px width override). Now a single token hairline. | `desktop/plugin.js` §StudioBriefForm, §StudioReviewBanner | “single `--ui-stroke-tertiary` hairline”; token widths only |
| 5 | First-run heading borrowed the chat text-size token (`text-[length:var(--conversation-text-font-size)]`), which DESIGN.md scopes to conversation text/composer. Replaced with the page scale used by native onboarding headings, and raised the supporting paragraph one step for hierarchy. | `desktop/plugin.js` §FirstRun | Chat typography section (conversation tokens stay in chat); `text-lg font-semibold tracking-tight`, body `text-sm`, spacing via `mt-2` |
| 6 | Textbook teaching segments, saved Notebook moments and Parent Studio page previews painted provider Markdown as literal text (visible `**…**`, `|---|` tables). They now render through the sanctioned transcript renderer, capped at reading width. | `desktop/plugin.js` §SectionPage, §NotebookView, §StudioPages | §14 “`MessageTextContent` for transcript-style content instead of another Markdown renderer”; tables inherit `--ui-stroke-tertiary` |

No colors, shadows, radii or control chrome were re-specified at any call site. Widths on
`Select`/`Input` (`w-36`, `w-40`, `w-44`, `min-w-0 flex-1`) are field layout, not primitive
padding/size overrides.

## Measured result (live Desktop, real backend)

Source audit of `desktop/plugin.js`:

- raw hex / `rgb()` / `rgba()` literals: **0**
- `shadow*` occurrences: **0** (elevation comes only from SDK primitives)
- inline `style: {` objects: **0**
- boxed callouts (`border border-(--ui-stroke-tertiary) px-*`): **0**
- `border-l-2` width overrides: **0**
- chat-size token uses outside chat: **0**
- `MessageTextContent` renderers added: **3**

Live DOM audit (`docs/cb049-shots/audit.json`, captured from the isolated window on CDP 9341,
real backend `127.0.0.1:44219`, plugin installed from this worktree):

- route and every destination render in both `data-hermes-mode="dark"` and `"light"`;
- no shadow inside `[data-cb-route]` other than the SDK's own focus ring and input inset;
- no nested bordered card inside another bordered card in any audited view;
- zero Markdown residue on the section, notebook and studio surfaces after fix 6
  (`markdownResidue: []`), with real `aui-md-table` chrome present instead;
- narrow 460px and 200% root text both keep the objective, table and actions operable.

First-run (clean backend on 44221, no courses): heading computed `18px / 600`, letter-spacing
`-0.45px`; paragraph `14px / 22.75px`, margin-top `8px`, in dark and light.

Lesson pane: pane adopted beside the real bound lesson chat, rendering `COURSEBOOK`,
`Open lesson chat` / `Continue lesson`; detached-binding copy is a 1px left hairline (no box).
The pane is unchanged when the focused chat has no enrollment — it keeps its own empty state.

Sidebar: the plugin's own `SIDEBAR_NAV_AREA` row “Coursebook” is present (codicon `book`).

## Evidence

- `docs/cb049-shots/030-…037-*` — dark: overview, Textbook, section, Notebook, Quizzes, Courses,
  Library, Parent Studio.
- `docs/cb049-shots/040-…046-*` — light: the same surfaces.
- `docs/cb049-shots/050-section-narrow-dark.png`, `051-section-text200-dark.png`,
  `052-section-reduced-motion-dark.png`.
- `docs/cb049-shots/060-firstrun-dark.png`, `061-firstrun-light.png`.
- `docs/cb049-shots/070-chat-pane-light.png`, `071-chat-pane-light.png` — real chat + pane.
- `docs/cb049-shots/audit.json` — the DOM audit printed above.

## Known limits

- There is no raw color or ad-hoc shadow left to remove; the remaining visible borders/shadows
  in the live audit belong to SDK primitives (buttons, inputs, Markdown tables) and are correct.
- The isolated first-run backend and its window are disposable test homes
  (`~/.hermes/cb049-backend`, `~/.hermes/cb049-firstrun`); the operator profile was untouched.
