# Pack authoring notes: identity, bounds and rights

**Owner:** Lattice (pack subsystem). **Applies to:** `cb.pack` v1 (`contracts/pack-manifest.v1.json`)
and the import/export code in `coursebook/packs.py`, `coursebook/segments.py`,
`coursebook/pack_flow.py`. **Last verified against:** `cb.rpc` v7 and `cb.pack` v1.

A pack is declarative data: JSON, Markdown/plain text, JSON documents and bounded media. It carries
no executable code, no tool calls, no provider settings, no credentials, no local paths, no
transcripts and no learning history. The manifest is allowlist-first, so an unknown field is
rejected rather than stored.

## 1. One lesson section is bounded at 4,000,000 characters

A pack's lesson sections are the files named by `objectives[].sections[].path`. When Coursebook
imports a pack, each section file becomes the teaching text of one lesson page. A lesson page is
shaped by `cb.rpc` `lesson.page`:

| Contract fact | Value | Source |
|---|---|---|
| maximum characters in one `segments[].text` | 8,000 | `contracts/rpc.v7.json`, `$defs.methods.properties.lesson.page.response.properties.segments.items.properties.text.maxLength` |
| maximum segments returned by one `lesson.page` | 500 | same object, `segments.maxItems` |

The authoring bound is their product: **500 × 8,000 = 4,000,000 characters per lesson section**.
A section above that number needs more teaching segments than one page can return, so its tail can
never render.

This is **derived from the contract at read time**, not a second constant. The single derivation is
`coursebook.segments.lesson_section_char_bound()`, which multiplies
`segments.lesson_page_caps()`. No module stores `4000000` as a limit; if the contract caps change,
the bound follows them and the tests fail if they drift.

What the bound is **not**:

* It is not `cb.pack`'s `max_single_file_bytes: 33554432` (32 MiB). That is a
  decompression/security bound on one declared file, not a readability promise. It is unchanged.
* It is not a schema field. `cb.pack` v1 gains no new key; the manifest contract's description
  carries this note and the code enforces nothing at manifest-validation time.
* It is not a guarantee that a section at exactly 4,000,000 characters will import. One lesson page
  also carries the objective's check prompts (one segment each), so the practical ceiling for a
  section in an objective that has a check is lower. Import's own pre-write refusal
  (`coursebook.segments.audit_objective_texts`, D1 at `e3d6770`) is the authority. The bound here is
  the absolute ceiling for a section taken alone.

## 2. What the author sees

The bound is surfaced as a **warning**, never as a refusal, because the import path owns refusal:

* `coursebook.packs.authoring_warnings(manifest, files)` returns one message per over-bound section,
  naming the file (its exact manifest path), its measured length in characters, the bound, and the
  contract facts it came from.
* `coursebook.packs.audit_warnings(directory)` does the same from an unpacked pack directory. It sits
  beside `audit_bundle`, which returns hard problems, and it never rejects.
* `coursebook.pack_flow.validate_and_audit` — reached by `pack.preview` and `pack.import` — emits
  each message as a Python `coursebook.packs.PackAuthoringWarning` (a `UserWarning`) before the
  import refusal runs.
* The export path emits the same warning: `coursebook.packs.build_export` (used by `pack.export`
  and `build_conversion`) and the authored `parent.export` write path.

Warning text example:

```
section file 'content/chapter-1.md' measures 4,000,001 characters, above the 4,000,000-character
authoring bound for one lesson section (cb.rpc lesson.page returns at most 500 segments of 8,000
characters, so a section of 4,000,000 characters is the most one page can carry); the page budget
also carries the objective's check prompts, so import may refuse a slightly shorter section. Import
will refuse this pack before writing anything. Split the section into smaller files.
```

`pack.preview`, `pack.import`, `pack.export` and `parent.export` payloads are frozen `cb.rpc` v7
shapes, so the warning adds **no wire field**. It is emitted through the host's warning channel; an
authoring tool that wants the list calls `packs.authoring_warnings` or `packs.audit_warnings`
directly. Nothing about this warning is a trust or safety badge.

## 3. Import behaviour at and over the bound

* At or below the bound: the section is accepted for authoring; import cuts it at semantic
  boundaries into pieces of at most 8,000 characters and stores them in reading order.
* One character over the bound: authoring warns with the file and measured length; `pack.preview`
  and `pack.import` refuse with `PACK_REJECTED` **before the first database write**, naming the file,
  its length and the caps. No pack, course, objective, lesson run or segment row is left behind.
* Mixed packs: one over-bound section is enough to refuse the objective it belongs to; other
  objectives do not rescue it, because the refusal is evaluated per objective before any write.

The boundary is pinned by `tests/test_pack_authoring_bound.py` (4,000,000 accepted with no warning;
4,000,001 warned at authoring, warned through preview, and refused at import) and
`tests/test_segment_cap.py` (the splitter and the pre-write refusal).

## 4. Identity, rights and trust (unchanged by this note)

* Pack identity is `pack_id` + immutable semantic `pack_version` + `content_hash`; enrollment
  identity is never part of a pack. A re-export of unchanged bytes keeps the same content hash.
* Export is rebuilt field by field from `packs.export_allowlist()`; no stored manifest, transcript,
  attempt, notebook entry, provider setting, path or reflection can ride along.
* Every media file needs a per-artifact licence record and a text equivalent. A pack's `license`
  and `attribution` describe the rights the author actually holds; a pack with
  `redistribution: unset` must not be redistributed.
* Trust labels are four separate dimensions (`integrity_verified`, `automated_checks_passed`,
  `human_review_recorded`, `model_assessed_support`). None of them, and no hash, means the content
  is safe or true.

## 5. An authored course packages itself (`course.export`, cb.rpc v13)

Before v13 the only authored export was Parent Studio's `parent.export`, and `pack.export` refused
any course with no `pack_id` (`course_not_pack_backed`). A course a learner created from a goal —
the main product path — could therefore not be packaged at all. v13 adds two commands and no
storage:

| Command | What it does |
|---|---|
| `course.export.read` | The review: `ready` / `blocked_reason` / `blocked_message` / `problems[]`, the exact file list with role, name, size and sha256, the course-text `content_hash`, the licence, the rights statement, the no-upload statement, the plan identity and the validated/total page counts. |
| `course.export` | The write: `enrollment_id` + `expected_content_hash` (the hash the review read returned) + an `idempotency_key`. Writes one archive, records one `export` artifact, and returns the file list and `pack` identity. |

**The gate, in order.** (1) The course must not be pack-backed — an imported course is refused with
`course_pack_backed` and keeps using `pack.export`, whose allowlist is not weakened. (2) The current
plan must be `approved` (`plan_not_approved`). (3) **Every** lesson section must carry a generated
page whose `gen_lessons.state` is `validated` (`lessons_not_validated`, one `problems[]` line per
page: "section 2 (…) is needs_review, not validated"). (4) If the course has an active
`final_approvals` row, its `content_hash` must still match (`changes_need_review`).

Final approval is **not** required: the approved plan plus validated pages is the approval authority
for a learner-authored course. A stored final approval is still honoured as a hash fence, so a
course a parent signed off cannot change and then ship under that signature.

**Two hash fences.** The reviewed hash is echoed back by the caller; a mismatch is
`DELETE_SCOPE_STALE` and no byte is written. The write then re-reads the course inside its adopt
transaction and refuses with `changes_need_review` if the text moved while the archive was built.

**What is in the archive.** A fresh `cb.pack` v3 document, built by
`parent_authoring.build_pack` from the validated page rows: `parent-guide/NN-*.md`,
`lessons/NN-*.md` and `answer-guide/NN-*.md` for every objective, the plan's objectives and
evidence criteria, and each check's stimulus, rubric and reference answer. The learner page text is
in the archive as Markdown; the learner surface offers no PDF handout (that stays
`parent.export`). Identity is `authored-<course-id>`, version `1.0.0`, licence
`all-rights-reserved` with `redistribution: local_only`. The response says what the file is: a local
copy for reuse, not a publication, and nothing was uploaded.

**Round-trip.** The archive is an ordinary pack: `pack.preview` → `pack.import` cuts a new course
from it, and that course is then pack-backed (`pack.export`, never `course.export`).
`tests/test_course_export.py` proves the loop end to end, including that imports still pass the
answer-key audit and the teaching minima.

**One content rule the round-trip enforces.** `packs._answer_key_problems` refuses an archive whose
learner-facing page prints a check's reference answer verbatim. A multiple-choice lesson that prints
the correct option in its own page therefore exports but does *not* import; the page has to ask for
the answer rather than show it. That rule is older than this command and is not relaxed here — the
test fixture uses a short-answer prompt for exactly this reason.

## 6. A pack carries its presentation and its visuals (`cb.pack` v3, CP-015g)

A course is more than its Markdown. Two things a learner sees were previously lost on the way out
of Coursebook, so an imported course did not match the course the author made:

1. **The section's own generated media.** `course.export` shipped `parent-guide/`, `lessons/` and
   `answer-guide/` text and nothing else, even when a section had a generated illustration or a
   narration clip. The bytes existed in the artifact store and the lesson page played them; the
   archive did not contain them.
2. **A Game course's mode and world.** `pack.import` inserted the new course with no
   `presentation_mode`, so a Game course re-imported as Textbook, and there was no mechanism to
   carry the approved world kit at all.

v3 fixes both without a second store and without weakening the evidence rules:

* A section's generated `visual`/`narration` artifacts are written as
  `media/<NN>-<role>-<hash>.ext` with a text equivalent and a per-artifact licence, and linked
  through the frozen v2 `media[]` array. Import adopts those bytes as artifacts and writes the same
  media segment into the lesson page it already builds. A media item whose artifact row disappears
  blocks the export (`media_artifact_missing`) rather than silently shipping a text-only lesson.
* The approved world kit is written under `world/` as declared `visual` files, and the
  `presentation` block records the mode, the grammar, the selected style, the style hash, the kit
  hash, the typed brief and one entry per plate with its objective ordinal. Import restores
  `courses.presentation_mode`, inserts the `course_worlds` row at `approved`, and rebuilds
  `world_assets` against the new objective ids; the stored `kit_hash` is re-derived from those rows
  (`coursebook.world.kit_hash_for`), not copied as an unverifiable string.
* `mode: game` with no approved world is legal and honest: the course imports as Game and its world
  is simply not approved, which the product already names as a gate. Textbook courses export
  `presentation: {mode: "textbook"}` and no plates.

**What is still not in a pack.** Gameplay and history: no XP, engagement event, attempt, evidence,
homework task or tutor turn is representable, and the GM contract test asserts that the seam reads
only the two art tables. A course's approved lesson text remains the export gate; the presentation
block is not a second approval surface (see the residual note in
`docs/ADVERSARIAL-BACKEND-REVIEW.md` R3).

**Proof.** `tests/test_pack_presentation_roundtrip.py` drives a real Game course through
`course.export` → `pack.preview` → `pack.import` and reads the world back through `world.read`
(approved, four plates, re-keyed section plates, byte-identical images), then does the same for a
section media artifact; `tests/test_pack_import_usability.py` proves an imported course's check is
now a real gradable row (import used to leave `checks` empty, so no attempt was possible).

