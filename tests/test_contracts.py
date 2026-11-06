"""Contract-set invariants: ids, versions, cross-document references, integrity hashes."""

from __future__ import annotations

import json
import unittest

from coursebook import contracts


class ContractSetTest(unittest.TestCase):
    def test_set_is_internally_coherent(self) -> None:
        problems = contracts.audit_contracts()
        self.assertEqual(problems, [], f"contract set problems: {problems}")

    def test_every_contract_has_stable_id_and_version(self) -> None:
        for contract_id in contracts.contract_ids():
            with self.subTest(contract_id=contract_id):
                document = contracts.contract(contract_id)
                self.assertEqual(document["x-contract-id"], contract_id)
                version = document["x-contract-version"]
                self.assertIsInstance(version, int)
                self.assertGreaterEqual(version, 1)
                # The $id carries the version, so a v2 cannot silently overwrite a v1 resolver.
                self.assertTrue(
                    str(document["$id"]).endswith(f"/v{version}"),
                    f"{contract_id}: $id {document['$id']} does not end with /v{version}",
                )

    def test_files_are_json_and_in_the_inventory(self) -> None:
        for contract_id, filename in contracts.CONTRACT_FILES.items():
            with self.subTest(filename=filename):
                path = contracts.CONTRACT_DIR / filename
                self.assertTrue(path.is_file(), f"missing contract file {path}")
                parsed = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(parsed["x-contract-id"], contract_id)

    def test_inventory_reports_a_hash_per_contract(self) -> None:
        inventory = contracts.schema_inventory()
        self.assertEqual({entry["id"] for entry in inventory}, set(contracts.CONTRACT_FILES))
        for entry in inventory:
            with self.subTest(contract_id=entry["id"]):
                self.assertRegex(entry["sha256"], r"^sha256:[a-f0-9]{64}$")
                self.assertEqual(entry["version"], contracts.contract_version(entry["id"]))

    def test_wire_contract_is_v1(self) -> None:
        self.assertEqual(contracts.WIRE_CONTRACT_ID, "cb.rpc")
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, contracts.contract_version("cb.rpc"))

    def test_every_method_publishes_request_and_response_schemas(self) -> None:
        methods = contracts.method_names()
        self.assertGreaterEqual(len(methods), 20)
        for method in methods:
            with self.subTest(method=method):
                schema = contracts.method_schema(method)
                self.assertEqual(schema["request"]["type"], "object")
                self.assertEqual(schema["response"]["type"], "object")

    def test_error_codes_match_their_catalog(self) -> None:
        catalog = contracts.error_catalog()
        for code in contracts.error_codes():
            with self.subTest(code=code):
                entry = catalog[code]
                self.assertIn(entry["category"], {
                    "validation", "conflict", "state", "capability", "content", "internal"
                })
                self.assertIsInstance(entry["retryable"], bool)
                self.assertIsInstance(entry["http"], int)

    def test_build_error_rejects_unknown_code(self) -> None:
        with self.assertRaises(contracts.ContractError):
            contracts.build_error("NOT_A_REAL_CODE", "nope")

    def test_db_contract_covers_the_required_record_families(self) -> None:
        tables = set(contracts.contract("cb.db")["tables"])
        required = {
            "courses", "plans", "objectives", "enrollments", "checks", "attempts",
            "transitions", "evidence", "bindings", "sources", "artifacts", "jobs",
            "usage_events", "notebook_entries", "idempotency_keys", "packs",
        }
        self.assertTrue(required <= tables, f"missing tables: {sorted(required - tables)}")

    def test_pack_contract_excludes_private_state(self) -> None:
        excluded = contracts.contract("cb.pack")["excluded_by_construction"]
        for needle in ("transcripts", "attempts", "notebook entries and personal notes"):
            self.assertIn(needle, excluded)


if __name__ == "__main__":
    unittest.main()
