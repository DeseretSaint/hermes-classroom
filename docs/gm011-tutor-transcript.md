# GM-011 tutor transcript (real backend, scripted host LLM)

The profile, migrations, commands, lesson document and citation resolver are real. The provider is a scripted fixture bound through the production seam; no network call was made and no model output is claimed as a live answer.

- course: `crs_158b50e773274ed1864cda9138774514` objective: `obj_1bc2475fbe0d4bc09ac03b01da97f0d9`
- lesson run: `run_c63b9f886cb4474ba974158ba09c0fc9` thread: `thr_cb85fd49ed2d435090a898dff9c8487d`
- lesson blocks: `blk_882912e55aeb3598bcf6, blk_ab26eae8e578bba4e013`
- context secret present: `False`
- context includes the reference/rubric keys: `False`

## 1. A cited answer

> The lesson walks through glucose breakdown step by step.

Citations as returned (the invented `blk_does_not_exist` was omitted):

- `block:blk_882912e55aeb3598bcf6` — Cells release usable energy by breaking down glucose in a series of steps. Each step hands a small amount of energy to the next carrier.
- `source:src_respiration` — Cell respiration primer

State: `answered`; assist: `{"available": true, "evidence_class": "hinted", "kind": "hint_request", "label": "Hint", "layer": 1, "policy": "available"}`

## 2. The model tries to reveal the sealed answer while the check is open

> That would give away the answer while the check is open. Ask for a hint instead — the lesson's steps are still here to work through.

State: `answer_withheld`; citations: `0`; the sealed answer appears in the stored turn: `False`

## 3. A hint that does not reveal the answer

> Start with the first step in the lesson: what molecule does the cell break down before any energy is released?

State: `answered` (the hint was a normal answer); assist policy `available`; no answer key appears in the hint: `True`

## Stored thread

1. **learner**: What happens to glucose?
2. **tutor**: The lesson walks through glucose breakdown step by step.
3. **learner**: Just tell me the answer.
4. **tutor**: That would give away the answer while the check is open. Ask for a hint instead — the lesson's steps are still here to work through.
5. **learner**: Give me a hint.
6. **tutor**: Start with the first step in the lesson: what molecule does the cell break down before any energy is released?

## Notes

- `tutor.ask` bumped the enrollment revision and wrote no attempt, transition or evidence row.
- The thread is bound to the lesson run, not to a host chat session.
- `withheld` is the named `answer_withheld` state; nothing leaky was persisted.
