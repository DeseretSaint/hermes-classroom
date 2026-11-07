# Coursebook visual and media plan

Status: planning draft for the post-CB-017 product line. This document freezes the direction
before implementation. It does not change the release gate in `docs/SUBMISSION.md` §0.

**M0 implementation status:** the host media adapter, lesson-post media generation, cache/fallback,
lesson-run media projection and the inline Desktop preview are merged on `master` at `3cead45`
(698 tests, `node --check`, validate 3/3 on 924 files). M1–M4 below remain the product plan.

## 1. The problem this plan solves

Coursebook is currently legible as a governed course *harness*: it can research, plan, author,
validate, grade and export. It is not yet legible as a place where a learner wants to spend time.
Two facts explain most of the gap:

1. The lesson surface is one linear list of prose segments. The renderer prints the segment
   `kind` as a small label, discards the authored `heading` for layout purposes, and has no
   presentation-mode state. Textbook, Guided and Gamified are therefore claims in the spec, not
   surfaces in the product.
2. The generation schema already contains declarative media specs, and `coursebook/artifacts.py`
   already owns a content-addressed store, MIME policy, cache keys, provenance and honest text
   fallback. But the lesson prompt said "never generate an image", no production
   caller reaches the media job path, and the Desktop renderer only shows a `View media` toast
   for a `segment.artifact_id`; it never displays an image or plays audio.

The fix is not "add a picture field". It is a media-capable lesson document:
**one validated lesson, several presentation views, and media that is generated, cached,
rendered and honestly labelled.**

## 2. Product principle

> The lesson is the document. The view is a lens. Media is evidence-bearing material inside the
> document, never a second authority and never a substitute for the text.

A learner can switch views without changing what counts as evidence:

| View | What it is for | What it renders |
|---|---|---|
| **Textbook** | reading, reference, revision | every block in authored order, full `deep` prose, inline figures |
| **Guided** | first pass, low working memory | one block at a time, `short` text, progress and a Continue control |
| **Field Quest** | motivation and sequence | the same blocks as a path of small missions; existing checks are the gates |
| **Field Notes** | capture and return | notebook entries, media, source cards and a next-best-action rail |

Gamification changes presentation, not evidence. There are no locked core lessons, no cosmetic
badges that imply mastery, and no second grading path.

## 3. Visual direction: "Ink & Field Notes"

Coursebook should look like a specialist instrument inside Hermes, not a second generic chat
pane. Hermes remains the spine: the app window, chat, gateway, theme contract and accessibility
rules stay Hermes. Coursebook contributes the teaching surface.

### 3.1 Palette

Use Hermes semantic tokens where they exist, and add only a small Coursebook namespace:

```
--cb-paper          warm off-white / near-black in dark mode
--cb-paper-raised   cards and reading surfaces
--cb-ink            primary text
--cb-ink-soft       secondary text
--cb-rule           hairlines and table rules
--cb-accent         indigo/ink blue for actions and active path
--cb-accent-soft    tint for selected blocks and focus rings
--cb-field          moss/olive for "done" and field notes
--cb-ochre          warm warning / "needs review"
--cb-coral          attention, never a substitute for error red
```

Do not use gradients as decoration. Do not use raw colours outside the token layer. Every token
must have a light and dark value and pass the existing contrast harness. The current Hermes
light-mode tertiary-text override already establishes the floor; Coursebook must not lower it.

### 3.2 Type and rhythm

- Reading text: the host's UI text face at a comfortable measure, 62–72 characters; headings use
  the host's heading face. No web-font download; the desktop must work offline.
- Lesson title: 28–34 px, tight leading; block heading: 18–22 px; body: 15–16 px, 1.55–1.7 line
  height.
- Use whitespace and rules, not boxes inside boxes. A block is separated by rhythm, not a card
  border on every paragraph.
- Media sits in a **field-note frame**: a thin rule, a caption, a provenance line and a
  "text equivalent" disclosure. It never floats as decoration.
- Motion is functional only: 100–140 ms for view transitions and block advance. Respect
  `prefers-reduced-motion`; no animated progress theatre.

### 3.3 Page architecture

The lesson route becomes a three-part workspace:

```
┌────────────────────────────────────────────────────────────────────┐
│ Coursebook · course title · section n of m · view switcher         │
├───────────────────────────────────────────────┬────────────────────┤
│ Lesson document                               │ Field rail         │
│                                               │                    │
│  orient block                                 │  next action       │
│  explain block + figure/audio                 │  listen / repeat   │
│  example block                                │  source cards      │
│  practice block + check                       │  notebook          │
│  recap block                                  │  progress          │
└───────────────────────────────────────────────┴────────────────────┘
```

On narrow layouts the rail becomes a bottom sheet. The reading column never shrinks below a
usable measure; the rail collapses before the text does. The chat remains the Hermes chat; the
Coursebook pane is the teaching surface and must be revealed beside it on lesson start (the
existing `revealPane` fix is the precedent).

### 3.4 Course home: "Field Desk"

Replace the current list-first home with:

- a single **Continue** card: current section, next action, estimated minutes, last touched;
- a **Field Notes** strip: saved excerpts and media from this course;
- a **Path** preview: the objectives as a compact route with state, not a table;
- a **Sources** drawer, collapsed by default;
- a secondary "All courses" list for people who actually have several.

The home must answer "what do I do next?" in one glance. It must not become a dashboard of
vanity metrics.

## 4. Capability policy and rubric angles

The harness must decide **what kind of lesson this is** before it decides what to generate. A
head-gasket procedure needs a deterministic schematic and a verification checklist; a Japanese
greeting needs narration and a production check; an algebra derivation needs neither an image nor
audio and should not get either.

Introduce one explicit, testable `LessonCapabilityPolicy` (new module `coursebook/policy.py`) with
inputs:

```
recipe            one_off | casual | committed | companion | parent
evidence_target   recall | comprehension | production | discrimination | procedure | transfer
lesson_intent     the authored section intent
locale / level     language and scaffold context
subject_domain    language | technical_procedure | mathematics | history | ... (advisory)
```

It returns a typed plan, not prose:

```
image:      none | optional | required
image_role: illustration | schematic | sourced_reference
audio:      none | optional | required
audio_role: narration | pronunciation_reference
check_angle: recall | comprehension | production | discrimination | procedure | transfer
             | verification | observation
rubric_profile: concept_explanation | procedural | language_production | recall_accuracy
                | source_analysis | observation
```

Hard rules:

- Default is `none` for both media. Media is added only when it carries the lesson's evidence.
- An abstract, symbolic or grammar lesson gets no image and no audio unless the authored intent
  names a genuinely visual or oral construct.
- A language pronunciation/production objective may require narration; a reading/writing
  objective must not get narration merely because the course has a locale.
- A technical procedure may require a schematic or a permissioned source image; an AI
  illustration is context only and is never a measurement, sequence or safety authority.
- A one-off practical brief gets a verification checklist, not a quiz, and no decorative media.
- A parent lesson gets parent observation, not a child quiz.
- The policy is deterministic and tested over a matrix of representative lessons (head gasket,
  Japanese greeting, algebra, history source analysis, wiring brief, parent reading lesson).
- The model may propose media, but the policy and validator reject media that the lesson does not
  justify. The prompt must ask for media only when the policy permits it; the validator must not
  invent a media requirement after the fact.

Rubrics are selected by construct, not one generic template:

- concept explanation: accurate claim, mechanism, example, limits;
- procedural: ordered steps, safety stop condition, verification;
- language production: target phrase, pronunciation/fluency, meaning, register;
- recall accuracy: correct answer, accepted alternatives, no cue leakage;
- source analysis: claim, evidence, provenance, contradiction handling;
- observation: observable behavior, context, note, follow-up.

Every profile still requires at least three distinct observable criteria. “Understands” is never a
criterion. The rubric profile is recorded on the plan/lesson and checked against the objective's
evidence target.

## 5. Lesson document model

One validated `LessonDocument` is stored per section and shared by every view.

```json
{
  "section_title": "...",
  "objective_id": "...",
  "blocks": [
    {
      "id": "blk_...",
      "role": "orient|explain|example|practice|recap",
      "headline": "...",
      "short": "...",
      "deep": "...",
      "check_id": null,
      "media": [
        {
          "kind": "visual|audio",
          "role": "illustration|schematic|narration",
          "artifact_id": "art_...",
          "purpose": "...",
          "text_equivalent": "...",
          "label": "..."
        }
      ],
      "source_ids": ["src_..."]
    }
  ],
  "check": { "...": "unchanged" },
  "sources": [ "..." ],
  "media": [ "..." ]
}
```

Rules:

- `role` is structural, not a skin. Textbook renders `deep`; Guided renders `short` one block at
  a time; Field Quest maps the same `role` sequence to missions.
- `short` and `deep` are both authored from the same validated source. `short` may omit detail,
  but may never add a claim that `deep` does not support.
- A block's `check_id` is the only place a check attaches. Checks are not duplicated per view.
- Media is a child of a block. It has one artifact, one purpose, one text equivalent and one
  honesty label. It cannot be a free-floating gallery item with no teaching role.
- The server is the authority for the document and for which artifact bytes are served. The
  Desktop never invents a media URL or a caption.

Migration: `gen_lessons.page_json` already stores segments and media. Add a `blocks` array in a
contract v8 read shape, projected from the existing validated page first, then authored directly
by the lesson prompt. Do not rewrite old rows. A v7 page renders in Textbook with a clear "this
older lesson has no guided view" state rather than a broken toggle.

## 6. Media architecture

### 5.1 Host seams

Coursebook must not read provider keys. The host already owns image generation and TTS:

- `image_generate` — configured `image_gen.provider` (currently `nous`). Returns an image URL or
  an absolute path.
- `text_to_speech` — configured `tts.provider` (currently `openai`). Returns a local audio path
  and a `MEDIA:` marker.
- Future pronunciation scoring needs a **host STT seam**. Until a public seam exists, the
  Coursebook backend may use the host's transcription service only through an explicitly
  documented adapter with a fail-closed "practice only" state; it must not read credentials or
  call a raw provider.

The agent-half `register(ctx)` binds a `HostMedia` object that wraps `ctx.dispatch_tool`.
Generation jobs run in the agent process, outside every transaction. Bare tests inject a fake
producer; they never call a provider.

### 5.2 Generation policy

- **Illustration** (`role=illustration`): AI image generation for context, atmosphere or a
  non-authoritative visual. Always labelled "Illustration — generated for context only. It is
  not a measurement, procedure, technical reference, or safety authority."
- **Schematic** (`role=schematic`): deterministic SVG from structured facts. Used for technical
  sequences, measurements, labelled parts and safety-critical steps. Never an AI image.
- **Sourced technical** (`role=sourced_technical`): a cited source's image or document, with
  permission status. Never synthesized.
- **Narration** (`role=narration`): TTS from the transcript. Used for language phrases,
  pronunciation models and optional lesson narration. The transcript is authoritative; audio is
  a rendering, not a second text.
- **No media** is a valid, complete lesson. A provider failure produces a visible degraded state
  and the complete text equivalent; it never produces a fake file or a silent substitution.

Technical procedure example (head gasket): the lesson should use a schematic or sourced
reference for torque sequence, part orientation and hazard callouts; an illustration may sit
beside it for context but may not be the procedure authority. This is a hard boundary, not a
style preference.

### 5.3 Storage and caching

Reuse `coursebook/artifacts.py` unchanged:

- content-addressed objects under the profile's `plugin-data/coursebook/artifacts`;
- `spec_hash` + `source_hash` cache key so a retry or reconnect never pays twice;
- MIME sniffing and size ceilings;
- SVG allowlist for deterministic schematics;
- provenance (`generator`, model, voice, language, prompt hash, source ids, label);
- honest text fallback with triage options.

Generation writes bytes before the DB row, then records metadata in one short transaction. The
lesson job records media artifacts in `gen_lessons.media_json` only after the bytes exist.

### 5.4 Rendering

The Desktop needs a binary-preview seam because `ctx.rest` is JSON, not a binary channel. Add a
small authenticated plugin route:

`GET /api/plugins/coursebook/media/{artifact_id}` → `{mime, bytes, label, data_url}`

The route verifies the artifact row size and sha256, refuses oversized payloads, and returns a
data URL only for renderable media (PNG/JPEG/WebP/GIF/SVG/MP3/WAV/OGG). The lesson renderer
uses that data URL in a native `<img>` or `<audio controls>` element, with the text equivalent
as caption and alt text. If the route refuses, the text equivalent and a download handle remain.

Audio never autoplays. A "Play" control is explicit and keyboard reachable. Images are lazy and
respect the reduced-data/text-only path. Every media item has a visible provenance line and a
caption.

## 7. Pronunciation: a real practice loop, not a fake score

The language-audio path is:

1. **Model phrase**: TTS generates a reference audio artifact from the authored transcript,
   with locale, voice and transcript metadata.
2. **Listen**: learner plays the reference; the text equivalent and romaji/furigana scaffolds
   are visible according to the lesson policy.
3. **Record**: learner records a short take in the Desktop with `MediaRecorder`; the take is
   uploaded to the plugin backend as a bounded audio blob.
4. **Transcribe**: the backend sends the take through the host STT adapter (configured
   `stt.provider`; currently `openai`) with the lesson locale as the language hint.
5. **Assess**: a separate, bounded scoring adapter compares the transcript and, where available,
   word/phoneme confidence against the target. It returns:
   - `transcript`, `target`, `locale`, `provider`, `model`;
   - `word_accuracy`, `phoneme_accuracy` (nullable), `confidence`;
   - `words[]` with `expected`, `heard`, `match`, `confidence`;
   - `verdict`: `meets_target | close | needs_practice | unavailable`;
   - `evidence_class: model_assessed`.
6. **Record evidence**: a pronunciation attempt is a real attempt with `evidence_class =
   model_assessed`; it is not "verified pronunciation" and never "mastery". The learner can
   dispute a score. No scorer configured → the UI says "practice only, not graded" and records
   no evidence.

Scoring must be **task-appropriate**: a single word, a phrase, a pitch-accent pattern and a
free response are different constructs. Do not reduce them to one cosine number. The first
shipping slice supports **word/phrase read-aloud** with transcript + word-level comparison; free
speech and pitch-accent scoring are later.

Privacy: audio is sent only after an explicit record action and a visible disclosure of the
configured STT provider; takes are deleted after scoring unless the learner saves them. The
recording is never included in a community pack or an export.

## 8. Technical visuals and procedure lessons

For a head-gasket or similar procedure, the lesson view uses:

- a **procedure header** with tools, parts, hazards and a stop condition;
- **step cards** with a number, an action, a check and an optional schematic;
- a **torque/sequence schematic** rendered deterministically from structured facts;
- a **"do not proceed"** hazard callout that is visually distinct and never an illustration;
- a completion check that is a verification checklist, not a quiz;
- a source card for the manual or reference, with permission status.

The model may propose the structured facts, but the validator must check them against the
source ledger. An AI illustration can set context; it cannot carry a torque value, a clearance,
a sequence or a safety instruction.

## 9. Contract and schema changes

This is a product-line change, so it gets a versioned contract, not an ad-hoc extra field.

### `cb.rpc` v8

- `lesson.page` response gains `document` (blocks) and `media[]` with `artifact_id`, `kind`,
  `role`, `purpose`, `text_equivalent`, `label`, `mime` and `bytes`; existing fields remain.
- `artifact.get` remains the authority for download handles. The new preview route is a host
  seam, not a contract method.
- Pronunciation adds `pronunciation.attempt` (or an `attempt.submit` answer variant) only after
  the STT adapter and evidence rules are frozen. Do not add a method that silently returns a
  fake score.

### `cb.db` v5

- `gen_lessons.media_json` already exists; no destructive migration.
- Add `schema_migrations` entry only if a new attempt kind or a media provenance table is
  required. Prefer JSON in existing rows for the first slice.
- Keep the current evidence and answer-leak invariants.

### `cb.pack` v2

Pack export already requires text equivalents and per-artifact licences. When audio is actually
generated, the pack may carry `narration` as `audio/mpeg` with its transcript; the current v1
pack rule that narration is audio-only stays. A text-only narration script remains the
narration tab, not a fake audio file.

## 10. Delivery phases

### Phase M0 — media truth (first vertical slice)

- Extend the lesson media spec with `role`, `source_ids`, `permission`, `voice`, `language`,
  `transcript`, `facts`.
- Add the `HostMedia` adapter and bind it in `register(ctx)`.
- Generate media after lesson authoring, cache by spec/source hash, update
  `gen_lessons.media_json` with artifact ids and honest degraded states.
- Seed authored media as `lesson_segments(kind='media')` when a lesson run is created.
- Add the `/media/{artifact_id}` preview route and render images/audio in the lesson page.
- Tests: fake producer, cache hit, provider failure/text fallback, MIME rejection, media segment
  seeding, UI contract scanner. No real provider in unit tests.
- Evidence: one real image and one real TTS artifact generated through the host and accepted by the
  artifact layer (`docs/M0-MEDIA-PROBE.md`); the lesson-pane projection and renderer are covered by
  `tests/test_media_generation.py`. A live lesson-pane observation remains gated by the
  operator-owned default-gateway restart (`t_6a32ffe9`).

### Phase M1 — LessonDocument and Textbook/Guided

- Add the v8 `document` projection and block authoring.
- Implement Textbook and Guided; one-block-at-a-time progress; the same check.
- Migrate old pages to Textbook-only with a clear state.

### Phase M2 — Field Quest and Field Notes

- Map blocks to a quest path; use existing checks as gates.
- Add the Field Desk home, next action, saved media and source cards.
- No locked core content; no evidence-changing gamification.

### Phase M3 — Pronunciation Studio

- TTS reference, recording, host STT adapter, word-level comparison, `model_assessed` evidence.
- Practice-only fallback when no scorer is configured.
- Dispute path and privacy disclosure.

### Phase M4 — visual identity and polish

- Apply "Ink & Field Notes" tokens, reading rhythm, media frames, responsive rail.
- Visual regression at light/dark, 100 %/200 %, 460 px narrow, reduced motion, no-media and
  text-only.
- F-01 contrast remains a gate.

## 11. Acceptance bar

The product line is ready only when all of these are true on one recorded commit:

- A non-Japanese technical lesson (head gasket or equivalent) produces a procedure document
  with at least one deterministic schematic and no AI illustration used as procedure authority.
- A language lesson produces a reference audio artifact, a player in every view, and a
  pronunciation attempt that records `model_assessed` evidence with a transcript and word
  comparisons; with no scorer, it says "practice only, not graded".
- Every generated media item has a text equivalent, a label, a source or generation provenance,
  and a working text fallback.
- An image or TTS provider failure leaves the lesson readable and says what failed; no fake
  artifact appears.
- The lesson renders in Textbook, Guided and Field Quest without changing the check or the
  evidence record.
- The same lesson is usable at 460 px, 200 % text, keyboard only, reduced motion and no-media.
- The pack export contains the approved text and any real media, with licences and text
  equivalents; it never contains attempts, recordings, notebook notes or provider settings.
- Publication remains gated on the operator's final sign-off.

## 12. Non-goals for this phase

- No chat-only "AI tutor" that replaces the validated lesson document.
- No generated image used as a measurement, torque spec, procedure authority or safety
  reference.
- No pronunciation "score" without a real STT/scoring result.
- No community pack that carries private recordings, attempts or notebook notes.
- No visual skin that breaks Hermes theme tokens or the light/dark contrast floor.
- No new provider key path in the plugin.

## 13. Open decisions

1. **Release boundary.** Recommend: land M0 as the media truth slice for the hackathon
   candidate; keep M1–M4 on the product line. Do not stuff the visual rewrite into the RC.
2. **Technical visuals.** Recommend deterministic schematics first, AI illustrations second.
   A generated illustration is never a procedure authority.
3. **Pronunciation provider.** Use the host's configured STT provider; if no provider is
   configured, ship practice-only. Do not add a plugin credential path.
4. **Pack audio.** Ship audio in packs only when the artifact is real, licensed and has a
   transcript; otherwise keep the narration tab textual.
5. **Demo.** The 73–82 s shot needs a bundled audio asset; M0 generates it, so the demo can use
   a real synthesized phrase without shipping a binary fixture.
