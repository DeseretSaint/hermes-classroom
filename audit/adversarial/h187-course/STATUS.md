# H-187 preparation — two courses with explicit audio and visual media requirements

Base tree: `wt/t_ac36aad4` from master `127cce1` (the H-187 fixes are already integrated in H-190,
`71f74e7`). Nothing in this task generates media: the store holds **0 artifact rows and 0 bytes**.

## Why the H-187 course was not reused

H-187's own evidence (`audit/adversarial/live-generation-2026-11-08/STATUS.md`) records that no
scope reached `plan.approve`: every plan job died in `coursebook.plan.validate`, and the one plan
that authored did so under a different plan id. There is no stored course, lesson or page in that
evidence to select. This task therefore produces a fresh equivalent, and says plainly that the
lesson prose was **authored by a preparation script**, not by a live model authoring pass.

## What exists now

A real, migrated SQLite store at

```
/home/deseretsaint/.hermes/h187-course/home
  plugin-data/coursebook/data.db        (sha256 703980dcc7f0413b4cb9655e93d1a06374c4050f7b3675d94aaa5ead6620ca3d)
```

built through the product commands `course.create`, `enrollment.create`,
`domain.record_objective` and `plan.approve`, then the product schema for plan document, sections
and lessons. Both courses load through `library.list`; every lesson page loads through
`lesson.page`.

**Two courses, not one, and why.** The capability policy decides audio from a plan whose domain
is `language` and a schematic from a plan whose domain is not `language`; one plan carries one
`subject_domain`. A single mixed-domain course is not a shape this product can author, so the
deliverable is the pair. Both are listed below and both load.

| role | course id | plan id | enrollment id | plan state |
|---|---|---|---|---|
| language + audio | `crs_c330330a969646cfb0735f9f3644c107` | `pln_a5481374abaa48c9824e656001a32c48` | `enr_22c18bf3305a4b0ca769b8219e0036dd` | approved |
| procedural + visual | `crs_53a1191816354c44acec268a03d6dba0` | `pln_5e9bb1300ea54413b3e422c9fe5a10d4` | `enr_5906d9d5f01a420cba6d2d202db8da53` | approved |

Course A — *Bike-shop Japanese: greet and say it aloud* (`locale: ja`, `level: L0`,
`subject_domain: language`, recipe `committed`), plan hash
`sha256:81079d0c4f11f9c4066c8e59749598e758180eab2063bac70dfa3a74608fd847`.

Course B — *Workshop procedure: torque a wheel in a cross pattern*
(`subject_domain: technical_procedure`, no locale, recipe `committed`), plan hash
`sha256:1642737af387e6d38c56198759b25f4d223d8e91deafe24270af5469df140aac`.

## The media requirements, and exactly where each artifact attaches

`page` is `lesson.page` with the course's enrollment id and the objective id. `block` is the
block id the served document already projects today (empty media child: `artifact_id: null`).

### 1. Audio — language / pronunciation lesson (course A)

- **lesson id**: `gen_lang_1`
- **section id**: `sec_lang_1`
- **objective id**: `obj_903c89f63e4940d7a8220082e4d68429`
- **objective**: *Greet shop staff with こんにちは and say it aloud*
- **declared need**: audio `required`, role `pronunciation_reference`; construct
  "pronounce the greeting こんにちは aloud from a clear model"
- **stored MediaSpec**: `kind: audio`, `role: narration`,
  `language: ja-JP`, `voice: default`, transcript `こんにちは`,
  text equivalent "こんにちは (konnichiwa) — the standard daytime greeting, hello / good afternoon."
- **producer**: `host.text_to_speech` (TTS)
- **mime constraint**: expected `audio/mpeg`; bytes must sniff as MPEG audio (ID3 or `0xFF 0xEx/0xFx`
  frame sync); kind `audio`; ceiling 67,108,864 bytes (64 MiB)
- **attach to**: lesson `gen_lang_1`, block `blk_280128ee1e4e4ded9d13` (role `practice`,
  headline "Say it back"), `media[0]` inside that block. The audio lesson has exactly one media
  child; after generation the block's child carries `artifact_id`, and the page's `artifacts[]`
  row carries `mime`, `bytes`, `content_hash`.

### 2. Required visual — procedural / technical lesson (course B)

- **lesson id**: `gen_tech_1`
- **section id**: `sec_tech_1`
- **objective id**: `obj_f57dc61989524ad99bb7fc66346e36b6`
- **objective**: *Tighten the four wheel bolts in the cross sequence*
- **declared need**: image `required`, role `schematic`; construct "a labelled sequence showing
  the four wheel bolts and the cross-pattern tightening order"
- **stored MediaSpec**: `kind: visual`, `role: schematic`, facts rows
  Step 1 front-left, Step 2 rear-right, Step 3 front-right, Step 4 rear-left
- **producer**: `deterministic_schematic` — `artifacts.make_schematic_svg`, **not** a provider
- **mime constraint**: `image/svg+xml`; bytes must be an SVG that passes the allowlist sanitiser
  (scripts, `foreignObject`, external `href` rejected); kind `visual`; ceiling 8,388,608 bytes
- **attach to**: lesson `gen_tech_1`, block `blk_8c780aa7b2cfb51d39aa` (role `example`,
  headline "The cross pattern"), `media[0]` inside that block.

  This is the card's "procedural lesson that requires a visual": the requirement is real and
  `missing_required_media` refuses the lesson without it. It does **not** call `image_generate`:
  the policy permits a required image only as `schematic` or `sourced_reference`, and an AI
  illustration is explicitly never required evidence (`policy.py`).

### 3. `image_generate`-reachable visual — technical lesson (course B)

Because a required image may never be an illustration, `image_generate` is reachable only through
an **optional** `illustration` role. The sibling image card therefore has a real target:

- **lesson id**: `gen_tech_2`
- **section id**: `sec_tech_2`
- **objective id**: `obj_75056df1acb84e4ea637b30421c5cca9`
- **objective**: *Recognise the workshop bench layout before starting*
- **declared need**: image `optional`, role `illustration`; construct "a workshop scene showing
  the bicycle wheel clamped in the stand beside the torque wrench"
- **stored MediaSpec**: `kind: visual`, `role: illustration`, prompt
  "An editorial illustration of a bicycle wheel clamped upright in a workshop stand, a torque
  wrench laid beside it on the bench; no text labels, no measurement claims."
- **producer**: `host.image_generate`
- **mime constraint**: expected `image/png`; bytes must sniff PNG
  (`89 50 4E 47 0D 0A 1A 0A`); kind `visual`; ceiling 8,388,608 bytes
  (the producer declares `image/png`, so a JPEG returned by the provider is refused, not relabelled)
- **attach to**: lesson `gen_tech_2`, block `blk_aecba1e56d346fc8e07b` (role `example`,
  headline "The bench, described"), `media[0]` inside that block.

Note on the read shape: `lesson.page` returns an `artifacts[]` list scoped to the **course**, so
course B's page may list both its schematic and its illustration. The per-page attachment is the
`artifact_id` on the block's media child, not membership in `artifacts[]`.

## Machine-readable target list

`downstream_media_targets.json` is the compact form of this section: one entry per media item with
`course_id`, `enrollment_id`, `objective_id`, `lesson_id`, `lesson_page_call`, `media_kind`,
`media_role`, `producer`, `expected_mime`, `mime_rule`, `spec_fingerprint` and `attach_to`
(`block_id`, `block_role`, `media_index_in_block`). Generate `downstream_targets.py` from
`verification.json` whenever the store is rebuilt.

## What is honest about this store and what is not claimed

- **No media bytes exist.** `artifacts` count is 0 and every media child has `artifact_id: null`,
  `mime: null`, `degraded: true`, reason "not generated yet; this task declares the requirement
  and does not produce bytes". A downstream worker must generate the bytes.
- **No live model authoring pass is claimed.** `build_course.py` authored the prose and wrote the
  rows; it made no provider call. `course_facts.json` records `authored_by` and
  `media_bytes_generated: 0`.
- **No validation pass is claimed.** The three `gen_lessons` rows carry state `model_assessed`
  only because that is the state `media.generate_for_lessons` and `lesson.page` admit;
  `validation_id` is NULL. The served page says so in its own provenance:
  `{"outcome": "model_assessed", "independent": false, "check_enabled": true,
  "warning": "model assessed, not independently validated: treat this page as a proposal."}`
- **No checks exist** (`check_id: null`): these pages are media carriers, not graded lessons.
- **The rehearsal is not evidence.** `rehearse_media_path.py` copied the store to a throwaway
  home, bound a fake host returning synthetic PNG/MP3 bytes, and got `generated: 3, degraded: 0,
  skipped: 0` with each artifact landing on the block above. That proves the specs are actionable
  and the caller does not refuse them; the bytes are fake and the prepared store was untouched
  (same `db_sha256`, 0 artifacts after the rehearsal).

## Reproduce / verify

```bash
python3 audit/adversarial/h187-course/build_course.py      # fresh store (new ids)
python3 audit/adversarial/h187-course/verify_course.py     # re-serve pages, hash the db
python3 audit/adversarial/h187-course/downstream_targets.py  # compact target list
python3 audit/adversarial/h187-course/rehearse_media_path.py  # fake-byte rehearsal, copy only
python3 -m unittest tests.test_media_generation tests.test_capability_policy tests.test_media_plan
```

Last run: 58 tests, OK. `verification.json` carries every id, block id, spec fingerprint, expected
mime and the db hash; `course_facts.json` carries the served documents.
