# Privacy and egress

Disclosure is per operation, not one generic "your model provider" sentence. This document states
what each Coursebook operation can send, where it goes, and whether that path exists in this
build.

Scope: version 0.1.0, the CB-014 candidate. Read the state column first. **Working** means the
operation was run against this build and passed; **Implemented** means the code path exists and is
exercised by the test suite; **Disabled** and **Absent** mean there is no path that could send
anything. The Desktop page does not mount on this candidate (CB-QA-09, `docs/REVIEW_CB014.md`), so
a shipped backend path is not reachable from the UI. That is a reachability problem, not a privacy
one: nothing below becomes true only when the page renders.

Coursebook holds no vendor credentials and reads no provider key. Its provider calls go through a
seam the Hermes profile already configures, so the user's provider choice, egress rules and SSRF
checks apply. The one direct outbound request is the **first-use download of its own local speech
model weights** from Hugging Face (see the pronunciation row below); no audio is ever uploaded on
that path.

## Egress inventory on this candidate

| Operation | Destination | What is sent | State in this build |
| --- | --- | --- | --- |
| Install, enable, load | local only | Nothing. The package is read from disk, and load-time reconciliation is a non-creating schema-version read | Working |
| Pane health check | the local Hermes backend: `ctx.rest('/health')` → `/api/plugins/coursebook/health` in the same process | Nothing leaves the machine. The first successful `health.get` provisions the profile database; the lifecycle hooks do not (CB-014-R1) | Working |
| `coursebook_status` tool | local only | Nothing. Reads local health, the mounted-method list and the contract inventory and returns JSON to the agent | Working |
| Plan and lesson generation (a `plan` job from the job tick) | the host plugin LLM route (`ctx.llm`) — the model configured for the Hermes profile | The goal, recipe, dials and locale; the bounded research query list and source briefs with capped excerpts. Each excerpt is wrapped in an explicit untrusted-data envelope and the prompt says it is data, never instructions; the source id is the only locally minted identifier. For a lesson, the approved plan, the section and the objective. A separate validation call re-reads the candidate artifact, the learner page and the source briefs, including the same enveloped excerpts | Implemented; unreachable from the Desktop behind CB-QA-09 |
| Research inside a plan job | the host `web_search` and `web_extract` tools, so the user's configured search backend, and then the named sites themselves | The goal-derived queries (capped before any call), then the URLs returned by search. Fetched text is kept as a bounded excerpt only and is treated as untrusted data in every later prompt; it cannot change recipe rules, schemas, state or exports | Implemented inside plan jobs. No standalone RPC |
| Lesson chat | the selected chat provider, plus any configured external memory provider (host behavior, not Coursebook's) | The learner message and the conversation history the host sends for any chat. Coursebook injects only the committed public verdict, the permitted next action and the objective id — never a reference answer, rubric internals or provider text | Implemented; subject to the same CB-QA-09 reachability gap |
| Grading, closed checks | local only | Nothing. The answer is compared against the stored reference by a deterministic local grader | Working |
| Grading, open response (auxiliary lane) | no destination | Nothing. No auxiliary adapter is configured in this build (`configure_aux_grader` is never called), so an open response is not sent anywhere and the attempt is recorded as unable to grade rather than passed | Disabled |
| Parent Studio planning | the same host plugin LLM route as plan generation, through a queued `plan` job | The parent brief: title, goal, age band, reading level, duration, setting, materials, exclusions, supervision notes, desired pages and visuals, narration script, locale. `parent.brief.create` refuses the brief unless `egress_acknowledged: true`, so no course is created from an unacknowledged paste | Implemented; unreachable from the Desktop behind CB-QA-09 |
| Image and speech generation | the host `image_generate`/`text_to_speech` tools, using the image and TTS providers configured for the Hermes profile; the returned image URL is fetched directly from an allowlisted `*.fal.media`/`*.fal.run` host | The media prompt and text equivalent for an image; the narration transcript, language and voice for audio. The image download is the provider's own artifact URL, never a URL supplied by the model or a learner. A generated lesson's text equivalents, labels and source references are stored locally. | Implemented in the lesson path when the host binds `ctx.dispatch_tool`; a provider failure degrades to text |
| Pronunciation attempt (`POST /pronunciation/attempt`) | **local only**, with one exception: the first use may download `faster-whisper` model weights from `huggingface.co` and cache them under `<plugin data>/stt-models` | The take is decoded with the host `ffmpeg` binary and scored on this machine by Coursebook's own `coursebook_local_whisper` model. **No audio is uploaded.** The first use fetches model weights only (no learner data) unless the model is already cached. The assessment (transcript, target, locale, provider, model, accuracies, words, verdict) is stored locally; the audio file is deleted after scoring | Implemented and backend-tested; the recording UI is M3-U1 |
| Pack import | a local file the user chose; no upload | Nothing leaves the machine. The archive is read from disk and hashed; a URL is refused, a symlink is refused, and an archive whose bytes no longer match its manifest is rejected | Working |
| Pack export, parent handout PDF | a local file and the local download route | Nothing is uploaded. The archive and the PDF are composed from stored rows, hashed, and served as an attachment from the local backend | Working |
| Reminders | no destination | Nothing. No RPC, no job kind and no storage | Absent |
| Usage accounting | local SQLite only | Provider and model names, token counts, cost and duration from LLM responses, and tool name plus duration for a bound lesson chat. Recorded locally and never reported anywhere | Working (local only) |

### The three chat lifecycle hooks

`pre_llm_call`, `post_llm_call` and `post_tool_call` are registered and are not no-ops.

- `pre_llm_call` reconciles the session binding, classifies the inbound message and grades a real
  answer through the same `attempt.submit` dispatcher the UI uses. It returns `{"context": ...}`
  only after a transition commits, a local `{"action": "block", "message": ...}` when grading fails
  or a refusal is required, and `None` for ordinary conversation or a chat not bound to an
  enrollment. **It provisions nothing.** When the profile has no Coursebook store it returns
  `None` before touching the filesystem; an unreadable store fails closed.
- `post_llm_call` is an observer. It records the assistant snapshot as a lesson segment, fenced by
  the revision and turn nonce captured before the turn; a late callback is discarded.
- `post_tool_call` writes one `usage_events` row — tool name and duration — for a session this
  process saw pass the gate. An unbound chat writes nothing and opens no database. A tool result is
  never altered, and source text stays untrusted content that cannot change policy, rubrics, tools,
  state, reminders or exports.

The hooks forward nothing to a provider themselves. What a lesson chat costs in egress is what the
host chat call costs, plus the context line above.

### Fetched third-party text

Research retrieves pages the user's search backend returned; that text is attacker-controlled input
and is never treated as policy. On the model path it is carried as bounded data, not as a message:
every source row is marked `role: "untrusted_source_data"`, the excerpt sits between
`[[BEGIN-UNTRUSTED-SOURCE-DATA]]` and `[[END-UNTRUSTED-SOURCE-DATA]]`, and marker occurrences in the
fetched text are escaped so page content cannot close the envelope. One shared rule appended to the
plan, lesson and validation prompts says the source array is data, text inside the markers is never
a command, and a source id is not support.

What that does not do: it does not make a model immune to injection, and this document does not
claim it does. A hostile page can still influence the prose a model writes. The harness enforces the
boundary after the fact: recipe and schema rules still run, the provenance lint refuses an invented
URL, title, publisher, DOI or ISBN in the artifact, and a validator cannot move a source to
`supported`/`partial`/`contradictory` without a ledger source id and a verbatim excerpt from that
source. Whether a real quote actually supports the sentence around it remains a model judgment.
Nothing fetched is uploaded anywhere beyond the model call already disclosed above.

## Local persistence

State lives in profile-scoped SQLite:

```
$HERMES_HOME/plugin-data/coursebook/data.db
```

Not inside the plugin directory, because removing the plugin deletes that directory. The path is
resolved per call so a profile switch cannot reuse another profile's handle. `health.get`
provisions the store on first contact and applies migrations `0001`-`0005` (schema v5); the hooks
and the tool never create it. `scripts/install-local.sh` also writes
`<home>/coursebook-single-home.env`, which sets `HERMES_COURSEBOOK_SINGLE_HOME=1` so an isolated
backend pins storage to that install's home instead of escaping to the default profile.

The database holds courses, plans, objectives, checks, attempts, pronunciation attempts, evidence,
transitions, bindings, sources, artifacts, jobs, packs, notebook entries, idempotency keys and the
local usage rows. A pronunciation attempt stores the typed assessment and its dispute trail, never
the audio take or a temporary path.

Hermes itself keeps session transcripts, logs and usage records under `$HERMES_HOME`. Those are
host behavior, not Coursebook behavior. Coursebook does not read them for policy decisions and
does not copy them into packs.

"Local" describes storage. It does not mean the model runs locally. Inference goes to whichever
provider the Hermes profile is configured to use.

## What Coursebook refuses by design

- No external-memory sync of schoolwork through Coursebook's own paths. If a host-level
  integration would sync it anyway, that integration is the host's; Coursebook cannot disable it.
- A parent brief cannot be created until the provider/egress disclosure is acknowledged in the
  contract (`egress_acknowledged: true`). Goal-only course creation has no equivalent hard gate;
  this document is the notice.
- Parent observations are stored as `parent_reported` and are never merged with automated mastery.
  Parent reflections are excluded from community export by construction, not by a promise to strip
  personal data afterwards.
- No request for names, birthdates, school identifiers or full schoolwork by default. Pasted
  material is offered redaction, and the provider is disclosed before any upload.
- Parent planning uses backend jobs rather than persistent child-related chats where possible,
  which avoids unnecessary transcript and memory retention.
- A pack is untrusted data. Its prose never becomes policy, and it cannot carry executable code,
  tool calls or learning history.
- No telemetry and no usage reporting. Usage rows stay in local SQLite and are never sent to
  Coursebook or a third party: no analytics, no crash reporting, no health pings.
- No credentials. Coursebook declares no `requires_env`, stores no key and does not fetch its own
  files. Its only configuration key is `status_include_contracts` (a boolean that adds the
  contract inventory to the `coursebook_status` output). The local speech model is a declared
  Python dependency with a weight download, not a credential.
- A pronunciation take is never retained by this slice: it is a private temporary file deleted
  after scoring, it never becomes an artifact, and no raw audio is stored in the database, a pack,
  an export, a notebook entry or telemetry. A missing local recogniser means "practice only, not
  graded"; no score is fabricated.

## Parent and child boundary

Parent mode means a parent prepares a lesson for a child. Children do not chat with Coursebook, and
Coursebook does not assess a child. Activity planning carries a setting-appropriate safety
checklist (heat, sharp objects, small parts, allergies, water, roads, tools) and suggests content
prerequisites only. It does not suggest disability, giftedness, attention or developmental
diagnoses.

There is no COPPA compliance claim and no child safety certification. Those are not things a
plugin can grant itself, and Coursebook does not claim them.

## Retention and deletion

`contracts/db.v3.json` carries the deletion policy this build implements: deleting a chat preserves
course evidence; deleting an imported pack marks its content frozen and retains evidence; deleting
personal course data is an explicit destructive scope. `enrollment.delete` requires the
`data_scope_hash` the caller previewed, and removes that enrollment's lesson segments, evidence,
transitions, attempts, pronunciation attempts, notebook entries, lesson runs, bindings, usage rows
and enrollment row. Deletion never claims to erase Hermes' own transcripts, backups, provider-side
data, or artifacts referenced by another course.

## Open defects that touch this document

- **CB-QA-10** — `evidence.inspect` returns an open check's reference answer in the L2 projection.
  The answer key crosses the local client boundary while the check is still open. It is not egress,
  and the UI does not render it, but this document does not claim the field is hidden.
- **CB-QA-11** — if the auxiliary grader lane is enabled, learner text would be passed to the
  grader, and an answer carrying instructor-style injection is currently accepted. The lane is
  **disabled in this build**; enabling it requires the structural cross-check that defect records.
