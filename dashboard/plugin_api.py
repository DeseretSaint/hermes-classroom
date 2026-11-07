"""Coursebook backend routes, mounted at ``/api/plugins/coursebook/``.

This module is imported by path (``spec_from_file_location``), so the plugin directory is not on
``sys.path``. :func:`_load_backend` loads the agent package explicitly under a stable private
name instead of mutating global import state.

Transport decisions (frozen for v1):

* ``GET  /health``  -> the ``health.get`` result body. Always HTTP 200; ``db.ready`` carries the
  state. A degraded backend is a fact to render, not a transport failure.
* ``GET  /schema``  -> the ``schema.get`` result body (contract inventory + hashes).
* ``POST /rpc``     -> one command. Always HTTP 200 with a contract envelope: ``ok:false`` means
  the command was refused, which the Desktop half renders from ``error.code``. Transport-level
  failures (no backend, unmounted route) are the only reason a client sees an HTTP error.

Host seams beside the frozen RPC contract (never new RPC methods):

* ``GET  /packs/intake``      -> whether this host can mint a local file grant.
* ``POST /packs/grant``       -> the only door a filesystem path may enter through; the result is a
  ``staged_id`` and nothing else. Refusals are HTTP 200 ``{ok:false, code:"PACK_REJECTED"}``.
* ``GET  /artifacts/{handle}`` -> streams one export after re-verifying it. The host's own auth
  middleware (``/api/`` session token / OAuth gate) authenticates the request; the handle is the
  only credential in the URL, is expiring, and never names a path.
* ``POST /sessions/bind``     -> the write half of ``binding.get``: the Desktop binds the focused
  chat's *stored* session id to the lesson run it opened. Never a runtime id, never recency.
  Refusals are HTTP 200 ``{ok:false, code, message}``.

No module-global process state lives here: SQLite is the source of truth, and the same package
may be imported twice by different loaders in one gateway process.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger("coursebook.api")

_BACKEND_PACKAGE = "coursebook_plugin_backend"
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent

router = APIRouter()


def _load_backend() -> Any:
    """Import the agent package by path, once, under a private module name."""
    if _BACKEND_PACKAGE in sys.modules:
        return sys.modules[_BACKEND_PACKAGE]
    spec = importlib.util.spec_from_file_location(
        _BACKEND_PACKAGE,
        _PLUGIN_ROOT / "__init__.py",
        submodule_search_locations=[str(_PLUGIN_ROOT)],
    )
    if spec is None or spec.loader is None:  # pragma: no cover - packaging error
        raise RuntimeError("coursebook: cannot locate the agent package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_BACKEND_PACKAGE] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_BACKEND_PACKAGE, None)
        raise
    return module


def _api() -> Any:
    _load_backend()
    return importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.api")


def _db() -> Any:
    _load_backend()
    return importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.db")


def _contracts() -> Any:
    _load_backend()
    return importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.contracts")


@router.get("/health")
async def health() -> dict[str, Any]:
    """Backend health. Never raises: an unavailable database is reported, not thrown."""
    api = _api()
    response = api.dispatch(
        {
            "contract": api.RPC_CONTRACT,
            "contract_version": api.RPC_CONTRACT_VERSION,
            "method": "health.get",
            "operation_id": "health-get-endpoint",
            "payload": {},
        }
    )
    return response


@router.get("/schema")
async def schema() -> dict[str, Any]:
    """Contract inventory with per-file hashes, so drift is visible from the client."""
    api = _api()
    return api.dispatch(
        {
            "contract": api.RPC_CONTRACT,
            "contract_version": api.RPC_CONTRACT_VERSION,
            "method": "schema.get",
            "operation_id": "schema-get-endpoint",
            "payload": {},
        }
    )


@router.post("/rpc")
async def rpc(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Execute one contract command. Shape errors come back as a contract envelope."""
    return _api().dispatch(body)


@router.post("/pronunciation/attempt")
async def pronunciation_attempt(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """One bounded pronunciation take, scored by Coursebook's own local recogniser.

    The body is the ``pronunciation.attempt`` request payload plus the envelope fields the caller
    controls (``expected_revision``, ``idempotency_key``). The take arrives as an audio data URL;
    a filesystem path is refused by the contract and never enters this process. The route is a thin
    adapter over :func:`coursebook.api.dispatch`, so a refusal is the same contract envelope the
    Desktop already renders — never a fabricated score.
    """
    api = _api()
    payload = {
        key: value
        for key, value in body.items()
        if key not in {"contract", "contract_version", "method", "operation_id",
                       "expected_revision", "idempotency_key"}
    }
    envelope: dict[str, Any] = {
        "contract": api.RPC_CONTRACT,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "method": "pronunciation.attempt",
        "operation_id": str(body.get("operation_id") or f"pronunciation-{uuid.uuid4().hex}"),
        "payload": payload,
    }
    for name in ("expected_revision", "idempotency_key"):
        if name in body:
            envelope[name] = body[name]
    return api.dispatch(envelope)


@router.get("/pronunciation/status")
async def pronunciation_status() -> dict[str, Any]:
    """Whether this process could score a take right now. Never downloads a model.

    ``available: false`` is the honest practice-only state the Desktop shows; it is not an error.
    """
    stt = _stt()
    return {"ok": True, **stt.described()}


@router.get("/packs/intake")
async def packs_intake() -> dict[str, Any]:
    """Capability probe for the local pack intake (CB-010).

    Reports whether this backend can mint a local file grant. The Desktop shows its import
    picker only when this answers true, so a host without the door is told plainly instead of
    rendering a control that cannot work.

    ``staging_root`` is an output-only hint (where grants are expanded). The client never sends a
    path back from it: a path only enters through ``POST /packs/grant`` after the user picks it.
    """
    pack_flow = _pack_flow()
    available = callable(getattr(pack_flow, "grant_local_file", None))
    response: dict[str, Any] = {"ok": True, "available": available, "can_grant": available}
    if available:
        try:
            response["staging_root"] = str(pack_flow.staging_root())
        except Exception:  # noqa: BLE001 - a diagnostics field must not fail the probe
            logger.warning("coursebook: could not resolve the staging root for the intake probe")
    return response


@router.post("/packs/grant")
async def packs_grant(body: dict[str, Any] = Body(...)) -> Any:
    """Grant one host-chosen archive and return its ``staged_id`` (CB-010).

    This is the only door a filesystem path may enter through; the RPC contract itself never
    accepts one. ``grant_local_file`` refuses URLs, relative paths and symlinks, and the refusal
    is returned as data (HTTP 200, ``ok: false``) so the Desktop renders the reason. Anything
    else is a bug in this process, and is reported as a 500 rather than disguised as a rejection.
    """
    pack_flow = _pack_flow()
    path = body.get("path")
    if not isinstance(path, str) or not path.strip():
        return {
            "ok": False,
            "code": "PACK_REJECTED",
            "message": "a local file grant needs an absolute path",
        }
    refusals = _refusal_types()
    try:
        staged_id = pack_flow.grant_local_file(path)
    except refusals as exc:
        return {"ok": False, "code": "PACK_REJECTED", "message": _message(exc)}
    except Exception:  # noqa: BLE001 - internal failure, not a policy refusal
        logger.exception("coursebook: pack grant failed outside a policy refusal")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "code": "INTERNAL_ERROR",
                "message": "the pack grant failed; nothing was staged",
            },
        )
    return {"ok": True, "staged_id": staged_id}


@router.get("/media/{artifact_id}")
async def media_preview(artifact_id: str) -> dict[str, Any]:
    """Bounded inline preview for one visual/audio artifact.

    The Desktop renderer has a JSON-only ``ctx.rest`` door, so an image or audio player needs a
    data URL rather than a relative file link. This route is authenticated by the host's normal
    ``/api/`` middleware; it re-verifies size and sha256 before encoding, and returns a refusal as
    data so the lesson can keep its text equivalent and download handle.
    """
    media = _media()
    return media.preview_artifact(artifact_id)


@router.get("/artifacts/{handle}")
async def artifact_download(handle: str) -> Any:
    """Stream one exported pack by its expiring, session-bound handle (CB-010).

    ``artifact.get`` mints the handle; ``pack_flow.open_artifact`` re-verifies expiry, size and
    sha256 against the artifacts row before a byte leaves. The request is authenticated by the
    host's ``/api/`` auth middleware (session token or OAuth gate) — there is no token in the URL,
    and the handle never names a filesystem path. A policy refusal is a 404; an integrity
    mismatch is a 500; neither carries a path or a traceback.
    """
    pack_flow = _pack_flow()
    refusals = _refusal_types()
    try:
        path, mime, _size = pack_flow.open_artifact(handle)
    except refusals as exc:
        code = _code(exc)
        return JSONResponse(
            status_code=404 if code == "NOT_FOUND" else 500,
            content={"ok": False, "code": code, "message": _message(exc)},
        )
    except Exception:  # noqa: BLE001 - internal failure, never a traceback over the wire
        logger.exception("coursebook: artifact download failed outside a policy refusal")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "code": "INTERNAL_ERROR",
                "message": "the artifact could not be read",
            },
        )
    return FileResponse(
        path,
        media_type=mime,
        filename=_download_name(path),
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


#: Export files are written as ``<pack_id>-<version>-<digest16>.zip``; the download is named for a
#: human, so the digest suffix is dropped. Anything unexpected keeps its on-disk name.
_EXPORT_NAME = re.compile(r"^(?P<stem>.+)-[0-9a-f]{16}\.zip$")


def _download_name(path: Path) -> str:
    match = _EXPORT_NAME.match(path.name)
    return f"{match.group('stem')}.zip" if match else path.name


def _pack_flow() -> Any:
    _load_backend()
    return importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.pack_flow")


def _media() -> Any:
    _load_backend()
    return importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.media")


def _stt() -> Any:
    _load_backend()
    return importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.stt")


def _bindings() -> Any:
    _load_backend()
    return importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.bindings")


def _refusal_types() -> tuple[type[BaseException], ...]:
    """Exception types that mean "refused by policy", as opposed to a bug in this process."""
    _load_backend()
    packs = importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.packs")
    api = importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.api")
    return (packs.PackRejected, api.RpcError)


def _code(exc: BaseException) -> str:
    error = getattr(exc, "error", None)
    if isinstance(error, dict):
        return str(error.get("code") or "INTERNAL_ERROR")
    return "PACK_REJECTED"


def _message(exc: BaseException) -> str:
    """The refusal's own message. Contract errors carry it in the error object, not ``str()``."""
    error = getattr(exc, "error", None)
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return str(exc)


@router.post("/sessions/bind")
async def sessions_bind(body: dict[str, Any] = Body(...)) -> Any:
    """Bind the host's focused chat to the lesson run the Desktop just opened.

    The durable stored session id does not exist until a fresh chat's first turn, so the Desktop
    cannot send it inside ``lesson.begin`` (``cb.rpc`` is frozen at v5 and that payload has no
    session field). This seam is the write half of ``binding.get``: the Desktop arms the run it
    started, and once the chat has a stored id it asks for exactly that bind. The rule lives in
    ``coursebook.bindings`` so it is unit-testable; this route only adapts HTTP.

    Refusals are HTTP 200 ``{ok:false, code, message}`` because they are policy, not transport:
    a chat already bound to another lesson, an enrollment with an active chat, or a run that is no
    longer active. The caller renders the reason; it never retries blindly.
    """
    bindings = _bindings()
    try:
        outcome = bindings.bind_session(
            stored_session_id=body.get("stored_session_id"),
            enrollment_id=body.get("enrollment_id"),
            objective_id=body.get("objective_id"),
            lesson_run_id=body.get("lesson_run_id"),
            profile=body.get("profile"),
            runtime_session_id=body.get("runtime_session_id"),
            connection_id=body.get("connection_id"),
            cwd_fingerprint=body.get("cwd_fingerprint"),
        )
    except _refusal_types() as exc:
        return {"ok": False, "code": _code(exc), "message": _message(exc)}
    except Exception:  # noqa: BLE001 - internal failure, not a policy refusal
        logger.exception("coursebook: session bind failed outside a policy refusal")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "code": "INTERNAL_ERROR",
                "message": "the lesson chat could not be bound; nothing was written",
            },
        )
    return {"ok": True, **outcome}


@router.get("/runtime")
async def runtime() -> dict[str, Any]:
    """Small diagnostics block: what this process loaded and which contracts it reads.

    Deliberately separate from ``health.get``: it describes the *process*, not the profile's
    course state, and it is the endpoint a doctor/QA probe reads.

    ``implemented_methods`` is the registry itself (``coursebook.api.METHOD_HANDLERS``), not a
    second list. A Desktop surface that needs to know whether a frozen command can run reads this
    instead of assuming a method exists because the contract names it — which is what lets the
    client absorb a contract amendment (v2) without a code change.
    """
    api, contracts, db = _api(), _contracts(), _db()
    problems = contracts.audit_contracts()
    try:
        pin = db.single_home_pin()
        storage = {
            "single_home_flag": db.SINGLE_HOME_FLAG,
            # Process-level, not per-request: tells the Desktop half that this backend serves ONE
            # home, so it should state its scope explicitly (`?profile=` = current profile) instead
            # of letting the app guess an ambient profile that resolves to a different home.
            "single_home_host": db.is_single_home_host(),
            "single_home_pinned": pin is not None,
            "single_home_pin": str(pin) if pin is not None else None,
        }
    except Exception:  # noqa: BLE001 - diagnostics must never fail the probe
        logger.warning("coursebook: could not resolve the single-home storage pin")
        storage = {}
    return {
        "backend_package": _BACKEND_PACKAGE,
        "plugin_root": str(_PLUGIN_ROOT),
        "wire_contract": api.RPC_CONTRACT,
        "wire_version": api.RPC_CONTRACT_VERSION,
        "contract_methods": len(api.method_names()),
        "implemented_methods": list(api.implemented_methods()),
        "contract_problems": problems,
        "db_path": str(db.database_path()),
        **storage,
    }
