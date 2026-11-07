# Lesson capability policy

**Status:** M1-P1 implemented on `wt/m1-capability-policy`. Authority: `coursebook/policy.py`.
Plan: `docs/VISUAL_MEDIA_PLAN.md` §4 (capability policy and rubric angles) and §8 (technical
visuals), `docs/VISUAL_MEDIA_PLAN.md` §5.2 (generation policy), §5.3 (rubrics).

This card adds one pure module and its tests. It does not change the plan or lesson prompts, the
contracts or the Desktop UI; P2/P3 integrate the policy into authoring, validation and export.
Nothing here publishes, tags, opens a catalog PR or claims Coursebook is installable.

## 1. Why this exists

Before this module the harness had no single answer to "what kind of lesson is this?". The lesson
prompt asked for media whenever it seemed useful, the rubric was one generic template, and nothing
made a head-gasket procedure, a Japanese greeting and an algebra derivation differ at the point
where generation is decided. A model could therefore ask for an image of a torque sequence, or for
narration of a reading lesson, and the only defence was a validation complaint after the fact.

`coursebook/policy.py` decides first, deterministically, from facts the plan already carries:

```
recipe            one_off | casual | committed | companion | parent
evidence_target   recall | comprehension | production | discrimination | procedure | transfer
lesson_intent     the authored section intent (the construct the lesson names)
locale / level    language and scaffold context
subject_domain    language | technical_procedure | mathematics | history | grammar | ... (advisory)
```

It returns an immutable `LessonCapabilityPlan`:

```
image:          none | optional | required
image_role:     illustration | schematic | sourced_reference
audio:          none | optional | required
audio_role:     narration | pronunciation_reference
check_angle:    recall | comprehension | production | discrimination | procedure | transfer
                | verification | observation
rubric_profile: concept_explanation | procedural | language_production | recall_accuracy
                | source_analysis | observation
reasons:        four strings naming the construct that justified each decision
```

The function is pure: no database, no network, no provider, no filesystem, no clock. The same
inputs always produce an equal plan. `reasons` is part of the plan because a decision that cannot
name its construct is a preference and must not be allowed to justify media.

## 2. The rule: media must carry the evidence

> Media is added only when the lesson intent names a construct that the media has to carry. If the
> text already carries it and the media only decorates it, the level is `none`.

The default for both media is `none`. A locale is not evidence. A recipe is not evidence. An
objective's evidence target alone is not evidence either: a language `production` objective that
asks for a written greeting card gets no narration, because the intent names writing, not speaking.
The intent names the construct; the policy only classifies that name.

Hard boundaries that the plan object enforces in `__post_init__`:

- `image_role` is `None` exactly when `image` is `none`; the same for audio. A plan never claims a
  role it does not use.
- `image == "required"` is incompatible with `image_role == "illustration"`. An AI illustration is
  context only and can never be required evidence, a measurement, a sequence or a safety authority.
- A plan without reasons is refused. Every decision must be explainable by a construct.

## 3. Decision order

1. **Check angle.** `one_off` is always `verification`; `parent` is always `observation`. Every
   other recipe keeps the objective's `evidence_target`.
2. **Image.** In order: parent reference material, symbolic domains, technical procedure, history,
   language, general. The first named construct wins; absent constructs fall through to `none`.
3. **Audio.** Parent never gets generated narration. Only a language lesson can get audio, and only
   when the intent names a spoken or listening construct. Reading and writing explicitly veto
   narration unless an `... aloud` construct is also named.
4. **Rubric profile.** Selected by construct, never by a single global template: parent observation,
   verification or procedure, language production, source analysis, recall accuracy, and
   concept explanation as the fallback for a comprehension or transfer explanation.

`subject_domain` is advisory in one direction only: it can tighten a decision (mathematics and
grammar refuse AI illustrations even when the intent names a picture) and it selects the rubric
family, but it can never manufacture a visual construct the intent did not name. A strong technical
word (`torque`, `wiring`, `circuit`, `schematic`, `clearance`, `tolerance`) still selects the
schematic when a caller omitted the domain, because the construct is in the text.

## 4. The matrix

Every row appears twice in `tests/test_capability_policy.py` where a positive and a negative case
exist. The reason column names the construct, not a preference.

| Lesson | Recipe | Evidence target | Image | Audio | Check angle | Rubric profile | Reason names |
|---|---|---|---|---|---|---|---|
| Head gasket procedure | committed | procedure | required schematic | none | procedure | procedural | torque sequence |
| Head gasket explanation | committed | comprehension | none | none | comprehension | concept_explanation | no sequence, labelled part, measurement |
| Japanese greeting | committed | production | none | required pronunciation_reference | production | language_production | spoken construct (greet, introduce yourself, aloud) |
| Japanese written greeting | committed | production | none | none | production | language_production | reading or writing (write) |
| Japanese reading-only | committed | comprehension | none | none | comprehension | concept_explanation | reading or writing (read); no speaking |
| Japanese read-aloud | committed | comprehension | none | required pronunciation_reference | comprehension | language_production | spoken construct (read ... aloud) |
| Algebra derivation | committed | comprehension | none | none | comprehension | concept_explanation | symbolic domain, no diagram or graph |
| Algebra graph sketch | committed | comprehension | optional schematic | none | comprehension | concept_explanation | graph |
| History source analysis | committed | transfer | required sourced_reference | none | transfer | source_analysis | poster, provenance |
| History textual source | committed | transfer | none | none | transfer | source_analysis | no source image |
| Wiring brief | one_off | procedure | required schematic | none | verification | procedural | wiring |
| Refund brief | one_off | comprehension | none | none | verification | procedural | no visual construct |
| Parent reading lesson | parent | comprehension | none | none | observation | observation | parent presents; no generated picture |
| Parent field-guide observation | parent | comprehension | optional sourced_reference | none | observation | observation | field guide |
| Japanese grammar discrimination | committed | discrimination | none | none | discrimination | recall_accuracy | symbolic domain |

Notes that matter more than the table:

- The wiring brief is `one_off`, so it is verified by a checklist, not quizzed. The schematic is
  required because the wiring order is the thing being verified, not because a procedure always
  gets a picture.
- The parent reading lesson mentions a picture book. That book is the parent's material, not an AI
  illustration, so the image level is `none`; and the parent is the reader, so narration is `none`.
- The algebra graph row is the only way a symbolic lesson gets an image: a deterministic schematic
  built from structured facts. A picture of a pizza is refused.
- A missing `subject_domain` cannot hide a construct. The torque example still produces a required
  schematic because the intent names the torque sequence.

## 5. Rubric profiles

Rubrics are selected by construct. Every profile covers at least three distinct observable criteria
(`MIN_RUBRIC_CRITERIA`), and "understands" is never one of them:

| Profile | Observable criteria |
|---|---|
| `concept_explanation` | accurate claim, mechanism, example, limits |
| `procedural` | ordered steps, safety stop condition, verification |
| `language_production` | target phrase, pronunciation or fluency, meaning, register |
| `recall_accuracy` | correct answer, accepted alternatives, no cue leakage |
| `source_analysis` | claim, evidence, provenance, contradiction handling |
| `observation` | observable behaviour, context, note, follow-up |

`RUBRIC_PROFILE_CRITERIA` is the shared list P2/P3 render into `check.rubric`. It is a floor for
the construct, not a fill-in-the-blank template: the criteria still have to describe this response.
The pack floor (`packs.MIN_RUBRIC_CRITERIA = 3`) is unchanged.

## 6. What this card does not do

- No prompt change: `_plan_instructions` and `_lesson_instructions` are untouched. P2 asks the model
  for media only where the plan permits it.
- No contract change: no `cb.rpc` or `cb.db` revision. The plan is not persisted yet.
- No validator change: P3 rejects lesson media the policy does not justify. The validator must not
  invent a media requirement after the fact.
- No platform binding: the policy is not yet bound into `coursebook/generation.py`. That is the
  next card, and it will import `plan_lesson_capability` rather than duplicate its rules.

## 7. Verify

```
python3 -m unittest tests.test_capability_policy -v
python3 -m unittest discover -s tests -t .
bash scripts/validate-plugin.sh
```

`tests/test_capability_policy.py` also asserts that the mirrored enums cannot drift from
`generation.RECIPES`, `generation.EVIDENCE_TARGETS` and `packs.MIN_RUBRIC_CRITERIA`, and that
`coursebook/policy.py` imports only `__future__`, `re`, `dataclasses` and `typing`.
