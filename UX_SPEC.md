# Coursebook Desktop UX and visual specification

Status: implementation-ready design contract. No implementation has started.
Governing architecture: `PREBUILD_SPEC.md`. Evidence: `AUDIT.md` and `VAULT_LEARNING.md`.

## 1. Experience thesis

Coursebook should feel like **Hermes acquired a learning workspace**, not like a separate
education portal embedded in a tab.

The winning visual is not a colorful course catalogue. It is the moment a learner sees:

- the actual Hermes teaching conversation on the left;
- one precise current objective on the right;
- what evidence their last answer produced;
- the next permitted action;
- a real source and artifact;
- and the same state after restart.

Tone: calm, exact, generous, quietly ambitious. The interface is a study instrument, not a
game, school-themed skin, file manager, or analytics dashboard.

Product nouns: **Coursebook**, **Courses**, **Lessons**, **Library**, **Parent Studio**.
Do not use Classroom as the visible plugin name; `coursebook` remains the package id.

## 2. Native Desktop composition

Register:

- `ROUTES_AREA` with `/coursebook`;
- `SIDEBAR_NAV_AREA` labelled `Coursebook`, using a suitable book/library codicon;
- `PANES_AREA` with `Coursebook` as the lesson-context pane;
- `PALETTE_AREA` actions for Open Coursebook, New course, Resume lesson, Import pack;
- `SETTINGS_PLUGINS_AREA` for preferences, not a custom preferences dialog;
- `TOOL_MEDIA_RENDERER_AREA` only for Coursebook-owned tool artifacts;
- optional `TRANSCRIPT_DIRECTIVE_AREA` for a validated current-check/evidence chip.

The route is one static segment. Selected course/enrollment/view lives in Coursebook state,
not `/coursebook/:id`.

The Coursebook pane is registered globally but renders content only for a bound lesson chat or
an explicit preview of the bundled example. On unrelated chats it shows a minimal course
entry/resume action or stays empty according to user preference; it never displays the last
lesson as if it belonged to the focused chat. Scope is `(connection, profile, enrollment)`.

**Chat remains the teaching surface.** Coursebook does not rebuild the transcript, composer,
markdown, or approvals. Its pane adds structure and deterministic controls. The route's course
library/detail is a full page; an actual lesson can open the bound Hermes chat plus the
Coursebook context pane, or a Coursebook workspace tab with a link to that chat.

Background jobs update state/badges but never steal focus, open a chat, reveal a pane, or
navigate. Starting/resuming a lesson is always an explicit user action.

## 3. Information architecture

The sidebar destination opens **Courses** with four top-level destinations:

1. **Courses** — enrollments, textbook sections, notebooks, quizzes, reviews, and plan management.
2. **Library** — create/import/bundled/community packs, attribution and trust previews.
3. **Parent Studio** — parent brief, research/approval, pack preview/export, reflections.
4. **Activity** — running/failed jobs, source changes, delivery/usage, recovery.

`Textbook`, `Notebook`, `Quizzes`, `Plan`, `Evidence`, and `Sources` are views of a selected
course, not more sidebar destinations. Avoid a second deep navigation rail. **Library** and
**Parent Studio** remain top-level destinations; sharing is an action on a course/pack.

At wide widths, use a restrained local course list on the left of the route and detail on the
right. At narrow widths, the course list becomes a picker/back step. The main Hermes sidebar
is not replaced.

### Page header

Left: current destination title, one-sentence context.
Right: one primary action only, plus an overflow menu for secondary operations.

Examples:

- Courses: **New course** primary; Import pack in Library/overflow.
- Course detail: **Resume lesson** or **Start lesson** primary.
- Library: **Import pack** primary.
- Parent Studio: **New lesson pack** or **Review plan** primary.
- Activity: no permanent primary action; failed jobs expose Retry where valid.

Use `WORKSPACE_PAGE_HEADER_AREA` for course/view switching when the route is in the workspace
pane. It must have an inline fallback in split route tiles.

## 4. First-open experience

### Fresh install, backend ready

Do not show a marketing hero, feature carousel, fake sample progress, or a wall of recipe
cards. Show a compact working welcome:

```
Coursebook
Build a course around what you want to do.

[ Create a course ]  [ Import a pack ]

Or start with the Japanese example
Conversational register · 3 short lessons · sources included
[ Preview example ]

Your courses will appear here. Progress and personal answers stay on this profile.
```

Below, a small three-part orientation, no cards-in-cards:

- **Create or import** — start from a goal or a prepared pack.
- **Practice with evidence** — answers change the next step.
- **Reuse and share** — export teaching material without learning history.

The example pack is locally bundled and clearly labelled as a demonstration. Opening it is a
preview, not an enrollment or model call.

### Python backend not enabled/available

The route still opens with an `ErrorState`:

- title: Coursebook needs its agent plugin;
- exact enable action/deep link to Capabilities → Plugins;
- explain that Desktop and backend halves are separately enabled;
- offer Import preview only if it can run without backend; otherwise disable with reason;
- never show an empty course list as if the user has no courses.

### Unsupported remote/profile topology

A scoped banner says course creation and mutation are unavailable on this backend. Allow safe
read-only bundled-pack preview. Do not silently switch profiles or connections. The visible
scope is active connection + active profile.

## 5. Create-course flow

Use one route-level staged flow, not a long wizard dialog. Three steps, all editable before
generation:

1. **Goal** — large focused field: “What do you want to be able to do?” Recipe choices appear
   as plain `ListRow` options with concrete examples. Parent preparation goes to Parent Studio.
2. **Shape** — only relevant time/depth/assessment/delivery settings. Use `ListRow`,
   `SegmentedControl`, `Select`, and `Switch`; no radio-pile or ten-card template gallery.
3. **Review** — end state, evidence, schedule arithmetic, research/provider egress, and exact
   generation action. No course generation until the user approves this step.

For imported packs, the equivalent flow is Preview → Trust/source/rights → Enrollment options
→ Import. Reimport offers Resume existing and Create fresh enrollment.

### Plan-generating state

Show real stages as they complete:

- goal normalized;
- sources gathered;
- objectives drafted;
- checks reviewed;
- plan ready.

Use the shared long-operation `Loader`, actual operation status, elapsed time, Cancel, and a
safe background action. Never fabricate percentages. Leaving/reopening the route reattaches
by operation id. Failure names the failed stage and preserves the brief.

### Plan preview

Lead with the performance goal, not token/research metrics.

- End state and observable evidence.
- Objectives in a flat ordered list; estimated sessions are planning aids, not promises.
- Scheduled hours arithmetic and any feasibility warning.
- Sources/support summary and content/safety notes.
- Egress/provider summary.
- Edit goal / Edit objectives / Approve plan.

Approval binds to the exact plan hash. Any meaningful edit invalidates it.

## 6. Courses home

When courses exist, show working rows rather than large boxed tiles:

```
Conversational Japanese
Next: Choose a register for the context
2 of 6 objectives have independent evidence       [Resume]

Washer setup
Ready to verify                                   [Continue]

Fractions for a 9-year-old
Parent pack awaiting review                       [Review]
```

Each row shows title, recipe/level, current next action, modest evidence summary, and any
warning that needs action. No global “82% mastered.” Use text such as `2 independent · 1 due`
and an accessible details link.

Top controls: SearchField, small filter (`All`, `In progress`, `Review due`, `Archived`), and
New course. Empty filtered results preserve courses and offer Clear filter.

Overflow per enrollment:

- View plan/evidence/sources;
- Open bound chat;
- Review queue;
- Export learning backup (distinct from Share pack);
- Archive/unarchive;
- Delete with typed/explicit ConfirmDialog and data-scope explanation.

Deleting a chat is different from deleting an enrollment; deleting an imported pack is
different from deleting locally generated work. All three have separate copy and recovery.

## 7. Course detail

Use local tabs: **Overview**, **Textbook**, **Notebook**, **Quizzes**, **Plan**, **Evidence**,
**Sources**. On narrow widths these collapse into one labelled view picker rather than a
horizontally clipped tab strip.

### Overview

- Current objective and recommended next action.
- Resume/start primary button.
- One small review-due row.
- Current media/source preview if relevant.
- Recent meaningful event, not a verbose activity feed.
- Status banners only when action is needed: stale source, detached chat, plan update,
  unavailable provider, pending migration.

### Textbook — sections, not one endless thread

Show a flat, scannable section list grouped by phase/milestone. Every row has title, objective,
state (`not started`, `in progress`, `independent evidence`, `review due`, `overridden`), and
last-opened time. Current section is visually emphasized with text, not just color.

Opening any section shows a durable lesson page: teaching segments, generated/sourced media,
sources, checks, notebook saves, and related quiz attempts. **Continue here** resumes its
existing bound lesson run when valid; **Start a fresh run** creates a new context-linked chat
with the objective and evidence summary. Previous chats remain available as history and never
become the source of current state. Jumping backward does not erase later evidence.

This is the primary answer to “where was I?” and “I want to go back to that section.” Users do
not have to scroll one infinite course transcript.

### Notebook — save a moment for later

Every structured teaching segment, sourced visual/audio, and quiz review exposes **Save to
notebook**. Where the host offers a supported message action/selection, an explicit assistant
excerpt can be saved; otherwise save the backend-owned current lesson segment/artifact. Never
invent a transcript-selection API.

Save opens a small editor prefilled with:

- excerpt/artifact preview;
- optional personal note;
- course/objective/source attribution;
- optional tags;
- destination Notebook (course-specific or All notebooks).

The notebook has SearchField, tag/course filters, and chronological or recently-saved sorting.
Each entry shows the saved excerpt, personal note, source section, and saved date. Actions:
**Open in textbook**, **Continue from here**, **Play/view media**, **Edit note/tags**, **Remove
from notebook**. Removal has undo; it does not delete the original lesson or media while
referenced elsewhere. Personal notes/raw saved excerpts never enter community exports.

An empty notebook says “Save an explanation, visual, or quiz moment and it will appear here,”
with a direct Go to current lesson action. No dummy notes.

### Quizzes — past attempts with their original feedback

Filter by objective, result, cold/hinted/answer-shown/override, and date. A quiz row shows the
topic, attempt date, verdict/evidence class, and whether a new version is available.

Opening one shows the original stimulus, answer, observed criteria, feedback, assistance,
sources, rubric/model provenance, and any dispute. **Reviewing is read-only** and never consumes
a retry or changes the old grade. Actions: **Review lesson**, **Try a new version**, **Dispute
grade**, **Save to notebook**. A new version is a fresh attempt/run with a new check version;
the original remains inspectable.

### Plan

Flat objective list with state vocabulary:

- not started;
- introduced;
- independent evidence;
- delayed evidence;
- review due;
- needs review (source/rubric issue);
- overridden.

Each objective expands to evidence criterion, attempts, hints/assistance, next review, and
available challenge-out. Do not render red failure markers or an optimistic progress ring.

Dials open an edit view with impact preview before save. Unsupported migration is refused and
keeps the working plan.

### Evidence

Three linked layers:

- L1 attempts/events;
- L2 objective evidence;
- L3 current recommendation with links back.

Filters: objective, evidence class, independent/assisted, date. Show actual verdict/rationale,
model/rubric provenance, and Dispute action. No personality analysis or emotion inference.

### Sources

Rows show title, publisher, source type, fetch/publication dates, support status, staleness,
and claim count. Opening external content is an explicit action. Unverified/model-assessed is
never rendered as a green “verified” badge.

## 8. Lesson workspace — the signature screen

### Wide layout

```
Hermes teaching chat                         Coursebook pane (~320–380px)
                                             Objective
                                             Choose an appropriate expression
                                             for this addressee and intent.

                                             Current check
                                             [structured prompt/options/input]
                                             [ Submit answer ]

                                             Hint · Show answer · Skip
                                             Evidence: cold attempt
                                             Sources: 2 reviewed
```

The chat remains primary. The pane does not mirror the transcript or repeat lesson prose.
Width is user-resizable through the native pane system; the pane stays mounted when hidden
so current attempt/media state is not lost. On narrow layouts it becomes a bottom pane or an
explicit Coursebook tab; never overlay the composer.

### Pane hierarchy

1. course/lesson label and state;
2. current objective + evidence target;
3. current required action;
4. attempt controls or current feedback;
5. hint/answer/skip/override;
6. compact sources/artifact/review status;
7. link to full evidence/plan.

One primary button at a time. No timer pressure, confetti, XP, streaks, red failure badges,
or progress animations masking model latency.

### Attempt states

- **awaiting_input:** structured options/input enabled, no verdict shown;
- **submitting:** immediate local pending state, input locked, Cancel only if supported;
- **graded:** observed criteria and next permitted action;
- **needs_retry:** local honest failure with Retry, edit answer, or explicit override;
- **clarification:** model/user asks a question; no retry consumed;
- **hinted/answer_shown:** evidence class changed visibly before proceeding;
- **overridden:** access granted with “not independent evidence” label;
- **detached/paused:** no submit action until rebound/reconciled;
- **completed:** summary and next objective/review, not automatic navigation.

If an answer starts in chat, the hook creates/reconciles the same pending attempt. If it starts
in the pane, `submit_attempt` owns it. Idempotency key is enrollment + check + canonical answer
hash + attempt nonce. One answer cannot produce two attempts or two transitions.

After grading, the pane shows the verdict immediately. **Continue lesson** sends the committed
public continuation to the bound chat. If that teaching turn fails, the grade stays committed
and Continue retries without regrading; the UI never pretends the teaching response occurred.

### Feedback presentation

Good:

```
Not yet — this choice treats a close friend like a formal audience.
Try the private, casual context instead.
[ Try a new example ]  [ Explain the difference ]
```

Avoid “Wrong”, red error treatments for ordinary learning errors, and long rubric prose.
Detailed observed criteria are available under Review grading.

### Lesson chat directives

An optional `::coursebook-check{id="..."}` chip may show the current validated state and focus
the Coursebook pane on explicit click. The id is validated against the bound enrollment. The
model cannot invent a check or transition through a directive. Invalid ids render nothing.

## 9. Library and pack trust

Library has three filters: **Bundled**, **Local packs**, **Community** (only when available).
No marketplace-style sales cards, popularity rankings, or “verified course” banner.

Pack row: title, subject, level, recipe, objective count, author, version, review/source status.

Pack preview sections:

1. What you will be able to do.
2. Objectives and estimated schedule.
3. Sources and support/staleness.
4. Assessment coverage and any unvalidated checks.
5. Content/safety/accessibility notes.
6. Rights/attribution per component.
7. Files/media size and integrity/automated check results.
8. Exact import action and fresh-enrollment behavior.

Trust labels use precise text: `schema checked`, `sources fetched`, `model-assessed support`,
`human content review recorded`, `assessment smoke tested`. Never collapse these into Safe or
Verified. Unknown rights can allow private import with warning but not public distribution.

Community updates show keep current / review update / refuse incompatible. No silent update.

## 10. Parent Studio

This is a separate authoring workflow, not a recipe chat persona.

### Brief

Parent-friendly sections:

- goal and starting activities/content prerequisites;
- age band/reading level, duration, setting, materials;
- desired pages/visuals/narration;
- exclusions and supervision constraints;
- before-paste provider/egress disclosure and optional redaction.

### Research and review

Use a split working view: outline/activities left, sources and review notes right. Parent can
edit all meaningful fields before approval. Safety notes are specific to setting/materials;
car activities are passenger-only.

Approval covers actual learner pages, answer guide, narration transcript, and activity
instructions. Edits mark **Changes need review** and disable final generation until reapproval.

### Pack preview/export

Tabs: **Parent guide**, **Learner pages**, **Answers**, **Audio & visuals**, **Sources**.
Show printable page preview with real text, readable type, low-ink layout, no color-only
answers, and oral alternatives where relevant. Export creates selected formats only and shows
exact file list/destination. Reflection is easy/about right/too hard + revisit note, explicitly
parent-reported.

## 11. Activity, jobs, and recovery

Activity is an operational list, not an analytics dashboard:

- running: stage, elapsed, cancel/background;
- failed: actual error, preserved work, retry/edit;
- stale sources: affected course/check, review action;
- delivery issues: target/error/test action;
- recovery: interrupted import/job, resume/discard;
- usage: measured tokens/calls/artifacts only when exposed.

Do not show token/cost counters in the main learning path. Usage belongs here and in a course
details disclosure, not as a gamified budget meter.

A persistent subtle status row may show active jobs count; clicking opens Activity. Never
auto-open it.

## 12. Settings

Settings → Plugins → Coursebook includes:

- default recipe/dials and research budgets;
- aux model task link (host-owned configuration);
- preferred media and narration choices;
- pack storage/export location and community index URL when supported;
- privacy/redaction/retention controls;
- accessibility preferences that are plugin-specific;
- backup/recovery and diagnostic export;
- feature/capability disclosures and links.

No secrets in course files or Desktop storage. Secrets remain host-owned.

## 13. Complete state matrix

Every route must implement, not merely describe, these states:

| State | Required presentation/action |
|---|---|
| first run | create/import/example preview; no fake progress |
| no courses | working welcome |
| no search results | clear filter, preserve data |
| backend off | enable instructions/deep link |
| reconnecting | stale read-only view and retry; no mutation optimism |
| unsupported backend | scoped unavailable message and safe preview |
| plan generating | real stages/cancel/background/resume job |
| generation failed | failed stage, preserved brief, retry/edit |
| plan awaiting approval | editable preview, explicit approve |
| lesson ready | objective and start/resume |
| attempt submitting | locked pending state, no duplicate |
| grader unavailable | needs_retry, retry/edit/override; no state advance |
| detached chat | rebind/new run; submit disabled |
| offline | cached content and local attempts if supportable; research/generation paused |
| TTS/image unavailable | text lesson and unavailable label; continue |
| source stale/dead | impact list and review, old evidence retained |
| pack invalid | specific validation failure, no partial course |
| incompatible pack update | keep working version, no fake migration |
| grant revoked | exact permission recovery, no fake file writes |
| export awaiting review | file/rights/metadata preview |
| export complete | exact destination/open/reveal, no upload implication |
| download failed/cancelled | saved-on-backend vs saved-locally distinction and retry |
| course archived | hidden by default, restore action |
| course deleted | scoped confirmation and recovery information |
| job interrupted | resume/reconcile/discard safely |
| demo fixture mode | clearly labelled, never represented as live research |

All async views handle stale responses with request tokens; an older response cannot overwrite
newer user intent. Optimistic UI is appropriate only for reversible presentation changes, not
for grading, evidence, imports, or evidence-affecting overrides.

## 14. Visual language

Follow `apps/desktop/DESIGN.md` and SDK exports exactly:

- `Button`, `SearchField`, `SegmentedControl`, `ListRow`, `ToggleRow`, `Select`, `Switch`,
  `Tabs`, `Badge`, `EmptyState`, `ErrorState`, `Loader`, `LogView`, `ConfirmDialog`, `Tip`;
- `PanelHeader`, `PanelList`, `PanelListRow`, `PanelSectionLabel`, `PanelEmpty` for pane
  structure where appropriate;
- theme variables only; no raw hex, custom gradients, shadows, radii, or button padding/size
  overrides;
- page gutters use `PAGE_INSET_X` semantics via the available SDK surface/styles;
- flat grouping with whitespace and sparse `--ui-stroke-tertiary` hairlines;
- no card-in-card, boxed search, pill overload, decorative emoji, glassmorphism, or “AI purple”;
- `Codicon` for compact vocabulary; do not mix icon sets;
- `MessageTextContent` for transcript-style content instead of another Markdown renderer;
- `<SandboxedFrame>` only for permitted external content, never raw `<webview>`.

Typography: readable body text and strong hierarchy through weight/spacing, not oversized
headings. Long lesson content caps around comfortable reading width; evidence tables can be
wider. Japanese uses an appropriate CJK fallback, proper line breaking, furigana support, and
no forced romaji-only line-height rules.

Motion: immediate state changes, ~100ms functional transitions, no animated progress theater,
no `transition-all`, respect reduced motion. Loading never displays literal `Loading…`.

## 15. Accessibility and responsive acceptance

- Keyboard-only path through create/import/learn/grade/parent/export.
- Visible focus and correct single-action Escape; no keyboard trap in the lesson pane.
- Every input has a programmatic label and error association.
- Every image has a useful description or is marked decorative; media has text/transcript.
- No status conveyed by color alone; badges include text.
- Text scaling and CJK font fallback do not clip objective, options, or buttons.
- 200% text zoom and high-contrast/forced-colors remain operable.
- Reduced-motion and screen-reader state announcements are concise and not per-token.
- Narrow pane, narrow window, split route, hidden pane, and restored layout retain the attempt.
- Parent PDF is selectable, low-ink, readable, and not an image of a page.

## 16. UX proof suite

Before recording:

1. Fresh profile → open sidebar → bundled preview → import → lesson without hidden setup.
2. Backend disabled → enable → return without losing brief.
3. New goal → cancel generation → reattach → approve edited plan.
4. Chat answer and pane answer race → one attempt/transition.
5. Wrong answer → alternate representation → clarification does not consume retry.
6. Grader timeout → needs_retry → explicit override recorded correctly.
7. Hide/reopen/split pane during attempt → no lost answer or duplicate submit.
8. Restart at every attempt state → same visible objective/pending state.
9. Parent edit after approval → reapproval required before export.
10. Import invalid/malicious pack → precise error, no course residue or network render.
11. Offline lesson → cached content works, research action explains pause.
12. Source goes stale → impact banner appears, old evidence remains.
13. Reimport same pack → Resume existing vs Create fresh works.
14. Course/chat/pack deletion paths remain distinct and recoverable as specified.
15. Keyboard-only, text-only, reduced-motion, 200% text, narrow layout pass.
16. Real long course names, 50+ objectives, long Japanese/English text, and many sources do
    not make the route slow or unreadable.
17. Save a teaching moment → find it by tag/search → open its exact textbook section →
    continue in a new run without mutating the old attempt.
18. Open a past quiz → original answer/feedback is unchanged → try a new version → both
    attempts remain independently inspectable.
19. Jump between early/late syllabus sections → separate context-bound runs open and later
    evidence remains intact.

## 17. Demo composition

Record at a comfortable desktop width with the real chat and Coursebook pane visible together
for the signature learning shot. The first shot is Courses/Library, not Settings. Do not spend
time showing plugin installation in the 90-second video.

Suggested final 82–86 seconds:

- 0–8s: sidebar Coursebook → Japanese pack preview → fresh enrollment;
- 8–25s: real teaching chat + current objective → wrong answer → specific governed retry;
- 25–34s: correct new attempt → exactly one evidence transition;
- 34–40s: save the explanation to Notebook and reopen its exact textbook section;
- 40–47s: restart/resume identical pending state;
- 47–62s: Parent Studio review → polished guide/learner page;
- 62–73s: export pack → allowlisted files/rights/no-upload preview;
- 73–82s: sourced visual/audio + text alternative and next review;
- 82–86s: “A chat answers. Coursebook makes the next step depend on what you did.”

If restart is too slow to show honestly, use a visible cut labelled Restarted and keep the
identical objective/check state. Do not replace a failed flow with a prerecorded simulation.

The visual proof is one coherent workspace changing state. No head-gasket detour, recipe tour,
feature grid, or nine unrelated screens.

## 18. Final UX judgement

The design is strong only if the interface makes the harness visible without making learning
bureaucratic. Keep the objective and action in front, keep evidence one click away, and keep
research/cost/trust machinery out of the way until needed. That balance—real Hermes chat on
one side, deterministic learning state on the other—is the plugin's clearest claim to polish,
usefulness, and technical distinction.
