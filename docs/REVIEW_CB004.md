# CB-004 review packet — pack system, safe import/export, demo classrooms

Owner: **Lattice**. Branch `wt/cb-004-lattice`, based on CB-001/CB-018 (`09d6027`).
`cb.pack` stays **v1** (`contracts/pack-manifest.v1.json`); the card was rebased onto **`cb.rpc`
v2** before completion, and every new surface is read from the contracts rather than restated.

## 1. What is in the change

| File | Role | Status |
|---|---|---|
| `coursebook/packs.py` | manifest validation, canonical content hash, teaching minima, content audit, preview, export allowlist/builder, minimum-version gate | extended from the CB-001 seam |
| `coursebook/archive.py` | bounded zip reader, path normalisation, link/bomb/MIME/active-content rejection, staging + atomic adopt, pack library, reconciliation | new |
| `bundled/packs/japanese-affection-context-l0/**` | L0 Japanese demo classroom (manifest, three lessons, source notes, relationship schematic) | new |
| `bundled/packs/parent-measurement-practice/**` | parent pack fixture: learner page, parent guide, separate answer guide | new |
| `bundled/packs/build_demo_packs.py` | reproducible manifest + schematic builder | new |
| `tests/test_packs_{schema,archive,roundtrip,preview,fixtures}.py` | 81 new cases | new |

No dependency was added. The archive reader uses the standard library (`zipfile`, `zlib`,
`struct`, `hashlib`) only, so `plugin.yaml`'s `python_dependencies` is unchanged — no YAML, no
PDF library, no `python-magic`.

## 2. Decisions this package owns

1. **`pack.json` is not listed in `files`.** Listing the manifest would make `content_hash`
   self-referential. `files` lists teaching content; the `manifest` role is reserved and refused
   inside `files`. `content_hash` is SHA-256 over the canonical JSON (sorted keys, tight
   separators, UTF-8) of the manifest without `content_hash`, followed by `path\0sha256\n` for
   each file record in manifest order.
2. **Preview reports four separate trust labels and nothing else.** `cb.rpc` v2 narrowed the
   preview `trust` object to `labels`; reviewer identity stays in the manifest's `trust` block.
   There is no `safe`, `true`, `verified` or popularity badge, and no label implies another.
3. **Export is rebuilt, not copied.** The exported document is assembled field-by-field from
   `export_allowlist()`; identity, licence and trust are set deliberately; private fields do not
   exist in the output to leak. Export performs no PII detection and does not claim to.
4. **Staging transport (open question 3).** A path enters the pack pipeline only through
   `StagingArea.grant_local_file()`, called by a host that actually holds the local file (native
   picker, CLI argument, bundled installer). The wire carries only the minted `staged_id`. A
   `file://` string, a relative path or a symlink is refused even at the grant. No upload route
   was invented.
5. **Pack versions are immutable.** Re-adopting the same `pack_id` + version + hash is a no-op
   (`duplicate: true`); the same identity with different content is refused, and the working
   version is untouched.

## 3. Demo pack hashes

Content hashes as printed by `bundled/packs/build_demo_packs.py` and verified by
`tests/test_packs_fixtures.py`:

| Pack | Version | `content_hash` |
|---|---|---|
| `japanese-affection-context-l0` | 1.0.0 | `sha256:638ce371db6bf2340a7b6a37a75a9762e0e9e6c3f723e55b0a0a5103a8376d7f` |
| `parent-measurement-practice` | 1.0.0 | `sha256:92ee4a79c2ea469c6567ccadbe9fc55290fdd576f28091546372aa87ac36db3d` |

File digests (SHA-256 of the committed bytes):

```
8fb84ad3d7797f6b11febd8510b4e2fb5f17be3ed573fd31dcb8fb9468f1093d  japanese-affection-context-l0/content/relationship-map.png
806201f9ca7bbf11e8921eb2486121926aeb8a8a2574ec2d8d9a336eedb5f1e8  japanese-affection-context-l0/content/section-01-two-ways.md
2098fe3d56cd888489f7682f6c62dbeb6a7e61ea47d071a4f8597824ecc0e7c0  japanese-affection-context-l0/content/section-02-choosing.md
80e26bb5d820603c003295234bdfd8f89dae9a75f273c69d1f9a3666ffdd555b  japanese-affection-context-l0/content/section-03-new-context.md
5090c5b0c58635d3889cb819ff2c984ad6ce5ad8a65ca48142b858fa3d0f048e  japanese-affection-context-l0/content/source-notes.md
eaa7195954e51b19488303ead1020e2fd042bc90426df24f4396e6a675159ea7  japanese-affection-context-l0/pack.json
cfccf28d078790345d6a25293378240d0605bd795e77c66c0ef7df1d2348fd48  parent-measurement-practice/content/answer-guide.md
1031f494d59250136648db00f0977b87e61e13c7e3b9a4d0e7eb51db83cbbc2e  parent-measurement-practice/content/learner-page.md
d07737bef80604105aa8c9949af02cb852de56b197ab532bb6cc48546e9c192e  parent-measurement-practice/content/parent-guide.md
22e65dadcf0a6e686df9e2c0a2bb68910fe8e97b0c289ed9d5e87f08de0036be  parent-measurement-practice/pack.json
```

## 4. Japanese demo pack — content and source notes

**Script policy (L0).** Every Japanese string in learner-facing content is on the same line as
romaji and an English meaning (`tests/test_packs_fixtures.py::test_script_policy_…`). Romaji is
described as a fading scaffold; no romaji-only answer is evidence of reading ability.

**Wording and usage, freshly verified 2026-11-06** (sources linked, not bundled):

| Claim | Source | Support status |
|---|---|---|
| `すきです` is a main A1 expression (Lesson 5) | Japan Foundation, *Marugoto Starter (A1)* contents | `authoritative_documentation` |
| Starter (A1) is written in romaji and kana | Japan Foundation, *How to teach with Marugoto* | `authoritative_documentation` |
| `好き` is a na-adjective; `好きです` is idiomatic for "I love you" | Wiktionary, 好き | `model_assessed` |
| `愛してる` is the continuous form of `愛する` ("to love") | Wiktionary, 愛する | `model_assessed` |
| Confession shape `好きです。付き合ってください。`; `愛してる` real but not to be overused | SNG (Shinjuku Japanese Language Institute) | `model_assessed` (secondary) |
| `です`/`ます` is addressee politeness; uchi/soto frames honorific choice | Wikipedia, *Honorific speech in Japanese* | `model_assessed` |

**No native-speaker review is recorded, and the pack says so.** No audio is bundled, so no
listening evidence and no voice certification are claimed. Culture claims are kept narrow and
attributed; variation is stated, not smoothed away.

**Checks (4 objectives, 4 checks):** discrimination → guided selection → cold recall in a new
context → transfer/explanation. Each rubric has three criteria; all checks are marked
`audit_state: unreviewed`. The reference answers are not present verbatim on a learner page
(enforced mechanically by `packs.audit_bundle` and asserted in the fixtures test).

**Visual:** a deterministic PNG (relationship → register map) with a manifest
`text_equivalent`. It is original geometry, generated by the committed builder, and licensed
`CC0-1.0` in `per_artifact`; no third-party imagery is used.

**Rights:** the pack's own licence is left `unspecified` / `local_only` because the operator has
not chosen a redistribution licence. No source text, exercise, audio or image is bundled.

## 5. Parent pack fixture

`parent-measurement-practice` (recipe `parent`) has three declared roles: `learner_page`,
`parent_guide`, `answer_guide`. The learner page carries two answer lines and no answers; both
reference answers (`150 ml`, `350 ml`) appear only in the answer guide. The parent guide is a
script and an observation checklist, not an answer sheet. Tests assert each of these separations.

## 6. Verification performed

```
python3 -m unittest discover -s tests -t .          → 141 tests OK
bash scripts/validate.sh                            → 141 tests OK; node --check OK;
                                                      hermes plugins validate . (16/16);
                                                      hermes plugins doctor . (1 tool, 3 hooks)
python3 bundled/packs/build_demo_packs.py           → rebuild reproduces both manifests
```

The 141 cases include 81 new pack cases: schema/minima rejections, traversal, absolute paths,
backslashes, control characters, hidden and URL-like names, case-folded collisions, two roots,
symlink/device entries, compression-ratio bomb, oversized file, too-many-files, encrypted entry,
unsupported compression, hash/size mismatch, MIME mismatch, HTML/SVG/script, remote images,
active PDF, NUL-disguised binary, answer-key-on-learner-page, grant refusals, staging residue,
reconcile, preview contract validation, import/export/reimport byte identity, private-data
exclusion, fork attribution, and immutable-version refusal.

## 7. Limits and hand-offs

- **RPC wiring is not in this package.** `pack.preview`/`pack.import`/`pack.export` handlers
  register through `coursebook/api.py` and `__init__.py`, which are Sable's files. This package
  exposes `packs.preview()` (validated against `cb.rpc` v2 `pack.preview`), the export builder,
  `archive.StagingArea`, and `archive.PackLibrary`; the handler bodies are a thin adapter.
- **Course/enrollment creation is the kernel's.** `pack.import` must create a fresh course and
  enrollment through Cinder's tables; `PackLibrary.adopt()` returns the pack-side record
  (`state: installed`, `revision: 0`) that the kernel writes. `pack.export` fetches the exported
  artifact through v2's `artifact.get`; this package writes the archive and reports its hash.
- **Version migration is v1-level:** incompatible upgrades are refused by the minimum-version
  gate; previewable migrations are a later package.
- **Not pushed.** No GitHub push, no publication, no media spend was performed; the licence
  decision for the demo content is left to the operator.
