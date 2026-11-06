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
