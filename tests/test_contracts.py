"""Contract-set invariants: ids, versions, cross-document references, integrity hashes.

CB-018 amended the set to v2, CB-022 to v3, CB-024 to v4. These tests fail if the new methods,
their payload schemas, the version links, the storage decisions, the pack-check projection or the
documented UX mapping disappear.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from coursebook import api, contracts, db
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

#: Fields cb.rpc v12 (H-26) appended to a shipped method: the optional syllabus binding on
#: ``course.create``. They travel together or not at all; the carried-over comparison removes them.
V12_ADDED_REQUEST_FIELDS: dict[str, tuple[str, ...]] = {
    "course.create": ("syllabus_id", "syllabus_revision"),
}

#: Fields cb.rpc v17 (H-106) appended to the *source item* inside two shipped responses. All six
#: are optional; no required list moved. The carried-over comparisons remove exactly these from the
#: live payload before comparing it to every earlier snapshot.
V17_SOURCE_PROVENANCE_FIELDS: tuple[str, ...] = (
    "excerpt",
    "excerpt_state",
    "content_hash",
    "modality",
    "licence",
    "support_assessment",
)
V17_ADDED_SOURCE_ITEMS: tuple[str, ...] = ("lesson.page", "parent.blueprint.read")

#: H-185 / cb.rpc v18 appends one *optional* response property to ``lesson.page``: the lesson
#: provenance block (``outcome``/``independent``/``warning``). It is never required, so the
#: carried-over comparison only has to drop the property.
V18_ADDED_RESPONSE_FIELDS: dict[str, tuple[str, ...]] = {"lesson.page": ("provenance",)}

#: H-194b / cb.rpc v20 appends one *required* response array to ``parent.blueprint.read``:
#: ``sections``, the section identity a fine-tune call needs (the H-194 UI could not reach
#: ``lesson.revise``/``lesson.regenerate`` without it). The carried-over comparisons drop the
#: property and its ``required`` entry before comparing to every earlier snapshot.
V20_ADDED_RESPONSE_FIELDS: dict[str, tuple[str, ...]] = {"parent.blueprint.read": ("sections",)}

#: GM-004 / cb.rpc v24 appends one *optional* request property to ``course.create``:
#: ``presentation_mode``, the creation-time Game/Textbook intent. It is never required, so the
#: carried-over comparison only has to drop the property before comparing the live wire to a
#: snapshot that predates it.
V24_ADDED_REQUEST_FIELDS: dict[str, tuple[str, ...]] = {"course.create": ("presentation_mode",)}


def _without_v24_course_create_intent(payload: dict, method: str) -> dict:
    """Undo GM-004's optional ``course.create.presentation_mode`` for a carried-over comparison."""
    for field in V24_ADDED_REQUEST_FIELDS.get(method, ()):
        (payload.get("request", {}).get("properties") or {}).pop(field, None)
    return payload


def _without_v17_source_fields(payload: dict, method: str) -> dict:
    """Undo v17's additive source-item fields and v18's provenance for a carried-over comparison."""
    carried = _without_v24_course_create_intent(json.loads(json.dumps(payload)), method)
    if method not in V17_ADDED_SOURCE_ITEMS:
        return carried
    items = carried["response"]["properties"]["sources"]["items"]
    for field in V17_SOURCE_PROVENANCE_FIELDS:
        items["properties"].pop(field, None)
    # The six fields are optional, so no `required` entry is ever removed here.
    return _without_v18_provenance(carried, method)


def _without_v18_provenance(payload: dict, method: str) -> dict:
    """Undo v18's ``lesson.page.provenance`` and v20's ``sections`` for a carried-over comparison."""
    carried = json.loads(json.dumps(payload))
    for field in V18_ADDED_RESPONSE_FIELDS.get(method, ()):
        carried["response"]["properties"].pop(field, None)
        required = carried["response"].get("required") or []
        if field in required:
            required.remove(field)
    return _without_v20_sections(carried, method)


def _without_v20_sections(payload: dict, method: str) -> dict:
    """Undo v20's additive response fields for a carried-over comparison."""
    carried = json.loads(json.dumps(payload))
    for field in V20_ADDED_RESPONSE_FIELDS.get(method, ()):
        carried["response"]["properties"].pop(field, None)
        required = carried["response"].get("required") or []
        if field in required:
            required.remove(field)
    return _without_v20_plan_validation(carried, method)


def _without_v20_plan_validation(payload: dict, method: str) -> dict:
    """Undo the H-182/D3 ``plan.validation`` projection inside ``parent.blueprint.read``."""
    carried = json.loads(json.dumps(payload))
    if method != "parent.blueprint.read":
        return carried
    plan = carried["response"]["properties"]["plan"]
    for option in plan.get("oneOf") or []:
        if isinstance(option, dict) and isinstance(option.get("properties"), dict):
            option["properties"].pop("validation", None)
    return carried


def _normalise_refresh_refs(payload: dict) -> dict:
    """Undo a pure cross-document reference refresh for a carried-over comparison.

    v11 moved ``cb.rpc``'s job-state references from ``cb.jobs`` v2 to v3: v3 is a reference-only
    refresh of the same states. Historical carried-over tests compare payload shape, not the
    version number inside a ``$ref``, so the current reference is mapped back to the snapshot's.
    """
    raw = json.dumps(payload)
    raw = raw.replace(
        "https://contracts.coursebook.hermes/jobs/v4#",
        "https://contracts.coursebook.hermes/jobs/v2#",
    )
    raw = raw.replace(
        "https://contracts.coursebook.hermes/jobs/v3#",
        "https://contracts.coursebook.hermes/jobs/v2#",
    )
    # v15 refreshed the reference to the additive cb.jobs v5 (`activity` on the job object); the
    # historical snapshots compare payload shape, so the version inside the ref is mapped back.
    raw = raw.replace(
        "https://contracts.coursebook.hermes/jobs/v5#",
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
    for field in V18_ADDED_RESPONSE_FIELDS.get(method, ()):
        carried["response"]["properties"].pop(field, None)
        required = carried["response"].get("required") or []
        if field in required:
            required.remove(field)
    request = carried["request"]
    for field in V10_ADDED_METHOD_FIELDS.get(method, ()):
        (request.get("properties") or {}).pop(field, None)
    for field in V11_ADDED_REQUEST_FIELDS.get(method, ()):
        (request.get("properties") or {}).pop(field, None)
    for field in V12_ADDED_REQUEST_FIELDS.get(method, ()):
        (request.get("properties") or {}).pop(field, None)
    if method == "jobs.create":
        # v10 applies a closed `$defs/plan_brief` to `kind = "plan"`; the open bounded brief
        # object every earlier snapshot froze is untouched.
        request.pop("allOf", None)
    return _normalise_refresh_refs(_without_v18_provenance(_without_v17_source_fields(carried, method), method))


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
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 26)
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, contracts.contract_version("cb.rpc"))
        self.assertTrue(str(contracts.contract("cb.rpc")["$id"]).endswith("/rpc/v26"))
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
                        "sections_done": 2,
                        "sections_total": 6,
                        "checks_recorded": 2,
                        "is_new": False,
                        "subject_label": "language",
                        "cover_artifact_id": None,
                        "last_studied_at": "2026-11-06T00:00:00Z",
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


class V3AmendmentTest(KernelCase):
    """CB-022: the additive v3 amendment that gives the review queue and Evidence tab a command path.

    CB-008 implemented the semantics (``coursebook/review.py``, ``coursebook/evidence.py``); these
    tests hold the contract to *that* backend: same field names, no second revision authority, no
    reference answer in the evidence view, and no storage claim that the database does not keep.

    Isolation is part of the contract (t_7dee7265): the handler assertions below reach the real
    kernel and answer ``NOT_FOUND`` only because a migrated store is present. As a plain
    ``unittest.TestCase`` this class opened whatever profile store the runner's ``HERMES_HOME``
    pointed at — a locked, corrupt or older-schema store turned those four assertions into
    ``INTERNAL_ERROR``. ``KernelCase`` owns a throwaway home per test, so the answer can no longer
    depend on the developer's profile.
    """

    def test_the_class_runs_against_its_own_store_not_the_ambient_profile(self) -> None:
        """Regression guard: a store the class does not own must never decide these assertions."""
        self.assertIsInstance(
            self,
            KernelCase,
            "V3AmendmentTest must inherit KernelCase: as a plain TestCase it resolves the ambient "
            "profile store, and a stale, locked or corrupt one answers INTERNAL_ERROR where the "
            "contract says NOT_FOUND (t_7dee7265)",
        )
        store = db.store_root().resolve()
        self.assertTrue(
            db.within(store, Path(self.home).resolve()),
            f"the class resolved its store to {store}, outside its per-test home {self.home}",
        )

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
        self.assertEqual(_document("errors.v3.json")["x-contract-version"], 3)
        tables = _document("db.v2.json")["tables"]
        for absent in ("review_schedule", "review_items", "disputes"):
            self.assertNotIn(absent, tables)
        v2_codes = set(_document("errors.v2.json")["code_catalog"])
        # cb.errors moved to v3 for cb.rpc v11's PREREQUISITE_UNMET; this amendment added none.
        # The live catalog moved on to v4 (H-26), so the era snapshot is the authority here.
        self.assertEqual(set(_document("errors.v3.json")["code_catalog"]),
                         v2_codes | {"PREREQUISITE_UNMET"})
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
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        v2_codes = set(_document("errors.v2.json")["code_catalog"])
        # cb.errors moved to v3 for cb.rpc v11's PREREQUISITE_UNMET; this amendment added none.
        # The live catalog moved on to v4 (H-26), so the era snapshot is the authority here.
        self.assertEqual(set(_document("errors.v3.json")["code_catalog"]),
                         v2_codes | {"PREREQUISITE_UNMET"})
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
    "rpc.v13.json": "sha256:bbaecc2df974744256cd5a5472a6af90dfa1df2f772f8f0ede7d0a211195faaf",
    "rpc.v14.json": "sha256:b454fab7e5b9fbc5e8fb536954486d01b0a3c580b55b8858450734f37357cc4e",
    "rpc.v15.json": "sha256:5d689b0cffce9ce6043ed5c9e60ab27f3a68f31462a0cc27572147b08c3772e7",
    "rpc.v16.json": "sha256:9b10439576fd667f9554c638bd92a7fccffd7ecaef6cef81bd23e1414e3cf46d",
    "rpc.v17.json": "sha256:c8444ba5ee7fb7d89375deb1fa4f2595d2754761fdbd01e376f4725f37cbd997",
    "rpc.v18.json": "sha256:5ddeedcb327b4f0f9ab2d25574aeb40b9cba4f4864b0977f33a86a0bc8003164",
    "rpc.v19.json": "sha256:0ebc9efb2f1c3bc2dd6b3a756bc7ceab3a0502c6d0eef34031a1edd9a2b6d5f5",
    "rpc.v20.json": "sha256:81cf882fb6f9dddc5caf7706b9dfe23d1ace2d4dea16c11e4e0281cbdf150f07",
    "rpc.v21.json": "sha256:eb17550859d4bbc42541837d32ee17e4594901d4065a17a1f75b6488c2d17282",
    "rpc.v22.json": "sha256:c187728add6c508d5643e42225a64766d4b887cfce58250fb45d04707b6eb956",
    # GM-007: v23 (GM-005's take-home wire) is now immutable history, pinned byte-identical.
    "rpc.v23.json": "sha256:b8988994d36cf7e422da0010ed157d3c4ff7dd69b5f8453e9bd7da8b8b4d3182",
    # CP-005: v24 (the composed World Studio wire) is now immutable history too. The shelf-fact
    # amendment is a new file, never an edit to a document a client already pinned.
    "rpc.v24.json": "sha256:5d0484600be58cc69fad432afb88f44d4cba3dc03d6b8791eb25e625b22ecbae",
    # CP-052: v25 (the shelf-fact wire) is immutable history; `world_brief.route_anchors` is a
    # new document, not an edit to the one CP-005's client pinned.
    "rpc.v25.json": "sha256:02bd2b9304a55ebf8b79e581ef7740d1e265b8a136045bc51848ceb15889c130",
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
    "db.v8.json": "sha256:f47b0d5153530e4027f5ed589bf84d763dbc2cca814d51d29f2dd880f0b791a4",
    "db.v10.json": "sha256:8bfe23413db17614f61a43d3be176e7a376ddd6a6ffc38d611652368f9d9209f",
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
        for version in range(1, 22):
            # Not in the inventory, and not silently repurposed: history stays history.
            self.assertNotIn(f"rpc.v{version}.json", contracts.CONTRACT_FILES.values())
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v26.json")

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
        self.assertEqual(_document("errors.v3.json")["x-contract-version"], 3)
        # The live catalog moved on to v4 (H-26); this amendment added no code to v3.
        self.assertEqual(set(_document("errors.v3.json")["code_catalog"]),
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
        "sections": [],
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
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v26.json")
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v14.json")

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
        self.assertEqual(_document("errors.v3.json")["x-contract-version"], 3)
        # The live catalog moved on to v4 (H-26); this amendment added no code to v3.
        self.assertEqual(set(_document("errors.v3.json")["code_catalog"]),
                         set(_document("errors.v2.json")["code_catalog"]) | {"PREREQUISITE_UNMET"})
        # The one thing this card could not add: `lesson` as a job family. cb.vocabulary stays v1
        # because every pack manifest embeds a reference to it, so lesson generation runs as the
        # `plan` family with `brief.stage = lessons`. The decision is recorded in the docs.
        job_kind = contracts.contract("cb.vocabulary")["$defs"]["job_kind"]["enum"]
        self.assertNotIn("lesson", job_kind)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
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
        current = list(_document("rpc.v11.json")["$defs"]["method"]["enum"])
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
                # v12 adds the optional syllabus binding to course.create; it travels with
                # syllabus_revision and no earlier request field moved.
                for field in V12_ADDED_REQUEST_FIELDS.get(method, ()):
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
                self.assertEqual(
                    original,
                    _normalise_refresh_refs(_without_v17_source_fields(carried, method)),
                )
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
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
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
        current = list(_document("rpc.v11.json")["$defs"]["method"]["enum"])
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
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
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
        self.assertEqual(
            list(_document("rpc.v11.json")["$defs"]["method"]["enum"]),
            v9["$defs"]["method"]["enum"],
        )
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
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v26.json")
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v14.json")

    def test_v10_adds_no_error_code_and_no_vocabulary_change(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
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
        v11 = _document("rpc.v11.json")
        self.assertEqual(v11["x-contract-version"], 11)
        self.assertEqual(v11["$id"], "https://contracts.coursebook.hermes/rpc/v11")
        self.assertEqual(v11["x-supersedes"], "https://contracts.coursebook.hermes/rpc/v10")
        self.assertEqual(list(v11["$defs"]["method"]["enum"]), v10["$defs"]["method"]["enum"])
        # The live wire contract moved on to v13 (H-26's v12 plus H-08's export); v11's names
        # survive as a prefix and the live file supersedes exactly the version before it.
        current = contracts.contract("cb.rpc")
        self.assertEqual(
            current["x-supersedes"],
            f"https://contracts.coursebook.hermes/rpc/v{contracts.WIRE_CONTRACT_VERSION - 1}",
        )
        self.assertEqual(
            list(contracts.method_names())[: len(v10["$defs"]["method"]["enum"])],
            v10["$defs"]["method"]["enum"],
        )
        self.assertEqual(contracts.audit_contracts(), [])

    def test_every_v10_method_payload_is_carried_over_verbatim(self) -> None:
        v10 = _document("rpc.v10.json")
        current = _document("rpc.v11.json")
        for method in v10["$defs"]["method"]["enum"]:
            with self.subTest(method=method):
                original = v10["$defs"]["methods"]["properties"][method]
                carried = json.loads(json.dumps(
                    current["$defs"]["methods"]["properties"][method]
                ))
                for field in V11_ADDED_REQUEST_FIELDS.get(method, ()):
                    carried["request"]["properties"].pop(field)
                for field in V12_ADDED_REQUEST_FIELDS.get(method, ()):
                    carried["request"]["properties"].pop(field, None)
                for field in V11_ADDED_RESPONSE_FIELDS.get(method, ()):
                    carried["response"]["properties"].pop(field)
                    required = carried["response"].get("required") or []
                    if field in required:
                        required.remove(field)
                if method == "health.get":
                    # The one permitted difference: the version echo follows the wire version.
                    carried["response"]["properties"]["contract_version"] = (
                        original["response"]["properties"]["contract_version"]
                    )
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
        self.assertEqual(contracts.CONTRACT_FILES["cb.errors"], "errors.v4.json")
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
        current = _document("db.v7.json")
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
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v26.json")
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v14.json")

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


class V13AmendmentTest(unittest.TestCase):
    """H-08: v13 appends the two authored-course export commands to the v12 enum.

    The union this file tests is the one the integrator had to build by hand: the H-08 delta was
    authored against v11 (its snapshot file declares ``x-supersedes: rpc/v12``) while master had
    already moved to v12 for H-26's syllabus intake. v13 is therefore v12 plus exactly two methods:
    no earlier method, payload, error code, job kind, vocabulary value, cb.db table or migration
    moves, and ``pack.export`` keeps its allowlist.
    """

    NEW_METHODS = ("course.export.read", "course.export")

    def test_v13_is_v12_plus_two_appended_methods(self) -> None:
        # The snapshots, not the live inventory: v14 appended `observation.record` afterwards, so
        # this claim is about the v13 file as shipped (H-53 leaves it byte-identical).
        v12 = _document("rpc.v12.json")
        v12_methods = list(v12["$defs"]["method"]["enum"])
        self.assertEqual(len(v12_methods), 61)
        v13 = _document("rpc.v13.json")
        v13_methods = list(v13["$defs"]["method"]["enum"])
        self.assertEqual(len(v13_methods), 63)
        self.assertEqual(v13_methods[: len(v12_methods)], v12_methods, "append-only enum")
        self.assertEqual(sorted(set(v13_methods) - set(v12_methods)), sorted(self.NEW_METHODS))

    def test_v13_keeps_the_v12_payloads_verbatim(self) -> None:
        v12 = _document("rpc.v12.json")
        current = _document("rpc.v13.json")

        def normalise(payload: dict) -> dict:
            payload = _normalise_refresh_refs(json.loads(json.dumps(payload)))

            # v13 also carries the H-26b amendment: `fields` on a syllabus.get item and a relaxed
            # decisions minItems on syllabus.alignment.review. Strip exactly that delta so this
            # stays a v13-vs-v12 check.
            response_items = payload.get("response", {}).get("properties", {}).get("items")
            if isinstance(response_items, dict) and isinstance(response_items.get("items"), dict):
                properties = response_items["items"].get("properties")
                if isinstance(properties, dict):
                    properties.pop("fields", None)
            decisions = payload.get("request", {}).get("properties", {}).get("decisions")
            if isinstance(decisions, dict):
                decisions["minItems"] = 1

            def walk(node: object) -> None:
                if isinstance(node, dict):
                    if node.get("contract_version") == {"const": 12}:
                        node["contract_version"] = {"const": 13}
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)

            walk(payload)
            return payload

        for method in v12["$defs"]["method"]["enum"]:
            with self.subTest(method=method):
                self.assertEqual(
                    normalise(current["$defs"]["methods"]["properties"][method]),
                    normalise(v12["$defs"]["methods"]["properties"][method]),
                )

    def test_v13_adds_no_db_table_column_or_migration(self) -> None:
        # v13 froze against cb.db v8 and touched no storage. The v8 snapshot is still on disk as
        # shipped; cb.db has since moved to v9 for H-53's one nullable `evidence.note` column, to
        # v10 for H-124's `hook_errors` diagnostics table, to v11 for H-120's two practice
        # tables, to v12 for H-194's two fine-tune ledgers and to v13 for GM-001's Game Mode
        # storage (eight tables plus nullable courses.presentation_mode). Those are the whole
        # delta between the v13-era inventory and today's.
        v8 = _document("db.v8.json")
        current = contracts.contract("cb.db")
        self.assertEqual(v8["schema_version"], 8)
        self.assertEqual(
            set(current["tables"]) - set(v8["tables"]),
            {"hook_errors", "practice_sessions", "practice_turns",
             "plan_revisions", "lesson_revisions", "course_worlds", "world_assets",
             "takehome_packs", "homework_tasks", "homework_events", "game_engagement",
             "tutor_threads", "tutor_turns"},
        )
        added = {
            (table, column)
            for table, spec in v8["tables"].items()
            for column in set(current["tables"][table]["columns"]) - set(spec["columns"])
        }
        self.assertEqual(added, {("evidence", "note"), ("courses", "presentation_mode")})
        self.assertEqual(current["migration_plan"][: len(v8["migration_plan"])], v8["migration_plan"])

    def test_the_export_methods_have_a_review_read_and_a_hash_fenced_write(self) -> None:
        read = contracts.method_schema("course.export.read")
        self.assertEqual(set(read["request"]["required"]), {"enrollment_id"})
        write = contracts.method_schema("course.export")
        self.assertEqual(
            set(write["request"]["required"]), {"enrollment_id", "expected_content_hash"}
        )
        self.assertIs(write["request"]["additionalProperties"], False)

    def test_docs_publish_the_v13_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in ("rpc.v13.json", "course.export.read", "course.export", "course_pack_backed"):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V14AmendmentTest(unittest.TestCase):
    """H-53 (`t_6646238d`): v14 appends `observation.record`, cb.db v9 stores its note.

    The kernel has recorded layer-1 observations since CB-002 and `self_reported`/`parent_reported`
    are already frozen `cb.vocabulary` classes, but no client could reach
    `domain.record_observation` — the B-2 defect in `docs/ASSESSMENT-BREADTH.md` §11. v14 is v13
    plus exactly one method, and cb.db v9 is v8 plus exactly one nullable column. No check kind,
    answer kind, evidence-class value, error code, job kind, upload path or learner-media retention
    is added: an observation is never independent evidence.
    """

    METHOD = "observation.record"

    def payload(self, **overrides) -> dict:
        body = {
            "enrollment_id": "enr_12345678",
            "objective_id": "obj_12345678",
            "evidence_class": "parent_reported",
            "note": "Read the passage aloud to me without being asked.",
        }
        body.update(overrides)
        return body

    def test_v14_is_v13_plus_one_appended_method(self) -> None:
        v13 = _document("rpc.v13.json")
        v13_methods = list(v13["$defs"]["method"]["enum"])
        self.assertEqual(len(v13_methods), 63)
        # The v14 file as shipped: v14 is v13 plus exactly one appended method.
        v14 = _document("rpc.v14.json")
        v14_methods = list(v14["$defs"]["method"]["enum"])
        self.assertEqual(len(v14_methods), 64)
        self.assertEqual(v14_methods[: len(v13_methods)], v13_methods, "append-only enum")
        self.assertEqual(sorted(set(v14_methods) - set(v13_methods)), [self.METHOD])
        # Every later amendment is append-only over v14, so the live document still starts with
        # its 64 names in the same order.
        current = list(contracts.method_names())
        self.assertEqual(current[: len(v14_methods)], v14_methods, "append-only enum")
        self.assertTrue(set(v14_methods) <= set(current), "a v14 method was removed")

    def test_v14_keeps_every_v13_payload_verbatim(self) -> None:
        v13 = _document("rpc.v13.json")
        current = contracts.contract("cb.rpc")

        def normalise(payload: dict) -> dict:
            payload = _normalise_refresh_refs(json.loads(json.dumps(payload)))

            # The version echoes are the one thing a bump is allowed to move.
            def walk(node: object) -> None:
                if isinstance(node, dict):
                    if node.get("contract_version") == {"const": 13}:
                        node["contract_version"] = {"const": contracts.WIRE_CONTRACT_VERSION}
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)

            walk(payload)
            return payload

        for method in v13["$defs"]["method"]["enum"]:
            with self.subTest(method=method):
                self.assertEqual(
                    normalise(_without_v17_source_fields(
                        current["$defs"]["methods"]["properties"][method], method)),
                    normalise(v13["$defs"]["methods"]["properties"][method]),
                )

    def test_the_v13_snapshot_is_superseded_history(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v13.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v13.json"])
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v26.json")
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 26)
        # v26 supersedes v25; v25 supersedes v24, v24 supersedes v23, and the older files remain
        # frozen predecessors pinned on disk.
        self.assertEqual(contracts.contract("cb.rpc")["x-supersedes"],
                         "https://contracts.coursebook.hermes/rpc/v25")

    def test_the_method_writes_one_layer_one_evidence_row(self) -> None:
        schema = contracts.method_schema(self.METHOD)
        request, response = schema["request"], schema["response"]
        self.assertEqual(set(request["required"]), {"enrollment_id", "objective_id", "evidence_class"})
        self.assertEqual(
            set(request["properties"]),
            {"enrollment_id", "objective_id", "evidence_class", "note"},
        )
        self.assertEqual(set(response["required"]), {"evidence_id", "evidence_class", "revision"})
        self.assertEqual(set(response["properties"]), {"evidence_id", "evidence_class", "revision"})
        # No attempt, no check state, no verdict, no transition: this is an append, not a grade.
        for forbidden in ("attempt_id", "attempt", "verdict", "next_action", "state", "layer", "kind"):
            self.assertNotIn(forbidden, response["properties"], forbidden)
        self.assertEqual(_schema_problems(request, "request"), [])
        self.assertEqual(_schema_problems(response, "response"), [])

    def test_the_evidence_class_is_the_full_frozen_vocabulary(self) -> None:
        # Closure is the kernel's policy decision, not a wire enum a client must reverse-engineer:
        # the schema accepts all six labels and the kernel refuses four with POLICY_VIOLATION.
        declared = contracts.method_schema(self.METHOD)["request"]["properties"]["evidence_class"]
        self.assertEqual(
            declared["$ref"],
            "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/evidence_class",
        )
        vocabulary = list(contracts.contract("cb.vocabulary")["$defs"]["evidence_class"]["enum"])
        self.assertEqual(
            sorted(vocabulary),
            ["answer_shown", "cold", "hinted", "override", "parent_reported", "self_reported"],
        )
        for evidence_class in vocabulary:
            with self.subTest(evidence_class=evidence_class):
                contracts.validate_request_payload(self.METHOD, self.payload(evidence_class=evidence_class))

    def test_the_note_is_optional_and_bounded_at_one_thousand(self) -> None:
        note = contracts.method_schema(self.METHOD)["request"]["properties"]["note"]
        branches = {option.get("type"): option for option in note["oneOf"]}
        self.assertEqual(branches["string"]["maxLength"], 1000)
        self.assertEqual(branches["string"]["minLength"], 0)
        self.assertIn("null", branches)
        for case in ("omitted", None, "", "x" * 1000):
            payload = self.payload()
            payload.pop("note", None)
            if case != "omitted":
                payload["note"] = case
            with self.subTest(note=case):
                contracts.validate_request_payload(self.METHOD, payload)

    def test_a_request_outside_the_bounds_is_refused(self) -> None:
        cases = {
            "note over the cap": {"note": "x" * 1001},
            "note of the wrong type": {"note": 7},
            "class outside the vocabulary": {"evidence_class": "model_assessed"},
            "unknown key": {"confidence": 0.9},
        }
        for label, overrides in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(contracts.ContractError):
                    contracts.validate_request_payload(self.METHOD, self.payload(**overrides))
        for missing in ("enrollment_id", "objective_id", "evidence_class"):
            with self.subTest(missing=missing):
                payload = self.payload()
                payload.pop(missing)
                with self.assertRaises(contracts.ContractError):
                    contracts.validate_request_payload(self.METHOD, payload)

    def test_the_envelope_requires_an_idempotency_key_and_no_revision_fence(self) -> None:
        # A double click must not mint two evidence rows: the key is the fence. An append that
        # cannot move the aggregate is deliberately not gated by `expected_revision`.
        with self.assertRaises(contracts.ContractError):
            contracts.validate("cb.rpc", _envelope(self.METHOD, self.payload()))
        contracts.validate(
            "cb.rpc",
            _envelope(self.METHOD, self.payload(), idempotency_key="obs-record-cb-h53-1"),
        )

    def test_db_v9_adds_only_a_nullable_note_column(self) -> None:
        v8 = _document("db.v8.json")
        current = _document("db.v9.json")
        self.assertEqual(current["schema_version"], 9)
        self.assertEqual(current["x-supersedes"], "https://contracts.coursebook.hermes/db/v8")
        self.assertEqual(set(current["tables"]), set(v8["tables"]))
        for table, spec in v8["tables"].items():
            for column, definition in spec["columns"].items():
                self.assertEqual(
                    current["tables"][table]["columns"][column], definition,
                    f"{table}.{column} changed",
                )
        added = {
            (table, column)
            for table, spec in v8["tables"].items()
            for column in set(current["tables"][table]["columns"]) - set(spec["columns"])
        }
        self.assertEqual(added, {("evidence", "note")})
        note = current["tables"]["evidence"]["columns"]["note"]
        self.assertEqual(note["type"], "TEXT")
        self.assertTrue(note["nullable"], "a pre-v9 evidence row has no note and must stay valid")
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v14.json")

    def test_the_migration_is_forward_only_and_rewrites_no_row(self) -> None:
        plan = contracts.contract("cb.db")["migration_plan"]
        entry = next(item for item in plan if item["version"] == 9)
        self.assertEqual(entry["from"], 8)
        self.assertEqual(entry["migration"], "0009_evidence_note.sql")
        self.assertTrue(any("Additive only" in line for line in entry["impact"]))
        self.assertTrue(any("No backfill" in line for line in entry["impact"]))
        sql = (
            contracts.CONTRACT_DIR.parent / "coursebook" / "migrations" / entry["migration"]
        ).read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE evidence ADD COLUMN note TEXT", sql)
        statements = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        for forbidden in ("UPDATE ", "DELETE ", "DROP ", "INSERT ", "CREATE TABLE"):
            self.assertNotIn(forbidden, statements, forbidden)

    def test_docs_publish_the_v14_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v14 delta (H-53)",
            "rpc.v15.json",
            "db.v9.json",
            "observation.record",
            "0009_evidence_note.sql",
            "B-2",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")

    def test_the_checklist_decision_no_longer_calls_the_method_v12(self) -> None:
        text = (
            contracts.CONTRACT_DIR.parent / "docs" / "CHECKLIST-CONFIRMATION.md"
        ).read_text(encoding="utf-8")
        stale = [
            line for line in text.splitlines() if "observation.record" in line and "v12" in line
        ]
        self.assertEqual(stale, [], f"CHECKLIST-CONFIRMATION.md still says v12: {stale}")


class DbV10AmendmentTest(unittest.TestCase):
    """H-124 (`t_e3f0d994`): cb.db v10 records a lost teaching snapshot; cb.rpc does not move.

    ``hooks.post_llm_call`` is the only writer of a teaching segment. A failed write used to be
    swallowed, so the turn vanished from the lesson page with no marker (H-114 F3). v10 is v9 plus
    exactly one diagnostics table, ``hook_errors``, and no column changes. The pane still reads it
    through ``binding.get`` because the ``binding`` object in ``cb.rpc`` is deliberately open —
    asserting that here is what keeps "no rpc version bump" a checked fact rather than a hope.
    """

    def test_v10_is_v9_plus_one_diagnostics_table(self) -> None:
        v9 = _document("db.v9.json")
        # The v10 file as shipped, not the live inventory: cb.db has since moved to v11 (H-120).
        v10 = _document("db.v10.json")
        self.assertEqual(v10["schema_version"], 10)
        self.assertEqual(v10["x-supersedes"], "https://contracts.coursebook.hermes/db/v9")
        self.assertEqual(set(v10["tables"]) - set(v9["tables"]), {"hook_errors"})
        self.assertEqual(set(v9["tables"]) - set(v10["tables"]), set(), "v10 dropped a table")
        for table, spec in v9["tables"].items():
            self.assertEqual(
                v10["tables"][table]["columns"], spec["columns"], f"{table} columns changed"
            )
            self.assertEqual(
                v10["tables"][table].get("indexes"), spec.get("indexes"),
                f"{table} indexes changed",
            )
        # v11 is additive over v10 too: two new tables, and no v10 table, column or index moves.
        # v12 adds the two fine-tune ledgers, v13 adds the eight Game Mode tables and exactly one
        # nullable column (courses.presentation_mode), and neither moves a v10 table or index.
        current = contracts.contract("cb.db")
        self.assertEqual(
            set(current["tables"]) - set(v10["tables"]),
            {"practice_sessions", "practice_turns", "plan_revisions", "lesson_revisions",
             "course_worlds", "world_assets", "takehome_packs", "homework_tasks",
             "homework_events", "game_engagement", "tutor_threads", "tutor_turns"},
        )
        self.assertEqual(set(v10["tables"]) - set(current["tables"]), set(), "v11 dropped a table")
        for table, spec in v10["tables"].items():
            expected_columns = dict(spec["columns"])
            if table == "courses":
                expected_columns["presentation_mode"] = (
                    current["tables"]["courses"]["columns"]["presentation_mode"]
                )
            self.assertEqual(
                current["tables"][table]["columns"], expected_columns, f"{table} columns changed"
            )
            self.assertEqual(
                current["tables"][table].get("indexes"), spec.get("indexes"),
                f"{table} indexes changed",
            )
        self.assertEqual(contracts.CONTRACT_FILES["cb.db"], "db.v14.json")

    def test_hook_errors_is_diagnostics_and_names_only_the_snapshot_loss(self) -> None:
        table = contracts.contract("cb.db")["tables"]["hook_errors"]
        self.assertEqual(
            table["columns"]["kind"]["enum"], ["snapshot_write_failed"],
            "the diagnostics table must not become a general-purpose error log",
        )
        self.assertTrue(table["columns"]["lesson_run_id"]["nullable"])
        self.assertEqual(table["columns"]["lesson_run_id"]["ref"], "lesson_runs.id")
        self.assertEqual(table["columns"]["attempts"]["default"], "1")
        self.assertIn(["lesson_run_id"], table["indexes"])

    def test_the_v10_migration_is_additive_and_rewrites_no_row(self) -> None:
        plan = contracts.contract("cb.db")["migration_plan"]
        entry = next(item for item in plan if item["version"] == 10)
        self.assertEqual(entry["from"], 9)
        self.assertEqual(entry["migration"], "0010_hook_errors.sql")
        self.assertTrue(any("Additive only" in line for line in entry["impact"]))
        sql = (
            contracts.CONTRACT_DIR.parent / "coursebook" / "migrations" / entry["migration"]
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE hook_errors", sql)
        statements = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        for forbidden in ("UPDATE ", "DELETE ", "DROP ", "ALTER ", "INSERT "):
            self.assertNotIn(forbidden, statements, forbidden)

    def test_the_pane_read_needs_no_rpc_bump(self) -> None:
        """``binding`` is an open object, so ``snapshot_failures`` is not a contract amendment."""
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v26.json")
        binding = contracts.method_schema("binding.get")["response"]["properties"]["binding"]
        closed = binding["oneOf"][1]
        self.assertNotIn(
            "additionalProperties", closed,
            "binding became a closed object: snapshot_failures would now need a cb.rpc version",
        )

    def test_docs_publish_the_v10_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v10 delta (H-124)",
            "db.v10.json",
            "0010_hook_errors.sql",
            "hook_errors",
            "snapshot_failures",
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
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 26)
        answer = contracts.method_schema("attempt.submit")["request"]["properties"]["answer"]
        self.assertFalse(answer["additionalProperties"])
        self.assertEqual(sorted(answer["properties"]), ["kind", "selection", "text"])


class V15AmendmentTest(unittest.TestCase):
    """H-139 (`t_a9160a86`): v15 is a reference refresh, cb.jobs v5 adds ``activity``.

    The pane needs to render an honest stage while a generation runs. Every fact it needs is
    already durable; the amendment exposes it as one read-only ``job.activity`` object. No method
    is added, no request changes, no error code, job kind, state or transition moves, and no
    percentage is introduced.
    """

    def test_v15_adds_no_method_and_keeps_every_v14_payload(self) -> None:
        v14 = _document("rpc.v14.json")
        # The v15 file as shipped: it added no method and moved no payload.
        v15 = _document("rpc.v15.json")
        self.assertEqual(
            list(v15["$defs"]["method"]["enum"]), list(v14["$defs"]["method"]["enum"])
        )
        current = contracts.contract("cb.rpc")
        self.assertEqual(
            list(current["$defs"]["method"]["enum"])[: len(v15["$defs"]["method"]["enum"])],
            list(v15["$defs"]["method"]["enum"]),
            "a later amendment is append-only over v15",
        )

        def normalise(payload: dict) -> dict:
            payload = _normalise_refresh_refs(json.loads(json.dumps(payload)))

            # The wire-version echo is the one thing a bump is allowed to move, so neutralise it
            # rather than pinning this check to whichever version is current.
            def walk(node: object) -> None:
                if isinstance(node, dict):
                    echo = node.get("contract_version")
                    if isinstance(echo, dict) and "const" in echo:
                        echo["const"] = 0
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)

            walk(payload)
            return payload

        for method in v14["$defs"]["method"]["enum"]:
            with self.subTest(method=method):
                self.assertEqual(
                    normalise(v15["$defs"]["methods"]["properties"][method]),
                    normalise(v14["$defs"]["methods"]["properties"][method]),
                    "v15 moved a v14 payload",
                )
                self.assertEqual(
                    normalise(_without_v17_source_fields(
                        current["$defs"]["methods"]["properties"][method], method)),
                    normalise(v15["$defs"]["methods"]["properties"][method]),
                    "a later amendment retyped a v15 payload",
                )

    def test_the_reference_refresh_points_every_job_item_at_cb_jobs_v5(self) -> None:
        schema = contracts.method_schema("jobs.list")["response"]["properties"]["jobs"]["items"]
        self.assertEqual(schema["$ref"], "https://contracts.coursebook.hermes/jobs/v5#/job")

    def test_cb_jobs_v5_is_v4_plus_the_activity_object(self) -> None:
        v4 = _document("jobs.v4.json")
        current = contracts.contract("cb.jobs")
        self.assertEqual(current["x-contract-version"], 5)
        self.assertEqual(current["$id"], "https://contracts.coursebook.hermes/jobs/v5")
        self.assertEqual(current["x-supersedes"], "https://contracts.coursebook.hermes/jobs/v4")
        self.assertEqual(set(current["states"]), set(v4["states"]))
        self.assertEqual(current["transitions"], v4["transitions"])
        self.assertEqual(set(current["$defs"]), set(v4["$defs"]))
        self.assertEqual(
            set(current["job"]["properties"]) - set(v4["job"]["properties"]), {"activity"}
        )
        for name, definition in v4["job"]["properties"].items():
            self.assertEqual(current["job"]["properties"][name], definition, f"job.{name} changed")
        activity = current["job"]["properties"]["activity"]
        self.assertFalse(activity["additionalProperties"])
        self.assertIn("usage", activity["properties"])
        self.assertNotIn("percent", activity["properties"])
        self.assertEqual(set(activity["required"]), set(activity["properties"]))

    def test_the_v14_snapshot_stays_byte_identical(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v14.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v14.json"])

    def test_docs_publish_the_v15_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in ("v15 delta (H-139)", "rpc.v15.json", "jobs.v5.json", "job.activity", "H-117"):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V16AmendmentTest(unittest.TestCase):
    """H-120 (`t_5eadfbca`): v16 appends the four conversation-practice commands, cb.db v11 stores
    the session and its turns.

    v16 is a strict superset of v15. It was authored as a v15 on `wt/h120-practice`, but v15 was
    already frozen by H-139 before this branch reached master, so the amendment takes the next
    free number rather than editing a frozen document: v15 stays byte-identical on disk and
    ``x-supersedes`` names it. Nothing on the wire is retyped — the four methods are appended, one
    optional property is added to ``check_stimulus``, and the version echo moves to 16.
    """

    NEW_METHODS = ("practice.start", "practice.state", "practice.end", "practice.cancel")

    def normalise(self, payload: dict) -> dict:
        payload = _normalise_refresh_refs(json.loads(json.dumps(payload)))

        def walk(node: object) -> None:
            if isinstance(node, dict):
                echo = node.get("contract_version")
                if isinstance(echo, dict) and "const" in echo:
                    echo["const"] = 0
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(payload)
        return payload

    def test_v16_is_v15_plus_four_appended_methods(self) -> None:
        v15 = _document("rpc.v15.json")
        v15_methods = list(v15["$defs"]["method"]["enum"])
        current = list(_document("rpc.v16.json")["$defs"]["method"]["enum"])
        self.assertEqual(len(v15_methods), 64)
        self.assertEqual(len(current), 68)
        # Append-only: a client diffing the enum sees four additions and no churn.
        self.assertEqual(current[: len(v15_methods)], v15_methods, "append-only enum")
        self.assertEqual(current[len(v15_methods):], list(self.NEW_METHODS))

    def test_every_v15_method_survives_with_the_same_shape(self) -> None:
        v15 = _document("rpc.v15.json")
        current = _document("rpc.v16.json")
        before = v15["$defs"]["methods"]["properties"]
        after = current["$defs"]["methods"]["properties"]
        self.assertEqual(set(after) - set(before), set(self.NEW_METHODS))
        self.assertEqual(set(before) - set(after), set(), "v16 removed a method")
        for method, schema in before.items():
            with self.subTest(method=method):
                self.assertEqual(
                    self.normalise(_without_v17_source_fields(after[method], method)),
                    self.normalise(schema),
                )

    def test_no_v15_definition_is_dropped_or_retyped(self) -> None:
        v15 = _document("rpc.v15.json")
        current = _document("rpc.v16.json")
        self.assertEqual(set(current["$defs"]), set(v15["$defs"]), "$defs set changed")
        # Every shared definition is v15's, except where the amendment says it moved: the echo in
        # the three envelopes and health.get, the method enum, the per-method payload map and the
        # one added `practice` property on check_stimulus.
        expected = {
            "envelope_request",
            "envelope_response_ok",
            "envelope_response_error",
            "method",
            "methods",
            "check_stimulus",
        }
        changed = {
            name for name in v15["$defs"]
            if current["$defs"][name] != v15["$defs"][name]
        }
        self.assertEqual(changed, expected)

    def test_check_stimulus_gains_only_the_practice_declaration(self) -> None:
        v15 = _document("rpc.v15.json")
        before = v15["$defs"]["check_stimulus"]
        after = contracts.contract("cb.rpc")["$defs"]["check_stimulus"]
        self.assertEqual(set(after), set(before), "check_stimulus gained or lost a keyword")
        self.assertEqual(
            set(after["properties"]) - set(before["properties"]), {"practice"},
            "check_stimulus gained more than the practice declaration",
        )
        self.assertEqual(set(before["properties"]) - set(after["properties"]), set())
        for name, subschema in before["properties"].items():
            self.assertEqual(after["properties"][name], subschema, f"check_stimulus.{name} moved")

    def test_the_wire_echo_moved_to_sixteen_everywhere(self) -> None:
        # The v16 file as shipped: every echo in it says 16 and it names v15 as its predecessor.
        v16 = _document("rpc.v16.json")
        echoes = _wire_echoes(v16)
        self.assertEqual(len(echoes), 4, echoes)
        for path, value in echoes:
            self.assertEqual(value, 16, path)
        self.assertEqual(v16["x-contract-version"], 16)
        self.assertEqual(v16["$id"], "https://contracts.coursebook.hermes/rpc/v16")
        self.assertEqual(
            v16["x-supersedes"], "https://contracts.coursebook.hermes/rpc/v15"
        )
        # A later amendment moves the live echo, never this frozen file.
        current = contracts.contract("cb.rpc")
        for path, value in _wire_echoes(current):
            self.assertEqual(value, contracts.WIRE_CONTRACT_VERSION, path)

    def test_the_v15_snapshot_is_pinned_history(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v15.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v15.json"])
        self.assertNotIn("rpc.v15.json", contracts.CONTRACT_FILES.values())

    def test_the_four_methods_publish_closed_bounded_schemas(self) -> None:
        expected_request = {
            "practice.start": {"enrollment_id", "objective_id"},
            "practice.state": {"enrollment_id", "objective_id"},
            "practice.end": {"enrollment_id", "check_id", "check_version", "attempt_nonce"},
            "practice.cancel": {"enrollment_id", "check_id"},
        }
        for method in self.NEW_METHODS:
            with self.subTest(method=method):
                schema = contracts.method_schema(method)
                for side in ("request", "response"):
                    self.assertEqual(schema[side]["type"], "object", side)
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    self.assertEqual(_schema_problems(schema[side]), [], f"{method}.{side}")
                self.assertEqual(
                    set(schema["request"]["required"]), expected_request[method]
                )
                self.assertEqual(
                    set(schema["request"]["properties"]), expected_request[method],
                    "a practice request accepts a field nobody reads",
                )

    def test_the_practice_commands_are_revision_fenced_in_the_envelope(self) -> None:
        """The schema, not the handler, refuses a fenceless command (``envelope_request``)."""
        doc = contracts.contract("cb.rpc")
        fenced: dict[str, set[str]] = {}
        for clause in doc["$defs"]["envelope_request"].get("allOf", []):
            names = clause.get("if", {}).get("properties", {}).get("method", {}).get("enum") or []
            for name in names:
                fenced.setdefault(name, set()).update(clause.get("then", {}).get("required", []))
        for method in ("practice.start", "practice.end", "practice.cancel"):
            self.assertIn("expected_revision", fenced.get(method, set()), method)
        # practice.state is a read: a read is never fenced (and needs no idempotency key).
        self.assertNotIn("practice.state", fenced)

        payloads = {
            "practice.start": {"enrollment_id": "enr_12345678", "objective_id": "obj_12345678"},
            "practice.end": {
                "enrollment_id": "enr_12345678",
                "check_id": "chk_12345678",
                "check_version": 1,
                "attempt_nonce": "nonce-practice-1",
            },
            "practice.cancel": {"enrollment_id": "enr_12345678", "check_id": "chk_12345678"},
        }
        for method, payload in payloads.items():
            with self.subTest(method=method):
                with self.assertRaises(contracts.ContractError):
                    contracts.validate("cb.rpc", _envelope(method, payload))
                contracts.validate(
                    "cb.rpc", _envelope(method, payload, expected_revision=1)
                )

    def test_the_practice_methods_add_no_error_code_and_no_job_kind(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        # `attempt.submit` may not grade a practice: one chat line is not a verdict.
        self.assertIn("attempt.submit", contracts.method_names())

    def test_the_practice_transcript_never_reaches_a_pack_or_course_export(self) -> None:
        for method in ("pack.export", "course.export"):
            with self.subTest(method=method):
                schema = contracts.method_schema(method)["response"]
                self.assertNotIn("practice", json.dumps(schema))

    def test_cb_db_v11_is_v10_plus_two_practice_tables(self) -> None:
        v10 = _document("db.v10.json")
        # The v11 file as shipped, not the live inventory: cb.db has since moved to v12 (H-194).
        current = _document("db.v11.json")
        self.assertEqual(v10["schema_version"], 10)
        self.assertEqual(current["schema_version"], 11)
        self.assertEqual(current["x-contract-version"], 11)
        self.assertEqual(current["$id"], "https://contracts.coursebook.hermes/db/v11")
        self.assertEqual(current["x-supersedes"], "https://contracts.coursebook.hermes/db/v10")
        self.assertEqual(
            set(current["tables"]) - set(v10["tables"]),
            {"practice_sessions", "practice_turns"},
        )
        self.assertEqual(set(v10["tables"]) - set(current["tables"]), set(), "v11 dropped a table")
        for table, spec in v10["tables"].items():
            self.assertEqual(
                current["tables"][table]["columns"], spec["columns"], f"{table} columns changed"
            )
            self.assertEqual(
                current["tables"][table].get("indexes"), spec.get("indexes"),
                f"{table} indexes changed",
            )
        self.assertEqual(
            current["migration_plan"][: len(v10["migration_plan"])], v10["migration_plan"]
        )

    def test_the_practice_tables_are_learner_owned_and_append_only(self) -> None:
        tables = contracts.contract("cb.db")["tables"]
        sessions = tables["practice_sessions"]
        self.assertEqual(
            sessions["columns"]["state"]["enum"],
            ["active", "graded", "cancelled", "abandoned"],
        )
        self.assertTrue(sessions["columns"]["attempt_id"]["nullable"])
        self.assertEqual(sessions["columns"]["attempt_id"]["ref"], "attempts.id")
        turns = tables["practice_turns"]
        self.assertEqual(turns["columns"]["speaker"]["enum"], ["learner", "tutor"])
        self.assertIn(["session_id", "ordinal"], turns["indexes"])
        self.assertIn(["session_id", "nonce"], turns["indexes"])

    def test_the_v11_migration_is_forward_only_and_rewrites_no_row(self) -> None:
        plan = contracts.contract("cb.db")["migration_plan"]
        entry = next(item for item in plan if item["version"] == 11)
        self.assertEqual(entry["from"], 10)
        self.assertEqual(entry["migration"], "0011_conversation_practice.sql")
        self.assertTrue(any("Additive only" in line for line in entry["impact"]))
        self.assertTrue(any("No backfill" in line for line in entry["impact"]))
        sql = (
            contracts.CONTRACT_DIR.parent / "coursebook" / "migrations" / entry["migration"]
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE practice_sessions", sql)
        self.assertIn("CREATE TABLE practice_turns", sql)
        statements = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        for forbidden in ("UPDATE ", "DELETE ", "DROP ", "ALTER ", "INSERT "):
            self.assertNotIn(forbidden, statements, forbidden)

    def test_docs_publish_the_v16_and_cb_db_v11_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v16 delta (H-120)",
            "rpc.v16.json",
            "db.v11.json",
            "0011_conversation_practice.sql",
            "practice_sessions",
            "practice.start",
            "practice_requires_practice_end",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")

    def test_docs_publish_the_conversation_grading_lane(self) -> None:
        text = (
            contracts.CONTRACT_DIR.parent / "docs" / "GRADING-LANES.md"
        ).read_text(encoding="utf-8")
        for needle in ("`conversation`", "configure_aux_grader", "provider-free"):
            self.assertIn(needle, text, f"GRADING-LANES.md is missing {needle!r}")


class V17AmendmentTest(unittest.TestCase):
    """H-106 (`t_96e05b28`): v17 adds six optional source-provenance fields to two read payloads.

    H-106 was authored against v15, which H-139 had already frozen, and `parent.blueprint.read` /
    `lesson.page` payloads had not moved since v6. The amendment therefore takes the next free
    number: v16 stays byte-identical on disk, `x-supersedes` names it, and no method name, required
    key, `additionalProperties`, error code, job kind, database table or vocabulary value moves.
    """

    SOURCE_FIELDS = V17_SOURCE_PROVENANCE_FIELDS
    METHODS = V17_ADDED_SOURCE_ITEMS

    def _source_items(self, method: str) -> dict:
        schema = contracts.method_schema(method)
        return schema["response"]["properties"]["sources"]["items"]

    def test_v17_is_v16_with_no_method_added(self) -> None:
        v16 = _document("rpc.v16.json")
        v16_methods = list(v16["$defs"]["method"]["enum"])
        v17 = _document("rpc.v17.json")
        current = list(v17["$defs"]["method"]["enum"])
        self.assertEqual(len(v16_methods), 68)
        self.assertEqual(current, v16_methods, "v17 appended or reordered a method")
        self.assertEqual(
            list(v17["$defs"]["method"]["enum"]), v16_methods
        )

    def test_every_v16_payload_is_carried_over_modulo_nothing_but_the_echo(self) -> None:
        v16 = _document("rpc.v16.json")
        current = _document("rpc.v17.json")
        before = v16["$defs"]["methods"]["properties"]
        after = current["$defs"]["methods"]["properties"]
        self.assertEqual(set(after), set(before), "v17 added or removed a method payload")
        for method, schema in before.items():
            with self.subTest(method=method):
                carried = _without_v17_source_fields(after[method], method)

                def neutralise(node: object) -> None:
                    if isinstance(node, dict):
                        echo = node.get("contract_version")
                        if isinstance(echo, dict) and "const" in echo:
                            echo["const"] = 0
                        for value in node.values():
                            neutralise(value)
                    elif isinstance(node, list):
                        for value in node:
                            neutralise(value)

                carried = json.loads(json.dumps(carried))
                original = json.loads(json.dumps(schema))
                neutralise(carried)
                neutralise(original)
                self.assertEqual(carried, original, "v17 retyped a v16 payload")

    def test_no_other_definition_moved(self) -> None:
        v16 = _document("rpc.v16.json")
        current = _document("rpc.v17.json")
        # The echo in the three envelopes and health.get (inside the per-method payload map) is the
        # only shared definition a bump may touch; the method enum itself does not move.
        expected = {
            "envelope_request",
            "envelope_response_ok",
            "envelope_response_error",
            "methods",
        }
        changed = {
            name for name in v16["$defs"] if current["$defs"][name] != v16["$defs"][name]
        }
        self.assertEqual(changed, expected)

    def test_the_six_fields_are_optional_and_option_typed_on_both_source_schemas(self) -> None:
        v16 = _document("rpc.v16.json")
        for method in self.METHODS:
            with self.subTest(method=method):
                before = v16["$defs"]["methods"]["properties"][method]["response"] \
                    ["properties"]["sources"]["items"]
                after = self._source_items(method)
                self.assertIs(after["additionalProperties"], False)
                self.assertEqual(
                    set(after["properties"]) - set(before["properties"]),
                    set(self.SOURCE_FIELDS),
                )
                self.assertEqual(set(before["properties"]) - set(after["properties"]), set())
                # Optional: no required key is added, and `excerpt_state` is not required either.
                self.assertEqual(after["required"], before["required"])
                for name in self.SOURCE_FIELDS:
                    self.assertNotIn(name, after["required"])
                for name, subschema in before["properties"].items():
                    self.assertEqual(after["properties"][name], subschema, f"{name} moved")

    def test_the_field_bounds_and_enums_are_h106s(self) -> None:
        excerpt, state, digest, modality, licence, support = self.SOURCE_FIELDS
        expected = {
            excerpt: {
                "oneOf": [{"type": "string", "maxLength": 20000}, {"type": "null"}]
            },
            state: {
                "type": "string",
                "enum": ["recorded", "missing", "unreadable"],
            },
            digest: {
                "oneOf": [
                    {"$ref": "https://contracts.coursebook.hermes/vocabulary/v1#/$defs/sha256_hash"},
                    {"type": "null"},
                ]
            },
            modality: {"type": ["string", "null"], "maxLength": 60},
            licence: {"type": ["string", "null"], "maxLength": 200},
            support: {
                "oneOf": [
                    {
                        "type": "string",
                        "enum": ["supported", "partial", "unverified", "contradictory"],
                    },
                    {"type": "null"},
                ]
            },
        }
        for method in self.METHODS:
            properties = self._source_items(method)["properties"]
            for name, subschema in expected.items():
                with self.subTest(method=method, field=name):
                    self.assertEqual(properties[name], subschema)

    def test_the_typed_absence_never_fabricates_an_excerpt(self) -> None:
        # `excerpt_state` is the only statement about a missing excerpt: `excerpt` may be null
        # while the state says why, and there is no default that invents an empty string.
        for method in self.METHODS:
            properties = self._source_items(method)["properties"]
            with self.subTest(method=method):
                self.assertNotIn("default", properties["excerpt"])
                self.assertNotIn("minLength", properties["excerpt"]["oneOf"][0])
                self.assertEqual(
                    set(properties["excerpt_state"]["enum"]),
                    {"recorded", "missing", "unreadable"},
                )

    def test_the_wire_echo_moved_to_the_current_version(self) -> None:
        current = contracts.contract("cb.rpc")
        echoes = _wire_echoes(current)
        self.assertEqual(len(echoes), 4, echoes)
        for path, value in echoes:
            self.assertEqual(value, 26, path)
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 26)
        self.assertEqual(contracts.CONTRACT_FILES["cb.rpc"], "rpc.v26.json")
        self.assertEqual(current["x-contract-version"], 26)
        self.assertEqual(current["$id"], "https://contracts.coursebook.hermes/rpc/v26")
        self.assertEqual(current["title"], "Coursebook backend RPC v26")
        self.assertEqual(
            current["x-supersedes"], "https://contracts.coursebook.hermes/rpc/v25"
        )

    def test_v15_and_v16_snapshots_stay_byte_identical_history(self) -> None:
        for filename in ("rpc.v15.json", "rpc.v16.json"):
            with self.subTest(filename=filename):
                digest = hashlib.sha256(
                    (contracts.CONTRACT_DIR / filename).read_bytes()
                ).hexdigest()
                self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256[filename])
                self.assertNotIn(filename, contracts.CONTRACT_FILES.values())

    def test_no_error_code_job_table_or_vocabulary_moved(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
        self.assertEqual(contracts.contract_version("cb.db"), 14)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)

    def test_docs_publish_the_v17_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v17 delta (H-106)",
            "rpc.v17.json",
            "excerpt_state",
            "typed absence",
            "never a fabricated",
            "support_assessment",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V20AmendmentTest(unittest.TestCase):
    """H-194b and H-182/D3: v20 is v19 plus two additive response amendments.

    H-194b appends ``sections[]`` to ``parent.blueprint.read`` — one ``blueprint_section_identity``
    per composed section, whose ``page_hash`` is the digest ``lesson.revise`` compares against.
    H-182/D3 appends one *optional* ``validation`` object to ``parent.blueprint.read.plan`` and to
    ``course.outline``'s ``outline_plan``, the durable approval provenance computed by the same gate
    ``plan.approve`` fences on. Nothing else moves: no method, request shape, error code, job kind
    or vocabulary value.
    """

    SECTION_FIELDS = (
        "section_id",
        "objective_id",
        "ordinal",
        "title",
        "lesson_state",
        "lesson_version",
        "page_hash",
    )

    def test_v20_is_v19_plus_the_additive_response_amendments(self) -> None:
        v19 = _document("rpc.v19.json")
        current = _document("rpc.v20.json")

        def normalise_echoes(node: object) -> None:
            """Blank the wire-version echo so the structural diff is not the version bump."""
            if isinstance(node, dict):
                echo = node.get("contract_version")
                if isinstance(echo, dict) and "const" in echo:
                    echo["const"] = 0
                for value in node.values():
                    normalise_echoes(value)
            elif isinstance(node, list):
                for value in node:
                    normalise_echoes(value)

        normalise_echoes(v19)
        normalise_echoes(current)
        self.assertEqual(
            list(current["$defs"]["method"]["enum"]),
            list(v19["$defs"]["method"]["enum"]),
            "no method may be added, removed or reordered",
        )
        before = v19["$defs"]["methods"]["properties"]
        after = current["$defs"]["methods"]["properties"]
        self.assertEqual(set(after), set(before))
        for method in before:
            with self.subTest(method=method):
                self.assertEqual(after[method]["request"], before[method]["request"])
                if method == "parent.blueprint.read":
                    continue
                self.assertEqual(after[method]["response"], before[method]["response"])
        # The one changed response: the new array, appended to both `properties` and `required`.
        v19_response = before["parent.blueprint.read"]["response"]
        v20_response = after["parent.blueprint.read"]["response"]
        self.assertFalse(v20_response["additionalProperties"])
        self.assertEqual(
            list(v20_response["required"]),
            list(v19_response["required"]) + ["sections"],
            "the required list only grows, at the end; `validation` stays optional",
        )
        self.assertEqual(
            set(v20_response["properties"]),
            set(v19_response["properties"]) | {"sections"},
        )
        for name, schema in v19_response["properties"].items():
            if name == "plan":
                continue
            self.assertEqual(v20_response["properties"][name], schema, name)
        sections = v20_response["properties"]["sections"]
        self.assertEqual(sections["type"], "array")
        self.assertEqual(sections["maxItems"], 100)
        self.assertEqual(sections["items"], {"$ref": "#/$defs/blueprint_section_identity"})

        # The nested plan object: v19's keys verbatim, plus the optional `validation` projection.
        v19_plan = v19_response["properties"]["plan"]["oneOf"][0]
        v20_plan = v20_response["properties"]["plan"]["oneOf"][0]
        self.assertEqual(
            set(v20_plan["properties"]), set(v19_plan["properties"]) | {"validation"}
        )
        for name, schema in v19_plan["properties"].items():
            self.assertEqual(v20_plan["properties"][name], schema, name)
        self.assertEqual(list(v20_plan["required"]), list(v19_plan["required"]))
        self.assertEqual(
            v20_plan["properties"]["validation"], {"$ref": "#/$defs/plan_validation"}
        )

        # `course.outline` moves only through `$defs.outline_plan`, additively the same way.
        v19_outline = v19["$defs"]["outline_plan"]
        v20_outline = current["$defs"]["outline_plan"]
        self.assertEqual(
            set(v20_outline["properties"]), set(v19_outline["properties"]) | {"validation"}
        )
        self.assertEqual(list(v20_outline["required"]), list(v19_outline["required"]))
        self.assertEqual(
            v20_outline["properties"]["validation"], {"$ref": "#/$defs/plan_validation"}
        )

    def test_the_plan_validation_projection_is_closed_and_names_the_gate(self) -> None:
        schema = contracts.contract("cb.rpc")["$defs"]["plan_validation"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["properties"]),
            {
                "approvable",
                "source",
                "verdict",
                "outcome",
                "independence",
                "facts_unverified",
                "reasons",
                "reason",
                "detail",
                "manual_authoring",
            },
        )
        self.assertEqual(len(schema["required"]), len(schema["properties"]))
        self.assertEqual(schema["properties"]["approvable"], {"type": "boolean"})

    def test_the_section_identity_is_closed_and_names_the_fence_digest(self) -> None:
        identity = contracts.contract("cb.rpc")["$defs"]["blueprint_section_identity"]
        self.assertFalse(identity["additionalProperties"])
        self.assertEqual(set(identity["properties"]), set(self.SECTION_FIELDS))
        self.assertEqual(list(identity["required"]), list(self.SECTION_FIELDS))
        # `page_hash` is the same nullable sha256 the fine-tune fence compares against.
        page_hash = identity["properties"]["page_hash"]
        self.assertEqual(len(page_hash["oneOf"]), 2)
        self.assertEqual(page_hash["oneOf"][1], {"type": "null"})
        self.assertTrue(page_hash["oneOf"][0]["$ref"].endswith("/sha256_hash"))

    def test_a_row_without_the_digest_or_the_version_is_refused(self) -> None:
        good = {
            "section_id": "sec_12345678",
            "objective_id": "obj_12345678",
            "ordinal": 1,
            "title": "One",
            "lesson_state": "validated",
            "lesson_version": 1,
            "page_hash": "sha256:" + "a" * 64,
        }
        contracts.validate_definition("cb.rpc", "blueprint_section_identity", good)
        # An unauthored section is served as an authored-shape row with nulls, never a missing key.
        unauthored = dict(good, lesson_state=None, lesson_version=None, page_hash=None)
        contracts.validate_definition("cb.rpc", "blueprint_section_identity", unauthored)
        for field in ("section_id", "page_hash", "lesson_version"):
            with self.subTest(missing=field):
                broken = {key: value for key, value in good.items() if key != field}
                with self.assertRaises(contracts.ContractError):
                    contracts.validate_definition("cb.rpc", "blueprint_section_identity", broken)
        with self.assertRaises(contracts.ContractError):
            contracts.validate_definition(
                "cb.rpc", "blueprint_section_identity", dict(good, page_hash="not-a-digest")
            )

    def test_v19_snapshot_stays_byte_identical_history(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v19.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v19.json"])
        self.assertNotIn("rpc.v19.json", contracts.CONTRACT_FILES.values())

    def test_v20_moves_no_method_error_code_job_or_vocabulary(self) -> None:
        self.assertEqual(contracts.contract_version("cb.rpc"), 26)
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
        self.assertEqual(contracts.contract_version("cb.db"), 14)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v20_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v20 delta (H-194b)",
            "rpc.v20.json",
            "blueprint_section_identity",
            "unreachable from the desktop",
            "sections: []",
            "Why the digest cannot drift",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V22AmendmentTest(unittest.TestCase):
    """GM-011: v22 appends the lesson-bound tutor commands and nothing else.

    ``tutor.ask`` is a learner-facing mutation (revision + idempotency), but a turn is not an
    attempt, transition or evidence row. ``tutor.history`` is a read. The frozen response cannot
    express a verdict, score or mastery claim.
    """

    NEW_METHODS = ("tutor.ask", "tutor.history")

    def normalise(self, payload: dict) -> dict:
        payload = _normalise_refresh_refs(json.loads(json.dumps(payload)))

        def walk(node: object) -> None:
            if isinstance(node, dict):
                echo = node.get("contract_version")
                if isinstance(echo, dict) and "const" in echo:
                    echo["const"] = 0
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(payload)
        return payload

    def test_v22_is_v21_plus_two_appended_methods(self) -> None:
        v21 = _document("rpc.v21.json")
        v21_methods = list(v21["$defs"]["method"]["enum"])
        current_document = _document("rpc.v22.json")
        current = list(current_document["$defs"]["method"]["enum"])
        self.assertEqual(current[: len(v21_methods)], v21_methods, "append-only enum")
        self.assertEqual(current[len(v21_methods):], list(self.NEW_METHODS))

    def test_every_v21_method_survives_with_the_same_shape(self) -> None:
        v21 = _document("rpc.v21.json")
        current = _document("rpc.v22.json")
        before = v21["$defs"]["methods"]["properties"]
        after = current["$defs"]["methods"]["properties"]
        self.assertEqual(set(after) - set(before), set(self.NEW_METHODS))
        self.assertEqual(set(before) - set(after), set(), "v22 removed a method")
        for method, schema in before.items():
            with self.subTest(method=method):
                self.assertEqual(self.normalise(after[method]), self.normalise(schema))

    def test_the_tutor_response_cannot_express_a_verdict(self) -> None:
        import coursebook.gm_contract as gm_contract

        schema = contracts.method_schema("tutor.ask")
        self.assertEqual(set(schema["request"]["required"]),
                         {"course_id", "enrollment_id", "objective_id", "lesson_run_id",
                          "question", "mode"})
        self.assertEqual(set(schema["response"]["required"]),
                         {"turn", "thread_id", "citations", "assist", "state"})
        self.assertEqual(_schema_problems(schema["request"], "request"), [])
        self.assertEqual(_schema_problems(schema["response"], "response"), [])
        for forbidden in gm_contract.FORBIDDEN_METHOD_KEYS:
            self.assertNotIn(forbidden, schema["response"]["properties"], forbidden)
        # The frozen state set has no success/failure claim about learning.
        states = schema["response"]["properties"]["state"]["enum"]
        self.assertEqual(set(states), {"answered", "answer_withheld", "provider_failure"})
        history = contracts.method_schema("tutor.history")
        for forbidden in gm_contract.FORBIDDEN_METHOD_KEYS:
            self.assertNotIn(forbidden, history["response"]["properties"], forbidden)

    def test_v21_snapshot_is_pinned_history_and_the_wire_echo_moved(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v21.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v21.json"])
        self.assertNotIn("rpc.v21.json", contracts.CONTRACT_FILES.values())
        current = contracts.contract("cb.rpc")
        self.assertEqual(contracts.contract_version("cb.rpc"), 26)
        self.assertEqual(_wire_echoes(current)[0][1], 26)
        self.assertEqual(current["x-supersedes"],
                         "https://contracts.coursebook.hermes/rpc/v25")

    def test_docs_publish_the_v22_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v22 delta (GM-011)",
            "rpc.v22.json",
            "tutor.ask",
            "tutor.history",
            "answer_withheld",
            "provider_failure",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V23AmendmentTest(unittest.TestCase):
    """GM-005: cb.rpc v23 appends the six frozen take-home methods to GM-011's v22.

    v23 is v22 (itself v21 plus ``tutor.ask``/``tutor.history``) plus exactly the take-home
    family, appended. The pack is a rendered print artifact bound to the source lesson version
    and content hash; the learner page and the answer guide are separate page objects on the
    wire.
    """

    NEW_METHODS = (
        "takehome.sources",
        "takehome.preview",
        "takehome.create",
        "takehome.approve",
        "takehome.export",
        "takehome.read",
    )

    def test_v23_is_v22_plus_the_take_home_family(self) -> None:
        v22 = _document("rpc.v22.json")
        # v24 is the live wire; this class pins the frozen v23 document it supersedes, so the
        # GM-005 delta stays testable after two later additive amendments.
        v23 = _document("rpc.v23.json")
        old = list(v22["$defs"]["method"]["enum"])
        new = list(v23["$defs"]["method"]["enum"])
        self.assertEqual(new[: len(old)], old)
        self.assertEqual(tuple(new[len(old):]), self.NEW_METHODS)
        self.assertEqual(v23["x-supersedes"], v22["$id"])
        self.assertEqual(contracts.contract_version("cb.rpc"), 26)
        self.assertEqual(v23["x-contract-version"], 23)
        # v23 is now history: the selected wire document has moved on to v26.
        self.assertNotIn("rpc.v23.json", contracts.CONTRACT_FILES.values())

    def test_v22_snapshot_stays_byte_identical_history(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v22.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v22.json"])
        self.assertNotIn("rpc.v22.json", contracts.CONTRACT_FILES.values())
        self.assertEqual(contracts.version_files("cb.rpc"),
                         {22: "rpc.v22.json", 23: "rpc.v23.json", 24: "rpc.v24.json",
                          25: "rpc.v25.json", 26: "rpc.v26.json"})
        v22 = _document("rpc.v22.json")
        self.assertEqual(len(v22["$defs"]["method"]["enum"]), 77)
        self.assertEqual(v22["x-supersedes"], "https://contracts.coursebook.hermes/rpc/v21")

    def test_every_v22_method_survives_with_the_same_shape(self) -> None:
        v22 = _document("rpc.v22.json")
        v23 = _document("rpc.v23.json")
        before = v22["$defs"]["methods"]["properties"]
        after = v23["$defs"]["methods"]["properties"]
        self.assertEqual(set(after) - set(before), set(self.NEW_METHODS))
        self.assertEqual(set(before) - set(after), set(), "v23 removed a method")
        self.assertEqual(set(before), set(v22["$defs"]["method"]["enum"]))

    def test_every_take_home_method_stays_in_the_frozen_v23_schema(self) -> None:
        """A dropped take-home method must fail here, not surface as NOT_IMPLEMENTED."""
        selected = _document("rpc.v23.json")
        declared = set(selected["$defs"]["method"]["enum"])
        schemas = selected["$defs"]["methods"]["properties"]
        for method in self.NEW_METHODS:
            with self.subTest(method=method):
                self.assertIn(method, declared)
                self.assertIn(method, schemas)
                contracts.method_schema(method)

    def test_every_take_home_payload_is_closed_and_bounded(self) -> None:
        import coursebook.gm_contract as gm

        for method in self.NEW_METHODS:
            with self.subTest(method=method):
                self.assertIn(method, gm.GM_RPC_METHODS)
                schema = contracts.method_schema(method)
                for side in ("request", "response"):
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    self.assertEqual(_schema_problems(schema[side]), [], f"{method}.{side}")

    def test_take_home_response_carries_the_frozen_field_names(self) -> None:
        import coursebook.gm_contract as gm

        for method in self.NEW_METHODS:
            with self.subTest(method=method):
                schema = contracts.method_schema(method)["response"]
                required = set(schema["required"])
                expected = set(gm.GM_RPC_METHODS[method]["response"]) - {"expected_revision"}
                self.assertTrue(expected <= required, (method, required, expected))

    def test_v23_moves_no_error_code_job_table_or_vocabulary(self) -> None:
        self.assertEqual(contracts.contract_version("cb.rpc"), 26)
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
        self.assertEqual(contracts.contract_version("cb.db"), 14)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v23_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v23 delta (GM-005)",
            "rpc.v23.json",
            "takehome.sources",
            "takehome.export",
            "answer guide",
            "tutor.ask",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V24AmendmentTest(unittest.TestCase):
    """GM-007 + GM-018 + GM-004: cb.rpc v24 composes three additive amendments onto GM-005's v23.

    GM-007 appends the away-from-screen homework family: one target, one context, one observable
    criterion and 3-10 minutes, and completion is ``self_reported_done`` or
    ``parent_reported_done`` — never a grade, score, mastery claim or XP award. GM-018 appends
    ``takehome.html``, the stored pack as self-contained content; ``artifact.get`` remains the
    only download handle. GM-004 appends the four frozen ``world.*`` methods plus the documented
    ``course.mode.set``, and ``course.create`` gains one optional ``presentation_mode``
    creation-intent field.

    World plates are textless orientation art: the read never generates art and never writes the
    mode, a style choice and a final kit are two separate hash-fenced approvals, and no method
    carries an evidence, verdict or score field.
    """

    NEW_METHODS = (
        "homework.create",
        "homework.read",
        "homework.complete",
        "homework.skip",
    )
    HTML_METHOD = "takehome.html"
    WORLD_METHODS = (
        "world.read",
        "world.style.preview",
        "world.generate",
        "world.approve",
        "course.mode.set",
    )

    def test_v24_is_v23_plus_the_homework_family_html_and_world_family(self) -> None:
        v23 = _document("rpc.v23.json")
        # v25 is the live wire; this class pins the frozen v24 document it supersedes, so the
        # GM-004/GM-007/GM-018 delta stays testable after CP-005's additive amendment.
        v24 = _document("rpc.v24.json")
        old = list(v23["$defs"]["method"]["enum"])
        new = list(v24["$defs"]["method"]["enum"])
        self.assertEqual(new[: len(old)], old)
        self.assertEqual(
            tuple(new[len(old):]),
            self.NEW_METHODS + (self.HTML_METHOD,) + self.WORLD_METHODS,
        )
        self.assertEqual(v24["x-supersedes"], v23["$id"])
        self.assertEqual(contracts.contract_version("cb.rpc"), 26)
        self.assertEqual(v24["x-contract-version"], 24)
        self.assertEqual(len(new), 93)

    def test_v23_snapshot_stays_byte_identical_history(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v23.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v23.json"])
        self.assertNotIn("rpc.v23.json", contracts.CONTRACT_FILES.values())
        self.assertEqual(contracts.version_files("cb.rpc"),
                         {22: "rpc.v22.json", 23: "rpc.v23.json", 24: "rpc.v24.json",
                          25: "rpc.v25.json", 26: "rpc.v26.json"})
        v23 = _document("rpc.v23.json")
        self.assertEqual(len(v23["$defs"]["method"]["enum"]), 83)
        self.assertEqual(v23["x-supersedes"], "https://contracts.coursebook.hermes/rpc/v22")
        self.assertTrue(digest)

    def test_every_v23_method_survives_with_the_same_shape(self) -> None:
        v23 = _document("rpc.v23.json")
        v24 = _document("rpc.v24.json")
        before = v23["$defs"]["methods"]["properties"]
        after = v24["$defs"]["methods"]["properties"]
        self.assertEqual(
            set(after) - set(before),
            set(self.NEW_METHODS) | {self.HTML_METHOD} | set(self.WORLD_METHODS),
        )
        self.assertEqual(set(before) - set(after), set(), "v24 removed a method")
        self.assertEqual(set(before), set(v23["$defs"]["method"]["enum"]))

    def test_every_homework_payload_is_closed_and_bounded(self) -> None:
        import coursebook.gm_contract as gm

        for method in self.NEW_METHODS:
            with self.subTest(method=method):
                self.assertIn(method, gm.GM_RPC_METHODS)
                schema = contracts.method_schema(method)
                for side in ("request", "response"):
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    self.assertEqual(_schema_problems(schema[side]), [], f"{method}.{side}")

    def test_every_world_method_is_closed_bounded_and_in_the_manifest(self) -> None:
        import coursebook.gm_contract as gm

        for method in self.WORLD_METHODS:
            with self.subTest(method=method):
                self.assertIn(method, gm.GM_RPC_METHODS)
                schema = contracts.method_schema(method)
                for side in ("request", "response"):
                    self.assertIs(schema[side].get("additionalProperties"), False, side)
                    self.assertEqual(_schema_problems(schema[side]), [], f"{method}.{side}")

    def test_homework_response_carries_the_frozen_field_names(self) -> None:
        import coursebook.gm_contract as gm

        for method in self.NEW_METHODS:
            with self.subTest(method=method):
                schema = contracts.method_schema(method)["response"]
                required = set(schema["required"])
                expected = set(gm.GM_RPC_METHODS[method]["response"]) - {"expected_revision"}
                self.assertTrue(expected <= required, (method, required, expected))

    def test_world_response_carries_the_frozen_field_names(self) -> None:
        import coursebook.gm_contract as gm

        for method in self.WORLD_METHODS:
            with self.subTest(method=method):
                schema = contracts.method_schema(method)["response"]
                required = set(schema["required"])
                expected = set(gm.GM_RPC_METHODS[method]["response"]) - {"expected_revision"}
                self.assertTrue(expected <= required, (method, required, expected))

    def test_the_homework_task_cannot_express_a_grade(self) -> None:
        task = contracts.contract("cb.rpc")["$defs"]["homework_task"]
        properties = set(task["properties"])
        for banned in ("grade", "score", "mastery", "verdict", "xp", "points", "streak"):
            self.assertNotIn(banned, properties)
        completion = task["properties"]["completion"]
        self.assertEqual(set(completion["properties"]["basis"]["enum"]),
                         {None, "self_reported", "parent_reported"})

    def test_world_schemas_carry_no_evidence_or_rating_key(self) -> None:
        import coursebook.gm_contract as gm

        for method in self.WORLD_METHODS:
            schema = contracts.method_schema(method)
            blob = json.dumps(schema)
            for forbidden in gm.FORBIDDEN_METHOD_KEYS:
                self.assertNotIn(f'"{forbidden}"', blob, f"{method} carries {forbidden}")

    def test_course_create_accepts_one_optional_creation_intent(self) -> None:
        create = contracts.method_schema("course.create")["request"]
        self.assertIn("presentation_mode", create["properties"])
        intent = create["properties"]["presentation_mode"]
        self.assertEqual(set(intent["enum"]), {"game", "textbook", None})
        self.assertNotIn("presentation_mode", create["required"])
        # The creation intent is an intent, not a world: a stored NULL still reads as Textbook.
        mode_set = contracts.method_schema("course.mode.set")
        self.assertEqual(set(mode_set["response"]["properties"]["mode"]["enum"]),
                         {"game", "textbook"})

    def test_the_html_method_is_closed_and_bounded(self) -> None:
        schema = contracts.method_schema(self.HTML_METHOD)
        self.assertIs(schema["request"].get("additionalProperties"), False)
        self.assertEqual(set(schema["request"]["required"]), {"pack_id"})
        self.assertIs(schema["response"].get("additionalProperties"), False)
        self.assertEqual(
            set(schema["response"]["required"]),
            {"pack_id", "title", "language", "mime", "pages", "html", "document_hash"},
        )
        self.assertEqual(schema["response"]["properties"]["mime"]["const"], "text/html")
        self.assertEqual(schema["response"]["properties"]["html"]["maxLength"], 400000)
        self.assertEqual(_schema_problems(schema["request"], "request"), [])
        self.assertEqual(_schema_problems(schema["response"], "response"), [])

    def test_v24_moves_no_error_code_job_table_or_vocabulary(self) -> None:
        self.assertEqual(contracts.contract_version("cb.rpc"), 26)
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
        self.assertEqual(contracts.contract_version("cb.db"), 14)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v24_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v24 delta (GM-007)",
            "v24 delta (GM-018)",
            "v24 delta (GM-004)",
            "rpc.v24.json",
            "homework.create",
            "homework.complete",
            "self_reported_done",
            "parent_reported_done",
            "takehome.html",
            "self-contained",
            "artifact.get",
            "world.read",
            "world.approve",
            "course.mode.set",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V25AmendmentTest(unittest.TestCase):
    """CP-005: cb.rpc v25 is v24 plus the seven `library_item` shelf facts, and nothing else.

    The v3 shelf card may not compute or invent a number. v25 hands it section counts, a recorded
    check count, the new-course flag, the authored subject, the approved-or-pack cover and the last
    study time from the one `library.list` read. No method, request shape, error code, job kind or
    vocabulary value moves, and there is deliberately no rating, learner count or percentage.
    """

    NEW_FIELDS = (
        "sections_done",
        "sections_total",
        "checks_recorded",
        "is_new",
        "subject_label",
        "cover_artifact_id",
        "last_studied_at",
    )

    FORBIDDEN = ("rating", "stars", "review_count", "learner_count", "percentage", "xp", "proofs")

    def test_v25_is_v24_plus_the_shelf_facts(self) -> None:
        v24 = _document("rpc.v24.json")
        # The frozen v25 document: a later additive amendment (CP-052) moved the selected wire.
        v25 = _document("rpc.v25.json")
        self.assertEqual(v25["$defs"]["method"]["enum"], v24["$defs"]["method"]["enum"],
                         "CP-005 adds no method")
        before = v24["$defs"]["library_item"]
        after = v25["$defs"]["library_item"]
        self.assertEqual(set(after["properties"]) - set(before["properties"]), set(self.NEW_FIELDS))
        self.assertEqual(set(before["properties"]) - set(after["properties"]), set())
        self.assertEqual(set(after["required"]) - set(before["required"]), set(self.NEW_FIELDS))
        self.assertEqual(set(before["required"]) - set(after["required"]), set())
        self.assertEqual(v25["x-supersedes"], v24["$id"])
        self.assertEqual(contracts.contract_version("cb.rpc"), 26)

    def test_every_v24_method_survives_with_the_same_shape(self) -> None:
        v24 = _document("rpc.v24.json")
        # The frozen v25 document, not the live one: this class is CP-005's delta and must keep
        # testing it after a later additive amendment (CP-052) moved the selected wire.
        v25 = _document("rpc.v25.json")
        before = v24["$defs"]["methods"]["properties"]
        after = v25["$defs"]["methods"]["properties"]
        self.assertEqual(set(after), set(before), "v25 moved a method schema")
        differing = [
            method for method in before
            if method != "health.get"
            and json.dumps(before[method], sort_keys=True) != json.dumps(after[method], sort_keys=True)
        ]
        self.assertEqual(differing, [], "v25 changed a request/response shape")
        # health.get is the one intentional difference: its echoed wire version moves with the
        # contract, and nothing else about the read changes.
        self.assertEqual(
            after["health.get"]["response"]["properties"]["contract_version"]["const"], 25
        )
        before_health = dict(before["health.get"]["response"])
        after_health = dict(after["health.get"]["response"])
        before_health["properties"] = {
            **before_health["properties"], "contract_version": {"const": 25}
        }
        self.assertEqual(before_health, after_health)

    def test_v24_snapshot_stays_byte_identical_history(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v24.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v24.json"])
        self.assertNotIn("rpc.v24.json", contracts.CONTRACT_FILES.values())
        self.assertEqual(
            contracts.version_files("cb.rpc"),
            {22: "rpc.v22.json", 23: "rpc.v23.json", 24: "rpc.v24.json",
             25: "rpc.v25.json", 26: "rpc.v26.json"},
        )

    def test_the_shelf_item_is_closed_typed_and_carries_no_rating(self) -> None:
        item = contracts.contract("cb.rpc")["$defs"]["library_item"]
        self.assertEqual(_schema_problems(item, "library_item"), [])
        for forbidden in self.FORBIDDEN:
            self.assertNotIn(forbidden, item["properties"], forbidden)
        for name in ("sections_done", "sections_total", "checks_recorded"):
            self.assertEqual(item["properties"][name]["type"], "integer", name)
            self.assertEqual(item["properties"][name]["minimum"], 0, name)
        self.assertEqual(item["properties"]["is_new"]["type"], "boolean")
        self.assertEqual(item["properties"]["subject_label"]["maxLength"], 60)

    def test_v25_moves_no_error_code_job_table_or_vocabulary(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
        self.assertEqual(contracts.contract_version("cb.db"), 14)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v25_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v25 delta (CP-005)",
            "rpc.v25.json",
            "sections_done",
            "sections_total",
            "checks_recorded",
            "is_new",
            "subject_label",
            "cover_artifact_id",
            "last_studied_at",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


class V26AmendmentTest(unittest.TestCase):
    """CP-052: cb.rpc v26 is v25 plus an optional `world_brief.route_anchors`, and nothing else.

    The plate declares where each section sits on its own box as normalised 0–1 coordinates; the
    course home renders nodes there when the array is present and its vertical route when it is
    not. The amendment is additive: no method, request shape, required key or error code moves.
    """

    def test_v25_is_v26_with_no_method_added(self) -> None:
        v25 = _document("rpc.v25.json")
        current = contracts.contract("cb.rpc")
        self.assertEqual(current["$defs"]["method"]["enum"], v25["$defs"]["method"]["enum"])
        self.assertEqual(current["x-supersedes"], v25["$id"])

    def test_every_v25_method_survives_with_the_same_shape(self) -> None:
        v25 = _document("rpc.v25.json")
        current = contracts.contract("cb.rpc")
        before = v25["$defs"]["methods"]["properties"]
        after = current["$defs"]["methods"]["properties"]
        self.assertEqual(set(after), set(before), "v26 added or removed a method payload")
        for method, schema in before.items():
            with self.subTest(method=method):
                carried = json.loads(json.dumps(after[method]))
                if method == "health.get":
                    carried["response"]["properties"]["contract_version"]["const"] = 25
                self.assertEqual(carried, schema, f"{method} moved")

    def test_the_brief_gains_one_optional_anchor_array(self) -> None:
        v25 = _document("rpc.v25.json")
        after = contracts.contract("cb.rpc")["$defs"]["world_brief"]
        before = v25["$defs"]["world_brief"]
        self.assertEqual(set(after["properties"]) - set(before["properties"]), {"route_anchors"})
        self.assertEqual(set(before["properties"]) - set(after["properties"]), set())
        self.assertNotIn("route_anchors", after["required"], "route_anchors must stay optional")
        self.assertEqual(after["required"], before["required"])
        self.assertEqual(after["additionalProperties"], False)
        for name, subschema in before["properties"].items():
            self.assertEqual(after["properties"][name], subschema, f"{name} moved")

    def test_the_anchor_item_is_closed_and_normalised(self) -> None:
        anchor = contracts.contract("cb.rpc")["$defs"]["world_route_anchor"]
        self.assertEqual(_schema_problems(anchor, "world_route_anchor"), [])
        self.assertEqual(anchor["additionalProperties"], False)
        self.assertEqual(set(anchor["required"]), {"anchor_id", "section_id", "x", "y"})
        self.assertEqual(set(anchor["properties"]), {"anchor_id", "section_id", "x", "y"})
        for axis in ("x", "y"):
            spec = anchor["properties"][axis]
            self.assertEqual(spec["type"], "number", axis)
            self.assertEqual((spec["minimum"], spec["maximum"]), (0, 1), axis)

    def _brief(self, anchors: object) -> dict:
        return {
            "course_id": "crs_00000000000000000000000000000001",
            "title": "Fixture: anchors",
            "subject_domain": "cooking",
            "end_capability": "Braise short ribs",
            "audience": "adult learner",
            "level": "novice",
            "locale": "en-US",
            "tone": "practical, calm, competent",
            "safety_class": "none",
            "motifs": ["braising pot"],
            "forbidden": ["text"],
            "sections": [
                {"id": "sec_00000000000000000000000000000001", "title": "Section one"},
                {"id": "sec_00000000000000000000000000000002", "title": "Section two"},
                {"id": "sec_00000000000000000000000000000003", "title": "Section three"},
            ],
            "route_anchors": anchors,
        }

    def _anchors(self) -> list[dict]:
        return [
            {"anchor_id": "anc_00000000000000000000000000000001",
             "section_id": "sec_00000000000000000000000000000001", "x": 0.18, "y": 0.72},
            {"anchor_id": "anc_00000000000000000000000000000002",
             "section_id": "sec_00000000000000000000000000000002", "x": 0.51, "y": 0.44},
            {"anchor_id": "anc_00000000000000000000000000000003",
             "section_id": "sec_00000000000000000000000000000003", "x": 0.82, "y": 0.19},
        ]

    def test_a_brief_with_three_anchors_validates(self) -> None:
        contracts.validate_definition("cb.rpc", "world_brief", self._brief(self._anchors()))

    def test_a_brief_without_anchors_stays_valid(self) -> None:
        brief = self._brief(None)
        brief.pop("route_anchors")
        contracts.validate_definition("cb.rpc", "world_brief", brief)

    def test_the_schema_refuses_an_off_box_coordinate(self) -> None:
        anchors = self._anchors()
        anchors[1]["x"] = 1.4
        with self.assertRaises(contracts.ContractError) as raised:
            contracts.validate_definition("cb.rpc", "world_brief", self._brief(anchors))
        self.assertIn("route_anchors", raised.exception.path)

    def test_the_schema_refuses_an_anchor_without_a_section(self) -> None:
        anchors = self._anchors()
        anchors[2].pop("section_id")
        with self.assertRaises(contracts.ContractError) as raised:
            contracts.validate_definition("cb.rpc", "world_brief", self._brief(anchors))
        self.assertIn("route_anchors", raised.exception.path)

    def test_v25_snapshot_stays_byte_identical_history(self) -> None:
        digest = hashlib.sha256((contracts.CONTRACT_DIR / "rpc.v25.json").read_bytes()).hexdigest()
        self.assertEqual(f"sha256:{digest}", FROZEN_RPC_SHA256["rpc.v25.json"])
        self.assertNotIn("rpc.v25.json", contracts.CONTRACT_FILES.values())
        self.assertEqual(contracts.contract_version("cb.rpc"), 26)

    def test_v26_moves_no_error_code_job_table_or_vocabulary(self) -> None:
        self.assertEqual(contracts.contract_version("cb.errors"), 4)
        self.assertEqual(contracts.contract_version("cb.jobs"), 5)
        self.assertEqual(contracts.contract_version("cb.db"), 14)
        self.assertEqual(contracts.contract_version("cb.vocabulary"), 1)
        self.assertEqual(contracts.audit_contracts(), [])

    def test_docs_publish_the_v26_delta(self) -> None:
        text = (contracts.CONTRACT_DIR.parent / "docs" / "CONTRACTS.md").read_text(encoding="utf-8")
        for needle in (
            "v26 delta (CP-052)",
            "rpc.v26.json",
            "route_anchors",
            "world_route_anchor",
            "normalised 0–1",
            "02bd2b9304a55ebf8b79e581ef7740d1e265b8a136045bc51848ceb15889c130",
        ):
            self.assertIn(needle, text, f"CONTRACTS.md is missing {needle!r}")


if __name__ == "__main__":
    unittest.main()
