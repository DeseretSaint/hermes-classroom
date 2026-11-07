# Lesson capability policy

**Status:** M1-P1 implemented the pure policy on `wt/m1-capability-policy`; M1-P3 binds it into
generation (`lesson-prompt.v5`) and validation on `wt/m1-policy-integration`. Authority:
`coursebook/policy.py`.
Plan: `docs/VISUAL_MEDIA_PLAN.md` §4 (capability policy and rubric angles) and §8 (technical
visuals), `docs/VISUAL_MEDIA_PLAN.md` §5.2 (generation policy), §5.3 (rubrics).

The module itself adds no prompt, contract or UI dependency. P3 (below) is where the policy reaches
the model and the validator. Nothing here publishes, tags, opens a catalog PR or claims Coursebook
is installable.

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

## 6. Integration: how the plan reaches the model and the validator (M1-P3)

`coursebook/generation.py` computes the plan with `lesson_capability_plan(...)` once per section,
before any prompt is built:

```
lesson_capability_plan(recipe=..., section=..., objective=..., locale=..., dials=..., plan=...)
    -> policy.plan_lesson_capability(recipe, objective.evidence_target, section.lesson_intent,
                                     locale, dials.level, subject_domain)
```

The subject domain is advisory and read from the section, then the plan, then the dials. Nothing
else is inferred: the construct must be named by the authored intent.

**Prompt.** `lesson-prompt.v5` receives only the resulting permissions and angles. For a lesson
whose policy says image `none`, the instruction is literally "emit no visual media item" plus the
plan's reason; it is never offered a menu of media kinds. The same is true of audio. The payload
also carries `capability_policy` (the plan projection) so the model sees the same decision the
validator will apply. The plan prompt names the recipe's forced check angle (`verification` for
one-off, `observation` for parent) and states that media is not the default.

**Schema and record.** `LESSON_SCHEMA` accepts a `policy` object internally (never learner-facing).
The harness overwrites whatever the model echoed with the computed plan, stores it in
`gen_lessons.policy_json`, and gives the same object to `enforce_lesson_rules`.

**Two gates, no bypass.** Media must pass both:

1. `policy.media_policy_problems(plan, media)` — is this kind/role permitted at all? A visual item
   in an image-`none` lesson (algebra derivation, one-off brief, parent reading, language
   reading-only) or an audio item in an audio-`none` lesson is rejected with the plan's reason. A
   permitted kind still has to use the permitted role (`illustration`, `schematic` or
   `sourced_technical` for images; `narration` for audio — a pronunciation reference is narration
   whose transcript is authoritative).
2. `artifacts.media_problems(spec)` — is the spec complete and honest? Text equivalent, narration
   transcript/voice/language, a sourced technical reference with `source_ids` and an explicit
   permission, a schematic with structured `facts.rows`, and an illustration that never claims
   technical authority.

Neither gate is advisory and neither can be satisfied by the validator's silence: a failure is a
`_RuleViolation` before the independent validator is called, so attempt 1 retries with the itemised
reasons and attempt 2 parks the lesson `needs_review`.

**Rubric angle.** The profile is resolved with `rubrics.resolve_profile(plan.rubric_profile,
declared_target)` so the check's declared evidence target stays authoritative; the profile's
criteria are validated as before. Media never counts as evidence and a clean rubric is never a
mastery claim.

## 7. What this line still does not do

- No `cb.rpc`/`cb.db` contract revision. `policy_json` is an additive internal column on the
  generation-owned `gen_lessons` table, migrated in place when absent.
- No UI change: the Desktop renders whatever the learner page already carries.
- Required-media *presence* is not enforced here. P3 refuses forbidden and dishonest media; making
  a required schematic/narration appear is the media job's production path, and a missing item
  degrades to the text equivalent rather than being fabricated.
- A schema-valid pack that declares its own media is still governed by the pack contract and
  `artifacts.media_problems`; the capability plan applies to **generated** lessons.

## 8. Verify

```
python3 -m unittest tests.test_capability_policy -v
python3 -m unittest tests.test_policy_integration -v
python3 -m unittest discover -s tests -t .
bash scripts/validate-plugin.sh
```

`tests/test_capability_policy.py` also asserts that the mirrored enums cannot drift from
`generation.RECIPES`, `generation.EVIDENCE_TARGETS` and `packs.MIN_RUBRIC_CRITERIA`, and that
`coursebook/policy.py` imports only `__future__`, `re`, `dataclasses` and `typing`.
`tests/test_policy_integration.py` covers the six matrix lessons for both prompt and validator:
the decision is named, forbidden media is never offered, permitted media passes both gates, and
policy-inappropriate media is rejected deterministically.
