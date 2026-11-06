# Vault-derived learning harness and Japanese demo addendum

Date: 2026-11-06
Status: planning input for `PREBUILD_SPEC.md`; no implementation started.
Vault access was read-only. No Obsidian files were modified.

## Purpose

Use the personal vault in two distinct ways:

1. extract **subject-independent mechanisms** that strengthen every Coursebook classroom;
2. build a **Japanese-specific demo/personal classroom** from the JP-Lingo research and personal
   preferences, without pretending Japanese pedagogy is universal.

This document distinguishes readable evidence, design interpretation, and unavailable source
material. A vault note is a research lead, not automatically proof of efficacy.

## Source coverage and limits

Read directly:

- `JP-Lingo/00-INDEX.md`
- `JP-Lingo/deeptutor-research.md`
- `JP-Lingo/humanifier-research.md`
- `JP-Lingo/game-designer-research.md`
- `JP-Lingo/coder-research.md`
- `JP-Lingo/storyteller-research.md`
- `JP-Lingo/ui-ux-research.md`
- `JP-Lingo/minimax-h3-research.md`
- `JP-Lingo/minimax-m3-free.md`
- `JP-Game-OSS-Quality-Stack.md`
- relevant portions of `Design & Render One-Shot Quality — Baseline, Evidence, Gates`,
  `UI-UX One-Shot Playbook`, and `Hermes Memory Mirror`.

The vault index points to canonical findings under `~/projects/japanese-lingo-lab/`,
`~/projects/game-design-lab/`, and `~/projects/writing-story-lab/`. Those directories are not
present on this machine. This limitation is independently acknowledged in the vault's own
`Design & Render...` note at lines 84–90. Therefore:

- statements below cite the readable vault notes by path;
- named but unread canonical FINDINGS files are **unverified leads**, not evidence we have read;
- no exact claims from those missing files become harness rules without fresh verification;
- the Japanese demo pack must re-fetch/verify its actual language claims and sources at pack
  build time, like every other pack.

The vault does not contain a general learning-science library comparable to this Japanese
collection. The general mechanisms below combine vault-derived engineering patterns with the
research cautions already recorded in `AUDIT.md`; they are not represented as a comprehensive
survey of learning science.

---

## 1. Generic mechanisms to incorporate into the harness

### G1 — Keep expected answers outside learner-facing context

Vault basis: `JP-Lingo/deeptutor-research.md` lines 38–42 describes storing the expected answer
with the question and avoiding a model round-trip for memory/procedure grading.

Harness application:

- store reference answers/rubrics in the backend assessment envelope, never in `AGENTS.md`,
  lesson prompts, or pack content rendered to the learner;
- closed-form checks use deterministic validators;
- open responses give the grader the minimal assessment envelope only;
- audit the question/key/rubric before use, since storing an incorrect key locally merely makes
  a wrong grade deterministic;
- no expected answer appears in transcript directives, artifact metadata, DOM text, or source
  previews shown before the attempt.

This strengthens v8 §8; it is not a claim that local answer storage guarantees validity.

### G2 — Use layered, inspectable evidence rather than a learner persona

Vault basis: `deeptutor-research.md` lines 44–49 describes raw traces → curated facts →
synthesis, with each layer traceable to evidence.

Harness application:

- **L1 attempts:** exact submitted answer, stimulus/rubric version, hints, provider/model,
  timing, verdict, dispute, and operation ids;
- **L2 objective evidence:** current independent/delayed evidence per objective, with links to
  L1 attempt ids;
- **L3 plan guidance:** a short, revisable recommendation such as “review register in a new
  context,” citing L2 objective ids.

L3 is never a persistent psychological diagnosis. `possible_error_pattern` requires different
items targeting the same concept. Users can inspect the chain and dispute it. This aligns with
v8's SQLite/evidence model and avoids an opaque “AI learner profile.”

### G3 — One authoritative writer/contract for learning events

Vault basis: `coder-research.md` lines 9 and 25–32 describes a stable data contract and single
anti-gaming/event-writing chokepoint; `game-designer-research.md` lines 72 and 120 repeats the
single-writer constraint.

Harness application:

- backend `submit_attempt`, `override`, `challenge_out`, `approve_parent_plan`, and pack commands
  are the only mutation paths;
- hooks, tools, Desktop actions, imports, and cron adapters call those commands;
- SQLite revision fencing and idempotency prevent duplicate transitions;
- every recipe uses the same event vocabulary, with recipe policy deciding what the events mean.

This confirms the v8 backend-command architecture rather than letting model prose advance state.

### G4 — Separate tools, workflow capabilities, and authority

Vault basis: `deeptutor-research.md` lines 32–36 distinguishes callable tools from multi-step
capabilities and privileged installation from per-user execution.

Harness application:

- tools: research fetch, artifact rendering, source inspection;
- workflows: compile course, run lesson, grade attempt, create parent pack, import/export;
- policy: what the current user, recipe, course, and approved pack permit.

An installed pack never acquires tool or workflow authority. This is also the security boundary
for community content.

### G5 — Match activity type to the target evidence

Vault basis: `game-designer-research.md` lines 30–46 points to a production/retrieval/
comprehension task taxonomy and examples including listening, shadowing, dictation, reading,
and discrimination tasks. The detailed taxonomy itself is unavailable here.

Harness application (our normalized model, not an unverified reproduction of E1/E2/E3):

| Evidence target | Suitable activity | Does not substitute for |
|---|---|---|
| recall/retrieval | cold answer, varied flash prompt, reconstruction | explanation or production in a new context |
| comprehension | explain relationship, choose interpretation, identify error | unassisted recall or real-world performance |
| production | write/speak/create within declared constraints | recognition of the correct option |
| discrimination | distinguish similar forms/registers/procedures | broad conceptual mastery |
| procedure | ordered simulation + self-reported physical verification | independently verified physical completion |
| transfer | novel situation using the same objective | repeated near-identical check |

Each rubric declares its evidence target so a polished answer in the wrong modality cannot pass
as equivalent learning. This is subject-independent; Japanese is only one consumer.

### G6 — Human review is a separate lens, not another generator

Vault basis: `humanifier-research.md` lines 5–13 and 26–27 describes independent review for
human comprehension, native-language naturalness, cultural fit, tone/flow, and parent/child
needs, producing SHIP/FIX/BLOCK without rewriting the learning mechanics.

Harness application:

- separate generation from review;
- review lenses are **comprehension/accessibility**, **domain naturalness**, **cultural/context
  fit**, **tone/cognitive load**, and **operator usability**;
- reviewer output identifies concrete defects and owning fields; it does not silently rewrite
  state or rubric;
- domain-naturalness review may use an appropriate model/persona, but must not be labelled a
  native-speaker or expert review unless a real qualified human did it;
- generated packs show automated-review vs human-review status separately.

### G7 — Treat media and voice as task requirements, not learning styles

Vault basis: `JP-Game-OSS-Quality-Stack.md` lines 10–21 and 44–47 lists offline Japanese TTS,
pronunciation analysis, accessible Japanese fonts/furigana, and caveats including voice
auditioning. `game-designer-research.md` names listening, dictation, shadowing, and pitch tasks.

Harness application:

- listening discrimination needs audio; character/form recognition needs legible text/visuals;
  pronunciation demonstration needs an appropriate voice/transcript;
- narration is not pronunciation assessment;
- every media asset has text/alternative and an offline/degraded path;
- voice/model choices are auditioned on the actual target language and content, not selected
  from generic quality claims;
- no “visual learner/auditory learner” diagnosis.

### G8 — Review source freshness and downstream impact

Vault basis: `game-designer-research.md` lines 78–92 calls native-usage findings live sync-flag
territory and says dependent specs must be re-checked when findings change.

Harness application:

- objective/lesson/rubric/media records retain source and spec versions;
- pack/source updates produce an impact list, not automatic migration;
- affected checks become stale pending review while existing evidence remains historical;
- imported learners choose keep-working-version or explicitly migrate after compatibility is
  supported.

### G9 — Design for honest, low-friction evidence capture

Vault basis: `humanifier-research.md` lines 16–22 names weighted kid input, emotion coaching,
mistake tolerance, and co-viewing research; the canonical findings are unavailable here.
`Hermes Memory Mirror.md` line 27 records a later playtesting lesson: concurrent teaching can
contaminate observed behavior, and parent observation is an instrument.

Harness application:

- do not count guided/co-viewed performance as independent evidence;
- label assistance and observer source;
- wrong answers invite retry/change of representation without shame;
- avoid using inferred emotion as a reliable grading signal;
- Parent mode records `parent_reported` observations and does not turn them into automated
  diagnoses;
- all fixed retry/session caps are workload controls, not scientifically optimal prescriptions.

### G10 — Make artifact quality executable and accessible

Vault basis: `Design & Render One-Shot Quality...` lines 27–36 lists measured accessibility and
interaction checks, while lines 38–59 documents missing/contradictory source material and the
need to avoid flat enforcement. `JP-Game-OSS-Quality-Stack.md` lists universal-design Japanese
fonts and accessibility tooling.

Harness application:

- native components and typed render templates over unconstrained “make it beautiful” prose;
- keyboard/focus/contrast/text scaling/reduced-motion checks;
- text alternatives and selectable PDF text;
- CJK-specific line breaking/font fallback/furigana support in the Japanese pack;
- verify actual rendered outputs, not merely schema-valid source;
- do not import every numeric UI heuristic as universal law.

---

## 2. Japanese demo/personal classroom

### Personal configuration, not universal policy

`Hermes Memory Mirror.md` line 13 states: all Japanese text must include romaji because Keaton
is L0 JP. Therefore Keaton's personal Japanese classroom defaults to:

- Japanese text + romaji + English meaning at beginner level;
- furigana where useful, with the ability to hide it for cold retrieval;
- romaji as a scaffold that fades independently of conceptual evidence;
- no romaji-only evidence for Japanese reading ability;
- standard polite register first unless a specific context requires otherwise;
- Japanese-capable fonts and correct line breaking/furigana rendering.

This is a learner-specific accessibility/scaffolding choice. Other Japanese packs can set a
different script policy.

### Domain review layers

The readable JP-Lingo notes motivate four Japanese-specific checks:

1. **Natural usage:** does the expression sound plausible in the stated relationship, setting,
   register, and era—not merely translate literally?
2. **Register/addressee:** who is speaking to whom, and what is their relationship? The vault
   specifically names per-addressee register and uchi/soto review.
3. **Cultural fit:** avoid stereotypes and unsourced claims about what “Japanese people” do;
   distinguish regional/generational/contextual variation.
4. **Script/sound:** render Japanese script, romaji/furigana, and audio consistently; do not
   infer pronunciation correctness from text or generic TTS quality.

These are review lenses, not claims that an LLM can certify native naturalness. Sources and
variation remain visible.

### Native-usage answer envelope

For questions such as “How do I say I love you?”, the harness should ask/require context before
choosing one answer:

```json
{
  "speaker": {"proficiency": "L0", "age_register": "adult"},
  "addressee": "partner|family|friend|other",
  "relationship": "new|established|unspecified",
  "setting": "private|public|text_message|other",
  "intent": "declaration|appreciation|affection|playful",
  "directness": "indirect_preferred|neutral|direct",
  "region_register": "standard_polite|casual|other",
  "requested_media": ["text", "audio"]
}
```

If the user does not know, the tutor offers a small number of contrasting contexts rather than
silently inventing one. Each alternative explains speaker/addressee, nuance, directness,
naturalness confidence, and source support. It must not dump every possible translation.

The actual Japanese wording, usage claims, and citations for the demo pack still require fresh
research. This addendum intentionally does not supply or validate those claims.

### Demo task progression

The following is a **pack design**, not a claim of an optimal Japanese curriculum:

1. **Comprehension/discrimination:** distinguish affection from a direct romantic declaration
   in two short contexts.
2. **Guided selection:** choose an appropriate expression for a specified addressee/intent and
   explain the contextual cue.
3. **Cold retrieval:** produce or select the expression in a new, non-identical context without
   the prior answer visible.
4. **Listening (if audio available):** distinguish the target phrase from a contrasting phrase;
   text fallback uses script/romaji only for a different evidence target and labels the missing
   listening evidence.
5. **Transfer:** respond to a new relationship/setting and justify why the register changes or
   stays the same.
6. **Delayed review:** a later varied item, not the same card repeated immediately.

A corrected misconception uses a new item targeting the same concept. A successful repeated
answer to one item does not display “fluent” or durable mastery.

### Demo grading fixture

Use one closed-form/context-selection check for the reliable contest path plus one optional
open explanation to demonstrate bounded aux grading. The fixture includes:

- expected answer and context stored only in the backend envelope;
- acceptable alternatives with their contextual limits;
- a wrong direct-literal answer that exposes the context error;
- an unexpected but valid answer that must not be failed for phrasing alone;
- an irrelevant answer and an answer asking for clarification;
- an answer-injection attempt that must not change the rubric or transition;
- hinted and answer-shown variants that cannot count as cold evidence.

The demonstration shows evidence/state transitions, not “Japanese mastered.”

### Media choices

- Text: Japanese script, romaji/furigana, English explanation, proper CJK rendering.
- Audio: a clearly identified synthetic voice speaking the exact reviewed phrase, with text
  transcript and an audition step. It is a listening model, not a native-speaker certification.
- Visual: a simple deterministic relationship/context map (speaker → addressee → intent →
  register) rather than an image-generated “Japanese people in love” stereotype.
- Offline: the imported pack retains its reviewed text/audio and works without regeneration.

### Parent/Japanese intersection

Parent mode is not a child Japanese chatbot. A parent can generate a short Japanese activity
pack with age/reading level/materials, romaji or furigana policy, a parent script, a listen-
together track, and an observation checklist. The parent approves the actual pages, answers,
audio transcript, and activity instructions before export.

---

## 3. Changes to the implementation specification

The generic mechanisms above map to v8 as follows:

- §8: add expected-answer isolation, pre-lesson key audit, evidence-target taxonomy, and layered
  L1/L2/L3 evidence views;
- §6/§7: retain single backend command authority and event contracts;
- §9/§10: add source-impact invalidation and task-mandated media review;
- §11: imported pack content remains untrusted and cannot write the policy file;
- §13: add independent human-sense review and evidence-target display, not a persona dashboard;
- §15: implement Japanese as a pack/policy configuration, not a second tutor engine;
- acceptance: test romaji fading vs reading evidence, hidden answer keys, cold vs assisted
  attempts, source-change invalidation, and text-only fallbacks.

No core architecture change is required. The vault research strengthens the same kernel rather
than adding another parallel system.

## 4. Remaining research work before authoring the Japanese demo pack

1. Re-locate or restore canonical JP-Lingo findings if a readable checkout exists elsewhere;
   do not cite unavailable files as reviewed evidence.
2. Verify the chosen phrase variants with appropriate Japanese sources and, ideally, qualified
   human review. Label automated naturalness review honestly if no human reviewer is used.
3. Verify current font/audio licenses and audition the selected voice on the exact demo phrases.
4. Validate the grading fixture with correct, contextually wrong, unexpected-valid, multilingual,
   and adversarial inputs; publish per-case outcomes, not a generalized Japanese-grader claim.
5. Keep personal romaji/script preference separate from the community pack's configurable
   defaults and document why.

The vault is now incorporated as evidence and design input, not merely referenced as a source
of generic prompt text.
