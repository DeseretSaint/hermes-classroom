# CB-009 review packet — the learning workspace

Branch `wt/cb-009-vellum`. Single-writer file: `desktop/plugin.js`.
Owner: Vellum. Status: **implemented; live verification partial and stated exactly below.**

## 1. What merged to build on

This task's branch was cut before any of its parents landed, so it starts with two merges:

```
e8bf2e1  CB-009: merge CB-008 grading gate and cb.rpc v3 review/evidence handlers
         (also carries CB-010's shell + pack flows, merged first and cleanly)
```

Resolution decisions, each made against the recorded upstream decision rather than by picking a side:

| File | Resolution | Why |
|---|---|---|
| `coursebook/domain.py` | cb-023 side wins (review/evidence handlers, hint consumption, delayed evidence) | CB-008 owns those semantics; `binding.get` stays in `api.py` per CB-008's own decision, so the kernel duplicate was **not** resurrected |
| `coursebook/hooks.py` | cb-023's pre/post-turn gate **plus** CB-010's `pack_flow` registration | both are additive at the same wiring point |
| `scripts/probe-backend.py`, `tests/test_rpc.py`, `tests/test_contracts.py` | unused-method probe uses `course.teleport` | with CB-010 every frozen method has a handler; `pack.preview` is implemented here |
| `tests/test_kernel_commands.py` | cb-023's binding assertions | stored id only, exactly one identifier — matches `api.py` |

Gates on the merged tree: `scripts/test.sh` → **422 tests OK**, `desktop/plugin.js` parses, `scripts/validate.sh` → **20/20 backend expectations, contract v3, 38 methods**.

## 2. What ships in the Desktop half

| Surface | Implementation | Commands | Gated on |
|---|---|---|---|
| Course detail, 7 local views (Overview / Textbook / Notebook / Quizzes / Plan / Evidence / Sources) | `CourseDetail`; `SegmentedControl` at wide widths, one labelled `Select` below 47.5rem | — | `lesson.page` |
| Overview | `OverviewView`: current objective, next action, one review row, one recent event, action banners | `lesson.page`, `review.queue`, `quiz.history` | per command |
| Textbook — sections, not one thread | `TextbookView` + `SectionPage`: segments, media, sources, checks, attempts, notebook saves; **Continue here** vs **Start a fresh run** | `lesson.page`, `lesson.begin`, `notebook.save`, `artifact.get` | `lesson.page` |
| Notebook | `NotebookView`: search (250 ms), tag filter, recent/oldest, edit note+tags, remove with restore, open/continue from here | `notebook.list`, `notebook.update`, `notebook.delete`, `notebook.save` | per command |
| Quizzes | `QuizzesView`: filters by verdict and assistance class, read-only review, new version, dispute, save moment | `quiz.history`, `progression.challenge_out`, `attempt.dispute`, `notebook.save` | per command |
| Plan | `PlanView`: flat objective list in the contracted state vocabulary, next review, challenge-out | `review.queue` (+ `course.outline` when it lands) | `review.queue` |
| Evidence | `EvidenceView`: L3 → L2 → L1, verdict and provenance, dispute history | `evidence.inspect` | `evidence.inspect` |
| Sources | `SourcesView`: support status in words, fetch/publish dates, no “verified” badge | `lesson.page` | `lesson.page` |
| Review across enrollments | `CoursesView` “Review due” strip with an honest per-course count and a Review action | `library.list` evidence summary | — |
| Bound lesson pane | `LessonPaneBody` + `AttemptControls`: objective, evidence target, check, submit, graded/needs_retry/overridden/stale, detached banner with Reattach / new run / abandon, Continue lesson, review and source counts | `binding.get`, `library.list`, `lesson.page`, `check.open`, `attempt.submit`, `attempt.override`, `review.queue`, `binding.abandon` | per command |
| One attempt per answer | shared `AttemptControls` on the pane and the section page; one nonce per check view, reused on **Retry grading** | `attempt.submit` idempotency key `cb-attempt-<check>-<nonce>` | — |
| Continuation | `continueLesson()` opens the bound chat and submits one real user turn through `host.composer.submit`; a false return is reported, never faked | — | `host.composer` |

No transcript, composer, markdown renderer or icon set is rebuilt. Components used: `Button`, `Badge`, `SearchField`, `SegmentedControl`, `Select`, `Input`, `Textarea`, `ListRow`, `EmptyState`, `ErrorState`, `Loader`, `ConfirmDialog`, `DropdownMenu*`, `Codicon`, `PanelSectionLabel`, `PanelEmpty`. Tokens only; no raw hex, gradient, shadow, radius or control-padding override; no `autoFocus`/`focus()`; no navigation from a background read.

## 3. Live verification — what was actually run

Isolated Electron window (`--user-data-dir` under my own scratch, CDP 9333) against the host gateway, profile `vellum`, drug over CDP with `scripts/cb009-cdp.mjs`.

| Shot | State | Reached by |
|---|---|---|
| `docs/cb009-shots/01-course-overview.png` | course detail, Overview | Courses → **Open** |
| `docs/cb009-shots/02-textbook.png` | Textbook index + the v4-outline note + honest empty state | view switcher |
| `docs/cb009-shots/03-notebook-empty.png` | Notebook empty state, tag picker, sort control | view switcher |
| `docs/cb009-shots/04-notebook-narrow.png` | same at 460×900 | `Emulation.setDeviceMetricsOverride` |

**Defect found and fixed by driving the live window:** `currentScope()` called `host.profileRoutes()` as if it were synchronous. Current Desktop returns a Promise, so `routes.find` threw and the whole route failed to render (`routes.find is not a function`). Fixed by resolving the inventory once at `register()` into `profileRouteCache` (the same shape CB-021 fixed in Sable's file).

## 4. What is NOT verified, and why (this is the honest limit)

The host gateway process has been running since before this branch existed and holds the **v2** Coursebook module in memory. `plugins.isolation` puts the plugin in-process for this package, so there is no supported way to re-import the Python half without restarting the gateway — and the gateway is the parent process of this worker, so a restart would kill the run that is producing this packet. Consequences:

- `review.queue`, `review.action`, `evidence.inspect`, `evidence.disputes` are **gated off** in the live window; the Plan/Evidence views and the Review strip therefore render their gated/empty states, not rows.
- No course on this profile has an approved plan with objectives (the two enrollments are CB-005's shell walkthrough), so the section page and attempt controls have no objective to open in the live window.
- The bound-chat pane was not reached: the profile has no sessions, and a binding only exists after a real teaching turn.

Everything above that could be exercised was: the route renders, the detail shell renders, the seven-view switcher works at wide and narrow widths, the notebook controls render with real state, and the v2 commands (`library.list`, `lesson.page`) answer from the real backend.

**What proves the rest:** `scripts/validate.sh` drives the merged backend through the real ASGI app — 20/20 expectations, contract v3, 38 methods registered, including `pack.import` creating a course with objectives. The UI's contract usage is covered by `tests/test_desktop_contracts.py`. The wiring, gating and copy are real code paths; the missing step is a gateway restart with this branch installed, which belongs to **CB-024 / t_fdf1950a (Sable: “chat + pane + grading + notebook + restart resume all function”)**.

## 5. Contract gaps — filed, not hidden

Card **t_5c626e59** (Atlas) asks for a v4 amendment with three findings from this task:

1. **`course.outline`** — no command lists a course's objectives, so the Textbook index and the Plan tab can only name the current objective (`library_item.evidence_summary.current_objective_id`) and scheduled review rows. `TextbookView` says this in the UI and lights up automatically when the command appears.
2. **`check.get`** — `check.open` returns ids only. The pane can submit an answer but cannot show the stimulus or its choices, so the answer field says plainly that the question and choices are in the teaching chat. `AttemptControls` already prefers `check.get` when `/runtime` lists it.
3. **`lesson.assist`** — Hint / Show answer / Skip have no command path; the pane says so instead of rendering dead buttons.

## 6. Accessibility and responsive notes

- Every control is a real button/input with a programmatic label; `aria-describedby` links the answer field to its help text; dialogs are `ConfirmDialog`.
- Status is never colour-only: state, verdict, assistance class and warnings are always text badges plus a sentence.
- Wide/narrow: `min-[47.5rem]` switches the view strip between `SegmentedControl` and one labelled `Select`; rows wrap rather than clip; 460×900 captured.
- Reduced motion: nothing animates except the shared `Loader`; no `transition-all`.
- Focus: no `autoFocus`, no programmatic focus, no navigation from a background read; opening a course is a click on **Open**.

## 7. Known gaps in this packet

- No 200 %-text capture for the new views (the shell's 200 % capture is CB-005's).
- The bound-chat pane states (awaiting_input → graded → needs_retry → overridden → detached) are implemented but not photographed, for the gateway reason in §4.
- `docs/cb009-shots/tmp-scratch.png` is a throwaway from the abandoned isolated-home attempt and should be deleted.
