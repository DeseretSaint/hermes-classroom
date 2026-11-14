#!/usr/bin/env python3
"""Fail when a release document quotes a stale count or pin.

The release docs (README.md, docs/SUBMISSION.md, docs/M4-VISUAL-MEDIA-AUDIT.md) quote
numbers that were true on some commit. This script ties them to one machine-readable
record, docs/release-evidence.json, and re-derives everything that can be re-derived
without rendering a browser:

  1. the measured commit exists, and the recorded desktop/plugin.js sha256 is the real
     hash of that file at that commit;
  2. the recorded cb.rpc version matches WIRE_CONTRACT_VERSION in coursebook/contracts.py
     and no newer contracts/rpc.<v>.json sits on disk than the record names, and the
     recorded declared-method count matches the tree's live contracts/rpc.<v>.json;
  3. the recorded schema version matches coursebook/db.py and contracts/db.<v>.json;
  4. every document quotes the recorded values (tests, text nodes, pin, versions);
  5. no document still carries a known stale string;
  6. docs/GENERATION.md quotes the prompt labels coursebook/generation.py emits, read from
     the module rather than copied from the doc;
  7. every historical plugin pin in release-evidence.json is the real hash at the
     commit the record attributes it to;
  8. every 64-hex desktop/plugin.js sha256 a release document quotes is the module's real
     hash, verified against the commit its passage names (or against module history);
  9. optionally (default on) the suite still reports the recorded test count;
  10. optionally (--require-head) every recorded measured_commit is this checkout's HEAD and
      the recorded module pin is this tree's module, so a release cannot pass on a
      self-consistent record of an older tree.

Usage:
  python3 scripts/check-docs-truth.py              # full check, re-runs the suite
  python3 scripts/check-docs-truth.py --skip-tests # fast doc/contract lint
  python3 scripts/check-docs-truth.py --require-head  # release run: the record must be HEAD's
  python3 scripts/check-docs-truth.py --json       # machine-readable result

Exit codes: 0 every check passed, 1 at least one check failed, 2 setup error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "docs" / "release-evidence.json"

DOCS = {
    "README.md": REPO / "README.md",
    "docs/SUBMISSION.md": REPO / "docs" / "SUBMISSION.md",
    "docs/INSTALL.md": REPO / "docs" / "INSTALL.md",
    "docs/M4-VISUAL-MEDIA-AUDIT.md": REPO / "docs" / "M4-VISUAL-MEDIA-AUDIT.md",
    "docs/RELEASE-EVIDENCE.md": REPO / "docs" / "RELEASE-EVIDENCE.md",
    "docs/HARNESS-STATUS.md": REPO / "docs" / "HARNESS-STATUS.md",
}

# Prompt labels are runtime constants, not prose. The doc must name the labels the module
# actually emits, and no label the module has retired may survive as a current claim.
PROMPT_DOC = REPO / "docs" / "GENERATION.md"
PROMPT_CONSTANTS = (
    "PLAN_PROMPT_VERSION",
    "PLAN_PROMPT_VERSION_V2",
    "UNIT_SECTIONS_PROMPT_VERSION",
    "LESSON_PROMPT_VERSION",
    "VALIDATION_PROMPT_VERSION",
)
PROMPT_LABEL_RE = re.compile(
    r"\b(?:plan|lesson|validation|unit-sections)-prompt\.v[0-9]+\b"
)

# Strings that were true on an earlier commit and must not survive in the docs that
# describe the current tree. Historical rows that deliberately describe 29bede7 may
# still say "685 tests at 29bede7"; they may not quote the retired current-tree counts.
STALE = [
    ("README.md", "1648", "retired suite count (now 1779)"),
    ("README.md", "1682 tests", "retired suite count (now 1779)"),
    ("README.md", "2,050 text nodes", "retired M4 text-node count (now 2,266)"),
    ("README.md", "635b7061", "retired M4 plugin pin (now 71fc4c3f)"),
    ("README.md", "80725f6", "retired M4 plugin pin (pre-merge module)"),
    ("docs/SUBMISSION.md", "1648", "retired suite count (now 1779)"),
    ("docs/SUBMISSION.md", "1682", "retired suite count (now 1779)"),
    ("docs/SUBMISSION.md", "635b7061", "retired M4 plugin pin"),
    ("docs/SUBMISSION.md", "schema v4", "retired schema claim (now schema 10)"),
    ("docs/INSTALL.md", "cb.rpc` v7", "retired current-tree contract version (now v14)"),
    ("docs/INSTALL.md", "Migrations `0001`-`0004` applied", "retired current-tree migration set"),
    ("docs/M4-VISUAL-MEDIA-AUDIT.md", "635b7061", "retired M4 plugin pin"),
    ("docs/M4-VISUAL-MEDIA-AUDIT.md", "2,050", "retired text-node count"),
]

# (doc, needle) -> the substring that must appear on the same line for a historical mention
# to be acceptable. An unlabelled retired value still fails.
STALE_CONTEXT = {
    ("README.md", "80725f6"): "670de1b",
    ("docs/M4-VISUAL-MEDIA-AUDIT.md", "635b7061"): "previous pin",
}

# Historical pins the current docs are allowed to quote, because a row names the commit
# they belong to. Any other 40-hex string outside these must be a real commit.
HISTORICAL_SHAS = {
    "c206e1c9091400af11594a440a105cda8a6794fe3563ad15a23a10e522232463",
    "5b0b3187aab781bff3b937023d6f9bea900ab309a43080ef168f0abd2efc7301",
    "c151974a7de0fed2662e977a001127327b3c3cf96d19a54cd49b819433f935fc",
    "635b7061e6a6a3d130701614fdc43829bc2c5fa8eb9f45ee4d067bb51f68d90a",
    "416ff74f27ea38d93faa561b6f70b7650bdb94354898c6b7bc6cf7cac9e7cea7",
    "2f806531aa840e53ecd0418ea13906d88e39909e4c858ed6f1b5e6f9af6b8240",
    "80725f67bbc8569e676100f5e8b50b0da517082546df1f602722fcdf86347910",
}

failures: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(REPO), text=True, capture_output=True, **kwargs)


def git_blob_sha(path_in_commit: str, commit: str) -> str:
    shown = run(["git", "cat-file", "-p", f"{commit}:{path_in_commit}"])
    if shown.returncode != 0:
        fail(f"git cat-file failed for {commit}:{path_in_commit}: {shown.stderr.strip()}")
        return ""
    return hashlib.sha256(shown.stdout.encode()).hexdigest()


def git_blob_sha_bytes(path_in_commit: str, commit: str) -> str:
    """sha256 of a blob exactly as git stores it (no text decode/re-encode)."""
    shown = subprocess.run(
        ["git", "cat-file", "-p", f"{commit}:{path_in_commit}"],
        cwd=str(REPO),
        capture_output=True,
    )
    if shown.returncode != 0:
        return ""
    return hashlib.sha256(shown.stdout).hexdigest()


def resolve_commit(token: str) -> str:
    """Full 40-hex commit id for a short or full token, or '' when it is not a commit."""
    shown = run(["git", "rev-parse", "--verify", "--quiet", f"{token}^{{commit}}"])
    return shown.stdout.strip() if shown.returncode == 0 else ""


_PLUGIN_PIN_INDEX: dict[str, str] | None = None


def plugin_pin_index() -> dict[str, str]:
    """Every sha256 desktop/plugin.js has ever had on a reachable commit.

    Built once, lazily: it is only needed for a quoted pin whose passage names no commit
    that carries it, so an attributed pin costs one `git cat-file` and nothing else.
    """
    global _PLUGIN_PIN_INDEX
    if _PLUGIN_PIN_INDEX is not None:
        return _PLUGIN_PIN_INDEX
    index: dict[str, str] = {}
    history = run(["git", "rev-list", "--all", "--", "desktop/plugin.js"])
    for commit in history.stdout.split():
        sha = git_blob_sha_bytes("desktop/plugin.js", commit)
        if sha:
            index.setdefault(sha, commit)
    _PLUGIN_PIN_INDEX = index
    return index



def read_evidence() -> dict:
    if not EVIDENCE.exists():
        print(f"check-docs-truth: missing {EVIDENCE}", file=sys.stderr)
        raise SystemExit(2)
    try:
        return json.loads(EVIDENCE.read_text())
    except json.JSONDecodeError as exc:
        print(f"check-docs-truth: {EVIDENCE} is not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(2)


def check_measured_commit(ev: dict) -> None:
    commit = ev.get("measured_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        fail(f"measured_commit is not 40 lowercase hex: {commit!r}")
        return
    exists = run(["git", "cat-file", "-e", f"{commit}^{{commit}}"])
    if exists.returncode != 0:
        fail(f"measured_commit {commit} is not a commit in this repository")
        return
    notes.append(f"measured commit {commit} exists")

    plugin = ev.get("plugin", {})
    path = plugin.get("path", "desktop/plugin.js")
    recorded = plugin.get("sha256", "")
    actual = git_blob_sha(path, commit)
    if actual != recorded:
        fail(
            f"plugin pin mismatch: evidence says {recorded[:12]}… for {commit}:{path}, "
            f"but the commit carries {actual[:12]}…"
        )
    else:
        notes.append(f"{path} at {commit[:7]} is {recorded[:12]}…")


def live_wire_contract_version() -> int | None:
    """`WIRE_CONTRACT_VERSION` the tree actually ships, or None when the module is silent.

    The record must follow the tree. Reading the version out of `coursebook/contracts.py`
    (the way the db block reads `DB_SCHEMA_VERSION`) is what makes a stale record visible:
    before this, the gate opened whichever `contracts/rpc.v<recorded>.json` the record
    named, so a v25 record passed on a v26 tree.
    """
    api = REPO / "coursebook" / "contracts.py"
    if not api.exists():
        fail(f"missing {api.relative_to(REPO)}")
        return None
    match = re.search(r"^WIRE_CONTRACT_VERSION\s*=\s*(\d+)", api.read_text(), re.MULTILINE)
    if not match:
        fail("coursebook/contracts.py has no WIRE_CONTRACT_VERSION assignment")
        return None
    return int(match.group(1))


def newest_on_disk_wire_contract() -> int | None:
    """Highest `contracts/rpc.v<N>.json` present, or None when there are no amendments."""
    versions: list[int] = []
    for path in (REPO / "contracts").glob("rpc.v*.json"):
        match = re.fullmatch(r"rpc\.v(\d+)\.json", path.name)
        if match:
            versions.append(int(match.group(1)))
    return max(versions) if versions else None


def recorded_measured_commits(ev: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Every `measured_commit` in the record, with the dotted path that carries it.

    The record names its measurement per block (tests, rpc, db, top level), so a
    freshness check has to walk them all: a record can be internally consistent and still
    describe a tree that is several merges behind the one the gate is running in.
    """
    found: list[tuple[str, str]] = []
    for key, value in ev.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            found.extend(recorded_measured_commits(value, f"{name}."))
        elif key == "measured_commit" and isinstance(value, str):
            found.append((name, value))
    return found


def check_record_is_head(ev: dict) -> None:
    """Opt-in (`--require-head`): every recorded measurement must name this checkout's HEAD.

    The default mode verifies the record against the commits it names, which is right for a
    historical audit and exactly wrong for a release: a fully consistent record of an old
    tree passes. This mode asks the other question — is the record about the tree in front
    of you — and fails naming both commit ids.
    """
    head = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        fail("--require-head: could not read HEAD in this checkout")
        return
    checked = 0
    for name, recorded in recorded_measured_commits(ev):
        full = resolve_commit(recorded) if recorded else ""
        target = full or recorded
        checked += 1
        if target != head:
            fail(
                f"--require-head: {name} is {recorded} ({(full or recorded)[:12]}…), "
                f"but HEAD is {head} ({head[:12]}…): the record describes a stale tree"
            )
    if checked and not [f for f in failures if f.startswith("--require-head:")]:
        notes.append(f"--require-head: {checked} recorded commit(s) all name HEAD {head[:7]}")

    # The record's module pin describes a tree too. A record can name HEAD and still quote
    # the module hash of an older build, which is the same staleness in another field.
    plugin = ev.get("plugin") or {}
    recorded_pin = plugin.get("sha256", "")
    plugin_path = REPO / plugin.get("path", "desktop/plugin.js")
    try:
        plugin_label = str(plugin_path.relative_to(REPO))
    except ValueError:  # a record may name a path outside the repo; report it, never crash
        plugin_label = str(plugin_path)
    if recorded_pin:
        if not plugin_path.exists():
            fail(f"--require-head: missing {plugin_label}")
        else:
            actual_pin = hashlib.sha256(plugin_path.read_bytes()).hexdigest()
            if actual_pin != recorded_pin:
                fail(
                    f"--require-head: {plugin_label} is {actual_pin} "
                    f"({actual_pin[:12]}…), but the record pins {recorded_pin} "
                    f"({recorded_pin[:12]}…): the pin describes a stale module"
                )
            else:
                notes.append("--require-head: the recorded module pin is this tree's module")


def check_contracts(ev: dict) -> None:
    rpc = ev["rpc"]
    recorded_version = rpc["version"]
    if not isinstance(recorded_version, int) or isinstance(recorded_version, bool):
        fail(f"rpc version in the record is not an integer: {recorded_version!r}")
        return
    live_version = live_wire_contract_version()

    if live_version is not None:
        if recorded_version != live_version:
            fail(
                f"rpc contract version: evidence says cb.rpc v{recorded_version}, but "
                f"WIRE_CONTRACT_VERSION in coursebook/contracts.py is {live_version}"
            )
        else:
            notes.append(f"cb.rpc v{live_version} agrees with coursebook/contracts.py")

    newest = newest_on_disk_wire_contract()
    if newest is not None and newest > recorded_version:
        fail(
            f"contracts/rpc.v{newest}.json is newer than the recorded cb.rpc "
            f"v{recorded_version}: move the record and every doc it feeds to v{newest}"
        )

    # The method count is asserted against the tree's own contract, never the file the
    # record happens to name; the record cannot vouch for itself.
    contract_version = live_version if live_version is not None else recorded_version
    contract = REPO / "contracts" / f"rpc.v{contract_version}.json"
    if not contract.exists():
        fail(f"missing {contract.relative_to(REPO)}")
    else:
        data = json.loads(contract.read_text())
        methods: set[str] = set()
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if isinstance(node.get("methods"), dict) and isinstance(
                    node["methods"].get("properties"), dict
                ):
                    methods.update(node["methods"]["properties"].keys())
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        if len(methods) != rpc["declared_methods"]:
            fail(
                f"rpc method count: evidence says {rpc['declared_methods']}, "
                f"{contract.name} declares {len(methods)}"
            )
        else:
            notes.append(f"{contract.name} declares {len(methods)} methods")

    db = ev["db"]
    db_contract = REPO / "contracts" / f"db.v{db['version']}.json"
    if not db_contract.exists():
        fail(f"missing {db_contract.relative_to(REPO)}")
    else:
        declared = json.loads(db_contract.read_text()).get("schema_version")
        if declared != db["schema_version"]:
            fail(
                f"schema version: evidence says {db['schema_version']}, "
                f"{db_contract.name} declares {declared}"
            )
    api = (REPO / "coursebook" / "db.py").read_text()
    match = re.search(r"DB_SCHEMA_VERSION\s*=\s*(\d+)", api)
    if not match:
        fail("coursebook/db.py has no DB_SCHEMA_VERSION assignment")
    elif int(match.group(1)) != db["schema_version"]:
        fail(
            f"schema version: evidence says {db['schema_version']}, "
            f"DB_SCHEMA_VERSION is {match.group(1)}"
        )
    else:
        notes.append(f"schema version {db['schema_version']} agrees with db.py and the contract")


def required_strings(ev: dict) -> dict[str, list[tuple[str, str]]]:
    tests = ev["tests"]["ran"]
    m4 = ev["m4"]
    pin_short = ev["plugin"]["sha256"][:7]
    pin_full = ev["plugin"]["sha256"]
    return {
        "README.md": [
            (f"{tests} tests", "suite count"),
            (f"{m4['text_nodes']:,} text nodes", "M4 text-node count"),
            (pin_short, "M4 plugin pin prefix"),
            (f"{ev['rpc']['declared_methods']} declared methods", "RPC method count"),
        ],
        "docs/SUBMISSION.md": [
            (f"{tests}", "suite count"),
            (f"schema v{ev['db']['schema_version']}", "schema version"),
            (f"cb.rpc` v{ev['rpc']['version']}", "RPC contract version"),
            (pin_short, "measured plugin pin prefix"),
        ],
        "docs/INSTALL.md": [
            (f"`cb.rpc` v{ev['rpc']['version']} is loaded", "RPC contract version"),
            (f"Migrations `0001`-`{ev['db']['schema_version']:04d}` applied", "migration set"),
            (f"{ev['rpc']['declared_methods']} names", "handler count"),
        ],
        "docs/M4-VISUAL-MEDIA-AUDIT.md": [
            (pin_full, "measured plugin sha256"),
            (f"{m4['text_nodes']:,}", "text-node count"),
            (f"{m4['frames']} frames", "frame count"),
        ],
    }


def check_docs(ev: dict) -> None:
    for name, path in DOCS.items():
        if not path.exists():
            fail(f"missing {name}")
            continue
        text = path.read_text()
        for needle, why in required_strings(ev).get(name, []):
            if needle not in text:
                fail(f"{name} does not quote the current {why} ({needle!r})")
        for doc, needle, why in STALE:
            if doc != name or needle not in text:
                continue
            # A historical mention is allowed only when the same line names the commit or
            # the role that makes it historical. An unlabelled retired pin still fails.
            context = STALE_CONTEXT.get((doc, needle))
            offenders = [
                line
                for line in text.splitlines()
                if needle in line and not (context and context in line)
            ]
            if offenders:
                fail(f"{name} still contains stale string {needle!r}: {why}")
        for sha in set(re.findall(r"\b[0-9a-f]{40}\b", text)):
            if sha in HISTORICAL_SHAS:
                continue
            if run(["git", "cat-file", "-e", f"{sha}^{{commit}}"]).returncode != 0:
                fail(f"{name} cites {sha}, which is not a commit in this repository")
    notes.append("documents quote the recorded values and no stale string")


HASH64_RE = re.compile(r"\b[0-9a-f]{64}\b")
COMMIT_TOKEN_RE = re.compile(r"\b[0-9a-f]{7,40}\b")


ARTIFACT_FILE_RE = re.compile(r"\.(mp4|webm|mov|png|jpe?g|gif|json|ya?ml)\b")
MODULE_CONTEXT = ("plugin.js", "plugin pin", "module_sha256", "desktop/src")


def _is_artifact_sha(block: str, pin: str) -> bool:
    """True when a 64-hex value is an artifact hash (a film, a PNG) quoted inside a
    passage that also mentions the plugin module.

    A release table is one markdown block: the film's sha256 and the module pin can sit
    four rows apart without being the same kind of value. Treating every 64-hex in a
    block that says "desktop/plugin.js" as a module pin rejects a truthful artifact hash.
    The value is an artifact hash only when every line that carries it names a file it is
    hashing and none of them frames it as the module.
    """
    lines = [line for line in block.splitlines() if pin in line]
    if not lines:
        return False
    for line in lines:
        if any(marker in line for marker in MODULE_CONTEXT):
            return False
        if not ARTIFACT_FILE_RE.search(line):
            return False
    return True


def check_doc_plugin_pins() -> None:
    """Every 64-hex desktop/plugin.js pin a release document quotes must be the real module.

    A pin's passage (the markdown block it sits in) is the attribution scope. If the
    passage names a commit whose desktop/plugin.js hashes to the quoted value, the pin is
    attributed and verified against that commit. A passage that names no such commit (a
    pin identified by a card id or tree label instead) still has to be a real hash the
    module has carried on some reachable commit, so a mutated hex digit cannot pass as a
    historical label. Anything else is a fabricated pin and fails.

    This is the check that the commit-existence rule cannot make: a 64-hex sha256 is not a
    git object id, so `git cat-file -e <sha>^{commit}` never saw it.
    """
    checked = 0
    attributed = 0
    for name, path in DOCS.items():
        if not path.exists():
            continue
        for block in re.split(r"\n\s*\n", path.read_text()):
            if "desktop/plugin.js" not in block:
                continue
            commits: list[str] = []
            for token in COMMIT_TOKEN_RE.findall(block):
                full = resolve_commit(token)
                if full and full not in commits:
                    commits.append(full)
            for pin in sorted(set(HASH64_RE.findall(block))):
                if _is_artifact_sha(block, pin):
                    notes.append(
                        f"{name}: sha256 {pin[:8]}… is quoted as an artifact hash, not a module pin"
                    )
                    continue
                carriers = [
                    c for c in commits
                    if git_blob_sha_bytes("desktop/plugin.js", c) == pin
                ]
                if carriers:
                    checked += 1
                    attributed += 1
                    continue
                index = plugin_pin_index()
                if pin in index:
                    checked += 1
                    notes.append(
                        f"{name}: pin {pin[:8]}… names no commit in its passage; it is the "
                        f"real desktop/plugin.js hash at {index[pin][:7]}"
                    )
                    continue
                named = (
                    ", ".join(
                        f"{c[:7]} carries "
                        f"{git_blob_sha_bytes('desktop/plugin.js', c)[:8]}…"
                        for c in commits[:4]
                    )
                    or "no commit is named in the passage"
                )
                fail(
                    f"{name}: sha256 {pin[:8]}… is quoted as the desktop/plugin.js pin but "
                    f"is not that file's hash at any reachable commit ({named})"
                )
    if checked:
        notes.append(
            f"{checked} quoted desktop/plugin.js pin(s) verified "
            f"({attributed} against the commit their passage names)"
        )


def check_prompt_versions() -> None:
    """docs/GENERATION.md must quote the prompt labels coursebook/generation.py emits.

    The constants are read from the module, never copied from the doc, so a prompt bump
    cannot pass the gate with a stale table or a stale prose reference.
    """
    source = (REPO / "coursebook" / "generation.py").read_text()
    current: dict[str, str] = {}
    for name in PROMPT_CONSTANTS:
        match = re.search(rf"^{name}\s*=\s*\"([^\"]+)\"", source, re.MULTILINE)
        if not match:
            fail(f"coursebook/generation.py has no {name} assignment")
            continue
        current[name] = match.group(1)

    if not PROMPT_DOC.exists():
        fail(f"missing {PROMPT_DOC.relative_to(REPO)}")
        return
    text = PROMPT_DOC.read_text()
    for name, label in current.items():
        if label not in text:
            fail(
                f"docs/GENERATION.md does not quote {name} ({label!r}) from "
                "coursebook/generation.py"
            )

    documented = set(PROMPT_LABEL_RE.findall(text))
    retired = documented - set(current.values())
    for label in sorted(retired):
        fail(
            f"docs/GENERATION.md names {label!r}, which no prompt constant emits; "
            f"the current labels are {sorted(set(current.values()))}"
        )
    if current and not retired:
        notes.append(
            "GENERATION.md prompt labels match the generation constants "
            f"({', '.join(sorted(set(current.values())))})"
        )


def check_historical_pins(ev: dict) -> None:
    for entry in ev.get("historical_plugin_pins", []):
        commit = entry["commit"]
        expected = entry["sha256"]
        actual = git_blob_sha(entry.get("path", "desktop/plugin.js"), commit)
        if not actual.startswith(expected[:8]):
            fail(
                f"historical pin {expected[:8]}… is attributed to {commit[:7]}, "
                f"but that commit carries {actual[:8]}…"
            )
    if ev.get("historical_plugin_pins"):
        notes.append("historical plugin pins match their attributed commits")


def run_suite(ev: dict) -> None:
    print("check-docs-truth: running the suite (use --skip-tests to skip)…", file=sys.stderr)
    # Some suite tests spawn helpers that inherit the parent's file descriptors. Capturing
    # through a pipe would then wait for EOF that never arrives; a temp file has no such
    # coupling, so the suite can be read after it exits.
    import tempfile

    with tempfile.TemporaryFile("w+") as sink:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=str(REPO),
            stdout=sink,
            stderr=subprocess.STDOUT,
        )
        sink.seek(0)
        output = sink.read()
    match = re.search(r"Ran (\d+) tests?", output)
    if not match:
        fail("could not read a test count from the suite output")
        return
    ran = int(match.group(1))
    if ran != ev["tests"]["ran"]:
        fail(
            f"suite count: evidence says {ev['tests']['ran']}, the suite ran {ran}. "
            "Re-measure, then update docs/release-evidence.json and every document that quotes it."
        )
    elif proc.returncode != 0:
        fail("the suite reported the recorded count but did not pass")
    else:
        notes.append(f"suite ran {ran} tests and passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true", help="do not run the suite")
    parser.add_argument(
        "--require-head",
        action="store_true",
        help="also fail when any recorded measured_commit is not this checkout's HEAD "
        "(release runs; the default stays a historical audit of the commits named)",
    )
    parser.add_argument("--json", action="store_true", help="print a JSON result")
    args = parser.parse_args()

    if run(["git", "rev-parse", "--is-inside-work-tree"]).returncode != 0:
        print("check-docs-truth: not a git checkout", file=sys.stderr)
        return 2

    ev = read_evidence()
    check_measured_commit(ev)
    if args.require_head:
        check_record_is_head(ev)
    check_contracts(ev)
    check_docs(ev)
    check_doc_plugin_pins()
    check_prompt_versions()
    check_historical_pins(ev)
    if not args.skip_tests:
        run_suite(ev)

    result = {"ok": not failures, "failures": failures, "notes": notes}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for note in notes:
            print(f"  ok  {note}")
        for problem in failures:
            print(f"  FAIL {problem}")
        print(
            "docs-truth: PASS"
            if not failures
            else f"docs-truth: FAIL ({len(failures)} problem(s))"
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
