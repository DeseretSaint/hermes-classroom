"""Check and repair the installed Desktop half of the Coursebook package.

Hermes runs a unified package's Desktop half from ``<home>/desktop-plugins/<name>/plugin.js``,
not from the checkout (``hermes_cli/desktop_plugin_halves.py``). Editing or updating the
checkout therefore changes nothing on screen until that copy is refreshed. Doctor warns about
the divergence, but the warning is easy to lose in a long report and it does not name a fix.

This module is the package's own, typed version of that check:

* it compares the SHA-256 of the installed ``plugin.js`` with the package's source and prints
  exactly one command that repairs it;
* it refuses to rewrite the machine-level home (``~/.hermes``) and refuses to copy while a
  Hermes worker using that home is live — nothing is refreshed silently;
* it writes the ``.hermes-package.json`` marker the way Electron and Hermes do (``source`` is
  the Desktop *directory*, not the file), so ``hermes plugins doctor`` can pair the copy;
* it cleans Chromium ``Singleton*`` sockets left in disposable audit directories, keeping any
  whose owning process is still alive.

Run it as ``python3 -m coursebook.install_check --home <HERMES_HOME>``. Exit codes:
``0`` current, ``1`` stale or missing (the fix command is printed), ``2`` usage or setup error,
``3`` a refresh was refused (live worker, or the machine-level root).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE = "coursebook"
MARKER = ".hermes-package.json"
#: Names Chromium leaves in its ``--user-data-dir``; all three belong to the same lock.
SINGLETON_PREFIX = "Singleton"
#: Executable basenames that mean a home is in use. Matched against argv tokens, not as
#: substrings: the machine-level home is literally named ``.hermes``, so a substring match would
#: flag every editor and shell whose path mentions it.
WORKER_HINTS = ("hermes", "hermes-desktop", "electron", "gateway")


class Refused(RuntimeError):
    """A refresh was refused: live worker, machine-level home, or an unowned target."""


@dataclass(frozen=True)
class Finding:
    level: str  # "ok" | "warning" | "error"
    code: str
    message: str
    fix: str | None = None


@dataclass
class CheckReport:
    home: Path
    source: Path
    findings: list[Finding] = field(default_factory=list)
    live_pids: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(finding.level != "error" for finding in self.findings)

    @property
    def fix_command(self) -> str | None:
        for finding in self.findings:
            if finding.fix:
                return finding.fix
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mtime_ms(stat_result: os.stat_result) -> float:
    """``mtimeMs`` exactly as Node/Hermes compute it, so both writers agree on freshness."""
    seconds, nanoseconds = divmod(stat_result.st_mtime_ns, 1_000_000_000)
    return seconds * 1e3 + nanoseconds / 1e6


def desktop_source_dir(source: Path) -> Path | None:
    """The package's Desktop half, by the rule Hermes and Electron share: a ``plugin.js`` at
    the package root wins, else ``desktop/plugin.js``."""
    for candidate in (source, source / "desktop"):
        if (candidate / "plugin.js").is_file():
            return candidate
    return None


def installed_plugin(home: Path) -> Path:
    return home / "desktop-plugins" / PACKAGE / "plugin.js"


def machine_root() -> Path:
    return Path.home() / ".hermes"


def fix_command(home: Path, source: Path) -> str:
    """The one command that refreshes the installed copy for *home* from *source*.

    The machine-level home needs ``--force`` because a plain refresh refuses it: installing into
    the operator's live home is their decision, not a script's default.
    """
    command = (f"bash {_quote(str(source))}/scripts/install-local.sh "
               f"--home {_quote(str(home))} --refresh-desktop")
    try:
        if home.expanduser().resolve() == machine_root().resolve():
            command += " --force"
    except OSError:
        pass
    return command


def _quote(text: str) -> str:
    """Shell-quote a path for the one printed fix command."""
    import shlex

    return shlex.quote(text)


def _read_marker(home: Path) -> dict | None:
    try:
        marker = json.loads((home / "desktop-plugins" / PACKAGE / MARKER).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return marker if isinstance(marker, dict) else None


def live_worker_pids(home: Path, proc_root: Path | None = None) -> list[int]:
    """PIDs of Hermes/Desktop processes that are using *home*, excluding this process.

    Reads ``/proc/<pid>/cmdline`` and ``/proc/<pid>/environ``. An unreadable process (another
    user's) is not evidence of use, so it is skipped rather than counted.
    """
    root = proc_root or Path("/proc")
    home_text = str(home)
    found: list[int] = []
    if not root.is_dir():
        return found
    for entry in root.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid in (os.getpid(), os.getppid()):
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        argv = [part.decode("utf-8", "replace") for part in raw.split(b"\x00") if part]
        cmdline = " ".join(argv)
        mentions_home = home_text in cmdline
        if not mentions_home:
            try:
                environ = (entry / "environ").read_bytes().split(b"\x00")
            except OSError:
                environ = []
            mentions_home = f"HERMES_HOME={home_text}".encode() in environ
        if not mentions_home:
            continue
        if any(os.path.basename(token).lower() in WORKER_HINTS for token in argv):
            found.append(pid)
    return sorted(found)


def _scope_finding() -> Finding | None:
    """Report a declared single-home backend whose storage scope cannot be resolved.

    The flag lives in ``<home>/coursebook-single-home.env``; when it is exported, storage MUST
    resolve to that home (H-69). A backend that cannot import the host module would otherwise
    fall back to the ambient profile's store with no diagnostic, so this surfaces it as a
    finding instead.
    """
    try:
        from . import db
    except ImportError:  # run as a bare script: add the checkout root, then import normally
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from coursebook import db

    if not db.is_single_home_host():
        return None
    try:
        pin = db.single_home_pin()
    except db.StoreScopeUnresolved as exc:
        return Finding(
            "error", "SCOPE_UNRESOLVED",
            f"{db.SINGLE_HOME_FLAG} is set but the storage scope does not resolve: {exc}",
            "start the backend with the Hermes runtime on PYTHONPATH (hermes serve), or unset "
            f"{db.SINGLE_HOME_FLAG} on a multi-profile gateway")
    if pin is None:
        return Finding(
            "warning", "SCOPE_AMBIENT",
            f"{db.SINGLE_HOME_FLAG} is set but storage resolves to the active profile, not a "
            f"pinned launch home (expected only when the active scope IS the launch home)")
    seam = db.host_seam_status()
    if not seam["available"]:
        return Finding(
            "error", "HOST_SEAM_UNAVAILABLE",
            f"single-home storage is pinned to {pin}, but the host surface that opens it moved: "
            f"{seam['module']}.{seam['attribute']} — {seam['detail']} (last verified against "
            f"{seam['verified_against']})",
            "update this package for the installed Hermes build, or unset "
            f"{db.SINGLE_HOME_FLAG} on a host that already resolves the launch profile itself")
    return Finding(
        "ok", "SCOPE_PINNED",
        f"single-home storage pinned to {pin} via {seam['module']}.{seam['attribute']}")


def inspect_provisioning(source: Path, home: Path | None = None) -> list[Finding]:
    """Check that the package a *user* installs is complete and wired, not just present.

    The desktop check answers "is the copy of plugin.js on screen current". This answers the
    questions a fresh install has to get right before a course can be created at all: the bundled
    skills exist and are readable, every declared tool/hook has an implementation, every contract
    parses and the current pack version is registered, the optional/required Python dependencies
    are importable, every bundled starter pack verifies its own hash, and — when a home is given —
    the profile database is at the schema version this build speaks.

    Nothing here writes or installs. A missing optional dependency is a warning because the
    product has a typed degraded path for it; a missing skill or contract is an error because the
    generation lane cannot run without it.
    """
    findings: list[Finding] = []
    source = source.expanduser().resolve()

    # 1. Bundled skills: one directory per skill with a readable SKILL.md carrying a name.
    skills_dir = source / "skills"
    skill_dirs = sorted(child for child in skills_dir.iterdir() if child.is_dir()) if skills_dir.is_dir() else []
    if not skill_dirs:
        findings.append(Finding(
            "error", "SKILLS_MISSING",
            f"no bundled skills under {skills_dir}; the tutor/coach lanes would be unavailable"))
    for child in skill_dirs:
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            findings.append(Finding(
                "error", "SKILL_NO_DOCUMENT", f"{child.name} has no SKILL.md"))
            continue
        try:
            text = skill_md.read_text(encoding="utf-8-sig")
        except OSError as exc:
            findings.append(Finding(
                "error", "SKILL_UNREADABLE", f"{skill_md} cannot be read: {exc}"))
            continue
        if not text.lstrip().startswith("---") or "name:" not in text.split("---", 2)[1]:
            findings.append(Finding(
                "warning", "SKILL_NO_FRONTMATTER",
                f"{skill_md} has no frontmatter name; a host may register it under a path"))
    if skill_dirs and not any(finding.code.startswith("SKILL_") and finding.level == "error"
                              for finding in findings):
        findings.append(Finding(
            "ok", "SKILLS_OK", f"{len(skill_dirs)} bundled skill(s): "
            + ", ".join(child.name for child in skill_dirs)))

    # 2. Every declared tool and hook resolves to an implementation in this build.
    try:
        from .contracts import ContractError, contract, version_files
        from . import tools
    except ImportError:  # run as a bare script
        sys.path.insert(0, str(source))
        from coursebook.contracts import ContractError, contract, version_files
        from coursebook import tools
    manifest_text = (source / "plugin.yaml").read_text(encoding="utf-8") if (source / "plugin.yaml").is_file() else ""
    for declared, attribute in (
        ("coursebook_status", "status_handler"),
        ("coursebook_due", "due_handler"),
    ):
        if getattr(tools, attribute, None) is None:
            findings.append(Finding(
                "error", "TOOL_NOT_WIRED",
                f"plugin.yaml declares {declared}, but coursebook.tools has no {attribute}"))
    for hook in ("pre_llm_call", "post_llm_call", "post_tool_call"):
        if f"- {hook}" in manifest_text:
            try:
                from . import hooks as hooks_module
                if not hasattr(hooks_module, hook):
                    findings.append(Finding(
                        "warning", "HOOK_NOT_WIRED",
                        f"plugin.yaml declares {hook}, but coursebook.hooks has no such callable"))
            except ImportError:
                pass
    if not any(finding.code in ("TOOL_NOT_WIRED", "HOOK_NOT_WIRED") for finding in findings):
        findings.append(Finding("ok", "TOOLS_OK", "declared tools and hooks resolve"))

    # 3. Contracts: every document parses, and the newest pack version is registered.
    try:
        try:
            from .contracts import CONTRACT_FILES, ContractError, contract, version_files
        except ImportError:  # run as a bare script
            sys.path.insert(0, str(source))
            from coursebook.contracts import CONTRACT_FILES, ContractError, contract, version_files
        pack_version = int(contract("cb.pack")["x-contract-version"])
        known = sorted(version_files("cb.pack"))
        missing = [name for name in CONTRACT_FILES.values()
                   if not (source / "contracts" / name).is_file()]
        if missing:
            findings.append(Finding(
                "error", "CONTRACT_FILE_MISSING", f"contract file(s) missing: {missing}"))
        elif pack_version not in known:
            findings.append(Finding(
                "error", "CONTRACT_VERSION_UNREGISTERED",
                f"cb.pack current version {pack_version} is not in version_files {known}"))
        else:
            findings.append(Finding(
                "ok", "CONTRACTS_OK",
                f"{len(CONTRACT_FILES)} contract(s); cb.pack v{pack_version} of {known}"))
    except (ContractError, OSError, ValueError) as exc:
        findings.append(Finding(
            "error", "CONTRACTS_UNREADABLE", f"the contract set cannot be loaded: {exc}"))

    # 4. Optional/required Python dependencies. A missing optional one degrades a named lane.
    for module, level, lane in (
        ("jsonschema", "error", "structured grading and every contract check"),
        ("faster_whisper", "warning", "pronunciation practice (reported unavailable)"),
        ("pypdf", "warning", "syllabus import (answers PARSER_UNAVAILABLE)"),
    ):
        try:
            __import__(module)
        except Exception:  # noqa: BLE001 - a broken install is the same as a missing one here
            findings.append(Finding(
                level, "DEP_MISSING", f"{module} is not importable; {lane} cannot run",
                f"python3 -m pip install '{module}'"))
    if not any(finding.code == "DEP_MISSING" for finding in findings):
        findings.append(Finding("ok", "DEPS_OK", "declared Python dependencies import"))

    # 5. Bundled starter packs: each must verify its own manifest hash.
    packs_dir = source / "bundled" / "packs"
    verified = 0
    for pack_dir in sorted(packs_dir.iterdir()) if packs_dir.is_dir() else []:
        manifest = pack_dir / "pack.json"
        if not pack_dir.is_dir() or not manifest.is_file():
            continue
        try:
            from . import packs as packs_module
        except ImportError:
            sys.path.insert(0, str(source))
            from coursebook import packs as packs_module
        try:
            packs_module.load_manifest(manifest)
            verified += 1
        except Exception as exc:  # noqa: BLE001 - any refusal is a broken bundled pack
            findings.append(Finding(
                "error", "BUNDLED_PACK_INVALID",
                f"{pack_dir.name} does not verify: {exc}"))
    if packs_dir.is_dir() and verified:
        findings.append(Finding(
            "ok", "BUNDLED_PACKS_OK", f"{verified} bundled pack(s) verify their own hash"))

    # 6. A home that already has storage must be at this build's schema version.
    if home is not None:
        database = home.expanduser().resolve() / "plugin-data" / PACKAGE / "data.db"
        if not database.is_file():
            findings.append(Finding(
                "ok", "DB_NOT_CREATED",
                "no profile database yet; it is created on first use (migrations 0001-current)"))
        else:
            try:
                from . import db
            except ImportError:
                sys.path.insert(0, str(source))
                from coursebook import db
            try:
                import sqlite3

                connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
                try:
                    row = connection.execute(
                        "SELECT MAX(version) FROM schema_migrations"
                    ).fetchone()
                    version = int(row[0] or 0) if row is not None else 0
                finally:
                    connection.close()
                if version == int(db.DB_SCHEMA_VERSION):
                    findings.append(Finding(
                        "ok", "DB_SCHEMA_OK", f"profile database at schema v{version}"))
                elif version < int(db.DB_SCHEMA_VERSION):
                    findings.append(Finding(
                        "warning", "DB_SCHEMA_BEHIND",
                        f"profile database is at v{version}; this build migrates to "
                        f"v{db.DB_SCHEMA_VERSION} on first open"))
                else:
                    findings.append(Finding(
                        "error", "DB_SCHEMA_AHEAD",
                        f"profile database is at v{version}, newer than this build's "
                        f"v{db.DB_SCHEMA_VERSION}; downgrading would lose data"))
            except Exception as exc:  # noqa: BLE001 - an unreadable db is a real finding
                findings.append(Finding(
                    "error", "DB_UNREADABLE", f"{database} cannot be read: {exc}"))
    return findings


def inspect_install(home: Path, source: Path, *, proc_root: Path | None = None) -> CheckReport:
    """Compare the installed halves with *source*; never writes anything."""
    home = home.expanduser().resolve()
    source = source.expanduser().resolve()
    report = CheckReport(home=home, source=source)
    command = fix_command(home, source)

    agent_dir = home / "plugins" / PACKAGE
    if not agent_dir.exists():
        report.findings.append(Finding(
            "error", "AGENT_MISSING",
            f"the agent half is not installed at {agent_dir}", command))
    elif not (agent_dir / "plugin.yaml").is_file():
        report.findings.append(Finding(
            "error", "AGENT_NO_MANIFEST",
            f"{agent_dir} holds no plugin.yaml (a real directory is in the slot)", command))
    else:
        report.findings.append(Finding("ok", "AGENT_OK", f"agent half: {agent_dir}"))

    source_dir = desktop_source_dir(source)
    if source_dir is None:
        report.findings.append(Finding(
            "error", "SOURCE_NO_DESKTOP",
            f"{source} holds no desktop/plugin.js; there is nothing to install"))
        return report

    installed = installed_plugin(home)
    marker = _read_marker(home)
    if not installed.is_file():
        report.findings.append(Finding(
            "error", "DESKTOP_MISSING",
            f"the Desktop half is missing at {installed}", command))
    else:
        source_sha = sha256_file(source_dir / "plugin.js")
        installed_sha = sha256_file(installed)
        if source_sha == installed_sha:
            report.findings.append(Finding(
                "ok", "DESKTOP_CURRENT",
                f"Desktop half matches the package ({installed_sha[:12]}…)"))
        else:
            report.findings.append(Finding(
                "error", "DESKTOP_STALE",
                f"Desktop runs a stale copy of desktop/plugin.js\n"
                f"    installed: {installed_sha[:12]}…  {installed}\n"
                f"    package  : {source_sha[:12]}…  {source_dir / 'plugin.js'}\n"
                f"    the window loads the installed copy, so package edits are not on screen",
                command))

    # The marker is how Doctor pairs a copy back to its package. ``install-local.sh`` used to
    # write the plugin.js *file* here; Hermes resolves ``source`` as a directory and then never
    # finds the copy, so it cannot warn about it. Name the defect instead of hiding it.
    if installed.is_file() and marker is not None:
        try:
            recorded = Path(str(marker.get("source", "")))
        except (TypeError, ValueError):
            recorded = None
        if recorded is not None and recorded.name == "plugin.js":
            report.findings.append(Finding(
                "warning", "MARKER_NAMES_FILE",
                f"{MARKER} records plugin.js, not the Desktop directory; Doctor cannot pair "
                f"this copy (Hermes resolves 'source' as a directory)", command))
        elif recorded is not None and recorded.resolve() != source_dir.resolve():
            report.findings.append(Finding(
                "warning", "MARKER_OTHER_SOURCE",
                f"{MARKER} points at {recorded}, not {source_dir}",
                command))

    report.live_pids = live_worker_pids(home, proc_root)
    scope = _scope_finding()
    if scope is not None:
        report.findings.append(scope)
    if report.live_pids:
        pids = ", ".join(str(pid) for pid in report.live_pids)
        report.findings.append(Finding(
            "warning", "HOME_IN_USE",
            f"a Hermes worker is using this home (pid {pids}); a refresh must not copy under "
            f"a live window"))
    return report


def write_marker(target: Path, source_dir: Path, linked: bool) -> dict:
    """Write the marker in the shape Electron and Hermes read (``source`` is a directory)."""
    marker = {
        "package": PACKAGE,
        "source": str(source_dir),
        "sourceMtimeMs": mtime_ms((source_dir / "plugin.js").stat()),
        "linked": linked,
    }
    (target / MARKER).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return marker


def refresh_desktop(home: Path, source: Path, *, force: bool = False,
                    proc_root: Path | None = None, root: Path | None = None) -> Path:
    """Replace the installed Desktop copy with *source*'s, atomically, and rewrite its marker.

    Refuses the machine-level home and a home with a live worker unless *force*. Never replaces
    a marker-less real directory: that is the user's own plugin, not our copy.
    """
    home = home.expanduser().resolve()
    source = source.expanduser().resolve()
    root = (root or machine_root()).expanduser().resolve()
    if home == root and not force:
        raise Refused(
            f"refusing to rewrite the machine-level home {home}: installing there is an "
            f"operator decision (rerun with --force only if that is what you mean)")
    live = live_worker_pids(home, proc_root)
    if live and not force:
        pids = ", ".join(str(pid) for pid in live)
        raise Refused(
            f"a Hermes worker is using {home} (pid {pids}); close the window and restart the "
            f"gateway, then refresh. Use --force only to update the file on disk while a "
            f"worker keeps the old code loaded")
    source_dir = desktop_source_dir(source)
    if source_dir is None:
        raise Refused(f"{source} holds no desktop/plugin.js; there is nothing to install")

    target = home / "desktop-plugins" / PACKAGE
    target.parent.mkdir(parents=True, exist_ok=True)
    existing_marker = _read_marker(home)
    if target.exists() and existing_marker is None:
        try:
            occupied = any(target.iterdir())
        except OSError:
            occupied = True
        if occupied and not force:
            raise Refused(
                f"{target} has no {MARKER} and holds files; it is not this package's copy, so "
                f"it will not be overwritten")

    staging = Path(tempfile.mkdtemp(prefix=f".{PACKAGE}.staging-", dir=target.parent))
    staged = staging / PACKAGE
    try:
        shutil.copytree(source_dir, staged, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        agent_dir = home / "plugins" / PACKAGE
        linked = agent_dir.is_symlink() and agent_dir.resolve() == source
        write_marker(staged, source_dir, linked)
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
        os.replace(staged, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def _lock_owner_pid(lock: Path) -> int | None:
    """The PID in Chromium's ``SingletonLock`` (a symlink ``hostname-pid`` or that text)."""
    try:
        if lock.is_symlink():
            text = os.readlink(lock)
        else:
            text = lock.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    tail = text.rsplit("-", 1)[-1].strip()
    if not tail.isdigit():
        return None
    pid = int(tail)
    return pid if pid > 0 else None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def clean_stale_sockets(root: Path, *, apply: bool = True) -> list[dict]:
    """Remove Chromium ``Singleton*`` entries under disposable ``.chromium`` profiles.

    A profile whose ``SingletonLock`` names a live PID is kept, with the pid reported. Anything
    else (a dead pid, a dangling lock, no lock at all) is stale and removed. Only entries whose
    name starts with ``Singleton`` are touched, and only inside a directory named ``.chromium``.
    With ``apply=False`` nothing is deleted; the same actions are reported as ``would_remove``.
    """
    root = root.expanduser().resolve()
    actions: list[dict] = []
    try:
        profiles = sorted({path for path in root.rglob(".chromium") if path.is_dir()})
    except OSError:
        return actions
    for profile in profiles:
        try:
            entries = sorted(entry for entry in profile.iterdir()
                             if entry.name.startswith(SINGLETON_PREFIX))
        except OSError:
            continue
        if not entries:
            continue
        lock = profile / "SingletonLock"
        pid = _lock_owner_pid(lock) if lock.exists() or lock.is_symlink() else None
        if pid is not None and _pid_alive(pid):
            actions.append({"profile": str(profile), "action": "kept", "pid": pid,
                            "reason": "owning process is alive"})
            continue
        removed = []
        for entry in entries:
            if not apply:
                removed.append(entry.name)
                continue
            try:
                entry.unlink()
                removed.append(entry.name)
            except OSError as exc:
                actions.append({"profile": str(profile), "action": "failed",
                                "entry": entry.name, "reason": str(exc)})
        if removed:
            actions.append({"profile": str(profile),
                            "action": "removed" if apply else "would_remove",
                            "pid": pid, "entries": removed,
                            "reason": "stale lock" if pid is not None else "no readable owner"})
    return actions


def _default_source() -> Path:
    return Path(__file__).resolve().parent.parent


def _print_report(report: CheckReport) -> None:
    print(f"Coursebook install: {report.home}")
    print(f"  package : {report.source}")
    for finding in report.findings:
        label = {"ok": "OK  ", "warning": "WARN", "error": "FAIL"}[finding.level]
        print(f"  {label}: {finding.message}")
    print()
    if report.ok and not any(f.level == "warning" for f in report.findings):
        print("Install is current: both halves match this package.")
    elif report.ok:
        print("Install works. Review the warnings above.")
    else:
        fix = report.fix_command
        print("The installed Desktop half does not match this package.")
        if fix:
            print(f"Fix it with one command:\n  {fix}")
    if report.live_pids:
        print("A worker is live; the fix command will refuse to copy until it is closed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m coursebook.install_check",
        description="Check that a Hermes home runs this package's agent and Desktop halves.")
    parser.add_argument("--home", default=None,
                        help="HERMES_HOME to check (required unless --clean-sockets)")
    parser.add_argument("--source", default=None,
                        help="package checkout (default: the checkout holding this module)")
    parser.add_argument("--refresh-desktop", action="store_true",
                        help="replace the installed Desktop copy with the package's and rewrite "
                             "its marker (refused while a worker is live unless --force)")
    parser.add_argument("--clean-sockets", action="store_true",
                        help="remove stale Chromium Singleton* entries under the package's "
                             "disposable .chromium profiles")
    parser.add_argument("--provisioning", action="store_true",
                        help="also check what a fresh user install needs: bundled skills, declared "
                             "tools/hooks, contracts, dependencies, bundled packs and (with "
                             "--home) the profile database schema")
    parser.add_argument("--dry-run", action="store_true",
                        help="with --clean-sockets, list what would go without deleting it")
    parser.add_argument("--force", action="store_true",
                        help="allow a refresh beside a live worker or in the machine-level home")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--quiet", action="store_true", help="print only failures")
    args = parser.parse_args(argv)

    if not args.home and not args.clean_sockets and not args.provisioning:
        parser.error("--home is required unless --clean-sockets or --provisioning is given")

    home = Path(args.home).expanduser() if args.home else None
    source = Path(args.source).expanduser() if args.source else _default_source()
    if not source.is_dir():
        print(f"install-check: no such package checkout: {source}", file=sys.stderr)
        return 2
    if home is not None and not home.is_dir():
        print(f"install-check: no such home: {home}", file=sys.stderr)
        return 2

    payload: dict = {"source": str(source)}
    if home is not None:
        payload["home"] = str(home)

    socket_failures = 0
    if args.clean_sockets:
        actions = clean_stale_sockets(source, apply=not args.dry_run)
        socket_failures = sum(1 for action in actions if action["action"] == "failed")
        payload["sockets"] = actions
        if not args.json and (not args.quiet or actions):
            if not actions:
                print("No Chromium Singleton* entries found.")
            for action in actions:
                if action["action"] in ("removed", "would_remove"):
                    verb = "would remove" if action["action"] == "would_remove" else "removed"
                    print(f"{verb} {len(action['entries'])} stale Singleton* entr"
                          f"{'y' if len(action['entries']) == 1 else 'ies'} in {action['profile']}"
                          f" ({action['reason']})")
                elif action["action"] == "kept":
                    print(f"kept {action['profile']} (pid {action['pid']} alive)")
                else:
                    print(f"could not remove {action['profile']}/{action['entry']}: {action['reason']}",
                          file=sys.stderr)

    provisioning_findings: list[Finding] = []
    if args.provisioning:
        provisioning_findings = inspect_provisioning(source, home)
        payload["provisioning"] = [finding.__dict__ for finding in provisioning_findings]

    if home is None:
        if provisioning_findings:
            ok = all(finding.level != "error" for finding in provisioning_findings)
            payload["ok"] = ok
            if args.json:
                print(json.dumps(payload, indent=2))
            elif not args.quiet or not ok:
                for finding in provisioning_findings:
                    if finding.level == "ok" and args.quiet:
                        continue
                    print(f"[{finding.level}] {finding.code}: {finding.message}")
                    if finding.fix:
                        print(f"    fix: {finding.fix}")
            return 1 if (socket_failures or not ok) else 0
        if args.json:
            print(json.dumps(payload, indent=2))
        return 2 if socket_failures else 0

    if args.refresh_desktop:
        try:
            target = refresh_desktop(home, source, force=args.force)
        except Refused as exc:
            print(f"install-check: {exc}", file=sys.stderr)
            return 3
        payload["refreshed"] = str(target)
        if not args.quiet and not args.json:
            print(f"refreshed {target} from {desktop_source_dir(source)}")

    report = inspect_install(home, source)
    report.findings.extend(provisioning_findings)
    payload["findings"] = [finding.__dict__ for finding in report.findings]
    payload["ok"] = report.ok
    if args.json:
        print(json.dumps(payload, indent=2))
    elif not args.quiet or not report.ok:
        _print_report(report)
    if socket_failures:
        return 2
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess in tests
    raise SystemExit(main())
