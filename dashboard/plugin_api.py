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

No module-global process state lives here: SQLite is the source of truth, and the same package
may be imported twice by different loaders in one gateway process.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
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


@router.get("/packs/intake")
async def packs_intake() -> dict[str, Any]:
    """Capability probe for the local pack intake (CB-010).

    Reports whether this backend can mint a local file grant. The Desktop shows its import
    picker only when this answers true, so a host without the door is told plainly instead of
    rendering a control that cannot work.
    """
    pack_flow = _pack_flow()
    available = callable(getattr(pack_flow, "grant_local_file", None))
    return {
        "ok": True,
        "available": available,
        "can_grant": available,
    }


@router.post("/packs/grant")
async def packs_grant(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Grant one host-chosen archive and return its ``staged_id`` (CB-010).

    This is the only door a filesystem path may enter through; the RPC contract itself never
    accepts one. ``grant_local_file`` refuses URLs, relative paths and symlinks, and the refusal
    is returned as data (HTTP 200, ``ok: false``) so the Desktop renders the reason.
    """
    pack_flow = _pack_flow()
    path = body.get("path")
    if not isinstance(path, str) or not path:
        return {"ok": False, "code": "PACK_REJECTED", "message": "a local file grant needs an absolute path"}
    try:
        staged_id = pack_flow.grant_local_file(path)
    except Exception as exc:  # noqa: BLE001 - a refused grant is data, not a transport failure
        return {"ok": False, "code": "PACK_REJECTED", "message": str(exc)}
    return {"ok": True, "staged_id": staged_id}


@router.get("/artifacts/{handle}")
async def artifact_download(handle: str) -> Any:
    """Stream one exported pack by its expiring, session-bound handle (CB-010).

    ``artifact.get`` mints the handle; ``pack_flow.open_artifact`` re-verifies expiry, size and
    sha256 against the artifacts row before a byte leaves. A filesystem path never crosses the
    wire, and the response is never cached.
    """
    pack_flow = _pack_flow()
    try:
        path, mime, _size = pack_flow.open_artifact(handle)
    except Exception as exc:  # noqa: BLE001 - shaped as a refusal, never a traceback
        return JSONResponse(status_code=404, content={"ok": False, "message": str(exc)})
    return FileResponse(
        path,
        media_type=mime,
        filename=path.name,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def _pack_flow() -> Any:
    _load_backend()
    return importlib.import_module(f"{_BACKEND_PACKAGE}.coursebook.pack_flow")


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
    return {
        "backend_package": _BACKEND_PACKAGE,
        "plugin_root": str(_PLUGIN_ROOT),
        "wire_contract": api.RPC_CONTRACT,
        "wire_version": api.RPC_CONTRACT_VERSION,
        "contract_methods": len(api.method_names()),
        "implemented_methods": list(api.implemented_methods()),
        "contract_problems": problems,
        "db_path": str(db.database_path()),
    }
