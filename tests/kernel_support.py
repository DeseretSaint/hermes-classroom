"""Shared fixtures for the backend-kernel tests.

These tests run against a **real** SQLite database, created by the real migrations, opened through
the real ``plugins.plugin_storage.plugin_db`` seam under a throwaway ``HERMES_HOME``. Nothing is
mocked except the aux grader (which has no implementation in this build by design) — the point of
the kernel is the database and the fence, so the tests exercise those.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from coursebook import api, db, domain


def request(
    method: str,
    payload: dict | None = None,
    *,
    operation_id: str | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": 1,
        "method": method,
        "operation_id": operation_id or f"op-{method.replace('.', '-')}-{os.urandom(4).hex()}",
        "payload": payload if payload is not None else {},
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    if idempotency_key is not None:
        body["idempotency_key"] = idempotency_key
    return body


def numeric_spec(value: str = "4", *, unit: str | None = None, tolerance: str = "0",
                 audit_state: str = "passed", variants: list[dict] | None = None) -> dict:
    reference = {"kind": "numeric", "value": value, "tolerance": {"abs": tolerance}}
    if unit:
        reference["unit"] = unit
    spec = {
        "audit_state": audit_state,
        "stimulus": {"prompt": "Compute the answer."},
        "reference": reference,
        "rubric": {"construct": "procedure", "pass_rule": "all",
                   "criteria": [{"id": "c1", "description": "Correct value"}]},
    }
    if variants is not None:
        spec["variants"] = variants
    return spec


def criteria_with(spec: dict, criterion_id: str = "c1") -> list[dict]:
    return [{"id": criterion_id, "description": "graded criterion", "check_spec": spec}]


class KernelCase(unittest.TestCase):
    """An isolated profile database per test, migrated with the real migration runner."""

    def setUp(self) -> None:
        self.home = tempfile.mkdtemp(prefix="coursebook-kernel-")
        self._previous_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.home
        db.migrate()

    def tearDown(self) -> None:
        if self._previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self._previous_home
        shutil.rmtree(self.home, ignore_errors=True)

    # ── dispatch helpers ────────────────────────────────────────────────

    def dispatch(self, method: str, payload: dict | None = None, **kwargs) -> dict:
        return api.dispatch(request(method, payload, **kwargs))

    def ok(self, method: str, payload: dict | None = None, **kwargs) -> dict:
        response = self.dispatch(method, payload, **kwargs)
        self.assertTrue(response["ok"], f"{method} failed: {response.get('error')}")
        return response

    def err(self, method: str, payload: dict | None = None, **kwargs) -> dict:
        response = self.dispatch(method, payload, **kwargs)
        self.assertFalse(response["ok"], f"{method} unexpectedly succeeded: {response.get('result')}")
        return response["error"]

    # ── fixtures ────────────────────────────────────────────────────────

    def new_course(self, *, title: str = "Learn to braise", recipe: str = "committed") -> tuple[str, str]:
        result = self.ok("course.create", {"title": title, "recipe": recipe, "goal": "Braise short ribs"})["result"]
        return result["course_id"], result["plan_id"]

    def new_enrollment(self, course_id: str, label: str = "Learner") -> str:
        return self.ok("enrollment.create", {"course_id": course_id, "learner_label": label})["result"]["enrollment_id"]

    def seed_objective(self, plan_id: str, spec: dict | None = None) -> str:
        spec = spec or numeric_spec()
        return domain.record_objective(
            plan_id, title="Compute", evidence_target="procedure", criteria=criteria_with(spec)
        )

    def approve(self, enrollment_id: str, plan_id: str, revision: int) -> int:
        return self.ok(
            "plan.approve",
            {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
            expected_revision=revision,
        )["result"]["revision"]

    def prepare_lesson(self, spec: dict | None = None, *, recipe: str = "committed") -> dict:
        """course -> objective -> approved plan -> open check, all through the real commands."""
        course_id, plan_id = self.new_course(recipe=recipe)
        objective_id = self.seed_objective(plan_id, spec)
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        opened = self.ok(
            "check.open", {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        return {
            "course_id": course_id,
            "plan_id": plan_id,
            "objective_id": objective_id,
            "enrollment_id": enrollment_id,
            "check_id": opened["check_id"],
            "check_version": opened["check_version"],
            "revision": opened["revision"],
        }

    def submit(self, lesson: dict, answer: str | dict | list, *, revision: int | None = None,
               nonce: str | None = None, key: str | None = None, operation_id: str | None = None) -> dict:
        if isinstance(answer, str):
            answer = {"kind": "text", "text": answer}
        elif isinstance(answer, list):
            answer = {"kind": "selection", "selection": answer}
        # A retry with the same idempotency key must resend the identical payload, nonce included —
        # otherwise it is a different command and IDEMPOTENCY_CONFLICT is the correct answer.
        nonce = nonce or (f"nonce-{key[-24:]}" if key else f"nonce-{os.urandom(6).hex()}")
        return self.dispatch(
            "attempt.submit",
            {
                "enrollment_id": lesson["enrollment_id"],
                "check_id": lesson["check_id"],
                "check_version": lesson["check_version"],
                "attempt_nonce": nonce,
                "answer": answer,
            },
            expected_revision=lesson["revision"] if revision is None else revision,
            idempotency_key=key or f"key-{os.urandom(8).hex()}",
            operation_id=operation_id,
        )

    # ── database helpers ────────────────────────────────────────────────

    def rows(self, sql: str, params: tuple = ()) -> list[dict]:
        with db.read() as connection:
            return [dict(row) for row in connection.execute(sql, params)]

    def scalar(self, sql: str, params: tuple = ()) -> object:
        with db.read() as connection:
            row = connection.execute(sql, params).fetchone()
        return None if row is None else row[0]

    def execute(self, sql: str, params: tuple = ()) -> None:
        with db.transaction() as connection:
            connection.execute(sql, params)
