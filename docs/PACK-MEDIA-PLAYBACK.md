# Pack-bundled media playback — frozen decision for 0.1.x

| | |
|---|---|
| Card | `H-73` / `t_cbb2e1c5` ("pack-bundled narration has no playback route") |
| Branch | `wt/h73-pack-media` |
| Base | `1c81ff3` (`master`, post-H-72: 1,648-test suite) |
| Author | Atlas (architecture) |
| Source finding | `t_fa50edb2` (Lattice, H-72) — the bundled Japanese L0 narration clip survives export/reimport but nothing can play it |
| Status | **Frozen.** No implementation is authorized by this document; §12 names the cards that are. |
| Contract delta | **`cb.pack` v2** (new file, one optional top-level `media[]`). No `cb.rpc` version, no `cb.db` migration. |
| Host-seam delta | `GET /media/{artifact_id}` gains two additive response keys (`license_id`, `attribution`). |

This is a decision card. It writes no product code, changes no contract JSON, adds no migration, and
spends no provider money. `PREBUILD_SPEC.md` §2 requires a coherent working vertical slice rather
than a wide set of partially wired controls; this document applies that rule to a file the shipped
pack already carries.

Every statement below about current behaviour was read out of the named file at `1c81ff3`, and the
existing roundtrip suite was run in that tree (`python3 -m unittest tests.test_packs_roundtrip` → 10
tests, OK) to confirm the asset-level claims. Nothing was imported against a live database in this
card — see §14 for what that leaves unproven.

---

## 1. Decision

**Option (a): authoring-time materialization, linked by a frozen `cb.pack` v2 `media[]` projection.**

A pack that wants its bundled bytes to be *played* declares, in its manifest, which section file each
`narration`/`visual` file belongs to and what one line of text the learner sees beside it. Import
turns that declaration into the durable rows the lesson surface already renders: one `artifacts` row
(hash-addressed, provenance-bearing) and one `lesson_segments` row of kind `media`, placed inside the
section's teaching block sequence. `lesson.page` needs no new field, because it already returns media
segments and media children.

A pack that declares nothing (every v1 pack, including the bundled Japanese pack as shipped today)
behaves exactly as it does now: the file is validated, hashed, licensed, exportable — and never
appears on a learner page. That stays honest because the learner page cannot name audio it has no
row for.

| Question the card asked | Answer |
|---|---|
| Where does the file → section link live? | A new top-level `media[]` array in `cb.pack` v2, not section front matter and not the section manifest entry |
| Is the link key `section_id` or the section path? | `section_path` — the exact string `_write_lesson_page` already resolves |
| Does this need a new artifact table (`lesson_artifacts`)? | No. The existing `artifacts` table plus `lesson_segments(kind='media', artifact_id)` already carry it |
| Does this need a `cb.db` migration? | No |
| Does this need a `cb.rpc` version? | No |
| Does the learner page gain an evidence class, listening check or score? | No, and §10 makes that a prohibition, not a promise |

---

## 2. What is true at `1c81ff3` (measured, not assumed)

### 2.1 The asset and what already carries it

`bundled/packs/japanese-affection-context-l0/content/narration-polite-confession.mp3` is 22,272 bytes,
`audio/mpeg`, sha256 `dea7f196…`, with a Japanese + romaji + English `text_equivalent` and an
Apache-2.0 per-artifact licence record (`pack.json:35-44`, `pack.json:87-98`). `cb.pack` v1 accepts
`role: narration` with `audio/mpeg` (`pack-manifest.v1.json:182-205`), and the union of import-time
audits already enforces what an asset must carry: a media file needs a text equivalent
(`packs.py:420`) and a per-artifact licence record (`packs.py:422`).

The existing test `test_imported_japanese_pack_exposes_the_narration_audio_and_its_text_equivalent`
(`tests/test_packs_roundtrip.py:143-170`) asserts the manifest-level facts — role, MIME, bytes, hash,
text equivalent. It asserts nothing about a lesson page, because at this commit there is nothing on a
lesson page to assert.

### 2.2 Import materializes section text only

`pack_flow._write_lesson_page` (`pack_flow.py:470-515`) creates one `lesson_runs` row, writes each
declared section file as `lesson_segments(kind='teaching')` cut at the `cb.rpc` segment cap, then
writes each check as `lesson_segments(kind='check_prompt')`. There is no branch for any other
`files[]` role. `validate_and_audit` (`pack_flow.py:372-403`) reads only section files and check
stimuli. Consequently, at `1c81ff3`, an imported pack produces **zero** `artifacts` rows and **zero**
`kind='media'` segments.

### 2.3 The media seam that already exists around it

Everything needed to *render* pack-authored bytes is already shipped and already load-bearing:

| Piece | Where | What it gives us |
|---|---|---|
| `artifacts` table | `migrations/0001_initial.sql:186-198` | content-addressed (`UNIQUE (content_hash, kind)`), `kind`/`mime`/`bytes`/`path`/`provenance_json` |
| Artifact store | `artifacts.py:466-597` | stage → fsync → atomic adopt, then metadata in the caller's transaction; reuse on `(content_hash, kind)` |
| Adoption precedent | `pack_flow.py:931-991` (`_adopt_artifact`) | records an artifact row for bytes that already exist, reusing the row and bumping `ref_count` |
| `lesson_segments` | `migrations/0002_…sql:21-31` | `kind IN (… 'media' …)`, nullable `artifact_id` |
| Segment → document | `lesson_document.py:849-946` | a `media` segment becomes a media child of the preceding block, typed from the artifact row |
| Media route | `media.py:613-664`, `dashboard/plugin_api.py:227-234` | bounded data URL, size and sha256 re-verified on every serve, label and text equivalent from provenance |
| Player | `desktop/plugin.js:8208-8280` | `<audio controls preload="metadata">`, never autoplay; caption, label, provenance line, "Text equivalent" disclosure |
| Byte policy | `artifacts.py:62-82, 186-230` | magic-byte MIME sniffing, render-safe allowlist, narration label "the transcript is the authoritative text; this is not pronunciation assessment" |

The gap is therefore not a renderer gap. It is exactly one thing: **no row**. Import never creates
the artifact, so `lesson.page` has no media segment to project and the renderer has nothing to ask the
route for. The visual file in the same pack (`content/relationship-map.png`) is in the same position.

### 2.4 Three constraints that any implementation must survive

These are the places where the obvious implementation breaks, and they are why this card is a
decision rather than a ticket.

1. **`lesson.page` lists artifacts by course** (`domain.py:2543-2545`:
   `SELECT * FROM artifacts WHERE course_id = ?`). `artifacts` is unique on
   `(content_hash, kind)`, not per course, and `_adopt_artifact` reuses a row across courses. Two
   courses importing the same pack would therefore have the second course's media segment point at an
   artifact whose `course_id` belongs to the first. The map passed to `document_from_segments` misses
   it, the media child degrades to a text block (`lesson_document.py:921-934`: unknown artifact ⇒
   prose, never a guessed kind), and the page silently loses the player. Import must not be built on
   top of that query; the read must also resolve the artifact ids the run's own media segments
   reference. No wire change: the response already carries `artifact_id` on every segment.
2. **A media child has hard display caps.** `purpose` is ≤ 200 characters and `text_equivalent` is
   ≤ 1200 (`lesson_document.py:89-91`, re-checked at `:1126-1166`; identical caps in
   `contracts/rpc.v14.json:6302-6312`). `document_from_segments` fills *both* from the segment's
   `text` (`lesson_document.py:935-942`). A media segment whose text is a full pack transcript would
   make `_finish` raise (`lesson_document.py:721-723`), and `lesson.page` calls
   `document_from_segments` outside its `try` (`domain.py:2589-2598`), so the whole page would fail.
   The import therefore writes a **short caption** into the segment text and keeps the full text
   equivalent in the artifact provenance, where the media route already serves it uncapped.
3. **The page budget counts teaching segments and checks, not media.** `segments.audit_objective_texts`
   (`segments.py:217-247`) computes `teaching_segments + checks` against the 500-segment
   `lesson.page` cap. Each linked media file adds one segment. A section already at the budget would
   push its media past `LIMIT 500` (`domain.py:2537`) and the tail — possibly the audio — would
   silently vanish. The audit must add linked media to `needed`, and the per-section media count must
   be bounded by the block's eight-child cap (`lesson_document.py:83`).

---

## 3. The options

### 3.1 (a) Authoring-time materialization — **chosen**

Import reads a manifest-level link, copies each linked file into the artifact store (content-addressed,
hash-verified, no provider call), records `provenance_json` with the pack identity, file path, file
hash, licence and attribution, and writes one `lesson_segments(kind='media', artifact_id, text=caption)`
row inside that section's block sequence.

- **What it costs**: one new frozen contract file (`pack-manifest.v2.json`), a version-dispatching
  pack validator and exporter, ~5 new refusal rules, the import branch in `_write_lesson_page`, the
  `lesson.page` read fix (§2.4.1), two additive keys on the media route, one rights/attribution line
  in the Desktop media frame, and one regeneration of the bundled pack. No migration.
- **What it buys**: the provenance story is the same one generated media already uses — one artifact,
  one hash, one label, one text equivalent — and the bytes are re-hashed by the route before every
  serve. Export symmetry is unchanged because the link travels *inside* the manifest the library
  already stores verbatim.
- **Disk cost**: one extra copy of each linked file in the artifact store, bounded by
  `cb.pack.max_expanded_bytes` (128 MiB); identical bytes across imports reuse one object.

### 3.2 (b) Read-time projection only — rejected

"Keep import as it is and let `lesson.page` project pack files by matching section path/order" cannot
be built as described, for three measured reasons:

1. **The projection requires an artifact row to type media.** `document_from_segments` only mints a
   media child when it can resolve `artifact_id` to a row and derive `kind` from it
   (`lesson_document.py:914-934`); with no row and no trusted MIME it deliberately degrades to a
   prose block. Removing that rule means guessing a media kind for an unknown child, which is the
   exact invariant the comment at `:921-923` exists to protect.
2. **There is still no byte route.** `preview_artifact` (`media.py:613-664`) serves only `artifacts`
   rows, by id, with a sha256 re-check. Projecting pack files without an artifact would need either a
   second binary route into the pack library (a new host seam with its own auth, size and hash story)
   or a data URL inside `lesson.page` (a wire-shape change larger than the contract delta chosen
   here, and a lesson response that can become megabytes — the reason `MAX_PREVIEW_BYTES` exists).
3. **Read-time coupling to a mutable library.** `pack.delete` freezes the pack row and keeps
   evidence; a page that resolves media at read time out of the library would have to re-implement
   the hash re-check and would change behaviour when the library record moves. Durable rows are why
   `lesson.page` is a pure read of the database today.

It is not cheaper. It is the same UI work plus a new byte path, minus the provenance and hash
guarantees.

### 3.3 (c) Decline for 0.1.x — viable fallback, not chosen

Declare pack-bundled audio stored evidence only, never playable, and put that sentence in
`cb.pack`'s description, `docs/PACK-AUTHORING.md` and the pack inspector. Cost: zero. H-72's honest
demo cut stands unchanged.

The reason not to take it: the product already ships the artifact store, the media segments, the
bounded preview route and the labelled player for *generated* media. The marginal cost of making the
same machinery read pack bytes is one contract version and one import branch, and declining means
every future pack carries permanently dead weight — a defect the ship review will keep re-finding.
If the v2 work cannot land before release freeze, (c) is the correct fallback and nothing in this
document forbids it; it is a sequencing choice, not an architecture one.

### 3.4 Variants that were considered and rejected

| Variant | Why not |
|---|---|
| Filename convention (`section-02-choosing.narration.mp3`) | No contract change, but the link becomes implicit naming magic: a typo silently unlinks, and an author cannot tell from the schema that the name carries meaning. |
| Section front matter (`<!-- cb:media … -->` in the section Markdown) | The section file is learner-facing prose; a machine directive in it needs a new strip rule in front of the teaching text, and a strip bug prints raw HTML comments to a learner. It also bypasses the manifest allowlist, which is where every other authoring claim is validated. |
| Objective-level implicit binding (the only narration belongs to the objective) | False for a pack with several sections and several media files, and the Japanese pack's clip models one line in one of four objectives. |
| A new `lesson_artifacts` table | A migration plus a second content-addressed store for no gain: `artifacts` + `lesson_segments.artifact_id` already model exactly this, and the preview route already resolves by artifact id. |
| Runtime TTS of the pack's transcript at import | Pays a provider, invents bytes the pack did not license, and produces a rendering whose provenance is *not* the pack author's. The pack ships real audio; play it or do not. |

---

## 4. Contract delta — `cb.pack` v2 (frozen by this document)

`cb.pack` v1 sets `additionalProperties: false` at the root (`pack-manifest.v1.json:22`) and pins
`contract_version: {"const": 1}` (`:39`), and `contracts.py:30-38` maps one contract id to one file.
An additive field therefore cannot be smuggled into v1: it needs a new frozen document, exactly as
`cb.rpc` has v1…v14. This section is that delta.

**New file `contracts/pack-manifest.v2.json`.** Everything in v1 is carried unchanged except:

```json
"contract_version": { "const": 2 },
"media": {
  "type": "array",
  "maxItems": 2000,
  "description": "Pack-authored media that the lesson page may play. A file not named here is stored
                  evidence only: it is validated, licensed and exportable, and no learner page may
                  reference it. Each entry links one declared narration/visual file to the section
                  file it belongs to and gives the one-line text equivalent shown beside it.",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["path", "section_path", "caption"],
    "properties": {
      "path":         { "type": "string", "minLength": 1, "maxLength": 500 },
      "section_path": { "type": "string", "minLength": 1, "maxLength": 500 },
      "caption":      { "type": "string", "minLength": 1, "maxLength": 200 }
    }
  }
}
```

Rules that travel with the field (enforced at validation, not prose):

| # | Rule | Failure mode |
|---|---|---|
| M1 | `media[].path` must name an entry in `files[]` | `PACK_REJECTED`, dangling media link |
| M2 | that entry's `role` must be `narration` or `visual`, and its MIME must match the role (`audio/mpeg|wav|ogg` / `image/png|jpeg|webp`) | refused; a PDF or a text file cannot be a media link |
| M3 | `media[].section_path` must equal `objectives[].sections[].path` for at least one objective | refused; a link that no page can ever resolve is a defect, not a no-op |
| M4 | no duplicate `(path, section_path)` pair; one file may link to several sections, and one section may link several files | refused |
| M5 | `caption` is 1–200 characters (the `lesson_document_media.purpose` cap) | refused |
| M6 | at most 8 linked files per section path (the block's media cap) | refused |
| M7 | a `contract_version: 1` document may not carry `media` (schema-enforced), and a v2 document must still satisfy every v1 minima rule | refused |

Additive consequences that must be implemented with the contract, not after it:

- `coursebook/contracts.py`: `cb.pack` becomes the one contract with a version map
  (`{1: pack-manifest.v1.json, 2: pack-manifest.v2.json}`); `CONTRACT_FILES["cb.pack"]` names v2 as
  current; the v1 file stays on disk, immutable, and loadable by explicit version.
- `coursebook/packs.py:276-294` (`load_manifest`) and `:122-131` (`validate_manifest`) dispatch on the
  document's `contract_version` before validating. `contract_version` is peeked, type-checked as an
  integer and bounded to the known set before any schema is chosen.
- `coursebook/packs.py:649-737` (`build_export`) already copies fields from `export_allowlist()`
  (the current contract's properties), so a **v1** manifest would be re-exported as
  `contract_version: 1` and then fail validation against a v2 `const`. Export must validate and build
  against the version the manifest declares, so "a re-export of unchanged bytes keeps the same
  content hash" survives (`docs/PACK-AUTHORING.md:90-92`). This is the single most likely place for
  the delta to break an existing test.
- `minimum_coursebook_version`: a v2 pack must declare the first plugin version that ships v2. An
  older build then refuses the pack at schema validation instead of silently ignoring `media[]` —
  and that is why §13 is an ordering constraint, not advice.

`docs/CONTRACTS.md` gains a `cb.pack` v2 row in its inventory and version table. `cb.pack` v1 is not
edited, and no v1 bytes, hash or roundtrip result change.

---

## 5. Database delta — none

`cb.db` stays at **v9**. The rows this needs already exist and are already written by other paths:

| Need | Existing carrier |
|---|---|
| bytes + hash + MIME + size | `artifacts` (`migrations/0001_initial.sql:186-198`) |
| provenance, label, text equivalent, licence, attribution | `artifacts.provenance_json` (free-form JSON, read by `media.preview_artifact`) |
| page placement | `lesson_segments(kind='media', artifact_id, text)` (`migrations/0002_…sql:21-31`) |
| per-course reach | `artifacts.course_id`, plus the read fix in §2.4.1 |

No column is added or retyped. A future field that provenance JSON cannot hold (for example a
per-artifact rights expiry) would need a migration; nothing in this decision does.

---

## 6. Wire delta — none, and two changes that are not wire changes

`cb.rpc` stays at **v14**. `lesson.page` already returns `segments[]` including
`kind: "media"` with `artifact_id` (`contracts/rpc.v14.json:2016-2081`) and a `document` whose
`blocks[].media[]` carries `kind`, `role`, `artifact_id`, `purpose`, `text_equivalent`, `label`,
`degraded`, `reason` (`:6263-6338`). Nothing a client reads changes shape.

Two server-side changes are required and neither moves the wire:

1. `domain.lesson_page` must resolve the artifacts its own `media` segments reference, not only the
   course's 200 most recent rows (§2.4.1). The response is identical in shape; the media child stops
   degrading to text when a row is reused across courses.
2. `lesson_document.document_from_segments` currently builds a media child with `role=None` and
   `label=None` (`:935-942`). For a pack child that is acceptable — the route supplies the honesty
   label — but the import must ensure `purpose`/`text_equivalent` carry the caption, not a transcript
   (§2.4.2). If the implementer instead wants the label baked into the document, that *would* be a
   `cb.rpc` amendment, and it is not taken here: `docs/CONTRACTS.md:1242` already froze the rule that
   "a media child keeps only the authored purpose, text equivalent and label; provenance stays on
   `artifact.get`".

---

## 7. Host-seam delta — media route, additive

`media.preview_artifact` (`media.py:613-664`) is a host route, not an RPC method
(`docs/VISUAL_MEDIA_PLAN.md:306-314`). It already returns `label`, `text_equivalent`, `permission`
and `source_ids` from provenance. It gains exactly two keys, both additive, so an older Desktop
ignores them:

```json
{ "license_id": "Apache-2.0",
  "attribution": "Synthetic speech generated locally with Kokoro-82M …" }
```

`null` when the artifact has no recorded licence. No route is added for pack files; no path crosses
the wire; the existing size cap (`MAX_PREVIEW_BYTES`), MIME allowlist and sha256 re-check are
unchanged.

---

## 8. Import behaviour (what the implementation card must build)

### 8.1 Order of operations

1. **Validate** (before the first DB write, like the segment-cap refusal at `segments.py:217-247`):
   schema, minima, M1–M7, and the page-budget check extended with the objective's linked media count.
2. **Adopt linked bytes into the artifact store** — outside the DB transaction, per the rule at
   `pack_flow.py:601` ("filesystem first, never inside a transaction"). `ArtifactStore.stage` +
   `adopt`; a failure aborts the import with nothing written, and `ArtifactStore.reconcile`
   (`artifacts.py:646`) removes adopted-but-unrecorded objects if the import later rolls back.
3. **Inside the existing import transaction** (`pack_flow.py:604-714`): record the artifact row via
   `ArtifactStore.record` (reusing an existing `(content_hash, kind)` row and bumping `ref_count`),
   then write the media segment.

### 8.2 Placement rule

For each objective, for each declared section in `objectives[].sections[]` order: write the section's
teaching pieces, then that section's linked media segments, in `media[]` order. The objective's
`check_prompt` segments are written last, as today. The document projector then attaches each media
child to the block immediately preceding it (`lesson_document.py:943-946`), which is that section's
last teaching block. Deterministic, no new placement vocabulary, and no view claims anything: the
child keeps its authored purpose, text equivalent and label.

### 8.3 Provenance record (the honesty spine)

```json
{
  "generator": "coursebook.pack_import",
  "model": null,
  "prompt_hash": null,
  "source_ids": [],
  "notes": "pack-authored media played from pack content; no provider call",
  "label": "Narration — the pack author's transcript is the authoritative text; this is not pronunciation assessment.",
  "text_equivalent": "<the file's files[].text_equivalent, verbatim>",
  "license_id": "Apache-2.0",
  "attribution": "<the matching license.per_artifact[].attribution, verbatim>",
  "pack_id": "japanese-affection-context-l0",
  "pack_version": "1.0.0",
  "pack_content_hash": "sha256:447aace8…",
  "pack_file": "content/narration-polite-confession.mp3",
  "pack_file_sha256": "sha256:dea7f196…"
}
```

Visual links use `artifacts.ILLUSTRATION_LABEL` verbatim: a pack-supplied image has no
`sourced_technical` source mapping and no structured facts, so it is context, never procedure,
measurement or safety authority (`artifacts.py:37-40`). If a future pack needs a schematic or a
sourced reference, that is a second decision with its own fields; it is not smuggled in here.

### 8.4 Refusals (all before any write, all `PACK_REJECTED`)

| Condition | Message shape |
|---|---|
| M1–M6 above | names the offending `media[]` index and the reason |
| linked media exceeds the objective's page budget | names the section, the teaching/check/media counts and the 500-segment cap |
| linked file fails magic-byte sniffing (`artifacts.sniff_mime`) | names the file and the detected type |
| linked file's bytes differ from the manifest hash | existing hash verification already refuses the whole pack |

A v1 pack with narration reaches none of these: it has no `media[]`, so import is byte-for-byte the
current behaviour.

---

## 9. Learner-facing copy

The rule the card set is the rule the surface obeys: **a learner page never claims audio it cannot
play, and the text equivalent is always present.**

| Situation | What the learner sees |
|---|---|
| Linked narration, route healthy | `<audio controls preload="metadata">` (no autoplay); caption = the pack's caption; label = the narration honesty label; provenance line `audio/mpeg · 22,272 bytes · <attribution> · <licence id>`; a "Text equivalent" disclosure carrying the full `files[].text_equivalent` |
| Linked visual, route healthy | `<img>` with the caption as `alt`; Illustration label; same provenance and disclosure |
| Route refuses or the file is missing | the caption and the disclosure remain, plus "This narration could not be played here; the text equivalent remains." Never a silent gap, never a disabled control that implies audio was expected |
| v1 pack (no `media[]`) | nothing. No player, no "listen", no mention. The lesson text is the pack's section Markdown, unchanged |
| Import preview / pack inspector, v1 pack with media files | one neutral line: "This pack bundles narration and visual files. This build stores them with the course but does not play them; each lesson uses its text equivalent." |
| Import preview, v2 pack with links | "This lesson plays N bundled media item(s). Each carries its text equivalent, licence and attribution." |

Prohibited copy, now and after implementation: "listen and repeat" on a pack asset that is not
linked; "pronunciation", "native speaker", "accent", "correct" attached to a synthetic clip;
"downloaded", "streamed" or any word implying an upload. The bundled clip is synthetic speech and
its own text equivalent says so.

---

## 10. What this decision does not authorize

- No listening check, no dictation check, no audio answer, no pronunciation score, and no new
  evidence class. `docs/ASSESSMENT-BREADTH.md` §1 keeps recorded performance out of 0.1.x; a played
  narration is material, not evidence, and opening a page records nothing (`lesson.page` is a read).
- No learner recordings in packs, no audio upload path, no retention of learner audio.
- No provider call at import and no TTS synthesis of pack transcripts.
- No autoplay, no waveform analysis, no duration-derived claim about what the audio "proves".
- No change to grading, attempts, revisions or mastery semantics.

---

## 11. Test plan the implementation cards must satisfy

Contract and import:
1. `pack-manifest.v2.json` validates the worked example in §15; v1 documents still validate against
   the v1 file unchanged (pinned by sha256 of the frozen v1 file).
2. A v1 pack exports to a v1 manifest with the **same** `content_hash` after v2 becomes current.
3. M1–M6 each refuse at `pack.preview` and at `pack.import` with no pack, course, objective, run,
   segment or artifact row left behind.
4. A v2 pack import creates exactly one artifact row and one `kind='media'` segment per link, at the
   right ordinal, with the caption as `text` and the licence/attribution/pack hash in provenance.
5. Two courses importing the same pack both render the player (the cross-course reuse case in
   §2.4.1) — this test fails on the naive `WHERE course_id = ?` read.
6. A media segment whose caption is 201 characters is refused (the 200-cap failure in §2.4.2).
7. A section at the page budget with one linked file is refused (the segment-budget failure in
   §2.4.3).
8. Import of the unchanged v1 Japanese pack produces no artifact and no media segment (the honest
   status quo is a pinned behaviour, not an accident).

Surface:
9. `lesson.page` for a v2 import returns a media child with `kind: "audio"`, the caption, and an
   `artifact_id` the media route resolves; the route returns `license_id` and `attribution`.
10. The Desktop frame shows label, provenance line and text equivalent, never autoplays, and falls
    back to the caption when the route refuses — extending the existing M4 C-05/C-07/C-13/C-15
    checks with a pack-imported fixture.
11. `bash scripts/validate-plugin.sh` stays green, and no existing contract, hash or evidence test
    changes.

---

## 12. Implementation cards this decision implies

In dependency order; none of them is this card, and none may be opened against a mutated §4.

| # | Title | Owns |
|---|---|---|
| H-74 | `Freeze cb.pack v2 — media[] link, version dispatch and export version carry` — contract file, `contracts.py` map, `packs.load_manifest`/`validate_manifest`/`build_export`, `docs/CONTRACTS.md` row, v1-immutability and re-export-hash tests (plan 1–3) | contract + pack service |
| H-75 | `Materialize linked pack media at import — artifact row, media segment, provenance, pre-write refusals` — `pack_flow._write_lesson_page`, adoption ordering, M1–M6, page-budget extension, provenance record, tests 4 and 6–8 | pack import path |
| H-76 | `Resolve lesson media by referenced artifact id, not by course` — `domain.lesson_page` artifact map, cross-course reuse test 5, no wire change | kernel read path |
| H-77 | `Serve pack media rights — licence/attribution on the media route and in the media frame` — `media.preview_artifact` two keys, `MediaFrame` rights disclosure, M4 pack fixture, tests 9–10 | host route + Desktop |
| H-78 | `Re-issue the bundled Japanese L0 pack at cb.pack v2 with its narration linked` — `build_demo_packs.py`, `pack.json`, `content_hash`, roundtrip + fixture tests, after §13's ordering constraint is met | pack content |
| H-79 | `Document pack media playback for authors` — `docs/PACK-AUTHORING.md` §"media you can play", `docs/ARCHITECTURE.md` media seam paragraph, pack inspector copy from §9 | docs |

H-72's demo script is not reopened by any of these. If the recorded demo is ever re-shot with audio,
that is a separate decision with its own evidence.

---

## 13. Ordering constraint (the one that can break the ship)

A build that only understands `cb.pack` v1 **rejects** a v2 pack at schema validation. Therefore:

> The bundled Japanese pack must not be re-issued at v2 until the plugin version that ships
> H-74…H-77 is the version the demo and the release carry, and `minimum_coursebook_version` in the
> pack names that version.

Shipping the pack first would make the bundled demo pack unimportable on the release build — a worse
defect than an unplayed file. Until the ordering is satisfied, the pack stays v1 and the lesson page
stays silent about audio, which is exactly H-72's honest position.

---

## 14. Honest limits of this document

- **No runtime probe.** This card ran the existing roundtrip suite (10 tests, OK at `1c81ff3`) and
  read the named files; it did not import a pack into a live profile, did not call the media route,
  and did not render a Desktop frame. The §2 claims are code-path claims, and the implementation
  cards own the behavioural proof.
- **No contract file was written.** §4 is frozen prose; H-74 turns it into JSON, and the exact
  `x-contract-version`, description text and property order are H-74's to write within this delta.
- **No estimate of effort, cost or duration.** The cost is stated as the artifacts it consumes
  (one contract file, one import branch, one read fix, two route keys, one frame line, one pack
  regeneration, eleven tests), not as hours.
- **Deferred, not decided**: a `section_id`-scoped link (needed only if one section path must play
  differently in two objectives); `sourced_technical` pack visuals; a second placement
  (`with_check`); per-artifact rights expiry. None blocks the seam chosen here.
- **Not applied**: the worked example in §15 is not in any pack. `bundled/…/pack.json` is untouched
  at `1c81ff3`.

---

## 15. Appendix — the worked example, written but not applied

The Japanese pack, were it re-issued at v2 (H-78), would carry exactly this addition and nothing
else:

```json
"media": [
  {
    "path": "content/narration-polite-confession.mp3",
    "section_path": "content/section-02-choosing.md",
    "caption": "好きです。付き合ってください。 (suki desu. tsukiatte kudasai.) — \"I like you. Please go out with me.\""
  }
]
```

It passes M1 (declared file, role `narration`), M2 (`audio/mpeg`), M3 (`section-02-choosing.md` is
objective 2's declared section), M4–M6 (one pair, 95-character caption, one file on one section).
Importing it would add one artifact row and one media segment to objective 2's page, and the lesson
would play the clip the pack already ships, labelled and licensed, with its text equivalent one
disclosure away.

The visual (`content/relationship-map.png`) stays unlinked in this example: linking it is a separate
one-line entry and a separate authoring decision about whether that schematic belongs on the page.
