"""RPC envelope behaviour: validation, refusal shapes, and no silent success."""

from __future__ import annotations

import unittest

from jsonschema import Draft202012Validator

from coursebook import api, contracts


def request(method: str, payload: dict | None = None, **overrides):
    body = {
        "contract": "cb.rpc",
        "contract_version": contracts.WIRE_CONTRACT_VERSION,
        "method": method,
        "operation_id": f"op-{method.replace('.', '-')}-0001",
        "payload": payload if payload is not None else {},
    }
    body.update(overrides)
    return body


class EnvelopeSchemaTest(unittest.TestCase):
    def test_ok_response_matches_contract(self) -> None:
        response = api.dispatch(request("health.get"))
        self.assertTrue(response["ok"])
        schema = contracts.contract("cb.rpc")["$defs"]["envelope_response_ok"]
        Draft202012Validator(schema, registry=contracts.registry()).validate(response)

    def test_error_response_matches_error_contract(self) -> None:
        response = api.dispatch(request("course.create"))
        self.assertFalse(response["ok"])
        schema = contracts.contract("cb.errors")["$defs"]["error"]
        Draft202012Validator(schema, registry=contracts.registry()).validate(response["error"])


class DispatchTest(unittest.TestCase):
    def test_health_reports_contract_and_db_block(self) -> None:
        response = api.dispatch(request("health.get"))
        result = response["result"]
        self.assertEqual(result["contract_version"], contracts.WIRE_CONTRACT_VERSION)
        self.assertIn("ready", result["db"])
        self.assertIn("schema_version", result["db"])

    def test_schema_lists_every_contract(self) -> None:
        response = api.dispatch(request("schema.get"))
        ids = {entry["id"] for entry in response["result"]["contracts"]}
        self.assertEqual(ids, set(contracts.CONTRACT_FILES))
        self.assertEqual(response["result"]["db_schema_version"], contracts.contract("cb.db")["schema_version"])

    def test_unimplemented_method_is_refused_not_faked(self) -> None:
        # ``course.create`` is implemented by the kernel package; ``pack.preview`` is still
        # Lattice's. This asserts the dispatch contract, not which package has landed.
        response = api.dispatch(request("pack.preview", {"staged_id": "stg_not_implemented_01"}))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "NOT_IMPLEMENTED")
        self.assertFalse(response["error"]["retryable"])

    def test_malformed_envelope_is_validation_failure(self) -> None:
        broken = request("health.get")
        del broken["operation_id"]
        response = api.dispatch(broken)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

    def test_wrong_contract_version_is_validation_failure(self) -> None:
        response = api.dispatch(request("health.get", contract_version=contracts.WIRE_CONTRACT_VERSION + 1))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

    def test_method_payload_is_validated(self) -> None:
        calls = []

        def handler(payload, envelope):
            calls.append(payload)
            return 1, {"entries": []}

        api.register_handler("notebook.list", handler)
        try:
            response = api.dispatch(request("notebook.list", {"tag": 5}))
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")
            self.assertEqual(calls, [], "handler must not run on an invalid payload")

            good = api.dispatch(request("notebook.list", {"tag": None}))
            self.assertTrue(good["ok"])
            self.assertEqual(good["revision"], 1)
        finally:
            api.METHOD_HANDLERS.pop("notebook.list", None)

    def test_handler_result_outside_contract_is_internal_error(self) -> None:
        api.register_handler("notebook.list", lambda payload, envelope: (1, {"entries": "not-a-list"}))
        try:
            response = api.dispatch(request("notebook.list"))
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")
        finally:
            api.METHOD_HANDLERS.pop("notebook.list", None)

    def test_handler_exception_is_internal_error_not_a_crash(self) -> None:
        def boom(payload, envelope):
            raise RuntimeError("database went away")

        api.register_handler("notebook.list", boom)
        try:
            response = api.dispatch(request("notebook.list"))
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")
            self.assertNotIn("database went away", response["error"]["message"])
        finally:
            api.METHOD_HANDLERS.pop("notebook.list", None)

    def test_policy_refusal_keeps_its_code_and_current_revision(self) -> None:
        def stale(payload, envelope):
            raise api.RpcError.of("STALE_REVISION", "That check moved on.", current_revision=7)

        api.register_handler("notebook.list", stale)
        try:
            response = api.dispatch(request("notebook.list"))
            self.assertFalse(response["ok"])
            error = response["error"]
            self.assertEqual(error["code"], "STALE_REVISION")
            self.assertEqual(error["category"], "conflict")
            self.assertFalse(error["retryable"])
            self.assertEqual(error["details"]["current_revision"], 7)
        finally:
            api.METHOD_HANDLERS.pop("notebook.list", None)

    def test_unknown_handler_registration_is_refused(self) -> None:
        with self.assertRaises(contracts.ContractError):
            api.register_handler("coursebook.invented", lambda payload, envelope: (0, {}))

    def test_grader_unavailable_is_retryable(self) -> None:
        self.assertTrue(contracts.is_retryable("GRADER_UNAVAILABLE"))
        self.assertFalse(contracts.is_retryable("STALE_REVISION"))


if __name__ == "__main__":
    unittest.main()
