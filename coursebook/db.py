"""SQLite access seam for Coursebook.

The database is the single source of truth (``PREBUILD_SPEC.md`` §6). This module owns the
connection policy only; tables, migrations and transactional commands belong to the backend
kernel work package (implementer: Cinder, see ``docs/WORK_PACKAGES.md``).

Frozen rules — do not relax them in a later phase:

* one short-lived connection per unit of work, always closed;
* ``BEGIN IMMEDIATE`` for every fenced mutation, with an expected-revision compare-and-swap;
* provider calls, archive generation and long artifact writes never run inside a transaction;
* migrations are transactional and recorded in ``schema_migrations`` with a checksum.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from . import PACKAGE_ID
from .contracts import contract

#: How long a writer waits for the write lock before failing. Bounded on purpose.
BUSY_TIMEOUT_MS = 5000


class DatabaseUnavailable(RuntimeError):
    """The database cannot be opened in this process/profile."""


def db_contract() -> dict[str, Any]:
    """The authoritative table/record inventory (``cb.db``)."""
    return contract("cb.db")


def target_schema_version() -> int:
    """Schema version this build expects, read from ``cb.db``."""
    return int(db_contract()["schema_version"])


def migration_table() -> str:
    return str(db_contract()["migration_table"])


def database_path() -> Path:
    """``<hermes home>/plugin-data/coursebook/data.db`` for the *active* profile.

    Resolved per call: never cache this across a profile switch.
    """
    from plugins.plugin_storage import plugin_data_dir

    return plugin_data_dir(PACKAGE_ID) / "data.db"


def migration_files() -> list[Path]:
    """``coursebook/migrations/*.sql`` in version order (empty until the kernel package lands)."""
    directory = Path(__file__).resolve().parent / "migrations"
    if not directory.is_dir():
        return []
    return sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def connect() -> sqlite3.Connection:
    """Open the profile-scoped database with WAL, foreign keys and a bounded busy timeout."""
    from plugins.plugin_storage import plugin_db

    try:
        connection = plugin_db(PACKAGE_ID)
    except Exception as exc:  # noqa: BLE001 - surfaced as a typed failure, never swallowed
        raise DatabaseUnavailable(f"cannot open coursebook database: {exc}") from exc
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return connection


def applied_schema_version() -> int | None:
    """Highest applied migration version, or ``None`` when the database has no schema yet.

    Read-only: it never creates the database file.
    """
    path = database_path()
    if not path.exists():
        return None
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (migration_table(),)
        ).fetchone()
        if row is None:
            return None
        applied = connection.execute(f"SELECT MAX(version) AS version FROM {migration_table()}").fetchone()
    version = applied["version"] if applied is not None else None
    return int(version) if version is not None else None


def health() -> dict[str, Any]:
    """The ``health.get`` database block. Honest about an unmigrated database."""
    version = applied_schema_version()
    return {
        "ready": version is not None and version >= target_schema_version(),
        "schema_version": version,
    }
