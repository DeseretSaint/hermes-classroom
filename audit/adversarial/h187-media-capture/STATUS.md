# H-187 media capture — real image artifact for `gen_tech_2` (task `t_b0e4b0e8`)

**Outcome: capture SUCCEEDED.** A real 1024×576 PNG was generated through the product media seam
(`HostMedia` → `coursebook.media.generate_for_lessons` → `artifacts.produce_with_fallback` →
`ArtifactStore`), stored in the profile artifact store, and attached to the served lesson page.
No stock download, no direct provider script, no committed fixture.

## Target

| | |
|---|---|
| Store | `HERMES_HOME=/home/deseretsaint/.hermes/h187-course/home` |
| DB | `…/plugin-data/coursebook/data.db` |
| Course | `crs_53a1191816354c44acec268a03d6dba0` (technical_procedure) |
| Lesson | `gen_tech_2` (state `model_assessed`) |
| Enrollment / objective | `enr_5906d9d5f01a420cba6d2d202db8da53` / `obj_75056df1acb84e4ea637b30421c5cca9` |
| Media role | `illustration` (level **optional**, expected `image/png`, ceiling 8 MiB) |
| Attach block | `blk_aecba1e56d346fc8e07b` (role `example`, "The bench, described"), `media[0]` |
| Prompt | "An editorial illustration of a bicycle wheel clamped upright in a workshop stand, a torque wrench laid beside it on the bench; no text labels, no measurement claims." |

The *required* visual on `gen_tech_1` is role `schematic` and is rendered deterministically from
structured facts — policy forbids a required AI illustration, so that item is not an
`image_generate` target and was not touched here.

## Provider (host-selected, no key read by the plugin)

- Tool: `image_generate` dispatched through the host registry
  (`tools.registry.registry.dispatch`), the same path `PluginContext.dispatch_tool` takes.
- Backend: **managed FAL queue gateway** (`FAL_KEY` unset; Nous subscription gateway reachable).
- Model / endpoint: `fal-ai/flux-2/klein/9b`
- `check_fal_api_key()`: `true`; dispatch duration ~4.7 s.

## Artifact

| Field | Value |
|---|---|
| artifact id | `art_d7dc7afd153d4736abc4d2e0560a8376` |
| kind / mime | `visual` / `image/png` |
| bytes (row = on disk) | **598,928** |
| sha256 (= `content_hash` in the row) | `a206b3493098e7616c77575cc5a4b252ee36da43b58df14d03183fbc91573d6c` |
| magic check | `89 50 4E 47 0D 0A 1A 0A` → PNG signature present |
| sniffed mime | `image/png` (matches declared) |
| dimensions | 1024 × 576, 8-bit RGB, non-interlaced (`file(1)`) |
| store path | `…/plugin-data/coursebook/artifacts/objects/a2/a206b349…d6c` |
| evidence copy | `audit/adversarial/h187-media-capture/a206b349…d6c.png` (byte-identical, hash re-checked) |
| provenance | `generator=host.image_generate`, `role=illustration`, `lesson_state=model_assessed`, `independent=false`, honesty label "Illustration — generated for context only…" |

## Served page reference

`lesson.page` (cb.rpc) returns `ok:true`, document state `complete`. The block
`blk_aecba1e56d346fc8e07b` (`media[0]`) now carries:

```json
{"kind": "visual", "role": "illustration",
 "artifact_id": "art_d7dc7afd153d4736abc4d2e0560a8376",
 "purpose": "See the bench layout before starting",
 "text_equivalent": "A workshop bench: the bicycle wheel is clamped upright in the stand and the torque wrench lies beside it.",
 "label": "Illustration — generated for context only. It is not a measurement, procedure, technical reference, or safety authority.",
 "degraded": false, "reason": null}
```

`media.preview_artifact(art_d7dc7afd…)` (the host route the Desktop renderer uses) returns
`ok:true`, `mime:image/png`, 598,928 bytes, `lesson_state:model_assessed`, `independent:false`,
and a `data:image/png;base64,…` URL. So the served page's reference is renderable, not just a row id.

Note: the page's block-level media child does not carry a `mime` field — that is the existing
`_media_child` projection shape; the MIME is re-derived by the preview route from the bytes.
Attachment was identified from the block's media `artifact_id` (not from `artifacts[]` membership,
which is course-scoped).

## Verification (independent process)

`verify_capture.py` re-reads the DB read-only, the file, the served page and the preview route in a
fresh process; `verification.json` records 12/12 checks passing: size row==disk, hash row==disk,
PNG magic, sniffed PNG, path inside the profile artifact store, lesson media has the artifact id and
`degraded:false`, served block references it, block not degraded, preview route serves PNG, evidence
copy matches.

## Honest caveats

- **Concurrent writer on the shared store.** The prepared home is shared with other in-flight work:
  a sibling capture wrote the language narration artifact `art_5d6c2b68…` (`host.text_to_speech`,
  `gen_lang_1`, job `h187-tts-capture`) at `2026-11-08T21:13:53Z`, before this run finished. The DB
  therefore no longer matches the parent's pinned `703980dc…`; the count went 1 → 2 with my row as
  the second. That is not a defect in this capture — my read-back is of the live row — but the
  pinned hash from the parent handoff is stale for that reason, not because of a wrong artifact.
- Lesson state is `model_assessed`, so the artifact's provenance records `independent:false` and the
  page's "treat this page as a proposal" warning still applies. The bytes are real; their
  instructional authority is not claimed.
- Nothing was published, tagged, merged, or restarted. Evidence lives only on `wt/t_b0e4b0e8`.

## Reproduce

```
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_b0e4b0e8
HERMES_HOME=/home/deseretsaint/.hermes/h187-course/home \
  python3 audit/adversarial/h187-media-capture/capture_image_artifact.py \
  --evidence-dir audit/adversarial/h187-media-capture
HERMES_HOME=/home/deseretsaint/.hermes/h187-course/home \
  python3 audit/adversarial/h187-media-capture/verify_capture.py
```

A second run reuses the cached artifact by spec/source hash (`reused:1`) rather than paying the
provider again.
