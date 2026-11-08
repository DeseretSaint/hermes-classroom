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

The only database handle is ``plugins.plugin_storage.plugin_db("coursebook")``
(``docs/ARCHITECTURE.md`` §3). The read side (:func:`store_root`, :func:`store_exists`) resolves
``<plugin data>/coursebook`` through ``hermes_constants.get_hermes_home()`` — exactly the path
``plugin_data_dir`` returns — because ``plugin_data_dir`` ``mkdir``s on every call and a read must
never create the store it is asking about.
"""

from __future__ import annotations

import hashlib
import os
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

#: Set to ``1`` by ``scripts/install-local.sh`` for a dedicated single-home backend.
#:
#: An isolated backend serves exactly one home, but the Desktop half reports ``sharedRemote`` and
#: appends ``?profile=<launch profile>`` to every plugin request. The host's profile scope then
#: resolves ``plugins.plugin_storage`` against the *default* home (``~/.hermes``), i.e. the
#: operator's live profile — not this process's launch home. With this flag set, Coursebook pins
#: its own storage to the launch home whenever the active scope points outside that home, so the
#: pane reads the database the seeder wrote. Multi-profile hosting never sets it, and the default
#: path is byte-for-byte the host's.
SINGLE_HOME_FLAG = "HERMES_COURSEBOOK_SINGLE_HOME"

_TX_DEPTH = 0
_TX_LOCK = threading.Lock()


class DatabaseUnavailable(RuntimeError):
    """The database cannot be opened in this process/profile."""


class SchemaDrift(RuntimeError):
    """An applied migration's checksum no longer matches the file on disk."""


#: Schema version this build expects and writes. ``cb.db`` declares the same number; the
#: migration runner refuses a package whose contract and constant disagree, so a half-done bump
#: is a hard failure rather than a database two versions apart from its contract.
DB_SCHEMA_VERSION = 10


def db_contract() -> dict[str, Any]:
    """The authoritative table/record inventory (``cb.db``)."""
    return contract("cb.db")


def target_schema_version() -> int:
    """Schema version this build expects, read from ``cb.db`` and pinned by the constant."""
    declared = int(db_contract()["schema_version"])
    if declared != DB_SCHEMA_VERSION:
        raise SchemaDrift(
            f"cb.db declares schema_version {declared}, code expects {DB_SCHEMA_VERSION}"
        )
    return DB_SCHEMA_VERSION


def migration_table() -> str:
    return str(db_contract()["migration_table"])


def _within(child: Path, parent: Path) -> bool:
    """Whether ``child`` is ``parent`` or lives under it (symlinks resolved, case-normalized)."""
    try:
        child_key = os.path.normcase(str(child.expanduser().resolve(strict=False)))
        parent_key = os.path.normcase(str(parent.expanduser().resolve(strict=False)))
    except OSError:  # pragma: no cover - unresolvable path on a broken filesystem
        return False
    return child_key == parent_key or child_key.startswith(parent_key + os.sep)


def within(child: Path, parent: Path) -> bool:
    """Public containment test for paths read out of a database row.

    A stored path is data, not proof: routes that read bytes named by ``artifacts.path`` must
    check :func:`within` against the directory that path is *supposed* to live under before the
    file is opened. Symlinks are resolved first, so a link inside the root that points outside it
    is refused.
    """
    return _within(child, parent)


def is_single_home_host() -> bool:
    """Whether this process declared itself a dedicated single-home backend (the flag is set)."""
    return os.environ.get(SINGLE_HOME_FLAG, "").strip().lower() in {"1", "true", "yes"}


class StoreScopeUnresolved(RuntimeError):
    """The single-home flag is set but the launch home cannot be resolved.

    Fail closed: returning ``None`` here is indistinguishable from "not a single-home host" and
    from "the scope is already the launch home", so the caller would resolve storage against the
    ambient profile — the wrong-home failure H-69 fixed. A backend that declared one home must
    answer with an explicit error instead of silently reading or writing another home.
    """

    code = "STORE_SCOPE_UNRESOLVED"


def single_home_pin() -> Path | None:
    """The launch home to pin storage to, or None to let the host resolve it as usual.

    Only acts when :data:`SINGLE_HOME_FLAG` is set (a dedicated single-home backend). Even then
    it returns None while the active scope is the launch home or a profile inside it, so a
    gateway that really does serve several profiles keeps the host's per-profile storage.

    Under the flag a pin is REQUIRED: if the host module cannot be imported or the homes cannot
    be read, this raises :class:`StoreScopeUnresolved` rather than answering None. Callers must
    let that error surface (a health/status read reports ``STORE_SCOPE_UNRESOLVED``); they must
    not catch it and fall back to the ambient profile.
    """
    if not is_single_home_host():
        return None
    try:  # the host module is present in a gateway/tool process, absent in a bare test run
        from hermes_constants import get_hermes_home, get_process_hermes_home

        launch = Path(get_process_hermes_home())
        active = Path(get_hermes_home())
    except Exception as exc:  # noqa: BLE001 - a declared single home must not degrade silently
        raise StoreScopeUnresolved(
            f"single-home backend ({SINGLE_HOME_FLAG}=1) cannot resolve its storage scope: "
            f"{exc}. Refusing to fall back to the ambient profile's store; set HERMES_HOME to "
            f"the launch home or unset the flag on a multi-profile gateway."
        ) from exc
    return None if _within(active, launch) else launch


def store_root() -> Path:
    """``<plugin data>/`` for the active profile, resolved **without creating anything**.

    This is the read-side twin of :func:`data_root`: same resolution rules — including
    :func:`single_home_pin` — but it never calls ``plugin_data_dir()``, which ``mkdir``s on every
    call. Existence probes and other reads must use this one: a lifecycle hook or a health read
    that has found nothing must leave the filesystem exactly as it found it (``PREBUILD_SPEC.md``
    §6/§7, CB-014-R1 R1/R3).
    """
    pinned = single_home_pin()
    if pinned is not None:
        return pinned / "plugin-data" / PACKAGE_ID
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "plugin-data" / PACKAGE_ID


def data_root() -> Path:
    """``<plugin data>/`` for the active profile, resolved per call (never cached).

    Creating on purpose: every caller of this function is about to write. Reads go through
    :func:`store_root` instead.
    """
    root = store_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    """``<plugin data>/data.db`` for the *active* profile.

    Resolved per call: never cache this across a profile switch. When :func:`single_home_pin`
    applies, this is the launch home's database, not a ``?profile=`` scope that escaped it.
    """
    return data_root() / "data.db"


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

    When :func:`single_home_pin` applies, the pinned file is opened through the same host
    ``open_db`` policy with the same arguments, because ``plugin_db`` would resolve the path from
    the request's ``?profile=`` scope again.
    """
    try:
        if single_home_pin() is None:
            from plugins.plugin_storage import plugin_db

            connection = plugin_db(PACKAGE_ID)
        else:  # single-home backend: same policy, path pinned to the launch home
            from hermes_cli.sqlite_util import open_db

            connection = open_db(
                database_path(),
                db_label=f"plugin-data/{PACKAGE_ID}/data.db",
                foreign_keys=True,
                check_same_thread=False,
            )
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


def store_exists() -> bool:
    """Whether this profile has a Coursebook database file, without creating anything.

    ``False`` means "this chat is not Coursebook use" for a lifecycle hook, and "nothing has been
    provisioned yet" for a health read. It must never be confused with ``False`` from a check that
    could not run: a store that exists but cannot be read stays a hard failure, so fail-closed
    behaviour is untouched (CB-014-R1 R2).
    """
    try:
        return (store_root() / "data.db").is_file()
    except Exception:  # noqa: BLE001 - no resolvable store is an absent store, never a block
        return False


def applied_schema_version() -> int | None:
    """Highest applied migration version, or ``None`` when the database has no schema yet.

    Read-only: it never creates the directory or the file. When the file is absent it returns
    ``None`` without opening a connection (a connection would create an empty database), and when
    the directory is absent it returns ``None`` without creating it either.
    """
    path = store_root() / "data.db"
    if not path.is_file():
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

    "First use" is an explicit Coursebook action — the user opening the pane (``health.get``),
    ``course.create``, a pack, a job, any command. A chat turn is not Coursebook use, so no
    lifecycle hook calls this (CB-014-R1 R1/R5).
    """
    version = applied_schema_version()
    if version is None or version < target_schema_version():
        version = migrate()
    _repair_lesson_segments_once()
    return version


#: ``PRAGMA user_version`` marker: stored lesson text has been re-cut to the ``cb.rpc`` segment cap.
#:
#: The schema version lives in ``schema_migrations``; this marker is not a schema version, it only
#: makes the one-time data repair cost a single PRAGMA read per command instead of a full text scan
#: of ``lesson_segments``. A database that has never been repaired reads ``0``.
SEGMENT_REPAIR_MARKER = 1


def _repair_lesson_segments_once() -> int:
    """Cut already-stored teaching text over the segment cap in place (D1), once per database.

    A course imported before the cap existed keeps its rows and becomes readable without a
    re-import. Idempotent: after the marker is set this is one ``PRAGMA`` read. If the write lock is
    unavailable the repair is skipped rather than failing the caller — the marker stays unset, so
    the next command retries.
    """
    from . import segments

    try:
        with read() as connection:
            marker = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if marker >= SEGMENT_REPAIR_MARKER:
            return 0
        with transaction() as connection:
            repaired = segments.repair_stored(connection)
            connection.execute(f"PRAGMA user_version = {SEGMENT_REPAIR_MARKER}")
        return repaired
    except sqlite3.OperationalError:
        # Contention or a read-only store: never turn a repair into a failed legitimate command.
        return 0


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
