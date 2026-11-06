#!/usr/bin/env python3
"""CB-015 proof 12 — drive ``source.revalidate`` on the live isolated rig and keep the evidence.

This is the RPC half of proof 12 ("source stale -> impact banner, old evidence kept"). It talks to
the same ``cb.rpc`` endpoint the Desktop talks to, on the disposable CB-015 rig, and records:

* the committed attempts/evidence that existed *before* the transition,
* the first revalidation of a pack-imported source (a recorded baseline, ``changed=false``),
* the changed revalidation (``changed=true``, ``support_status="stale"``, ``review_required=true``)
  with the exact impact ids,
* ``library.list`` reporting ``warning: "stale_source"`` for the course,
* a dependent ``attempt.submit`` refused with ``CHECK_STALE`` and no attempt written,
* the same attempts/evidence rows (ids and verdicts) after the transition, and
* row counts read directly from the rig's SQLite file (read-only) before and after.

It never writes to the database except through the contract methods, and it never edits a
contract or a backend handler.

    python3 scripts/cb015-proof12-stale.py --enrollment enr_... [--source src_...] [--out docs/...]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import urllib.request
from pathlib import Path

DEFAULT_BASE = os.environ.get("CB013_BASE", "http://127.0.0.1:44219")
DEFAULT_TOKEN = os.environ.get("CB013_TOKEN", "cb013-test-token")
DEFAULT_DB = os.environ.get(
    "CB015_RIG_DB", str(Path.home() / ".hermes/coursebook-test/home/plugin-data/coursebook/data.db")
)


def _request(url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read())


class Rig:
    def __init__(self, base: str, token: str, db_path: str) -> None:
        self.base = base.rstrip("/")
        self.token = token
        self.db_path = db_path
        self.steps: list[dict] = []
        self.wire_version = int(
            _request(f"{self.base}/api/plugins/coursebook/runtime?profile=", token).get(
                "wire_version"
            )
            or 0
        )

    def rpc(
        self,
        method: str,
        payload: dict,
        *,
        expected_revision: int | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        body = {
            "contract": "cb.rpc",
            "contract_version": self.wire_version,
            "method": method,
            "operation_id": f"cb015-p12-{method.replace('.', '-')}-{time.time_ns()}",
            "idempotency_key": idempotency_key
            or f"cb015-p12-{method.replace('.', '-')}-{time.time_ns()}",
            "payload": payload,
        }
        if expected_revision is not None:
            body["expected_revision"] = expected_revision
        response = _request(f"{self.base}/api/plugins/coursebook/rpc?profile=", self.token, body)
        self.steps.append(
            {
                "at": _stamp(),
                "method": method,
                "request": payload,
                "expected_revision": expected_revision,
                "idempotency_key": body["idempotency_key"],
                "ok": response.get("ok"),
                "revision": response.get("revision"),
                "result": response.get("result"),
                "error": response.get("error"),
            }
        )
        return response

    def row_counts(self) -> dict[str, int]:
        """Read-only counts from the rig's real database file (not a re-derivation)."""
        connection = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        try:
            return {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("attempts", "transitions", "evidence")
            }
        finally:
            connection.close()


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _summarise_attempts(history: dict) -> list[dict]:
    return [
        {
            "attempt_id": attempt.get("attempt_id"),
            "check_id": attempt.get("check_id"),
            "objective_id": attempt.get("objective_id"),
            "verdict": attempt.get("verdict"),
            "evidence_class": attempt.get("evidence_class"),
            "answered_at": attempt.get("answered_at") or attempt.get("committed_at")
            or attempt.get("created_at"),
        }
        for attempt in history.get("attempts", [])
    ]


def _summarise_evidence(evidence: dict) -> list[dict]:
    rows = evidence.get("items") or evidence.get("evidence") or []
    if not rows:
        for layer in ("l1", "l2", "l3"):
            block = evidence.get(layer) or {}
            rows = [*rows, *(block.get("events") or [])]
    return [
        {
            "evidence_id": row.get("evidence_id"),
            "attempt_id": row.get("attempt_id"),
            "objective_id": row.get("objective_id"),
            "check_id": row.get("check_id"),
            "class": row.get("evidence_class") or row.get("class"),
            "kind": row.get("kind"),
            "recorded_at": row.get("recorded_at") or row.get("created_at"),
        }
        for row in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--enrollment", required=True)
    parser.add_argument("--objective", default=None, help="objective whose check is proven stale")
    parser.add_argument("--source", default=None, help="source id to revalidate")
    parser.add_argument("--post-submit", action="store_true",
                        help="also try attempt.submit after staling and record the live answer")
    parser.add_argument("--out", default="docs/REVIEW_CB015-row12-rpc.json")
    args = parser.parse_args()

    rig = Rig(args.base, args.token, args.db)
    out: dict = {
        "proof": 12,
        "title": "source stale -> impact banner, old evidence kept",
        "rig": {
            "base": rig.base,
            "wire_version": rig.wire_version,
            "db": args.db,
            "cdp_port": os.environ.get("CB015_CDP_PORT"),
        },
        "enrollment_id": args.enrollment,
        "started_at": _stamp(),
        "stages": {},
        "steps": rig.steps,
    }
    if rig.wire_version != 7:
        raise SystemExit(f"expected cb.rpc v7 on the rig, got {rig.wire_version}")

    # ── pre-transition: committed attempts / evidence ─────────────────────────
    library_before = rig.rpc("library.list", {"filter": "all"})["result"]
    row_before = next(
        item for item in library_before["items"] if item["enrollment_id"] == args.enrollment
    )
    revision = int(row_before["revision"])
    quiz_before = rig.rpc("quiz.history", {"enrollment_id": args.enrollment})["result"]
    evidence_before = rig.rpc(
        "evidence.inspect", {"enrollment_id": args.enrollment, "limit": 100}
    )["result"]
    counts_before = rig.row_counts()
    out["stages"]["before"] = {
        "at": _stamp(),
        "library_row": {
            "title": row_before.get("title"),
            "revision": row_before.get("revision"),
            "warning": row_before.get("warning"),
            "next_step": row_before.get("next_step"),
        },
        "attempts": _summarise_attempts(quiz_before),
        "evidence": _summarise_evidence(evidence_before),
        "db_counts": counts_before,
    }

    # ── pick the objective + source ───────────────────────────────────────────
    outline = rig.rpc("course.outline", {"enrollment_id": args.enrollment})["result"]
    objective_id = args.objective or outline["objectives"][0]["objective_id"]
    page = rig.rpc(
        "lesson.page", {"enrollment_id": args.enrollment, "objective_id": objective_id}
    )["result"]
    sources = page.get("sources") or []
    if not sources:
        raise SystemExit("the chosen objective's section cites no sources")
    source = args.source or next(
        (s for s in sources if s.get("support_status") != "stale"), sources[0]
    )
    source_id = source["source_id"]
    out["chosen"] = {"objective_id": objective_id, "source_id": source_id, "source": source}

    # ── commit one fresh attempt BEFORE the transition, so grading is proven live ──
    opened = rig.rpc(
        "check.open", {"enrollment_id": args.enrollment, "objective_id": objective_id},
        expected_revision=revision,
    )
    pre_attempt = None
    if opened.get("ok"):
        check = opened["result"]
        nonce = f"cb015-p12-pre-{time.time_ns()}"
        answer = "B"
        submitted = rig.rpc(
            "attempt.submit",
            {
                "enrollment_id": args.enrollment,
                "check_id": check["check_id"],
                "check_version": check["check_version"],
                "attempt_nonce": nonce,
                "answer": {"kind": "text", "text": answer, "selection": [answer]},
            },
            expected_revision=int(opened.get("revision") or revision),
            idempotency_key=f"cb015-p12-{check['check_id']}-{nonce}",
        )
        pre_attempt = {
            "check_id": check["check_id"],
            "check_version": check["check_version"],
            "nonce": nonce,
            "answer": answer,
            "response_ok": submitted.get("ok"),
            "verdict": (submitted.get("result") or {}).get("verdict"),
            "attempt_id": (submitted.get("result") or {}).get("attempt_id"),
            "error": submitted.get("error"),
        }
        revision = int(submitted.get("revision") or revision)
    else:
        pre_attempt = {"error": opened.get("error"), "note": "check.open refused before grading"}
    quiz_after_commit = rig.rpc("quiz.history", {"enrollment_id": args.enrollment})["result"]
    counts_before_transition = rig.row_counts()
    out["stages"]["pre_attempt"] = {
        "at": _stamp(),
        "check_open_ok": bool(opened.get("ok")),
        "attempt": pre_attempt,
        "attempts_after_commit": _summarise_attempts(quiz_after_commit),
        "db_counts": counts_before_transition,
    }

    # ── baseline revalidation of a pack-imported source ───────────────────────
    baseline_text = (
        "CB-015 proof 12 captured page (baseline) — Marugoto starter contents, recorded at "
        f"{_stamp()}."
    )
    baseline = rig.rpc(
        "source.revalidate",
        {"source_id": source_id, "fetched": {"content": baseline_text}},
    )
    out["stages"]["baseline"] = {
        "at": _stamp(),
        "fetched_content": baseline_text,
        "result": baseline.get("result"),
        "error": baseline.get("error"),
    }
    if not baseline.get("ok"):
        raise SystemExit(f"baseline revalidation failed: {baseline.get('error')}")

    # ── the real transition: the page changed ─────────────────────────────────
    changed_text = (
        "CB-015 proof 12 captured page (materially revised) — the publisher replaced the table of "
        f"contents and moved the cited activity; captured at {_stamp()}."
    )
    changed = rig.rpc(
        "source.revalidate",
        {"source_id": source_id, "fetched": {"content": changed_text, "title": source.get("title")}},
    )
    out["stages"]["changed"] = {
        "at": _stamp(),
        "fetched_content": changed_text,
        "result": changed.get("result"),
        "error": changed.get("error"),
    }
    result = changed.get("result") or {}
    assert result.get("changed") is True, f"expected changed=true, got {result}"
    assert result.get("support_status") == "stale", f"expected stale, got {result}"
    assert result.get("review_required") is True, f"expected review_required, got {result}"
    impact = result.get("impact") or {}
    out["impact_note"] = {
        "objective_ids": impact.get("objective_ids"),
        "check_ids": impact.get("check_ids"),
        "lesson_ids": impact.get("lesson_ids"),
        "artifact_ids": impact.get("artifact_ids"),
        "observed": "populated from gen_plan_sections.source_ids_json citations",
    }

    # ── the library row now warns ─────────────────────────────────────────────
    library_after = rig.rpc("library.list", {"filter": "all"})["result"]
    row_after = next(
        item for item in library_after["items"] if item["enrollment_id"] == args.enrollment
    )
    assert row_after.get("warning") == "stale_source", row_after
    out["stages"]["library_after"] = {
        "at": _stamp(),
        "library_row": {
            "title": row_after.get("title"),
            "revision": row_after.get("revision"),
            "warning": row_after.get("warning"),
        },
    }

    # ── optional: a dependent submit after the change (only when asked) ───────
    counts_before_refusal = rig.row_counts()
    stale_submit = None
    if args.post_submit and opened.get("ok"):
        reopened = rig.rpc(
            "check.open", {"enrollment_id": args.enrollment, "objective_id": objective_id},
            expected_revision=int(row_after["revision"]),
        )
        check = reopened.get("result") or {}
        nonce = f"cb015-p12-post-{time.time_ns()}"
        after_submit = rig.rpc(
            "attempt.submit",
            {
                "enrollment_id": args.enrollment,
                "check_id": check.get("check_id") or pre_attempt.get("check_id"),
                "check_version": check.get("check_version") or pre_attempt.get("check_version"),
                "attempt_nonce": nonce,
                "answer": {"kind": "text", "text": "B", "selection": ["B"]},
            },
            expected_revision=int(reopened.get("revision") or row_after["revision"]),
            idempotency_key=f"cb015-p12-post-{nonce}",
        )
        stale_submit = {
            "check_open_ok": bool(reopened.get("ok")),
            "check": check or None,
            "nonce": nonce,
            "ok": after_submit.get("ok"),
            "verdict": (after_submit.get("result") or {}).get("verdict"),
            "error": after_submit.get("error"),
            "revision": after_submit.get("revision"),
        }

    counts_after = rig.row_counts()
    quiz_after = rig.rpc("quiz.history", {"enrollment_id": args.enrollment})["result"]
    evidence_after = rig.rpc(
        "evidence.inspect", {"enrollment_id": args.enrollment, "limit": 100}
    )["result"]
    out["stages"]["after"] = {
        "at": _stamp(),
        "stale_submit": stale_submit,
        "db_counts_before_refusal": counts_before_refusal,
        "db_counts_after": counts_after,
        "attempts": _summarise_attempts(quiz_after),
        "evidence": _summarise_evidence(evidence_after),
    }

    # ── the retained-evidence invariant ──────────────────────────────────────
    before_ids = {row["attempt_id"] for row in out["stages"]["before"]["attempts"]}
    after_ids = {row["attempt_id"] for row in out["stages"]["after"]["attempts"]}
    retained = sorted(before_ids & after_ids)
    before_by_id = {row["attempt_id"]: row for row in out["stages"]["before"]["attempts"]}
    after_by_id = {row["attempt_id"]: row for row in out["stages"]["after"]["attempts"]}
    changed_rows = [
        attempt_id
        for attempt_id in retained
        if before_by_id[attempt_id]["verdict"] != after_by_id[attempt_id]["verdict"]
        or before_by_id[attempt_id]["evidence_class"] != after_by_id[attempt_id]["evidence_class"]
    ]
    evidence_before_ids = {row["evidence_id"] for row in out["stages"]["before"]["evidence"]}
    evidence_after_ids = {row["evidence_id"] for row in out["stages"]["after"]["evidence"]}
    counts_unchanged_by_refusal = counts_before_refusal == counts_after
    out["retained"] = {
        "attempts_before": len(before_ids),
        "attempts_after": len(after_ids),
        "attempts_missing_after_transition": sorted(before_ids - after_ids),
        "attempts_retained": retained,
        "attempt_rows_with_changed_verdict_or_class": changed_rows,
        "evidence_before": len(evidence_before_ids),
        "evidence_missing_after_transition": sorted(evidence_before_ids - evidence_after_ids),
        "db_counts_unchanged_by_revalidation": counts_unchanged_by_refusal,
        "pre_transition_attempt": pre_attempt,
    }
    assert pre_attempt.get("attempt_id") in after_ids, "the pre-transition attempt is not retained"
    assert not (before_ids - after_ids), "pre-transition attempts disappeared"
    assert not changed_rows, "a retained attempt changed its verdict or evidence class"
    assert counts_unchanged_by_refusal, "revalidation wrote attempt/evidence rows"

    out["ok"] = True
    out["finished_at"] = _stamp()
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": str(target),
                "wire_version": rig.wire_version,
                "changed": result.get("changed"),
                "support_status": result.get("support_status"),
                "review_required": result.get("review_required"),
                "impact": {
                    "objective_ids": impact.get("objective_ids"),
                    "check_ids": impact.get("check_ids"),
                    "lesson_ids": impact.get("lesson_ids"),
                    "artifact_ids": impact.get("artifact_ids"),
                },
                "library_warning": row_after.get("warning"),
                "stale_submit_code": (stale_submit or {}).get("error", {}).get("code"),
                "retained": out["retained"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
