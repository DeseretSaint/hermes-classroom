# REVIEW H-72 — the demo's 73–82 s narration shot

Task: `t_fa50edb2`, branch `wt/h72-demo-narration`, base `972b96d`.
Date: 2026-11-07. Author: Lattice. Reviewer of record: still Sentinel / DeseretSaint at the gate; nothing here
certifies the pack as safe, true or native-speaker reviewed.

## What path was taken

**A for the asset, and the script narrowed where A cannot reach.** One real Japanese narration clip is now
bundled in `bundled/packs/japanese-affection-context-l0`, synthesized locally with **zero provider spend**
(no API call, no key, no network TTS). The demo row is nevertheless **not** returned to "spoken": packing a
file is not the same as a surface that plays it (see §5), so `docs/DEMO.md` now scripts the still-and-text
shot the build can actually produce.

No path C was needed. Provider TTS was never called.

## 1. The asset

| field | value |
| --- | --- |
| path in pack | `content/narration-polite-confession.mp3` |
| role / MIME | `narration` / `audio/mpeg` (both already in `contracts/pack-manifest.v1.json`; no contract change) |
| bytes | 22,272 |
| sha256 | `sha256:dea7f196f147958a536b41c6ee8f2ff51558f56a74e7f4e8ab86f580db971349` |
| container | MPEG-2 Layer III, 24 kHz mono, 64 kbps CBR, 116 frames, header-parsed 2.784 s (ffprobe: 2.700 s) |
| spoken line | 好きです。付き合ってください。 (suki desu. tsukiatte kudasai.) — "I like you. Please go out with me." |
| loudness (ffmpeg volumedetect) | mean −24.6 dB, max −8.6 dB — speech, not silence and not a placeholder |
| pack `content_hash` after rebuild | `sha256:447aace8ee718f73834af324192e3395ada63da81f7625e613af7e0e66983856` (was `sha256:638ce371…6d7f`) |

The line is the pack's own polite first-confession example (section 1, check `chk-discrimination-1` line B).
It is a model of a taught line, not an answer key: no check's reference answer is spoken.

## 2. Exact tool, voice, licence and commands

Engine: **Kokoro-82M** (`hexgrad/Kokoro-82M`, revision `f3ff3571791e39611d31c381e3a41a3af07b4987`),
model weights **Apache-2.0** per the model card (`cardData.license: apache-2.0`), used through the
`kokoro` Python package (Apache-2.0). Japanese G2P via `misaki`/`pyopenjtalk` + UniDic. Nothing is
redistributed from the training data; the clip is model output.

Voice: **`jf_alpha`**, speed 0.9. It is a synthetic voice embedding shipped with the Apache-2.0 model.
**No human speaker was recorded, and no native speaker reviewed the pronunciation.** The pack says exactly
that in `content_notes`, `safety_notes`, the contributors list (`narrator`) and the per-artifact attribution.

Environment (scratch venv, nothing installed system-wide):

```
uv venv --python 3.12 venv            # CPython 3.12.16
uv pip install --python venv/bin/python "kokoro>=0.9.4" soundfile "misaki[ja]"
venv/bin/python -m unidic download    # UniDic 3.1.0+2021-08-31
```

Resolved versions: `kokoro 0.9.4`, `misaki 0.9.4`, `torch 2.15.0` (CPU), `pyopenjtalk 0.4.1`,
`fugashi 1.5.2`, `unidic 1.1.0` (dictionary 3.1.0+2021-08-31), `numpy 2.5.4`, `soundfile 0.14.0`.

Synthesis and encode:

```python
from kokoro import KPipeline
pipeline = KPipeline(lang_code="j")
for gs, ps, audio in pipeline("好きです。付き合ってください。", voice="jf_alpha", speed=0.9):
    ...  # concatenate, write 24 kHz PCM WAV with soundfile
```

```
lame --quiet -b 64 --cbr -m m --resample 24000 polite.wav narration-polite-confession.mp3
```

`lame --version` → `LAME 64bits version 4.0`; `ffmpeg -version` → `n9.0.2` (used only to measure
duration and loudness, not to create the file).

### Rejected first attempt — piper

`uv pip install piper-tts` succeeded (`piper-tts 1.8.0`), but the piper voice repository has **one**
Japanese voice, `ja_JP-hi_fi_captain-medium`, and its `MODEL_CARD` records the training set
`hi-fi-captain` under **CC BY-NC-SA 4.0**
(`https://huggingface.co/rhasspy/piper-voices/raw/main/ja/ja_JP/hi_fi_captain/medium/MODEL_CARD`).
Non-commercial + share-alike is not a permissive model for a bundled demo fixture, so piper was not used.
Recorded here because the card names piper first; the licence, not the engine, is why it was dropped.

## 3. What changed in the pack (built, never hand-edited)

`bundled/packs/build_demo_packs.py` now reads the committed MP3, hashes the real bytes, and emits the
manifest entry; `pack.json` and `content_hash` are rewritten by:

```
python3 bundled/packs/build_demo_packs.py
```

Verified after the build: `packs.verify_content_hash(manifest)` returns clean, `packs.audit_bundle(pack)`
returns `[]`, and `tests/test_packs_fixtures.py::test_committed_manifests_match_the_builder` compares the
committed manifest to a fresh build.

Fields added: `files[]` entry (`role: narration`, `mime: audio/mpeg`, real `bytes`/`sha256`,
`text_equivalent` with Japanese + romaji + English, `description`), a `license.per_artifact` record
(`license_id: Apache-2.0`, attribution naming the model, the voice and "no human speaker"), a `narrator`
contributor, one `content_notes` entry (tool, date, sample rate, encoder), one `accessibility_notes` entry
(the clip carries its text equivalent; the lesson does not depend on hearing it), and the rewritten
`safety_notes` line.

Notes that changed, and only as far as they became false:

- Old: "No audio is bundled, so no listening evidence is claimed and no voice is certified."
- New: "Audio is bundled and is synthetic. It is not a native-speaker pronunciation model, and this pack
  implements no listening check and no pronunciation score, so no listening evidence is claimed."

No check's `evidence_target` mentions listening or pronunciation; the grading surface is unchanged.

The parent pack's manifest was rebuilt during the first iteration because the shared attribution string was
edited; it was moved to a Japanese-only constant so `parent-measurement-practice/pack.json` is **not** part
of this diff.

## 4. Tests and evidence

- `python3 -m unittest discover -s tests -t .` → **Ran 1647 tests, OK (skipped=1)**.
- New roundtrip probe:
  `tests/test_packs_roundtrip.py::RoundtripTests::test_imported_japanese_pack_exposes_the_narration_audio_and_its_text_equivalent`
  exports the pack, reimports it through `archive.StagingArea`/`PackLibrary`, and asserts the adopted
  manifest still declares `role: narration`, `audio/mpeg`, the same byte count and sha256,
  the Japanese/romaji/English text equivalent, the Apache-2.0 per-artifact licence, and that the bytes parse
  as ≥20 MPEG Layer III frames over 1.5 s (a stub or a silent zero-length file fails this).
- New fixture tests: `test_narration_asset_is_declared_licensed_and_not_a_stub` (declared size ≥4 KiB,
  hash matches, >100 distinct byte values, licence and text equivalent present) and
  `test_audio_note_claims_only_what_the_pack_implements` (the stale "No audio is bundled" line is gone, the
  note still denies listening evidence, no check scores listening or pronunciation).
- `bash scripts/validate-plugin.sh` — result recorded at the end of this file.

Command used to re-derive the numbers in §1 (scratch script outside the tree; it imports the test
module's frame parser and the pack loader):

```
python3 /home/deseretsaint/.hermes/profiles/lattice/cache/scratch/h72/probe_h72.py
→ path content/narration-polite-confession.mp3
  mime audio/mpeg bytes 22272 sha sha256:dea7f196…71349
  parsed_seconds 2.784 frames 116
  content_hash sha256:447aace8…3856
  verify_content_hash None
  audit []
```

## 5. Why the demo still does not say "spoken"

`coursebook/pack_flow.py::_write_lesson_page` materializes a pack's **section text** into `lesson_segments`
(`teaching`, `check_prompt`) and writes nothing else. Import creates no `artifacts` row and no `media`
segment for a `visual` or `narration` file, and the pack schema has no field linking a media file to an
objective or a section. So in this build:

- the pack's audio is **declared, hashed, licensed, previewed and exported** (pack preview, `pack.inspect`,
  the export file list and `review_export_tree` all carry it), and the roundtrip probe proves it survives;
- the lesson surface has **no route that plays it** — `MediaSegment` in `desktop/plugin.js` only ever plays
  an `artifact_id` from a lesson segment, and no pack-file artifact is created.

Bundling the file therefore does not make the shot audible, and claiming otherwise would be exactly the
stale claim this card exists to remove. `docs/DEMO.md` row 73–82 s is now: show the sourced visual, then its
text alternative and the next review date — narration "A sourced visual, with the text right here. The next
review is scheduled." — with the acceptance column reading "no audible-playback claim".

**What a later card would need (not done here, deliberately):** a media seam that adopts a pack's declared
`visual`/`narration` files as artifacts at import and attaches them to a lesson page — which first requires
a contract-level way to say *which* objective a media file belongs to. That is an Atlas schema decision and
a Desktop change, and it would invalidate the M4-V frames again. It is not invented in this card.

`desktop/plugin.js` was **not** touched. No `role: "audio"` was added; the frozen contract already allows
`narration` + `audio/mpeg` and that is what is used.

## 6. What the demo may and may not say about the audio

May say:

- the pack ships one narration clip for the polite line, with the Japanese text, its romaji and its English
  meaning on the page;
- the clip is synthetic, produced offline, licensed Apache-2.0, and is a model of the line rather than a
  native-speaker reference;
- the file appears in the pack preview and in the export file list with its size, hash and role.

May not say:

- that the lesson plays the audio, that the learner hears it, or that a listening check exists;
- that any pronunciation was scored, certified or reviewed by a native speaker;
- that the voice is a person, or name a speaker. The voice id `jf_alpha` is a model voice embedding, and it
  is described as such.

## 7. Stale stills (supervisor re-pins; this card did not regenerate frames)

The pack `content_hash` changed from `sha256:638ce371…6d7f` to `sha256:447aace8…3856`, and the manifest now
lists a sixth file. Any still or record that shows the pack preview file list, the file count, the expanded
byte total or the content hash is stale. Known ones:

- `audit/visual/m4-visual/` textbook / guided / field-quest media frames — they render a fixture media
  surface, not the pack; they do not show the audio file and are unchanged in content but now incomplete as
  evidence for the pack.
- `tests/adversarial/evidence/attack-packs.json` — recorded at `638ce371…`; its pack preview, export file
  list and data-scope hashes no longer match this pack. It is a historical audit record, not a live
  assertion (no test reads those hashes).
- `docs/REVIEW_CB017-demo-gate.md` rows 51 and 146 — annotated by the H-72 addendum at the end of that file,
  not rewritten.

## 8. Release gate

`bash scripts/validate-plugin.sh` on the committed branch — see `## Gate result` below.

## Gate result

```
$ bash scripts/validate-plugin.sh
== 1/3 plugin admission: PASS ==
== 2/3 desktop module: PASS ==   (desktop/plugin.js: syntax OK)
== 3/3 desktop contract tests: PASS ==   (Ran 26 tests, OK)
Release gate passed: 3/3 checks on e9c030d26d174d018b6c187ff5c5f43c5ef49805 (1566 files).
```

Run on the committed branch (`git archive` export of the commit, not the checkout), so the new MP3 and the
regenerated `pack.json` are the ones the gate saw.

The commit named there is the implementation commit; the review file was amended onto the same branch
after that run, and a doc-only amend cannot change the plugin, the Desktop module or the pack. The final
HEAD was re-gated the same way before this branch was handed back.
