# GM-014 fixture source and phrase provenance

This note records what the take-home fixture teaches, where each word came from, and the exact
lesson block the print pages are bound to. It is the provenance companion to
`bundled/homework/japanese-l0-mealtime/fixture.json` and `docs/visual-review/gm-014/`.

## Fixture lesson block binding

| field | value |
|---|---|
| source course id | `demo-japanese-l0-mealtime` |
| source objective id | `obj_mealtime_greetings` |
| source lesson version | `2026-11-09.1` |
| fixture lesson block hash | `sha256:349968476b95c2a750f302fb6b7dd7aa229868ab4cda22183c6c601947886f1a` |

The hash is `sha256` over the canonical JSON of the fixture's **own** `lesson` block (sorted keys,
UTF-8, no insignificant whitespace). `coursebook.homework_print.lesson_hash()` computes it, and
`tests/test_homework_content_print.py` recomputes it and fails if this note drifts. Changing a
printed form, reading, romaji or gloss changes the hash, so a pack can say which fixture lesson
text it printed.

`demo-japanese-l0-mealtime`, `obj_mealtime_greetings` and version `2026-11-09.1` name fields
inside this fixture. They do not name a live course: no course, objective or lesson with those
ids exists in this repository or in any branch, and the parent guide prints that plainly. The
binding says "these are the fixture's words", not "this reproduces an existing lesson".

## Phrases

### いただきます — reading いただきます — romaji `itadakimasu`

- Meaning recorded in the lesson: "thank you (for the meal just served); I receive (this meal)".
- Register recorded: polite (ます form; author's analysis). This is the author's grammatical
  analysis of the ます ending; **the cited Jisho entry does not label the phrase polite**. Only
  `ごちそうさまでした` carries a dictionary register label in this fixture.
- Use recorded: said before eating a meal.
- Sources:
  - Jisho.org, いただきます / 頂きます — https://jisho.org/search/itadakimasu — accessed 2026-11-09.
    Entry text: "thank you (for the meal just served); I receive (this meal) · Usually written
    using kana alone".
  - Cambridge Dictionary, いただきます — https://dictionary.cambridge.org/us/dictionary/japanese-english/%E3%81%84%E3%81%9F%E3%81%A0%E3%81%8D%E3%81%BE%E3%81%99
    — accessed 2026-11-09. Entry text: "a phrase said before eating expressing gratitude for the
    meal".

### ごちそうさまでした — reading ごちそうさまでした — romaji `gochisōsamadeshita`

- Meaning recorded in the lesson: "thank you for the meal; that was a delicious meal".
- Register recorded: polite (teineigo; Jisho label).
- Use recorded: said after finishing a meal.
- Source: Jisho.org, ごちそうさまでした / ご馳走様でした —
  https://jisho.org/search/%E3%81%94%E3%81%A1%E3%81%9D%E3%81%86%E3%81%95%E3%81%BE%E3%81%A7%E3%81%97%E3%81%9F
  — accessed 2026-11-09. Entry text: "thank you for the meal; that was a delicious meal; what a
  wonderful meal · Polite (teineigo) language · Usually written using kana alone".

## Household labels

| word | reading | romaji | gloss | source |
|---|---|---|---|---|
| ドア | ドア | doa | door | https://jisho.org/search/%E3%83%89%E3%82%A2 |
| まど | まど | mado | window | https://jisho.org/search/%E3%81%BE%E3%81%A9 |
| いす | いす | isu | chair | https://jisho.org/search/%E3%81%84%E3%81%99 |
| テーブル | テーブル | tēburu | table | https://jisho.org/search/%E3%83%86%E3%83%BC%E3%83%96%E3%83%AB |
| コップ | コップ | koppu | glass (drinking vessel); tumbler | https://jisho.org/search/%E3%82%B3%E3%83%83%E3%83%97 |
| ほん | ほん | hon | book | https://jisho.org/search/%E3%81%BB%E3%82%93 |

All six entries were read on Jisho.org on 2026-11-09. Each is labelled a common word at JLPT N5
except コップ, whose entry gives the gloss above without a level tag. The fixture does not promote
a label to a higher level and does not add a word that is not in this table.

## What is deliberately not claimed

- No native-speaker review is recorded and none is claimed.
- No claim is made that the greetings are universal, compulsory or religiously meaningful. The
  only use note is the one the cited entries give: before eating and after finishing a meal.
- No culture claim, etymology claim or regional variation claim is made beyond those entries.
- The phrases are demo fixture content for the print proof; they are not a published course and
  they do not enroll or grade anyone.
