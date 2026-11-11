"""CP-015g/D1-F2: an undeclared subject domain is resolved from the goal, never from the locale.

The defect these tests pin: a course created with a goal and a locale but no ``subject_domain``
used to resolve to ``language``. A hands-on goal ("set up a small backyard telescope and find and
observe the moons of Jupiter") was therefore handed a language-course curriculum brief and
language-course research queries, and the plan author had to ignore both. The resolution now
happens in exactly one place — ``curriculum.resolve_domain`` — and every consumer (the brief, the
research queries, the plan prompt, the validator payload and the run record) calls it, so the
profile the research uses and the profile the author is told about are the same profile.

The required cases:

* undeclared domain + hands-on goal;
* undeclared domain + language goal;
* declared domain (unchanged);
* a parent brief.
"""

from __future__ import annotations

import json
import unittest

from coursebook import curriculum, generation, research

TELESCOPE = (
    "Set up a small backyard telescope and find and observe the moons of Jupiter on a clear night"
)
SPANISH = "Learn Spanish to order food in Mexico City"
VAGUE = "Plan a calm bedtime routine"


def unavailable_run() -> research.ResearchRun:
    return research.ResearchRun(status="unavailable", queries=[], sources=[], reason="test seam")


class _PageSeam:
    """A bounded search/extract seam: one fetchable page per query, no network."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, limit: int) -> list[dict]:
        self.queries.append(query)
        slug = "-".join(query.lower().split())[:48] or "q"
        return [
            {"url": f"https://example.org/{slug}/{index}", "title": query, "description": "s"}
            for index in range(limit)
        ]

    def fetch(self, url: str, max_chars: int) -> dict:
        return {
            "url": url,
            "title": url,
            "content": "A page about setting up and using a small telescope. " * 10,
            "published_at": None,
        }


class UndeclaredHandsOnGoalTest(unittest.TestCase):
    def test_the_brief_is_a_procedure_brief_not_a_language_brief(self) -> None:
        brief = curriculum.curriculum_brief(
            domain=None, locale="en-US", level=None, recipe="casual", goal=TELESCOPE
        )
        self.assertEqual(brief["domain"], "technical_procedure")
        self.assertEqual(brief["profile"], "task_analysis_and_safety")
        self.assertEqual(brief["domain_source"], "inferred")
        self.assertIsNone(brief["declared_subject_domain"])
        self.assertNotIn("language", brief)
        self.assertIn("worked procedure", brief["procedure"]["order"])

    def test_the_research_queries_are_not_language_queries(self) -> None:
        queries = curriculum.curriculum_queries(TELESCOPE, domain=None, locale="en-US")
        joined = " | ".join(queries).lower()
        self.assertIn("prerequisite knowledge learning progression", joined)
        self.assertNotIn("vocabulary", joined)
        self.assertNotIn("high frequency", joined)

    def test_the_research_pass_uses_the_same_profile_as_the_brief(self) -> None:
        brief = curriculum.curriculum_brief(
            domain=None, locale="en-US", level=None, recipe="casual", goal=TELESCOPE
        )
        budget = research.budget_for(depth="working", scope="short")
        queries = research.derive_queries(
            TELESCOPE,
            recipe="casual",
            dials={"depth": "working"},
            locale="en-US",
            subject_domain=None,
            max_queries=budget.max_queries,
        )
        self.assertEqual(brief["domain"], "technical_procedure")
        # The procedure qualifier is derived from the same resolved domain, not the locale.
        # This asks at the budget the research pass actually gets (short/working = 6), not at
        # ``derive_queries``' smallest default cap of 4: CP-015a puts the qualifier query after the
        # capability clauses and truncates it first, so a 4-query cell that names three
        # capabilities legitimately holds no qualifier. The live-run test below pins the same claim
        # through ``run_research`` at the real budget.
        self.assertTrue(
            any("official procedure steps safety limits" in query for query in queries), queries
        )
        self.assertFalse(any("Japanese" in query or "vocabulary" in query.lower() for query in queries))

    def test_the_recorded_research_ledger_holds_no_language_query(self) -> None:
        # The CP-015g live run's own brief: goal, recipe, locale and a depth dial, no domain.
        seam = _PageSeam()
        run = research.run_research(
            TELESCOPE,
            recipe="casual",
            dials={"depth": "working"},
            locale="en-US",
            scope="short",
            search=seam,
        )
        recorded = [str(entry.get("query") or "") for entry in run.queries]
        self.assertTrue(recorded)
        self.assertTrue(any("official procedure steps safety limits" in q for q in recorded), recorded)
        self.assertFalse(any("high frequency vocabulary" in q.lower() for q in recorded), recorded)
        self.assertFalse(any("curriculum high frequency" in q.lower() for q in recorded), recorded)

    def test_the_plan_prompt_and_validator_see_the_inferred_domain(self) -> None:
        planning = generation.build_plan_request(
            goal=TELESCOPE,
            recipe="casual",
            dials={"depth": "working"},
            locale="en-US",
            research_run=unavailable_run(),
            scope="short",
        )
        payload = json.loads(planning.input_text)
        self.assertEqual(payload["subject_domain"], None)
        self.assertEqual(payload["curriculum"]["domain"], "technical_procedure")
        self.assertEqual(payload["curriculum"]["domain_source"], "inferred")
        # The author is told the profile as inferred, not as a declaration.
        self.assertIn("Subject domain: technical_procedure (inferred from the goal", planning.instructions)
        self.assertNotIn("particles, copulas and verb endings", planning.instructions)

        validation = generation.build_plan_validation_requests(
            plan={"plan_schema": generation.PLAN_SCHEMA_V2_NAME},
            goal=TELESCOPE,
            recipe="casual",
            dials={"depth": "working"},
            locale="en-US",
            research_run=unavailable_run(),
            scope="short",
        )[0]
        validated = json.loads(validation.input_text)
        # Author and validator are handed one brief, field for field.
        self.assertEqual(validated["curriculum"], payload["curriculum"])


class UndeclaredLanguageGoalTest(unittest.TestCase):
    def test_a_named_target_language_with_a_locale_resolves_to_language(self) -> None:
        brief = curriculum.curriculum_brief(
            domain=None, locale="es-MX", level=None, recipe="casual", goal=SPANISH
        )
        self.assertEqual(brief["domain"], "language")
        self.assertEqual(brief["profile"], "frequency_and_communication")
        self.assertEqual(brief["domain_source"], "inferred")
        self.assertEqual(brief["language"]["target_language"], "Spanish")

    def test_the_language_queries_follow_the_inferred_domain(self) -> None:
        queries = curriculum.curriculum_queries(SPANISH, domain=None, locale="es-MX")
        joined = " | ".join(queries)
        self.assertIn("Spanish beginner curriculum high frequency vocabulary grammar order", joined)

    def test_a_language_goal_without_a_locale_stays_general_and_says_why(self) -> None:
        resolved = curriculum.resolve_domain(goal=SPANISH, domain=None, locale=None)
        self.assertEqual(resolved["domain"], "general")
        self.assertEqual(resolved["source"], "default")
        self.assertEqual(resolved["inferred_from"], "goal_language_without_locale")
        self.assertIn("no locale", resolved["note"])

    def test_a_named_orthography_is_a_language_goal(self) -> None:
        # A Japanese L0 brief declares the locale and says what to learn; naming the script is
        # naming the subject, so the goal must not resolve to `general` just because the language
        # is not spelled out.
        for goal in (
            "Learn to read hiragana",
            "Practice reading kana",
            "Memorise 100 kanji",
            "Learn romaji before kana",
        ):
            resolved = curriculum.resolve_domain(goal=goal, domain=None, locale="ja-JP")
            self.assertEqual(resolved["domain"], "language", goal)
            self.assertEqual(resolved["source"], "inferred", goal)
            self.assertEqual(resolved["inferred_from"], "goal_language", goal)
            self.assertEqual(resolved["target_language"], "Japanese", goal)

    def test_the_metalanguage_of_a_language_course_is_a_language_goal(self) -> None:
        for goal in (
            "Improve my vocabulary for the SAT",
            "Learn grammar rules for formal writing",
            "Practise Spanish pronunciation",
        ):
            resolved = curriculum.resolve_domain(goal=goal, domain=None, locale="en-US")
            self.assertEqual(resolved["domain"], "language", goal)

    def test_a_named_orthography_still_needs_a_locale(self) -> None:
        resolved = curriculum.resolve_domain(goal="Learn to read hiragana", domain=None, locale=None)
        self.assertEqual(resolved["domain"], "general")
        self.assertEqual(resolved["inferred_from"], "goal_language_without_locale")


class LanguageIsNeverTheOmissionDefaultTest(unittest.TestCase):
    def test_a_locale_alone_does_not_make_a_language_course(self) -> None:
        for locale in ("ja-JP", "es-MX", "en-US"):
            resolved = curriculum.resolve_domain(goal=VAGUE, domain=None, locale=locale)
            self.assertEqual(resolved["domain"], "general", locale)
            self.assertEqual(resolved["source"], "default", locale)
            brief = curriculum.curriculum_brief(
                domain=None, locale=locale, level=None, recipe="casual", goal=VAGUE
            )
            self.assertNotIn("language", brief, locale)
            self.assertNotIn(
                "vocabulary",
                " ".join(curriculum.curriculum_queries(VAGUE, domain=None, locale=locale)).lower(),
                locale,
            )

    def test_a_subject_about_a_language_is_not_a_language_course(self) -> None:
        # H-44's warning: "read Spanish colonial history" must not become a Spanish course.
        resolved = curriculum.resolve_domain(
            goal="Read Spanish colonial history", domain=None, locale="es-MX"
        )
        self.assertNotEqual(resolved["domain"], "language")
        self.assertEqual(resolved["domain"], "general")

    def test_building_a_language_tool_is_not_a_language_course(self) -> None:
        resolved = curriculum.resolve_domain(
            goal="Build a language learning app with spaced repetition", domain=None, locale="en-US"
        )
        self.assertEqual(resolved["domain"], "general")
        self.assertEqual(resolved["source"], "default")

    def test_learning_a_foreign_language_without_naming_one_needs_a_locale(self) -> None:
        resolved = curriculum.resolve_domain(
            goal="Learn a foreign language for travel", domain=None, locale="it-IT"
        )
        self.assertEqual(resolved["domain"], "language")
        self.assertEqual(resolved["inferred_from"], "goal_language")


class DeclaredDomainIsUnchangedTest(unittest.TestCase):
    def test_a_declared_domain_wins_over_the_goal_text(self) -> None:
        resolved = curriculum.resolve_domain(goal=TELESCOPE, domain="mathematics", locale="en-US")
        self.assertEqual(resolved["domain"], "mathematics")
        self.assertEqual(resolved["source"], "declared")
        self.assertEqual(resolved["declared_subject_domain"], "mathematics")
        brief = curriculum.curriculum_brief(
            domain="mathematics", locale="en-US", level=None, recipe="casual", goal=TELESCOPE
        )
        self.assertEqual(brief["profile"], "prerequisite_and_representation")
        self.assertEqual(brief["domain_source"], "declared")

    def test_the_alias_table_still_canonicalises_a_declared_spelling(self) -> None:
        resolved = curriculum.resolve_domain(goal=TELESCOPE, domain="repair", locale="en-US")
        self.assertEqual(resolved["domain"], "technical_procedure")
        self.assertEqual(resolved["source"], "declared")

    def test_a_declared_language_course_keeps_its_declared_provenance(self) -> None:
        resolved = curriculum.resolve_domain(goal=SPANISH, domain="language", locale="es-MX")
        self.assertEqual(resolved["domain"], "language")
        self.assertEqual(resolved["source"], "declared")
        self.assertEqual(resolved["target_language"], "Spanish")


class DeclaredSubjectInOwnWordsTest(unittest.TestCase):
    """CREATE-7: the subject box is free text, so an exact alias cannot be the only door.

    The create form asks for the subject "in your own words" and its own examples include
    `Spanish`, `statistics` and `electrical safety`. A declared subject that missed the exact
    alias table fell to the generic profile, so a repair course was researched and authored as
    if it were a generic one. The three phrases below are the audit's, plus a subject that must
    stay generic: no stem may claim a topic the product has no profile for.
    """

    def test_the_forms_own_examples_resolve(self) -> None:
        for declared, expected in (
            ("auto repair", "technical_procedure"),
            ("Spanish", "language"),
            ("electrical safety", "technical_procedure"),
        ):
            resolved = curriculum.resolve_domain(goal="Do the thing", domain=declared, locale="en-US")
            self.assertEqual(resolved["domain"], expected, declared)
            # The profile is the declared one; nothing was inferred from the goal.
            self.assertEqual(resolved["source"], "declared", declared)

    def test_a_subject_no_profile_names_stays_generic(self) -> None:
        for declared in ("astronomy", "poetry", "marine biology"):
            resolved = curriculum.resolve_domain(goal="Do the thing", domain=declared, locale="en-US")
            self.assertEqual(resolved["domain"], "general", declared)
            self.assertEqual(resolved["source"], "declared", declared)

    def test_case_a_plural_and_word_order_do_not_decide_it(self) -> None:
        for declared in (
            "AUTO REPAIR",
            "auto repairs",
            "repair auto",
            "electrical-safety",
            "safety, electrical",
        ):
            self.assertEqual(
                curriculum.resolve_domain(goal="Do the thing", domain=declared, locale="en-US")["domain"],
                "technical_procedure",
                declared,
            )
        self.assertEqual(
            curriculum.resolve_domain(goal="Do the thing", domain="languages", locale="en-US")["domain"],
            "language",
        )

    def test_the_head_of_the_phrase_decides(self) -> None:
        # A declared "Spanish colonial history" is a history course, not a language course:
        # the last word that names a domain is the one the phrase is about.
        resolved = curriculum.resolve_domain(
            goal="Do the thing", domain="Spanish colonial history", locale="es-MX"
        )
        self.assertEqual(resolved["domain"], "history")

    def test_the_single_word_alias_table_still_answers(self) -> None:
        for declared, expected in (
            ("repair", "technical_procedure"),
            ("technical", "technical_procedure"),
            ("math", "mathematics"),
            ("statistics", "mathematics"),
            ("grammar", "grammar"),
        ):
            self.assertEqual(
                curriculum.resolve_domain(goal="Do the thing", domain=declared, locale="en-US")["domain"],
                expected,
                declared,
            )


class ParentBriefTest(unittest.TestCase):
    def test_a_parent_brief_for_a_hands_on_goal_gets_the_procedure_profile(self) -> None:
        request = generation.build_plan_request(
            goal=TELESCOPE,
            recipe="parent",
            dials={"depth": "working"},
            locale="en-US",
            research_run=unavailable_run(),
            parent_brief={"desired_pages": 3},
            scope="short",
        )
        payload = json.loads(request.input_text)
        self.assertEqual(payload["curriculum"]["domain"], "technical_procedure")
        self.assertEqual(payload["curriculum"]["domain_source"], "inferred")
        self.assertEqual(payload["parent_brief"]["desired_pages"], 3)
        self.assertNotIn("particles, copulas and verb endings", request.instructions)
        self.assertIn("Subject domain: technical_procedure (inferred from the goal", request.instructions)


if __name__ == "__main__":
    unittest.main()
