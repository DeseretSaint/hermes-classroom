"""SQLite access seam and migration runner for Coursebook.

The database is the single source of truth (``PREBUILD_SPEC.md`` §6, ``AUDIT.md`` R5). This module
owns the connection policy, the transaction fence and the migration runner; commands live in
:mod:`coursebook.domain`.

Frozen rules — do not relax them in a later phase:

* one short-lived connection per unit of work, always closed (``read`` / ``transaction``);
* ``BEGIN IMMEDIATE`` for every fenced mutation, with an expected-revision compare-and-swap;
* provider calls, archive generation and long artifact writes never run inside a transaction
  (:func:`active_transactions` is the observable check the tests use to prove it);
* migrations are transactional and recorded in ``schema_migrations`` with a checksum, one
  transaction per migration.

The only handle is ``plugins.plugin_storage.plugin_db("coursebook")`` (``docs/ARCHITECTURE.md``
§3). Nothing here opens a path directly.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import PACKAGE_ID
from .contracts import contract

#: How long a writer waits for the write lock before failing. Bounded on purpose.
BUSY_TIMEOUT_MS = 5000

_TX_DEPTH = 0
_TX_LOCK = threading.Lock()


class DatabaseUnavailable(RuntimeError):
    """The database cannot be opened in this process/profile."""


class SchemaDrift(RuntimeError):
    """An applied migration's checksum no longer matches the file on disk."""


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
    """``coursebook/migrations/*.sql`` in version order."""
    directory = Path(__file__).resolve().parent / "migrations"
    if not directory.is_dir():
        return []
    return sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def migration_version(path: Path) -> int:
    return int(path.name.split("_", 1)[0])


def file_checksum(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def utcnow() -> str:
    """RFC 3339 UTC with an explicit offset — the only timestamp shape Coursebook stores."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def connect() -> sqlite3.Connection:
    """Open the profile-scoped database in explicit-transaction mode, FK on and WAL.

    ``plugin_db`` already applies WAL (with the shared fallbacks), ``foreign_keys=ON`` and the
    busy timeout. Setting ``isolation_level = None`` here means *this* module decides exactly
    when a transaction starts, so ``BEGIN IMMEDIATE`` cannot land inside an implicit one.
    """
    from plugins.plugin_storage import plugin_db

    try:
        connection = plugin_db(PACKAGE_ID)
    except Exception as exc:  # noqa: BLE001 - surfaced as a typed failure, never swallowed
        raise DatabaseUnavailable(f"cannot open coursebook database: {exc}") from exc
    connection.row_factory = sqlite3.Row
    connection.isolation_level = None
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def read() -> Iterator[sqlite3.Connection]:
    """A short-lived read connection, always closed."""
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """A fenced write transaction: ``BEGIN IMMEDIATE``, commit on exit, rollback on error.

    The connection is closed in every path. ``_TX_DEPTH`` is process-wide and observable so a
    test can prove a grader/provider call ran with no transaction open.
    """
    global _TX_DEPTH
    connection = connect()
    with _TX_LOCK:
        _TX_DEPTH += 1
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.execute("COMMIT")
    except BaseException:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.OperationalError:
            # SQLite may already have rolled back (EIO, contention); the original error wins.
            pass
        raise
    finally:
        with _TX_LOCK:
            _TX_DEPTH -= 1
        connection.close()


def active_transactions() -> int:
    """Number of transactions open in this process. Used by tests and diagnostics."""
    with _TX_LOCK:
        return _TX_DEPTH


def _statements(script: str) -> list[str]:
    """Split a migration file into statements, respecting quotes and ``--`` comments.

    ``executescript`` cannot be used: it implicitly commits, which would break "one transaction
    per migration".
    """
    statements: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(script):
        char = script[index]
        if quote is None and char == "-" and script[index : index + 2] == "--":
            newline = script.find("\n", index)
            index = len(script) if newline == -1 else newline
            continue
        if quote is None and char in ("'", '"'):
            quote = char
        elif quote is not None and char == quote:
            quote = None
        if char == ";" and quote is None:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
        else:
            buffer.append(char)
        index += 1
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def applied_schema_version() -> int | None:
    """Highest applied migration version, or ``None`` when the database has no schema yet.

    Read-only: it never creates the database file.
    """
    path = database_path()
    if not path.exists():
        return None
    with read() as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (migration_table(),)
        ).fetchone()
        if row is None:
            return None
        applied = connection.execute(f"SELECT MAX(version) AS version FROM {migration_table()}").fetchone()
    version = applied["version"] if applied is not None else None
    return int(version) if version is not None else None


def migrate() -> int:
    """Apply every pending migration, one transaction per file. Idempotent.

    Returns the resulting schema version. Raises :class:`SchemaDrift` when a recorded migration's
    checksum no longer matches its file, because that means the history on disk is not the history
    that was applied.
    """
    files = migration_files()
    if not files:
        raise SchemaDrift("no migration files found; the package is incomplete")
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {migration_table()} ("
            "version INTEGER NOT NULL PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        applied = {
            int(row["version"]): str(row["checksum"])
            for row in connection.execute(f"SELECT version, checksum FROM {migration_table()}")
        }
        for path in files:
            version = migration_version(path)
            checksum = file_checksum(path)
            if version in applied:
                if applied[version] != checksum:
                    raise SchemaDrift(
                        f"migration {version} was applied with checksum {applied[version]}, file is {checksum}"
                    )
                continue
            for statement in _statements(path.read_text(encoding="utf-8")):
                connection.execute(statement)
            connection.execute(
                f"INSERT INTO {migration_table()} (version, checksum, applied_at) VALUES (?, ?, ?)",
                (version, checksum, utcnow()),
            )
            connection.execute("COMMIT")
            connection.execute("BEGIN IMMEDIATE")
        connection.execute("COMMIT")
        row = connection.execute(f"SELECT MAX(version) AS version FROM {migration_table()}").fetchone()
        return int(row["version"])
    except BaseException:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        connection.close()


def ensure_schema() -> int:
    """Migrate on first use. Returns the schema version now on disk.

    Every command calls this before touching data, so a fresh install works without a separate
    provisioning step and ``health.get`` can report ``ready`` honestly.
    """
    version = applied_schema_version()
    if version is not None and version >= target_schema_version():
        return version
    return migrate()


def recover_interrupted() -> dict[str, int]:
    """Startup reconciliation: no row may stay in a state a crashed process left it in.

    * ``attempts`` left ``pending`` never committed a verdict — they are marked ``failed`` with
      ``needs_retry``. A retry is a new attempt; the pending row is never promoted by inference.
    * ``jobs`` left ``running`` past their lease become ``interrupted_requires_retry`` so the brief
      and checkpoint survive for an edited retry (``cb.jobs`` transition_notes).
    """
    now = utcnow()
    with transaction() as connection:
        attempts = connection.execute(
            "UPDATE attempts SET state = 'failed', verdict = 'needs_retry',"
            " grading_provenance_json = json_set(grading_provenance_json, '$.recovered', 'startup')"
            " WHERE state = 'pending'"
        ).rowcount
        jobs = connection.execute(
            "UPDATE jobs SET state = 'interrupted_requires_retry', updated_at = ?"
            " WHERE state = 'running' AND (lease_expires_at IS NULL OR lease_expires_at < ?)",
            (now, now),
        ).rowcount
    return {"attempts": int(attempts), "jobs": int(jobs)}


def health() -> dict[str, Any]:
    """The ``health.get`` database block. Honest about an unmigrated database."""
    version = applied_schema_version()
    target = target_schema_version()
    return {
        "ready": version is not None and version >= target,
        "schema_version": version,
    }
