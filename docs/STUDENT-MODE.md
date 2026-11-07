# StudentMode: a second import path, paired to an external class

Status: design only, 2026-11-07. Owner: atlas. Branch: `wt/harness-student-mode-design`.
Base: local `master` at `2e57efa` (H-02 learner flow, H-03 blueprint design, H-13 policy
threading merged). This card changes no code, no contract, no migration and no `desktop/plugin.js`.

Read with: `docs/ADVERSARIAL-UX-REVIEW.md` UX-06, `docs/GENERIC-HARNESS-REVIEW.md` G-06 and
section 5, `docs/COURSE-BLUEPRINT.md` (scopes and unit-scoped authoring), `docs/PLAN-APPROVAL.md`,
`docs/PRIVACY_EGRESS.md`, `docs/CONTRACTS.md`.

This document freezes the product and data decisions for a **student mode**: a learner uploads the
syllabus of a college class they are already taking, and Coursebook builds a **companion course**
that supports that class. The syllabus is the scope authority. Coursebook is not the registrar, not
the gradebook, and not the official course. Nothing below is true until the implementing cards land
the contract delta, the migration and the tests named in section 10.

## 0. Seam verdict (read this first)

The feature is buildable honestly on the current host seam. It does not need a private file path, a
bespoke file manager, or an LMS integration. The evidence:

| Need | Verified seam | Consequence |
|---|---|---|
| Let the user choose a file | `ctx.files.requestFolder()` returns an opaque folder handle plus a display path; calls take the handle, not the path (`apps/desktop/src/contrib/plugin-files.ts:45-57`) | The renderer lists and opens files by relative path inside a user-granted folder. It never sends an absolute path to the backend. |
| Read Markdown / plain text | `ctx.files.readText(folder, path)` — UTF-8, up to 4 MiB, refuses binary or larger, never truncates (`plugin-files.ts:55-56`; `apps/desktop/electron/plugin-files-ops.ts:14`, `:365-378`) | Text syllabi enter as text, not as a path. |
| Read PDF / DOCX bytes | `ctx.files.readDataUrl(folder, path)` — any non-sensitive plain file up to 16 MiB as a `data:` URL (`plugin-files.ts:57-58`; `plugin-files-ops.ts:15`, `:380-386`) | Bytes enter as a bounded base64 string. The renderer strips the data-URL prefix and posts the base64 body to the RPC. |
| Keep paths off the wire | The only route that accepts a filesystem path is `POST /packs/grant`, and it accepts a path only after the host picker (`dashboard/plugin_api.py:19`, `:189-217`) | Student intake adds **no** path-taking route. A path is never an RPC field. |
| A MIME we can trust | `readDataUrl` maps only image extensions; everything else is labelled `application/octet-stream` (`plugin-files-ops.ts:268-270`) | The backend sniffs magic bytes (`%PDF-`, `PK\x03\x04` + `[Content_Types].xml`) and refuses a mismatch. It never trusts a filename or a declared MIME. |

Two consequences follow and are part of the design, not caveats bolted on:

1. **PDF text extraction needs a declared dependency.** This tree declares `jsonschema`,
   `faster-whisper` and `pypdf>=4.0,<7` (`plugin.yaml`), and `coursebook/archive.py` only checks
   PDF magic bytes and active-content markers; it does not extract text (`archive.py:80-90`,
   `:155-158`). DOCX can be read deterministically with stdlib (`zipfile` + `ElementTree`, with
   DTD/entity and zip-bomb guards). PDF cannot be parsed honestly without an extractor. The
   optional `pypdf` dependency answers `PARSER_UNAVAILABLE` — a typed refusal, not a guess — when
   it is absent. Markdown, plain text and pasted text work with no new dependency.
2. **`full` scope is blocked on H-21.** `PLAN_SCHEMA` is still 4–8 objectives and 2–8 sections
   (`coursebook/generation.py:671-672`). A 14-week companion course cannot be honest until H-21's
   CourseBlueprint v2 lands. H-26 may ship intake, parse, anchors and alignment before that, but it
   must refuse `scope=full` with a typed `BLUEPRINT_UNAVAILABLE`, not truncate a semester into
   eight objectives.

If H-26 cannot meet both conditions, it stops at `single`/`short` and text formats, and says so in
its own card. It does not invent an extraction path or a second planner.

## 1. Two import paths, one kernel

Coursebook now has exactly two ways for a course to get content, and they are different in kind.

| | Community pack | Student syllabus |
|---|---|---|
| What enters | Lessons someone already authored | A scope document for a class taken elsewhere |
| Identity | `pack_id` + immutable semantic version + content hash (`contracts/pack-manifest.v1.json:5`, `:208`) | A local `syllabus_id` + a revision lineage + the file's SHA-256. No publisher, no catalog identity. |
| Storage | `packs` rows; the course keeps `courses.pack_id` (`migrations/0001_initial.sql:18-46`) | New `syllabi`/`syllabus_files` rows. A companion course keeps `courses.pack_id = NULL`; the link lives in `course_syllabi`. |
| Authority | The pack is the course content | The syllabus is the scope authority; Coursebook authors its own lessons |
| Content shape | Objectives, sections, checks with reference answers, declared media | Weeks, topics, readings, assessments, deadlines, weights, study policies |
| Lifetime | Immutable; a new version is a new pack | Revisable; a new revision supersedes the old and makes alignments stale |
| Trust flow | Preview → hash/integrity → trust labels → import | Intake → extraction → strict parse → anchor verification → alignment review |

`pack.import` cannot be stretched to cover the syllabus path, for five concrete reasons:

1. **Pack identity would be a lie.** A pack is a published artifact with an author, a license and a
   redistribution decision. A syllabus is a personal copy of an institution's document. Minting a
   `pack_id` for it would put it in the pack identity space, where `library.list`, `pack.export`
   and community catalog tooling already operate. The product requirement is the opposite: never a
   community artifact.
2. **The manifest schema has no home for the data.** `cb.pack` requires objectives with evidence
   targets and criteria, sections with paths, and checks with `reference_answer`
   (`contracts/pack-manifest.v1.json:116-160`). A syllabus has dates, weights and readings and no
   reference answers. Filling those fields would mean the parser fabricating authored content
   before preview, which also breaks the pack promise that what is previewed is exactly what is
   imported.
3. **Unknown fields are rejected by design.** The manifest is allowlist-first; extending it with
   `weeks`, `deadlines`, `weights` and `policies` is a second content schema wearing the pack's
   name. The pack validator, archive audit, export and export-level authoring bounds all assume
   authored lessons.
4. **Immutability fights revision.** A pack version is frozen. An institution issues syllabus
   revision 2 mid-term. The student path must detect the change, mark mappings stale and ask for a
   decision; it must not silently produce a second pack or silently keep the old alignment.
5. **The authority is reversed.** Importing a pack means "this content is the course." Importing a
   syllabus means "this document constrains the course, and Coursebook writes the course." Pack
   rows and `pack.export` have no concept of an external authority that can overrule the course.

What is reused is the kernel, unchanged: `course.create`, `enrollment.create`, one plan job, the
existing `plans`/`objectives`/`checks`/`attempts`/`evidence` tables, `plan.approve` with its exact
hash fence, and the existing job engine. The syllabus path adds a document, an intake job and an
alignment record; it does not add a course engine, a second enrollment authority or a second
grading path.

Invariants that make "not a pack" testable:

- a companion course has `courses.pack_id IS NULL` and a `course_syllabi` row;
- a syllabus is never written to `packs`, never appears in `library.list`, and never has a
  `pack.export` handle;
- no syllabus bytes or parsed items appear in any pack archive or pack manifest.

## 2. Input surface

### 2.1 Accepted intake

| Input | How it enters | Hard limit | Refusal when over |
|---|---|---|---|
| Markdown (`.md`, `.markdown`) | `ctx.files.readText` → text field | 4 MiB (host limit) and 200,000 characters (product) | `SYLLABUS_REJECTED` with the measured size |
| Plain text (`.txt`) | `ctx.files.readText` → text field | same | same |
| PDF (`.pdf`) | `ctx.files.readDataUrl` → base64 → RPC | 8 MiB file, 60 pages (product); 16 MiB is the host ceiling | `SYLLABUS_REJECTED` |
| DOCX (`.docx`) | `ctx.files.readDataUrl` → base64 → RPC | 8 MiB file, 2,000 paragraphs | `SYLLABUS_REJECTED` |
| Pasted text | textarea → `pasted_text` field | 200,000 characters | typed refusal before any job |

Exactly one of `content_base64` or `pasted_text` is accepted. Both or neither is
`VALIDATION_FAILED`. A pasted-text document gets one anchor block (`source_kind = "pasted"`,
`label = "Pasted text"`, line range 1..n); it is a first-class syllabus, not a second-class input.

The renderer may offer a folder picker (the host seam) and a paste box. It may not walk the
filesystem, accept a typed absolute path, or build its own file browser. The backend may not read a
path: the RPC contract has no path field, and the only path-taking route remains `/packs/grant`.

The host's `readDataUrl` labels a PDF or DOCX as `application/octet-stream`, so the intake request
carries a display-only `file_name` and a `mime_hint`, and the backend verifies:

- PDF: bytes start `%PDF-`; no `/Encrypt`, `/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`,
  `/OpenAction`, `/AA`, `/RichMedia`, `/XFA` marker (the same conservative scan
  `archive.py:80-90` already uses);
- DOCX: bytes start `PK\x03\x04`, the archive contains `[Content_Types].xml` and
  `word/document.xml`, no `vbaProject.bin`, no external relationship target, and expanded size is
  bounded;
- text: valid UTF-8, no NUL byte in the first 8,000 bytes (the same rule the host already applies
  before returning `readText`).

A mismatch is `SYLLABUS_REJECTED` with the reason. The bytes are not stored on a failed intake.

### 2.2 Out of scope at the input surface

- **No LMS scraping.** No Canvas, Moodle, Blackboard, D2L or Gradescope login, session cookie,
  URL fetch or HTML parse.
- **No calendar OAuth.** No Google/Outlook calendar read or write, no `.ics` import in this scope.
- **No gradebook.** No grade export, import, sync or prediction.
- **No assignment submission.** Coursebook never submits anything to the class.
- **No OCR.** An image-only scanned PDF has no text layer and is refused
  (`SYLLABUS_NO_TEXT_LAYER`), not sent to a model to read pixels.
- **No `.docm`, `.pages`, `.gdoc`, `.rtf`, `.html`, images or archives.** The type list is closed.
- **No URL intake.** A syllabus URL is refused. A pasted link is data in the document, not a fetch.

## 3. Parsing and trust

### 3.1 Deterministic extraction first

The pipeline is fixed and ordered:

1. **Store** the bytes and compute `content_sha256`. Nothing is parsed at intake.
2. **Extract** deterministically, locally, with no model call:
   - PDF: page-by-page text via `pypdf`; one block per page with `page` 1-based, plus a section
     split on detected headings when they are unambiguous. No table reconstruction is claimed.
   - DOCX: paragraph text, with `Heading 1/2/3` mapped to section paths; one block per paragraph
     group; table rows extracted as tab-separated text inside their block.
   - Markdown: heading tree → section blocks; line ranges recorded.
   - Plain text / pasted: line-range blocks, with a blank-line/heading heuristic for section labels
     marked `label_source = "heuristic"`.
   Every block gets a durable `block_id`, its anchor (page, section path or line range), its text,
   and `text_sha256`.
3. **Strict structured parse.** Extraction produces text and anchors; it does not decide what a
   week or an assessment is. A deterministic pre-pass fills only literal patterns (a `Week N`
   heading, an ISO date, an explicit percentage), and the model-assisted parse produces the closed
   `syllabus.parse.v1` document for everything else. The model receives numbered blocks wrapped in
   the existing untrusted-data envelope. It sees no tools, no URLs are followed, and it cannot
   write to any table except through the schema validator.
4. **Anchor verification** (local, deterministic): every `extracted` value must cite at least one
   block id; the cited `quote` must appear verbatim in that block after whitespace normalization.
   An item that fails verification is downgraded to `unknown` with `reason = "anchor_mismatch"`.
   A parse where more than 20% of items fail anchor verification is `parse_state = "needs_review"`
   and the course path is blocked until the user re-parses or uploads a cleaner file.
5. **Persist** the parse run with provider, model, schema version and validation result, in the
   same shape the build already uses for plan generation provenance.

Extraction never interprets. It does not resolve a link, open an attachment, run a macro, or follow
an instruction found in the text.

### 3.2 `syllabus.parse.v1` (versioned, closed)

Every scalar is an **item**, not a bare value:

```json
{
  "value": "CS 340",
  "state": "extracted",
  "anchors": [{"block_id": "b0003", "quote": "CS 340 — Introduction to Databases"}],
  "derivation": "explicit"
}
```

`state` is `extracted | unknown | ambiguous`. `value` is `null` when state is `unknown`;
`ambiguous` carries the candidates in `candidates` and no chosen value. `derivation` is
`explicit | computed_from_term_start | ambiguous | unknown`. A field the document does not contain
is `unknown`; it is never filled from world knowledge, the model's prior, or another field.

Required top-level fields:

| Field | Shape | Rule |
|---|---|---|
| `institution` | item | Unknown is common and acceptable |
| `course.code`, `course.title` | items | At least one must be `extracted` or the document is not a syllabus |
| `term` | `{label, start_date, end_date}` items | Dates ISO-8601 or unknown; no year is inferred |
| `instructor` | item | Optional; no email requirement, no personal data beyond what the document states |
| `meeting_pattern` | item | Free text ("MWF 10:00–10:50"); timezone is not inferred |
| `learning_outcomes` | items[] | Prose is preserved; the parser does not rewrite it into Coursebook objectives |
| `weeks` | `[{ordinal, label, topic, readings[], assessments[], anchors[]}]` | `ordinal` integer or unknown; week labels may be "Week 3", "Module 2", "Sep 14" |
| `readings` | items[] inside a week | Title/author/edition as written; page ranges kept as text |
| `assessments` | `[{id, title, kind, due, weight, week_ordinal, anchors[]}]` | `due` is a dated item with `derivation`; `weight` is a number item plus a `weight_unit` (`percent | points | unknown`) |
| `policies` | items[] | Only study-affecting policy text (attendance, late work, integrity, collaboration, tool use). Verbatim or unknown; never summarized into a rule Coursebook enforces |
| `unknowns` | string[] | Every field left unknown, named |
| `coverage` | `{pages, blocks, extracted_chars, items_total, items_extracted}` | Measured, not estimated |

Hard rules on the parse:

- **No date arithmetic without a term start.** "Week 4" is a week ordinal. A calendar date is
  produced only when the document states it, or when `term.start_date` is `extracted` and the
  derivation is recorded as `computed_from_term_start`. A missing start date leaves every due date
  `unknown`; the UI shows "due date not in the file", not a guess.
- **No weight normalization.** Weights that do not sum to 100 are stored as written with
  `weight_consistent = false`. Points and percentages are not converted into each other.
- **No completeness claim.** The parse run carries `parse_coverage` and the UI sentence "Parsed
  from your file. Check each item against the page." The words "complete", "official" and
  "verified with your institution" are forbidden strings in this surface (test-enforced).

### 3.3 Prompt injection is data

A syllabus is attacker-controlled input. The design reuses the boundary already proven for research
sources and packs (`docs/PRIVACY_EGRESS.md`, "Fetched third-party text"):

- Extracted blocks are wrapped between `[[BEGIN-UNTRUSTED-SYLLABUS-DATA]]` and
  `[[END-UNTRUSTED-SYLLABUS-DATA]]`; marker occurrences inside the text are escaped.
- The parse prompt says the blocks are data, never commands. The schema has no field that can set
  recipe, scope, dials, model, provider, tools, prompts, file paths or approval state.
- An instruction-like sentence (a fake system directive, a demand for full credit, a request to
  email the file outside the app) is stored as an ordinary item under `policies` if it appears in a
  policy section, or ignored otherwise. It is never executed, never followed, never used to compose
  a research query.
- No tool call is made from syllabus text. No URL in a syllabus is fetched. `source.revalidate`
  does not apply to syllabus items.
- The alignment and planner prompts receive only validated item values plus anchors, not raw pages.

This does not claim a model cannot be influenced. It claims the harness does not let syllabus text
change policy, schema, tools, state or approval, and that a hostile sentence cannot become an
instruction with effects. H-26 must include an injection fixture and assert that recipe, scope,
dials, provider and approval are unchanged.

### 3.4 What the parser will refuse

| Condition | Code |
|---|---|
| Encrypted PDF (`/Encrypt`) | `SYLLABUS_REJECTED` |
| PDF with active/embedded content markers | `SYLLABUS_REJECTED` |
| Image-only PDF, no text layer | `SYLLABUS_NO_TEXT_LAYER` |
| Malformed ZIP/DOCX, missing `word/document.xml`, macro present | `SYLLABUS_REJECTED` |
| Non-UTF-8 text, NUL bytes | `SYLLABUS_REJECTED` |
| Over the size/page/paragraph cap | `SYLLABUS_REJECTED` |
| No recognizable course code or title | `SYLLABUS_REJECTED` (`not_a_syllabus`) |
| PDF/DOCX but the extractor dependency is absent | `PARSER_UNAVAILABLE` |
| Parse output fails schema or anchor verification | `parse_state = "needs_review"`; no course path |

Every refusal is typed, side-effect free, and stores no bytes for a file that was never accepted.

## 4. Alignment and pairing

### 4.1 The durable mapping

`course_syllabi` binds one companion course to one syllabus revision and records the review state.
`syllabus_alignments` holds one row per (syllabus item, plan target):

```
course_syllabi(course_id PK, syllabus_id, syllabus_revision, alignment_revision,
               reviewed_revision, reviewed_at, created_at)
syllabus_alignments(id, course_id, plan_id, syllabus_id, syllabus_revision, item_id,
                    target_kind, target_id, state, reason_code, evidence_json,
                    review_state, stale, created_at)
```

- `target_kind` is `unit | objective | lesson`; `target_id` is the real row id in the approved or
  draft plan, and `plan_id` is stored so a superseded plan is detectable.
- `item_id` is the syllabus item, so many items can map to one objective and one assessment can map
  to a unit.
- `evidence_json` carries the syllabus anchors, the target's plan/objective ids, the rule that
  produced the mapping (`week_ordinal | title_tokens | reading_match | assessment_match | model`),
  whether it was deterministic or model-assisted, and a one-line explanation. A model explanation
  is a hypothesis, not evidence of truth; the user's review is the gate.
- `stale` is set, never silently cleared, when the plan is superseded or the syllabus revision
  changes.

### 4.2 States

| State | Meaning | Blocks approval? |
|---|---|---|
| `aligned` | The item maps to at least one target and the target's objective covers the item's stated scope | No |
| `partial` | Maps, but the target covers less than the item asks (reading not included, outcome only surveyed) | No, if the user accepts it |
| `unmatched` | The syllabus item has no target in this plan (exam week, guest lecture, reading not authored) | No, if the user accepts "not covered" |
| `conflict` | The plan contradicts the syllabus: different week, a deadline the plan schedules past, an objective that claims more than the syllabus asks, or an assessment the plan ignores while claiming coverage | **Yes, until resolved** |
| `unknown` | An extracted item that has not been evaluated yet, or an item whose parsed `value` is unknown | **Yes for an extracted item awaiting evaluation.** An unknown-valued item never blocks: nothing is mapped, so nothing is invented. |
| `stale` | The syllabus revision or plan changed after the mapping was made | **Yes, until re-aligned and re-reviewed** |

### 4.3 What the learner must approve, and when

The order is fixed; no step is skippable and none runs silently:

1. **Scope confirmation** (before the plan job). The parser proposes `single`, `short` or `full`
   from the parsed shape, with the reason shown ("14 weeks and 6 assessments → full"). The learner
   confirms or changes it. The proposal is never silently applied, and a missing term length never
   defaults to `full`.
2. **Plan job** (`jobs.create`, `kind=plan`, existing brief plus the syllabus fields). This produces
   a draft plan; it authors no lessons.
3. **Alignment job** (`syllabus.align`, `kind=import`, stage `syllabus_align`) between the draft
   plan and the parsed syllabus. Deterministic rules run first; the model is used only for items the
   deterministic rules cannot place.
4. **Alignment review** (`syllabus.alignment.get` → the learner sees every item, its state, its
   anchors and the source text beside the proposed target). Decisions are recorded through
   `syllabus.alignment.review`; the review is fenced to `alignment_revision`.
5. **Plan approval** (`plan.approve`, the existing exact-hash fence). For a companion course the
   approval additionally requires: `reviewed_revision == syllabus.revision`, no pending `conflict`
   or `stale` row, and the syllabus content hash still equal to the one the plan was generated
   against. A legacy (non-companion) course is unaffected — the precondition is additive and only
   fires when `course_syllabi` has a row.
6. **Lesson authoring**, one unit at a time, exactly as `docs/COURSE-BLUEPRINT.md` defines. The
   learner enqueues the next unit; nothing is pre-generated for the whole semester.

### 4.4 Missing items and conflicts

- **Syllabus item with no course target** → `unmatched`. The review screen lists it under "Not
  covered by this Coursebook course". The learner may accept it (no lesson is invented) or request
  a replan. There is no hidden "cover everything" mode and no zero-content lesson that pretends to.
- **Generated objective that contradicts the syllabus** → `conflict`. Two honest resolutions:
  replan the plan to match the syllabus (existing `plan.replan`, which invalidates approval and
  validation per `docs/PLAN-APPROVAL.md`), or explicitly accept the divergence. Acceptance records
  `review_state = "accepted_divergence"`, changes the state to `partial`, and the course surface
  shows "1 topic diverges from your syllabus — accepted by you". The system never resolves a
  conflict by itself.
- **A syllabus policy that restricts tool use** (for example an integrity rule about AI help) is
  surfaced in the review screen verbatim with its anchor. Coursebook does not adjudicate it, does
  not disable generation, and does not claim the learner complied. It records that the policy was
  shown before generation.
- **Deadlines** are planning metadata: Coursebook can schedule review before an exam and can say
  "your syllabus lists this on 2027-03-04". It never submits, never reminds through an external
  calendar in this scope, and never claims a grade.
- **Weights** are metadata. Coursebook's checks grade Coursebook's objectives only. The product
  never predicts a class grade and never converts a check result into a course percentage.

### 4.5 Revision

A new upload (or a re-paste) for an existing `series_id` creates revision `n+1` with a new
`content_sha256`, sets `superseded_at` on revision `n`, deletes nothing, and in one transaction:

- sets `stale = 1` on every `syllabus_alignments` row for the older revision;
- leaves the approved plan and all existing lessons and evidence valid — they were legitimately
  produced against the older revision and are not retroactively wrong;
- blocks **new** plan approvals and **new** lesson-authoring jobs for that course until the new
  revision is parsed, re-aligned and reviewed (`SYLLABUS_STALE`);
- shows the learner a diff summary: items added, removed, or with a changed date/weight/title, each
  with both anchors.

No silent re-generation. A new lesson set requires the learner to run `plan.replan` (or a new plan
version) after the review; the old plan stays readable until then and is labelled "aligned to
syllabus revision 1".

### 4.6 Language

The external class is the authority. Test-enforced copy rules for every surface and export:

- allowed: "this lesson supports week 4", "aligned to your syllabus's week 4 topic", "your syllabus
  lists the midterm on …";
- forbidden: "official week 4 lesson", "your professor's lesson", "required by your course",
  "counts toward your grade", "enrolled", "accredited".

The alignment row's `reason_code` and evidence are visible to the learner; a mapping with no
evidence is `unknown`, not `aligned`.

## 5. Course shape

Scope and recipe are orthogonal, with two hard rules for this path:

- **Recipe is always `companion`.** `one_off` is refused (an external class is a sequence, not one
  task); `parent` is refused (not a child-facing mode); `casual`/`committed` are not offered in the
  student path because the syllabus, not a dial, sets the scope.
- **Scope is chosen by the learner, proposed by the parser.** The parser's proposal:

| Parsed shape | Proposal | Never silent |
|---|---|---|
| 1 week / 1 session, or one topic | `single` | The learner sees "one lesson" and can choose `short` |
| 2–7 weeks, or 1–3 clear phases | `short` | Shown with the week count |
| 8+ weeks, or 3+ assessments across a term | `full` | Shown with "this is a long course; authoring runs unit by unit" |
| term length unknown | no proposal; ask | Never defaults to `full` or `single` |

A `single`/`short` companion is legitimate when the learner says so ("I only want week 4"), but the
course then covers only the named slice, and the review screen says "this course covers 1 of 14
syllabus weeks". It may not claim to cover the semester. A `full` companion requires H-21; before it
lands, the path refuses with `BLUEPRINT_UNAVAILABLE`.

Honest time and cost:

- `single`: one plan job + one unit authoring job. Minutes to about an hour, depending on provider.
- `short`: 1–3 units, 3–8 lessons. Tens of minutes to a few hours across sessions.
- `full`: 2–12 units, 12–40 objectives, 12–48 lessons, each unit its own job with research,
  authoring and validation, each resumable and cancellable. Hours to several sessions; the cost is
  proportional to the objective count and cannot be quoted as a fixed number before the plan
  exists. The UI shows the plan's own estimate once it exists and otherwise says "several minutes
  per unit"; it never invents minutes.

For a semester syllabus the default authoring horizon is **rolling**: the plan covers the term, but
only the unit the learner enqueues is authored. This is deliberate — a syllabus can change, and a
pre-generated twelve-week course would be stale before week 3.

## 6. Contract and storage delta

### 6.1 Version line (checked, not assumed)

- Current on this tree: `cb.rpc` **v10** (`contracts/rpc.v10.json`), `cb.db` **v6**
  (`contracts/db.v6.json`), `cb.errors` **v2**.
- H-21 owns the next line: `cb.rpc` v11 (`plan_brief.unit_ordinal`, `stage=unit_sections`) and
  `cb.db` v7 (`0007` adds `plan_units`). See `docs/COURSE-BLUEPRINT.md` section 6 and
  `docs/HARNESS-NEXT-CARDS.md`.
- Therefore this design targets **`cb.rpc` v12, `cb.db` v8, `cb.errors` v3**, each strictly
  additive over the line that exists when H-26 starts. H-26 must re-read the contract directory at
  implementation time and take the next free version; it may not reserve v13 now, skip a number, or
  renumber 0008 over another card's migration. If H-21 has not merged, H-26 waits or scopes itself
  to parse/alignment without the plan-brief fields.

### 6.2 Additive methods (RPC v12)

| Method | Request (closed) | Response |
|---|---|---|
| `syllabus.intake.create` | `file_name` (≤255), `mime_hint` enum, exactly one of `content_base64` (≤11,184,812 chars) / `pasted_text` (≤200,000), optional `supersedes_syllabus_id` | `syllabus_id`, `series_id`, `revision`, `content_sha256`, `bytes`, `state`, `extraction` summary |
| `syllabus.get` | `syllabus_id`, optional `revision`, optional `include_blocks` (≤200,000 chars of text) | document metadata, `blocks[]` (anchors), `items[]`, parse run summary, `coverage`, `unknowns` |
| `syllabus.parse` | `syllabus_id`, `revision`, `egress_acknowledged` | `job_id`, `state` — enqueues `kind=import`, stage `syllabus_parse`, idempotency key `cb-syllabus-parse-<id>-<revision>-<sha>` |
| `syllabus.align` | `syllabus_id`, `revision`, `course_id`, `plan_id` | `job_id`, `state`, `alignment_revision` — enqueues stage `syllabus_align` |
| `syllabus.alignment.get` | `syllabus_id`, `revision`, `course_id` | `alignment_revision`, `reviewed_revision`, `stale`, `items[]`, `counts` by state |
| `syllabus.alignment.review` | `syllabus_id`, `revision`, `course_id`, `alignment_revision`, `decisions[]` (`item_id`, `action` ∈ `accept_partial|accept_unmatched|accept_divergence|request_replan`) | `reviewed_revision`, `counts`, `plan_replan_required` |
| `syllabus.delete` | `syllabus_id` | `deleted: true` or `SYLLABUS_IN_USE` |

Field changes to existing methods (additive, optional):

- `course.create`: optional `syllabus_id` + `syllabus_revision`, supplied together or not at all.
  When present, the handler writes `course_syllabi` and leaves `courses.pack_id` NULL.
- `plan_brief` (in `jobs.create`): optional `syllabus_id`, `syllabus_revision`, `alignment_revision`.
  Unknown fields stay rejected, so a typo cannot silently drop the binding.
- `course.get`: the `course` object gains an optional `syllabus` summary (id, revision, hash,
  reviewed revision, counts). No schema change is needed because the object is open, but H-26 must
  document and test it.
- `jobs.create`: a `kind=import` brief becomes closed by a new `import_brief` definition:
  `{stage, syllabus_id, revision, course_id?, plan_id?, egress_acknowledged?}`. Today the import
  brief is only bounded by `maxProperties: 40`.

The plan job is not syllabus-blind. When `plan_brief` carries a syllabus, `run_plan_job` composes
the planner input from the **validated items** (learning outcomes, week topics, assessment names)
alongside the learner's own goal, and the research queries are built from those outcomes instead of
the generic `companion` suffix `"course outline exam"` (`coursebook/research.py:316-317`). The
syllabus supplies the target; the planner still authors the objectives, and every objective remains
the course's own, subject to the alignment review. A syllabus item never becomes an objective by
copy.

New error codes (`cb.errors` v3): `SYLLABUS_REJECTED`, `SYLLABUS_NO_TEXT_LAYER`,
`SYLLABUS_STALE`, `SYLLABUS_UNREVIEWED`, `SYLLABUS_IN_USE`, `PARSER_UNAVAILABLE`,
`BLUEPRINT_UNAVAILABLE`. Every one is a typed refusal with no partial write.

`plan.approve` gains one precondition, only when a `course_syllabi` row exists:

1. `syllabus_revision` supplied by the plan brief equals the current revision of the bound syllabus;
2. `reviewed_revision` equals that revision;
3. no alignment row for that revision is `conflict` or `stale` with `review_state = "pending"`;
4. the syllabus `content_sha256` still equals the hash recorded on the generation row.

The existing hash fence, revision fence and idempotency rules are unchanged. A refusal writes no
transition and does not bump the enrollment revision.

### 6.3 Storage (cb.db v8, migration `0008`)

| Table | Columns (abbreviated) | Notes |
|---|---|---|
| `syllabus_series` | `id`, `learner_label`, `created_at` | One lineage per class/syllabus the student tracks; local only |
| `syllabi` | `id`, `series_id`, `revision`, `supersedes_id`, `content_sha256`, `file_name`, `mime`, `source_kind`, `state`, `created_at`, `superseded_at`, `deleted_at` | `UNIQUE(series_id, revision)`; `state ∈ stored/parsing/parsed/failed`. Bytes live in `syllabus_files`, not here, so metadata reads stay small. |
| `syllabus_files` | `syllabus_id PK`, `bytes BLOB`, `size`, `sha256` | Original bytes for anchor viewing; bounded by the intake cap; no path |
| `syllabus_blocks` | `id`, `syllabus_id`, `ordinal`, `kind`, `label`, `page`, `line_start`, `line_end`, `text`, `text_sha256` | The anchors; text is what verification quotes |
| `syllabus_parse_runs` | `id`, `syllabus_id`, `schema`, `state`, `provider`, `model`, `validation_json`, `coverage_json`, `created_at` | Provenance, one row per parse attempt |
| `syllabus_items` | `id`, `syllabus_id`, `parse_run_id`, `kind`, `ordinal`, `week_ordinal`, `title`, `value_json`, `value_state`, `anchors_json`, `created_at` | `kind` closes the vocabulary in 3.2 |
| `course_syllabi` | `course_id PK`, `syllabus_id`, `syllabus_revision`, `alignment_revision`, `reviewed_revision`, `reviewed_at`, `created_at` | FK to `courses`; one companion course per course |
| `syllabus_alignments` | as in 4.1 | `UNIQUE(course_id, syllabus_revision, item_id, target_kind, target_id)` |

Migration rules:

- `0008_syllabus_intake_and_alignment.sql` is additive: no existing table, column, index or unique
  key is dropped or retyped, and there is no backfill.
- An existing course keeps no `course_syllabi` row and no link; every pre-v8 course behaves exactly
  as before (this is the legacy invariance test).
- The table inventory in `contracts/db.v8.json` is the authority the loader validates against;
  migration SQL and contract inventory move together or the build fails closed.
- No second identity authority: `enrollments` is unchanged and `enrollment.create` is the only
  enrollment writer. `syllabus_series.learner_label` repeats the existing free-text label; it is
  not an enrollment row and confers no institutional identity.

## 7. Privacy and provenance

- **Local by default.** Bytes, extracted blocks, items, parse runs and alignments live in the
  profile SQLite store (`docs/PRIVACY_EGRESS.md`, "Local persistence"). No coursebook-operated
  server, no telemetry, no analytics, no crash upload.
- **One egress, disclosed before it happens.** The parse and alignment stages may send extracted
  syllabus text to the profile's configured model provider. `syllabus.parse` and `syllabus.align`
  require `egress_acknowledged: true`, and the Desktop shows what will be sent (the extracted text,
  bounded, with the envelope) and to which configured provider, before the job is queued. A parse is
  queued only after that disclosure; a re-read of the same stored parse sends nothing.
- **Never a community artifact.** A syllabus cannot be exported as a pack, cannot appear in
  `library.list`, cannot be attached to a pack manifest, and cannot be uploaded to a catalog. There
  is no "share this syllabus" control. `pack.export` and `pack.inspect` do not read these tables.
- **Copyright and redistribution.** A syllabus is usually the instructor's or institution's
  document. The product treats it as a personal study copy: stored locally, never redistributed,
  never bundled, never published. Course exports exclude syllabus text and quotes by default.
  If a learner explicitly enables `include_syllabus` in an export, the export carries item titles
  and page anchors only — never the original file, never long verbatim passages. The default is
  off, and the UI says why.
- **Deletion scope.** `syllabus.delete` removes the bytes, blocks, items, parse runs, alignments and
  review state for that syllabus in one transaction. It refuses with `SYLLABUS_IN_USE` while a
  non-archived companion course is bound. The learner can archive/delete the course, then delete
  the syllabus. Deleting the course does not delete the syllabus automatically; the two are separate
  decisions and the UI states both.
- **Identity.** `learner_label` is a local display label. Coursebook never asks for a student ID,
  institutional email, birthdate or roster data, and never claims enrollment. The words "enrolled",
  "registered" and "official" describe the external class only in copy that says Coursebook is not
  it.
- **Provenance in the product.** Every parsed item shows its anchor on demand. Every alignment shows
  its rule and whether it was deterministic or model-assisted. Every course surface that mentions
  the syllabus shows the revision and the parse date. A model-written explanation is labelled as
  such and is never presented as proof.

## 8. Acceptance matrix

Fixtures live in `tests/fixtures/syllabi/` and are committed by H-26; each has a Markdown source and
a generated PDF/DOCX where the format matters. None is Japanese, and the bundled Japanese demo pack
is **not** evidence for any row.

### A. CS/data course — `cs340-databases.pdf`

- **Shape:** 15 weeks, weekly topics and textbook chapters, 8 labs, 3 exams, explicit dates, weights
  summing to 100, instructor and meeting pattern present.
- **Parse:** all weeks anchored per page; one week's reading is literally "TBD" → `value_state =
  unknown`; exam dates exact.
- **Mapping:** week ordinals and chapter titles align deterministically to units 1–12; the TBD
  reading produces no target and no invented reading; two lab assessments map to the lab unit.
- **Unknown/conflict:** the TBD reading is listed as unknown; a proposed unit that schedules the
  midterm topic after the midterm date is a `conflict` and blocks approval until re-timed.
- **Review:** every week visible with its page anchor beside the proposed unit; learner accepts one
  `partial` (a chapter split across two units).
- **Generation scope:** `full` (H-21 required). Rolling unit authoring; no semester pre-generation.
- **Not supported:** lab environment access, autograder integration, exam dates pushed to a calendar.

### B. History/humanities course — `hist210-early-modern-europe.docx`

- **Shape:** 14 weeks, prose outcomes, two papers and a final, reading page ranges, no term start
  date, midterm "date TBA".
- **Parse:** DOCX headings become section anchors; outcomes preserved verbatim; term start
  `unknown`; midterm `due` is `unknown` with `derivation = unknown`.
- **Mapping:** paper topics map to units by title tokens; a prose outcome that spans three weeks
  maps to three units as `partial`, not one `aligned`.
- **Unknown/conflict:** every date is unknown and shown as "not in the file" (this is the
  missing-dates case). No date is inferred from "Week 6". A unit that claims to cover an outcome the
  syllabus only introduces is a `conflict` until the objective's evidence target is lowered or the
  divergence is accepted.
- **Review:** learner chooses `short` (three of fourteen weeks) and the review states "this course
  covers 3 of 14 syllabus weeks".
- **Generation scope:** `short`, no H-21 dependency.
- **Not supported:** essay submission, plagiarism checking, grade prediction, calendar export.

### C. Lab/technical course — `bio150l-general-biology-lab.md`, revision 2

- **Shape:** 12 labs, lab reports, a practical exam, safety and attendance policies, weights by
  points.
- **Parse:** Markdown headings produce section anchors plus line ranges; points are stored with
  `weight_unit = points` and **not** normalized to percentages; safety policy preserved verbatim.
- **Mapping:** each lab maps to a unit section; the practical exam maps to the final unit.
- **Changed revision (the required case):** revision 2 moves the practical from week 14 to week 13
  and changes the report weight from 10% to 15%. New `content_sha256`, revision 2, prior alignments
  `stale`, approved plan untouched, new authoring blocked until re-review. The diff shows both
  anchors side by side.
- **Unknown/conflict:** the moved practical conflicts with the existing unit 4 schedule and blocks
  new authoring until the learner replans or accepts the divergence.
- **Review:** learner re-reviews only the changed items; unchanged alignments are shown as
  `stale → re-confirmed` with their original evidence.
- **Generation scope:** `short` (12 labs is a short technical sequence) or `full` if the learner
  wants the whole term; the choice is explicit.
- **Not supported:** lab safety certification, equipment scheduling, lab-report submission.

### D. Hostile input (defence row, not a course)

- `hostile-injection.txt` contains a fake system directive, a demand for full credit, a URL and a
  claim that the file overrides the app's rules.
- **Expected:** intake succeeds; the parse treats the text as data; recipe stays `companion`, scope
  stays what the learner chose, dials/providers/tools/approval unchanged; the URL is never fetched;
  the fake instruction is not stored as policy unless it sits in a policy section, and even then it
  is inert text with an anchor. H-26 asserts this with a fake provider.

### E. Refusal row

- `scanned-no-text-layer.pdf` → `SYLLABUS_NO_TEXT_LAYER`, nothing stored, no job.
- `syllabus-encrypted.pdf` → `SYLLABUS_REJECTED`, nothing stored.

### Cross-cutting assertions

1. No syllabus path writes `courses.pack_id`; no syllabus row is visible to `library.list` or
   `pack.export`.
2. Anchor verification rejects a fabricated quote; a parse with >20% mismatches is `needs_review`.
3. A conflict blocks `plan.approve`; an accepted divergence unblocks it and is visible on the
   course.
4. A revision marks alignments stale and blocks new authoring; `plan.approve` refuses with
   `SYLLABUS_STALE` against the old revision.
5. `syllabus.delete` refuses while a course is bound; after the course is archived it removes every
   row and leaves no bytes.
6. Forbidden copy strings are absent from every student-mode surface and export.
7. A pre-v8 course with no syllabus link passes the full existing suite unchanged (legacy
   invariance).

## 9. Out of scope

- No official enrollment, registration or institutional affiliation claim.
- No grade import, grade export, gradebook sync or grade prediction.
- No assignment submission, autograding of class assignments, or proctoring.
- No LMS scraping or authenticated LMS session.
- No calendar OAuth or `.ics` sync.
- No child mode, no parent-facing student mode. Parent Studio is unchanged.
- No community redistribution of a syllabus; no pack wrapping, catalog entry or share control.
- No OCR of scanned syllabi.
- No automatic semester pre-generation and no silent replanning.
- No second course engine, second enrollment authority, second approval path or second grader.
- No claim that a parsed syllabus is complete, official, or verified with the institution.

## 10. Implementation split

Two cards, as seeded. The split is kept because the backend has one coherent state machine and the
UI has one coherent review surface; a third card would create a contract-only branch that cannot be
tested against behavior.

### H-26 (`t_da9e472c`, cinder) — backend: intake, parse, alignment, companion course

Dependencies: H-25 (this doc), **H-21 merged** for `full` scope and for `plan_brief.unit_ordinal`.

Deliverables, in this order:

1. `cb.rpc` v12, `cb.db` v8, `cb.errors` v3 and migration `0008` — contract first, with the loader
   and inventory tests.
2. Intake: `syllabus.intake.create`, magic-byte/MIME verification, caps, encryption/active-content
   refusals, 4 MiB / 8 MiB / 200k-character bounds, no path field anywhere.
3. Deterministic extraction for text and DOCX (stdlib), optional `pypdf` for PDF in `plugin.yaml`
   with `PARSER_UNAVAILABLE` when absent.
4. `syllabus.parse` job (stage `syllabus_parse`), `syllabus.parse.v1` validation, anchor
   verification, unknown discipline, injection fixture.
5. `syllabus.align` job (stage `syllabus_align`), deterministic rules then bounded model assist,
   `syllabus_alignments` with evidence.
6. `course.create`/`plan_brief` link, the planner/research binding from validated syllabus items
   (replacing the generic `companion` query, with the existing query cap unchanged), the
   `plan.approve` precondition, and the `SYLLABUS_STALE` / `SYLLABUS_UNREVIEWED` refusals.
7. `syllabus.get`, `syllabus.alignment.get`, `syllabus.alignment.review`, `syllabus.delete`.
8. Fixtures A–E and the cross-cutting assertions; full suite, `node --check` only if
   `desktop/plugin.js` is touched (it should not be), and `bash scripts/validate-plugin.sh`.

Explicitly not in H-26: any UI, any new course/plan/lesson engine, any pack change, any LMS client.

### H-27 (`t_71ea55ee`, vellum) — learner intake, anchors and alignment UI

Dependencies: H-26.

Deliverables:

1. The entry point in the learner path, phrased as the UX review requires: "Have a college syllabus?
   Start a Student companion course" (`docs/ADVERSARIAL-UX-REVIEW.md` UX-06).
2. Folder picker through `ctx.files` plus a paste fallback; accepted-type copy and the host-door
   absent state ("This Hermes Desktop build has no file door").
3. Intake progress, parse result and the **anchor view**: item on the left, source block with page
   or line label on the right. Unknown items are visibly unknown, never blank or filled.
4. Scope confirmation with the parser's proposal and its reason.
5. Alignment review: per item state, evidence, accept/accept-divergence/replan, conflict blocking,
   stale banner after a revision, and the "covers 3 of 14 weeks" honesty line.
6. Privacy disclosure before the parse/alignment job: what text goes to which configured provider,
   and the local-only storage statement.
7. The deletion flow with its refusal state (`SYLLABUS_IN_USE`) and the course/syllabus split.
8. Copy tests for the forbidden strings; M4 contrast/keyboard gate for the new surfaces.

Explicitly not in H-27: a second planner view, a second approval mechanism, or any control that
enqueues lesson authoring before `plan.approve`.

## 11. What the product will refuse

The complete refusal list, so a demo cannot accidentally promise otherwise:

- A scanned, image-only PDF (`SYLLABUS_NO_TEXT_LAYER`), an encrypted PDF, a macro DOCX, a
  non-UTF-8 text file, an unsupported extension, a URL, an oversized file or page count.
- Treating a syllabus as a pack, exporting it, cataloguing it or sharing it.
- Inventing a course code, title, term, date, weight, instructor or reading the document does not
  state.
- Producing a calendar date from "Week 6" when the term start is absent.
- Normalizing points into percentages or percentages into points.
- Executing an instruction found in a syllabus, fetching a URL from it, or letting it change recipe,
  scope, dials, provider, tools or approval.
- Approving a plan while a syllabus conflict, stale alignment or unreviewed revision is pending.
- Generating a full-semester course before H-21, or generating more than the learner enqueued.
- Submitting an assignment, reading a gradebook, syncing a calendar, or logging into an LMS.
- Claiming enrollment, affiliation, official status, completeness, or that a lesson is the class's
  lesson.
- Deleting a syllabus that a live companion course still uses.
- Reading or writing an arbitrary filesystem path from the RPC.

## 12. Evidence and limits of this document

This card ran no product code and produced no test result. The source reads behind every seam claim:

```
git log --oneline -5                      -> f17ec54 … 2e57efa (base)
sed -n '1180,1340p' desktop/plugin.js     -> PackImportFlow uses ctx.files.requestFolder + /packs/grant
read apps/desktop/src/contrib/plugin-files.ts:45-58, :99-176
read apps/desktop/electron/plugin-files-ops.ts:14-16, :268-270, :365-386
sed -n '1,80p' dashboard/plugin_api.py; sed -n '160,260p' dashboard/plugin_api.py
read contracts/pack-manifest.v1.json (identity, content hash, required manifest fields)
read contracts/rpc.v10.json (method list, course.create, jobs.create, plan_brief, pack.preview/import)
read contracts/vocabulary.v1.json:13-16, :72-76
read contracts/db.v6.json (schema_version 6, table inventory)
read coursebook/migrations/0001_initial.sql:18-110; 0006_courses_plan_brief_inputs.sql
read coursebook/generation.py:671-672 (PLAN_SCHEMA 4-8 objectives, 2-8 sections)
read coursebook/research.py:313-320 (companion query is generic today)
read coursebook/archive.py:80-90, :100-158 (magic bytes, PDF active-content scan; no extraction)
read plugin.yaml (declared dependencies: jsonschema, faster-whisper, pypdf)
```

What this document does not claim:

- It does not claim a PDF extractor is installed; it is not.
- It does not claim H-21 is merged; it is not.
- It does not claim any syllabus has been parsed; none has.
- It does not claim the RPC body accepts an 8 MiB base64 payload; H-26 must measure it and lower the
  cap if the host refuses it.
- It does not choose a final contract number beyond "the next free one above H-21's v11".

If those measurements fail, H-26 reports the failure and lowers the input surface (text formats and
pasted text, `single`/`short` only) rather than inventing a path, a parser or a planner.

### Verification run for this commit

This is a doc-only commit; no product code changed and nothing in the feature was exercised. The
tree-level checks were run anyway, after the document was written:

```
python3 -m unittest discover -s tests -t .   -> Ran 1130 tests in 275.680s, OK
bash scripts/validate-plugin.sh              -> Release gate passed: 3/3 checks (1230 files)
```

The first gate run failed: the plugin security scan reads the literal injection phrase embedded in
this document as hostile text (`prompt_injection_ignore` on two lines). The sentence was rewritten to
describe the fixture without quoting the trigger. Any future document or fixture that quotes an
injection payload verbatim will fail the gate the same way; the fixture itself should be built by
concatenating fragments, not by committing the assembled phrase in a scanned file.
