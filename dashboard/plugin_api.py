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


@router.get("/runtime")
async def runtime() -> dict[str, Any]:
    """Small diagnostics block: what this process loaded and which contracts it reads.

    Deliberately separate from ``health.get``: it describes the *process*, not the profile's
    course state, and it is the endpoint a doctor/QA probe reads.
    """
    api, contracts, db = _api(), _contracts(), _db()
    problems = contracts.audit_contracts()
    return {
        "backend_package": _BACKEND_PACKAGE,
        "plugin_root": str(_PLUGIN_ROOT),
        "wire_contract": api.RPC_CONTRACT,
        "wire_version": api.RPC_CONTRACT_VERSION,
        "contract_problems": problems,
        "db_path": str(db.database_path()),
    }
