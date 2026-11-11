# Adversarial backend review — course portability, import usability, install provisioning

Scope: everything outside the Desktop UI, reviewed against `origin/master` `adca16a6` with the
CP-015g changes in this branch. Reviewer stance: assume the pack is hostile, the author's database
is not the importer's, and a green unit test is not a product claim. Every finding below names a
file, a test, or a measured command.

**Verdict: PASS WITH NAMED OPEN RISKS.** Four product-blocking defects are fixed and proven; four
residual risks are recorded, two with cards, two accepted with a stated rationale. Nothing here
claims live model quality or a live Desktop drive.

## 1. Defects found and fixed

| # | Defect (measured before the fix) | Fix | Proof |
|---|---|---|---|
| D1 | `pack.import` wrote a `check_prompt` segment and no `checks` row. Bundled Japanese pack imported with `select count(*) from checks` → **0**; `check.open` had nothing to open, so no attempt, transition or evidence was reachable on any imported course. | `pack_flow._write_lesson_page` projects each manifest check through `check_spec_from_pack_check` (the existing deterministic audit) and inserts a real `checks` row. An item failing its own audit imports ungraded. | `tests/test_pack_import_usability.py` (3): import → 4 checks for 4 objectives, `attempt.submit` → `verdict=pass`, `evidence_class=cold`, 1 transition + evidence; parent pack → 0 checks. |
| D2 | A Game course could not round-trip at all: `cb.pack` had no presentation data, `pack_flow` inserted courses with `presentation_mode` NULL (Textbook), and GM tables were forbidden to any pack read, so the approved world and its plates were dropped. | `cb.pack` v3 `presentation` block; authored export emits `world/` plates + kit identity; import restores `presentation_mode`, `course_worlds` at `approved`, `world_assets` re-keyed to new objective ids; `world.kit_hash_for` shared between generation and import. | `tests/test_pack_presentation_roundtrip.py` (8): export carries hero/cover/2 section plates with per-artifact licences; import reads back `presentation_mode=game`, approved world, plates hash-identical, section keys equal to the imported objectives. |
| D3 | Authored `course.export` shipped text only: a section's generated illustration/narration bytes were never in the archive. | `build_pack` reads `gen_lessons.media_json`, writes `media/<NN>-<role>-<hash>.ext`, links it through the frozen v2 `media[]`, adds a text equivalent + per-artifact licence; a missing artifact blocks the export (`media_artifact_missing`). | `MediaPackRoundTripTest`: export manifest has one `media[]` link with a declared `visual` file; import writes one `media` segment whose artifact resolves to real bytes. |
| D4 | No install-time verification that the package a user receives is complete: bundled skills, declared tools/hooks, contract set, dependencies, bundled starter packs, database schema. | `install_check.inspect_provisioning()` + `--provisioning` CLI, exit 1 on any error. | `tests/test_install_provisioning.py` (5) and `python3 -m coursebook.install_check --source . --provisioning` → exit 0 with `SKILLS_OK`, `TOOLS_OK`, `CONTRACTS_OK`, `DEPS_OK`, `BUNDLED_PACKS_OK`. |

## 2. Attack surface reviewed, with the rule that stops it

- **Pack carries gameplay or history.** v3 `presentation` is art only. `GM_ART_TABLES`
  (`course_worlds`, `world_assets`) may be read by the pack seam; `GM_NEVER_EXPORTED_TABLES`
  (homework, engagement, tutor) may not, and `test_gm_contract.py` asserts both halves, including
  that a v3 pack cannot name `attempts`, `evidence`, `verdict` or `score` (the schema has no such
  field and `additionalProperties: false` refuses them).
- **Contradictory mode.** A `recipe: parent` pack declaring `presentation.mode: game` is refused —
  a parent-led plan is not a player course. (`_presentation_problems`, tested.)
- **Smuggling through the brief.** `presentation.world.brief` is a closed 12-field object with
  `additionalProperties: false`; `{"attempts": [...]}` is a schema refusal, not ignored data.
  (Tested.)
- **Oversized wire value.** `style_id` is bounded to the 80 characters `cb.rpc` accepts; without
  that, an import would store a value that makes every subsequent `world.read` an
  `INTERNAL_ERROR`. (Tested.)
- **Partial world claiming approval.** Import refuses a world block whose brief names section
  plates that the pack does not carry, instead of inserting `state='approved'` over an incomplete
  kit. (`_restore_world` completeness rule.)
- **Unverifiable hashes.** Every plate's `sha256` must equal the declared file's, every
  `style_hash`/`prompt_hash` must be a `sha256:` digest, and the imported `kit_hash` is re-derived
  from the importing database's own rows rather than copied.
- **Path traversal / zip bomb / MIME spoof.** Unchanged and still enforced by
  `coursebook/archive.py` (normalized unique relative paths, compression-ratio ceiling, magic-byte
  MIME check, active-content refusal); the new `world/` and `media/` paths go through the same
  extractor and the same `ArtifactStore.stage` validation.
- **Answer leak into a new surface.** `_answer_key_problems` scans learner-facing text, including
  the new media files' text equivalents; the export still refuses an archive whose learner page
  prints the reference answer.
- **Import idempotency / rollback.** World artifacts are adopted filesystem-first and registered in
  `_discard_adopted_objects`; a refusal after adoption removes the new objects, as media already
  did. A replayed `idempotency_key` returns the stored result and adopts nothing.

## 3. Residual risks (open, named)

- **R1 — P1 — a fine-tuned pack-backed course re-exports stale bytes.** `pack.export` rebuilds from
  the installed pack, not from the course's edited lesson revisions. Import → fine-tune →
  re-export therefore ships the pre-edit lesson while the course on screen shows the edit. Card:
  `[CP-015g residual] Fine-tuned pack-backed course re-exports stale pack bytes`.
  Not fixed here because the honest fix is a policy decision (allow `course.export` for a
  pack-backed course with revisions, or refuse `pack.export` once a revision exists); silently
  choosing one would change the export contract.
- **R2 — P2 — the reviewed content hash does not cover world plates.** `course.export.read`
  returns a course-text digest; re-approving art between the read and the write does not change it.
  The archive's own `content_hash` covers every plate byte and is recomputed from disk on write, and
  the adopt transaction re-asks the text gate, so no unreviewed *text* ships. Accepted: plates
  state no teaching fact and carry no evidence. Card filed for the contract-level fix.
- **R3 — P2 — `prompt_hash` on an imported plate is a claim, not a proof.** Import recomputes
  `kit_hash` over the declared `prompt_hash` values, so a hostile pack can be internally consistent
  without proving what prompt produced the art. Accepted: plates are art-only, never evidence, and
  the imported world is marked `approved` only because the pack's author approved it — the same
  trust level as any pack content. `trust.labels` still carries no `human_review_recorded`.
- **R4 — P2 — no in-app fresh-user inventory.** `t_244d7ad2` (no Coursebook row in
  Capabilities → Plugins on fresh userdata) is a Desktop loader defect outside this lane. The
  backend and package are complete; the row is a UI discovery bug that Opus/Atlas own. Commented,
  not duplicated.
- **Not claimed:** no live provider generation was run in this pass, and no Desktop window drove
  these commits. The in-plugin one-course acceptance (`t_ad25d623`) is still the gate that converts
  "backend wired" into "product demonstrated".

## 4. Commands this review was measured with

```
python3 -m unittest tests.test_pack_import_usability          # 3 tests, OK
python3 -m unittest tests.test_pack_presentation_roundtrip    # 8 tests, OK
python3 -m unittest tests.test_gm_contract                    # 26 tests, OK
python3 -m unittest tests.test_install_provisioning tests.test_install_check  # 19 tests, OK
python3 -m coursebook.install_check --source . --provisioning # exit 0
python3 -m unittest discover -s tests -t .                    # full-suite result recorded in docs/RELEASE-EVIDENCE.md
```
