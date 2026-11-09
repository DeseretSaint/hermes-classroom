"""H-192c — the validator's own output is bounded on the nous chat-completions route.

Measured defect (``cb/t_958c3f23`` @ ``c58c05a``, live, validator ``nous/z-ai/glm-5.3-flash``):
a ``plan.validate`` pass asked for five criteria and six claims still emitted 19 739 completion
tokens in 927 s and missed its 600 s deadline; ``unit_sections.validate`` emitted 23 096. The
demand was already bounded (H-192b); what was unbounded was the validator's reasoning, because
the host drops ``LLMRequest.max_tokens`` on the nous chat-completions route.

The repair does not depend on a host patch: the plugin declares one auxiliary task
(``cb_validate``) whose host-documented defaults carry ``reasoning_effort`` and an
``extra_body.max_tokens`` cap, and every validation call passes that key. These tests pin the
declaration, the call-time key, and the two fallback behaviours without a provider.

Live wire evidence for the same path (probe, not this suite): identical five-criteria/six-claim
request uncapped 105.7 s / 6 114 completion tokens; through ``cb_validate`` 11.6 s / 566 tokens,
schema-valid 5 criteria + 6 claims.
"""

from __future__ import annotations

import unittest

from coursebook import generation as gen
from tests.test_h192_validation_bounds import big_plan, build_requests


class _FakePluginLLM:
    """The minimal ``ctx.llm`` surface the adapter is allowed to use."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        usage = type("Usage", (), {"input_tokens": 11, "output_tokens": 22, "cost_usd": 0.0})()
        return type(
            "Result",
            (),
            {
                "text": "{}",
                "parsed": {},
                "provider": "nous",
                "model": "z-ai/glm-5.3-flash",
                "usage": usage,
            },
        )()


class _RecordingCtx:
    def __init__(self, *, accept: bool = True, seam: bool = True) -> None:
        self.calls: list[tuple] = []
        self.accept = accept
        if seam:
            self.register_auxiliary_task = self._register

    def _register(self, key, **kwargs):
        self.calls.append((key, kwargs))
        if not self.accept:
            raise PermissionError("reserved key")


class ValidatorOutputBoundTests(unittest.TestCase):
    def setUp(self) -> None:
        # Module globals are process-wide by design; each test states its own host.
        gen._VALIDATION_TASK = None
        gen._VALIDATOR_LLM = None
        gen._VALIDATOR_OVERRIDES = {"provider": None, "model": None}
        gen._HOST_LLM = None

    def tearDown(self) -> None:
        gen._VALIDATION_TASK = None
        gen._VALIDATOR_LLM = None
        gen._VALIDATOR_OVERRIDES = {"provider": None, "model": None}
        gen._HOST_LLM = None

    # -- declaration ------------------------------------------------------
    def test_register_declares_one_bounded_auxiliary_task(self) -> None:
        ctx = _RecordingCtx()
        key = gen.register_validation_output_bound(ctx)

        self.assertEqual(key, gen.VALIDATION_AUX_TASK)
        self.assertEqual(len(ctx.calls), 1)
        declared_key, kwargs = ctx.calls[0]
        self.assertEqual(declared_key, "cb_validate")
        defaults = kwargs["defaults"]
        self.assertEqual(defaults["reasoning_effort"], gen.VALIDATION_REASONING_EFFORT)
        self.assertEqual(defaults["extra_body"]["max_tokens"], gen.VALIDATION_OUTPUT_TOKENS)
        # The declaration is not a route: it must not pin a provider or model.
        self.assertEqual(defaults["provider"], "auto")
        self.assertEqual(defaults["model"], "")

    def test_declared_cap_is_reported_not_implied(self) -> None:
        gen.bind_validator_llm(_FakePluginLLM(), provider="nous", model="z-ai/glm-5.3-flash")
        gen.register_validation_output_bound(_RecordingCtx())
        bound = gen.validator_config()["output_bound"]

        self.assertTrue(bound["registered"])
        self.assertEqual(bound["aux_task"], "cb_validate")
        self.assertEqual(bound["reasoning_effort"], "low")
        self.assertEqual(bound["completion_cap"], gen.VALIDATION_OUTPUT_TOKENS)

    # -- degraded hosts ---------------------------------------------------
    def test_host_without_the_seam_is_reported_as_unbounded(self) -> None:
        ctx = _RecordingCtx(seam=False)
        self.assertIsNone(gen.register_validation_output_bound(ctx))
        gen.bind_validator_llm(_FakePluginLLM(), provider="nous", model="z-ai/glm-5.3-flash")
        self.assertFalse(gen.validator_config()["output_bound"]["registered"])

    def test_a_refused_key_does_not_break_plugin_load(self) -> None:
        ctx = _RecordingCtx(accept=False)
        self.assertIsNone(gen.register_validation_output_bound(ctx))
        # The validator route still binds; it is simply not capped.
        gen.bind_validator_llm(_FakePluginLLM(), provider="nous", model="z-ai/glm-5.3-flash")
        adapter = gen._VALIDATOR_LLM
        if adapter is None:
            self.fail("validator adapter did not bind")
        self.assertIsNone(adapter.overrides["task"])

    # -- call-time key ----------------------------------------------------
    def _plan_request(self) -> gen.LLMRequest:
        return build_requests(big_plan(objectives=4))[0]

    def test_validator_calls_carry_the_task_key_and_the_cap(self) -> None:
        host = _FakePluginLLM()
        gen.register_validation_output_bound(_RecordingCtx())
        gen.bind_validator_llm(host, provider="nous", model="z-ai/glm-5.3-flash")

        adapter = gen.validator_llm()
        assert adapter is not None
        adapter(self._plan_request())

        call = host.calls[0]
        self.assertEqual(call["task"], "cb_validate")
        self.assertEqual(call["provider"], "nous")
        self.assertEqual(call["model"], "z-ai/glm-5.3-flash")
        self.assertEqual(call["max_tokens"], gen.VALIDATION_OUTPUT_TOKENS)

    def test_author_route_validation_is_bounded_too(self) -> None:
        """No validator configured: the pass runs on the author model, still capped."""
        host = _FakePluginLLM()
        gen.register_validation_output_bound(_RecordingCtx())
        gen.bind_host_llm(host)
        gen.bind_validator_llm(None, provider="", model="")

        self.assertIsNone(gen.validator_llm())
        bounded = gen.validation_llm()
        assert bounded is not None
        bounded(self._plan_request())
        self.assertEqual(host.calls[0]["task"], "cb_validate")

    def test_generation_calls_carry_no_validation_task(self) -> None:
        """The cap belongs to validation; authoring keeps its own budget."""
        host = _FakePluginLLM()
        gen.register_validation_output_bound(_RecordingCtx())
        gen.bind_host_llm(host)

        gen.host_llm()(self._plan_request())

        self.assertNotIn("task", host.calls[0])

    def test_every_plan_validation_request_declares_the_cap(self) -> None:
        requests = build_requests(big_plan(objectives=12))
        self.assertGreater(len(requests), 1)
        for request in requests:
            self.assertEqual(request.max_tokens, gen.VALIDATION_OUTPUT_TOKENS)
            self.assertEqual(request.purpose, "coursebook.plan.validate")


if __name__ == "__main__":
    unittest.main()
