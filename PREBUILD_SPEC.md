# Coursebook — pre-build implementation specification v8

Status: architecture candidate after adversarial audit. No implementation has started.
Companion evidence and source citations: `AUDIT.md` in this repository.
Personal-vault learning research and Japanese demo mapping: `VAULT_LEARNING.md`. Vault notes
are read-only research leads; unavailable canonical findings require fresh verification.
Native Desktop layout, task flows, state matrix, accessibility, and demo composition:
`UX_SPEC.md`.
Contest: catalog PR + under-90-second X demo + form by Nov 11, 2026, 5 PM EST.

## 1. Product

Coursebook is a native Hermes Desktop learning workspace for adults and parents. It turns a
goal or reusable course pack into a governed, resumable sequence of lessons. It researches
when needed, teaches one objective at a time, evaluates attempts, schedules later retrieval,
and produces sourced visuals/audio. Parent mode prepares parent-led lesson packs; children do
not chat with Coursebook.

Users can create from a goal or import a pre-prepared classroom. Authors can export an
allowlisted pack for others after reviewing all included content and metadata. Shared teaching
material transfers; personal learning history is excluded by schema, not promised PII removal.

**The judge-facing thesis:** the model teaches, but Coursebook owns the objective, attempt,
rubric, evidence, next permitted transition, and durable record. A prompt cannot guarantee
those transitions.

No learning-style diagnosis, “2 sigma,” guaranteed mastery, child-safety certification, or
COPPA-compliance claim. Educational research motivates design; Coursebook has not established
learning efficacy.

## 2. Contest promise vs product roadmap

All requested capabilities remain in the product design. The contest submission must be a
coherent working vertical slice, not a wide set of partially functional controls.

### Contest end-to-end paths

The guaranteed contest platform is the **active local Hermes profile/backend**. Remote and
cross-profile controls stay disabled until their cwd, REST, identity, media, and download
paths pass the same tests; a README caveat alone is not support.

1. **Create:** goal → recipe-aware intake → plan preview → isolated lesson chat.
2. **Import:** local/bundled pack → trust/source/license preview → fresh course → lesson.
3. **Learn:** typed check → bounded grade → governed transition → misconception/retry.
4. **Control:** hint/answer/skip/override/challenge-out with correct evidence classes.
5. **Resume:** restart or rebuild state and return to the same lesson revision.
6. **Media:** Coursebook-owned visual/audio artifact, cached, with complete text fallback.
7. **Parent:** brief → research/plan/source approval → parent guide + learner-page export.
8. **Share:** allowlisted, versioned local pack export with content/rights/metadata review →
   safe reimport.
9. **Operate:** course list, current objective, evidence, jobs, source status, and usage.
10. **Submit:** clean fresh install/enable/restart/revoke/uninstall, validate/doctor, demo.

### Roadmap within the same architecture

Richer dial/migration UX, public community index, optional gateway reminders, additional
recipe/milestone variants, and larger media/catalog collections. Schemas can anticipate them;
incomplete features must be labelled honestly and must not appear as working contest features.
Companion v1 is a thin pasted-syllabus/current-unit workflow with exam/evaluator/deadline
intake; LMS/calendar integrations are later. Reminder v1 displays a manual schedule; actual
cron delivery is enabled only after explicit channel/DST/delivery verification.

## 3. Recipes

| Recipe | Purpose | Assessment/output |
|---|---|---|
| One-off | complete a discrete task | verification, sourced visuals, no retrieval/homework requirement |
| Casual | independent learning without deadline | optional checks, light reviews |
| Committed | performance goal + deadline | graded checks, phases, milestones, capstone |
| Companion | support an external course | imported syllabus and exam-aligned drills |
| Parent | prepare a lesson for one's child | parent-approved printable/narrated lesson pack |

Adult recipes share an objective/attempt/evidence lifecycle. Parent mode reuses the planning,
source, and artifact infrastructure with a parent-observation checklist; it is not presented
as equivalent automated assessment or adaptation.

## 4. Intake and planning

Progressive intake asks only relevant questions:

- observable end state;
- one-off / self-study / existing course / parent preparation;
- available time and deadline;
- depth, assessment, and reminder choices where relevant;
- parent age band, current level, duration, setting, materials, reading level, outputs, and
  content exclusions where relevant.

Base knowledge is measured with optional probes after plan approval. Parent-supplied level is
confirmed, not diagnosed. Schoolwork is optional sensitive input with redaction and provider
disclosure.

Plans contain stable objective ids, evidence criteria, phases/milestones when relevant, and
schedule arithmetic. Replanning and backward navigation preserve evidence unless the user
explicitly deletes it. Replanning versions objectives and maps evidence forward.
Pace/depth/assessment/autonomy dials are explicit user controls.

### Honest time display

Do not convert FSI intensive class hours to conversational self-study using an invented
factor. Show:

- scheduled time: `sessions/week × minutes × weeks`;
- external benchmark context with target/population limits, if relevant;
- `model_estimate` with low confidence and rationale, or no attainment estimate;
- observed work/pace later, without equating hours with mastery.

## 5. Lesson template and evidence

Eight logical states: warm-up retrieval, performance, model, guided attempt, solo attempt,
retrieval check, homework, exit ticket. Recipes transform or remove states rather than adding
unbounded new ones.

- One-off substitutes physical/task verification for a quiz and omits homework.
- Casual allows self-checks and optional reviews.
- Casual with checks disabled advances only on explicit Next and records
  `instruction_complete`/`self_reported`; the UI says no independent evidence was collected.
- Committed requires the stated evidence criteria and capstone.
- Companion aligns to the external syllabus.
- Companion also asks exam/evaluator/deadline and labels imported material `unofficial`; no
  exam prediction, accommodation equivalence, proctoring, or past-paper redistribution claim.
  Moving beyond the imported/current unit requires explicit user permission and a visible
  scope change; it is never inferred from a correct answer.
- Parent renders these as warm-up, goal, model, guided activity, independent activity,
  observation check, take-home, and parent notes.

Scaffold fading, interleaving, and representation changes are configurable heuristics, not
universal laws. Two unsuccessful attempts trigger a different explanation/representation and
an escape option, not a louder repetition.

Evidence classes: `cold`, `hinted`, `answer_shown`, `self_reported`, `parent_reported`, and
`override`. Instruction completion, independent evidence, and delayed retrieval are separate.
One immediate item never proves durable mastery. A manual override grants access, not mastery.
Users can inspect and dispute evidence.

Every check declares its evidence target: recall, comprehension, production, discrimination,
procedure, or transfer. Recognition cannot substitute for production, a repeated near-
identical item cannot substitute for transfer, and simulated/self-reported physical completion
cannot become independently verified completion.

## 6. Authoritative architecture

```
desktop/plugin.js
  Native route/sidebar cockpit, import/export previews, job progress, source/evidence views
  host.request/openSession for Hermes session lifecycle; ctx.rest for Coursebook API

plugin_api.py + backend modules
  Courses, plans, grading, session bindings, jobs, research, artifacts, packs, usage
  plugin_db() SQLite per active profile, WAL, transactions, schema migrations

Hermes adapters
  pre_llm_call: validate binding, grade pending answer, commit transition, inject policy delta
  post_llm_call: record assistant snapshot only
  post_tool_call: capture real tool provenance and usage correlation
  API request hooks: usage accounting, including failed/abnormal turns
  Coursebook-owned tools: governed research and media artifacts

Course workspace (backend-owned, outside git roots)
  Coursebook-generated AGENTS.md policy only
  Generated files/artifacts/exports; never arbitrary imported instructions
```

SQLite is the source of truth. Markdown/JSON/PDF/audio are exports or content artifacts, not
parallel authorities. Large media lives in content-addressed storage with metadata in SQLite.

Evidence is inspectable at three layers: L1 raw attempts/events, L2 current objective evidence
linked to L1, and L3 short revisable plan recommendations linked to L2. L3 is not a learner
persona or psychological diagnosis.

The course is also a user-navigable textbook. Every completed/current section has a durable
lesson page and, where created, a separate bound chat. Users can revisit a section, read its
teaching/artifacts, review or retry its quiz, and start a fresh run without altering earlier
attempts. A new attempt never overwrites the previous one.

**Notebook:** a user can save a lesson moment—an assistant excerpt, generated explanation,
diagram/audio, source passage, or their own note—into a local notebook with course, objective,
lesson run, source links, and timestamp. Notebook entries support search, tags, edit/delete,
and **Continue from here**, which opens the source lesson or starts a new context-linked run.
Raw selected transcript text is stored only after explicit save and is excluded from community
packs by schema. Transcript row selection/ids are not assumed from an undocumented SDK seam;
the fallback saves the current structured lesson segment/artifact from backend state.

The Desktop and agent backend must share a filesystem/authority topology. Otherwise use a
backend-driven workspace flow or report the unsupported topology; never pretend a Desktop
folder grant creates a remote backend cwd.

## 7. Identity and session lifecycle

Coursebook generates random `course_id`, `enrollment_id`, `lesson_run_id`, and operation ids.
Each syllabus objective/section can open its own lesson run with its own chat and preserved
objective context; a course is not one endless thread. A session binding
contains profile, course/run ids, runtime/stored ids when known, cwd fingerprint, current
compression tip, and status. Titles are display only.

Create operations are adopt-before-mint with an in-flight lock. Repeating a lesson creates a
new run and never depends on acquiring the same title. Runtime-id loss triggers resume by the
stored binding, not recency.

Binding statuses: `active`, `paused`, `detached`, `branched`, `completed`, `orphaned`.
Rename is cosmetic. Cwd change detaches governance. Model change is recorded and may require
policy/grader compatibility review. Compaction updates the tip. Editing history does not
rewrite evidence. Branches are ungoverned until explicitly forked into a new run. Deleted
chats preserve evidence and allow a new run. Multiple windows use revision-fenced DB writes.

## 8. Grading gate and transactional transitions

Checks are typed, versioned records created before the answer: id, objective, construct,
locale/register assumptions, accepted variation, rubric, prerequisites, and scoring rule.

Before a learner sees a check, a separate audit verifies objective alignment, an unambiguous
stimulus, correct reference answer, acceptable alternatives, and rubric consistency. A flawed
key/question/rubric is replaced or the lesson pauses; it cannot be used for grading.

Closed forms use deterministic validators. Open responses use `ctx.llm` with only answer,
rubric, construct, and permitted context. Return observed criteria, verdict, rationale, and a
possible error pattern. Unexpected phrasing is not automatically a misconception. The plugin
declares `jsonschema` explicitly and locally validates structured output; a missing optional
host package must never turn invalid grading JSON into an accepted verdict.

The minimal assessment envelope contains stimulus, learner instructions, response, rubric,
reference answer/scoring examples, locale, allowed conventions, and attempt id. The key stays
out of learner-facing context. Deterministic validators cover units, rounding/tolerance,
equivalent forms, Unicode/notation, and multiple valid solutions rather than exact strings.

`pre_llm_call` grades a pending answer with an internal deadline shorter than Hermes' hook
timeout. It catches errors and returns a local `needs_retry` response/block if grading cannot
finish. The transition commits before the next teaching turn proceeds. A timeout never grants
a pass. `post_llm_call` is an observer, not the gate.

The primary correctness door is an explicit backend `submit_attempt` command invoked by the
Coursebook UI/owned tool. It returns the committed verdict and next permitted action. The chat
hook is an adapter for free-text submissions and calls the same command; it is not the sole
boundary. If a hook fails open, the next Coursebook action reconciles the pending attempt and
refuses advancement. Clarifying questions do not consume retries or create error evidence.

After a grade commits, the pane immediately displays its local verdict and offers **Continue
lesson**. That explicit action sends a transition-specific continuation prompt to the bound
runtime session. The prompt contains only the committed public verdict/next teaching action,
never the reference key. If the follow-up model turn fails, the grade/transition remains
committed and Continue can be retried with a new continuation idempotency key; it never
regrades or advances twice. If the bound session is gone, offer a new governed run with a
short evidence summary rather than silently using another chat.

A transition transaction checks course/run identity, open check, answer hash/id, rubric
version, verdict freshness, current revision, and idempotency key. Late callbacks carry turn
nonces and compare-and-swap fencing; they cannot modify newer state.

Evidence histories record attempts, hints, overrides, disputes, and model/provider/rubric
provenance. Grader evaluation uses 60 initial labeled cases, expanded per domain, with
correct/partial/wrong/irrelevant/code-switched/dialect/non-native/adversarial categories.
Report per-category false pass, false block, retry, and repeat stability; do not claim fairness
from aggregate accuracy. Sixty is a smoke-test floor **per grader configuration and domain/
language slice**, not a universal validity result. Re-run whenever model, prompt, rubric
schema, or language changes. A misconception requires different items targeting the same
concept; one flawed/repeated item cannot confirm it.

## 9. Research, sources, and claims

Research jobs have operation ids, source/turn/token/time ceilings, cancellation, progress, and
idempotent recovery. Deep research never runs inside the pre-turn grading hook. Main-agent
research is observed but cannot be considered capped by prose; governed research uses
Coursebook-owned tools where enforcement is required.

The ledger records actual returned URL/title/fetch date and source type. Provenance is not
support. Claim support is `model_assessed`, with excerpt/locator where legally permitted and
conflict/staleness status. Unreachable old sources remain historical evidence but trigger
review on reuse.

High-risk physical/medical/legal/electrical/mechanical instruction requires authoritative
documentation and an expert-check warning. Coursebook does not certify procedures.
Before procedural steps, a hazard gate identifies exact equipment/manual, protective
equipment, isolation procedure, and stop/professional-help conditions. Live mains, gas, fuel,
pressure-system, structural, and safety-critical vehicle verification are excluded. Physical
completion reported in chat is `self_reported`, never independently verified.

Web/source text is untrusted content, never policy. It cannot alter tools, rubrics, state,
reminders, provider configuration, or exports.

Source/spec versions attach to dependent lessons/checks/media. An updated source produces an
impact list and marks affected generated checks stale pending review; it does not silently
rewrite evidence or migrate learners.
If an imported voice/model is unavailable during regeneration, the impact flow offers keep
cached original, use text fallback, or choose a new voice/model; it never silently substitutes
a different narrator.

## 10. Media and parent exports

Coursebook-owned tools produce artifacts so `TOOL_MEDIA_RENDERER_AREA` can render their
`MEDIA:` files. Cache by content/spec/source hash and record model/provider/license metadata.

- sourced technical reference: authoritative source and permission status;
- deterministic schematic: sanitized safe-subset SVG from structured facts;
- illustration: visibly labelled, never a measurement/procedure authority.

No arbitrary pack HTML/SVG/PDF execution or active rendering. PDFs are generated from safe
Coursebook templates with selectable text and accessible print layout. Narration includes the
text and voice/language metadata; it is not pronunciation assessment.

All media has a text equivalent, instructional images have descriptions, controls are keyboard
accessible, status is not color-only, reduced motion/theme preferences are respected, and
TTS/image failure leaves a complete text lesson. Imported packs can work offline with cached
artifacts.

Generation and human-sense review are separate passes: comprehension/accessibility, domain
naturalness, cultural/context fit, tone/cognitive load, and operator usability. Automated
review is never labelled native-speaker/expert review; only a real qualified reviewer earns
that label. Voice/model choices are auditioned on actual target-language content.

Parent flow: brief → bounded research/plan → parent edits and approves sources/activities →
generate guide/learner pages/answers/optional narration → offline parent-led use → optional
`parent_reported` reflection. Community export excludes reflections and private material by
construction. Planning uses backend jobs rather than persistent child-related chat sessions
where possible.

There are two approval events: **plan approval** before expensive artifact generation and
**final pack approval** after the actual pages/answers/transcript/activity instructions exist.
Export/use requires the second. Editing between them invalidates the appropriate approval.

Approval binds to the exact plan/content hash, including actual learner pages, answers,
narration transcript, and activity instructions. Any edit to objectives, exclusions,
activities, source text, or media specs invalidates approval and blocks generation until
reapproved.
Activities include setting-specific supervision/safety checks (heat, sharp objects, small
parts, allergies, water, roads, tools). Car activities are passenger-only and never ask for
driver interaction. Parent-confirmed level informs activities, not developmental diagnoses.

Before any sensitive upload, show operation-specific egress: chat/aux provider, external
memory integration, research endpoints, image/TTS provider, local persistence, and community
export. Coursebook never sends schoolwork to external memory through its own paths and shows
host integrations it cannot disable. “Local” means local storage, not local inference.

## 11. Community packs

A pack is versioned declarative JSON/Markdown plus bounded declared media. It contains stable
objective ids, lesson/check/rubric versions, sources, attribution, licenses, content notes,
default dials, and minimum Coursebook version. It contains no executable code, arbitrary tool
calls, provider settings, credentials, local paths, transcripts, learning history, or secrets.

Import steps: stage → validate schema/limits/hashes/MIME → sanitize preview → show author,
end state, sources/support, licenses, content notes, media size, and version → explicit import
→ fresh course/evidence. No compilation call for unchanged material. Placement is optional
and disclosed.

Archive rules: one root, normalized unique paths, no links/devices/includes, bounded file
count/string/list/expanded bytes, hash verification, decoder/MIME validation, no render-time
remote images, no auto-open links, atomic adopt or complete rejection. Prompt-injection text
stays in the untrusted content channel.

Updates are previewed migrations only after migration is implemented and tested; v1 refuses
incompatible upgrades and keeps the working version. Stable ids carry evidence; changed
rubrics are versioned; removed objectives retain archived evidence. Reimporting the same pack
offers **Resume existing enrollment** or **Create fresh enrollment**, never a silent duplicate
or reset. Pack, course, and enrollment ids are distinct. Local forks retain attribution.

Export defaults to no license until the author chooses. Distinguish local adaptation from
redistribution; ND/unknown-license content cannot be published as remixable. Track rights per
artifact. Linked sources are not bundled by default. Export uses an allowlisted schema and
previews all prose/prompts/media/metadata; it does not promise automatic PII detection or
removal. Unknown-license private imports may carry warnings; public distribution rejects them.

Trust states are separate: integrity verified, automated checks passed, human review recorded,
and model-assessed source support. No universal “safe/true” badge. Correction/revocation is
supported. A public registry requires maintainers, CI, report/takedown, license-dispute, and
spam processes; local import/export does not depend on that service.

## 12. Jobs, reminders, usage, and failure behavior

Backend job service handles planning/research/media/export. `POST /jobs` returns quickly;
Desktop polls by operation id and can cancel/reconnect. Socket is an optional optimization,
never required on OAuth remotes. Restart reconciles interrupted jobs without duplicate spend.
Jobs persist request brief/input references and safe resume checkpoints, so a failed/cancelled
job can be edited and retried without reconstructing the form. Cancellation marks the job and
stops future stages; an already-running provider call reconciles its result by operation id
and cannot produce duplicate artifacts or evidence.

Generated downloads use an authenticated artifact endpoint plus
`captureGatewayFileDownload()` on an explicit user gesture. Import uses a backend upload route
where supported or an explicitly local file-grant flow; raw `file://` remote paths are never
opened. Export completion has downloading/cancelled/failed/saved states, not just file-written.

Usage events are separate from lesson transitions. Record actual calls, provider/model,
tokens/cache fields when exposed, operation duration, artifacts, and unknowns. Never fabricate
missing values or dollar savings. Budgets stop future governed work at safe boundaries; they
cannot undo an overrun.

Reminders require an explicit verified delivery channel or a clearly selected local-only mode.
Show timezone, destination, quiet hours, frequency, test action, and last delivery error.
Omitted/`origin` delivery is never represented as Telegram delivery. Stable job ids make
creation idempotent through list-by-namespaced-name → reuse. `cron.manage` has no update or
idempotency key: schedule changes require remove+add, and the returned random job id is stored.
Scheduling and DST are evaluated in the backend's declared timezone, tested separately from
the Desktop display timezone.

Provider/aux/web/image/TTS/PDF failures produce visible degraded states. No fabricated lesson,
source, media, mastery, or successful delivery. Offline imported content remains usable.

## 13. UI contract

The detailed visual and interaction contract is `UX_SPEC.md`; this section is only the
architectural summary. The signature lesson view pairs the real Hermes chat with a
Coursebook context pane rather than reimplementing chat.

One native Coursebook page with four task-oriented views:

1. **Learn:** current objective, expected action, hint/answer/skip, sources, media, progress.
2. **Plan:** end state, evidence, milestones, dials, version/update preview.
3. **Library:** create/import/bundled/community packs, licenses, sources, local forks.
4. **Parent:** brief, approval, pack preview/export, reflection.

Within each course, **Textbook** is the section navigator, **Notebook** contains saved moments,
and **Quizzes** contains past attempts. A quiz review shows stimulus, the learner's answer,
observed rubric criteria, feedback, assistance class, sources, and grading provenance. Actions
include Review lesson, Try a new version, Dispute grade, and Save to notebook. Reviewing a past
quiz never consumes a retry or mutates its evidence; retrying creates a new attempt/run.

Course list and operation status remain visible without becoming a file manager. Empty,
loading, offline, degraded, revoked-grant, detached-session, and failed-job states each have
honest copy and a recovery action. No focus/navigation hijack from background jobs.
Pause/abandon, skip/late homework, retry, review queue, archive/delete, recovery export, and
imported-content deletion are explicit workflows with confirmation and recovery semantics.

Course/enrollment state is scoped by `(connection_id, profile, course_id, enrollment_id)`;
Desktop views and REST queries carry that owner explicitly rather than assuming a global
profile name is unique.

Lifecycle commands are distinct: archive enrollment (reversible), delete bound chat (course
evidence retained), delete imported pack content (retain evidence and mark content frozen),
and delete personal course data (explicit destructive scope). Deletion never claims to erase
Hermes' own transcripts, backups, provider-side data, or artifacts still referenced by another
course. Shared artifacts are reference-counted; tombstones preserve required attribution and
audit history without claiming indefinite retention of sensitive raw input.

## 14. Required live probes before full implementation

1. Runtime/stored ids across create, first turn, resume, and compression in every hook/event.
2. Sentinel `pre_llm_call` injection replay on this exact runtime; source docs and persistence
   code disagree about ephemerality, so verify provider-bound messages after restart.
3. Actual context discovery for an isolated cwd inside/outside a git repo and local/remote.
4. Owned aux structured grading latency/timeout/invalid JSON/outage under the intended model.
5. Owned tool → artifact → `MEDIA:` renderer on local and remote plus disabled-media fallback.
6. Explicit vs omitted cron delivery targets; no real external send without user authorization.
7. Backend `submit_attempt` remains authoritative when the chat hook is disabled/times out.

These probes gate implementation details, not the product concept.

## 15. Work packages

1. **Foundation:** manifest, unified package, native route, DB migrations, schemas, job service.
2. **Identity:** isolated workspace, Coursebook policy writer, create/adopt/resume/detach.
3. **Learning kernel:** objectives/checks/attempts/transitions/evidence/grading gate.
4. **Research/media:** source ledger, budgets, artifact cache, native media, text fallback.
5. **Packs:** schema, safe import/export, privacy/license/trust previews, version migration.
6. **Parent:** brief/approval/guide and learner export/reflection.
7. **Product breadth:** recipes, cadence, dials, challenge-out, Companion, reminder setup.
8. **Hardening:** concurrency, crash recovery, malicious packs, remote topology, accessibility.
9. **Submission:** README/disclosures, validation, fresh-install QA, catalog PR, rehearsed demo.

Implement 1→3 before polishing UI or generating a large content library. The learning kernel
is the differentiator; everything else depends on its correctness.

## 16. Acceptance gates

### Identity/state
- duplicate submissions and two windows commit once;
- timeout/late callback cannot change a newer revision;
- restart after every state restores the same state;
- rename/branch/edit/delete/compress/repeat behave explicitly;
- replan preserves and maps evidence;
- unrelated sessions receive no Coursebook context.
- any syllabus section opens its own durable page/run; returning backward preserves later
  evidence and does not require scrolling one course thread;

### Learning/grading
- wrong/irrelevant answers do not pass;
- flawed question/key/rubric fails closed before learner grading;
- answer-shown/hint/override evidence is correct;
- grade dispute is inspectable;
- misconceptions require repeated evidence;
- unexpected phrasing triggers appropriate clarification, not automatic failure;
- capstone measures the declared end state.
- physical completion is labelled self-reported, never independently verified;
- past quiz review is read-only; a new version creates a fresh attempt without overwriting it;
- notebook saves retain course/objective/source provenance and exclude personal notes/raw
  excerpts from community packs;

### Security/content
- pack/web prompt injection cannot change policy/tools/rubrics/state/reminders/exports;
- traversal/archive bombs/links/active SVG/remote images/bad MIME reject safely;
- offline cached content works; source staleness is visible;
- rights/attribution and ND/unknown-license restrictions are enforced;
- exports contain no private state or unrequested upload.
- reimport supports both resume-existing and deliberately fresh enrollment.
- failed jobs preserve the brief and resume checkpoint; retry never duplicates artifacts;
- export covers saved/download-failed/cancelled states with an authenticated download path;

### Reliability/accessibility
- Parent edits invalidate approval; setting/supervision checks and passenger-only car rules
  are enforced.
- Backend timezone/DST behavior is tested independently of display timezone.
- provider/web/media failures do not fabricate outcomes or lose usage;
- jobs cancel/reconnect/recover without duplicate artifacts;
- keyboard-only/text-only/reduced-motion/no-media paths are complete;
- local/remote behavior is explicit, not silently wrong;
- fresh install/enable/restart/revoke/uninstall and validate/doctor pass.

### Demo/submission
- rehearsed fresh-install demo below 90 seconds;
- no fake live research; precomputed artifacts disclosed;
- catalog PR pinned to 40-hex commit and form submitted on time.

## 17. Demo strategy

Target 82–86 seconds with visible chapter cuts, not nine latency-sensitive live operations.
Precompute lesson/media packs and disclose that. Show live local import, one wrong answer and
its governed retry, override/evidence semantics, parent approval/export, pack privacy preview,
and restart recovery.

The strongest sequence is:

1. import a prepared classroom and start with fresh evidence;
2. answer incorrectly and watch the rubric/state/retry change;
3. show the sourced visual and text alternative;
4. approve/export a parent lesson page;
5. export an allowlisted community pack with no private learning events and a full content
   review;
6. restart and resume the exact lesson.

Include one brief Notebook save → exact textbook section jump to demonstrate that the course
is navigable rather than one endless thread; the full timed composition is `UX_SPEC.md`.

Close: **“A chat answers. Coursebook makes the next step depend on what you did.”**

The Japanese fixture uses the vault-derived personal policy: Japanese script + romaji +
English at L0, with furigana/romaji as independently fading scaffolds. It evaluates contextual
usage through a relationship/addressee/intent/register envelope, not one literal translation.
The contest-safe check is context selection; an open explanation can additionally demonstrate
bounded aux grading. Actual wording and native-usage claims must be freshly sourced before
pack authoring; no unavailable canonical vault finding is cited as reviewed evidence.

## 18. Final position

The defensible winning entry is not the largest AI-tutor feature list. It is the plugin that
visibly and reliably turns learning into a governed Hermes workflow, with reusable community
content and a parent lesson studio built on the same kernel.

`AUDIT.md` records the adversarial findings that led to this specification and the remaining
live probes. No further broad feature design is needed before those probes and work packages.
