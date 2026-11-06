"""Coursebook QA probe plugin — observable evidence only, never product code.

Every hook/tool appends one JSON object per event to the file named by
``CB_PROBE_LOG`` (absolute path). With no CB_PROBE_LOG the plugin is inert
apart from tool registration, so it cannot touch an operator session.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()
_MAX_SP = 200_000

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


# --------------------------------------------------------------------------- log


def _log_path() -> str:
    path = (os.environ.get("CB_PROBE_LOG") or "").strip()
    if path:
        return path
    # A routed gateway turn has no CB_PROBE_LOG in the process env; fall back to a
    # marker-gated per-profile path so hook evidence survives multiplexing.
    try:
        from hermes_constants import get_hermes_home

        candidate = Path(get_hermes_home()) / "test-root" / "logs" / "probe.jsonl"
        if candidate.parent.is_dir():
            return str(candidate)
    except Exception:
        pass
    return ""


def _log(event: str, **fields) -> None:
    path = _log_path()
    if not path:
        return
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
    rec.update(fields)
    try:
        with _LOCK:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _safe(fn):
    """Never let evidence collection break the runtime under test."""

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            _log("probe_error", where=getattr(fn, "__name__", "?"), trace=traceback.format_exc())
            return None

    return wrapper


# ------------------------------------------------------------------------- hooks


def _control() -> dict:
    """Per-call control file (multiplexed gateway turns cannot see the caller's env)."""
    path = (os.environ.get("CB_PROBE_CONTROL") or "").strip()
    if not path:
        try:
            from hermes_constants import get_hermes_home

            path = str(Path(get_hermes_home()) / "test-root" / "control.json")
        except Exception:
            return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


@_safe
def h_pre_llm_call(session_id="", task_id="", turn_id="", user_message="", is_first_turn=None,
                   model="", platform="", conversation_history=None, **kw):
    _log(
        "pre_llm_call",
        session_id=session_id, task_id=task_id, turn_id=turn_id,
        is_first_turn=is_first_turn, model=model, platform=platform,
        user_message_chars=len(user_message or ""),
        history_len=len(conversation_history or []),
        kw_keys=sorted(kw),
    )
    ctrl = _control()
    sleep_s = float(ctrl.get("pre_llm_sleep") or 0)
    if sleep_s:
        _log("pre_llm_call_sleep", seconds=sleep_s, session_id=session_id)
        time.sleep(sleep_s)
    if ctrl.get("pre_llm_raise"):
        raise RuntimeError("cb-probe forced pre_llm_call failure")
    sentinel = ctrl.get("inject_sentinel")
    if sentinel:
        _log("pre_llm_inject", session_id=session_id, sentinel=sentinel)
        return {"context": f"CB_INJECTED_SENTINEL[{sentinel}] end-sentinel"}
    return None


@_safe
def h_post_llm_call(session_id="", task_id="", turn_id="", user_message="", assistant_response="",
                    model="", platform="", conversation_history=None, **kw):
    _log("post_llm_call", session_id=session_id, task_id=task_id, turn_id=turn_id, model=model,
         platform=platform, user_message_chars=len(user_message or ""),
         assistant_chars=len(assistant_response or ""),
         assistant_head=(assistant_response or "")[:120], kw_keys=sorted(kw))


@_safe
def h_post_tool_call(tool_name="", args=None, result="", task_id="", duration_ms=None, session_id="",
                     turn_id="", tool_call_id="", status=None, **kw):
    _log("post_tool_call", tool_name=tool_name, task_id=task_id, session_id=session_id,
         turn_id=turn_id, tool_call_id=tool_call_id, duration_ms=duration_ms, status=status,
         result_chars=len(result or ""), result_head=(result or "")[:300])


@_safe
def h_pre_api_request(session_id="", task_id="", turn_id="", api_request_id="", api_call_count=None,
                      model="", provider="", api_mode="", message_count=None, request_messages=None,
                      request=None, **kw):
    sp = ""
    msgs = request_messages or []
    if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
        c = msgs[0].get("content")
        if isinstance(c, str):
            sp = c
        elif isinstance(c, list):
            sp = "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
    markers = [m for m in ("CB_CTX_ROOT", "CB_CTX_REPO", "CB_CTX_COURSE", "CB_CTX_HOME",
                           "CB_CTX_GITIGNORE", "CB_INJECTED_SENTINEL") if m in sp]
    # Where does a sentinel live: the current (last) user message, or earlier replayed history?
    sentinel_idx, sentinel_total = [], 0
    for i, m in enumerate(msgs):
        blob = json.dumps(m, ensure_ascii=False)
        if "CB_INJECTED_SENTINEL" in blob:
            sentinel_total += blob.count("CB_INJECTED_SENTINEL")
            sentinel_idx.append(i)
    _log("pre_api_request", session_id=session_id, task_id=task_id, turn_id=turn_id,
         api_request_id=api_request_id, api_call_count=api_call_count, model=model,
         provider=provider, api_mode=api_mode, message_count=message_count,
         system_prompt_chars=len(sp), markers=markers,
         sentinel_message_indexes=sentinel_idx, sentinel_occurrences=sentinel_total,
         sentinel_in_earlier_history=any(i < len(msgs) - 1 for i in sentinel_idx),
         message_roles=[m.get("role") if isinstance(m, dict) else type(m).__name__ for m in msgs],
         first_user_chars=(len(json.dumps(msgs[1])) if len(msgs) > 1 else 0))
    outdir = (os.environ.get("CB_PROBE_SP_DIR") or "").strip()
    if outdir and sp:
        try:
            Path(outdir).mkdir(parents=True, exist_ok=True)
            name = f"sp_{datetime.now(timezone.utc).strftime('%H%M%S%f')}_{api_request_id or uuid.uuid4().hex[:8]}.txt"
            Path(outdir, name).write_text(sp[:_MAX_SP], encoding="utf-8")
            _log("system_prompt_capture", file=name, markers=markers)
        except Exception:
            pass


@_safe
def h_post_api_request(session_id="", task_id="", turn_id="", api_request_id="", api_duration=None,
                       finish_reason="", response_model="", usage=None, **kw):
    _log("post_api_request", session_id=session_id, task_id=task_id, turn_id=turn_id,
         api_request_id=api_request_id, api_duration=api_duration, finish_reason=finish_reason,
         response_model=response_model, usage=usage)


@_safe
def h_pre_auxiliary_call(aux_task="", session_id="", task_id="", turn_id="", api_request_id="",
                         retry_count=None, streaming=None, model="", provider="", **kw):
    _log("pre_auxiliary_call", aux_task=aux_task, session_id=session_id, task_id=task_id,
         turn_id=turn_id, api_request_id=api_request_id, retry_count=retry_count,
         streaming=streaming, model=model, provider=provider)


@_safe
def h_post_auxiliary_call(aux_task="", api_duration=None, finish_reason="", response_model="",
                          usage=None, error=None, error_type="", **kw):
    _log("post_auxiliary_call", aux_task=aux_task, api_duration=api_duration,
         finish_reason=finish_reason, response_model=response_model, usage=usage,
         error=error, error_type=error_type)


@_safe
def h_on_session_start(session_id="", model="", platform="", **kw):
    _log("on_session_start", session_id=session_id, model=model, platform=platform, kw_keys=sorted(kw))


@_safe
def h_on_session_end(session_id="", task_id="", turn_id="", completed=None, failed=None,
                     interrupted=None, turn_exit_reason="", model="", platform="", **kw):
    _log("on_session_end", session_id=session_id, task_id=task_id, turn_id=turn_id,
         completed=completed, failed=failed, interrupted=interrupted,
         turn_exit_reason=turn_exit_reason, model=model, platform=platform, kw_keys=sorted(kw))


@_safe
def h_post_compaction(session_id="", old_session_id="", kind="", reason="", before_tokens=None,
                      after_tokens=None, messages_removed=None, **kw):
    _log("post_compaction", session_id=session_id, old_session_id=old_session_id, kind=kind,
         reason=reason, before_tokens=before_tokens, after_tokens=after_tokens,
         messages_removed=messages_removed, kw_keys=sorted(kw))


# -------------------------------------------------------------------------- tools


def _ids_payload(kw):
    home = os.environ.get("HERMES_HOME", "")
    cwd = os.getcwd()
    resolved_home, agent_cwd = "", ""
    try:
        from hermes_constants import get_hermes_home

        resolved_home = str(get_hermes_home())
    except Exception:
        pass
    try:
        from agent.runtime_cwd import resolve_agent_cwd

        agent_cwd = str(resolve_agent_cwd())
    except Exception:
        pass
    return {
        "process_cwd": cwd,
        "process_hermes_home_env": home,
        "resolved_hermes_home": resolved_home,
        "resolved_agent_cwd": agent_cwd,
        "profile": os.environ.get("HERMES_PROFILE", ""),
        "pid": os.getpid(),
        "session_id": kw.get("session_id", ""),
        "task_id": kw.get("task_id", ""),
        "turn_id": kw.get("turn_id", ""),
        "parent_session_id": kw.get("parent_session_id", ""),
        "user_task": (kw.get("user_task") or "")[:120],
    }


def t_ids(args, **kwargs):
    _log("tool_ids", **{k: v for k, v in _ids_payload(kwargs).items() if k != "user_task"})
    return json.dumps({"ok": True, **_ids_payload(kwargs)})


SCHEMA_IDS = {
    "name": "cb_probe_ids",
    "description": "QA probe: report the runtime/stored session identifiers and cwd visible to a plugin tool.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def t_emit_media(args, **kwargs):
    outdir = (os.environ.get("CB_PROBE_ARTIFACT_DIR") or "").strip()
    if not outdir:
        ctrl = _control()
        outdir = str(ctrl.get("artifact_dir") or "")
    if not outdir:
        try:
            from hermes_constants import get_hermes_home

            outdir = str(Path(get_hermes_home()) / "test-root" / "artifacts")
        except Exception:
            outdir = ""
    if not outdir:
        return json.dumps({"error": "no artifact dir configured"})
    d = Path(outdir)
    d.mkdir(parents=True, exist_ok=True)
    stem = (args.get("stem") or f"artifact_{uuid.uuid4().hex[:8]}").strip()
    png = d / f"{stem}.png"
    txt = d / f"{stem}.md"
    png.write_bytes(PNG_1PX)
    txt.write_text("# Coursebook text alternative\n\nA 1x1 probe image stands in for a sourced visual. "
                   "Text lessons remain complete without it.\n", encoding="utf-8")
    digest = hashlib.sha256(png.read_bytes()).hexdigest()
    _log("tool_media", png=str(png), text=str(txt), sha256=digest, bytes=png.stat().st_size)
    return json.dumps({
        "ok": True,
        "artifact_id": stem,
        "sha256": digest,
        "text_fallback": str(txt),
        "MEDIA": f"MEDIA:{png}",
    })


SCHEMA_MEDIA = {
    "name": "cb_probe_emit_media",
    "description": "QA probe: emit a cached visual artifact plus a complete text alternative and return a MEDIA: tag.",
    "parameters": {"type": "object", "properties": {"stem": {"type": "string"}}, "required": []},
}


GRADE_SCHEMA = {
    "type": "object",
    "required": ["verdict", "criteria"],
    "additionalProperties": False,
    "properties": {
        "verdict": {"enum": ["pass", "fail", "partial"]},
        "criteria": {"type": "array", "items": {"type": "string"}},
    },
}

GRADE_SCHEMA_IMPOSSIBLE = {
    "type": "object",
    "required": ["verdict"],
    "additionalProperties": False,
    "properties": {"verdict": {"const": "NEVER_A_VALID_VERDICT"}},
}


def _run_grade(ctx, scenario, timeout):
    t0 = time.monotonic()
    out = {"scenario": scenario, "timeout": timeout}
    try:
        if scenario == "schema_ok" or scenario == "baseline":
            r = ctx.llm.complete_structured(
                instructions="Grade the arithmetic answer. Answer: '42'. Reference: 6*7=42. "
                             "Return JSON with verdict 'pass' and one short criterion.",
                input=[{"type": "text", "text": "answer=42"}],
                json_schema=GRADE_SCHEMA, schema_name="coursebook_grade",
                task="cb_grader", timeout=timeout, purpose="qa-probe-grade",
            )
        elif scenario == "schema_violation":
            r = ctx.llm.complete_structured(
                instructions="Grade the arithmetic answer '42'. Return JSON.",
                input=[{"type": "text", "text": "answer=42"}],
                json_schema=GRADE_SCHEMA_IMPOSSIBLE, schema_name="coursebook_grade_impossible",
                task="cb_grader", timeout=timeout, purpose="qa-probe-grade",
            )
        elif scenario == "invalid_json":
            r = ctx.llm.complete_structured(
                instructions="Reply with the exact literal text NOT_JSON_AT_ALL and no braces or quotes.",
                input=[{"type": "text", "text": "answer=42"}],
                json_mode=True, task="cb_grader", timeout=timeout, purpose="qa-probe-grade",
            )
        elif scenario == "outage":
            r = ctx.llm.complete_structured(
                instructions="Grade: return JSON verdict pass.",
                input=[{"type": "text", "text": "answer=42"}],
                json_schema=GRADE_SCHEMA, schema_name="coursebook_grade",
                task="cb_grader_bad", timeout=timeout, purpose="qa-probe-grade",
            )
        elif scenario == "realistic":
            rubric = ("Rubric: (1) states that 6*7 equals 42 [required]; (2) shows a correct method "
                      "(repeated addition, array, or known fact) [required]; (3) uses a clear single "
                      "sentence [optional]. Accept equivalent phrasing. Reject an answer that states a "
                      "different product. Do not treat a correct number with no method as full credit; "
                      "mark partial. Context: learner is L0 beginner, answer typed in English with "
                      "romaji. ") * 8
            r = ctx.llm.complete_structured(
                instructions="Grade the learner answer against the rubric. Return JSON with verdict "
                             "pass/fail/partial and the observed criteria list.\n" + rubric,
                input=[{"type": "text", "text": "learner answer: six times seven is forty two because 6+6+6+6+6+6=42"}],
                json_schema=GRADE_SCHEMA, schema_name="coursebook_grade",
                task="cb_grader", timeout=timeout, purpose="qa-probe-grade",
            )
        elif scenario == "timeout":
            r = ctx.llm.complete_structured(
                instructions="Grade: return JSON verdict pass.",
                input=[{"type": "text", "text": "answer=42"}],
                json_schema=GRADE_SCHEMA, schema_name="coursebook_grade",
                task="cb_grader", timeout=timeout, purpose="qa-probe-grade",
            )
        else:
            return {"scenario": scenario, "error": "unknown scenario"}
        out.update({
            "ok": True,
            "elapsed_s": round(time.monotonic() - t0, 3),
            "content_type": getattr(r, "content_type", None),
            "parsed": getattr(r, "parsed", None),
            "provider": getattr(r, "provider", None),
            "model": getattr(r, "model", None),
            "usage": vars(getattr(r, "usage", None) or {}).get("total_tokens") if hasattr(r, "usage") else None,
            "text_head": (getattr(r, "text", "") or "")[:200],
            "audit": getattr(r, "audit", None),
        })
        _log("grade_result", **out)
        return out
    except Exception as exc:
        out.update({
            "ok": False, "elapsed_s": round(time.monotonic() - t0, 3),
            "error_type": type(exc).__name__, "error": str(exc)[:500],
        })
        _log("grade_error", **out)
        return out


def t_grade(args, **kwargs):
    ctx = kwargs.get("_ctx")
    scenario = (args.get("scenario") or "schema_ok").strip()
    timeout = args.get("timeout")
    return json.dumps(_run_grade(ctx, scenario, timeout), default=str)


SCHEMA_GRADE = {
    "name": "cb_probe_grade",
    "description": "QA probe: run one bounded structured aux grading call and report latency/failure semantics.",
    "parameters": {
        "type": "object",
        "properties": {
            "scenario": {"type": "string", "enum": ["schema_ok", "schema_violation", "invalid_json", "timeout", "outage"]},
            "timeout": {"type": "number"},
        },
        "required": ["scenario"],
    },
}


# ------- submit_attempt fixture: the authoritative backend command under test


def _db_path() -> str:
    path = (os.environ.get("CB_PROBE_DB") or "").strip()
    if path:
        return path
    ctrl = _control()
    if ctrl.get("db_path"):
        return str(ctrl["db_path"])
    try:
        from hermes_constants import get_hermes_home

        return str(Path(get_hermes_home()) / "test-root" / "probe.db")
    except Exception:
        return ""


def _db():
    path = _db_path()
    if not path:
        raise RuntimeError("CB_PROBE_DB not set")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS attempts (
               key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, answer TEXT NOT NULL,
               revision INTEGER NOT NULL, verdict TEXT NOT NULL, created_at TEXT NOT NULL)"""
    )
    conn.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK (id=1), revision INTEGER NOT NULL)")
    conn.execute("INSERT OR IGNORE INTO state (id, revision) VALUES (1, 1)")
    return conn


def submit_attempt(key: str, answer: str, revision: int) -> dict:
    payload_hash = hashlib.sha256(f"{answer}\x00{revision}".encode()).hexdigest()
    conn = _db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT payload_hash, verdict FROM attempts WHERE key=?", (key,)).fetchone()
        if row:
            conn.execute("COMMIT")
            if row[0] == payload_hash:
                return {"status": "duplicate", "key": key, "verdict": json.loads(row[1]), "durable": True}
            return {"status": "conflict", "key": key, "conflict": "idempotency_key_reused_with_other_payload", "durable": True}
        cur = conn.execute("SELECT revision FROM state WHERE id=1").fetchone()[0]
        if int(revision) != int(cur):
            conn.execute("COMMIT")
            return {"status": "stale", "http": 409, "current_revision": cur, "key": key, "durable": True}
        verdict = {"result": "pass" if answer.strip() == "42" else "fail",
                   "rubric_version": "r1", "evidence_class": "cold", "next_action": "continue_lesson"}
        conn.execute(
            "INSERT INTO attempts (key, payload_hash, answer, revision, verdict, created_at) VALUES (?,?,?,?,?,?)",
            (key, payload_hash, answer, cur, json.dumps(verdict), datetime.now(timezone.utc).isoformat()),
        )
        conn.execute("COMMIT")
        _log("submit_committed", key=key, answer=answer, revision=cur, verdict=verdict)
        return {"status": "committed", "key": key, "attempt_revision": cur, "verdict": verdict, "durable": True}
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def t_submit(args, **kwargs):
    try:
        out = submit_attempt(str(args.get("key") or ""), str(args.get("answer") or ""), int(args.get("revision") or 1))
    except Exception as exc:
        out = {"status": "error", "error_type": type(exc).__name__, "error": str(exc)}
    return json.dumps(out, default=str)


SCHEMA_SUBMIT = {
    "name": "cb_probe_submit",
    "description": "QA probe: the backend submit_attempt command (idempotent, revision-fenced).",
    "parameters": {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "answer": {"type": "string"},
            "revision": {"type": "integer"},
        },
        "required": ["key", "answer", "revision"],
    },
}


# ------------------------------------------------------------------- CLI command


def _cli(args):
    sub = getattr(args, "cbprobe_cmd", None)
    if sub == "ids":
        print(json.dumps({"cwd": os.getcwd(), "hermes_home": os.environ.get("HERMES_HOME", ""),
                          "pid": os.getpid()}, indent=2))
    elif sub == "submit":
        print(json.dumps(submit_attempt(args.key, args.answer, args.revision), indent=2, default=str))
    elif sub == "grade":
        ctx = _ctx_singleton
        print(json.dumps(_run_grade(ctx, args.scenario, args.timeout), indent=2, default=str))
    elif sub == "media":
        print(t_emit_media({"stem": args.stem or "cli_artifact"}))
    else:
        print("usage: cbqa cbprobe {ids|submit|grade|media} ...")


def _setup(subparser):
    subs = subparser.add_subparsers(dest="cbprobe_cmd")
    subs.add_parser("ids")
    p = subs.add_parser("submit")
    p.add_argument("--key", required=True)
    p.add_argument("--answer", required=True)
    p.add_argument("--revision", type=int, default=1)
    g = subs.add_parser("grade")
    g.add_argument("--scenario", default="schema_ok")
    g.add_argument("--timeout", type=float, default=None)
    m = subs.add_parser("media")
    m.add_argument("--stem", default="")
    subparser.set_defaults(func=_cli)


_ctx_singleton = None


# ---------------------------------------------------------------------- register


def register(ctx):
    global _ctx_singleton
    _ctx_singleton = ctx
    _log("plugin_registered", plugin="cb-probe", router=type(ctx).__name__)

    ctx.register_auxiliary_task("cb_grader", display_name="Coursebook grader",
                                description="QA probe slot for bounded structured grading")
    ctx.register_auxiliary_task("cb_grader_bad", display_name="Coursebook grader (outage probe)",
                                description="QA probe slot pointed at an unavailable model")

    ctx.register_hook("pre_llm_call", h_pre_llm_call)
    ctx.register_hook("post_llm_call", h_post_llm_call)
    ctx.register_hook("post_tool_call", h_post_tool_call)
    ctx.register_hook("pre_api_request", h_pre_api_request)
    ctx.register_hook("post_api_request", h_post_api_request)
    ctx.register_hook("pre_auxiliary_call", h_pre_auxiliary_call)
    ctx.register_hook("post_auxiliary_call", h_post_auxiliary_call)
    ctx.register_hook("on_session_start", h_on_session_start)
    ctx.register_hook("on_session_end", h_on_session_end)
    ctx.register_hook("post_compaction", h_post_compaction)

    ctx.register_tool(name="cb_probe_ids", toolset="cb_probe", schema=SCHEMA_IDS,
                      handler=lambda args, **kw: t_ids(args, **{**kw, "_ctx": ctx}))
    ctx.register_tool(name="cb_probe_emit_media", toolset="cb_probe", schema=SCHEMA_MEDIA,
                      handler=lambda args, **kw: t_emit_media(args, **{**kw, "_ctx": ctx}))
    ctx.register_tool(name="cb_probe_grade", toolset="cb_probe", schema=SCHEMA_GRADE,
                      handler=lambda args, **kw: t_grade(args, **{**kw, "_ctx": ctx}))
    ctx.register_tool(name="cb_probe_submit", toolset="cb_probe", schema=SCHEMA_SUBMIT,
                      handler=lambda args, **kw: t_submit(args, **{**kw, "_ctx": ctx}))

    ctx.register_cli_command(name="cbprobe", help="Coursebook QA probe commands",
                             setup_fn=_setup, handler_fn=_cli)
