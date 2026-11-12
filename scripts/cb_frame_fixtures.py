#!/usr/bin/env python3
"""Real backend fixtures for the route destinations that `scripts/cb-frame.py --all` frames.

The frame harness itself has no backend and no window: it stages the built module with a stub SDK
and a stub transport. That is only honest if the payloads that stub replays were *recorded from the
real backend*. This module produces them:

* `coursebook.workshop.catalog_view()` — the same function `/workshop/catalog` answers with, run
  against a throwaway, migrated profile home; the installed variant is produced by the real
  `workshop.install()` (the atomic `pack.import` gate), not by editing JSON;
* `library.list`, `course.outline`, `lesson.page`, `world.read`, `takehome.sources`, `pack.list` and
  the rest of the course detail reads — real `coursebook.api.dispatch` envelopes over that profile;
* `parent.brief.create` / `parent.brief.get` / `parent.blueprint.read` / `parent.review.read` /
  `parent.reflection.list` — the real handlers over a parent course whose plan and generated
  content are seeded the way the repository's own `ParentSeedMixin` seeds them;
* `homework.create` / `homework.read` — the real handlers over a seeded, validated lesson.

Two frames are deliberately contract fixtures rather than live reads, and their manifests say so:
the syllabus parse/alignment documents come from the frozen `syllabus.parse.v1` fixture in
`tests/test_desktop_syllabus_ui.py` (the backend cannot produce a parsed syllabus without an LLM
call), and the Home settings sheet reads the host storage contract directly.

Nothing here writes to the operator's profile: `HERMES_HOME` is a temporary directory that is
removed before this function returns. The fixtures are JSON, so every frame can name its source.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

PACK_ID = "japanese-affection-context-l0"

#: The parent brief the Studio's own form submits. Same values as tests/test_parent_studio.py.
PARENT_BRIEF = {
    "title": "Japanese café basics",
    "goal": "Order coffee in Japanese politely",
    "starting_point": None,
    "age_band": "6-8",
    "reading_level": "early reader",
    "duration_minutes": 20,
    "setting": "home",
    "materials": ["menu card"],
    "exclusions": [],
    "supervision": "An adult is nearby.",
    "desired_pages": 4,
    "desired_visuals": "none",
    "narration": "script",
    "locale": "ja-JP",
    "egress_acknowledged": True,
    "redaction_requested": False,
}

#: The novice wizard's own seed: a real goal and one of the three contract scopes. A seed with both
#: answers opens on Review (H-170), which is the screen that states what the chosen size means.
CREATE_GOAL = "Order coffee in Japanese without pointing at the menu"
CREATE_SCOPES = ("single", "short", "full")
CREATE_DIALS = {"pace": "light", "depth": "working", "assessment": "self_check", "autonomy": "guided"}


def _envelope(method: str, payload: dict[str, Any], *, key: str | None = None,
              expected: int | None = None) -> dict[str, Any]:
    """One real command, through the same dispatcher the host calls."""
    from coursebook import api
    from tests.kernel_support import request

    body = request(method, payload, idempotency_key=key, expected_revision=expected)
    return api.dispatch(body)


def _ok(method: str, payload: dict[str, Any], *, key: str | None = None,
        expected: int | None = None) -> dict[str, Any]:
    envelope = _envelope(method, payload, key=key, expected=expected)
    if envelope.get("ok") is not True:
        raise RuntimeError(f"fixture read {method} refused: {envelope.get('error')}")
    return envelope


def _seed_parent_plan(course_id: str, enrollment_id: str) -> tuple[str, list[str]]:
    """Give the parent course an approved two-section plan and validated lesson pages.

    Mirrors `tests/test_parent_studio.py::ParentSeedMixin.seed_generated_content`. The rows are what
    a completed `plan` + `lessons` job writes; the reads below are the real handlers over them.
    """
    from coursebook import db, domain, generation
    from tests.kernel_support import criteria_with, numeric_spec
    from tests.test_parent_studio import page_document

    now = "2026-11-06T12:00:00Z"
    gen_hash = "sha256:" + "a" * 64
    plan_id = f"pln_{course_id}"
    with db.read() as connection:
        generation.ensure_schema(connection)
    with db.transaction() as connection:
        connection.execute(
            "INSERT INTO plans (id, course_id, version, state, plan_hash, schedule_json, created_at, approved_at)"
            " VALUES (?, ?, 1, 'draft', NULL, '{}', ?, NULL)",
            (plan_id, course_id, now),
        )
    objectives = []
    for ordinal in (1, 2):
        objectives.append(
            domain.record_objective(
                plan_id,
                title=("Greet the staff politely" if ordinal == 1 else "Order a coffee"),
                evidence_target="production",
                criteria=criteria_with(numeric_spec()),
            )
        )
    with db.transaction() as connection:
        connection.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint, plan_hash,"
            " document_json, research_json, generation_state, validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL, '{}', ?)",
            (f"gpd_{course_id}", plan_id, course_id, gen_hash, now),
        )
        for ordinal, objective_id in enumerate(objectives, start=1):
            section_id = f"sec_{ordinal}_{course_id}"
            lesson_id = f"lsn_{ordinal}_{course_id}"
            check_id = f"chk_{ordinal}_{course_id}"
            connection.execute(
                "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title, lesson_intent,"
                " objective_refs_json, context_needs_json, source_ids_json)"
                " VALUES (?, ?, ?, ?, ?, 'Practise with a parent.', ?, '[]', '[]')",
                (section_id, plan_id, ordinal, gen_hash, f"Section {ordinal}", f"[{ordinal}]"),
            )
            connection.execute(
                "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state, page_json,"
                " media_json, parent_notes_json, rejection_reasons_json, validation_id, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 1, 'validated', ?, '[]', ?, '[]', NULL, ?, ?)",
                (
                    lesson_id, plan_id, section_id, gen_hash,
                    json.dumps(page_document(f"Section {ordinal}")),
                    json.dumps({
                        "parent_notes": "Ask once more.",
                        "supervision_notes": ["An adult listens for the polite form"],
                    }),
                    now, now,
                ),
            )
            connection.execute(
                "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
                " rubric_json, reference_json, locale, audit_state, state, created_at)"
                " VALUES (?, ?, 1, 'production', ?, ?, ?, 'ja-JP', 'passed', 'open', ?)",
                (
                    check_id, objective_id,
                    json.dumps({"prompt": "Which greeting opens politely?", "format": "selection"}),
                    json.dumps({"criteria": [
                        {"criterion": "a", "description": "Greets politely"},
                        {"criterion": "b", "description": "Uses the polite register"},
                        {"criterion": "c", "description": "Speaks clearly"},
                    ]}),
                    json.dumps({
                        "reference_answer": "Politely greet the staff",
                        "accepted_answers": ["Politely greet the staff"],
                        "accepted_alternatives": [],
                    }),
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, ?)",
                (lesson_id, check_id, ordinal),
            )
    plan_hash = domain.plan_hash(plan_id)
    with db.transaction() as connection:
        connection.execute(
            "UPDATE plans SET state = 'approved', plan_hash = ?, approved_at = ? WHERE id = ?",
            (plan_hash, now, plan_id),
        )
    return plan_id, objectives


def _seed_validated_lesson() -> dict[str, str]:
    """A committed learner course with one validated lesson; same rows as tests/test_gm_homework.py."""
    from coursebook import db, domain, generation
    from tests.kernel_support import criteria_with, numeric_spec
    from tests.test_gm_homework import ANSWER_MARKER, GEN_HASH, NOW, RUBRIC_MARKER, japanese_page

    created = _ok("course.create", {
        "title": "Japanese at home",
        "recipe": "committed",
        "goal": "Use one Japanese greeting at a real meal.",
        "locale": "ja-JP",
    })["result"]
    course_id, plan_id = created["course_id"], created["plan_id"]
    objective_id = domain.record_objective(
        plan_id,
        title="Say the before-meal greeting",
        evidence_target="production",
        criteria=criteria_with(numeric_spec()),
    )
    enrollment = _ok("enrollment.create", {"course_id": course_id})["result"]
    enrollment_id = enrollment["enrollment_id"]
    _ok(
        "plan.approve",
        {"enrollment_id": enrollment_id, "plan_id": plan_id, "plan_hash": domain.plan_hash(plan_id)},
        expected=0,
    )
    with db.read() as connection:
        generation.ensure_schema(connection)
    with db.transaction() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO gen_plan_documents (id, plan_id, course_id,"
            " request_fingerprint, plan_hash, document_json, research_json, generation_state,"
            " validation_id, result_json, created_at)"
            " VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL, '{}', ?)",
            (f"gpd_{plan_id}", plan_id, course_id, GEN_HASH, NOW),
        )
        section_id = f"sec_{plan_id}"
        lesson_id = f"lsn_{plan_id}"
        check_id = f"chk_{plan_id}"
        connection.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
            " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
            " VALUES (?, ?, 1, ?, ?, 'Say one greeting at the table.', '[1]', '[]', '[]')",
            (section_id, plan_id, GEN_HASH, "Mealtime greetings"),
        )
        connection.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
            " page_json, media_json, parent_notes_json, rejection_reasons_json,"
            " validation_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 1, 'validated', ?, '[]', '{}', '[]', NULL, ?, ?)",
            (lesson_id, plan_id, section_id, GEN_HASH,
             json.dumps(japanese_page("Mealtime greetings")), NOW, NOW),
        )
        connection.execute(
            "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
            " rubric_json, reference_json, locale, audit_state, state, created_at)"
            " VALUES (?, ?, 1, ?, ?, ?, ?, 'ja-JP', 'passed', 'open', ?)",
            (
                check_id, objective_id, "production",
                json.dumps({"prompt": "Say the greeting.", "format": "short_text"}),
                json.dumps({"criteria": [{"criterion": "a", "description": RUBRIC_MARKER}]}),
                json.dumps({"reference_answer": ANSWER_MARKER, "accepted_answers": []}),
                NOW,
            ),
        )
        connection.execute(
            "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, 1)",
            (lesson_id, check_id),
        )
    return {
        "course_id": course_id,
        "plan_id": plan_id,
        "objective_id": objective_id,
        "enrollment_id": enrollment_id,
        "lesson_version": f"{lesson_id}:v1",
    }


def build() -> dict[str, Any]:
    home = tempfile.mkdtemp(prefix="coursebook-cb-frame-fixtures-")
    previous = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = home
    try:
        from coursebook import api, db, domain, media, workshop  # noqa: F401 - domain registers handlers

        db.migrate()
        runtime = {
            "ok": True,
            "wire_version": api.RPC_CONTRACT_VERSION,
            "implemented_methods": list(api.implemented_methods()),
            "single_home_host": False,
        }
        health = {
            "ok": True,
            "result": {
                "db": {"ready": True},
                "plugin_version": "frame-fixture",
                "contract_version": api.RPC_CONTRACT_VERSION,
                "wire_version": api.RPC_CONTRACT_VERSION,
            },
        }
        library_empty = _ok("library.list", {"filter": "all", "limit": 50, "sort": "recent"})
        catalog_fresh = {"ok": True, **workshop.catalog_view()}
        install = {"ok": True, **workshop.install(PACK_ID)}
        catalog_installed = {"ok": True, **workshop.catalog_view()}
        library_full = _ok("library.list", {"filter": "all", "limit": 50, "sort": "recent"})
        packs = _ok("pack.list", {"filter": "all", "limit": 100})
        rows = [item for item in library_full["result"]["items"] if item.get("recipe") != "parent"]
        if not rows:
            raise RuntimeError("the installed pack produced no library row")
        row = rows[0]
        enrollment_id = row["enrollment_id"]
        course_id = row["course_id"]

        outline = _ok("course.outline", {"enrollment_id": enrollment_id})
        objectives = outline["result"].get("objectives") or []
        current = (row.get("evidence_summary") or {}).get("current_objective_id")
        objective_id = current or (objectives[0]["objective_id"] if objectives else None)
        detail_rpc: dict[str, Any] = {
            "library.list": library_full,
            "course.outline": outline,
            "review.queue": _ok("review.queue", {"enrollment_id": enrollment_id, "cap": 25, "include_upcoming": True}),
            "notebook.list": _ok("notebook.list", {"enrollment_id": enrollment_id}),
            "quiz.history": _ok("quiz.history", {"enrollment_id": enrollment_id}),
            "evidence.inspect": _ok("evidence.inspect", {"enrollment_id": enrollment_id, "limit": 100}),
            "jobs.list": _ok("jobs.list", {"enrollment_id": enrollment_id, "limit": 20}),
            "world.read": _envelope("world.read", {"course_id": course_id}),
            "engagement.read": _envelope("engagement.read", {"course_id": course_id, "enrollment_id": enrollment_id}),
            "takehome.sources": _envelope("takehome.sources", {"course_id": course_id}),
        }
        if objective_id:
            detail_rpc["lesson.page"] = _envelope(
                "lesson.page", {"enrollment_id": enrollment_id, "objective_id": objective_id}
            )

        # ── the pack's own cover media, served the way the artifact route serves it ────────────
        rest: dict[str, dict[str, Any]] = {"/runtime": runtime, "/health": health}
        with db.read() as connection:
            for entry in catalog_installed["items"]:
                artifact_id = (entry.get("cover") or {}).get("artifact_id")
                if not artifact_id:
                    continue
                found = connection.execute(
                    "SELECT id FROM artifacts WHERE id = ?", (artifact_id,)
                ).fetchone()
                if found is not None:
                    rest[f"/media/{artifact_id}"] = media.preview_artifact(artifact_id)
        installed_item = next(
            (item for item in catalog_installed["items"] if item["pack_id"] == PACK_ID),
            catalog_installed["items"][0],
        )

        # ── Parent Studio: a real brief, an approved plan, and the reads the detail issues ────
        parent = _ok("parent.brief.create", {"brief": PARENT_BRIEF}, key="cb-frame-parent-brief-1")["result"]
        parent_plan, parent_objectives = _seed_parent_plan(parent["course_id"], parent["enrollment_id"])
        parent_list = _ok("library.list", {"filter": "all", "recipe": "parent", "limit": 50, "sort": "recent"})
        parent_course_row = next(
            item for item in parent_list["result"]["items"] if item["course_id"] == parent["course_id"]
        )
        parent_detail_rpc = {
            "library.list": parent_list,
            "parent.brief.get": _ok("parent.brief.get", {"course_id": parent["course_id"]}),
            "course.outline": _ok("course.outline", {"enrollment_id": parent["enrollment_id"]}),
            "parent.blueprint.read": _envelope("parent.blueprint.read", {"course_id": parent["course_id"]}),
            "parent.review.read": _envelope("parent.review.read", {"course_id": parent["course_id"]}),
            "parent.reflection.list": _envelope("parent.reflection.list", {"course_id": parent["course_id"]}),
            "jobs.get": _envelope("jobs.get", {"job_id": parent["job_id"]}),
        }

        # ── Homework: a real task over the seeded validated lesson ───────────────────────────
        seeded = _seed_validated_lesson()
        homework_made = _ok(
            "homework.create",
            {
                "course_id": seeded["course_id"],
                "enrollment_id": seeded["enrollment_id"],
                "objective_id": seeded["objective_id"],
                "audience": "parent",
                "source_lesson_version": seeded["lesson_version"],
                "context": "At your own table, just before you eat today.",
            },
            key=f"cb-frame-homework-{seeded['course_id']}",
            expected=0,
        )["result"]
        homework_read = _ok("homework.read", {"task_id": homework_made["task_id"]})
        homework_library = _ok("library.list", {"filter": "all", "limit": 50, "sort": "recent"})
        homework_sources = _ok("takehome.sources", {"course_id": seeded["course_id"]})
        homework_store = {
            "homework-index.v1": {
                "enrollments": {
                    seeded["enrollment_id"]: {
                        "course_id": seeded["course_id"],
                        "tasks": {
                            homework_made["task_id"]: {
                                "objective_id": seeded["objective_id"],
                                "course_id": seeded["course_id"],
                                "created_at": "2026-11-11T09:00:00Z",
                            }
                        },
                    }
                }
            }
        }

        from tests.test_desktop_syllabus_ui import FIXTURE_PARSE, _fixture_alignment

        syllabus_parse = FIXTURE_PARSE
        syllabus_alignment = _fixture_alignment()

        implemented = list(api.implemented_methods())
        sources = {
            "catalog_fresh": "coursebook.workshop.catalog_view() on a migrated temp HERMES_HOME (no install)",
            "catalog_installed": f"coursebook.workshop.catalog_view() after the real workshop.install({PACK_ID!r})",
            "library_empty": "coursebook.api.dispatch(library.list) on the migrated temp profile before any install",
            "library_full": "coursebook.api.dispatch(library.list) after the real pack import",
            "course_row": f"the real library row for the imported pack (course {course_id})",
            "course_detail": "coursebook.api.dispatch reads: course.outline, lesson.page, review.queue, notebook.list, quiz.history, evidence.inspect, jobs.list, world.read, engagement.read, library.list",
            "pack_list": "coursebook.api.dispatch(pack.list) over the installed catalogue",
            "parent": "real parent.brief.create, then an approved two-section plan seeded like tests/test_parent_studio.py::ParentSeedMixin; parent.brief.get / course.outline / parent.blueprint.read / parent.review.read / parent.reflection.list read back through api.dispatch",
            "homework": "real homework.create + homework.read over a course seeded with a validated lesson like tests/test_gm_homework.py::HomeworkCase",
            "syllabus": "frozen syllabus.parse.v1 contract fixture (tests/test_desktop_syllabus_ui.FIXTURE_PARSE / _fixture_alignment); not a live parse",
            "create": "the create form's own seed (goal + one contract scope); no backend data",
            "settings": "the host ctx.storage contract with CB_HOME_PREF_DEFAULTS; no backend data",
        }

        return {
            "runtime": runtime,
            "health": health,
            "rest_media": {path: payload for path, payload in rest.items() if path.startswith("/media/")},
            "catalog_fresh": catalog_fresh,
            "catalog_installed": catalog_installed,
            "install": install,
            "library_empty": library_empty,
            "library_full": library_full,
            "packs": packs,
            "course_row": row,
            "course_id": course_id,
            "enrollment_id": enrollment_id,
            "objective_id": objective_id,
            "detail_rpc": detail_rpc,
            "installed_item": installed_item,
            "parent_list": parent_list,
            "parent_course_row": parent_course_row,
            "parent_detail_rpc": parent_detail_rpc,
            "homework_library": homework_library,
            "homework_sources": homework_sources,
            "homework_read": homework_read,
            "homework_store": homework_store,
            "syllabus_parse": syllabus_parse,
            "syllabus_alignment": syllabus_alignment,
            "implemented": implemented,
            "sources": sources,
            "create_goal": CREATE_GOAL,
            "create_dials": CREATE_DIALS,
            "create_scopes": list(CREATE_SCOPES),
        }
    finally:
        if previous is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous
        shutil.rmtree(home, ignore_errors=True)


def _create_seed(scope: str) -> dict[str, Any]:
    return {
        "goal": CREATE_GOAL,
        "scope": scope,
        "title": "Coffee in Kyoto",
        "dials": dict(CREATE_DIALS),
        "recipe": "casual",
    }


def frames(data: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per destination. `rpc` names a bundle below; `rest` is merged into the replay map."""
    media = data["rest_media"]
    common_rest = {**media, "/runtime": data["runtime"], "/health": data["health"]}
    destinations: list[dict[str, Any]] = [
        {
            "id": "workshop-discover",
            "title": "Workshop — Discover",
            "surface": "WorkshopView",
            "rest": {**common_rest, "/workshop/catalog": data["catalog_fresh"]},
            "rpc": {"library.list": data["library_empty"], "pack.list": data["packs"]},
            "source": ["catalog_fresh", "library_empty", "pack_list"],
        },
        {
            "id": "workshop-library",
            "title": "Workshop — Library",
            "surface": "WorkshopView",
            "rest": {**common_rest, "/workshop/catalog": data["catalog_installed"]},
            "rpc": {"library.list": data["library_full"], "pack.list": data["packs"]},
            "actions": [{"click": '[data-cb-workshop-tab="library"]', "note": "Library tab"}],
            "source": ["catalog_installed", "library_full", "pack_list"],
        },
        {
            "id": "workshop-provenance",
            "title": "Workshop — Provenance",
            "surface": "WorkshopView",
            "rest": {**common_rest, "/workshop/catalog": data["catalog_installed"]},
            "rpc": {"library.list": data["library_full"], "pack.list": data["packs"]},
            "actions": [{"click": '[data-cb-workshop-tab="provenance"]', "note": "Provenance tab"}],
            "source": ["catalog_installed", "library_full", "pack_list"],
        },
        {
            "id": "workshop-pack",
            "title": "Workshop — pack detail",
            "surface": "WorkshopDetail",
            "props": {"item": data["installed_item"]},
            "rest": common_rest,
            "rpc": {},
            "source": ["catalog_installed", "course_row"],
        },
        {
            "id": "courses-list",
            "title": "Courses — list",
            "surface": "CoursesView",
            "rest": common_rest,
            "rpc": {"library.list": data["library_full"]},
            "source": ["library_full", "course_row"],
        },
        {
            "id": "courses-empty",
            "title": "Courses — first run",
            "surface": "CoursesView",
            "rest": common_rest,
            "rpc": {"library.list": data["library_empty"]},
            "source": ["library_empty"],
        },
        {
            "id": "courses-detail",
            "title": "Course detail",
            "surface": "CourseDetail",
            "props": {"row": data["course_row"]},
            "rest": common_rest,
            "rpc": data["detail_rpc"],
            "source": ["course_row", "course_detail"],
        },
        {
            "id": "create-empty",
            "title": "Create course — the goal step, empty",
            "surface": "CreateCourseFlow",
            "props": {"seed": None},
            "rest": common_rest,
            "rpc": {},
            "source": ["create"],
        },
        {
            "id": "studio-detail",
            "title": "Parent Studio — one plan",
            "surface": "StudioDetail",
            "props": {"course": data["parent_course_row"], "revision": 0},
            "rest": common_rest,
            "rpc": data["parent_detail_rpc"],
            "source": ["parent"],
        },
        {
            "id": "studio-list",
            "title": "Parent Studio — plans",
            "surface": "StudioList",
            "rest": common_rest,
            "rpc": {"library.list": data["parent_list"]},
            "source": ["parent"],
        },
        {
            "id": "studio-brief",
            "title": "Parent Studio — a new brief",
            "surface": "StudioBriefForm",
            "props": {"initial": None},
            "rest": common_rest,
            "rpc": {},
            "source": ["parent"],
        },
        {
            "id": "takehome-shelf",
            "title": "Take-home — shelf",
            "surface": "TakeHomeStudio",
            "rest": common_rest,
            "rpc": {"library.list": data["homework_library"], "takehome.sources": data["homework_sources"]},
            "source": ["homework"],
        },
        {
            "id": "homework-studio",
            "title": "Homework — studio",
            "surface": "HomeworkStudio",
            "rest": common_rest,
            "rpc": {
                "library.list": data["homework_library"],
                "takehome.sources": data["homework_sources"],
                "homework.read": data["homework_read"],
            },
            "storage": data["homework_store"],
            "source": ["homework"],
        },
        {
            "id": "syllabus-intake",
            "title": "Syllabus — intake",
            "surface": "SyllabusIntakeFlow",
            "rest": common_rest,
            "rpc": {},
            "source": ["syllabus"],
        },
        {
            "id": "syllabus-parse",
            "title": "Syllabus — parse review",
            "surface": "SyllabusParseReview",
            "props": {
                "parsed": data["syllabus_parse"],
                "blocks": data["syllabus_parse"].get("blocks", []),
            },
            "rest": common_rest,
            "rpc": {},
            "source": ["syllabus"],
        },
        {
            "id": "syllabus-alignment",
            "title": "Syllabus — alignment",
            "surface": "SyllabusAlignmentReview",
            "props": {"alignment": data["syllabus_alignment"]},
            "rest": common_rest,
            "rpc": {},
            "source": ["syllabus"],
        },
        {
            "id": "home-settings",
            "title": "Home — settings sheet",
            "surface": "HomeSettingsSheet",
            "props": {"prefs": {}, "classroom": {"course_id": data["course_id"], "title": data["course_row"]["title"]}},
            "rest": common_rest,
            "rpc": {},
            "source": ["settings"],
        },
    ]
    for scope in data["create_scopes"]:
        destinations.append(
            {
                "id": f"create-{scope}",
                "title": f"Create course — review, {'one lesson' if scope == 'single' else scope + ' course'}",
                "surface": "CreateCourseFlow",
                "props": {"seed": _create_seed(scope)},
                "rest": common_rest,
                "rpc": {},
                "source": ["create"],
            }
        )
    for destination in destinations:
        destination["implemented"] = data["implemented"]
        destination.setdefault("props", {})
        destination.setdefault("rpc", {})
        destination.setdefault("rest", {})
        destination.setdefault("actions", [])
    return destinations


def fixture_record(data: dict[str, Any]) -> dict[str, Any]:
    """Small, hashable facts about what the fixture build actually contained."""
    import hashlib

    return {
        "installed_pack": PACK_ID,
        "course_id": data["course_id"],
        "enrollment_id": data["enrollment_id"],
        "objective_id": data["objective_id"],
        "catalog_packs": [item["pack_id"] for item in data["catalog_installed"]["items"]],
        "library_rows": len(data["library_full"]["result"]["items"]),
        "homework_task_id": data["homework_read"]["result"]["task"]["task_id"],
        "fixture_sha256": hashlib.sha256(
            json.dumps(
                {
                    "catalog": data["catalog_installed"],
                    "library": data["library_full"],
                    "detail": {k: v.get("ok") for k, v in data["detail_rpc"].items()},
                    "parent": data["parent_list"],
                    "homework": data["homework_read"],
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest(),
        **data["sources"],
    }
