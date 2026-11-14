# H-187 TTS capture — real narration audio for `gen_lang_1`

Task: `t_ce380228` (Generate real TTS audio artifact for language lesson).
Branch: `wt/t_ce380228`, base `127cce1`. **Not pushed, not merged, gateway not restarted.**

## Result

**Capture succeeded.** A real MP3 was produced by the product media path, stored in the
prepared store, and the served `lesson.page` for the language lesson references it.

| fact | value |
|---|---|
| course / lesson | `crs_c330330a969646cfb0735f9f3644c107` / `gen_lang_1` (locale `ja`, L0, state `model_assessed`) |
| artifact id | `art_adf2e015a0694641a409bb54e9a6a746` |
| stored path | `~/.hermes/h187-course/home/plugin-data/coursebook/artifacts/objects/20/208bb60d…48d3c` |
| size | **41,088 bytes** |
| sha256 | **`208bb60d6b56b0e734550e849755a3ec6d86d4a726b6293d399989b240648d3c`** |
| declared / sniffed mime | `audio/mpeg` / `audio/mpeg` |
| first bytes | `ff f3 c4 c4 00 5a 8c 39 b8 01 5a c0 00 3b 56 0e` (MPEG frame sync, no ID3 tag) |
| ffprobe | `mp3`, `audio`, 24,000 Hz, mono, 2.568 s, 128 kbps |
| review copy | `artifact/gen_lang_1-narration.mp3` — byte-identical copy, same sha256 |
| transcript spoken | `こんにちは` (language `ja-JP`, voice `default`) |
| lesson state on the artifact's provenance | `model_assessed`, `independent: false` |

`file artifact/gen_lang_1-narration.mp3` → `MPEG ADTS, layer III, v2, 128 kbps, 24 kHz, Monaural`.

## The path that produced it (product path, not a provider script)

```
host ctx.dispatch_tool("text_to_speech", …)          <- HostCtx.dispatch_tool = tools.registry.dispatch
  coursebook.media.bind_host_seam(ctx)               <- the same binding register(ctx) calls
    HostCtx → HostMedia.speech                       <- builds {text, output_path, instructions}, no provider key
      coursebook.media.generate_for_lessons(...)     <- production caller
        artifacts.produce_with_fallback → ArtifactStore (sniff, cap, content-address, DB row)
```

The dispatch entry is the host's own `text_to_speech` (`tools/tts_tool.py`, toolset `tts`), and the
provider resolved by the host was **`openai` through the Nous Tool Gateway**
(`https://openai-audio-gateway.nousresearch.com/v1`, managed mode). Recorded envelope from
`dispatch_calls[0]` in `capture_result.json`: `success: true`, `provider: "openai"`.
No Coursebook code read a provider key or called a vendor endpoint; no bytes were read from a
fixture.

`lesson_ids=["gen_lang_1"]` only — the technical course was not touched by this run.

## Served page

`served_lesson_page.json` is the full `lesson.page` result. The target block
`blk_280128ee1e4e4ded9d13` (`practice`, "Say it back") now carries:

```json
{"kind": "audio", "role": "narration",
 "artifact_id": "art_adf2e015a0694641a409bb54e9a6a746", "degraded": false, "reason": null}
```

and `page.artifacts[]` lists `{kind: audio, mime: audio/mpeg, bytes: 41088, content_hash:
sha256:208bb60d…}`. Page-level provenance still says `model assessed, not independently
validated: treat this page as a proposal.` — the artifact's own provenance carries the same
`lesson_state: model_assessed`, `independent: false`; the bytes are not evidence of lesson quality.

## Honest failure record (attempt 1)

Before the store home had a host `tts` selection, the tool fell back to its built-in default
provider and failed. Verbatim stdout is in `attempt_1_edge_unavailable.json`:

- provider attempted: **edge** (`edge_tts`), no endpoint of ours — the library's Microsoft endpoint
- error: `TTS chunk 1 failed (edge): TTS generation failed (edge): No audio was received. Please verify that your parameters are correct.`
- learner surface: media item `degraded: true`, `reason: "media generation failed (MediaGenerationError); delivered as text"`,
  `text_equivalent` retained, `artifact_id` absent, `artifacts` rows **0**. No player, no fake bytes.

That attempt also exposed a harness bug: calling `api.dispatch` without importing
`coursebook.domain` answers `NOT_IMPLEMENTED` for `lesson.page`. The real plugin entry imports
`hooks`, which imports `domain`; the harness now imports `coursebook.domain` explicitly.

## Environment completion (declared)

The prepared home `/home/deseretsaint/.hermes/h187-course/home` shipped with `plugin-data/` only —
no `config.yaml` — so the host tool had no `tts` selection. I added a five-line `config.yaml` that
mirrors the operator's real host config (`profiles/sable/config.yaml`):

```yaml
tts:
  provider: openai
  use_gateway: true
```

Nothing else was changed in the home. The managed-gateway bearer came from the root profile's
portal identity (the profile-then-root auth fallback); no secret is copied into the store home or
recorded here.

## Shared-store note

The prepared store is shared with the sibling image task (`t_b0e4b0e8`, same profile). The
`artifacts` table now also holds `art_d7dc7afd…` (598,928-byte `image/png`, course
`crs_53a119…`, written at the same minute). **That row is not this capture**; this card's evidence
is `art_adf2e015…` only. `verification.json` therefore reports `artifact_row_count: 2`.

## Reproduce

```bash
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_ce380228
HERMES_HOME=/home/deseretsaint/.hermes/h187-course/home \
  python3 audit/adversarial/h187-tts/capture_tts.py      # capture (spends one provider call)
HERMES_HOME=/home/deseretsaint/.hermes/h187-course/home \
  python3 audit/adversarial/h187-tts/verify_artifact.py  # re-read, no provider call
```

`capture_result.json` and `verification.json` are the machine-readable records; `manifest.json`
pins every evidence file's sha256.
