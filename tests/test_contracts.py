"""Contract-set invariants: ids, versions, cross-document references, integrity hashes.

CB-018 amended the set to v2, CB-022 to v3, CB-024 to v4. These tests fail if the new methods,
their payload schemas, the version links, the storage decisions, the pack-check projection or the
documented UX mapping disappear.
"""

from __future__ import annotations

import hashlib
import json
import unittest

from coursebook import api, contracts
from tests.kernel_support import KernelCase

#: Handler registration happens when a module is imported, and the dispatch seam answers
#: NOT_IMPLEMENTED until then. Importing the two registering modules here keeps this module's
#: seam assertions independent of test discovery order (they used to depend on another module
#: having imported them first).
import coursebook.domain  # noqa: E402,F401  (registers the kernel methods)
import coursebook.pack_flow  # noqa: E402,F401  (registers the pack methods)

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

#: Added in cb.rpc v5 (CB-026): the three surfaces the Desktop learning workspace needs.
V5_NEW_METHODS = (
    "course.outline",
    "check.get",
    "lesson.assist",
)

#: Added in cb.rpc v6 (CB-011): the Parent Studio authoring surface (brief, draft edit, final
#: approval, blueprint read, authored export, reflections).
V6_NEW_METHODS = (
    "parent.brief.create",
    "parent.brief.get",
    "parent.plan.edit",
    "parent.final.approve",
    "parent.blueprint.read",
    "parent.export",
    "parent.reflection.record",
    "parent.reflection.list",
)

#: Added in cb.rpc v7 (CB-015 residual): the one wire command that can reach the stale-source state.
V7_NEW_METHODS = (
    "source.revalidate",
)

#: Added in cb.rpc v9 (M3-B1): the bounded pronunciation practice loop. Two commands, no grade.
V9_NEW_METHODS = (
    "pronunciation.attempt",
    "pronunciation.dispute",
)


def _document(filename: str) -> dict:
    return json.loads((contracts.CONTRACT_DIR / filename).read_text(encoding="utf-8"))


#: Fields cb.rpc v8 appended to an existing method. Additive means no v7 field moved, so the
#: carried-over comparisons remove exactly these before comparing against the earlier snapshot.
V8_ADDED_METHOD_FIELDS: dict[str, tuple[str, ...]] = {"lesson.page": ("document",)}

#: Fields cb.rpc v10 appended to a shipped method's *request*. They are optional and were absent
#: from every earlier snapshot, so the carried-over comparisons remove exactly these.
V10_ADDED_METHOD_FIELDS: dict[str, tuple[str, ...]] = {
    "course.create": ("level", "subject_domain", "scope"),
}

#: Fields cb.rpc v11 appended to a shipped method (request and optional response facts). Absent
#: from every earlier snapshot, so the carried-over comparisons remove exactly these too.
V11_ADDED_REQUEST_FIELDS: dict[str, tuple[str, ...]] = {
    "lesson.begin": ("acknowledge_prerequisites",),
    "check.open": ("acknowledge_prerequisites",),
}
V11_ADDED_RESPONSE_FIELDS: dict[str, tuple[str, ...]] = {
    "lesson.begin": ("prerequisite_state",),
    "check.open": ("prerequisite_state",),
}


def _normalise_refresh_refs(payload: dict) -> dict:
    """Undo a pure cross-document reference refresh for a carried-over comparison.

    v11 moved ``cb.rpc``'s job-state references from ``cb.jobs`` v2 to v3: v3 is a reference-only
    refresh of the same states. Historical carried-over tests compare payload shape, not the
    version number inside a ``$ref``, so the current reference is mapped back to the snapshot's.
    """
    raw = json.dumps(payload)
    raw = raw.replace(
        "https://contracts.coursebook.hermes/jobs/v3#",
        "https://contracts.coursebook.hermes/jobs/v2#",
    )
    return json.loads(raw)


def _carried_payload(payload: dict, method: str) -> dict:
    carried = json.loads(json.dumps(payload))
    for field in V8_ADDED_METHOD_FIELDS.get(method, ()):
        carried["response"]["properties"].pop(field, None)
        required = carried["response"].get("required") or []
        if field in required:
            required.remove(field)
    for field in V11_ADDED_RESPONSE_FIELDS.get(method, ()):
        carried["response"]["properties"].pop(field, None)
        required = carried["response"].get("required") or []
        if field in required:
            required.remove(field)
    request = carried["request"]
    for field in V10_ADDED_METHOD_FIELDS.get(method, ()):
        (request.get("properties") or {}).pop(field, None)
    for field in V11_ADDED_REQUEST_FIELDS.get(method, ()):
        (request.get("properties") or {}).pop(field, None)
    if method == "jobs.create":
        # v10 applies a closed `$defs/plan_brief` to `kind = "plan"`; the open bounded brief
        # object every earlier snapshot froze is untouched.
        request.pop("allOf", None)
    return _normalise_refresh_refs(carried)


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

    def test_wire_contract_is_current(self) -> None:
        self.assertEqual(contracts.WIRE_CONTRACT_ID, "cb.rpc")
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 11)
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, contracts.contract_version("cb.rpc"))
        self.assertTrue(str(contracts.contract("cb.rpc")["$id"]).endswith("/rpc/v11"))
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
                    carried = _carried_payload(
                        current["$defs"]["methods"]["properties"][method], method
                    )
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
        self.assertEqual(
            state_ref,
            contracts.contract_uri("cb.jobs") + "#/$defs/job_state",
        )
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
        # The v2 snapshot, not the live inventory: cb.db moved on to v3 under CB-011, and this
        # test is a fact about what v2 froze.
        db = _document("db.v2.json")
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
        # v4/v5 carry every v3 method verbatim, so the chain is append-only. (v6 appended the
        # Parent Studio family afterwards; the live inventory is asserted in V6AmendmentTest.)
        v5_methods = set(_document("rpc.v5.json")["$defs"]["method"]["enum"])
        self.assertEqual(v5_methods, v3_methods | set(V4_NEW_METHODS) | set(V5_NEW_METHODS))
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
        # dispute lives inside the attempt's provenance. Neither gets a table, so cb.db stayed at
        # the v2 snapshot v3 froze against and no migration was implied. (cb.db has since moved to
        # v3 for CB-011's Parent Studio tables; that later delta is CB-011's, not this one's.)
        self.assertEqual(_document("db.v2.json")["x-contract-version"], 2)
        self.assertEqual(contracts.contract_version("cb.errors"), 3)
        tables = _document("db.v2.json")["tables"]
        for absent in ("review_schedule", "review_items", "disputes"):
            self.assertNotIn(absent, tables)
        v2_codes = set(_document("errors.v2.json")["code_catalog"])
        # cb.errors moved to v3 for cb.rpc v11's PREREQUISITE_UNMET; this amendment added none.
        self.assertEqual(set(contracts.error_codes()), v2_codes | {"PREREQUISITE_UNMET"})
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

    def test_v3_payloads_are_validated_before_any_handler(self) -> None:
        for method, payload in (
            ("review.queue", {"enrollment_id": "enr_12345678", "cap": 0}),
            ("review.queue", {"enrollment_id": "enr_12345678", "cap": 51}),
            ("evidence.inspect", {"enrollment_id": "enr_12345678", "limit": 0}),
        ):
            with self.subTest(method=method, payload=payload):
                response = api.dispatch(_envelope(method, payload))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

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
        v4_methods = set(_document("rpc.v4.json")["$defs"]["method"]["enum"])
        # v5 is the snapshot that carries v4 verbatim; the live inventory (v6) is asserted in
        # V6AmendmentTest, where the Parent Studio family is the only later delta.
        v5_methods = set(_document("rpc.v5.json")["$defs"]["method"]["enum"])
        self.assertEqual(v5_methods, v4_methods | set(V5_NEW_METHODS))
        self.assertEqual(len(v5_methods), 43)
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
        # packs row. No table, no column, no migration, no error code — the storage snapshot this
        # amendment froze against is cb.db v2.
        self.assertEqual(_document("db.v2.json")["x-contract-version"], 2)
        self.assertEqual(contracts.contract_version("cb.errors"), 3)
        v2_codes = set(_document("errors.v2.json")["code_catalog"])
        # cb.errors moved to v3 for cb.rpc v11's PREREQUISITE_UNMET; this amendment added none.
        self.assertEqual(set(contracts.error_codes()), v2_codes | {"PREREQUISITE_UNMET"})
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
                contracts.validate_request_payload(method, payload)

        def leaking_handler(payload, envelope):
            item = _pack_item()
            item["directory"] = "/var/lib/coursebook/library/packs"
            return 0, {
                "items": [item],
                "total": 1,
                "truncated": False,
                "applied_filter": "all",
            }

        saved = api.METHOD_HANDLERS.get("pack.list")
        api.register_handler("pack.list", leaking_handler)
        try:
            response = api.dispatch(_envelope("pack.list", {}))
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")
            self.assertIn("directory", response["error"]["message"])
        finally:
            if saved is not None:
                api.METHOD_HANDLERS["pack.list"] = saved
            else:
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
                    self.assertIn(expectation["reason"], reasons)
                    self.assertTrue(set(expectation["problems"]) <= problems)
        # The vectors must cover both outcomes, or the conformance set proves nothing.
        self.assertEqual(seen_kinds, {"spec", "none"})

    def test_divergence_record_is_closed_and_each_entry_keeps_its_vector(self) -> None:
        document = self.projection()
        vectors = {example.get("divergence") for example in document["examples"]}
        # CB-025 landed both importer fixes (commits 577d268, 725ffbf). The record stays as
        # provenance, so every entry must say it is resolved and name the commit that did it —
        # an entry drifting back to "open" without an importer change fails here.
        for divergence in document["x-known-divergences"]:
            with self.subTest(divergence=divergence["id"]):
                self.assertIn(divergence["id"], vectors)
                self.assertIn(divergence["status"], {"resolved", "fixed"})
                self.assertTrue(divergence["resolved_by"])
                self.assertTrue(divergence["resolution"].startswith("Resolved."))

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
        # R6 is an audit rule like the rest: the same import_audit_failed reason, with the
        # rule's own problem string. There is no separate 'declared_audit_failed' vocabulary.
        self.assertEqual(example["expect"]["reason"], "import_audit_failed")
        self.assertEqual(
            example["expect"]["problems"], ["the pack declares this check failed its own audit"]
        )
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


#: Byte hashes of the superseded RPC documents. Pinned so "additive" is a fact about the files,
#: not a claim about the diff: history is not edited in place, so these can never legitimately move.
FROZEN_RPC_SHA256 = {
    "rpc.v1.json": "sha256:de5f65360da0d7c4a0065a1c4c9d69f5d0dec48742d5650bc396ff71f22d1997",
    "rpc.v2.json": "sha256:4afc3c5fe0248c32733884dc68295f4a3aff916df7782f437945a8862e4352f4",
    "rpc.v3.json": "sha256:006232ae71b642fd44d6461ce0e0f83f7fd40cf6dfeb4b0730fc4283cb6aad9a",
    "rpc.v4.json": "sha256:b910c5e4a02015db6d35131e283b10582a4a8d400a24b9f3a6f8b242b538ad49",
    "rpc.v5.json": "sha256:e4dfea0e031b32698e9e354f640b25acfcdf68244ec819a3cedc375e8bd8b156",
    "rpc.v6.json": "sha256:7fa0ccfe5553c43b249ea370d87fd993e32047092f5be5471b9ddd0dc2bf3397",
    "rpc.v7.json": "sha256:3862b55e6853a93e064f8ee9475b5dd464ae32e9221d04e527f498fc6cc41f64",
    "rpc.v8.json": "sha256:02df1a21823e086926f6df7be6b9db93066243d676d34c4cff6329504c94e6ae",
    "rpc.v9.json": "sha256:f0484a930c9a1666d54d86cb0e80443b611cb166ae4ecdc4676ed82784475812",
    "rpc.v10.json": "sha256:3567b5149531fe51f6cbe9d44698dfdab12a1cacb24949695dd0244bef285618",
}

#: The superseded storage snapshots stay on disk and stay byte-identical: a later amendment is a
#: new file, never an edit to one a client or a migration already recorded.
FROZEN_DB_SHA256 = {
    "db.v1.json": "sha256:e4ad371ba64a8dc76a3055a46c7a127160028d17c36ec07413e542d0f9a8d53a",
    "db.v2.json": "sha256:873fd56c4ea0a7229721ce9eb6065dd2a9370cc5563099852c88858e0413c0d7",
    "db.v3.json": "sha256:4c0569e4505f12e5862db6d63effe7363da64c1e0e0c837a49ed278b08ab48b6",
    "db.v4.json": "sha256:ef243b2db653c49e90b35b08746e2283409b609cb310e9b2185f8fa898cebcde",
    "db.v5.json": "sha256:3a1a6f0155130523fcbecbb64bfa23eb709666f888d20486f15dc6ce4d18ea5b",
    "db.v6.json": "sha256:c142f79143198565162d72fa9691563fa41d5691a77d7e275e8aab69037d2e27",
}


class V5AmendmentTest(unittest.TestCase):
    """CB-026: the three surfaces CB-009 cannot build without, and what they may never return.

    The Desktop learning workspace may not read SQLite and may not invent a second authority, so
    the Textbook/Plan index (``course.outline``), the structured check prompt (``check.get``) and
    the pane's Hint/Show answer events (``lesson.assist``) have to be commands. All three read or
    write rows ``cb.db`` v2 already defines; v5 adds no storage and no error code.
    """

    def test_superseded_rpc_documents_are_byte_identical(self) -> None:
        for filename, expected in FROZEN_RPC_SHA256.items():
            with self.subTest(filename=filename):
                digest = hashlib.sha256((contracts.CONTRACT_DIR / filename).read_bytes()).hexdigest()
                self.assertEqual(f"sha256:{digest}", expected)
        for version in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            # Not in the inventory, and not silently repurposed: history stays history.
            self.assertNotIn(f"rpc.v{version}.json", contracts.CONTRACT_FILES.values())
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v11.json")

    def test_v5_adds_only_the_outline_check_and_assist_surface(self) -> None:
        # The v5 snapshot, not the live inventory: v6 appended the Parent Studio family afterwards.
        v4 = _document("rpc.v4.json")
        v4_methods = list(v4["$defs"]["method"]["enum"])
        self.assertEqual(len(v4_methods), 40)
        v5 = _document("rpc.v5.json")
        v5_methods = list(v5["$defs"]["method"]["enum"])
        self.assertEqual(set(v5_methods), set(v4_methods) | set(V5_NEW_METHODS))
        self.assertEqual(len(v5_methods), 43)
        # Append-only: the v4 order survives as a prefix, so a client diffing enums sees no churn.
        self.assertEqual(v5_methods[: len(v4_methods)], v4_methods)
        for method in V5_NEW_METHODS:
            with self.subTest(method=method):
                schema = contracts.method_schema(method)
                for side in ("request", "response"):
                    self.assertEqual(schema[side]["type"], "object", side)
                    if "oneOf" in schema[side]:
                        for branch in schema[side]["oneOf"]:
                            self.assertIs(branch.get("additionalProperties"), False, side)
                            self.assertEqual(_schema_problems(branch), [], f"{method}.{side}")
                        continue
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    self.assertEqual(_schema_problems(schema[side]), [], f"{method}.{side}")

    def test_every_v1_to_v4_method_schema_is_carried_over_verbatim(self) -> None:
        current = contracts.contract("cb.rpc")
        for version in (1, 2, 3, 4):
            document = _document(f"rpc.v{version}.json")
            for method in document["$defs"]["method"]["enum"]:
                with self.subTest(version=version, method=method):
                    original = document["$defs"]["methods"]["properties"][method]
                    carried = _carried_payload(
                        current["$defs"]["methods"]["properties"][method], method
                    )
                    if method == "health.get":
                        carried["response"]["properties"]["contract_version"] = {
                            "const": original["response"]["properties"]["contract_version"]["const"]
                        }
                    self.assertEqual(original, carried)
            # The superseded envelope still says what it said when it was shipped.
            self.assertEqual(
                document["$defs"]["envelope_request"]["properties"]["contract_version"]["const"], version
            )
        # The one thing that may move: the wire echo, which must equal the current version.
        self.assertEqual(
            current["$defs"]["methods"]["properties"]["health.get"]["response"]["properties"]
            ["contract_version"]["const"],
            contracts.WIRE_CONTRACT_VERSION,
        )
        for path, value in _wire_echoes(current):
            self.assertEqual(value, contracts.WIRE_CONTRACT_VERSION, path)

    def test_course_outline_is_a_bounded_read_of_the_current_plan(self) -> None:
        schema = contracts.method_schema("course.outline")
        request = schema["request"]
        self.assertEqual(set(request["required"]), {"enrollment_id"})
        self.assertEqual(set(request["properties"]), {"enrollment_id", "limit"})
        self.assertLessEqual(request["properties"]["limit"]["maximum"], 400)
        # Read path: no fence and no idempotency key of its own; both live in the envelope only.
        for forbidden in ("expected_revision", "idempotency_key", "revision", "cursor"):
            self.assertNotIn(forbidden, request["properties"])

        response = schema["response"]
        self.assertEqual(
            set(response["required"]), {"enrollment_id", "plan", "objectives", "total", "truncated"}
        )
        self.assertLessEqual(response["properties"]["objectives"]["maxItems"], 400)
        # A short list must never hide a long course: total is the full count.
        self.assertIn({"type": "null"}, response["properties"]["plan"]["oneOf"])

        plan = contracts.contract("cb.rpc")["$defs"]["outline_plan"]
        self.assertEqual(set(plan["required"]), {"plan_id", "version", "state", "plan_hash"})
        self.assertEqual(set(plan["properties"]["state"]["enum"]), {"draft", "approved", "superseded"})

        objective = contracts.contract("cb.rpc")["$defs"]["outline_objective"]
        self.assertEqual(
            set(objective["required"]),
            {
                "objective_id",
                "ordinal",
                "title",
                "evidence_target",
                "state",
                "check_state",
                "attempt_count",
                "independent",
                "last_opened_at",
            },
        )
        self.assertEqual(
            set(objective["properties"]["check_state"]["enum"]), {"none", "open", "closed", "superseded"}
        )
        self.assertEqual(objective["properties"]["independent"]["type"], "boolean")

    def test_check_get_serves_the_stimulus_and_never_the_key(self) -> None:
        schema = contracts.method_schema("check.get")
        branches = schema["request"]["oneOf"]
        self.assertEqual(len(branches), 2)
        self.assertEqual({frozenset(branch["required"]) for branch in branches},
                         {frozenset({"enrollment_id", "check_id"}),
                          frozenset({"enrollment_id", "objective_id"})})
        response = schema["response"]
        self.assertEqual(
            set(response["required"]),
            {"check_id", "objective_id", "check_version", "evidence_target", "state",
             "audit_state", "stimulus", "attempt_count"},
        )
        self.assertEqual(set(response["properties"]["state"]["enum"]), {"open", "closed", "superseded"})
        self.assertEqual(set(response["properties"]["audit_state"]["enum"]), {"pending", "passed", "failed"})

        stimulus = contracts.contract("cb.rpc")["$defs"]["check_stimulus"]
        self.assertEqual(set(stimulus["required"]), {"prompt", "format", "choices"})
        self.assertEqual(set(stimulus["properties"]["format"]["enum"]),
                         {"text", "selection", "verification"})
        self.assertLessEqual(stimulus["properties"]["choices"]["maxItems"], 8)
        # `items` is the structured checklist: optional on the wire (an older check has none) but
        # bounded and closed, so a label cannot be served as an unbounded blob or carry a key.
        self.assertNotIn("items", stimulus["required"])
        items = stimulus["properties"]["items"]
        self.assertEqual(items["maxItems"], 24)
        self.assertFalse(items["items"]["additionalProperties"])
        self.assertEqual(set(items["items"]["required"]), {"id", "label"})
        self.assertLessEqual(items["items"]["properties"]["label"]["maxLength"], 200)
        # The prompt bound must cover what storage can hold: a pack check's stimulus is up to 8000
        # characters in cb.pack, and it is copied into checks.stimulus_json verbatim. A tighter
        # bound would make a legitimate imported check unrenderable.
        self.assertGreaterEqual(stimulus["properties"]["prompt"]["maxLength"], 8000)

        # The answer key and the rubric are not on this wire, in any spelling.
        names = _property_names(response) | _property_names(stimulus)
        for forbidden in (
            "reference_answer", "reference", "reference_json", "rubric", "rubric_json",
            "accepted_answers", "accepted_alternatives", "grading_provenance", "check_spec",
        ):
            self.assertNotIn(forbidden, names, forbidden)

    def test_v5_payloads_validate_and_refuse_a_smuggled_answer(self) -> None:
        contracts.validate_response_payload("course.outline", _outline_result())
        contracts.validate_response_payload("course.outline", _outline_result(plan=None, objectives=[]))
        contracts.validate_response_payload("check.get", _check_result())
        contracts.validate_response_payload(
            "lesson.assist",
            {"event_id": "evd_12345678", "kind": "hint_request", "evidence_class": "hinted", "revision": 9},
        )
        contracts.validate_request_payload("check.get", {"enrollment_id": "enr_12345678", "check_id": "chk_12345678"})
        contracts.validate_request_payload("check.get", {"enrollment_id": "enr_12345678", "objective_id": "obj_12345678"})

        # Exactly one addressing mode: both or neither is a caller bug, not a merge.
        for payload in (
            {"enrollment_id": "enr_12345678"},
            {"enrollment_id": "enr_12345678", "check_id": "chk_12345678", "objective_id": "obj_12345678"},
        ):
            with self.subTest(payload=payload), self.assertRaises(contracts.ContractError):
                contracts.validate_request_payload("check.get", payload)

        # additionalProperties:false means a passthrough of stimulus_json would not validate: an
        # unknown stored key (an answer smuggled into the stimulus) cannot ride out as a field.
        leaked = _check_result()
        leaked["stimulus"]["reference_answer"] = "丁寧に"
        with self.assertRaises(contracts.ContractError):
            contracts.validate_response_payload("check.get", leaked)
        with self.assertRaises(contracts.ContractError):
            contracts.validate_response_payload("check.get", {**_check_result(), "rubric": []})

    def test_v5_payloads_validate_before_any_handler(self) -> None:
        for method, payload in (
            ("course.outline", {}),
            ("course.outline", {"enrollment_id": "enr_12345678", "limit": 0}),
            ("course.outline", {"enrollment_id": "enr_12345678", "limit": 401}),
            ("check.get", {"enrollment_id": "enr_12345678"}),
            ("lesson.assist", {"enrollment_id": "enr_12345678", "objective_id": "obj_12345678", "kind": "reveal"}),
            ("lesson.assist", {"objective_id": "obj_12345678", "kind": "hint_request"}),
        ):
            with self.subTest(method=method, payload=payload):
                response = api.dispatch(_envelope(method, payload))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

        # Valid shapes reach the seam and say honestly that no handler is registered yet (Cinder's
        # registration is the next step; the UI gates on runtime.implemented_methods meanwhile).
        # Valid shapes are schema-valid; whether a handler answers is a branch fact (Cinder's
        # registration follows this freeze), so the seam is tested by the two invariants above and
        # below instead of by asserting today's unimplemented state.
        contracts.validate_request_payload("course.outline", {"enrollment_id": "enr_12345678"})
        contracts.validate_request_payload("check.get", {"enrollment_id": "enr_12345678",
                                                        "objective_id": "obj_12345678"})
        contracts.validate_request_payload(
            "lesson.assist", {"enrollment_id": "enr_12345678", "objective_id": "obj_12345678",
                              "kind": "hint_request"}
        )

        # A handler that leaks the key is refused by the seam, not trusted.
        def leaking_handler(payload, envelope):
            result = _check_result()
            result["reference_answer"] = "丁寧に"
            return 7, result

        saved = api.METHOD_HANDLERS.get("check.get")
        api.register_handler("check.get", leaking_handler)
        try:
            response = api.dispatch(_envelope("check.get", {"enrollment_id": "enr_12345678",
                                                           "check_id": "chk_12345678"}))
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")
            self.assertIn("reference_answer", response["error"]["message"])
        finally:
            if saved is not None:
                api.METHOD_HANDLERS["check.get"] = saved
            else:
                api.METHOD_HANDLERS.pop("check.get", None)

    def test_lesson_assist_is_a_revision_fenced_learner_command(self) -> None:
        schema = contracts.method_schema("lesson.assist")
        self.assertEqual(set(schema["request"]["required"]), {"enrollment_id", "objective_id", "kind"})
        self.assertEqual(set(schema["request"]["properties"]["kind"]["enum"]),
                         {"hint_request", "answer_shown"})
        response = schema["response"]
        self.assertEqual(set(response["required"]), {"event_id", "kind", "evidence_class", "revision"})
        self.assertEqual(set(response["properties"]["evidence_class"]["enum"]),
                         {"hinted", "answer_shown"})
        # It is a command, so the envelope fence is mandatory: the event changes what class the
        # next answer inherits, and an answer already being graded must lose the race.
        envelope = contracts.contract("cb.rpc")["$defs"]["envelope_request"]
        conditional = [
            rule for rule in envelope["allOf"]
            if rule.get("if", {}).get("properties", {}).get("method", {}).get("enum") == ["lesson.assist"]
        ]
        self.assertEqual(len(conditional), 1, "lesson.assist must be conditional in the envelope")
        self.assertIn("expected_revision", conditional[0]["then"]["required"])
        self.assertIn("idempotency_key", conditional[0]["then"]["required"])
        self.assertNotIn("expected_revision", schema["request"]["properties"])

    def test_v5_claims_no_new_storage_and_no_new_error_code(self) -> None:
        # The v5 surface reads and writes the storage snapshot it froze against, cb.db v2. (cb.db
        # moved to v3 afterwards for CB-011's Parent Studio tables, not for anything v5 added.)
        self.assertEqual(_document("db.v2.json")["x-contract-version"], 2)
        self.assertEqual(contracts.contract_version("cb.errors"), 3)
        self.assertEqual(set(contracts.error_codes()),
                         set(_document("errors.v2.json")["code_catalog"]) | {"PREREQUISITE_UNMET"})
        self.assertEqual(contracts.contract_version("cb.pack"), 1)
        self.assertEqual(contracts.contract_version("cb.projection"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v5_surface_the_refusals_and_the_derivations(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for method in V5_NEW_METHODS:
            self.assertIn(method, text, f"CONTRACTS.md does not document {method}")
        for needle in (
            "rpc.v5.json",
            # what each method may not return
            "reference_answer",
            "rubric",
            # the event/revision rule and its precedent
            "review.action",
            "bump",
            # the storage the three methods read
            "objectives",
            "plans",
            "checks",
            "lesson_runs",
            "evidence",
            # the honest omission, recorded rather than silently dropped
            "section_titles",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


def _parent_brief(**overrides) -> dict:
    brief = {
        "title": "Kitchen chemistry for a seven-year-old",
        "goal": "Explain why baking soda fizzes and predict what changes it",
        "starting_point": None,
        "age_band": "7-9",
        "reading_level": "early reader, short sentences",
        "duration_minutes": 45,
        "setting": "home",
        "materials": ["baking soda", "vinegar", "two bowls"],
        "exclusions": ["no open flame"],
        "supervision": "An adult pours the vinegar; the child measures and writes.",
        "desired_pages": 6,
        "desired_visuals": "diagrams",
        "narration": "script",
        "locale": "en-US",
        "egress_acknowledged": True,
        "redaction_requested": False,
    }
    brief.update(overrides)
    return brief


def _blueprint_file(**overrides) -> dict:
    item = {
        "role": "parent_guide",
        "title": "Parent guide — all sections",
        "objective_id": None,
        "text": "Ask the child to predict first, then measure.",
        "sha256": "sha256:" + "a" * 64,
        "bytes": 1200,
        "source": "authored",
        "truncated": False,
    }
    item.update(overrides)
    return item


def _blueprint_result(**overrides) -> dict:
    result = {
        "course_id": "crs_12345678",
        "recipe": "parent",
        "plan": {"plan_id": "pln_12345678", "version": 2, "state": "approved",
                 "plan_hash": "sha256:" + "b" * 64},
        "approval": {"state": "active", "plan_hash": "sha256:" + "b" * 64,
                     "content_hash": "sha256:" + "c" * 64,
                     "approved_at": "2026-11-06T00:00:00+00:00", "invalidated_reason": None},
        "content_hash": "sha256:" + "c" * 64,
        "export": {"ready": True, "blocked_reason": None},
        "tabs": {
            "parent_guide": [_blueprint_file()],
            "learner_pages": [_blueprint_file(role="learner_page", title="Section 1")],
            "answers": [_blueprint_file(role="answer_guide", title="Answer guide — section 1")],
            "narration": [_blueprint_file(role="narration", title="Narration transcript — section 1")],
        },
        "sources": [
            {"source_id": "src_12345678", "title": "Why does baking soda fizz?",
             "url": None, "publisher": None, "support_status": "unassessed",
             "fetched_at": "2026-11-06T00:00:00+00:00"}
        ],
    }
    result.update(overrides)
    return result


def _export_result(**overrides) -> dict:
    result = {
        "export_id": "exp_12345678",
        "pack": {"pack_id": "crs_12345678_parent", "pack_version": "1.0.0",
                 "manifest_hash": "sha256:" + "d" * 64},
        "files": [
            {"role": "parent_guide", "name": "parent-guide.md",
             "sha256": "sha256:" + "a" * 64, "bytes": 1200, "mime": "text/markdown"},
            {"role": "learner_page", "name": "learner/page-01.md",
             "sha256": "sha256:" + "b" * 64, "bytes": 900, "mime": "text/markdown"},
            {"role": "answer_guide", "name": "answer-guide.md",
             "sha256": "sha256:" + "c" * 64, "bytes": 700, "mime": "text/markdown"},
            {"role": "narration", "name": "narration.md",
             "sha256": "sha256:" + "e" * 64, "bytes": 500, "mime": "text/markdown"},
        ],
        "artifacts": [
            {"artifact_id": "art_12345678", "kind": "pack", "mime": "application/zip",
             "bytes": 4000, "content_hash": "sha256:" + "f" * 64},
            {"artifact_id": "art_87654321", "kind": "pdf", "mime": "application/pdf",
             "bytes": 3000, "content_hash": "sha256:" + "1" * 64},
        ],
        "content_hash": "sha256:" + "c" * 64,
        "exported_at": "2026-11-06T00:00:00+00:00",
    }
    result.update(overrides)
    return result


def _reflection(**overrides) -> dict:
    item = {
        "reflection_id": "rfl_12345678",
        "difficulty": "about_right",
        "revisit_note": "He lost interest at the measuring step; revisit with a smaller bowl.",
        "apply_to_next_draft": True,
        "plan_hash": "sha256:" + "b" * 64,
        "content_hash": "sha256:" + "c" * 64,
        "created_at": "2026-11-06T00:00:00+00:00",
    }
    item.update(overrides)
    return item


class V6AmendmentTest(unittest.TestCase):
    """CB-011: the Parent Studio authoring surface, and what it may hold that a learner surface may not.

    The studio cannot be built on v5: a queued plan job had no typed brief, a draft plan had no
    edit command, a lesson-set approval had nowhere to live, authored content had no export and the
    five blueprint tabs had no read. v6 adds eight methods, two additive cb.db v3 tables and no
    error code. The answers tab is the one place answer text legitimately reaches the wire, and it
    is reachable only here.
    """

    def test_superseded_documents_are_byte_identical(self) -> None:
        for filename, expected in {**FROZEN_RPC_SHA256, **FROZEN_DB_SHA256}.items():
            with self.subTest(filename=filename):
                digest = hashlib.sha256((contracts.CONTRACT_DIR / filename).read_bytes()).hexdigest()
                self.assertEqual(f"sha256:{digest}", expected)
        for version in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            self.assertNotIn(f"rpc.v{version}.json", contracts.CONTRACT_FILES.values())
        for version in (1, 2, 3, 4, 5):
            self.assertNotIn(f"db.v{version}.json", contracts.CONTRACT_FILES.values())
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v11.json")
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v7.json")

    def test_v6_adds_only_the_parent_studio_surface(self) -> None:
        v5 = _document("rpc.v5.json")
        v5_methods = list(v5["$defs"]["method"]["enum"])
        self.assertEqual(len(v5_methods), 43)
        v6 = _document("rpc.v6.json")
        v6_methods = list(v6["$defs"]["method"]["enum"])
        self.assertEqual(set(v6_methods), set(v5_methods) | set(V6_NEW_METHODS))
        self.assertEqual(len(v6_methods), 51)
        # Append-only: the v5 order survives as a prefix, so a client diffing enums sees no churn.
        self.assertEqual(v6_methods[: len(v5_methods)], v5_methods)
        self.assertEqual(
            sorted(set(v6_methods) - set(v5_methods)), sorted(V6_NEW_METHODS)
        )
        for method in V6_NEW_METHODS:
            with self.subTest(method=method):
                schema = {"request": v6["$defs"]["methods"]["properties"][method]["request"],
                          "response": v6["$defs"]["methods"]["properties"][method]["response"]}
                for side in ("request", "response"):
                    self.assertEqual(schema[side]["type"], "object", side)
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    self.assertEqual(_schema_problems(schema[side]), [], f"{method}.{side}")

    def test_every_v1_to_v5_method_schema_is_carried_over_verbatim(self) -> None:
        current = contracts.contract("cb.rpc")
        for version in (1, 2, 3, 4, 5):
            document = _document(f"rpc.v{version}.json")
            for method in document["$defs"]["method"]["enum"]:
                with self.subTest(version=version, method=method):
                    original = document["$defs"]["methods"]["properties"][method]
                    carried = _carried_payload(
                        current["$defs"]["methods"]["properties"][method], method
                    )
                    if method == "health.get":
                        carried["response"]["properties"]["contract_version"] = {
                            "const": original["response"]["properties"]["contract_version"]["const"]
                        }
                    self.assertEqual(original, carried)
            self.assertEqual(
                document["$defs"]["envelope_request"]["properties"]["contract_version"]["const"], version
            )
        self.assertEqual(
            current["$defs"]["methods"]["properties"]["health.get"]["response"]["properties"]
            ["contract_version"]["const"],
            contracts.WIRE_CONTRACT_VERSION,
        )
        for path, value in _wire_echoes(current):
            self.assertEqual(value, contracts.WIRE_CONTRACT_VERSION, path)

    def test_parent_brief_is_typed_and_cannot_skip_the_egress_disclosure(self) -> None:
        schema = contracts.method_schema("parent.brief.create")
        self.assertEqual(set(schema["request"]["required"]), {"brief"})
        brief = contracts.contract("cb.rpc")["$defs"]["parent_brief"]
        for required in (
            "title", "goal", "age_band", "reading_level", "duration_minutes", "setting",
            "materials", "exclusions", "supervision", "desired_pages", "desired_visuals",
            "narration", "egress_acknowledged",
        ):
            self.assertIn(required, brief["required"], required)
        # Acknowledgement is a wire-level fact: a brief that has not seen the disclosure does not
        # validate, so no course can be created under an unacknowledged paste.
        self.assertEqual(brief["properties"]["egress_acknowledged"]["const"], True)
        names = _property_names(brief)
        for forbidden in ("provider", "model", "api_key", "credentials", "tools", "transcript"):
            self.assertNotIn(forbidden, names, forbidden)
        # The brief is readable, which is what makes "duplicate brief" a copy and not a re-render.
        read = contracts.method_schema("parent.brief.get")
        self.assertEqual(set(read["request"]["required"]), {"course_id"})
        self.assertEqual(set(read["response"]["required"]),
                         {"course_id", "enrollment_id", "brief", "plan_job", "created_at"})
        self.assertEqual(read["response"]["properties"]["brief"], {"$ref": "#/$defs/parent_brief"})

    def test_final_approval_is_a_different_fact_from_plan_approval(self) -> None:
        tables = contracts.contract("cb.db")["tables"]
        # The plan-level gate is unchanged: plans.state still has exactly the three v2 values.
        self.assertEqual(set(tables["plans"]["columns"]["state"]["enum"]),
                         {"draft", "approved", "superseded"})
        # The lesson-set approval is its own row about its own hashes.
        approval = tables["final_approvals"]["columns"]
        for column in ("id", "course_id", "plan_id", "plan_hash", "content_hash", "state",
                       "invalidation_reason", "approved_at", "superseded_at"):
            self.assertIn(column, approval, column)
        self.assertEqual(set(approval["state"]["enum"]), {"active", "superseded"})
        self.assertEqual(approval["state"]["default"], "active")
        self.assertEqual(
            set(approval["invalidation_reason"]["enum"]),
            {"plan_edited", "content_changed", "course_edited", "replaced"},
        )
        self.assertTrue(approval["invalidation_reason"]["nullable"])

        approve = contracts.method_schema("parent.final.approve")
        self.assertEqual(
            set(approve["request"]["required"]),
            {"enrollment_id", "plan_id", "plan_hash", "content_hash"},
        )
        # plan.approve binds one hash; final approval binds the plan hash AND the content hash.
        plan_approve = contracts.method_schema("plan.approve")
        self.assertNotIn("content_hash", plan_approve["request"]["properties"])
        self.assertEqual(approve["response"]["properties"]["state"], {"const": "active"})

        # The studio's read of the same fact, including how it stopped binding.
        status = contracts.contract("cb.rpc")["$defs"]["parent_approval_status"]
        self.assertEqual(set(status["properties"]["state"]["enum"]),
                         {"none", "active", "superseded"})
        self.assertEqual(
            set(status["properties"]["invalidated_reason"]["oneOf"][0]["enum"]),
            {"plan_edited", "content_changed", "course_edited", "replaced"},
        )
        self.assertEqual(status["properties"]["invalidated_reason"]["oneOf"][1], {"type": "null"})

    def test_final_approval_invalidation_is_storable_and_gates_export(self) -> None:
        db = _document("db.v3.json")
        self.assertEqual(db["schema_version"], 3)
        self.assertEqual(_document("db.v6.json")["schema_version"], 6)
        # The live inventory moved on to v7 for H-21's plan units; the migration this test is
        # about is still the v3 one and is still on disk.
        self.assertEqual(_document("db.v6.json")["x-contract-version"], 6)
        migration = [entry for entry in db["migration_plan"] if entry["version"] == 3]
        self.assertEqual(len(migration), 1)
        self.assertEqual(migration[0]["migration"],
                         "0003_parent_studio_approvals_and_reflections.sql")
        self.assertTrue(any("Additive only" in line for line in migration[0]["impact"]))
        # The migration the contract names is on disk and creates exactly those tables.
        sql = (contracts.CONTRACT_DIR.parent / "coursebook" / "migrations"
               / migration[0]["migration"]).read_text(encoding="utf-8")
        for table in ("final_approvals", "parent_reflections"):
            self.assertIn(f"CREATE TABLE {table}", sql)
        self.assertIn("CHECK (state IN ('active', 'superseded'))", sql)
        self.assertIn("'plan_edited', 'content_changed', 'course_edited', 'replaced'", sql)

        # "Changes need review" is a stored value plus a wire blocker, not a UI guess.
        export = contracts.method_schema("parent.export")["response"]
        self.assertIn("content_hash", export["required"])
        studio = contracts.method_schema("parent.blueprint.read")["response"]
        self.assertIn("content_hash", studio["required"])
        status = contracts.contract("cb.rpc")["$defs"]["parent_export_status"]
        self.assertEqual(
            set(status["properties"]["blocked_reason"]["oneOf"][0]["enum"]),
            {"no_final_approval", "changes_need_review", "plan_not_approved", "no_generated_content"},
        )
        self.assertEqual(status["properties"]["ready"]["type"], "boolean")

    def test_blueprint_read_serves_declared_text_and_never_a_path(self) -> None:
        rpc = contracts.contract("cb.rpc")
        file_schema = rpc["$defs"]["blueprint_file"]
        self.assertEqual(set(file_schema["required"]),
                         {"role", "title", "text", "sha256", "bytes", "source", "truncated"})
        self.assertEqual(set(file_schema["properties"]["role"]["enum"]),
                         {"parent_guide", "learner_page", "answer_guide", "narration"})
        self.assertEqual(set(file_schema["properties"]["source"]["enum"]), {"authored", "pack"})
        self.assertLessEqual(file_schema["properties"]["text"]["maxLength"], 20000)

        response = contracts.method_schema("parent.blueprint.read")["response"]
        names = _property_names(response)
        for forbidden in ("path", "directory", "local_path", "file_path", "absolute_path"):
            self.assertNotIn(forbidden, names, forbidden)
        self.assertEqual(set(response["properties"]["tabs"]["required"]),
                         {"parent_guide", "learner_pages", "answers", "narration"})
        self.assertIn("sources", response["required"])

        # Every tab is present and bounded; a long course must be able to say it was clipped.
        for tab, schema in response["properties"]["tabs"]["properties"].items():
            self.assertEqual(schema["type"], "array", tab)
            self.assertIn("maxItems", schema, tab)

    def test_the_answers_tab_exception_is_scoped_to_the_studio(self) -> None:
        # The one surface allowed to carry answer text is the parent's own authoring view. The
        # learner surfaces must still not name it in any spelling.
        studio_file = contracts.contract("cb.rpc")["$defs"]["blueprint_file"]
        self.assertEqual(
            set(studio_file["properties"]["role"]["enum"]),
            {"parent_guide", "learner_page", "answer_guide", "narration"},
        )
        self.assertIn("text", studio_file["required"])
        for method in ("lesson.page", "check.get", "course.outline", "evidence.inspect"):
            names = _property_names(contracts.method_schema(method)["response"])
            for forbidden in ("answer_guide", "reference_answer", "accepted_answers",
                              "rubric", "answer_text"):
                self.assertNotIn(forbidden, names, f"{method} must not carry {forbidden}")
        # And the studio has no field that could hand an answer to a learner binding.
        self.assertNotIn("enrollment_id", contracts.method_schema("parent.blueprint.read")["request"]["required"])

    def test_parent_export_reuses_the_pack_vocabulary_and_a_pdf_artifact(self) -> None:
        pack_roles = set(contracts.contract("cb.pack")["properties"]["files"]["items"]
                         ["properties"]["role"]["enum"])
        export_files = contracts.contract("cb.rpc")["$defs"]["parent_export_file"]
        roles = set(export_files["properties"]["role"]["enum"])
        self.assertEqual(roles, {"parent_guide", "learner_page", "answer_guide", "narration"})
        self.assertTrue(roles <= pack_roles, sorted(roles - pack_roles))
        # A pack-internal name, not a local path.
        self.assertIn("not", export_files["properties"]["name"])
        self.assertNotIn("path", export_files["properties"])
        response = contracts.method_schema("parent.export")["response"]
        for required in ("export_id", "pack", "files", "artifacts", "content_hash", "exported_at"):
            self.assertIn(required, response["required"])
        self.assertLessEqual(response["properties"]["files"]["maxItems"], 200)
        kinds = set(contracts.contract("cb.rpc")["$defs"]["artifact_ref"]["properties"]["kind"]["enum"])
        self.assertIn("pdf", kinds)
        self.assertIn("pack", kinds)
        # Export is content-fenced: the request names the enrollment, the response names the hash
        # that was approved, so a stale panel cannot export bytes nobody approved.
        self.assertEqual(set(contracts.method_schema("parent.export")["request"]["required"]),
                         {"enrollment_id"})

    def test_v6_payloads_validate(self) -> None:
        contracts.validate_request_payload("parent.brief.create", {"brief": _parent_brief()})
        contracts.validate_request_payload("parent.brief.get", {"course_id": "crs_12345678"})
        contracts.validate_request_payload(
            "parent.plan.edit",
            {
                "enrollment_id": "enr_12345678",
                "plan_id": "pln_12345678",
                "expected_plan_hash": "sha256:" + "b" * 64,
                "objective_edits": [
                    {"objective_id": "obj_12345678", "title": "Predict, then measure",
                     "evidence_target": "comprehension", "criteria": [{"id": "c1"}]}
                ],
                "add_objectives": [{"title": "Write the result down", "evidence_target": "production"}],
                "remove_objective_ids": [],
                "order": ["obj_12345678"],
            },
        )
        contracts.validate_request_payload(
            "parent.final.approve",
            {"enrollment_id": "enr_12345678", "plan_id": "pln_12345678",
             "plan_hash": "sha256:" + "b" * 64, "content_hash": "sha256:" + "c" * 64},
        )
        contracts.validate_request_payload("parent.blueprint.read", {"course_id": "crs_12345678"})
        contracts.validate_request_payload(
            "parent.export", {"enrollment_id": "enr_12345678", "formats": ["pack", "pdf"]}
        )
        contracts.validate_request_payload(
            "parent.reflection.record",
            {"course_id": "crs_12345678", "difficulty": "too_hard", "apply_to_next_draft": True},
        )
        contracts.validate_request_payload("parent.reflection.list", {"course_id": "crs_12345678"})

        contracts.validate_response_payload(
            "parent.brief.create",
            {"course_id": "crs_12345678", "enrollment_id": "enr_12345678",
             "job_id": "job_12345678", "state": "queued", "revision": 0},
        )
        contracts.validate_response_payload(
            "parent.brief.get",
            {"course_id": "crs_12345678", "enrollment_id": "enr_12345678",
             "brief": _parent_brief(), "plan_job": None,
             "created_at": "2026-11-06T00:00:00+00:00"},
        )
        contracts.validate_response_payload(
            "parent.plan.edit",
            {"plan_id": "pln_12345678", "plan_version": 3, "plan_hash": "sha256:" + "d" * 64,
             "objective_ids": ["obj_12345678"], "changes_need_review": True, "revision": 8},
        )
        contracts.validate_response_payload(
            "parent.final.approve",
            {"approval_id": "apr_12345678", "state": "active",
             "plan_hash": "sha256:" + "b" * 64, "content_hash": "sha256:" + "c" * 64,
             "approved_at": "2026-11-06T00:00:00+00:00", "revision": 9},
        )
        contracts.validate_response_payload("parent.blueprint.read", _blueprint_result())
        contracts.validate_response_payload("parent.blueprint.read", _blueprint_result(
            plan=None, approval={"state": "none", "plan_hash": None, "content_hash": None,
                                 "approved_at": None, "invalidated_reason": None},
            export={"ready": False, "blocked_reason": "no_final_approval"},
        ))
        contracts.validate_response_payload("parent.export", _export_result())
        contracts.validate_response_payload(
            "parent.reflection.record",
            {"reflection_id": "rfl_12345678", "difficulty": "easy",
             "plan_hash": None, "content_hash": None,
             "created_at": "2026-11-06T00:00:00+00:00"},
        )
        contracts.validate_response_payload(
            "parent.reflection.list", {"reflections": [_reflection()], "total": 1}
        )
        # A reflection cannot claim evidence: there is no field for one.
        self.assertEqual(
            set(contracts.contract("cb.rpc")["$defs"]["parent_reflection"]["required"]),
            {"reflection_id", "difficulty", "revisit_note", "apply_to_next_draft",
             "plan_hash", "content_hash", "created_at"},
        )

    def test_v6_refuses_the_payloads_that_would_make_it_dishonest(self) -> None:
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "parent.brief.create", {"brief": _parent_brief(egress_acknowledged=False)}
            )
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "parent.reflection.record",
                {"course_id": "crs_12345678", "difficulty": "mastered"},
            )
        with self.assertRaises(contracts.ContractError):
            # A path, absolute or traversing, is not a pack-internal name.
            contracts.validate_response_payload("parent.export", _export_result(
                files=[{"role": "parent_guide", "name": "../../etc/passwd",
                        "sha256": "sha256:" + "a" * 64, "bytes": 10, "mime": "text/markdown"}]
            ))
        with self.assertRaises(contracts.ContractError):
            contracts.validate_response_payload("parent.export", _export_result(
                files=[{"role": "transcript", "name": "chat.md",
                        "sha256": "sha256:" + "a" * 64, "bytes": 10, "mime": "text/markdown"}]
            ))
        with self.assertRaises(contracts.ContractError):
            # The answer text may ride in `text`, never as an unexplained extra field.
            leaked = _blueprint_result()
            leaked["tabs"]["answers"][0]["reference_answer"] = "carbon dioxide"
            contracts.validate_response_payload("parent.blueprint.read", leaked)
        with self.assertRaises(contracts.ContractError):
            contracts.validate_response_payload(
                "parent.plan.edit",
                {"plan_id": "pln_12345678", "plan_version": 3, "plan_hash": "sha256:" + "d" * 64,
                 "objective_ids": [], "changes_need_review": False, "revision": 8},
            )

    def test_v6_payloads_validate_before_any_handler(self) -> None:
        for method, payload in (
            ("parent.brief.create", {}),
            ("parent.brief.create", {"brief": _parent_brief(egress_acknowledged=False)}),
            ("parent.brief.get", {}),
            ("parent.plan.edit", {"enrollment_id": "enr_12345678", "plan_id": "pln_12345678"}),
            ("parent.final.approve", {"enrollment_id": "enr_12345678", "plan_id": "pln_12345678",
                                      "plan_hash": "sha256:" + "b" * 64}),
            ("parent.blueprint.read", {"course_id": "x"}),
            ("parent.export", {"format": "pdf"}),
            ("parent.reflection.record", {"course_id": "crs_12345678", "difficulty": "hard"}),
            ("parent.reflection.list", {"course_id": "crs_12345678", "limit": 201}),
        ):
            with self.subTest(method=method, payload=payload):
                response = api.dispatch(_envelope(method, payload))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")

    def test_v6_commands_are_fenced_and_reads_are_not(self) -> None:
        envelope = contracts.contract("cb.rpc")["$defs"]["envelope_request"]
        rules = {
            tuple(rule["if"]["properties"]["method"]["enum"]): set(rule["then"]["required"])
            for rule in envelope["allOf"]
        }
        self.assertEqual(rules[("parent.brief.create",)], {"idempotency_key"})
        self.assertEqual(rules[("parent.plan.edit",)], {"idempotency_key", "expected_revision"})
        self.assertEqual(rules[("parent.final.approve",)], {"idempotency_key", "expected_revision"})
        self.assertEqual(rules[("parent.export",)], {"idempotency_key"})
        self.assertEqual(rules[("parent.reflection.record",)], {"idempotency_key"})
        for method in ("parent.brief.get", "parent.blueprint.read", "parent.reflection.list"):
            self.assertNotIn((method,), rules, f"{method} is a read and must not be fenced")
        # Export must not bump a revision: bumping would refuse an answer that is being graded.
        self.assertNotIn("revision", contracts.method_schema("parent.export")["response"]["required"])

    def test_v6_adds_no_error_code_and_no_job_kind(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 3)
        self.assertEqual(set(contracts.error_codes()),
                         set(_document("errors.v2.json")["code_catalog"]) | {"PREREQUISITE_UNMET"})
        # The one thing this card could not add: `lesson` as a job family. cb.vocabulary stays v1
        # because every pack manifest embeds a reference to it, so lesson generation runs as the
        # `plan` family with `brief.stage = lessons`. The decision is recorded in the docs.
        job_kind = contracts.contract("cb.vocabulary")["$defs"]["job_kind"]["enum"]
        self.assertNotIn("lesson", job_kind)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.contract_version("cb.jobs"), 3)
        self.assertEqual(contracts.contract_version("cb.pack"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v6_surface_and_the_invalidation_rule(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for method in V6_NEW_METHODS:
            self.assertIn(method, text, f"CONTRACTS.md does not document {method}")
        for needle in (
            "rpc.v6.json",
            "db.v3.json",
            "final_approvals",
            "parent_reflections",
            "content_hash",
            "changes_need_review",
            "invalidated_reason",
            # the UX §10 mapping row must name the studio methods, not the old v1 guess
            "parent.brief.create",
            "parent.blueprint.read",
            "parent.export",
            # and the decision this card could not take must be written down, not implied
            "brief.stage",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V7AmendmentTest(unittest.TestCase):
    """CB-015 residual: v7 gives the stale-source state a wire surface and cb.db a baseline column.

    Before v7, ``sources.refresh`` existed but no cb.rpc method called it, so a reviewer could not
    reach ``support_status='stale'`` without hand-writing a row. v7 adds exactly one command and
    cb.db v4 adds exactly one nullable column; no shipped method payload, error code or job kind
    changes.
    """

    def test_v7_adds_only_source_revalidate(self) -> None:
        v6 = _document("rpc.v6.json")
        v6_methods = list(v6["$defs"]["method"]["enum"])
        self.assertEqual(len(v6_methods), 51)
        current = list(contracts.method_names())
        self.assertEqual(len(current), 54)
        self.assertEqual(current[: len(v6_methods)], v6_methods)
        self.assertEqual(
            sorted(set(current) - set(v6_methods)),
            sorted(set(V7_NEW_METHODS) | set(V9_NEW_METHODS)),
        )

    def test_every_v6_method_payload_is_carried_over_verbatim(self) -> None:
        v6 = _document("rpc.v6.json")
        current = contracts.contract("cb.rpc")
        for method in v6["$defs"]["method"]["enum"]:
            with self.subTest(method=method):
                original = v6["$defs"]["methods"]["properties"][method]
                carried = current["$defs"]["methods"]["properties"][method]
                if method == "health.get":
                    # The one intentional difference: the version echo moves with the wire version.
                    self.assertEqual(
                        original["response"]["properties"]["contract_version"]["const"], 6
                    )
                    self.assertEqual(
                        carried["response"]["properties"]["contract_version"]["const"],
                        contracts.WIRE_CONTRACT_VERSION,
                    )
                    original = json.loads(json.dumps(original))
                    carried = json.loads(json.dumps(carried))
                    original["response"]["properties"]["contract_version"] = {
                        "const": contracts.WIRE_CONTRACT_VERSION
                    }
                if method == "lesson.page":
                    # v8 adds exactly one response field to the read method and removes nothing.
                    self.assertIn("document", carried["response"]["properties"])
                    self.assertIn("document", carried["response"]["required"])
                    self.assertEqual(
                        carried["response"]["properties"]["document"],
                        {"$ref": "#/$defs/lesson_document"},
                    )
                    carried = json.loads(json.dumps(carried))
                    carried["response"]["properties"].pop("document")
                    carried["response"]["required"].remove("document")
                # v10 adds optional request inputs and one plan-brief condition; nothing moved.
                for field in V10_ADDED_METHOD_FIELDS.get(method, ()):
                    carried = json.loads(json.dumps(carried))
                    carried["request"]["properties"].pop(field)
                # v11 adds one optional request flag and one optional response fact to the two
                # work-starting commands; no earlier field moved.
                for field in V11_ADDED_REQUEST_FIELDS.get(method, ()):
                    carried = json.loads(json.dumps(carried))
                    carried["request"]["properties"].pop(field)
                for field in V11_ADDED_RESPONSE_FIELDS.get(method, ()):
                    carried = json.loads(json.dumps(carried))
                    carried["response"]["properties"].pop(field)
                    required = carried["response"].get("required") or []
                    if field in required:
                        required.remove(field)
                if method == "jobs.create":
                    carried = json.loads(json.dumps(carried))
                    carried["request"].pop("allOf", None)
                self.assertEqual(original, _normalise_refresh_refs(carried))
        # Both response envelopes and the request envelope echo the live version.
        echoes = _wire_echoes(current)
        self.assertGreaterEqual(len(echoes), 3)
        for path, value in echoes:
            self.assertEqual(value, contracts.WIRE_CONTRACT_VERSION, path)

    def test_source_revalidate_request_response_and_fence(self) -> None:
        method = "source.revalidate"
        schema = contracts.method_schema(method)
        request, response = schema["request"], schema["response"]
        self.assertEqual(set(request["required"]), {"source_id", "fetched"})
        self.assertIs(request["additionalProperties"], False)
        fetched = request["properties"]["fetched"]
        branches = fetched["oneOf"]
        self.assertEqual([branch["type"] for branch in branches], ["object", "null"])
        self.assertEqual(set(branches[0]["required"]), {"content"})
        self.assertIs(branches[0]["additionalProperties"], False)
        # A wire field that the kernel discards is a seam that reads as working; there is no reason.
        self.assertNotIn("reason", request["properties"])
        self.assertEqual(
            set(response["required"]),
            {"source_id", "changed", "support_status", "review_required",
             "fetched_at", "previous_hash", "content_hash", "impact"},
        )
        self.assertIs(response["additionalProperties"], False)
        impact = response["properties"]["impact"]
        self.assertEqual(
            set(impact["required"]),
            {"source_id", "course_id", "objective_ids", "check_ids",
             "artifact_ids", "lesson_ids", "support_status"},
        )
        self.assertEqual(_schema_problems(request), [])
        self.assertEqual(_schema_problems(response), [])
        # Fenced by idempotency only: a course-scoped source row has no aggregate revision.
        envelope = contracts.contract("cb.rpc")["$defs"]["envelope_request"]
        rules = {
            tuple(rule["if"]["properties"]["method"]["enum"]): set(rule["then"]["required"])
            for rule in envelope["allOf"]
        }
        self.assertEqual(rules[(method,)], {"idempotency_key"})
        self.assertNotIn("revision", response["properties"])

    def test_db_v4_adds_only_a_nullable_content_hash_column(self) -> None:
        # The v4 snapshot, not the live inventory: v5 appended the pronunciation table afterwards.
        db4 = _document("db.v4.json")
        db3 = _document("db.v3.json")
        self.assertEqual(db4["x-contract-version"], 4)
        self.assertEqual(db4["schema_version"], 4)
        self.assertEqual(set(db4["tables"]), set(db3["tables"]), "v4 adds no table and drops none")
        column = db4["tables"]["sources"]["columns"]["content_hash"]
        self.assertEqual(column["type"], "TEXT")
        self.assertTrue(column["nullable"], "NULL means no baseline yet, not unchanged")
        migration = [entry for entry in db4["migration_plan"] if entry["version"] == 4]
        self.assertEqual(len(migration), 1)
        self.assertEqual(migration[0]["migration"], "0004_sources_content_hash.sql")
        self.assertTrue(any("Additive only" in line for line in migration[0]["impact"]))
        self.assertTrue(any("No backfill" in line for line in migration[0]["impact"]))
        sql = (contracts.CONTRACT_DIR.parent / "coursebook" / "migrations"
               / migration[0]["migration"]).read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE sources ADD COLUMN content_hash TEXT", sql)

    def test_v7_adds_no_error_code_and_no_job_kind(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 3)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.contract_version("cb.jobs"), 3)
        self.assertEqual(contracts.contract_version("cb.pack"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v7_surface_and_its_omission(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v7 delta (CB-015 residual)",
            "source.revalidate",
            "rpc.v7.json",
            "db.v4.json",
            "content_hash",
            "no `expected_revision`",
            "No recovery",
            "stale_source",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V9AmendmentTest(unittest.TestCase):
    """M3-B1: pronunciation practice gets two commands and one separate storage table.

    The point of the amendment is what it does *not* add: no grade, no objective transition, no
    audio column and no error code. A missing recogniser must remain expressible without a score.
    """

    def test_v9_adds_only_the_two_pronunciation_commands(self) -> None:
        v8 = _document("rpc.v8.json")
        v8_methods = list(v8["$defs"]["method"]["enum"])
        self.assertEqual(len(v8_methods), 52)
        current = list(contracts.method_names())
        self.assertEqual(len(current), 54)
        self.assertEqual(current[: len(v8_methods)], v8_methods, "append-only enum")
        self.assertEqual(sorted(set(current) - set(v8_methods)), sorted(V9_NEW_METHODS))

    def test_pronunciation_attempt_request_is_bounded(self) -> None:
        schema = contracts.method_schema("pronunciation.attempt")
        request, response = schema["request"], schema["response"]
        self.assertEqual(
            set(request["required"]),
            {"enrollment_id", "objective_id", "attempt_nonce", "target", "locale", "audio_data_url"},
        )
        self.assertIs(request["additionalProperties"], False)
        self.assertEqual(request["properties"]["audio_data_url"]["maxLength"], 5_000_000)
        self.assertEqual(request["properties"]["target"]["maxLength"], 200)
        self.assertEqual(set(response["required"]),
                         {"status", "recorded", "attempt_id", "revision", "assessment", "reason"})
        self.assertEqual(set(response["properties"]["status"]["enum"]),
                         {"assessed", "empty", "unavailable"})
        self.assertEqual(response["properties"]["recorded"]["type"], "boolean")
        self.assertEqual(
            response["properties"]["assessment"], {"$ref": "#/$defs/pronunciation_assessment"}
        )
        # The unusable outcome is representable without inventing a transcript or an accuracy.
        assessment = contracts.contract("cb.rpc")["$defs"]["pronunciation_assessment"]
        self.assertEqual(assessment["properties"]["evidence_class"], {"const": "model_assessed"})
        self.assertEqual(
            set(assessment["properties"]["verdict"]["enum"]),
            {"meets_target", "close", "needs_practice", "unavailable"},
        )
        for nullable in ("word_accuracy", "phoneme_accuracy", "confidence"):
            self.assertIn({"type": "null"}, assessment["properties"][nullable]["oneOf"])
        self.assertLessEqual(assessment["properties"]["words"]["maxItems"], 200)
        for side in (request, response, assessment):
            self.assertEqual(_schema_problems(side), [])

    def test_pronunciation_dispute_is_note_only_and_cannot_rewrite_a_score(self) -> None:
        schema = contracts.method_schema("pronunciation.dispute")
        request, response = schema["request"], schema["response"]
        self.assertEqual(set(request["required"]), {"enrollment_id", "attempt_id", "note"})
        self.assertEqual(request["properties"]["note"]["maxLength"], 1_000)
        self.assertNotIn("verdict", response["properties"])
        self.assertNotIn("evidence_class", response["properties"])
        self.assertEqual(response["properties"]["state"], {"const": "open"})

    def test_db_v5_adds_only_the_pronunciation_attempts_table(self) -> None:
        # The v5 snapshot, not the live inventory: v6 appended the H-01 course-input columns.
        v4 = _document("db.v4.json")
        v5 = _document("db.v5.json")
        self.assertEqual(v5["x-contract-version"], 5)
        self.assertEqual(v5["schema_version"], 5)
        self.assertEqual(set(v5["tables"]), set(v4["tables"]) | {"pronunciation_attempts"})
        for table, spec in v4["tables"].items():
            self.assertEqual(v5["tables"][table], spec, f"v4 table {table} changed")
        columns = v5["tables"]["pronunciation_attempts"]["columns"]
        self.assertEqual(columns["verdict"]["enum"], ["meets_target", "close", "needs_practice"])
        self.assertEqual(columns["evidence_class"]["enum"], ["model_assessed"])
        for forbidden in ("audio", "audio_bytes", "audio_path", "path", "api_key", "model_path"):
            self.assertNotIn(forbidden, columns)
        migration = [entry for entry in v5["migration_plan"] if entry["version"] == 5]
        self.assertEqual(len(migration), 1)
        self.assertEqual(migration[0]["migration"], "0005_pronunciation_attempts.sql")
        self.assertTrue(any("Additive only" in line for line in migration[0]["impact"]))
        self.assertTrue(any("No backfill" in line for line in migration[0]["impact"]))
        sql = (contracts.CONTRACT_DIR.parent / "coursebook" / "migrations"
               / migration[0]["migration"]).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE pronunciation_attempts", sql)
        self.assertIn("UNIQUE (enrollment_id, attempt_nonce)", sql)

    def test_v9_adds_no_error_code_and_no_job_kind(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 3)
        self.assertEqual(contracts.contract_version("cb.jobs"), 3)
        self.assertEqual(contracts.audit_contracts(), [])


V10_NEW_COURSE_FIELDS = ("level", "subject_domain", "scope")

#: The plan-brief fields v10 accepts for `kind = "plan"`. The parent-authoring fields are part of
#: it because a Parent Studio job is re-queued from its own stored brief.
V10_PLAN_BRIEF_FIELDS = {
    "goal", "brief", "title", "recipe", "dials", "locale", "level", "subject_domain", "scope",
    "course_id", "enrollment_id", "plan_id", "budget_usd", "stage",
    "starting_point", "age_band", "reading_level", "duration_minutes", "setting", "materials",
    "exclusions", "supervision", "desired_pages", "desired_visuals", "narration",
    "egress_acknowledged", "redaction_requested",
}


def _course_payload(**overrides) -> dict:
    payload = {
        "title": "Replace the front brake pads",
        "recipe": "one_off",
        "goal": "Replace the front brake pads and torque the caliper to spec",
        "locale": "es-ES",
        "level": "L0",
        "subject_domain": "repair",
        "scope": "single",
        "dials": {
            "pace": "steady",
            "depth": "working",
            "assessment": "self_check",
            "autonomy": "guided",
        },
    }
    payload.update(overrides)
    return payload


class V10AmendmentTest(unittest.TestCase):
    """H-01: the inputs the policy and planner need are on the wire, additively.

    v9 froze four dials and no level/domain/scope, so the capability policy's fallback read
    `locale` as "this is a language course" and the L0 scaffold was unreachable. v10 makes the
    inputs first-class without moving a single v9 payload.
    """

    def _carried_from_v9(self, payload: dict, method: str) -> dict:
        carried = json.loads(json.dumps(payload))
        request = carried["request"]
        for field in V10_ADDED_METHOD_FIELDS.get(method, ()):
            (request.get("properties") or {}).pop(field, None)
        if method == "jobs.create":
            request.pop("allOf", None)
        return carried

    def test_v10_is_additive_over_v9_and_keeps_the_method_enum(self) -> None:
        v9 = _document("rpc.v9.json")
        self.assertEqual(v9["x-contract-version"], 9)
        # The v10 snapshot, not the live inventory: v11 added optional unit/prerequisite fields.
        current = _document("rpc.v10.json")
        self.assertEqual(current["x-contract-version"], 10)
        self.assertEqual(current["$id"], "https://contracts.coursebook.hermes/rpc/v10")
        self.assertEqual(current["x-supersedes"], "https://contracts.coursebook.hermes/rpc/v9")
        self.assertEqual(list(contracts.method_names()), v9["$defs"]["method"]["enum"])
        self.assertEqual(contracts.audit_contracts(), [])

    def test_every_v9_method_payload_is_carried_over_verbatim(self) -> None:
        v9 = _document("rpc.v9.json")
        current = _document("rpc.v10.json")
        for method in v9["$defs"]["method"]["enum"]:
            with self.subTest(method=method):
                original = v9["$defs"]["methods"]["properties"][method]
                carried = self._carried_from_v9(
                    current["$defs"]["methods"]["properties"][method], method
                )
                if method == "health.get":
                    # The one permitted difference: the v10 echo.
                    self.assertEqual(
                        carried["response"]["properties"]["contract_version"],
                        {"const": 10},
                    )
                    original = json.loads(json.dumps(original))
                    carried = json.loads(json.dumps(carried))
                    original["response"]["properties"]["contract_version"] = {
                        "const": 10
                    }
                self.assertEqual(original, carried)

    def test_every_v9_payload_still_validates(self) -> None:
        # A v9 caller sends no level/domain/scope and the four dials only. Each payload below is a
        # shape that was legal at v9 and must still validate at v10.
        contracts.validate_request_payload(
            "course.create", {"title": "Braise", "recipe": "casual", "goal": "Braise short ribs"}
        )
        contracts.validate_request_payload(
            "course.create",
            {
                "title": "Braise",
                "recipe": "casual",
                "goal": "Braise short ribs",
                "locale": "en-US",
                "dials": {"pace": "light", "depth": "survey", "assessment": "none", "autonomy": "balanced"},
            },
        )
        contracts.validate_request_payload("jobs.create", {"kind": "plan", "brief": {}})
        contracts.validate_request_payload(
            "jobs.create", {"kind": "plan", "brief": {"stage": "lessons", "plan_id": "pln_12345678"}}
        )
        contracts.validate_request_payload(
            "jobs.create",
            {"kind": "plan", "brief": {"goal": "Braise", "recipe": "casual", "dials": {"depth": "deep"},
                                        "locale": "en-US", "course_id": "crs_12345678"}},
        )
        contracts.validate_request_payload(
            "jobs.create", {"kind": "research", "brief": {"topic": "braising"}}
        )
        contracts.validate_request_payload("jobs.create", {"kind": "media", "brief": {"goal": "diagram"}})

    def test_the_new_inputs_validate_and_nulls_mean_unspecified(self) -> None:
        contracts.validate_request_payload("course.create", _course_payload())
        contracts.validate_request_payload(
            "course.create", _course_payload(level=None, subject_domain=None, scope=None)
        )
        for scope in ("single", "short", "full"):
            with self.subTest(scope=scope):
                contracts.validate_request_payload("course.create", _course_payload(scope=scope))

    def test_unknown_fields_are_rejected(self) -> None:
        # course.create is closed at the top level and inside the dials.
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload("course.create", _course_payload(lesson_intent="do it"))
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "course.create", _course_payload(dials={"pace": "light", "level": "L0"})
            )
        # A plan brief is closed: a typo cannot become an input nobody reads.
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "jobs.create", {"kind": "plan", "brief": {"goal": "Braise", "scop": "full"}}
            )
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "jobs.create", {"kind": "plan", "brief": {"goal": "Braise", "dials": {"levl": "L0"}}}
            )
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "jobs.create", {"kind": "plan", "brief": {"goal": "Braise", "scope": "whole"}}
            )

    def test_the_four_dials_stay_closed(self) -> None:
        dials = contracts.method_schema("course.create")["request"]["properties"]["dials"]
        self.assertEqual(set(dials["properties"]), {"pace", "depth", "assessment", "autonomy"})
        self.assertIs(dials["additionalProperties"], False)
        plan_brief = contracts.contract("cb.rpc")["$defs"]["plan_brief"]
        self.assertEqual(
            set(plan_brief["properties"]["dials"]["properties"]),
            {"pace", "depth", "assessment", "autonomy"},
        )
        self.assertIs(plan_brief["properties"]["dials"]["additionalProperties"], False)
        # level/subject_domain/scope are course inputs, not dials: they are top-level siblings.
        request = contracts.method_schema("course.create")["request"]
        for field in V10_NEW_COURSE_FIELDS:
            self.assertIn(field, request["properties"])
            self.assertNotIn(field, dials["properties"])
        self.assertNotIn("level", request["required"])

    def test_jobs_create_accepts_one_plan_brief_without_a_second_job_kind(self) -> None:
        # The v10 snapshot, not the live inventory: v11 adds `unit_ordinal` to the same brief.
        plan_brief = _document("rpc.v10.json")["$defs"]["plan_brief"]
        self.assertIs(plan_brief["additionalProperties"], False)
        self.assertEqual(set(plan_brief["properties"]), V10_PLAN_BRIEF_FIELDS)
        self.assertEqual(_schema_problems(plan_brief), [])
        self.assertIn("plan", contracts.contract("cb.vocabulary")["$defs"]["job_kind"]["enum"])
        self.assertEqual(set(contracts.contract("cb.vocabulary")["$defs"]["job_kind"]["enum"]),
                         {"plan", "research", "media", "export", "import"})
        # A full Parent Studio brief round-trips through jobs.create: that is the retry path the
        # desktop uses (`jobs.get` -> `jobs.create`), so its fields are part of the accepted shape.
        contracts.validate_request_payload(
            "jobs.create",
            {"kind": "plan", "brief": {
                "title": "Kitchen chemistry", "goal": "Explain fizzing", "recipe": "parent",
                "dials": {}, "locale": "en-US", "level": "L0", "subject_domain": "science",
                "scope": "short", "course_id": "crs_12345678", "enrollment_id": "enr_12345678",
                "stage": "plan", "starting_point": None, "age_band": "7-9",
                "reading_level": "early reader", "duration_minutes": 45, "setting": "home",
                "materials": ["baking soda"], "exclusions": ["no flame"],
                "supervision": "An adult pours.", "desired_pages": 6,
                "desired_visuals": "diagrams", "narration": "script",
                "egress_acknowledged": True, "redaction_requested": False,
                "budget_usd": 2.5,
            }},
        )

    def test_the_plan_brief_names_a_typed_positive_budget_override(self) -> None:
        """H-17: ``brief.budget_usd`` is an accepted input, not a typo the closed brief refuses."""
        plan_brief = contracts.contract("cb.rpc")["$defs"]["plan_brief"]
        budget = plan_brief["properties"]["budget_usd"]
        self.assertEqual(budget["type"], "number")
        self.assertEqual(budget["exclusiveMinimum"], 0)
        self.assertEqual(budget["maximum"], 1000)
        self.assertNotIn("budget_usd", plan_brief.get("required", []))
        # The lessons-retry brief the recovery checkpoint names validates as-is.
        contracts.validate_request_payload(
            "jobs.create",
            {"kind": "plan",
             "brief": {"stage": "lessons", "plan_id": "pln_12345678", "budget_usd": 2.0}},
        )
        for impossible in (0, -1.5, "cheap", True):
            with self.assertRaises(contracts.ContractError, msg=repr(impossible)):
                contracts.validate_request_payload(
                    "jobs.create",
                    {"kind": "plan",
                     "brief": {"stage": "lessons", "plan_id": "pln_12345678",
                               "budget_usd": impossible}},
                )
        # The brief stays closed: a near-miss is still refused rather than stored.
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "jobs.create",
                {"kind": "plan",
                 "brief": {"stage": "lessons", "plan_id": "pln_12345678", "budget": 2.0}},
            )

    def test_db_v6_adds_only_the_three_nullable_course_columns(self) -> None:
        v5 = _document("db.v5.json")
        current = _document("db.v6.json")
        self.assertEqual(current["x-contract-version"], 6)
        self.assertEqual(current["schema_version"], 6)
        self.assertEqual(current["x-supersedes"], "https://contracts.coursebook.hermes/db/v5")
        self.assertEqual(set(current["tables"]), set(v5["tables"]))
        for table, spec in v5["tables"].items():
            if table != "courses":
                self.assertEqual(current["tables"][table], spec, f"v5 table {table} changed")
        columns = current["tables"]["courses"]["columns"]
        for field in V10_NEW_COURSE_FIELDS:
            self.assertEqual(columns[field]["type"], "TEXT")
            self.assertTrue(columns[field]["nullable"], f"{field} must be nullable for old rows")
        self.assertEqual(set(columns["scope"]["enum"]), {"single", "short", "full"})
        self.assertEqual(
            [column for column in columns if column not in v5["tables"]["courses"]["columns"]],
            list(V10_NEW_COURSE_FIELDS),
        )
        migration = [entry for entry in current["migration_plan"] if entry["version"] == 6]
        self.assertEqual(len(migration), 1)
        self.assertEqual(migration[0]["migration"], "0006_courses_plan_brief_inputs.sql")
        self.assertTrue(any("Additive only" in line for line in migration[0]["impact"]))
        self.assertTrue(any("No backfill" in line for line in migration[0]["impact"]))
        sql = (contracts.CONTRACT_DIR.parent / "coursebook" / "migrations"
               / migration[0]["migration"]).read_text(encoding="utf-8")
        for statement in (
            "ALTER TABLE courses ADD COLUMN level TEXT",
            "ALTER TABLE courses ADD COLUMN subject_domain TEXT",
            "ALTER TABLE courses ADD COLUMN scope TEXT CHECK (scope IS NULL OR scope IN ('single', 'short', 'full'))",
        ):
            self.assertIn(statement, sql)
        # The migration the contract names is applied by the real runner, and the v6 target holds.
        self.assertEqual(_document("db.v6.json")["schema_version"], 6)

    def test_superseded_snapshots_are_pinned(self) -> None:
        for filename in ("rpc.v9.json", "db.v5.json"):
            expected = {**FROZEN_RPC_SHA256, **FROZEN_DB_SHA256}[filename]
            digest = hashlib.sha256((contracts.CONTRACT_DIR / filename).read_bytes()).hexdigest()
            self.assertEqual(f"sha256:{digest}", expected)
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v11.json")
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v7.json")

    def test_v10_adds_no_error_code_and_no_vocabulary_change(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 3)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.contract_version("cb.jobs"), 3)
        self.assertEqual(contracts.contract_version("cb.pack"), 1)
        self.assertEqual(contracts.contract_version("cb.projection"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v10_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v10 delta (H-01)",
            "rpc.v10.json",
            "db.v6.json",
            "0006_courses_plan_brief_inputs.sql",
            "plan_brief",
            "subject_domain",
            "`single`/`short`/`full`",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V10PersistenceTest(KernelCase):
    """The new inputs survive the real database: stored once, read back by `course.get`."""

    def test_course_create_round_trips_all_new_fields(self) -> None:
        result = self.ok("course.create", _course_payload())["result"]
        course = self.ok("course.get", {"course_id": result["course_id"]})["result"]["course"]
        self.assertEqual(course["level"], "L0")
        self.assertEqual(course["subject_domain"], "repair")
        self.assertEqual(course["scope"], "single")
        self.assertEqual(course["locale"], "es-ES")
        self.assertEqual(
            course["dials"],
            {"pace": "steady", "depth": "working", "assessment": "self_check", "autonomy": "guided"},
        )
        # Level is a course input, never smuggled into the stored dials.
        self.assertNotIn("level", course["dials"])
        self.assertNotIn("subject_domain", course["dials"])
        row = self.rows("SELECT level, subject_domain, scope FROM courses WHERE id = ?",
                        (result["course_id"],))[0]
        self.assertEqual(row, {"level": "L0", "subject_domain": "repair", "scope": "single"})

    def test_blank_inputs_are_stored_as_null_not_empty_strings(self) -> None:
        payload = _course_payload(level="  ", subject_domain="", scope=None)
        result = self.ok("course.create", payload)["result"]
        course = self.ok("course.get", {"course_id": result["course_id"]})["result"]["course"]
        self.assertIsNone(course["level"])
        self.assertIsNone(course["subject_domain"])
        self.assertIsNone(course["scope"])

    def test_an_old_row_with_null_fields_is_valid(self) -> None:
        # A course row written before v6 (or by a caller that sent none of the new fields).
        course_id, _ = self.new_course()
        course = self.ok("course.get", {"course_id": course_id})["result"]["course"]
        for field in V10_NEW_COURSE_FIELDS:
            self.assertIsNone(course[field], field)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM courses WHERE level IS NULL"), 1)
        # NULL is a value the schema describes, not a row the reader refuses.
        self.assertEqual(contracts.contract("cb.db")["tables"]["courses"]["columns"]["level"]["nullable"], True)

    def test_a_v9_job_brief_still_creates_a_plan_job(self) -> None:
        created = self.ok("jobs.create", {"kind": "plan",
                                          "brief": {"goal": "Braise", "recipe": "casual"}})["result"]
        self.assertEqual(created["state"], "queued")
        job = self.ok("jobs.get", {"job_id": created["job_id"]})["result"]["job"]
        self.assertEqual(job["brief"], {"goal": "Braise", "recipe": "casual"})

    def test_an_unknown_plan_brief_field_never_reaches_a_job_row(self) -> None:
        error = self.err("jobs.create", {"kind": "plan",
                                         "brief": {"goal": "Braise", "scop": "full"}})
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 0)


def _outline_result(*, plan: dict | None | str = "default", objectives: list | None = None) -> dict:
    if plan == "default":
        plan = {
            "plan_id": "pln_12345678",
            "version": 2,
            "state": "approved",
            "plan_hash": "sha256:" + "b" * 64,
        }
    return {
        "enrollment_id": "enr_12345678",
        "plan": plan,
        "objectives": objectives if objectives is not None else [_outline_objective()],
        "total": 1 if objectives is None else len(objectives),
        "truncated": False,
    }


def _outline_objective(**overrides) -> dict:
    objective = {
        "objective_id": "obj_12345678",
        "ordinal": 1,
        "title": "Choose an appropriate expression for this addressee",
        "evidence_target": "production",
        "state": "independent_evidence",
        "check_state": "closed",
        "attempt_count": 2,
        "independent": True,
        "last_opened_at": "2026-11-06T00:00:00+00:00",
    }
    objective.update(overrides)
    return objective


def _check_result(**overrides) -> dict:
    result = {
        "check_id": "chk_12345678",
        "objective_id": "obj_12345678",
        "check_version": 1,
        "evidence_target": "production",
        "state": "open",
        "audit_state": "passed",
        "stimulus": {
            "prompt": "You are thanking a professor. Which expression do you use?",
            "format": "selection",
            "choices": ["ありがとう", "ありがとうございます", "どうも"],
            "learner_instructions": "Choose one option.",
        },
        "attempt_count": 0,
    }
    result.update(overrides)
    return result


class V11AmendmentTest(unittest.TestCase):
    """H-21 slice A: the unit contract and the typed prerequisite refusal, additively.

    v11 freezes the wire and storage shapes docs/COURSE-BLUEPRINT.md section 14.2 R1-R9 need,
    without shipping the handlers: a v10 payload still validates, a legacy plan still projects
    exactly what it projected, and no v10 field moved.
    """

    R9_UNIT_KEYS = {
        "ordinal", "title", "goal", "prereq_unit_ordinals", "prerequisite_state", "unmet",
        "objectives",
    }

    def test_v11_is_additive_over_v10_and_keeps_the_method_enum(self) -> None:
        v10 = _document("rpc.v10.json")
        current = contracts.contract("cb.rpc")
        self.assertEqual(current["x-contract-version"], 11)
        self.assertEqual(current["$id"], "https://contracts.coursebook.hermes/rpc/v11")
        self.assertEqual(current["x-supersedes"], "https://contracts.coursebook.hermes/rpc/v10")
        self.assertEqual(list(contracts.method_names()), v10["$defs"]["method"]["enum"])
        self.assertEqual(contracts.audit_contracts(), [])

    def test_every_v10_method_payload_is_carried_over_verbatim(self) -> None:
        v10 = _document("rpc.v10.json")
        current = contracts.contract("cb.rpc")
        for method in v10["$defs"]["method"]["enum"]:
            with self.subTest(method=method):
                original = v10["$defs"]["methods"]["properties"][method]
                carried = json.loads(json.dumps(
                    current["$defs"]["methods"]["properties"][method]
                ))
                for field in V11_ADDED_REQUEST_FIELDS.get(method, ()):
                    carried["request"]["properties"].pop(field)
                for field in V11_ADDED_RESPONSE_FIELDS.get(method, ()):
                    carried["response"]["properties"].pop(field)
                    required = carried["response"].get("required") or []
                    if field in required:
                        required.remove(field)
                if method == "health.get":
                    original = json.loads(json.dumps(original))
                    original["response"]["properties"]["contract_version"] = {
                        "const": contracts.WIRE_CONTRACT_VERSION
                    }
                self.assertEqual(original, _normalise_refresh_refs(carried))

    def test_plan_brief_takes_one_ordinal_and_the_unit_section_stage(self) -> None:
        brief = contracts.contract("cb.rpc")["$defs"]["plan_brief"]
        self.assertIs(brief["additionalProperties"], False)
        ordinal = brief["properties"]["unit_ordinal"]
        self.assertEqual(ordinal["type"], "integer")
        self.assertEqual(ordinal["minimum"], 1)
        self.assertEqual(ordinal["maximum"], 12)
        self.assertNotIn("unit_ordinal", brief.get("required", []))
        self.assertEqual(set(brief["properties"]["stage"]["enum"]),
                         {"plan", "lessons", "unit_sections"})
        # The closed brief still accepts a unit-scoped authoring job and still refuses a typo.
        contracts.validate_request_payload(
            "jobs.create",
            {"kind": "plan", "brief": {"stage": "unit_sections", "plan_id": "pln_12345678",
                                       "unit_ordinal": 2}},
        )
        for impossible in (0, 13, "2", True):
            with self.assertRaises(contracts.ContractError, msg=repr(impossible)):
                contracts.validate_request_payload(
                    "jobs.create",
                    {"kind": "plan", "brief": {"stage": "unit_sections",
                                               "plan_id": "pln_12345678",
                                               "unit_ordinal": impossible}},
                )
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "jobs.create",
                {"kind": "plan", "brief": {"stage": "unit_sections", "plan_id": "pln_12345678",
                                           "unit_ordinals": [1]}},
            )

    def test_outline_unit_projection_has_exactly_the_r9_key_set(self) -> None:
        defs = contracts.contract("cb.rpc")["$defs"]
        unit = defs["outline_unit"]
        self.assertIs(unit["additionalProperties"], False)
        self.assertEqual(set(unit["properties"]), self.R9_UNIT_KEYS)
        self.assertEqual(set(unit["required"]), self.R9_UNIT_KEYS)
        self.assertEqual(_schema_problems(unit), [])
        self.assertEqual(set(unit["properties"]["prerequisite_state"]["enum"]),
                         {"no_edges", "satisfied", "unmet"})
        self.assertEqual(unit["properties"]["prereq_unit_ordinals"]["items"]["maximum"], 12)
        self.assertEqual(unit["properties"]["prereq_unit_ordinals"]["maxItems"], 11)
        self.assertEqual(unit["properties"]["objectives"]["items"]["$ref"],
                         "#/$defs/outline_objective")
        # The plan carries the additive unit index and the objective its own ordinal only.
        plan = defs["outline_plan"]
        self.assertEqual(set(plan["required"]), {"plan_id", "version", "state", "plan_hash"})
        self.assertEqual(plan["properties"]["units"]["items"]["$ref"], "#/$defs/outline_unit")
        self.assertNotIn("units", plan.get("required", []))
        objective = defs["outline_objective"]
        self.assertEqual(objective["properties"]["unit"]["type"], "integer")
        self.assertEqual(objective["properties"]["unit"]["maximum"], 12)
        self.assertNotIn("unit", objective.get("required", []))
        # R7: the projection exposes no score, probability, readiness or mastery field.
        names = set()
        for key in ("outline_unit", "prerequisite_state", "prerequisite_unmet_objective"):
            names |= set(defs[key]["properties"])
        self.assertFalse(names & {"score", "probability", "readiness", "mastery", "ready",
                                  "percent", "percentage", "weight"})

    def test_work_commands_take_the_ack_and_can_return_the_disclosure(self) -> None:
        defs = contracts.contract("cb.rpc")["$defs"]
        for method in ("lesson.begin", "check.open"):
            with self.subTest(method=method):
                entry = defs["methods"]["properties"][method]
                request = entry["request"]["properties"]
                ack = request["acknowledge_prerequisites"]
                self.assertEqual(ack["type"], "boolean")
                self.assertEqual(ack["default"], False)
                self.assertNotIn("acknowledge_prerequisites", entry["request"]["required"])
                state = entry["response"]["properties"]["prerequisite_state"]
                self.assertEqual(state["oneOf"][0]["$ref"], "#/$defs/prerequisite_state")
                self.assertEqual(state["oneOf"][1], {"type": "null"})
                self.assertNotIn("prerequisite_state", entry["response"].get("required", []))
                self.assertIs(entry["request"]["additionalProperties"], False)
                self.assertIs(entry["response"]["additionalProperties"], False)
        # A v10 payload (no flag, no new response field) still validates on both.
        contracts.validate_request_payload(
            "lesson.begin", {"enrollment_id": "enr_12345678", "objective_id": "obj_12345678",
                             "mode": "fresh"})
        contracts.validate_request_payload(
            "check.open", {"enrollment_id": "enr_12345678", "objective_id": "obj_12345678"})

    def test_prerequisite_unmet_is_a_typed_refusal(self) -> None:
        self.assertEqual(contracts.CONTRACT_FILES["cb.errors"], "errors.v3.json")
        self.assertIn("PREREQUISITE_UNMET", contracts.error_codes())
        catalog = contracts.error_catalog()["PREREQUISITE_UNMET"]
        self.assertEqual(catalog["category"], "state")
        self.assertEqual(catalog["http"], 409)
        self.assertFalse(catalog["retryable"])
        # Additive over v2: the v2 snapshot is untouched and does not carry the new code.
        self.assertNotIn("PREREQUISITE_UNMET",
                         _document("errors.v2.json")["code_catalog"])
        self.assertEqual(
            hashlib.sha256((contracts.CONTRACT_DIR / "errors.v2.json").read_bytes()).hexdigest(),
            "27b666a42654d2207f1dd2475c0941d5543c27527b5aa03a2c30491582d39fb6",
        )

    def test_db_v7_freezes_unit_storage_additively(self) -> None:
        v6 = _document("db.v6.json")
        current = contracts.contract("cb.db")
        self.assertEqual(current["x-contract-version"], 7)
        self.assertEqual(current["schema_version"], 7)
        self.assertEqual(current["x-supersedes"], "https://contracts.coursebook.hermes/db/v6")
        # Every v6 table and every v6 column survives; v7 only adds.
        for table, spec in v6["tables"].items():
            self.assertIn(table, current["tables"])
            for column, definition in spec["columns"].items():
                self.assertEqual(current["tables"][table]["columns"][column], definition,
                                 f"{table}.{column} changed")
        units = current["tables"]["plan_units"]
        self.assertEqual(set(units["columns"]),
                         {"id", "plan_id", "ordinal", "title", "goal",
                          "prereq_unit_ordinals_json", "target_lessons", "created_at"})
        self.assertEqual(units["unique"], [["plan_id", "ordinal"]])
        self.assertIn("unit_id", current["tables"]["objectives"]["columns"])
        section = current["tables"]["gen_plan_sections"]["columns"]
        self.assertIn("unit_id", section)
        self.assertEqual(section["section_role"]["default"], "owner")
        migration = [entry for entry in current["migration_plan"] if entry["version"] == 7]
        self.assertEqual(len(migration), 1)
        self.assertEqual(migration[0]["migration"], "0007_plan_units.sql")
        self.assertTrue(any("Additive only" in line for line in migration[0]["impact"]))
        self.assertTrue(any("No backfill" in line for line in migration[0]["impact"]))
        sql = (contracts.CONTRACT_DIR.parent / "coursebook" / "migrations"
               / migration[0]["migration"]).read_text(encoding="utf-8")
        for statement in (
            "CREATE TABLE plan_units",
            "ALTER TABLE objectives ADD COLUMN unit_id TEXT",
            "ALTER TABLE gen_plan_sections ADD COLUMN unit_id TEXT",
            "ALTER TABLE gen_plan_sections ADD COLUMN section_role TEXT NOT NULL DEFAULT 'owner'",
        ):
            self.assertIn(statement, sql)

    def test_superseded_v10_snapshots_are_byte_identical(self) -> None:
        for filename in ("rpc.v10.json", "db.v6.json"):
            expected = {**FROZEN_RPC_SHA256, **FROZEN_DB_SHA256}[filename]
            digest = hashlib.sha256((contracts.CONTRACT_DIR / filename).read_bytes()).hexdigest()
            self.assertEqual(f"sha256:{digest}", expected)
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v11.json")
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v7.json")

    def test_docs_publish_the_v11_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v11 delta (H-21)",
            "rpc.v11.json",
            "db.v7.json",
            "errors.v3.json",
            "0007_plan_units.sql",
            "unit_sections",
            "PREREQUISITE_UNMET",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class ChecklistConfirmationWireTest(unittest.TestCase):
    """H-34 (`docs/CHECKLIST-CONFIRMATION.md` §2.1): the confirmation needs no v11.

    A verification checklist is confirmed by an existing ``selection`` answer over the check's
    declared item ids. The ``answer`` object is closed, so no confirmation field can be invented
    and nothing about ``cb.rpc`` moved.
    """

    def payload(self, answer: dict) -> dict:
        return {
            "enrollment_id": "enr_12345678",
            "check_id": "chk_12345678",
            "check_version": 1,
            "attempt_nonce": "nonce-confirm-1",
            "answer": answer,
        }

    def test_selection_of_declared_item_ids_is_wire_legal(self) -> None:
        contracts.validate_request_payload(
            "attempt.submit",
            self.payload({"kind": "selection", "selection": ["item_1", "item_2", "item_3"]}),
        )

    def test_an_extra_key_inside_answer_is_refused(self) -> None:
        with self.assertRaises(contracts.ContractError):
            contracts.validate_request_payload(
                "attempt.submit",
                self.payload({
                    "kind": "selection",
                    "selection": ["item_1"],
                    "confirmations": ["item_1"],
                }),
            )

    def test_the_wire_version_moved_only_for_the_blueprint(self) -> None:
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 11)
        answer = contracts.method_schema("attempt.submit")["request"]["properties"]["answer"]
        self.assertFalse(answer["additionalProperties"])
        self.assertEqual(sorted(answer["properties"]), ["kind", "selection", "text"])


if __name__ == "__main__":
    unittest.main()

