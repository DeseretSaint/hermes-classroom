"""Contract-set invariants: ids, versions, cross-document references, integrity hashes.

CB-018 amends the set to v2. These tests fail if the new methods, their payload schemas, the
version links, the v2 storage plan or the documented UX mapping disappear.
"""

from __future__ import annotations

import json
import unittest

from coursebook import api, contracts

#: Added in cb.rpc v2. Every one of these must stay schema-complete and bounded.
V2_NEW_METHODS = (
    "library.list",
    "lesson.page",
    "lesson.begin",
    "enrollment.update",
    "enrollment.delete",
    "pack.delete",
    "artifact.get",
    "jobs.list",
    "notebook.update",
    "binding.abandon",
)


def _document(filename: str) -> dict:
    return json.loads((contracts.CONTRACT_DIR / filename).read_text(encoding="utf-8"))


def _envelope(method: str, payload: dict | None = None, **overrides) -> dict:
    body = {
        "contract": "cb.rpc",
        "contract_version": contracts.WIRE_CONTRACT_VERSION,
        "method": method,
        "operation_id": f"op-{method.replace('.', '-')}-cb018",
        "payload": payload if payload is not None else {},
    }
    body.update(overrides)
    return body


def _schema_problems(schema: dict, path: str = "schema") -> list[str]:
    """Bounds/airtightness walker for one new-method payload schema."""
    problems: list[str] = []
    for branch in ("oneOf", "anyOf"):
        for index, option in enumerate(schema.get(branch, [])):
            problems.extend(_schema_problems(option, f"{path}.{branch}[{index}]"))
    properties = schema.get("properties")
    if isinstance(properties, dict):
        if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
            problems.append(f"{path}: object with named properties lacks additionalProperties:false")
        for name, subschema in properties.items():
            problems.extend(_schema_problems(subschema, f"{path}.{name}"))
    items = schema.get("items")
    if isinstance(items, dict):
        problems.extend(_schema_problems(items, f"{path}.items"))
    declared = schema.get("type")
    types = declared if isinstance(declared, list) else [declared]
    if "array" in types and "maxItems" not in schema:
        problems.append(f"{path}: array lacks maxItems")
    if "string" in types and not any(key in schema for key in ("maxLength", "const", "enum")):
        problems.append(f"{path}: string lacks maxLength")
    if "integer" in types and "maximum" not in schema:
        problems.append(f"{path}: integer lacks maximum")
    return problems


def _property_names(schema: dict) -> set[str]:
    names: set[str] = set()
    for branch in ("oneOf", "anyOf"):
        for option in schema.get(branch, []):
            names |= _property_names(option)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        names |= set(properties)
        for subschema in properties.values():
            names |= _property_names(subschema)
    items = schema.get("items")
    if isinstance(items, dict):
        names |= _property_names(items)
    return names


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

    def test_wire_contract_is_v2(self) -> None:
        self.assertEqual(contracts.WIRE_CONTRACT_ID, "cb.rpc")
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 2)
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, contracts.contract_version("cb.rpc"))
        self.assertTrue(str(contracts.contract("cb.rpc")["$id"]).endswith("/rpc/v2"))

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


class V2AmendmentTest(unittest.TestCase):
    """CB-018: the additive v2 amendment that makes the UX screens implementable."""

    def test_v1_documents_are_preserved_on_disk(self) -> None:
        v1 = _document("rpc.v1.json")
        v2 = contracts.contract("cb.rpc")
        self.assertEqual(v1["x-contract-version"], 1)
        self.assertEqual(str(v1["$id"]), "https://contracts.coursebook.hermes/rpc/v1")
        self.assertEqual(len(v1["$defs"]["method"]["enum"]), 24)
        for filename in ("errors.v1.json", "db.v1.json", "jobs.v1.json"):
            self.assertTrue((contracts.CONTRACT_DIR / filename).is_file(), filename)
        # Every v1 method and payload survives; the only permitted edit is the wire-version
        # constant echoed by health.get (v1 said 1, v2 must say 2).
        for method in v1["$defs"]["method"]["enum"]:
            with self.subTest(method=method):
                self.assertIn(method, contracts.method_names())
                v2_method = json.loads(json.dumps(v2["$defs"]["methods"]["properties"][method]))
                if method == "health.get":
                    v2_method["response"]["properties"]["contract_version"] = {"const": 1}
                self.assertEqual(v1["$defs"]["methods"]["properties"][method], v2_method)
        self.assertEqual(
            v2["$defs"]["methods"]["properties"]["health.get"]["response"]["properties"]
            ["contract_version"]["const"],
            2,
        )

    def test_new_methods_are_present_with_airtight_bounded_schemas(self) -> None:
        for method in V2_NEW_METHODS:
            with self.subTest(method=method):
                self.assertIn(method, contracts.method_names())
                schema = contracts.method_schema(method)
                for side in ("request", "response"):
                    self.assertEqual(schema[side]["type"], "object")
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    problems = _schema_problems(schema[side])
                    self.assertEqual(problems, [], f"{method}.{side}: {problems}")

    def test_library_list_covers_empty_and_filtered_empty_states(self) -> None:
        schema = contracts.method_schema("library.list")
        request = schema["request"]["properties"]
        self.assertEqual(set(request["filter"]["enum"]), {"all", "in_progress", "review_due", "archived"})
        self.assertLessEqual(request["limit"]["maximum"], 100)
        response = schema["response"]
        self.assertLessEqual(response["properties"]["items"]["maxItems"], 100)
        empty = response["properties"]["empty_reason"]["oneOf"][0]["enum"]
        # Both "nothing yet" and "nothing matched this filter" are nameable screen states.
        self.assertIn("no_courses", empty)
        self.assertIn("no_matches", empty)
        item = contracts.contract("cb.rpc")["$defs"]["library_item"]
        for field in ("next_step", "evidence_summary", "provenance", "enrollment_status", "revision"):
            self.assertIn(field, item["properties"])
        self.assertIn("archived", item["properties"]["enrollment_status"]["enum"])
        self.assertIn("pack_id", item["properties"]["provenance"]["properties"])

    def test_lesson_page_is_a_read_only_navigation_surface(self) -> None:
        schema = contracts.method_schema("lesson.page")
        self.assertEqual(
            set(schema["request"]["properties"]), {"enrollment_id", "objective_id", "section_id"}
        )
        response = schema["response"]
        for field in (
            "runtime", "segments", "sources", "artifacts", "checks",
            "notebook_entries", "attempts", "state",
        ):
            self.assertIn(field, response["required"])
        # The page renders from backend records, not a chat transcript field.
        self.assertNotIn("transcript", _property_names(schema))

    def test_lesson_begin_defines_resume_fresh_and_stale_binding_behavior(self) -> None:
        schema = contracts.method_schema("lesson.begin")
        self.assertEqual(set(schema["request"]["properties"]["mode"]["enum"]), {"resume", "fresh"})
        response = schema["response"]
        for field in ("lesson_run_id", "run_state", "binding", "resume"):
            self.assertIn(field, response["required"])
        binding = contracts.contract("cb.rpc")["$defs"]["lesson_binding"]
        for field in ("runtime_session_id", "stored_session_id", "reattachable", "status"):
            self.assertIn(field, binding["properties"])
        self.assertIn("needs_fresh_run", response["properties"]["run_state"]["enum"])
        reasons = response["properties"]["resume"]["properties"]["reason"]["oneOf"][0]["enum"]
        for reason in ("detached", "branched", "orphaned", "session_missing"):
            self.assertIn(reason, reasons)
        # Starting/resuming a run must be idempotent: a double-click cannot mint two chats.
        with self.assertRaises(contracts.ContractError):
            contracts.validate(
                "cb.rpc", _envelope("lesson.begin", {
                    "enrollment_id": "enr_12345678",
                    "objective_id": "obj_12345678",
                    "mode": "fresh",
                })
            )

    def test_artifact_get_never_exposes_a_filesystem_path(self) -> None:
        schema = contracts.method_schema("artifact.get")
        forbidden = {"path", "file_path", "local_path", "absolute_path", "filesystem_path"}
        self.assertEqual(_property_names(schema) & forbidden, set())
        download = schema["response"]["properties"]["download"]
        self.assertIs(download["required"] and download["properties"]["requires_session"]["const"], True)
        self.assertRegex(
            download["properties"]["url"]["pattern"],
            r"^\^/api/plugins/coursebook/artifacts/",
        )
        self.assertIn("expires_at", download["required"])

    def test_notebook_update_cannot_rewrite_provenance(self) -> None:
        schema = contracts.method_schema("notebook.update")
        self.assertEqual(set(schema["request"]["properties"]), {"entry_id", "note", "tags"})
        self.assertEqual(schema["request"]["minProperties"], 2)
        # Editing must not create a second entry, change attribution, or move the note.
        for immutable in (
            "excerpt", "source_ref", "objective_id", "enrollment_id", "lesson_run_id", "kind",
        ):
            self.assertNotIn(immutable, schema["request"]["properties"])

    def test_deletion_methods_have_separate_semantics_and_server_returned_scope(self) -> None:
        delete_enrollment = contracts.method_schema("enrollment.delete")
        delete_pack = contracts.method_schema("pack.delete")
        update = contracts.method_schema("enrollment.update")

        # Archive/unarchive is a reversible status change, not a deletion.
        self.assertEqual(
            set(update["request"]["properties"]["action"]["enum"]),
            {"archive", "unarchive", "pause", "resume"},
        )
        self.assertNotIn("data_scope", update["response"]["properties"])

        for schema, scope_def in ((delete_enrollment, "data_scope"), (delete_pack, "pack_scope")):
            request = schema["request"]
            self.assertEqual(request["properties"]["dry_run"]["default"], False)
            self.assertIn("data_scope", schema["response"]["properties"])
            self.assertEqual(schema["response"]["properties"]["data_scope"]["$ref"], f"#/$defs/{scope_def}")
            scope = contracts.contract("cb.rpc")["$defs"][scope_def]
            for field in ("counts", "preserved", "scope_hash", "summary"):
                self.assertIn(field, scope["properties"])
            # Destructive confirmation is fenced by the previewed scope hash.
            self.assertIn("data_scope_hash", request["properties"])

        # dry_run preview needs no hash; the destructive call does.
        contracts.validate_request_payload(
            "enrollment.delete", {"enrollment_id": "enr_12345678", "dry_run": True}
        )
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "enrollment.delete", {"enrollment_id": "enr_12345678", "dry_run": False}
            )
        contracts.validate_request_payload(
            "enrollment.delete",
            {
                "enrollment_id": "enr_12345678",
                "dry_run": False,
                "data_scope_hash": "sha256:" + "a" * 64,
            },
        )
        contracts.validate_request_payload(
            "pack.delete", {"pack_id": "pack_demo_japanese", "dry_run": True}
        )

    def test_jobs_list_is_bounded_and_reuses_the_job_state_authority(self) -> None:
        schema = contracts.method_schema("jobs.list")
        self.assertLessEqual(schema["request"]["properties"]["limit"]["maximum"], 100)
        self.assertLessEqual(schema["response"]["properties"]["jobs"]["maxItems"], 100)
        state_ref = schema["request"]["properties"]["state"]["items"]["$ref"]
        self.assertEqual(state_ref, "https://contracts.coursebook.hermes/jobs/v2#/$defs/job_state")
        jobs_contract = contracts.contract("cb.jobs")
        self.assertEqual(jobs_contract["$defs"]["job_state"]["enum"], jobs_contract["states"])
        contracts.validate_request_payload("jobs.list", {"state": ["running", "failed"], "limit": 10})
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload("jobs.list", {"state": ["invented_state"]})
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload("jobs.list", {"limit": 0})

    def test_v2_error_code_is_catalogued(self) -> None:
        self.assertIn("DELETE_SCOPE_STALE", contracts.error_codes())
        catalog = contracts.error_catalog()["DELETE_SCOPE_STALE"]
        self.assertEqual(catalog["category"], "conflict")
        self.assertEqual(catalog["http"], 409)
        self.assertFalse(catalog["retryable"])

    def test_db_v2_adds_durable_lesson_storage_with_a_migration_plan(self) -> None:
        db = contracts.contract("cb.db")
        self.assertEqual(db["schema_version"], 2)
        tables = db["tables"]
        for table in ("lesson_runs", "lesson_segments"):
            self.assertIn(table, tables)
        self.assertIn("lesson_run_id", tables["bindings"]["columns"])
        self.assertIn("objective_id", tables["bindings"]["columns"])
        self.assertIn("revision", tables["notebook_entries"]["columns"])
        self.assertIn("state", tables["packs"]["columns"])
        self.assertIn("revision", tables["packs"]["columns"])
        plan = db["migration_plan"]
        self.assertEqual([entry["version"] for entry in plan], [2])
        self.assertIn("additive", " ".join(plan[0]["impact"]).lower())
        # Deletion still never claims to erase Hermes' own transcripts.
        self.assertIn("Hermes' own transcripts", db["deletion_policy"])

    def test_docs_map_every_ux_screen_and_new_method(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for screen in ("§6", "§7", "§8", "§10", "§11"):
            self.assertIn(screen, text, f"CONTRACTS.md has no mapping for UX {screen}")
        for method in V2_NEW_METHODS:
            self.assertIn(method, text, f"CONTRACTS.md does not document {method}")

    def test_dispatch_validates_new_methods_before_any_handler(self) -> None:
        # Handlers are Cinder's job; the seam must validate payloads and refuse honestly.
        response = api.dispatch(_envelope("library.list", {"limit": 0}))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

        response = api.dispatch(_envelope("library.list", {"filter": "all"}))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "NOT_IMPLEMENTED")

        def handler(payload, envelope):
            return 3, {
                "items": [
                    {
                        "enrollment_id": "enr_12345678",
                        "course_id": "crs_12345678",
                        "title": "Conversational Japanese",
                        "recipe": "committed",
                        "enrollment_status": "active",
                        "course_status": "active",
                        "provenance": {"source": "bundled", "pack_id": "jp-l0", "pack_version": "1.0.0"},
                        "next_step": {"kind": "resume_lesson", "label": "Choose a register"},
                        "evidence_summary": {
                            "independent": 2, "review_due": 0, "total_objectives": 6,
                            "current_objective_id": "obj_12345678",
                        },
                        "updated_at": "2026-11-06T00:00:00Z",
                        "revision": 3,
                    }
                ],
                "next_cursor": None,
                "total": 1,
                "empty_reason": None,
                "applied_filter": "all",
            }

        api.register_handler("library.list", handler)
        try:
            response = api.dispatch(_envelope("library.list", {"filter": "all"}))
            self.assertTrue(response["ok"], response)
        finally:
            api.METHOD_HANDLERS.pop("library.list", None)


if __name__ == "__main__":
    unittest.main()
