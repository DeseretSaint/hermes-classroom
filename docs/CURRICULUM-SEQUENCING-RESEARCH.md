# Curriculum sequencing research and harness policy

Status: research note and implementation record, 2026-11-07. This is not a claim that the
harness has solved pedagogy. It records what the evidence supports, what it does not, and the
policy now passed into course generation.

## The claim under test

The starting intuition was: "a few hundred Japanese words make up over 80% of Japanese speech,
so a course should teach those first in a proper order."

Directionally, the intuition is right: high-frequency vocabulary is the correct first
investment, and a course should not be a random topic list. The numerical form is not supported
as stated for Japanese. "A few hundred" is not enough for 80% in the corpora below, and
"coverage" is not "comprehension."

## What the evidence says

### Japanese vocabulary coverage

| Source / corpus | ~500 items | ~1,000 | ~2,000 | Caveat |
|---|---:|---:|---:|---|
| Everyday Japanese, 21.4M words of subtitles + Tatoeba (Mindomax, 2026) | 76.7% | 82.1% | 86.9% | Corpus-based estimate, not a peer-reviewed frequency dictionary; includes particles and function words. |
| Written Japanese, BCCWJ-based summary (AJATT, citing BCCWJ) | — | ~75% | ~80% | Written text, not speech. |
| Matsushita (2012), General Learners' Vocabulary List, as cited by Rothville (2024) | — | — | ~85% of Japanese texts | The first 2,000 are still not enough for unsupported reading. |
| Japanese junior-high textbooks, 2,500 high-frequency types (JLTA Journal, 2024) | — | — | ~80% (2,500 types) | Textbook corpus, not everyday speech. |
| Sato (2014), BCCWJ short-unit words | — | — | — | 4,024 short-unit words were required for 87% of tokens; Japanese high-frequency share is lower than English. |

The practical answer: **the first ~1,000 items, not a few hundred, are the point where everyday
spoken Japanese crosses ~80% in the best-known corpus count**. Five hundred is closer to 77%.
Written Japanese needs considerably more: roughly 2,000 for ~80-85% of text and several
thousand more for comfortable reading.

### Coverage is not comprehension

A learner who knows 80% of the running words still meets one unknown word in five. The
comprehension literature puts useful reading at roughly 95% coverage, with 98% for comfortable
unsupported reading and incidental learning (Laufer, 1989; Hu & Nation, 2000; Nation, 2013).
Japanese researchers similarly discuss 93-96% for reading with some support (Matsushita, 2014;
Komori et al. as cited by Tamaoka, 2014). A course must not say "80% coverage means you
understand 80%."

### What the high-frequency items actually are

The most frequent Japanese items are largely **grammatical**: particles (は, の, を, に, が),
copulas and verb endings. In the Mindomax count the 30 most frequent items are 44.1% of all
words, and particles/endings alone are 47.8% of the stream. They are not a vocabulary list of
content words. Teaching them as isolated word cards is a design error; they must be taught as
grammar in context.

Kanji is a separate frequency problem. A newspaper-corpus study found the top 500 kanji cover
about 80% of kanji occurrences, but that is not 80% of words or of speech. Kana and
pronunciation come first; kanji should be introduced inside high-frequency words.

### Language pedagogy

- **Frequency principle.** High-frequency vocabulary should generally be learned before
  low-frequency vocabulary because it gives the largest comprehension return per item. Nation's
  English figures are about 3,000 high-frequency words for 80-90% of running words; the exact
  band is language- and corpus-dependent.
- **Four strands.** A balanced language course gives roughly equal time to meaning-focused
  input, meaning-focused output, language-focused learning and fluency development. Explicit
  language focus is about 25%, not the whole course (Nation, 2007; Nation interview, 2019).
- **Japanese beginner order (practitioner consensus, not a controlled trial):** pronunciation
  and kana early; core particles and polite sentence patterns; high-frequency vocabulary in
  context; kanji inside useful words; listening and speaking from the start. Sources such as
  Preply, Fluentera and Aaronsan agree on this shape, but they are teaching guides, not
  experimental evidence. The harness treats this as a default profile, open to the research
  sources it retrieves.
- **Retrieval and spacing.** Repeated retrieval beats rereading; spacing and interleaving
  improve retention, with supports fading over time. A curriculum should schedule review of
  core items, not teach them once.
- **Backward design and prerequisites.** Start from the performance the learner must be able
  to do, define acceptable evidence, then sequence instruction and prerequisite knowledge
  (Wiggins & McTighe; Gagné's learning hierarchies). For procedures, start with task analysis,
  safety and stop conditions. For concepts, move from a representation the learner can use to
  symbolic procedure and transfer.

## What the harness now does

The implementation is deliberately policy-level, not a hidden second model:

1. `coursebook/curriculum.py` builds a typed `curriculum` brief from the declared domain,
   locale, level and recipe. It names the sequence profile and the questions the plan must
   answer. It does not invent a syllabus.
2. `coursebook/research.py` adds two bounded curriculum queries for every non-survey,
   non-one-off course: how to teach/sequence the subject, and its prerequisites or (for a
   language) the target language's high-frequency vocabulary/grammar order. One-off briefs keep
   their faster bounded pass; a survey stays one query.
3. `coursebook/generation.py` passes that brief to both the plan author and the independent
   validator. The plan prompt now requires prerequisite-first sequencing, a why-now statement
   in each unit goal, no forward prerequisites, retrieval/review, and source-grounded coverage
   claims. Language courses get the coverage-is-not-comprehension, function-words-are-grammar,
   script, four-strands and 95-98% guidance. Procedure, mathematics and history get their own
   sequence profiles.
4. The independent validator judges sequence under `objective_alignment`: arbitrary order,
   prerequisite edges that do not match stated dependencies, or unsourced coverage claims are
   rejection reasons. This is a model judgment, not a deterministic proof; the deterministic
   unit-edge rules still run first.
5. `tests/test_curriculum.py` pins the brief, the query additions, the budget cap and the fact
   that both plan and validation requests receive the same policy. `audit/adversarial/harness-e2e`
   was regenerated for the new prompt versions and passes its three recorded scenarios.

## What is not solved

- There is **no bundled frequency lexicon**. The harness researches frequency and requires
  source-grounded claims, but the planner can still propose a weak vocabulary set. A real
  frequency-aware vocabulary sequencer needs a licensed/public word list, a level and modality
  policy, and a deterministic check that objectives cover the intended band. That is the next
  card, not a claim of this one.
- The sequence validator is an LLM judgment. It can be wrong; the deterministic prerequisite
  graph catches structural errors only.
- The Japanese coverage numbers vary by corpus, tokenisation, and whether function words are
  counted. No percentage should be shown to a learner without its source and modality.
- This does not turn Coursebook into an adaptive tutor. It makes the generated plan explain and
  defend its order; adaptation remains the existing state/evidence loop.

## Sources

- Mindomax, "Most Common Japanese Words: The Top 100, Ranked" (25 Oct 2026),
  https://www.mindomax.com/japanese-words — corpus counts and coverage table; industry estimate,
  not peer-reviewed.
- K. Rothville, "Developing a Japanese Vocabulary Levels Test for the Purposes of Extensive
  Reading," *Journal of Extensive Reading* 11(3), 2024,
  https://jalt-publications.org/content/index.php/jer/article/download/1221/118/8198 —
  Matsushita's 2,000-word ~85% estimate and 93-96% reading figures.
- S. Sato, "Text Readability and Word Distribution in Japanese," LREC 2014,
  https://aclanthology.org/L14-1505.pdf — 4,024 short-unit words for 87% of tokens; Japanese
  high-frequency share lower than English.
- "Developing a Receptive Vocabulary List for Japanese Junior High School Students," JLTA
  Journal 27 (2024), https://www.jstage.jst.go.jp/article/jltajournal/27/0/27_25/_pdf —
  2,500 high-frequency types at about 80% textbook coverage.
- I. S. P. Nation, "The Four Strands" and related vocabulary work; P. Nation interview (2019),
  https://www.wgtn.ac.nz/__data/assets/pdf_file/0003/1882470/2019-Nation-Interview.pdf —
  frequency principle, four strands, high-frequency first.
- B. Laufer (1989); M. Hu & I. S. P. Nation (2000); I. S. P. Nation (2006, 2013) — coverage
  thresholds; cite the primary works before using a percentage in learner-facing copy.
- Wiggins & McTighe, *Understanding by Design*; R. Gagné, learning hierarchies; Sweller,
  cognitive load; Cepeda et al. and Roediger & Karpicke on spacing/retrieval — curriculum
  sequencing and retrieval principles.
- Japanese beginner sequence guides (Preply, Fluentera, Aaronsan) — practitioner consensus for
  kana → particles → high-frequency vocabulary → kanji in words; not experimental evidence.
- BCCWJ / NINJAL and Tono, Yamazaki & Maekawa, *A Frequency Dictionary of Japanese* (2013) —
  corpus and frequency-list references; check licence before bundling any list.
