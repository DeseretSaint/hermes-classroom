# CP-031b — Shared chrome on the homework, Game, World Studio and Parent Studio surfaces

Card: **CP-031b** (`t_adc9bdee`). Closes **GAP-30** for the shell chrome these four surfaces paint:
`desktop/src/00-header.js` (reviewed at `475efefc`) plus the shared offline/child-safe lines that
other files own. Docs only; no product string changed.

Row citations in this file were re-derived on the strings at `475efefc`: each `file:line` is the
line that carries the row's own words today. Section headings keep a coarse range as navigation;
the row citation is the authoritative anchor.

**Surface:** the rail, the route title, the mode words, the settings sheet and the offline line —
every string a person sees around the four in-scope surfaces that is authored outside them.
Shell gaps `GAP-01`/`GAP-02` already own the sheet; this file orders their surface-relevant rows.

## 1. Navigation and the route title (`00-header.js:39`, `129-136`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Coursebook (route title and wordmark) | `00-header.js:2` | default | `GAP-01 shell.wordmark` (cited, not new) |
| Home / Courses / Workshop / Parent Studio (destinations) | `00-header.js:190`, `00-header.js:193` | default | already in `COPY.md` as `nav.home`/`nav.courses`/`nav.workshop`/`nav.parent` — **ok**, no gap (see `CP-021-discover.md`) |

## 2. The parent door (`00-header.js:62-83`)

The create form's recipe list is where a person chooses "for my child"; the last option is the
pointer into Parent Studio.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| One task I need to do now / A single thing to get right — a repair, a form, a procedure. You practise the task, not a quiz. | `00-header.js:122-123` | default | `GAP-37 create.recipe.one_off` / `.desc` |
| A little at a time / Short sessions you pick up when you have ten minutes, with no schedule to keep. | `00-header.js:126-127` | default | `GAP-37 create.recipe.casual` / `.desc` |
| A steady plan / A sequence that builds on itself, with practice you come back to. | `00-header.js:130-131` | default | `GAP-37 create.recipe.committed` / `.desc` |
| Alongside something else / A subject you keep returning to while you study or work on other things. | `00-header.js:134-135` | default | `GAP-37 create.recipe.companion` / `.desc` |
| Preparing for my child / You are preparing material for a child. That happens in Parent Studio, not here. | `00-header.js:138-139` | default | `GAP-37 create.recipe.parent` / `.desc` |

The `parent` recipe's description is the only place the shell names Parent Studio as a destination
from the create form; a restyle that drops "not here" turns it into a second way to make a child
course.

## 3. The settings sheet the four surfaces mount (`00-header.js:84-204`)

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| Pace / Light / Steady / Intense | `00-header.js:148` | default | `GAP-37 create.dial.pace.*` |
| Depth / Survey / Working / Deep | `00-header.js:152`, `00-header.js:154-156` | default | `GAP-37 create.dial.depth.*` |
| Assessment / None / Self-check / Graded | `00-header.js:160`, `00-header.js:162-164` | default | `GAP-37 create.dial.assessment.*` |
| Autonomy / Guided / Balanced / Independent | `00-header.js:54`, `00-header.js:168`, `00-header.js:171` | default | `GAP-37 create.dial.autonomy.*` |
| All / In progress / Review due / Archived (course filters) | `00-header.js:69`, `00-header.js:177-178`, `00-header.js:180` | default | `GAP-37 create.filter.*` |
| System / Light / Dark (appearance) | `00-header.js:227` | default | `GAP-01 home.settings.appearance.*` |
| Game / Guided / Textbook (presentation options) | `00-header.js:235` | default | `GAP-27 world.mode.*`; `Guided` → **GAP-36** |
| Follow system / Reduce motion | `00-header.js:240-241` | default | `GAP-01 home.settings.motion.*` |
| Loss-framed reminders / Public leaderboard / Loot or random rewards / XP and streaks — each with `Never` | `00-header.js:252-254` | default | `GAP-01 home.settings.child_safe.*` (`studio.child_safe` in `GAP-28`) |
| 10 min / 15 min / 20 min / 30 min (session length) | `00-header.js:259-262` | default | `GAP-28 studio.session.*` |

## 4. The offline line these surfaces do **not** inherit

The shell has one offline sentence per route, and none of the four in-scope surfaces mounts it:

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|

| Offline. Showing the classrooms that were last read; starting a lesson is paused until the connection returns. | `32-desk.js:352` | offline | `GAP-35 shell.offline.desk` |
| Offline (badge) and `Offline. Lessons, notes and review keep working from what this profile already saved. …` | `00-header.js:1119` | offline | `GAP-35 shell.offline.page` |
| A new course is paused while this profile is offline. Nothing you already saved is lost. | `10-primitives.js:273` | offline | `GAP-35 shell.offline.first_run` |

`useOnline()` is defined once (`00-header.js:1035-1048`) and `95-studio.js` / `97-world.js` /
`30-home.js`'s game block never call it. So the four surfaces have **no offline state**, which is
the §3.12 requirement CP-025a/CP-025b flagged. This sweep names it **GAP-35** and lists the four
existing sentences as the wording precedent — not as rows the four surfaces render.

## 5. Chrome from elsewhere, and what is deliberately not a row

`00-header.js:565-982` carries the lesson-chat open path (`This lesson has no chat to return to yet.`
`798`, `This lesson is not connected to a chat right now.` `801`, `Update Hermes Desktop to resume a
bound lesson.` `804`, `The saved lesson chat could not be opened from this desktop. The section is
still available to read.` `814`, `Coursebook lesson` `868`, `{code}: {backend message | this chat
could not be bound.}` `892`, `No course was read for this action.` `915`, `This course has no current
objective yet; approve the plan first.` `918`, `{code}: {backend text}` `930`, `Resumed the bound
lesson chat.` `936`, `There is no saved lesson chat for this section yet. …` `944-945`, `The lesson is
ready. Your section is open below. …` `965`). That is the Classroom's tutor path and it is not
painted on any of the four surfaces, so this sweep does not row it — but it is **not** already
inventoried either: `CP-023-classroom.md` records the deck's own no-chat state (`classroom.nochat.*`,
deck `161-163`, "This section has no chat yet"), whose wording does not carry these shipped
sentences, and no other inventory names them. New gap **GAP-40**, so this block is not left claiming
coverage it does not have.

Two sentences in this file **are** painted on all four surfaces and no inventory carried either. The
shell's own contract-envelope error (`641`) is a synthesized `INTERNAL_ERROR`. So is the fallback
inside `describeError()` (`970`, `973`): every error path on all four surfaces calls that helper
(`95-studio.js` alone calls it 20 times), so when the backend hands back nothing quotable the person
reads product-internal wording instead of the backend's own message. New gap **GAP-39**.

| string | source file:line | state | proposed copy id (GAP-nn) |
|---|---|---|---|
| The Coursebook backend answered with something that is not a contract envelope. | `00-header.js:710` | error | `GAP-39 shell.rpc.envelope` |
| The Coursebook backend did not answer. | `00-header.js:1058` | error | `GAP-39 shell.rpc.no_answer` |

Named here, **not** rowed, because they never reach a person:

- `00-header.js:514` — `profile routes could not be read` is stored in `profileRouteState.error`,
  which nothing renders; only its sibling `routingUnavailable` boolean is read (`00-header.js:817`).
- `00-header.js:838` — `loadBinding needs exactly one of storedSessionId or enrollmentId` is a
  developer invariant thrown on a console path, not copy.
- `00-header.js:634`, `1065`, `1070` — `Coursebook is not registered` is thrown from a `!pluginContext`
  guard. It is a developer invariant that surfaces only as a crash string, not a designed state.
- `00-header.js:603`, `658`, `942`, `967`, `1015`, `1018`, `1204` — these pass `describeError(error)`
  straight through, so their rendered text is the backend's own message; rowing them would duplicate
  the backend rows.

## 6. State coverage for the chrome

| state | what renders | deck |
|---|---|---|
| default | rail, wordmark, create-form recipe/dial options | GAP-01, GAP-28 |
| loading | none in the chrome itself | — |
| empty | none | — |
| error | the envelope error and the `describeError()` fallback, on all four surfaces | GAP-39 |
| offline | one line per route, never on these four surfaces | GAP-35 |
| overflow | none | — |
| dialog | the settings sheet (owned by `GAP-01`) | GAP-01 |

## 7. Row count

Tables above: the complete visible-string inventory for the chrome these surfaces paint. Two blocks
are named and excluded rather than omitted: the classroom tutor path (GAP-40) and the
non-rendered developer invariants listed in §5.

## Rows removed in the 475efefc re-derivation

These strings were listed by an earlier cut of this sweep and no longer ship at this revision.
Each is removed with its reason rather than re-anchored to a neighbouring line.

- `Offline. Showing the courses that were last read; starting a course or writing a brief is paused until the connection returns.` — the banner now reads "Offline. Showing the classrooms that were last read; starting a lesson is paused until the connection returns." at 32-desk.js:352, which the next row already carries.
