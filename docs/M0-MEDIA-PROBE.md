# M0 media probe — real host image and speech

> **History record (H-136, 2026-11-07).** The bytes recorded below were probe artifacts in
> `~/.hermes/cache/scratch/`; that directory is pruned and those two files are no longer on this
> machine or in this tree. This document is kept as the record of what the M0 host probe measured.
> The M4 visual/media gate no longer serves these bytes: it serves the committed, labelled fixtures
> in `tests/fixtures/media/` (real 1024×576 PNG and real speech MP3 of the same utterance) whose
> path, sha256 and byte count are recorded in `audit/visual/m4-visual/audit.json` under
> `summary.media_fixtures`. See `tests/fixtures/media/README.md` and
> `docs/M4-VISUAL-MEDIA-AUDIT.md` §Independent illustration review.

Date: 2026-11-06 (MST)
Host profile: `default` (`~/.hermes`)
Host image provider: `image_gen.provider = nous`
Host speech provider: `tts.provider = openai`

The probe called the production `HostMedia` adapter in `coursebook/media.py` with a
`dispatch_tool` shim over the host's own `image_generate` and `text_to_speech` tools. It did not
read a provider key and did not use a test double.

## Image

Prompt: an editorial workshop-bench illustration with a head gasket and a torque wrench, no text.

```
bytes:   1,137,959
mime:    image/png
sha256:  193c10f4b80fd5a70fa2e97b27a48bd07aa77933947e8983df9d87f612f15036
```

Vision inspection: the result is a good atmospheric illustration, but it is **not** a usable
head-gasket procedure authority. It shows one large bore (rather than a multi-cylinder gasket
layout), no block/head relationship, a cluttered surface, and generic wrenches rather than a
torque wrench. This is exactly why the plan requires a deterministic schematic or a sourced
reference for a procedure, and labels AI output as context only.

## Speech

Text: `こんにちは。今日はいい天気ですね。`
Language: `ja-JP`; voice: `default`; beginner, clear and slow guidance.

```
bytes:   50,688
mime:    audio/mpeg
sha256:  9772e2d1c41c33bc3395bc1ddd382e753650db55da98d74764f66853f64f3d9e
```

The bytes are a real MP3 (magic `ff f3`), not a fabricated file. The lesson player uses the same
bytes through `GET /api/plugins/coursebook/media/{artifact_id}` as a data URL; audio never
autoplays.

## What this proves, and what it does not

Proved: the configured host can generate both media modalities; the adapter accepts the returned
URL/path, validates the bytes, and the artifact store accepts the detected MIME types.

Not proved here: a full lesson job on the default gateway. The gateway process predates the
Coursebook plugin install, so its Python half has not loaded the media binding; that is the same
operator-owned gateway restart recorded in `t_6a32ffe9`. The media unit tests exercise the lesson
attachment, cache and fallback paths without a live provider.
