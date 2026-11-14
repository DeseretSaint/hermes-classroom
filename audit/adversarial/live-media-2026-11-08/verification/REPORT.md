# H-187 — Independent verification of live media artifacts and degradation

**Verifier:** Sentinel (adversarial QA / security / accessibility)
**Date:** 2026-11-08 (MST)
**Tree:** `wt/t_2f587f6b` @ `127cce1290b33af4f2cd7ffa1bd7ccd0e87d1359` (plugin.js sha256 `6aeca221…fbf6d4f`)
**Evidence store:** `/home/deseretsaint/.hermes/h187-course/home` — read-only for the verification run
**Verdict: PASS.** 161/161 checks pass across five independent probes. No artifact is missing, fake, or misreferenced; the audio degradation path is honest and grows no player or fake controls.

---

## 1. What was verified, and how

| Probe | File | Checks | Result |
|---|---|---|---|
| Artifact bytes + store rows + `lesson.page` + preview route | `verify_live_media.py` | 88 | PASS |
| Provider-refusal degradation (product path) | `degrade_audio.py` | 25 | PASS |
| Shipped Desktop render (jsdom, React 19) | `run_ui_probe.py` + `ui_probe.mjs` | 31 | PASS |
| Tamper / fake-bytes refusals | `tamper_preview.py` | 8 | PASS |
| Real ASGI `/media/{id}` route | `route_http_probe.py` | 9 | PASS |

The prepared store was never mutated. `sha256(data.db)` before and after every read probe:
`4c3423fcad0543b0baac7f0fea2fd5b6de4c92befe4c6412caca5c0976126c12` (byte-identical to the
hash both parent captures recorded). Destructive probes (degradation, tamper) ran only against
dedicated copies under `/home/deseretsaint/.hermes/h187-course-verify/` and
`…/h187-course-tamper/`.

Raw command transcript: `evidence/commands.log`.

---

## 2. Artifact A — narration `art_adf2e015…` (lesson `gen_lang_1`) — **PASS**

```
$ sha256sum …/objects/20/208bb60d…48d3c
208bb60d6b56b0e734550e849755a3ec6d86d4a726b6293d399989b240648d3c  …
$ stat -c "%s" …            41088
$ od -An -tx1 -N16 …        ff f3 c4 c4 00 5a 8c 39 b8 01 5a c0 00 3b 56 0e
$ file …                    MPEG ADTS, layer III, v2, 128 kbps, 24 kHz, Monaural
$ ffprobe …                 codec_name=mp3 codec_type=audio sample_rate=24000 channels=1
                            duration=2.568000 format_name=mp3 size=41088
$ ffmpeg -af volumedetect    mean_volume: -20.6 dB   max_volume: -4.7 dB
```

Recorded vs observed: size **41088 == 41088**, sha256 **208bb60d…48d3c == 208bb60d…48d3c**,
mime **audio/mpeg == sniffed audio/mpeg**, MPEG frame sync present. The audio carries real
programme material (mean −20.6 dB, peak −4.7 dB), not silence.

Store/DB: `kind=audio`, `course_id=crs_c330330a…`, `ref_count=1`; the object filename equals its
content hash (content-addressed); provenance says `generator=host.text_to_speech`,
`lesson_id=gen_lang_1`, `lesson_state=model_assessed`, `independent=false`, with a
text equivalent and an honesty label.

Served page (`lesson.page`, enrollment `enr_22c18bf…`, objective `obj_903c89f6…`):
- `page.artifacts[0]` = `{artifact_id: art_adf2e015…, kind: audio, mime: audio/mpeg, bytes: 41088, content_hash: sha256:208bb60d…}` — exact match.
- target block `blk_280128ee1e4e4ded9d13` (`role=practice`) has one media child pointing at the same artifact, `degraded:false`, `role=narration`, non-empty `text_equivalent`, `reason:null`.
- page provenance: `outcome=model_assessed`, `independent=false`, warning "model assessed, not independently validated…" — media is never presented as independent evidence.

Preview: `media.preview_artifact()` and the real ASGI `GET /api/plugins/coursebook/media/art_adf2e015…` both return HTTP 200 / `ok:true`, `data:audio/mpeg;base64,…`, and the decoded bytes
hash to `208bb60d…48d3c` exactly. No filesystem path appears in the response body.

## 3. Artifact B — illustration `art_d7dc7afd…` (lesson `gen_tech_2`) — **PASS**

```
$ sha256sum …/objects/a2/a206b349…d6c
a206b3493098e7616c77575cc5a4b252ee36da43b58df14d03183fbc91573d6c  …
$ stat -c "%s" …            598928
$ od -An -tx1 -N16 …        89 50 4e 47 0d 0a 1a 0a 00 00 00 0d 49 48 44 52
$ file …                    PNG image data, 1024 x 576, 8-bit/color RGB, non-interlaced
$ identify -format …        mean=0.871759 stddev=0.263453 colors=50658
$ (last 12 bytes)           00 00 00 00 49 45 4e 44 ae 42 60 82   (IEND + CRC)
```

Recorded vs observed: size **598928 == 598928**, sha256 **a206b349…d6c == a206b349…d6c**,
dimensions **1024×576**, mime **image/png == sniffed image/png**. The PNG decodes fully and has
50,658 distinct colours — a real rendering, not a blank or solid placeholder.

Served page (enrollment `enr_5906d9d5…`, objective `obj_75056df1…`): `page.artifacts[0]` matches
the row; target block `blk_aecba1e56d346fc8e07b` (`role=illustration`) references the same
artifact, `degraded:false`, `reason:null`, with its text equivalent. Preview and HTTP route serve
`data:image/png;base64,…` whose decoded sha256 equals the record.

The required `gen_tech_1` schematic is untouched and remains text-only (`degraded:true`, retained
text equivalent) — consistent with the policy that a required technical schematic is not
AI-synthesised. Not counted as a defect.

## 4. Learner-facing render (shipped `desktop/plugin.js`) — **PASS**

The real module was mounted in jsdom with the repo's SDK stub, its `rest` seam answering with the
real `lesson.page` and the real `/media/` payloads (`evidence/rendered_*.html`).

Generated narration:
```html
<audio aria-label="こんにちは (konnichiwa) — the standard daytime greeting, hello / good afternoon."
       style="width: 100%;" controls="" preload="metadata"
       src="data:audio/mpeg;base64,//PExABajDm4AVrAADtWDqTD…">
```
One `<audio controls>` per artifact, sourced from the verified data URL, with an accessible name
and the text equivalent visible as the caption. Generated illustration renders one `<img alt="A
workshop bench…" src="data:image/png;base64,…">`.

Provider refused (`degrade_audio.py` output rendered):
```
data-cb-block-media="text-only"
No generated artifact is attached; the text equivalent is shown.
Media is degraded: media generation failed (MediaGenerationError); delivered as text
こんにちは (konnichiwa) — the standard daytime greeting, hello / good afternoon.
```
`<audio>` count = **0**, `controls=` = **0**, `data:audio/` = **0**, and no media route was even
called. Stale reference (artifact id present, bytes deleted): again no `<audio>`, no data URL; the
route is called and its refusal is shown ("artifact not found"), with the text equivalent kept.

## 5. Degradation path (product code, provider refusal) — **PASS**

Copies of the prepared home only. The host seam returned the registry's own refusal envelope
(`{"success": false, "error": "provider refused the request …"}`); no network call was made.

- `media.generate_for_lessons` → `generated=0`, `degraded=1`, `artifact_ids=[]`, provider was asked once via `text_to_speech`.
- `gen_lessons.media_json` item: no `artifact_id`, no `content_hash`, no `mime`; `degraded:true`; reason "media generation failed (MediaGenerationError); delivered as text"; `text_equivalent` intact.
- Store: no new artifact row, no new object bytes (`artifacts` count unchanged).
- Served `lesson.page`: block media child has no artifact id, `degraded:true`, a reason, a text equivalent, and the page advertises no audio artifact.
- Second refusal shape (old host with no `dispatch_tool`): seam stays unbound, generation skipped, and the served page keeps the authored degraded item and its text. Nothing is invented.

## 6. Tamper probes (the player cannot be faked) — **PASS**

On a throwaway copy with rows remapped to that copy:

| Attack | Observed refusal |
|---|---|
| flip one byte of stored audio | `ok:false / INTERNAL_ERROR — "artifact hash does not match its record"` |
| delete stored image | `ok:false / NOT_FOUND — "artifact file is missing on disk"` |
| symlink the image object outside the store | `ok:false / NOT_FOUND — "artifact file is outside this profile's artifact store"` |
| HTML payload declared `image/png`, row hash+size rewritten to match | `ok:false / UNSAFE_MEDIA — "artifact bytes are not the declared, render-safe media type"` |

Restoring the untouched bytes returns `ok:true`. Containment, hash and render-safety are all
enforced before a byte reaches the learner.

---

## 7. Findings

**Blocking defects: none.**

**Observations (non-blocking, for owners):**
1. **Image content nit — `gen_tech_2`.** An independent visual read of the PNG finds the wheel
   clamped in a truing stand with a wrench on the bench and **no text, numbers or torque values**,
   but the tool reads as a ratchet/socket wrench rather than a torque wrench. The artifact is
   labelled "context only … not a … technical reference or safety authority" and its text
   equivalent is authoritative, so this is a content-precision note, not an integrity or reference
   failure.
2. **Raw backend copy on a stale-bytes refusal.** When an artifact id is served but its bytes are
   gone, the learner sees the route's raw message `artifact not found` instead of the friendlier
   `useArtifactPreview` fallback. It is honest and the text equivalent remains, but the wording is
   backend-shaped.
3. **Authored vs served media.** `gen_lessons.page_json.media` still carries the author's
   `degraded:true / "not generated yet"` placeholder while `media_json` carries the generated
   overlay; the serve path uses `media_json`. Recorded so the placeholder is not mistaken for
   served state.
4. **Empty shard directory** `artifacts/objects/16/` (no file, no row) left over from an earlier
   capture. Housekeeping only; no orphan bytes.
5. **Degradation reason hides provider detail** (`MediaGenerationError`); honest but not
   diagnostic. Acceptable for learner-facing copy.

**Limitations of this run (stated, not hidden):**
- No local speech recogniser is installed, so the MP3's *spoken content* was not transcribed;
  format, duration, frame sync and energy were verified, not the phonemes.
- The UI probe uses jsdom + the repo's SDK stub (the same seam its own desktop suites use), not a
  live Electron window.
- The HTTP probe mounts the shipped router without the host's auth middleware; auth is the host's
  own `/api/` gate and is out of this card's scope.

## 8. Reproduction

```bash
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_2f587f6b
H=/home/deseretsaint/.hermes/h187-course/home

HERMES_HOME=$H python3 audit/adversarial/h187-independent-verify/verify_live_media.py \
  --home $H --out audit/adversarial/h187-independent-verify/verification.prepared.json

HERMES_HOME=$H python3 audit/adversarial/h187-independent-verify/route_http_probe.py \
  --home $H --out audit/adversarial/h187-independent-verify/route_http.json

HERMES_HOME=/home/deseretsaint/.hermes/h187-course-verify/home \
python3 audit/adversarial/h187-independent-verify/degrade_audio.py \
  --home /home/deseretsaint/.hermes/h187-course-verify/home \
  --out audit/adversarial/h187-independent-verify/degradation.json \
  --served audit/adversarial/h187-independent-verify/served_degraded_page.json

HERMES_HOME=$H python3 audit/adversarial/h187-independent-verify/run_ui_probe.py \
  --home $H --degraded-page audit/adversarial/h187-independent-verify/served_degraded_page.json \
  --out audit/adversarial/h187-independent-verify/ui_render.json

HERMES_HOME=/home/deseretsaint/.hermes/h187-course-tamper/home \
python3 audit/adversarial/h187-independent-verify/tamper_preview.py \
  --home /home/deseretsaint/.hermes/h187-course-tamper/home \
  --out audit/adversarial/h187-independent-verify/tamper.json
```

Note: the degradation and tamper probes refuse to run against the prepared home. Re-running the
degradation probe requires a fresh copy (it removes the audio row to force a real provider attempt).
