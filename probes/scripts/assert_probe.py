#!/usr/bin/env python3
"""Assertions over recorded probe evidence. Prints JSON verdicts; exit 1 on FAIL."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

MARKER_EXPECT = {
    "isolated": ["CB_CTX_COURSE"],
    "repo_course": ["CB_CTX_REPO", "CB_CTX_COURSE"],
    "repo_root": ["CB_CTX_REPO"],
    "outside": [],
    "ignore_rules": [],
}


def load_log(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def p1(log: str, sids: list[str]) -> dict:
    rows = load_log(Path(log))
    turns = [r for r in rows if r.get("event") == "pre_llm_call"]
    starts = [r for r in rows if r.get("event") == "on_session_start"]
    ids = [r for r in rows if r.get("event") == "tool_ids"]
    checks = {
        "turns_observed": len(turns),
        "session_id_stable_across_resume": len({r["session_id"] for r in turns}) == 1,
        "turn_id_changes_per_turn": len({r["turn_id"] for r in turns}) == len(turns),
        "turn_id_prefixed_by_session_id": all(r["turn_id"].startswith(r["session_id"] + ":") for r in turns),
        "task_id_equals_session_id": all(r.get("task_id") == r.get("session_id") for r in turns),
        "on_session_start_fires_once": len(starts) == 1,
        "tool_receives_session_and_task_but_no_turn_id": bool(ids) and ids[0].get("session_id") and ids[0].get("task_id") and not ids[0].get("turn_id"),
        "tool_agent_cwd_is_course_dir": bool(ids) and ids[0].get("resolved_agent_cwd", "").endswith("/isolated_course"),
        "tool_process_cwd_is_gateway_cwd": bool(ids) and ids[0].get("process_cwd") != ids[0].get("resolved_agent_cwd"),
    }
    ok = all(v for k, v in checks.items() if k not in ("turns_observed",))
    return {"probe": "p1", "status": "PASS" if ok else "FAIL", "checks": checks}


def p2(db: str, sid: str, nonce: str) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, role, content, api_content FROM messages WHERE session_id=? ORDER BY id", (sid,)
    ).fetchall()
    users = [r for r in rows if r["role"] == "user"]
    persisted = any(nonce in (r["api_content"] or "") for r in users)
    content_clean = all(nonce not in (r["content"] or "") for r in users)
    return {
        "probe": "p2",
        "status": "FAIL" if persisted else "PASS",
        "checks": {
            "injected_text_persisted_in_api_content": persisted,
            "display_content_left_clean": content_clean,
            "user_rows": len(users),
        },
        "note": "FAIL = pre_llm_call injection is not ephemeral on this runtime: it is stored in api_content and replayed.",
    }


def p3(raw: str) -> dict:
    observed = {}
    for name in MARKER_EXPECT:
        path = Path(raw) / f"{name}.jsonl"
        rows = load_log(path)
        markers = set()
        for r in rows:
            if r.get("event") == "pre_api_request":
                markers.update(r.get("markers") or [])
        observed[name] = sorted(markers)
    checks = {name: observed[name] == sorted(MARKER_EXPECT[name]) for name in MARKER_EXPECT}
    leak = "CB_CTX_REPO" in observed.get("isolated", [])
    status = "PASS" if all(checks.values()) else "FAIL"
    return {"probe": "p3", "status": status, "checks": checks, "observed": observed,
            "note": "repo_course expects repo policy to leak on this runtime; that is why a course workspace must live outside git roots."}


def p4(raw: str) -> dict:
    d = Path(raw)
    realistic = []
    for p in sorted(d.glob("p4_realistic_*.json")):
        realistic.append(json.loads(p.read_text(encoding="utf-8")))
    lat = sorted(float(x["elapsed_s"]) for x in realistic if x.get("elapsed_s") is not None)
    p50 = lat[len(lat) // 2] if lat else None
    p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None
    checks = {
        "realistic_samples": len(lat),
        "all_realistic_json": all(x.get("content_type") == "json" for x in realistic),
        "latency_p50_under_4s": bool(p50 is not None and p50 < 4.0),
        "latency_p95_under_8s": bool(p95 is not None and p95 < 8.0),
    }
    extra = {}
    for name in ("invalid_json", "timeout", "outage", "schema_ok"):
        p = d / f"p4_{name}.json"
        if p.exists():
            extra[name] = json.loads(p.read_text(encoding="utf-8"))
    if "invalid_json" in extra:
        # The model may comply with json_mode; the seam test below proves how non-JSON
        # text is classified. This check records the observed path, not model compliance.
        extra["invalid_json"]["observed_path"] = (
            "json" if extra["invalid_json"].get("content_type") == "json" else "text")
    if "timeout" in extra:
        checks["timeout_raises"] = extra["timeout"].get("ok") is False
    if "outage" in extra:
        checks["outage_model_differs_from_pin"] = extra["outage"].get("model") != "definitely-not-a-model-xyz"
    seam = d / "p4_runtime_seam.json"
    if seam.exists():
        s = json.loads(seam.read_text(encoding="utf-8"))
        checks["jsonschema_available"] = isinstance(s.get("jsonschema"), str) and s["jsonschema"][0].isdigit()
        checks["schema_violation_raises"] = isinstance(s.get("with_jsonschema"), dict) and "error_type" in s["with_jsonschema"]
        checks["invalid_accepted_without_package"] = (s.get("without_jsonschema") or {}).get("content_type") == "json"
    status = "PASS" if all(checks.values()) else "FAIL"
    return {"probe": "p4", "status": status, "checks": checks,
            "latency_s": {"p50": p50, "p95": p95, "samples": lat}, "scenarios": extra}


def p5(raw: str) -> dict:
    d = Path(raw)
    result = json.loads((d / "p5_tool_result.json").read_text(encoding="utf-8"))
    seam = json.loads((d / "p5_media_seam.json").read_text(encoding="utf-8"))
    checks = {
        "artifact_exists": seam.get("artifact_exists"),
        "text_fallback_exists": seam.get("text_fallback_exists"),
        "extract_media_finds_plain_tag": bool(seam.get("extract_media_plain_text")),
        "gateway_auto_append_excludes_plugin_tool": seam.get("plugin_tool_is_allowlisted") is False,
        "hash_recorded": bool(result.get("sha256")),
    }
    return {"probe": "p5", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
            "seam": seam}


def p6(jobs: str) -> dict:
    data = json.loads(Path(jobs).read_text(encoding="utf-8"))
    jobs_list = data.get("jobs", [])
    by_name = {}
    for j in jobs_list:
        by_name.setdefault(j["name"], []).append(j)
    te = by_name.get("qa-tele", [{}])[0]
    om = by_name.get("qa-omit", [{}])[0]
    checks = {
        "omitted_delivery_stored_as_local": om.get("deliver") == "local",
        "explicit_target_stored_verbatim": te.get("deliver") == "telegram:999999999",
        "created_paused": all(j.get("state") == "paused" for j in jobs_list),
        "duplicate_name_creates_second_job": len(by_name.get("qa-omit", [])) >= 2,
        "origin_absent_without_gateway_session": om.get("origin") is None,
    }
    return {"probe": "p6", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def p7(raw: str) -> dict:
    d = Path(raw)
    checks = {}
    for key, want in (("submit_first", "committed"), ("submit_duplicate", "duplicate"),
                      ("submit_conflict", "conflict"), ("submit_stale", "stale")):
        p = d / f"p7_{key}.json"
        if p.exists():
            checks[key] = json.loads(p.read_text(encoding="utf-8")).get("status") == want
    p = d / "p7_hook_bypass.json"
    if p.exists():
        b = json.loads(p.read_text(encoding="utf-8"))
        checks["hook_exception_turn_proceeded"] = b.get("raise_turn_proceeded") is True
        checks["hook_timeout_turn_proceeded"] = b.get("timeout_turn_proceeded") is True
        checks["hook_did_not_run_after_timeout"] = b.get("pre_llm_after_timeout") is False
        checks["submit_worked_while_hook_disabled"] = b.get("submit_after_bypass") == "committed"
    return {"probe": "p7", "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def main() -> None:
    kind = sys.argv[1]
    args = sys.argv[2:]
    if kind == "p1":
        out = p1(args[0], args[1:])
    elif kind == "p2":
        out = p2(*args)
    elif kind == "p3":
        out = p3(args[0])
    elif kind == "p4":
        out = p4(args[0])
    elif kind == "p5":
        out = p5(args[0])
    elif kind == "p6":
        out = p6(args[0])
    elif kind == "p7":
        out = p7(args[0])
    else:
        raise SystemExit(f"unknown probe {kind}")
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if out["status"] == "PASS" or out["status"] == "BLOCKED" else 2)


if __name__ == "__main__":
    main()
