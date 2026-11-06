# Coursebook pre-build adversarial audit — 2026-11-06

Scope: audit v7 `PLAN.md` before implementation. No plugin code was written. Findings below
come from the live Hermes source tree, official SDK/plugin documentation, and the research
sources listed at the end. This is not a claim that Coursebook improves learning; no learner
study has been run.

## Bottom line

The product thesis is strong and still worth building: a governed, inspectable learning
workflow with user/community course packs and a parent lesson studio. The v7 plan is **not yet
safe to implement as written**. Several core mechanisms were specified at the wrong authority
layer, and the schedule confuses feature breadth with an integrated, reliable submission.

The corrected architecture is:

> Desktop is the control surface. A profile-scoped Python backend owns course state, policy,
> grading, artifacts, and pack validation. SQLite is authoritative. Hooks are adapters between
> Hermes chat turns and that backend. A chat transcript is a view of a lesson, never its source
> of truth. Pack and web content are always untrusted data.

---

## Release-blocking findings

### R1 — A title is not a stable lesson identity

v7 says `Coursebook · <slug> · <node>` is the durable identity, with id/title/lineage checks.
That fails on legitimate user actions: renaming, deleting, archiving, editing, branching,
compression, runtime-id eviction, and repeating a lesson. Titles are unique per state DB
(`hermes_state_schema.py:136`), so a repeat lesson can also fail to acquire the same title.
`session.create` is lazy and returns both runtime `session_id` and `stored_session_id`.

**Decision:** create a random `course_id` and `lesson_run_id` in Coursebook's DB. Bind the
profile, runtime id when live, stored id after the first turn, exact cwd fingerprint, course
id, run id, and current compression tip. Titles are display strings only. Adopt-before-mint
uses the DB binding and in-flight create lock; title lookup is only recovery evidence, never
identity. Repeating a lesson creates a new run. Branch/edit/rename/detach are explicit states,
not silently adopted chats. A deleted chat preserves course evidence and offers a new run.
No recency fallback.

### R2 — “Coursebook decides” needs a fail-closed gate, not only observers

`pre_llm_call` and `post_llm_call` are bounded hooks. On timeout or error they are skipped;
post-turn hooks only observe successful turns. See `hermes_cli/plugins_dispatch.py:42-52`,
`agent/turn_finalizer.py:494-505`, and the hook reference. A post-turn hook therefore cannot
be the sole grading/advance mechanism. An abandoned timed-out thread may also finish later;
late writes must not mutate current state.

**Decision:** evaluate a submitted answer in `pre_llm_call`, inside a short internal deadline
strictly below Hermes' hook timeout. The callback catches all errors and returns a local
`needs_retry` response/block when grading cannot finish; no provider/model inference occurs
for that turn. A successful grade commits the state event *before* returning the teaching
context. `post_llm_call` only records the resulting assistant snapshot. Late callbacks carry a
turn nonce and compare-and-swap fence; stale callbacks are discarded.

There is a UX consequence: a failing aux model must produce an immediate local retry message,
not a 30-second stall. If the gate cannot maintain this latency under the configured provider,
the lesson remains paused with a manual override; it never advances by timeout.

The authoritative operation is an explicit backend `submit_attempt` command called by the
Coursebook UI/owned tool, not merely a hook callback. It returns the committed verdict/next
action. The free-text chat hook invokes the same command; if it is skipped/fails open, the
next Coursebook action reconciles the pending attempt and refuses advancement. This also
supports non-chat attempts without pretending Hermes' entire chat is transactional.

### R3 — Untrusted pack text cannot become `AGENTS.md`

Imported/community material and web pages are indirect-prompt-injection input. Declaring a
pack “non-executable” does not make its natural-language instructions safe. OWASP explicitly
recommends treating external content as untrusted and separating it from trusted instructions.

**Decision:** Coursebook writes `AGENTS.md` itself from a fixed, versioned policy template.
It contains only Coursebook behavior rules, never author-supplied text. Pack prose, source
extracts, imported syllabus prose, and learner schoolwork remain content records, passed to
the model as clearly delimited untrusted material. They cannot change tool authority, state,
grading rubrics, reminders, exports, or provider configuration. User-edited policy fields are
limited to typed values; arbitrary “teacher instructions” are a separate untrusted preference
channel with declared limits.

### R4 — Workspace/context assumptions were incomplete

The old design assumed cwd-only `AGENTS.md`. Current `agent/prompt_builder.py:1589-1614`
loads an AGENTS chain from git root through cwd. Parent repos can therefore add instructions.
`CLAUDE.md` and `.cursorrules` may also be discovered. Remote/container cwd semantics differ
from local-host paths.

**Decision:** the Python backend creates each isolated workspace outside any git root, with
only the Coursebook-owned policy file. It writes no `CLAUDE.md` or `.cursorrules`. Session
creation verifies actual context discovery, not just that a path exists. The backend and chat
must share a filesystem namespace; otherwise Coursebook offers its REST-driven workspace
experience or reports the topology honestly instead of pretending the same local path works.
A folder grant alone does not establish a backend cwd.

### R5 — Authoritative state belongs in SQLite, not competing files

`events.jsonl` + `state.json` + lesson JSON + UI preferences creates multiple authorities and
crash/concurrency problems. The plugin provides `plugins.plugin_storage.plugin_db()` with WAL
and profile-scoped durable storage.

**Decision:** one Coursebook SQLite DB per active profile holds courses, plans, checks,
attempts, transitions, session bindings, source evidence, artifacts, budgets, and idempotency
keys. Every state change is one transaction with an expected current revision. Markdown,
JSON, PDFs, audio, and pack files are generated exports/artifacts. Export rebuilds from DB;
DB rebuild never depends on Markdown. `state.json` is not authoritative. Store large blobs
outside SQLite with content hashes and transactional metadata.

### R6 — Pack integrity is not pack safety, truth, or permission

Hashes prove bytes did not change; they do not prove the original bytes were safe or correct.
A GitHub author name is attribution, not cryptographic authorship. “Source checked” can be
mistaken for human fact review. “Licensed” is not a verified copyright claim.

**Decision:** distinguish four states: integrity verified, automated checks passed, human
review recorded, and source support assessed. No “verified/true/safe” umbrella badge. Signed
hashes are optional authenticity evidence, not a safety guarantee. Preserve SBOM-like pack
manifests, per-file hashes, size/count limits, decompression limits, MIME sniffing, active
content rejection, and path/symlink isolation. Reject HTML/SVG/PDF/script active content from
untrusted packs unless sanitized by a pinned parser. Images receive no network fetches at
render time. Markdown is sanitized; no arbitrary links auto-open. Version migration is always
previewed. Support author correction/revocation notices and “keep local / migrate” choices.

### R7 — Source provenance does not establish claim support

`post_tool_call` proves a tool returned content. It does not prove the model used it faithfully.
A second LLM saying “supports” is still an assessment, not ground truth. Retrieved pages can
contain injection, and old packs can cite stale/dead sources.

**Decision:** label support `model_assessed` and keep the relevant source excerpt and locator
when legally permitted. Otherwise retain URL/title/date and a generated claim/support note,
not an unlicensed full-text snapshot. Distinguish primary/secondary sources, publication and
fetch dates, staleness, unreachable sources, and conflicting evidence. High-risk physical,
medical, legal, electrical, or mechanical steps require authoritative documentation and a
visible expert-check warning; Coursebook does not certify the procedure.

### R8 — Generated media needs provenance and capability degradation

Generated technical illustrations can look authoritative while wrong. Generated SVG/HTML/PDF
can carry active content. TTS may be unavailable, mispronounce language, or differ across
providers. `TOOL_MEDIA_RENDERER_AREA` only renders `MEDIA:` files attributed to the package's
own tool calls; an arbitrary aux-generated file does not automatically appear in chat.

**Decision:** media passes through Coursebook-owned tools and artifact records. Use native
renderers only for tool-produced files. Every visual is labelled sourced technical reference,
deterministic schematic, or illustrative generation. Illustrative generation never supplies
measurements or procedural authority. Sanitize deterministic SVG to a safe subset; do not
render arbitrary pack HTML. PDFs are generated from Coursebook templates with accessible text
and print layout. Image/TTS failure leaves a fully usable text lesson with an explicit
unavailable label; never block learning on media.

### R9 — The time-estimate example was fabricated, not evidence-based

The Japanese `180–240 hours` range was not derived from a validated FSI-to-conversation/self-
study conversion. Adding `basis: fsi` does not validate it. FSI provides class-hour estimates
for professional working proficiency in an intensive program, not this target.

**Decision:** remove that numeric example and any hard-coded scaling factor. Display schedule
arithmetic separately from attainment uncertainty: “At 3 × 25 min/week, your 24-week calendar
contains 30 scheduled hours.” FSI may appear as context with explicit non-transferability.
An attainment estimate must be `model_estimate`, low confidence, with reasoning and evidence
limits, or omitted. After actual sessions, report observed pace without extrapolating mastery.

### R10 — One passed item is not mastery; scaffolding contaminates independence

The eight-state sequence currently allows immediate guided and solo attempts to establish a
node. Familiarity, hints, visible answer context, phrasing, and grader leniency can produce a
false pass. Interleaving, fading, and two-fail rules are design heuristics, not universally
validated prescriptions.

**Decision:** separate `instruction_complete`, `independent_evidence`, and `delayed_evidence`.
A same-session solo attempt with no answer/scaffold in view can record independent evidence;
it cannot alone establish durable mastery. Milestones require the evidence criterion's stated
number/diversity of attempts. Review scheduling records cold retrieval separately. Challenge-
out uses a fresh varied check, not a replayed item. Never label a learner “mastered” globally;
show the evidence history.

The generated question/rubric itself also needs pre-lesson validation: objective alignment,
unambiguous stimulus, correct reference answer, accepted alternatives, and rubric consistency.
The grader receives a minimal envelope with stimulus, learner instructions, reference answer/
scoring examples, response, locale, allowed conventions, and attempt id. A flawed check fails
closed. Sixty cases are only a smoke-test floor per grader configuration/domain/language slice,
re-run on model/prompt/schema/language changes, not universal evidence of grading validity.

### R11 — Multilingual and open-response grading needs construct separation

Grammar, dialect, accent, concision, translation choice, and conceptual understanding are
different constructs. A fluent wrong answer and a correct answer in unexpected phrasing are
both common. Automated evaluation may vary across realistic learner language.

**Decision:** rubrics declare target construct, accepted variation, register/locale assumptions,
and whether language form itself is being assessed. Return observed evidence per criterion,
not only a verdict. “Unexpected phrasing” triggers clarification/alternate check rather than
an automatic misconception. Keep native-language support where requested. Validate against
correct/partial/wrong answers with realistic spelling, dialect, code-switching, and non-native
phrasing; publish per-category errors, not just aggregate accuracy. Learners can inspect and
dispute a grade.

### R12 — Hints and overrides need auditability without punishment

A learner can ask for the answer, branch into another chat, or repeatedly override. That is
legitimate autonomy, but must not be represented as independent evidence. Excessive friction
also makes a tutor worse than a normal chat.

**Decision:** record `cold`, `hinted`, `answer_shown`, `self_reported`, and `override` evidence
classes. “Explain”, “hint”, “show answer”, “skip”, and “move on” are always available and have
clear consequences for the evidence map, never guilt messaging. Overrides advance access, not
mastery. The user can reset/dispute evidence explicitly.

---

## High-priority product and reliability findings

### H1 — Chat control can be lost through normal Hermes actions

The user can rename, change model/cwd/tools, compact, branch, edit/delete, or open a second
window. Coursebook cannot treat a chat as a locked application window.

**Decision:** define `active`, `paused`, `detached`, `branched`, `completed`, and `orphaned`
bindings. Validate binding at every pre-turn. Changing cwd detaches governance. Model changes
are recorded and trigger grader/policy compatibility checks. Compaction updates the tip without
losing the run. Edited historical turns never rewrite committed evidence; later attempts are
new events. Branches start ungoverned until the user explicitly creates a forked lesson run.
Multiple windows use DB transactions and revision fencing.

### H2 — “Bounded research” needs executable budgets and cancellation

A phrase in AGENTS.md cannot cap cost. `ctx.llm.complete_structured` supports timeout and
max_tokens; usage results include input/output/cache tokens and host-estimated cost when
available. Hook timeouts also bound callbacks.

**Decision:** a backend job service owns research, planning, media, and exports with explicit
operation ids, cancellation, progress, timeout, attempt counts, token ceilings, source count,
artifact count/bytes, and idempotent resume. The main teaching agent's tool calls are observed
and counted but cannot be assumed capped by prompt text; use Coursebook-owned research tools
for governed lesson research and a session budget pause at the next turn boundary. Never kill
a turn mid-write. Media jobs must not be repeated after an uncertain response without checking
the operation ledger/cache.

### H3 — Hooks must return quickly; backend jobs must not block Desktop

Planning/research/PDF/TTS can exceed RPC/hook/UI timeouts. `host.request` defaults to 30s
unless overridden; `ctx.rest` jobs need their own lifecycle.

**Decision:** `POST /jobs` returns an operation id quickly; Desktop polls (socket is optional,
no-op on OAuth remotes). Progress is honest and cancellable. Pre-turn grading uses only a
small bounded aux request, never deep research or generation. A closed/reopened cockpit
reattaches to running jobs by id. No unbounded daemon threads; backend-owned worker lifecycle
and restart recovery are required.

### H4 — Cron delivery is not automatic

A desktop-created cron job with omitted/`origin` delivery can remain local and never message
the user. The cron contract supports explicit `deliver`, pause/resume, and delivery errors.

**Decision:** reminders are configured only after the user selects/verifies a live gateway
channel or explicitly chooses local-only. Show target and timezone at confirmation, max/quiet
hours, last delivery error, and a test action. No promise of Telegram just because a gateway
exists. Job names include stable course/reminder ids and creation/update is idempotent.

`cron.manage` actually exposes list/add/remove/pause/resume, not a general update operation,
and creation mints a random UUID without an idempotency key. Implement namespaced-list →
reuse for creation; store the returned id; use remove+add for schedule changes. Do not claim
inherent update idempotency or timezone fields the RPC lacks.

### H5 — Cost accounting and cost control are different

`pre/post_api_request` can observe usage even on turns that do not complete normally; usage
availability varies. Cache hit fields do not prove savings without a baseline. Prompt research
can cost more than an ordinary answer.

**Decision:** separate per-turn usage events from lesson transitions. Record actual calls,
provider/model, tokens/cache fields when exposed, artifacts, operation duration, and unknowns.
Do not infer missing values. “Savings” requires a same-task measured baseline, which is not a
release requirement. Session budget stops future governed work; it cannot refund an overrun.

### H6 — Pack and source size/type attacks remain after banning code

Zip bombs, path traversal, duplicate names, huge Markdown, malformed Unicode, remote images,
malicious PDFs/SVG, instructions hidden in media metadata, oversized rubrics, and recursive
pack includes all need explicit handling.

**Decision:** fixed archive schema; no includes; path normalization; file count/size/total
expanded limits; media MIME and decoder validation; hash/size verification before import;
no symlink/hardlink/device files; one pack root; no runtime remote URLs except user-initiated
source refetch; normalized ids; bounded strings/list lengths; sanitized text previews;
transactional staging then atomic adopt. A rejected import leaves no course or background job.

Pack identity and enrollment identity are separate. Reimport offers **Resume existing
enrollment** or **Create fresh enrollment**; it must not prevent a parent/teacher deliberately
starting another learner with the same pack.

### H7 — Pack licensing and adaptation rights need concrete policy

The current `CC-BY-4.0` example is not universal. NC/ND/SA choices have compatibility and
remix implications; source citations do not grant media redistribution rights.

**Decision:** default export license is unspecified until the author chooses. Explain local
adaptation vs redistribution. ND content cannot be offered as a remixable community pack.
Track attribution and license per text/media artifact. Linked sources are not bundled by
default. Authors affirm rights; reviewers can reject or take down content but Coursebook does
not certify copyright ownership.

### H8 — Accessibility and low-connectivity behavior were missing

**Decision:** all audio has text, all instructional images have alt text/long descriptions,
interactive controls are keyboard accessible, status is not color-only, and PDFs contain real
text rather than page screenshots. Respect reduced motion and theme variables. Do not infer
learning style. Allow text-only lessons and parent packs. Imported artifacts work offline;
source refresh and generation clearly require network/provider access.

### H9 — “Parent reflection” is not child assessment

**Decision:** label parent observations `parent_reported`; never combine them with automated
mastery. Do not request names, birthdates, school identifiers, or full schoolwork by default.
Offer paste redaction and local-model recommendation, with provider disclosure before upload.
Community export excludes parent reflections by construction. UNESCO/NIST guidance supports
human oversight and privacy; no COPPA-compliance claim.

Privacy disclosure is per operation, not a generic “your model provider” sentence. Lesson chat
may reach the selected chat provider and any configured external memory provider; planning and
grading may reach their aux provider; research reaches search/fetch services and named sites;
image/TTS reaches their respective providers; logs/session DB/artifacts persist locally;
community export releases only the reviewed pack. Parent planning uses backend jobs rather
than persistent child-related chats where possible, avoiding unnecessary memory/transcript
retention. No external-memory sync of schoolwork is permitted by Coursebook's own paths, and
the preflight shows any host-level integration it cannot disable. “Local” describes storage,
not automatic local inference.

Parent approval is bound to an exact plan/content hash. Editing objectives, exclusions,
activities, source text, or media specs invalidates approval and returns the pack to review;
generation cannot proceed under the old approval. Activity planning includes a safety
checklist appropriate to the setting: heat, sharp objects, small parts, allergies, water,
roads, and tools require age-appropriate supervision. Car activities are passenger-only and
must never require driver interaction. Coursebook suggests activities/content prerequisites,
not disability, giftedness, attention, or developmental diagnoses.

### H10 — Public ecosystem launch is a separate operational system

A public Git-backed pack registry needs maintainers, review SLAs, report/takedown flows,
version immutability, malware scanning, license disputes, correction/revocation, and spam
control. That cannot be implied by “add a JSON index.”

**Decision:** v1 supports local file import/export plus a bundled example pack. A read-only
community index is a launch layer only after its repository, validation CI, review policy,
and takedown owner exist. Submission templates can ship without promising instant publishing.
This preserves the requested sharing capability without making an unstaffed public registry a
release dependency.

---

## Product/demo/schedule corrections

1. The 88-second script has too many model/network transitions and too little narration time.
   It is not a reliable single-take live demo. Pre-generate packs before recording, disclose
   that generation was precomputed, and use the video to prove live import, grading, gating,
   export preview, and resume. Keep media generation in the README/extended video, not as a
   live dependency in 90 seconds.
2. The primary winning shot is not “three recipes.” It is **a wrong answer causing a governed
   state change that an ordinary chat cannot guarantee**, followed by restart recovery.
3. Community import should open the lesson immediately, but placement must not add a surprise
   model call. Make placement optional in the demo and explicit in the UX.
4. Parent mode should export a polished parent guide + learner page, not try to show four
   artifact formats in fifteen seconds.
5. Do not claim a “single continuous run” if cuts hide waits. Use visible chapter cuts and say
   “lesson packs generated beforehand”; never present cached output as live deep research.
6. v7's ~66–70 hours against ~50 excluded integration buffers, docs, test fixture authoring,
   remote testing, review changes, and recording. The full product cannot honestly be promised
   by Nov 11 at production quality. Preserve the roadmap; define a coherent contest vertical
   slice rather than hiding partially working breadth behind a demo.

## Required contest vertical slice

This is not a feature cut; it is the release boundary between a working plugin and continued
product development.

**Must work end to end for judges:**
- native Coursebook page + course list;
- create from goal with one committed-course plan preview;
- import one bundled/local course pack with safe preview;
- isolated backend-owned workspace and session binding;
- typed check → bounded grading → transactional transition;
- one misconception/retry path with override semantics;
- evidence map and exact restart/resume;
- one Coursebook-owned visual/audio artifact with text fallback;
- parent brief → source/plan approval → parent guide + learner-page export;
- privacy-stripped local pack export and reimport;
- SQLite-backed operation/usage ledger and honest unavailable states;
- clean install/enable/restart/revoke/uninstall and validation/doctor.

**Same codebase, can ship after contest without redesign:** remaining recipe depth, Companion,
cron delivery channel setup, public read-only community index, richer media, capstone/milestone
variants, full dial migration UX. Their schemas should be present but unfinished controls must
not masquerade as functional in the contest build.

## Live probes required before coding the full vertical slice

These are small executable probes, not more planning:

1. Create a plugin-owned session, then capture the exact runtime/stored session ids visible in
   `pre_llm_call`, `post_llm_call`, `post_tool_call`, and `session.info` after first turn,
   resume, and compression.
2. Inject a sentinel with `pre_llm_call`, restart/resume, and inspect actual provider-bound
   messages to settle the doc/code contradiction about `api_content` replay on this runtime.
3. Verify an isolated course cwd loads only the intended Coursebook AGENTS policy, including
   when launched from a git repository and on the actual local/remote topology.
4. Measure `ctx.llm.complete_structured(task=<owned>)` latency and failure semantics for the
   grader with the intended aux route, including timeout, invalid JSON, and provider outage.
5. Verify Coursebook-owned tool → artifact → `MEDIA:` → native renderer for local and remote
   backends, including TTS/image-disabled fallback.
6. Create a reminder with explicit vs omitted delivery and inspect stored job/delivery target;
   do not use a real user's Telegram until explicit delivery authorization is requested.
7. Verify the backend `submit_attempt` command remains authoritative when chat hooks are
   disabled, time out, or are bypassed by a non-chat UI attempt.

## Acceptance expansion beyond v7

- Answer arriving after timeout/restart cannot mutate a newer lesson revision.
- Two Desktop windows submitting simultaneously produce one attempt/transition.
- Same node can be repeated without title collision; renamed/branched/deleted sessions behave
  explicitly.
- Pack with prompt injection cannot modify policy, rubric, tools, export, or reminder target.
- Zip bomb/traversal/symlink/active-SVG/remote-image/malformed MIME cases reject cleanly.
- Offline imported lesson can render cached text/media and record attempts; generation waits.
- Model/provider outage does not advance evidence, lose usage records, or fabricate media.
- Source death/staleness preserves old evidence but visibly prompts review on next use.
- ND/unknown-license media cannot be published as remixable content.
- Grade dispute, answer-shown, skip, and override produce correct evidence classes.
- Keyboard-only, text-only, reduced-motion, and no-TTS/no-image flows remain complete.
- Demo is rehearsed below 90 seconds using only operations that work on a fresh install.
- Parent edits after approval invalidate the approval and prevent generation until reapproved.
- Parent activities carry setting/supervision checks; car activities never involve the driver.
- Backend timezone/DST behavior is tested separately from the learner's display timezone.
- `jsonschema` is declared as an explicit plugin dependency; invalid grading output cannot be
  accepted merely because the optional host package is absent.

## Research anchors

- OWASP LLM Prompt Injection Prevention Cheat Sheet: untrusted external content and separation
  of trusted instructions from data. https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- NIST AI 600-1 Generative AI Profile: avoid extrapolating narrow assessments; review/verify
  sources; document provenance. https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- UNESCO Guidance for Generative AI in Education and Research (2023): human-centered use,
  privacy and age-appropriate use. https://www.unesco.org/en/articles/guidance-generative-ai-education-and-research
- FSI/NFATC language training: Category I 600–750 and Category IV 2200 class hours for its
  intensive program/proficiency target, not a conversational self-study conversion.
  https://www.state.gov/national-foreign-affairs-training-center/foreign-language-training
- VanLehn (2011): tutoring/ITS comparison and caution around 2-sigma claims.
- Adesope et al. (2017): practice testing; Bisra et al. (2018): self-explanation;
  Cepeda et al. (2006): distributed practice. These motivate design, not Coursebook efficacy.
- Sheeran et al., 642-test planning meta-analysis: implementation-intention outcomes vary by
  outcome; do not present d=.27 as a universal adherence effect.
  https://kops.uni-konstanz.de/entities/publication/cf394f1f-49d8-4256-bf24-df7af124514a
- Creative Commons license overview and adaptation conditions. https://creativecommons.org/cc-licenses/
- Stanford SCALE, AI Tutoring is Not a Monolith: evidence varies by tutoring model and
  implementation. https://scale.stanford.edu/research-in-action/ai-tutoring-not-monolith

## Decision

Proceed to the six small live probes, then write implementation work packages against the
corrected architecture. Do not start with the visual cockpit or course-content generation;
those would hide the hardest correctness problems until too late.
