"""Contract-set invariants: ids, versions, cross-document references, integrity hashes.

CB-018 amended the set to v2, CB-022 to v3, CB-024 to v4. These tests fail if the new methods,
their payload schemas, the version links, the storage decisions, the pack-check projection or the
documented UX mapping disappear.
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

#: Added in cb.rpc v3 (CB-022): the learning-loop surface CB-008 proved in the backend.
V3_NEW_METHODS = (
    "review.queue",
    "review.action",
    "evidence.inspect",
    "evidence.disputes",
)

#: Added in cb.rpc v4 (CB-024): the installed-pack read surface the pack lifecycle needs.
V4_NEW_METHODS = (
    "pack.list",
    "pack.inspect",
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


def _wire_echoes(node: object, path: str = "") -> list[tuple[str, object]]:
    """Every schema location that pins the wire contract version, with its path."""
    found: list[tuple[str, object]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "contract_version" and isinstance(value, dict) and "const" in value:
                found.append((path or "<root>", value["const"]))
            found.extend(_wire_echoes(value, f"{path}/{key}"))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            found.extend(_wire_echoes(item, f"{path}[{index}]"))
    return found


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

    def test_wire_contract_is_v4(self) -> None:
        self.assertEqual(contracts.WIRE_CONTRACT_ID, "cb.rpc")
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 4)
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, contracts.contract_version("cb.rpc"))
        self.assertTrue(str(contracts.contract("cb.rpc")["$id"]).endswith("/rpc/v4"))
        # Every place the wire version is echoed (both response envelopes, health.get) must agree.
        # A missed constant is an envelope the plugin itself produces and cannot validate.
        echo = _wire_echoes(contracts.contract("cb.rpc"))
        self.assertTrue(echo, "the wire version must be echoed somewhere")
        for path, value in echo:
            self.assertEqual(value, contracts.WIRE_CONTRACT_VERSION, path)

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

    def test_v1_and_v2_documents_are_preserved_on_disk(self) -> None:
        current = contracts.contract("cb.rpc")
        v1 = _document("rpc.v1.json")
        v2 = _document("rpc.v2.json")
        v3 = _document("rpc.v3.json")
        self.assertEqual(v1["x-contract-version"], 1)
        self.assertEqual(str(v1["$id"]), "https://contracts.coursebook.hermes/rpc/v1")
        self.assertEqual(len(v1["$defs"]["method"]["enum"]), 24)
        self.assertEqual(v2["x-contract-version"], 2)
        self.assertEqual(str(v2["$id"]), "https://contracts.coursebook.hermes/rpc/v2")
        self.assertEqual(len(v2["$defs"]["method"]["enum"]), 34)
        self.assertEqual(v3["x-contract-version"], 3)
        self.assertEqual(str(v3["$id"]), "https://contracts.coursebook.hermes/rpc/v3")
        self.assertEqual(len(v3["$defs"]["method"]["enum"]), 38)
        for filename in ("errors.v1.json", "db.v1.json", "jobs.v1.json"):
            self.assertTrue((contracts.CONTRACT_DIR / filename).is_file(), filename)

        # Every superseded method and payload survives verbatim. The only permitted edit is the
        # wire-version constant echoed by health.get, which follows the current contract version.
        for document, version in ((v1, 1), (v2, 2), (v3, 3)):
            for method in document["$defs"]["method"]["enum"]:
                with self.subTest(version=version, method=method):
                    self.assertIn(method, contracts.method_names())
                    carried = json.loads(json.dumps(current["$defs"]["methods"]["properties"][method]))
                    if method == "health.get":
                        carried["response"]["properties"]["contract_version"] = {
                            "const": document["$defs"]["methods"]["properties"][method]
                            ["response"]["properties"]["contract_version"]["const"]
                        }
                    self.assertEqual(document["$defs"]["methods"]["properties"][method], carried)
        self.assertEqual(
            current["$defs"]["methods"]["properties"]["health.get"]["response"]["properties"]
            ["contract_version"]["const"],
            contracts.WIRE_CONTRACT_VERSION,
        )
        # Superseded documents are not edited in place: their own envelopes still say what they said.
        self.assertEqual(v2["$defs"]["envelope_request"]["properties"]["contract_version"]["const"], 2)

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

        # With CB-010 every frozen method has a handler. The seam must still refuse honestly when
        # one is absent, so the absence is simulated instead of asserted about a real method.
        saved = api.METHOD_HANDLERS.pop("pack.preview")
        try:
            response = api.dispatch(_envelope("pack.preview", {"staged_id": "stg_12345678"}))
        finally:
            api.METHOD_HANDLERS["pack.preview"] = saved
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

        # The kernel registers the real handler; swap in a contract-shaped fake and restore it, so
        # this stays a test of the dispatch seam rather than of the database.
        saved = api.METHOD_HANDLERS.get("library.list")
        api.register_handler("library.list", handler)
        try:
            response = api.dispatch(_envelope("library.list", {"filter": "all"}))
            self.assertTrue(response["ok"], response)
        finally:
            if saved is not None:
                api.METHOD_HANDLERS["library.list"] = saved
            else:
                api.METHOD_HANDLERS.pop("library.list", None)


class V3AmendmentTest(unittest.TestCase):
    """CB-022: the additive v3 amendment that gives the review queue and Evidence tab a command path.

    CB-008 implemented the semantics (``coursebook/review.py``, ``coursebook/evidence.py``); these
    tests hold the contract to *that* backend: same field names, no second revision authority, no
    reference answer in the evidence view, and no storage claim that the database does not keep.
    """

    def test_v3_adds_only_the_learning_loop_surface(self) -> None:
        v2_methods = set(_document("rpc.v2.json")["$defs"]["method"]["enum"])
        v3_methods = set(_document("rpc.v3.json")["$defs"]["method"]["enum"])
        self.assertEqual(v3_methods, v2_methods | set(V3_NEW_METHODS))
        self.assertEqual(len(v3_methods), 38)
        # v4 carries every v3 method verbatim and adds only the installed-pack reads.
        self.assertEqual(set(contracts.method_names()), v3_methods | set(V4_NEW_METHODS))
        for method in V3_NEW_METHODS:
            with self.subTest(method=method):
                schema = contracts.method_schema(method)
                for side in ("request", "response"):
                    self.assertEqual(schema[side]["type"], "object", side)
                    if "$ref" in schema[side]:
                        continue  # evidence.disputes.response reuses $defs/evidence_disputes
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    self.assertEqual(_schema_problems(schema[side]), [], f"{method}.{side}")

    def test_v3_claims_no_new_storage_and_no_new_error_code(self) -> None:
        # Decision: the queue is derived from committed evidence + learner action events, and a
        # dispute lives inside the attempt's provenance. Neither gets a table in v3, so cb.db and
        # cb.errors stay at v2 and no migration is implied.
        self.assertEqual(contracts.contract_version("cb.db"), 2)
        self.assertEqual(contracts.contract_version("cb.errors"), 2)
        tables = contracts.contract("cb.db")["tables"]
        for absent in ("review_schedule", "review_items", "disputes"):
            self.assertNotIn(absent, tables)
        v2_codes = set(_document("errors.v2.json")["code_catalog"])
        self.assertEqual(set(contracts.error_codes()), v2_codes)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_review_queue_cannot_hide_a_backlog(self) -> None:
        schema = contracts.method_schema("review.queue")
        request = schema["request"]["properties"]
        self.assertEqual(set(request), {"enrollment_id", "cap", "include_upcoming"})
        # The clock is the backend's: a client cannot age its own queue into looking overdue.
        self.assertNotIn("now", request)
        self.assertLessEqual(request["cap"]["maximum"], 50)
        response = schema["response"]
        self.assertLessEqual(response["properties"]["items"]["maxItems"], 50)
        for field in ("total_due", "total_overdue", "total_scheduled", "upcoming_hidden", "now", "cap"):
            self.assertIn(field, response["required"])
        # The cap may hide rows, never the counts.
        self.assertIn("upcoming_hidden", response["required"])

        item = contracts.contract("cb.rpc")["$defs"]["review_item"]
        for field in ("interval_days", "step", "ladder_days", "last_evidence_at", "due_at", "overdue"):
            self.assertIn(field, item["properties"])
        # A schedule is arithmetic over a declared heuristic, not an attainment prediction.
        forbidden = {"mastery", "retention", "probability", "attain", "attainment_estimate", "score"}
        self.assertEqual(_property_names(item) & forbidden, set())
        contracts.validate_response_payload(
            "review.queue",
            {
                "enrollment_id": "enr_12345678",
                "items": [
                    {
                        "objective_id": "obj_12345678",
                        "title": "Order a drink politely",
                        "ordinal": 1,
                        "evidence_target": "recall",
                        "state": "review_due",
                        "interval_days": 1,
                        "step": 0,
                        "ladder_days": [1, 3, 7, 16, 35],
                        "last_evidence_at": "2026-11-05T00:00:00+00:00",
                        "due_at": "2026-11-06T00:00:00+00:00",
                        "overdue": True,
                        "overdue_days": 0,
                    }
                ],
                "total_due": 1,
                "total_overdue": 1,
                "total_scheduled": 2,
                "upcoming_hidden": 1,
                "now": "2026-11-06T12:00:00+00:00",
                "cap": 10,
            },
        )

    def test_review_action_is_a_revision_fenced_learner_command(self) -> None:
        schema = contracts.method_schema("review.action")
        self.assertEqual(
            set(schema["request"]["properties"]["action"]["enum"]),
            {"snooze", "stretch", "drop", "resume"},
        )
        # Fencing lives in the envelope, once, for every learner command: the payload must not
        # carry a second opinion about the revision, and the result must not echo a third.
        for duplicated in ("expected_revision", "idempotency_key", "revision"):
            self.assertNotIn(duplicated, schema["request"]["properties"])
        self.assertNotIn("revision", schema["response"]["properties"])

        rule = [
            entry
            for entry in contracts.contract("cb.rpc")["$defs"]["envelope_request"]["allOf"]
            if "review.action" in entry.get("if", {}).get("properties", {}).get("method", {}).get("enum", [])
        ]
        self.assertEqual(len(rule), 1, "review.action needs exactly one envelope fence rule")
        self.assertEqual(set(rule[0]["then"]["required"]), {"idempotency_key", "expected_revision"})

        expected = {"idempotency_key", "expected_revision"}
        missing_revision = api.dispatch(_envelope("review.action", {
            "enrollment_id": "enr_12345678",
            "objective_id": "obj_12345678",
            "action": "snooze",
        }, idempotency_key="idem-review-action-1"))
        self.assertFalse(missing_revision["ok"])
        self.assertEqual(missing_revision["error"]["code"], "VALIDATION_FAILED")
        missing_key = api.dispatch(_envelope("review.action", {
            "enrollment_id": "enr_12345678",
            "objective_id": "obj_12345678",
            "action": "snooze",
        }, expected_revision=4))
        self.assertFalse(missing_key["ok"])
        self.assertEqual(missing_key["error"]["code"], "VALIDATION_FAILED")
        fenced = api.dispatch(_envelope("review.action", {
            "enrollment_id": "enr_12345678",
            "objective_id": "obj_12345678",
            "action": "snooze",
        }, expected_revision=4, idempotency_key="idem-review-action-1"))
        self.assertFalse(fenced["ok"])
        # The handler is registered now, so a well-formed fenced envelope reaches it; the
        # unknown enrollment is the handler's refusal, not the seam's.
        self.assertEqual(fenced["error"]["code"], "NOT_FOUND")
        self.assertNotIn("revision", fenced.get("result") or {})
        self.assertTrue(expected <= set(rule[0]["then"]["required"]))

        # drop is a scheduling preference, not mastery evidence: the response says what changed.
        contracts.validate_response_payload(
            "review.action",
            {
                "objective_id": "obj_12345678",
                "action": "drop",
                "recorded_at": "2026-11-06T12:00:00+00:00",
                "state": "independent_evidence",
                "due_at": None,
            },
        )

    def test_evidence_inspect_answers_all_three_layers_and_disputes(self) -> None:
        schema = contracts.method_schema("evidence.inspect")
        self.assertEqual(set(schema["request"]["properties"]), {"enrollment_id", "objective_id", "limit"})
        self.assertLessEqual(schema["request"]["properties"]["limit"]["maximum"], 200)
        self.assertEqual(set(schema["response"]["required"]), {"l1", "l2", "l3", "disputes"})

        defs = contracts.contract("cb.rpc")["$defs"]
        for layer in ("evidence_l1", "evidence_l2", "evidence_l3", "evidence_disputes"):
            self.assertIn(layer, defs)

        # L1 is the raw record: the learner's own answer plus how it was produced.
        for field in ("answer", "answer_hash", "criteria", "provenance", "dispute_count"):
            self.assertIn(field, defs["evidence_attempt"]["properties"])
        for field in ("kind", "is_action", "evidence_class", "layer"):
            self.assertIn(field, defs["evidence_event"]["properties"])

        # L2 must link down to L1 and must not be inferable from an action.
        for field in ("independent", "delayed", "L2_evidence_ids", "attempt_classes"):
            self.assertIn(field, defs["evidence_objective"]["properties"])

        # L3 is a short revisable recommendation, never a persona or a percentage.
        self.assertFalse(defs["evidence_l3"]["properties"]["is_persona"]["const"])
        self.assertIn("is_persona", defs["evidence_l3"]["required"])
        self.assertLessEqual(defs["evidence_l3"]["properties"]["recommendations"]["maxItems"], 5)
        self.assertEqual(
            set(defs["evidence_recommendation"]["properties"]["kind"]["enum"]),
            {"needs_independent_evidence", "hint_contamination", "on_track"},
        )

        # Nothing here can leak a reference answer, rubric internals or a transcript.
        forbidden = {
            "reference_answer", "answer_key", "rubric", "rubric_internals", "grading_output",
            "transcript", "persona", "mastery",
        }
        self.assertEqual(_property_names(schema) & forbidden, set())
        self.assertEqual(_property_names(defs["evidence_l1"]) & forbidden, set())
        self.assertEqual(_property_names(defs["evidence_l3"]) & forbidden, set())

        contracts.validate_response_payload(
            "evidence.inspect",
            {
                "l1": {
                    "enrollment_id": "enr_12345678",
                    "objective_id": None,
                    "attempts": [],
                    "events": [],
                },
                "l2": {"enrollment_id": "enr_12345678", "objective_id": None, "objectives": []},
                "l3": {
                    "enrollment_id": "enr_12345678",
                    "recommendations": [],
                    "as_of": None,
                    "is_persona": False,
                },
                "disputes": {
                    "enrollment_id": "enr_12345678",
                    "disputes": [],
                    "count": 0,
                    "truncated": False,
                },
            },
        )

    def test_evidence_disputes_is_bounded_and_says_when_it_truncates(self) -> None:
        schema = contracts.method_schema("evidence.disputes")
        self.assertEqual(set(schema["request"]["properties"]), {"enrollment_id", "attempt_id", "limit"})
        self.assertLessEqual(schema["request"]["properties"]["limit"]["maximum"], 200)
        disputes = contracts.contract("cb.rpc")["$defs"]["evidence_disputes"]
        self.assertLessEqual(disputes["properties"]["disputes"]["maxItems"], 200)
        for field in ("count", "truncated", "disputes"):
            self.assertIn(field, disputes["required"])

        contracts.validate_response_payload("evidence.disputes", {
            "enrollment_id": "enr_12345678",
            "disputes": [
                {
                    "dispute_id": "dsp_12345678",
                    "attempt_id": "att_12345678",
                    "check_id": "chk_12345678",
                    "verdict": "not_yet",
                    "evidence_class": "cold",
                    "state": "open",
                    "note": "The answer is correct with a different honorific.",
                    "created_at": "2026-11-06T12:00:00+00:00",
                }
            ],
            "count": 1,
            "truncated": False,
        })
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "evidence.disputes", {"enrollment_id": "enr_12345678", "limit": 0}
            )
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "evidence.disputes", {"enrollment_id": "enr_12345678", "limit": 201}
            )

    def test_v3_payloads_are_validated_before_the_handler(self) -> None:
        # A registered handler does not weaken the seam: malformed payloads never reach it.
        for method, payload in (
            ("review.queue", {"enrollment_id": "enr_12345678", "cap": 0}),
            ("review.queue", {"enrollment_id": "enr_12345678", "cap": 51}),
            ("evidence.inspect", {"enrollment_id": "enr_12345678", "limit": 0}),
        ):
            with self.subTest(method=method, payload=payload):
                response = api.dispatch(_envelope(method, payload))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

        # Well-formed payloads reach the wired handler, which refuses the unknown enrollment
        # honestly instead of answering an empty queue / bundle.
        for method, payload in (
            ("review.queue", {"enrollment_id": "enr_12345678"}),
            ("evidence.inspect", {"enrollment_id": "enr_12345678", "objective_id": "obj_12345678"}),
            ("evidence.disputes", {"enrollment_id": "enr_12345678"}),
        ):
            with self.subTest(method=method):
                response = api.dispatch(_envelope(method, payload))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "NOT_FOUND")

        def handler(payload, envelope):
            return 7, {
                "enrollment_id": "enr_12345678",
                "items": [],
                "total_due": 0,
                "total_overdue": 0,
                "total_scheduled": 0,
                "upcoming_hidden": 0,
                "now": "2026-11-06T12:00:00+00:00",
                "cap": 10,
            }

        # Swap in a contract-shaped fake and restore the kernel's real handler afterwards, so
        # this stays a test of the dispatch seam rather than of the database.
        saved = api.METHOD_HANDLERS.get("review.queue")
        api.register_handler("review.queue", handler)
        try:
            response = api.dispatch(_envelope("review.queue", {"enrollment_id": "enr_12345678"}))
            self.assertTrue(response["ok"], response)
            self.assertEqual(response["contract_version"], contracts.WIRE_CONTRACT_VERSION)
            self.assertEqual(response["revision"], 7)
        finally:
            if saved is not None:
                api.METHOD_HANDLERS["review.queue"] = saved
            else:
                api.METHOD_HANDLERS.pop("review.queue", None)

    def test_docs_publish_the_v3_surface_and_the_handler_contract(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for method in V3_NEW_METHODS:
            self.assertIn(method, text, f"CONTRACTS.md does not document {method}")
        for needle in (
            "review.py",              # the implementer file Cinder wires
            "evidence.py",
            "grading_provenance_json",  # disputes stay inline; no v3 table
            "derived",                  # the queue has no table of its own
            "pack.list",                # explicitly deferred to v4, not a v3 extension
        ):
            self.assertIn(needle, text, f"CONTRACTS.md does not record the v3 decision on {needle!r}")


class V4AmendmentTest(unittest.TestCase):
    """CB-024: the installed-pack read surface, and the frozen pack-check projection.

    CB-010 wired the pack lifecycle (preview/import/export/delete) but the UI could only re-list
    files from a manifest it had just previewed in the same session: ``library.list`` enumerates
    enrollments, and ``pack.preview`` requires a fresh upload grant. An installed pack therefore had
    no wire read. v4 is additive over v3: two read-only methods and nothing else.
    """

    def test_v4_adds_only_the_installed_pack_read_surface(self) -> None:
        v3_methods = set(_document("rpc.v3.json")["$defs"]["method"]["enum"])
        self.assertEqual(set(contracts.method_names()), v3_methods | set(V4_NEW_METHODS))
        self.assertEqual(len(contracts.method_names()), 40)
        for method in V4_NEW_METHODS:
            with self.subTest(method=method):
                schema = contracts.method_schema(method)
                for side in ("request", "response"):
                    self.assertEqual(schema[side]["type"], "object", side)
                    if "$ref" in schema[side]:
                        continue  # pack.inspect.response reuses $defs/pack_inspection
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    self.assertEqual(_schema_problems(schema[side]), [], f"{method}.{side}")

    def test_pack_list_cannot_return_a_path_an_enrollment_claim_or_a_manifest(self) -> None:
        item = contracts.contract("cb.rpc")["$defs"]["pack_list_item"]
        names = _property_names(item)
        # The library index stores an absolute directory; it is storage, not a wire field.
        for forbidden in ("directory", "path", "local_path", "file_path", "manifest"):
            self.assertNotIn(forbidden, names)
        # Enrollment facts stay with library.list. A pack row is enrollment-agnostic by design.
        for forbidden in ("enrollment_id", "course_id", "enrolled", "course_count", "status"):
            self.assertNotIn(forbidden, names)
        # A list row must still carry the revision pack.delete fences on, or deletion is unreachable.
        self.assertIn("revision", item["required"])
        for field in (
            "pack_id", "pack_version", "content_hash", "recipe", "source", "state",
            "installed_at", "file_count", "expanded_bytes", "license",
        ):
            self.assertIn(field, item["required"])

        contracts.validate_definition("cb.rpc", "pack_list_item", _pack_item())
        with self.assertRaises(contracts.ContractError):
            contracts.validate_definition(
                "cb.rpc", "pack_list_item", _pack_item(directory="/var/lib/coursebook/packs")
            )

    def test_pack_list_is_bounded_and_says_when_it_truncated(self) -> None:
        schema = contracts.method_schema("pack.list")
        request = schema["request"]["properties"]
        self.assertEqual(set(request), {"pack_id", "pack_version", "filter", "limit"})
        self.assertLessEqual(request["limit"]["maximum"], 200)
        self.assertEqual(
            set(request["filter"]["enum"]), {"all", "installed", "frozen", "removed"}
        )
        response = schema["response"]
        self.assertLessEqual(response["properties"]["items"]["maxItems"], 200)
        for field in ("items", "total", "truncated", "applied_filter"):
            self.assertIn(field, response["required"])

        contracts.validate_response_payload(
            "pack.list",
            {
                "items": [_pack_item()],
                "total": 3,
                "truncated": True,
                "applied_filter": "all",
            },
        )
        # A truncated list must never look like a short library: total is the full count.
        contracts.validate_response_payload(
            "pack.list",
            {"items": [], "total": 0, "truncated": False, "applied_filter": "installed"},
        )

    def test_pack_inspect_reads_an_installed_pack_without_a_grant(self) -> None:
        schema = contracts.method_schema("pack.inspect")
        self.assertEqual(set(schema["request"]["required"]), {"pack_id", "pack_version"})
        self.assertNotIn("staged_id", schema["request"]["properties"])
        inspection = contracts.contract("cb.rpc")["$defs"]["pack_inspection"]
        self.assertEqual(set(inspection["required"]), {"pack", "manifest", "integrity", "trust"})
        integrity = inspection["properties"]["integrity"]
        self.assertEqual(
            set(integrity["required"]), {"hashes_match", "file_count", "expanded_bytes"}
        )
        labels = inspection["properties"]["trust"]["properties"]["labels"]
        self.assertLessEqual(labels["maxItems"], 4)
        contracts.validate_response_payload("pack.inspect", _inspection())
        # hashes_match is the honest boolean, not a verdict: drifting content must be reportable.
        self.assertFalse(_inspection(hashes_match=False)["integrity"]["hashes_match"])
        contracts.validate_response_payload("pack.inspect", _inspection(hashes_match=False))

    def test_pack_state_and_source_enums_come_from_the_storage_authority(self) -> None:
        packs = contracts.contract("cb.db")["tables"]["packs"]["columns"]
        item = contracts.contract("cb.rpc")["$defs"]["pack_list_item"]["properties"]
        self.assertEqual(set(item["state"]["enum"]), set(packs["state"]["enum"]))
        self.assertEqual(set(item["source"]["enum"]), set(packs["source"]["enum"]))
        # 'removed' is reserved by the migration and is not produced by this build; the contract
        # still names it so a future writer does not need a wire bump.
        self.assertIn("removed", item["state"]["enum"])

    def test_v4_claims_no_new_storage_and_no_new_error_code(self) -> None:
        # Both methods read what adoption and pack.delete already write: the library index and the
        # packs row. No table, no column, no migration, no error code.
        self.assertEqual(contracts.contract_version("cb.db"), 2)
        self.assertEqual(contracts.contract_version("cb.errors"), 2)
        v2_codes = set(_document("errors.v2.json")["code_catalog"])
        self.assertEqual(set(contracts.error_codes()), v2_codes)
        # The projection is a new contract id, not a new version of cb.pack: the manifest is
        # unchanged, only the derivation from it is frozen.
        self.assertEqual(contracts.contract_version("cb.pack"), 1)
        self.assertEqual(contracts.contract_version("cb.projection"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_v4_payloads_validate_before_any_handler_and_refuse_a_path(self) -> None:
        for method, payload in (
            ("pack.inspect", {"pack_id": "japanese-affection-context-l0"}),
            ("pack.list", {"limit": 0}),
            ("pack.list", {"limit": 201}),
            ("pack.list", {"filter": "deleted"}),
            ("pack.list", {"pack_version": "not-a-version"}),
        ):
            with self.subTest(method=method, payload=payload):
                response = api.dispatch(_envelope(method, payload))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

        for method, payload in (
            ("pack.list", {}),
            ("pack.inspect", {"pack_id": "japanese-affection-context-l0", "pack_version": "1.0.0"}),
        ):
            with self.subTest(method=method):
                response = api.dispatch(_envelope(method, payload))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "NOT_IMPLEMENTED")

        def leaking_handler(payload, envelope):
            item = _pack_item()
            item["directory"] = "/var/lib/coursebook/library/packs"
            return 0, {
                "items": [item],
                "total": 1,
                "truncated": False,
                "applied_filter": "all",
            }

        api.register_handler("pack.list", leaking_handler)
        try:
            response = api.dispatch(_envelope("pack.list", {}))
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")
            self.assertIn("directory", response["error"]["message"])
        finally:
            api.METHOD_HANDLERS.pop("pack.list", None)

    def test_docs_publish_the_v4_surface_and_the_projection_authority(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for method in V4_NEW_METHODS:
            self.assertIn(method, text, f"CONTRACTS.md does not document {method}")
        for needle in (
            "cb.projection",
            "check_spec_from_pack_check",
            "objective_criteria",
            "pack_delete",  # the fence the list revision feeds
            "previewCache",  # the CB-010 workaround this amendment removes
        ):
            self.assertIn(needle, text, f"CONTRACTS.md does not record the v4 decision on {needle!r}")


class ProjectionContractTest(unittest.TestCase):
    """CB-024: the pack-check projection is frozen as contract text, not importer code.

    Import is the first consumer of the mapping. Parent Studio generation and community upload
    review will be the second and third, so the rules live in ``cb.projection`` and the importer
    applies them. The vectors below are the conformance set the implementation must satisfy.
    """

    def projection(self) -> dict:
        return contracts.contract("cb.projection")

    def test_projection_is_a_frozen_contract_at_v1(self) -> None:
        document = self.projection()
        self.assertEqual(document["x-contract-id"], "cb.projection")
        self.assertEqual(document["x-contract-version"], 1)
        self.assertEqual(document["$id"], "https://contracts.coursebook.hermes/projection/v1")
        self.assertEqual(document["x-status"], "frozen")
        self.assertEqual(contracts.audit_contracts(), [])

    def test_every_example_validates_against_the_frozen_schemas(self) -> None:
        document = self.projection()
        reasons = {
            document["recipe_gate"]["reason"],
            "import_audit_failed",
            "declared_audit_failed",
        }
        problems = {rule["problem"] for rule in document["audit_rules"]["rules"]}
        seen_kinds = set()
        for example in document["examples"]:
            with self.subTest(example=example["name"]):
                expectation = example["expect"]
                seen_kinds.add(expectation["kind"])
                if expectation["kind"] == "spec":
                    contracts.validate_definition(
                        "cb.projection", "check_spec", expectation["spec"], what=example["name"]
                    )
                    spec = expectation["spec"]
                    self.assertEqual(spec["audit_state"], "passed")
                    self.assertEqual(spec["audit_source"], "import_automated_audit")
                    self.assertEqual(
                        spec["rubric"]["construct"], example["check"]["evidence_target"]
                    )
                    self.assertIn("locale", spec)
                else:
                    self.assertIn(expectation["reason"], reasons | {"declared_audit_failed"})
                    self.assertTrue(set(expectation["problems"]) <= problems)
        # The vectors must cover both outcomes, or the conformance set proves nothing.
        self.assertEqual(seen_kinds, {"spec", "none"})

    def test_known_divergences_have_vectors(self) -> None:
        document = self.projection()
        vectors = {example.get("divergence") for example in document["examples"]}
        for divergence in document["x-known-divergences"]:
            with self.subTest(divergence=divergence["id"]):
                self.assertIn(divergence["id"], vectors)
                self.assertEqual(divergence["status"], "open")
                self.assertTrue(divergence["resolution"])

    def test_objective_examples_validate_and_keep_the_first_graded_check(self) -> None:
        for example in self.projection()["objective_examples"]:
            with self.subTest(example=example["name"]):
                criteria = example["expect"]
                self.assertEqual(criteria[0]["id"], "pack_objective")
                self.assertEqual(criteria[0]["pack_objective_id"], example["objective"]["objective_id"])
                for criterion in criteria:
                    contracts.validate_definition("cb.projection", "objective_criterion", criterion)
                graded = [entry for entry in criteria if "check_spec" in entry]
                withheld = [entry for entry in criteria if entry.get("check_spec_withheld")]
                self.assertEqual(
                    len(graded) + len(withheld), len(example["objective"]["checks"])
                )
                if example["recipe"] == "parent":
                    self.assertEqual(graded, [], "a parent pack must never yield a graded check")
                else:
                    self.assertEqual(
                        graded[0]["id"], example["objective"]["checks"][0]["check_id"],
                        "the first gradable check is the one the objective opens",
                    )

    def test_rules_are_named_ordered_and_total(self) -> None:
        document = self.projection()
        rules = document["audit_rules"]["rules"]
        self.assertEqual([rule["id"] for rule in rules], ["R1", "R2", "R3", "R4", "R5", "R6"])
        self.assertEqual([rule["name"] for rule in rules], [
            "stimulus_present", "reference_present", "rubric_present",
            "reference_not_in_stimulus", "alternatives_add_a_form", "declared_audit_not_failed",
        ])
        for rule in rules:
            with self.subTest(rule=rule["id"]):
                self.assertTrue(rule["passes_when"])
                self.assertTrue(rule["problem"])
        # The projection is total over a schema-valid manifest check: every required field is
        # either read or explicitly accounted for as deliberately unread (the check's own version).
        pack_check = contracts.contract("cb.pack")["properties"]["objectives"]["items"]["properties"]["checks"]["items"]
        self.assertTrue(set(document["inputs"]["fields_read"]) <= set(pack_check["properties"]))
        unread = set(document["inputs"]["fields_deliberately_unread"])
        self.assertTrue(set(pack_check["required"]) <= set(document["inputs"]["fields_read"]) | unread)
        self.assertIn("version", unread)

    def test_declared_failure_cannot_become_gradable(self) -> None:
        # A pack's own audit_state may refuse a check and may never grant one.
        example = next(
            item for item in self.projection()["examples"] if item["name"] == "declared_failed_withholds"
        )
        self.assertEqual(example["check"]["audit_state"], "failed")
        self.assertEqual(example["expect"]["kind"], "none")
        self.assertEqual(example["expect"]["reason"], "declared_audit_failed")
        # ... and a pack cannot buy gradability by declaring 'passed' either: the deterministic
        # audit in R1-R5 is the only gate, which the reference_leaked_into_stimulus vector shows.
        leaked = next(
            item for item in self.projection()["examples"] if item["name"] == "reference_leaked_into_stimulus"
        )
        self.assertEqual(leaked["check"]["audit_state"], "passed")
        self.assertEqual(leaked["expect"]["kind"], "none")

    def test_projection_never_carries_a_learner_path_or_answer_authority(self) -> None:
        document = self.projection()
        spec = document["$defs"]["check_spec"]
        names = _property_names(spec)
        for forbidden in (
            "learner_label", "enrollment_id", "course_id", "attempt_id", "path", "local_path",
            "provider", "model", "persona", "mastery", "pass_threshold",
        ):
            self.assertNotIn(forbidden, names)
        self.assertIn("check_id", document["projection"]["never_produced"])
        self.assertIn("version", document["projection"]["never_produced"])
        self.assertIn("criterion_id", document["projection"]["never_produced"])
        # An exact reference answer is the answer key. It lives in the spec the grader reads and
        # nowhere in this contract's response shapes; no RPC response may carry the spec.
        for method in contracts.method_names():
            response_names = _property_names(contracts.method_schema(method)["response"])
            self.assertNotIn("check_spec", response_names, method)
            self.assertNotIn("reference_answer", response_names, method)


def _pack_item(**overrides) -> dict:
    item = {
        "pack_id": "japanese-affection-context-l0",
        "pack_version": "1.0.0",
        "content_hash": "sha256:" + "a" * 64,
        "recipe": "casual",
        "source": "local",
        "state": "installed",
        "revision": 0,
        "installed_at": "2026-11-06T00:00:00Z",
        "file_count": 12,
        "expanded_bytes": 40213,
        "license": {"id": "CC-BY-4.0", "redistribution": "allowed"},
    }
    item.update(overrides)
    return item


def _inspection(*, hashes_match: bool = True) -> dict:
    return {
        "pack": _pack_item(),
        "manifest": {"pack_id": "japanese-affection-context-l0", "pack_version": "1.0.0"},
        "integrity": {
            "hashes_match": hashes_match,
            "file_count": 12,
            "expanded_bytes": 40213,
        },
        "trust": {"labels": ["integrity_verified", "automated_checks_passed"]},
    }


if __name__ == "__main__":
    unittest.main()

