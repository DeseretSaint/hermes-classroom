# CP-015g/D1-F2 — an undeclared subject domain is resolved from the goal, never from the locale

Card: `t_2c045efc`. Branch `wt/cp-015g-domain-default`, based on `wt/cp-015g-d1-f1-authoring`
(`e728fbe9`, i.e. `origin/master` `58ce4d85` plus CP-015g/D1 and D1-F1). Not rebased onto the later
master that carries D3, and not pushed. The D3 merge and the integration decision are not this
card's.

## The defect

A course created with a goal and a locale but no `subject_domain` resolved to the locale default,
`language`. The hands-on goal in `docs/cp015g-d1-f1/` therefore received a language-course
curriculum brief (`target_language`, script order, frequency guidance) and language-course research
queries; the plan author had to ignore both. D1-F1 worked around the brief half by typing the
performance requirement from the goal text only.

## The decision

One resolver, `curriculum.resolve_domain(goal=…, domain=…, locale=…)`, returns the resolved
`domain`, its `source` (`declared` / `inferred` / `default`), the declared inputs, the target
language, and — for an inferred or default answer — `inferred_from` and a human `note`.

| brief declares | goal | resolved | source |
|---|---|---|---|
| a domain | anything | that domain (alias table honoured) | `declared` |
| nothing | a performed physical act ("set up a telescope and find and observe the moons") | `technical_procedure` | `inferred` |
| nothing | a named target language plus learning/use, with a locale | `language` | `inferred` |
| nothing | a named orthography (`hiragana`, `kanji`, `kana`, `romaji`), or a study verb governing `vocabulary` / `grammar` / `pronunciation`, with a locale | `language` | `inferred` |
| nothing | a language goal with no declared locale | `general`, with a note saying a language course needs a declared target language | `default` |
| nothing | nothing (a vague goal, a locale alone) | `general`, with a note saying the domain is the default | `default` |

`language` is not reachable by omission: the locale is the language of delivery, not the subject.
A content frame outranks the language words — "read Spanish colonial history" and "the art of kanji
calligraphy" stay non-language, and "build a language learning app" stays `general`.

## What changed

`coursebook/curriculum.py`

* `resolve_domain` and `DOMAIN_SOURCES`; the physical-act detector is D1-F1's
  `performance_requirement`, unchanged and still goal-only.
* `curriculum_brief` resolves through it and carries `domain`, `domain_source` and
  `declared_subject_domain`; the `language` block appears only for a resolved language course.
* `curriculum_queries` derives the subject qualifier from the same resolution.

`coursebook/research.py`

* `derive_queries` resolves the same way from the same goal; the deep-pass reference query follows
  the resolution, not a bare `subject_domain or None`.

`coursebook/generation.py`

* `_domain_provenance` records the resolution (`source`, `inferred_from`, `note`); only the
  `default` note reaches `warnings`.
* `build_plan_request`, both plan instruction builders and the plan-validation payload use the same
  resolution, so the author and the validator are handed one brief; an inferred domain is stated to
  the author as inferred.
* The plan-time capability decision is computed for the resolved domain, not the declared one.
* Prompt labels: `plan-prompt.v14`, `plan-prompt.v15`, `validation-prompt.v7` (`docs/GENERATION.md`).

`docs/COURSE-BLUEPRINT.md` §15 freezes the resolution and records why it replaced H-44's
"never infer" choice. `docs/GENERATION.md` carries the labels.

## Evidence (all run on this tree, `14a9b5a8`)

```
$ python3 -m unittest tests.test_cp015g_domain_default
Ran 19 tests ... OK
$ python3 -m unittest tests.test_curriculum tests.test_capability_policy tests.test_policy_threading \
    tests.test_policy_integration tests.test_media_plan tests.test_scope_copy \
    tests.test_validation_shape_repair tests.test_research_floor tests.test_generation \
    tests.test_cp015g_d1_f1_authoring tests.test_cp015g_domain_default
Ran 232 tests in 5.990s ... OK
$ python3 -m unittest discover -s tests -t .
Ran 3783 tests in 930.759s ... OK (skipped=11)
$ python3 scripts/check-docs-truth.py --skip-tests
docs-truth: PASS   (prompt labels: lesson-prompt.v10, plan-prompt.v14, plan-prompt.v15,
                    unit-sections-prompt.v1, validation-prompt.v7)
$ PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
overall: PASS  (3/3 scenarios)
$ PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py --verify
packet: FRESH — every evidence file and harness input matches manifest.json
```

`check-docs-truth.py` was run with `--skip-tests` (its document pins); the suite it would have run
is the `discover` run above, on the same tree.

## What this card did not change

* The lesson stage still resolves an undeclared domain through `policy._normalise_domain`, so a
  telescope lesson is gated as a language lesson. Filed as `t_c23d633c` (lesson capability) and
  outside this card's boundary.
* `performance_requirement` keeps its act vocabulary. A hands-on goal whose act is outside it
  ("bake sourdough bread", "change a car tyre") resolves to `general` — the safe direction, and
  never `language` — because the class of goals this card must not get wrong is affected by the
  omission default, and `general` is not.
* The Desktop half still sends `goal` and `recipe` only; it does not have to change for this fix.

## Addendum: the integrated stack, not the branch

The measurements above were taken on the D1-F2 branch (`14a9b5a8`). Three cards' work landed
together — D1-F2's domain resolution and its unverified-claim rule, the source-body excerpt fix,
and the CP-015a clause-query correction that made the first two agree — so the numbers and prompt
labels this note records were superseded by the merge itself: the labels are now
`plan-prompt.v21`, `plan-prompt.v22` and `validation-prompt.v12` (`docs/GENERATION.md` is the
authority), and the suite on the rebased stack over current master is

```
$ python3 -m unittest discover -s tests -t .
Ran 4015 tests in 1445.315s ... OK (skipped=12)
```

The clause-query correction matters for this note's claim: with the domain now inferred from the
goal, `research.derive_queries` treated the inferred qualifier as declared and joined it onto the
capability clauses, which pushed those clauses out of a short depth cell. `bake with steam`
stopped reaching the ledger and `test_cp015_goal_coverage` failed on three cells. The rule now
follows `resolution["source"]`: a declared domain outranks the recipe question and the clauses
join it; an inferred domain only shapes the base query.
