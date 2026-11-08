#!/usr/bin/env python3
"""H-186 proof: import the bundled v2 demo pack and read it back the way the Desktop does.

Run from the plugin root:

    PYTHONPATH=. python3 scripts/h186-demo-pack-probe.py [audit/h186/evidence.json]

It uses a throwaway HERMES_HOME, the real migrations, the real dispatcher and the real pack
archive. No provider is called, no network is used and nothing is written to the operator's
profile. The JSON it writes is the raw response text, not a summary.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from coursebook import api, archive, db, domain, pack_flow, packs  # noqa: E402,F401
from coursebook.api import RPC_CONTRACT, RPC_CONTRACT_VERSION  # noqa: E402

JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"


def request(method: str, payload: dict, *, operation_id: str, revision: int | None = None,
            key: str | None = None) -> dict:
    body = {
        "contract": RPC_CONTRACT,
        "contract_version": RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": operation_id,
        "payload": payload,
    }
    if revision is not None:
        body["expected_revision"] = revision
    if key is not None:
        body["idempotency_key"] = key
    return api.dispatch(body)


def call(method: str, payload: dict, **kwargs) -> dict:
    response = request(method, payload, **kwargs)
    if not response["ok"]:
        raise SystemExit(f"{method} failed: {json.dumps(response['error'], ensure_ascii=False)}")
    return response


def scalar(sql: str, params: tuple = ()):
    with db.read() as connection:
        row = connection.execute(sql, params).fetchone()
    return None if row is None else row[0]


def objective_id(course_id: str, ordinal: int) -> str:
    return str(scalar(
        "SELECT o.id FROM objectives o JOIN plans p ON p.id = o.plan_id"
        " WHERE p.course_id = ? AND o.ordinal = ?",
        (course_id, ordinal),
    ))


def import_demo(work: Path, name: str) -> dict:
    manifest, files = archive.read_directory(JAPANESE)
    destination = work / name
    archive.write_archive(destination, manifest, files)
    staged = pack_flow.grant_local_file(destination)
    preview = call("pack.preview", {"staged_id": staged}, operation_id=f"h186-preview-{name.removesuffix('.zip')}")["result"]
    imported = call(
        "pack.import", {"staged_id": staged, "mode": "fresh"}, operation_id=f"h186-import-{name.removesuffix('.zip')}"
    )["result"]
    return {"preview": preview, "import": imported}


def library_row(enrollment_id: str) -> dict:
    result = call("library.list", {}, operation_id="h186-library")["result"]
    for row in result["items"]:
        if row["enrollment_id"] == enrollment_id:
            return row
    raise SystemExit("imported enrollment is missing from library.list")


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "audit" / "h186" / "evidence.json"
    home = tempfile.mkdtemp(prefix="coursebook-h186-probe-")
    previous = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = home
    work = Path(tempfile.mkdtemp(prefix="coursebook-h186-work-"))
    evidence: dict = {"home": home, "pack": str(JAPANESE), "steps": {}}
    try:
        db.migrate()
        manifest = packs.load_manifest(JAPANESE / "pack.json")
        evidence["manifest"] = {
            "contract_version": manifest["contract_version"],
            "pack_version": manifest["pack_version"],
            "title": manifest["title"],
            "content_hash": manifest["content_hash"],
            "media": manifest["media"],
            "checks": [
                {
                    "objective_id": objective["objective_id"],
                    "ordinal": objective["ordinal"],
                    "evidence_target": objective["evidence_target"],
                    "check_id": check["check_id"],
                    "reference_answer": check["reference_answer"],
                    "accepted_alternatives": check["accepted_alternatives"],
                }
                for objective in manifest["objectives"]
                for check in objective["checks"]
            ],
        }
        evidence["audit_problems"] = packs.audit_bundle(JAPANESE)

        first = import_demo(work, "first.zip")
        evidence["steps"]["first_import"] = first
        course_id = first["import"]["course_id"]
        enrollment_id = first["import"]["enrollment_id"]

        evidence["steps"]["runs"] = [
            {"objective_id": row[0], "state": row[1]}
            for row in _rows(
                "SELECT objective_id, state FROM lesson_runs WHERE enrollment_id = ? ORDER BY rowid",
                (enrollment_id,),
            )
        ]
        evidence["steps"]["pages"] = {}
        for ordinal in (1, 2, 3, 4):
            page = call(
                "lesson.page",
                {"enrollment_id": enrollment_id, "objective_id": objective_id(course_id, ordinal)},
                operation_id=f"h186-page-{ordinal}",
            )["result"]
            media = [child for block in page["document"]["blocks"] for child in block["media"]]
            (out.parent / f"page-{ordinal}.json").parent.mkdir(parents=True, exist_ok=True)
            (out.parent / f"page-{ordinal}.json").write_text(
                json.dumps(page, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
            )
            evidence["steps"]["pages"][str(ordinal)] = {
                "objective_id": page["section"]["objective_id"],
                "title": page["section"]["title"],
                "artifact_count": len(page["artifacts"]),
                "media_count": len(media),
                "media": [
                    {
                        "kind": child["kind"],
                        "artifact_id": child["artifact_id"],
                        "caption": child["purpose"],
                        "text_equivalent": child["text_equivalent"],
                        "degraded": child["degraded"],
                    }
                    for child in media
                ],
            }

        evidence["steps"]["next_step_fresh"] = library_row(enrollment_id)["next_step"]
        # A run-recency query would pick objective 4 once its row is the most recently touched;
        # the probe proves the answer follows ordinal instead.
        with db.transaction() as connection:
            connection.execute(
                "UPDATE lesson_runs SET updated_at = '2999-01-01T00:00:00Z'"
                " WHERE objective_id = ?",
                (objective_id(course_id, 4),),
            )
        evidence["steps"]["next_step_after_touching_last_run"] = library_row(enrollment_id)["next_step"]

        opened = call(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id(course_id, 4)},
            operation_id="h186-open-4",
            revision=int(scalar("SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,))),
        )["result"]
        check4 = {"check_id": opened["check_id"], "check_version": opened["check_version"]}
        evidence["steps"]["objective4_reference"] = json.loads(str(scalar(
            "SELECT reference_json FROM checks WHERE id = ?", (check4["check_id"],)
        )))
        wrong = call(
            "attempt.submit",
            {
                "enrollment_id": enrollment_id,
                **check4,
                "attempt_nonce": "h186-wrong",
                "answer": {"kind": "text", "text": "B"},
            },
            operation_id="h186-wrong",
            revision=int(scalar("SELECT revision FROM enrollments WHERE id = ?", (enrollment_id,))),
            key="h186-wrong",
        )["result"]
        evidence["steps"]["objective4_wrong"] = wrong

        # A fresh import for the correct attempt: a second answer to the same check is classified
        # as following feedback, and this proof wants an unaided pass, not a hinted one.
        second = import_demo(work, "second.zip")
        course2 = second["import"]["course_id"]
        enrollment2 = second["import"]["enrollment_id"]
        opened2 = call(
            "check.open",
            {"enrollment_id": enrollment2, "objective_id": objective_id(course2, 4)},
            operation_id="h186-open-4b",
            revision=int(scalar("SELECT revision FROM enrollments WHERE id = ?", (enrollment2,))),
        )["result"]
        correct = call(
            "attempt.submit",
            {
                "enrollment_id": enrollment2,
                "check_id": opened2["check_id"],
                "check_version": opened2["check_version"],
                "attempt_nonce": "h186-right",
                "answer": {"kind": "text", "text": "casual"},
            },
            operation_id="h186-right",
            revision=int(scalar("SELECT revision FROM enrollments WHERE id = ?", (enrollment2,))),
            key="h186-right",
        )["result"]
        evidence["steps"]["objective4_correct"] = correct
        evidence["steps"]["objective4_state_after_correct"] = scalar(
            "SELECT state FROM objectives WHERE id = ?", (objective_id(course2, 4),)
        )
        evidence["steps"]["next_step_after_objective4"] = library_row(enrollment2)["next_step"]

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({
            "out": str(out),
            "contract_version": manifest["contract_version"],
            "media_links": len(manifest["media"]),
            "media_count_page2": evidence["steps"]["pages"]["2"]["media_count"],
            "artifact_count_page2": evidence["steps"]["pages"]["2"]["artifact_count"],
            "next_step_fresh": evidence["steps"]["next_step_fresh"],
            "wrong_verdict": wrong["verdict"],
            "correct_verdict": correct["verdict"],
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        if previous is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


def _rows(sql: str, params: tuple = ()):
    with db.read() as connection:
        return [tuple(row) for row in connection.execute(sql, params)]


if __name__ == "__main__":
    raise SystemExit(main())
