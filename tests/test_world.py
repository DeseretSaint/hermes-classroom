"""GM-003: the world layer is policy, not a skin.

Policy selection is pure and deterministic; a technical procedure can never inherit the
Japanese field-atlas; and the anti-generic swap must reject art that would serve both.
"""

from __future__ import annotations

import unittest

from coursebook import api, executor, world
from coursebook import gm_contract
from tests.kernel_support import KernelCase
from tests.world_fixtures import (
    GENERIC_SWAP_BRIEF,
    HEAD_GASKET_BRIEF,
    JAPANESE_L0_BRIEF,
)


class WorldPolicyTest(unittest.TestCase):
    def test_world_grammar_deterministic(self) -> None:
        cases = {
            "language": "field_atlas",
            "technical_procedure": "workshop_manual",
            "mathematics": "instrument_board",
            "history": "archive_desk",
            "astronomy": "observatory",
            "cooking": "kitchen_table",
            "unknown_subject": "field_atlas",
        }
        for subject, expected in cases.items():
            intent = {"subject_domain": subject, "title": subject, "motifs": []}
            chosen = world.WorldPolicy.select(intent)
            self.assertEqual(chosen, expected, subject)
            # Deterministic: no randomness, no provider call, same answer every time.
            self.assertEqual(
                {world.WorldPolicy.select(intent) for _ in range(50)},
                {expected},
                subject,
            )
        # The selector reads a typed brief as well as a plain intent mapping.
        self.assertEqual(
            world.WorldPolicy.select(world.WorldBrief.from_mapping(JAPANESE_L0_BRIEF)),
            "field_atlas",
        )

    def test_head_gasket_never_field_atlas(self) -> None:
        grammar = world.WorldPolicy.select(HEAD_GASKET_BRIEF)
        self.assertEqual(grammar, "workshop_manual")
        self.assertNotEqual(grammar, "field_atlas")

        # A caller may still *ask* for any grammar; the policy refuses a decorative-only one
        # for a technical procedure instead of rendering lanterns over a torque sequence.
        with self.assertRaises(world.WorldPolicyViolation) as caught:
            world.WorldPolicy.assert_allowed(HEAD_GASKET_BRIEF, "field_atlas")
        self.assertEqual(caught.exception.reason, "technical_world_needs_service_grammar")

        record = world.grammar_record(grammar)
        self.assertGreaterEqual(len(record.subject_cues), 2)
        joined = " ".join(record.motifs).lower()
        self.assertIn("service bay", joined)
        self.assertIn("tool wall", joined)

    def test_world_style_swap_rejects_generic_art(self) -> None:
        japanese_grammar = world.WorldPolicy.select(JAPANESE_L0_BRIEF)
        gasket_grammar = world.WorldPolicy.select(HEAD_GASKET_BRIEF)
        self.assertNotEqual(japanese_grammar, gasket_grammar)

        # Correct grammars: the two worlds are genuinely different visual systems.
        self.assertEqual(
            world.anti_generic_problems(JAPANESE_L0_BRIEF, HEAD_GASKET_BRIEF), ()
        )

        # Swap the subject but keep the Japanese art: the same motifs cannot pass for cooking.
        self.assertEqual(world.WorldPolicy.select(GENERIC_SWAP_BRIEF), "kitchen_table")
        problems = world.anti_generic_problems(
            JAPANESE_L0_BRIEF, GENERIC_SWAP_BRIEF, grammar=japanese_grammar
        )
        self.assertIn("shared_motifs_survive_subject_swap", problems)
        self.assertIn("art_grammar_does_not_fit_swapped_subject", problems)

        # And the fixture pair really does share the motifs the test claims.
        self.assertGreaterEqual(
            len(
                set(JAPANESE_L0_BRIEF["motifs"])
                & set(GENERIC_SWAP_BRIEF["motifs"])
            ),
            2,
        )


class WorldPromptTest(unittest.TestCase):
    def test_world_prompts_are_textless(self) -> None:
        brief = world.WorldBrief.from_mapping(JAPANESE_L0_BRIEF)
        grammar = world.WorldPolicy.select(brief)
        prompt = world.build_prompt(brief, grammar, role="hero")
        negative = prompt.negative_prompt.lower()
        for forbidden in ("text", "letters", "numbers", "logos", "watermark", "ui chrome"):
            self.assertIn(forbidden, negative, forbidden)
        self.assertIn("textless", prompt.prompt.lower())
        self.assertIn("lantern district", prompt.prompt.lower())
        self.assertIn("quiet", prompt.prompt.lower())

        # Three style boards, three real directions, no repeated board.
        boards = world.build_style_boards(brief)
        self.assertEqual(len(boards), 3)
        self.assertEqual(len({board.prompt for board in boards}), 3)
        self.assertEqual(len({board.style_id for board in boards}), 3)
        for board in boards:
            self.assertIn("style board", board.prompt.lower())
            self.assertIn("lantern district", board.prompt.lower())

        # A kit covers hero, cover and one card per section, capped at six.
        kit = world.build_kit_prompts(
            brief, grammar, style_id=boards[0].style_id, style=boards[0]
        )
        roles = [item.role for item in kit]
        self.assertEqual(roles.count("hero"), 1)
        self.assertEqual(roles.count("cover"), 1)
        self.assertEqual(roles.count("section"), len(JAPANESE_L0_BRIEF["sections"]))
        capped = world.build_kit_prompts(
            brief, grammar, style_id=boards[0].style_id, style=boards[0], max_sections=6
        )
        self.assertLessEqual(
            [item.role for item in capped].count("section"), 6
        )

        # The model never sees an answer key, a check, a rubric or a learner attempt: they are
        # not fields of the brief, and a caller that smuggles them into a mapping cannot leak.
        leaky = dict(JAPANESE_L0_BRIEF)
        leaky["answer_key"] = "ANSWER-SECRET-9931"
        leaky["checks"] = [{"id": "c1", "reference": "ANSWER-SECRET-9931"}]
        leaky["rubric"] = {"criteria": ["ANSWER-SECRET-9931"]}
        for item in world.build_kit_prompts(
            world.WorldBrief.from_mapping(leaky), grammar, style_id=boards[0].style_id,
            style=boards[0],
        ):
            self.assertNotIn("ANSWER-SECRET-9931", item.prompt)

        # A technical world's prompts forbid a depicted procedure or measurement outright.
        gasket = world.WorldBrief.from_mapping(HEAD_GASKET_BRIEF)
        gasket_prompt = world.build_prompt(gasket, "workshop_manual", role="hero")
        self.assertIn("procedure", gasket_prompt.negative_prompt.lower())
        self.assertIn("torque", gasket_prompt.negative_prompt.lower())
        self.assertIn("service bay", gasket_prompt.prompt.lower())


class WorldHandlerMixin:
    """Call the world handlers the way ``dispatch`` will once the wire manifest carries them.

    ``cb.rpc`` v20 does not yet contain the four world methods (GM-001's intended fence), so the
    handlers are invoked directly with a contract-shaped envelope. The frozen GM manifest is the
    authority for their names and field tuples; the wire bump is an integration-card act.
    """

    def call(self, method: str, payload: dict, *, expected_revision: int, idempotency_key: str | None = None):
        envelope = {
            "operation_id": f"op-{method}-{idempotency_key or 'none'}",
            "expected_revision": expected_revision,
            "idempotency_key": idempotency_key,
        }
        return world.HANDLERS[method](payload, envelope)

    def call_ok(self, method: str, payload: dict, *, expected_revision: int, idempotency_key: str | None = None):
        return self.call(
            method, payload, expected_revision=expected_revision, idempotency_key=idempotency_key
        )[1]

    def call_err(self, method: str, payload: dict, *, expected_revision: int, idempotency_key: str | None = None) -> dict:
        try:
            self.call(
                method, payload, expected_revision=expected_revision, idempotency_key=idempotency_key
            )
        except api.RpcError as exc:
            return exc.error
        raise AssertionError(f"{method} unexpectedly succeeded")

    def read_world(self) -> dict:
        return self.call_ok("world.read", {"course_id": self.course_id}, expected_revision=0)

    # ``KernelCase`` helpers route through dispatch; until the wire manifest carries the world
    # methods, the same calls go straight to the handler with a contract-shaped envelope.
    def ok(self, method: str, payload: dict | None = None, **kwargs):  # type: ignore[override]
        if method in world.HANDLERS:
            return {
                "ok": True,
                "result": self.call_ok(
                    method,
                    payload or {},
                    expected_revision=int(kwargs.get("expected_revision") or 0),
                    idempotency_key=kwargs.get("idempotency_key"),
                ),
            }
        return super().ok(method, payload, **kwargs)

    def err(self, method: str, payload: dict | None = None, **kwargs):  # type: ignore[override]
        if method in world.HANDLERS:
            return self.call_err(
                method,
                payload or {},
                expected_revision=int(kwargs.get("expected_revision") or 0),
                idempotency_key=kwargs.get("idempotency_key"),
            )
        return super().err(method, payload, **kwargs)

    def test_world_methods_are_wired_to_the_frozen_manifest(self) -> None:
        names = set(world.HANDLERS)
        self.assertEqual(
            names,
            {"world.read", "world.style.preview", "world.generate", "world.approve"},
        )
        self.assertTrue(names.issubset(set(gm_contract.manifest_methods())))
        read = self.read_world()
        self.assertEqual(
            tuple(read), tuple(gm_contract.method_manifest("world.read")["response"])
        )
        # Under cb.rpc v20 the four names are still fenced: registration binds nothing and
        # dispatch would answer NOT_IMPLEMENTED rather than inventing a method.
        self.assertEqual(world.ensure_registered(), ())
        for method in names:
            with self.subTest(method=method):
                self.assertNotIn(method, api.method_names())


class FakeWorldMedia:
    """A real provider-shaped seam with deterministic bytes and a call log."""

    #: A 1x1 transparent PNG; trailing bytes make each plate content-distinct.
    PNG = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000b4944415478da63fcffff3f0300050001a5f645400000000049454e44ae426082"
    )

    def __init__(self, *, fail_when: str | None = None) -> None:
        self.calls: list[str] = []
        self.aspects: list[str] = []
        self.fail_when = fail_when

    def image(self, prompt: str, *, aspect_ratio: str = "landscape") -> tuple[bytes, str]:
        self.calls.append(prompt)
        self.aspects.append(aspect_ratio)
        if self.fail_when and self.fail_when.lower() in prompt.lower():
            raise world.WorldMediaFailure("provider refused this plate")
        tag = f"{len(self.calls)}:{prompt[-80:]}".encode("utf-8")
        return self.PNG + tag, "image/png"


class WorldMediaJobTest(WorldHandlerMixin, KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.course_id, self.plan_id = self.new_course()
        self.fake = FakeWorldMedia()
        world.bind_media(self.fake)

    def tearDown(self) -> None:
        world.bind_media(None)
        super().tearDown()

    def _brief(self, fixture: dict | None = None) -> dict:
        source = dict(fixture or JAPANESE_L0_BRIEF)
        source["course_id"] = self.course_id
        return source

    def test_world_cache_prevents_duplicate_spend(self) -> None:
        brief = world.WorldBrief.from_mapping(self._brief())
        base = world.cache_key(brief, "field_atlas", "hero", "field_atlas--authored", None)
        self.assertEqual(
            base, world.cache_key(brief, "field_atlas", "hero", "field_atlas--authored", None)
        )
        self.assertNotEqual(
            base, world.cache_key(brief, "field_atlas", "cover", "field_atlas--authored", None)
        )
        self.assertNotEqual(
            base, world.cache_key(brief, "field_atlas", "hero", "field_atlas--night-ink", None)
        )
        self.assertNotEqual(
            base, world.cache_key(brief, "field_atlas", "hero", "field_atlas--authored", "s1")
        )
        self.assertNotEqual(
            base,
            world.cache_key(
                brief, "field_atlas", "hero", "field_atlas--authored", None, prompt_version="v2"
            ),
        )
        other = world.WorldBrief.from_mapping({**self._brief(), "title": "Another course"})
        self.assertNotEqual(
            base, world.cache_key(other, "field_atlas", "hero", "field_atlas--authored", None)
        )

        first = self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=0,
            idempotency_key="world-concepts-1",
        )["result"]
        self.assertEqual(existing_job_kind(first["job_id"]), "media")
        self.assertEqual(self.count("SELECT COUNT(*) FROM course_worlds"), 1)
        self.assertEqual(self.count("SELECT COUNT(*) FROM jobs"), 1)

        views = executor.pump_once(limit=1)
        self.assertEqual(views[0]["state"], "completed")
        self.assertEqual(len(self.fake.calls), 3)
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(read["world"]["state"], "concepts_ready")
        board_hashes = [item["style_hash"] for item in read["world"]["concepts"]]
        self.assertEqual(len(set(board_hashes)), 3)

        # Ask for another set of concepts: the same cache key means the provider is not called
        # again, so an identical request never double-spends.
        second = self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts"},
            expected_revision=read["revision"],
            idempotency_key="world-concepts-2",
        )["result"]
        self.assertNotEqual(second["job_id"], first["job_id"])
        executor.pump_once(limit=1)
        self.assertEqual(len(self.fake.calls), 3)
        again = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(
            [item["style_hash"] for item in again["world"]["concepts"]], board_hashes
        )
        self.assertEqual(self.count("SELECT COUNT(*) FROM jobs"), 2)

    # ── helpers ─────────────────────────────────────────────────────────
    def count(self, sql: str) -> int:
        from coursebook import db

        with db.read() as connection:
            return int(connection.execute(sql).fetchone()[0])


class WorldFailureAndModeTest(WorldHandlerMixin, KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.course_id, self.plan_id = self.new_course()
        self.fake = FakeWorldMedia()
        world.bind_media(self.fake)

    def tearDown(self) -> None:
        world.bind_media(None)
        super().tearDown()

    def count(self, sql: str) -> int:
        from coursebook import db

        with db.read() as connection:
            return int(connection.execute(sql).fetchone()[0])

    def _technical_patch(self) -> dict:
        return {
            "subject_domain": "technical_procedure",
            "safety_class": "workshop",
            "end_capability": "Replace a head gasket on a four-cylinder engine",
            "motifs": ["service bay", "car on a lift", "tool wall", "component trays"],
            "sections": [
                {"id": "s1", "title": "Before you lift the car"},
                {"id": "s2", "title": "Removing the head"},
            ],
        }

    def _concepts_then_style(self) -> tuple[dict, dict]:
        self.ok(
            "world.generate",
            {"course_id": self.course_id, "stage": "concepts", "brief_patch": self._technical_patch()},
            expected_revision=0,
            idempotency_key="g-concepts",
        )
        executor.pump_once(limit=1)
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        board = read["world"]["concepts"][0]
        approved = self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": read["world"]["world_id"],
                "stage": "style",
                "approved_hash": board["style_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="g-style-1",
        )["result"]
        after = self.ok("world.read", {"course_id": self.course_id})["result"]
        return after, approved

    def test_partial_world_failure_names_missing_roles(self) -> None:
        read, approved = self._concepts_then_style()
        self.assertEqual(approved["state"], "style_selected")
        self.fake.fail_when = "Section scene s2"

        queued = self.ok(
            "world.generate",
            {
                "course_id": self.course_id,
                "stage": "kit",
                "style_id": approved["world"]["selected_concept_id"],
            },
            expected_revision=approved["world"]["revision"],
            idempotency_key="g-kit-001",
        )["result"]
        view = executor.pump_once(limit=1)[0]
        self.assertEqual(view["state"], "failed")
        self.assertEqual(view["error"]["code"], "POLICY_VIOLATION")
        self.assertEqual(view["checkpoint"]["missing_roles"], ["section:s2"])

        after = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(after["world"]["state"], "failed")
        self.assertEqual(after["world"]["error"]["missing_roles"], ["section:s2"])
        self.assertEqual(after["fallback"], "textbook")
        roles = {(item["role"], item["section_key"]) for item in after["world"]["assets"]}
        self.assertIn(("hero", ""), roles)
        self.assertIn(("cover", ""), roles)
        self.assertIn(("section", "s1"), roles)
        self.assertNotIn(("section", "s2"), roles)

        # No fabricated asset: every world_asset row points at a real artifact the provider made.
        self.assertEqual(
            self.count(
                "SELECT COUNT(*) FROM world_assets WHERE artifact_id NOT IN"
                " (SELECT id FROM artifacts)"
            ),
            0,
        )
        # Final approval of a partial world is refused even with the right-shaped hash.
        error = self.err(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": after["world"]["world_id"],
                "stage": "final",
                "approved_hash": "sha256:" + "0" * 64,
            },
            expected_revision=after["revision"],
            idempotency_key="g-final-bad",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertIn("world_not_ready", error["details"].get("reason", ""))

        # A retry pays only for the plate that was missing; the three that survived are reused.
        before = len(self.fake.calls)
        self.fake.fail_when = None
        self.ok(
            "world.generate",
            {
                "course_id": self.course_id,
                "stage": "kit",
                "style_id": approved["world"]["selected_concept_id"],
            },
            expected_revision=after["revision"],
            idempotency_key="g-kit-retry",
        )
        retried = executor.pump_once(limit=1)[0]
        self.assertEqual(retried["state"], "completed")
        self.assertEqual(len(self.fake.calls) - before, 1)
        completed = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(completed["world"]["state"], "kit_ready")
        roles_after = {
            (item["role"], item["section_key"]) for item in completed["world"]["assets"]
        }
        self.assertIn(("section", "s2"), roles_after)

    def test_world_approval_hash_fence(self) -> None:
        read, style = self._concepts_then_style()
        world_id = read["world"]["world_id"]
        board = read["world"]["concepts"][1]
        # A hash that is not one of the generated boards is refused; nothing moves.
        error = self.err(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": world_id,
                "stage": "style",
                "approved_hash": "sha256:" + "f" * 64,
            },
            expected_revision=read["revision"],
            idempotency_key="style-wrong",
        )
        self.assertEqual(error["code"], "POLICY_VIOLATION")
        self.assertEqual(error["details"]["reason"], "style_hash_not_a_concept")
        unchanged = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(unchanged["world"]["state"], "style_selected")
        self.assertEqual(unchanged["revision"], read["revision"])

        # The real board hash selects that concept and raises the world revision.
        selected = self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": world_id,
                "stage": "style",
                "approved_hash": board["style_hash"],
            },
            expected_revision=read["revision"],
            idempotency_key="style-right",
        )["result"]
        self.assertEqual(selected["state"], "style_selected")
        self.assertEqual(selected["world"]["selected_concept_id"], board["style_id"])
        self.assertEqual(selected["style_hash"], board["style_hash"])

        # Build the kit, then try to approve a hash the kit did not produce.
        self.ok(
            "world.generate",
            {
                "course_id": self.course_id,
                "stage": "kit",
                "style_id": board["style_id"],
            },
            expected_revision=selected["world"]["revision"],
            idempotency_key="kit-build-1",
        )
        self.assertEqual(executor.pump_once(limit=1)[0]["state"], "completed")
        kit_ready = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(kit_ready["world"]["state"], "kit_ready")
        self.assertIsNotNone(kit_ready["world"]["kit_hash"])
        self.assertEqual(len(kit_ready["world"]["assets"]), 4)

        stale = self.err(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": world_id,
                "stage": "final",
                "approved_hash": "sha256:" + "a" * 64,
            },
            expected_revision=kit_ready["revision"],
            idempotency_key="final-wrong",
        )
        self.assertEqual(stale["code"], "POLICY_VIOLATION")
        self.assertEqual(stale["details"]["reason"], "kit_hash_mismatch")

        approved = self.ok(
            "world.approve",
            {
                "course_id": self.course_id,
                "world_id": world_id,
                "stage": "final",
                "approved_hash": kit_ready["world"]["kit_hash"],
            },
            expected_revision=kit_ready["revision"],
            idempotency_key="final-right",
        )["result"]
        self.assertEqual(approved["state"], "approved")
        self.assertEqual(approved["approved_hash"], kit_ready["world"]["kit_hash"])
        final = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(final["world"]["state"], "approved")
        self.assertIsNone(final["fallback"])
        self.assertEqual(final["world"]["approved_hash"], kit_ready["world"]["kit_hash"])

    def test_textbook_generates_no_world_job(self) -> None:
        # A Textbook course is created plan-first: no world row, no media job, no asset.
        self.assertEqual(self.count("SELECT COUNT(*) FROM course_worlds"), 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM jobs"), 0)
        read = self.ok("world.read", {"course_id": self.course_id})["result"]
        self.assertEqual(read["presentation_mode"], "textbook")
        self.assertIsNone(read["world"])
        self.assertEqual(read["fallback"], "textbook")
        self.assertEqual(read["revision"], 0)
        self.assertFalse(world.world_job_on_create("textbook"))
        self.assertTrue(world.world_job_on_create("game"))


def existing_job_kind(job_id: str) -> str:
    from coursebook import db

    with db.read() as connection:
        return str(connection.execute("SELECT kind FROM jobs WHERE id = ?", (job_id,)).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
