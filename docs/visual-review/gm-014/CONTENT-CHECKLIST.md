# GM-014 content checklist

One task, one target, one context, one success criterion. This checklist is applied per printed
task and is enforced by `tests/test_homework_content_print.py` against
`bundled/homework/japanese-l0-mealtime/fixture.json`.

| gate | rule | how it is checked |
|---|---|---|
| one target | exactly one target object per task; a label task chooses at most three lesson labels | `validate_fixture()` resolves `target_id` once; tests assert one resolved target |
| one context | one place-and-time sentence naming where and when | context must be a single non-empty sentence |
| one success criterion | one observable sentence the learner can judge | exactly one sentence; at least seven words |
| at most three steps | short, concrete actions | 1–3 steps, all non-empty |
| 3–10 minutes | small enough for a real evening | `estimated_minutes` integer in range |
| no generic task | not "practise for ten minutes" | criterion must name the phrase and the moment |
| no surveillance | no photo, recording, geolocation or location data | learner text word screen in the fixture validator and the test |
| no grade | completion is not a score, pass or mastery claim | completion is `self_reported` or `parent_reported`; learner text screen |
| no XP | print carries no XP, level or game progress | learner text screen; no XP in any template |
| no answer key on learner page | answer guide is a separate parent-only document | `render_documents()` returns distinct documents; test checks both |
| source-bound | every phrase, reading, romaji and gloss cites a recorded entry | every `source_ids` resolves; each source has https URL, access date and quote |
| no external send | printing is local | fixture checklist `external_send = false`; no network call in the print path |

## Per-task result

| task | target | context | success criterion | minutes | result |
|---|---|---|---|---|---|
| `hw_premeal` | いただきます (itadakimasu) | at the learner's table, before one meal today | said once, aloud, at the table, before eating | 3 | pass |
| `hw_postmeal` | ごちそうさまでした (gochisōsamadeshita) | at the learner's table, after one meal today | said once, aloud, at the table, after finishing | 3 | pass |
| `hw_labels` | three of the six sourced household labels | at home, on three objects passed daily | three labels placed; each said aloud on two days | 8 | pass |

## Not present anywhere in the print set

- No learner attempt, tutor turn, private observation or child data.
- No photo, recording, location or proof-of-completion requirement.
- No grade, score, percentage, mastery label or XP.
- No generated image used as a procedure, measurement or safety authority.
