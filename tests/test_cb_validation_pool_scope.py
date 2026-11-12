"""The validation pool must carry the tick's profile secret scope into every pass (t_3d735846).

Measured defect: on the isolated rig ``~/.hermes/coursebook-test-cp015g-r4`` (``hermes serve
--isolated --port 44629``, plugin source ``c18617e1``) plan job
``job_f867e8b6231349bbb3fa7957affea9c5`` completed with ``research_status: "ok"`` and four sources,
yet its ``errors.log`` carried twenty copies of::

    hermes_cli.auth: nous: NOUS_INFERENCE_BASE_URL unreadable — no profile secret scope on a
    multiplexed call; treating the override as absent (default routing applies).

clustered at the validation calls (12:10:34, 12:13:43, 12:19:01, 12:26:16), not at the plan-tick
call. ``coursebook/generation.py::_run_validation_passes`` submits its passes to a
``ThreadPoolExecutor(thread_name_prefix="coursebook-validation")`` with no context copy, and a
Python thread starts with an **empty** contextvars context: the route the tick carries
(``_LAUNCH_BODY_SCOPE``, or a per-turn ``_SECRET_SCOPE``) was simply absent inside the pass.

That is not fatal only while default routing happens to be the right endpoint. On a deployment
that sets ``NOUS_INFERENCE_BASE_URL`` the validator's calls silently route to the default host,
which spends the wrong token against the wrong endpoint. ``coursebook/grading.py``'s aux-grader
thread had the same shape and is fixed and tested here too; ``deadline.py`` (``BoundedCallPool``,
``run_async_bounded``), ``executor.py`` and ``job_service.py`` already copy the caller's context.

Static, in-process proof only (NO LIVE WINDOW RULE, owner directive 2026-11-12): no rig backend,
no Desktop window, no CDP probe. The host's real ``agent.secret_scope`` contextvars are bound, the
override is read once on this (tick) thread and once inside a real pool thread, and the two must
agree with no ``no profile secret scope`` warning logged.

Red proof: revert the propagation in ``_run_validation_passes`` to a bare
``pool.submit(_call_llm, ...)`` and three assertions fail. The pool thread resolves ``None``
instead of the bound override
(``test_the_pool_thread_resolves_the_ticks_override``: ``[None, None]`` vs
``['https://staging.invalid/nous', 'https://staging.invalid/nous']``); the host logs the warning
twice (``test_the_pool_thread_logs_no_lost_scope_warning``); and the same revert in
``grading._run_with_deadline`` fails ``test_the_aux_grader_thread_resolves_the_ticks_override``.
All three were observed with the revert in place.

Run only these with::

    python3 -m unittest tests.test_cb_validation_pool_scope -v
"""

from __future__ import annotations

import logging
import os
import threading
import unittest
from unittest import mock

from coursebook import generation as gen
from coursebook import grading

try:  # The host is what owns the secret-scope boundary; a bare checkout has no host.
    from agent import secret_scope
    from hermes_cli import auth_nous

    HAVE_HOST_SECRET_SCOPE = True
except Exception:  # pragma: no cover - environment guard
    HAVE_HOST_SECRET_SCOPE = False


OVERRIDE_NAME = "NOUS_INFERENCE_BASE_URL"
OVERRIDE_URL = "https://staging.invalid/nous"


class _WarningCapture(logging.Handler):
    """Collect ``hermes_cli`` warnings. ``assertLogs`` needs a record to pass, so it cannot
    assert silence; this can."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102 - logging API
        self.messages.append(record.getMessage())


@unittest.skipUnless(HAVE_HOST_SECRET_SCOPE, "agent.secret_scope is not importable here")
class _BoundScopeCase(unittest.TestCase):
    """Binds the host's real secret-scope contextvars the way the measured rig was bound."""

    def setUp(self) -> None:
        # No ambient value: every reading below can only come from the bound scope.
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(OVERRIDE_NAME, None)

        # The measured topology: the process is a profile multiplexer (a process-global, shared by
        # every thread) and the tick entered with a launch-body scope (a contextvar, which is what
        # the pool thread lost). Patching the module flag avoids ``set_multiplex_active``'s
        # launch-home pin side effect.
        active = mock.patch.object(secret_scope, "_MULTIPLEX_ACTIVE", True)
        active.start()
        self.addCleanup(active.stop)

        launch = secret_scope.set_launch_body_scope(lambda: {OVERRIDE_NAME: OVERRIDE_URL})
        self.addCleanup(secret_scope.reset_launch_body_scope, launch)
        bound = secret_scope.set_secret_scope(None)
        self.addCleanup(secret_scope.reset_secret_scope, bound)

        self.capture = _WarningCapture()
        logger = logging.getLogger("hermes_cli")
        logger.addHandler(self.capture)
        logger.setLevel(logging.WARNING)
        self.addCleanup(logger.removeHandler, self.capture)

        self.requests = [
            gen.LLMRequest(
                purpose=f"test.validate.pass{index}",
                prompt_version="test",
                system_prompt="validator",
                instructions="judge the pass",
                input_text="{}",
                schema={"type": "object"},
                schema_name="test_pass",
                max_tokens=64,
                timeout_s=30.0,
            )
            for index in range(2)
        ]
        self.readings: list[tuple[str, str | None]] = []
        self._lock = threading.Lock()

    def _tick_read(self) -> str | None:
        """The routed override exactly as the tick that submits the passes reads it."""
        return auth_nous._nous_inference_env_override()

    def _llm_reading_its_own_route(self, request: gen.LLMRequest) -> gen.LLMResponse:
        """Stand in for the validator provider: resolve the route from inside the pass's thread."""
        value = self._tick_read()
        with self._lock:
            self.readings.append((threading.current_thread().name, value))
        return gen.LLMResponse(
            text="{}",
            parsed={"pass": request.purpose},
            provider="fake",
            model="fake-validator",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
        )


class ValidationPoolSecretScopeTest(_BoundScopeCase):
    """A validation pass resolves exactly the routed override its tick resolves."""

    def _run_pool(self) -> str | None:
        """Submit two real passes to the real pool, each reading the route from its own thread."""
        self.assertEqual(
            self._tick_read(), OVERRIDE_URL, "the bound launch-body scope was not readable"
        )
        self.readings.clear()
        responses = gen._run_validation_passes(
            self._llm_reading_its_own_route,
            self.requests,
            gen._Usage(gen.CostBudget(max_calls=8, max_cost_usd=None)),
        )
        self.assertEqual(len(responses), len(self.requests))
        self.assertEqual(len(self.readings), len(self.requests), "a pass never reached the provider")
        names = [name for name, _ in self.readings]
        self.assertTrue(
            all(name.startswith("coursebook-validation") for name in names),
            f"the reading did not run on the validation pool: {names}",
        )
        return self._tick_read()

    def test_the_pool_thread_resolves_the_ticks_override(self) -> None:
        """Red pre-fix: ``[None, None]`` instead of the tick's routed override."""
        tick_value = self._run_pool()
        # The bare pool context held neither the multiplex context nor the launch-body scope, so
        # the routed override was treated as absent and default routing applied.
        self.assertEqual(
            [value for _, value in self.readings],
            [tick_value, tick_value],
            "a validation pass resolved a different route than the tick that submitted it",
        )

    def test_the_pool_thread_logs_no_lost_scope_warning(self) -> None:
        """Red pre-fix: the host logs ``no profile secret scope on a multiplexed call``."""
        self._run_pool()
        lost_scope = [
            message for message in self.capture.messages if "profile secret scope" in message
        ]
        self.assertEqual(lost_scope, [], f"the pool lost the profile scope: {lost_scope}")


@unittest.skipUnless(HAVE_HOST_SECRET_SCOPE, "agent.secret_scope is not importable here")
class AuxGraderThreadSecretScopeTest(_BoundScopeCase):
    """The aux-grader thread is the same class: it inherits the turn's context."""

    def test_the_aux_grader_thread_resolves_the_ticks_override(self) -> None:
        tick_value = self._tick_read()
        self.assertEqual(tick_value, OVERRIDE_URL)

        def grader(**_kwargs: object) -> dict:
            return {
                "verdict": "pass",
                "criteria": [{"id": "c1", "observed": "ok", "met": True}],
                "route": self._tick_read(),
                "thread": threading.current_thread().name,
            }

        result = grading._run_with_deadline(grader, 5000)
        self.assertEqual(result["thread"], "coursebook-aux-grader")
        self.assertEqual(
            result["route"],
            tick_value,
            "the aux grader resolved a different route than the turn that asked for the grade",
        )
        lost_scope = [message for message in self.capture.messages if "profile secret scope" in message]
        self.assertEqual(lost_scope, [], f"the aux grader lost the profile scope: {lost_scope}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
