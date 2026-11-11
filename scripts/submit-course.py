#!/usr/bin/env python3
"""Submit one exported course pack to the Coursebook store as a pull request.

This is the backend of the "Share to store" button. One command does what a person would do by
hand, and stops at the same gate:

1. **Audit** the archive with the importer's own pre-write gate (``pack_flow.validate_and_audit``):
   manifest rules, teaching minima, content hash, media bytes, presentation rules (including the
   Game-mode world kit), and the bundled-version floor. A pack that would be refused on import is
   refused here, before a branch exists.
2. **Identify** it without asking the author anything. If the pack id is already on a shelf with
   *different* bytes, the id is namespaced with the first 8 hex of its own content hash (and the
   archive is re-hashed and re-gated), so two learners can both publish "spanish-basics" without a
   collision. The same bytes again is a no-op.
3. **Place** it at ``store/packs/<pack_id>.zip`` and regenerate ``store/index.json``.
4. **Publish** one branch and one pull request whose body carries the pack id, version, mode,
   objective count, media count, world plate count, content hash and archive sha256. The owner
   merges; the pack ships with the next update.

Nothing invents metadata: every field is read from the pack, and the hashes are computed from the
bytes being submitted.

Usage:
    python3 scripts/submit-course.py course.zip --dry-run
    python3 scripts/submit-course.py course.zip
    python3 scripts/submit-course.py course.zip --no-push     # local branch only (verification)
"""
from __future__ import annotations

import argparse
import hashlib
import re
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from coursebook import archive, packs, pack_flow  # noqa: E402


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _single_root(target: Path) -> Path:
    roots = [child for child in target.iterdir() if child.is_dir()]
    if len(roots) != 1:
        raise SystemExit("the archive must carry exactly one root directory")
    return roots[0]


def _gate(directory: Path, manifest: dict[str, Any], source: str = "") -> None:
    """The importer's own pre-write gate, exactly as ``pack.import`` runs it."""
    staged = archive.StagedPack(
        staged_id="store-submission",
        directory=directory,
        manifest=manifest,
        integrity={},
        granted_from=source or str(directory),
    )
    pack_flow.validate_and_audit(staged)


def _store_index(repo: Path) -> dict[str, Any]:
    try:
        return json.loads((repo / "store" / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema": 1, "pack_count": 0, "packs": []}


def _prepare(tmp: Path, archive_path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    target = tmp / "pack"
    manifest = archive.extract_archive(archive_path, target)
    directory = _single_root(target)
    _gate(directory, manifest, str(archive_path))
    _manifest, files = archive.read_directory(directory)
    return manifest, files


def _namespaced(tmp: Path, manifest: dict[str, Any], files: dict[str, bytes]) -> tuple[dict[str, Any], Path]:
    """Rebuild under a collision-free id derived from the pack's own content hash."""
    suffix = str(manifest["content_hash"]).split(":", 1)[-1][:8]
    renamed = dict(manifest)
    renamed["pack_id"] = f"{manifest['pack_id']}-{suffix}"
    renamed = packs.with_content_hash(renamed)
    destination = tmp / "renamed.zip"
    archive.write_archive(destination, renamed, files)
    # A rewritten archive is a different file: gate it again rather than trust the rewrite.
    check = tmp / "renamed-check"
    check_manifest = archive.extract_archive(destination, check)
    _gate(_single_root(check), check_manifest, str(destination))
    return renamed, destination


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _run(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(command, capture_output=True, text=True, cwd=str(cwd))
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(command)} failed:\n{result.stdout}{result.stderr}")
    return (result.stdout or result.stderr).strip()


def _counts(manifest: dict[str, Any]) -> dict[str, Any]:
    presentation = manifest.get("presentation") or {}
    world = presentation.get("world") or {}
    return {
        "mode": str(presentation.get("mode") or "textbook"),
        "objectives": len(manifest.get("objectives") or []),
        "media": len(manifest.get("media") or []),
        "world_plates": len(world.get("assets") or []),
    }


def _version_tuple(text: Any) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in str(text or "0").split("."):
        digits = re.match(r"\d+", piece)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts) or (0,)


#: A pack may only sit on the store shelf when its licence grants redistribution. A course exported
#: for a friend says ``local_only`` on purpose; sharing it is the author's own act, so the submission
#: path rewrites the licence only when the caller says the author asked to share.
#: The author's licence id is kept; only the redistribution grant changes, and only because the
#: author themselves asked for the course to be published.
STORE_LICENSE = {"redistribution": "allowed"}


def _store_licence(manifest: dict[str, Any], redistribute: bool) -> dict[str, Any] | None:
    """Return the rewritten manifest when the licence must change, else ``None``."""
    licence = manifest.get("license") if isinstance(manifest.get("license"), dict) else {}
    redistribution = str(licence.get("redistribution") or "unset")
    if redistribution == "allowed":
        return None
    if redistribution == "forbidden":
        raise SystemExit("this pack's licence forbids redistribution; it cannot be published")
    if not redistribute:
        raise SystemExit(
            f"this pack's licence was exported for {redistribution.replace('_', ' ')} use; "
            "sharing it publishes it under an author-shared licence, so pass --share "
            "(the Share button does this when the author confirms)"
        )
    rewritten = dict(manifest)
    rewritten["license"] = {**licence, **STORE_LICENSE}
    return packs.with_content_hash(rewritten)


def submit(
    archive_path: Path,
    *,
    repo: Path = ROOT,
    remote: str = "origin",
    base: str = "master",
    dry_run: bool = False,
    push: bool = True,
    redistribute: bool = False,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cb-submit-") as temporary:
        tmp = Path(temporary)
        manifest, files = _prepare(tmp, archive_path)

        rewritten = _store_licence(manifest, redistribute)
        if rewritten is not None:
            archive_path = tmp / "licensed.zip"
            archive.write_archive(archive_path, rewritten, files)
            check = tmp / "licensed-check"
            check_manifest = archive.extract_archive(archive_path, check)
            _gate(_single_root(check), check_manifest, str(archive_path))
            manifest, files = rewritten, files

        # Identity is decided against the *base branch*, never against the checkout the author is
        # running from: a hand-edited or stale local index used to let a submission replace a
        # published pack's bytes without a version bump.
        fetched = _git(repo, "fetch", "--quiet", remote, base)
        if fetched.returncode != 0:
            raise SystemExit(
                f"could not fetch {remote}/{base}: {fetched.stderr.strip() or fetched.stdout.strip()}"
            )
        base_sha = _git(repo, "rev-parse", "FETCH_HEAD").stdout.strip()
        if not base_sha:
            raise SystemExit(f"could not resolve {remote}/{base} to build the store branch from")

        scratch = Path(tempfile.mkdtemp(prefix="cb-store-"))
        work = scratch / "repo"
        added = _git(repo, "worktree", "add", "--detach", str(work), base_sha)
        if added.returncode != 0:
            shutil.rmtree(scratch, ignore_errors=True)
            raise SystemExit(
                "sharing needs this plugin installed as a git checkout of the store repository; "
                f"nothing was written ({added.stderr.strip() or added.stdout.strip()})"
            )
        try:
            shelf = {
                str(row.get("pack_id")): row
                for row in _store_index(work).get("packs") or []
                if isinstance(row, dict)
            }
            original_id = str(manifest["pack_id"])
            existing = shelf.get(original_id)
            status = "new"
            derived_from = None
            if existing is not None:
                if str(existing.get("content_hash")) == str(manifest["content_hash"]):
                    return {
                        "status": "already_present",
                        "pack_id": original_id,
                        "pack_version": str(manifest["pack_version"]),
                        **_counts(manifest),
                        "content_hash": manifest["content_hash"],
                        "message": "the store already carries these exact bytes; nothing to submit",
                    }
                if _version_tuple(manifest["pack_version"]) > _version_tuple(
                    existing.get("pack_version")
                ):
                    # A higher version is an update: the shelf file is replaced under its own id.
                    status = "update"
                else:
                    derived_from = original_id
                    manifest, archive_path = _namespaced(tmp, manifest, files)
                    status = "renamed"
                    if str(manifest["pack_id"]) in shelf:
                        raise SystemExit(
                            f"both {original_id!r} and its namespaced form are already in the store; "
                            "bump the pack version in Coursebook and export again"
                        )

            pack_id = str(manifest["pack_id"])
            archive_sha = _sha256_file(archive_path)
            ledger: dict[str, Any] = {
                "status": status,
                "pack_id": pack_id,
                "derived_from": derived_from,
                "pack_version": manifest["pack_version"],
                "title": manifest["title"],
                **_counts(manifest),
                "content_hash": manifest["content_hash"],
                "archive_sha256": archive_sha,
                "would_write": f"store/packs/{pack_id}.zip",
            }
            if dry_run:
                ledger["dry_run"] = True
                return ledger
            ledger.update(_publish_from_worktree(
                work, archive_path, pack_id, manifest, archive_sha, ledger,
                derived_from=derived_from, base=base, remote=remote, push=push,
            ))
            return ledger
        finally:
            _git(repo, "worktree", "remove", "--force", str(work))
            shutil.rmtree(scratch, ignore_errors=True)


def _push(work: Path, remote: str, branch: str) -> tuple[subprocess.CompletedProcess[str], str]:
    """Push the store branch, forking the repository when the author has no write access.

    Most people do not own the Coursebook repository. A share has to work for them too, so a push
    refused for permissions forks the repository under the author's own account and pushes there;
    the pull request is then opened across repositories. Returns the push result and the head ref
    the pull request needs.
    """
    direct = _git(work, "push", "-u", remote, branch)
    if direct.returncode == 0:
        return direct, branch
    failure = f"{direct.stdout}\n{direct.stderr}".lower()
    if not any(word in failure for word in ("permission", "403", "denied", "not authorized")):
        return direct, branch
    slug = _repo_slug(work)
    fork = _run(["gh", "repo", "fork", slug, "--remote=false", "--clone=false"], cwd=work)
    del fork  # gh prints the created fork; the login below is the authority for the head ref
    login = _run(["gh", "api", "user", "--jq", ".login"], cwd=work)
    owner, name = slug.split("/", 1)
    fork_url = f"https://github.com/{login}/{name}.git"
    forked = _git(work, "push", "-u", fork_url, branch)
    return forked, f"{login}:{branch}"


def _publish_from_worktree(
    work: Path, archive_path: Path, pack_id: str, manifest: dict[str, Any],
    archive_sha: str, ledger: dict[str, Any], *, derived_from: str | None, base: str,
    remote: str, push: bool,
) -> dict[str, Any]:
    """Place the pack, regenerate the index, commit, push and open the pull request in `work`."""
    destination = work / "store" / "packs" / f"{pack_id}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive_path, destination)
    _run([sys.executable, str(work / "scripts" / "store_index.py")], cwd=work)
    indexed = _store_index(work)
    if not any(str(row.get("pack_id")) == pack_id for row in indexed.get("packs") or []):
        raise SystemExit(f"{pack_id} was not indexed after submission; the store is inconsistent")

    branch = f"store/{pack_id}-{manifest['pack_version']}".replace(".", "-")
    _git(work, "checkout", "-B", branch)
    _git(work, "add", "store")
    commit = _git(
        work,
        "commit",
        "-m",
        f"store: add {manifest['title']} ({pack_id} {manifest['pack_version']})\n\n"
        f"content-hash: {manifest['content_hash']}\n"
        f"archive-sha256: {archive_sha}\n"
        f"objectives: {ledger['objectives']} · media: {ledger['media']} · "
        f"world plates: {ledger['world_plates']}\n"
        f"submitted by scripts/submit-course.py",
    )
    if commit.returncode != 0:
        raise SystemExit(f"git commit failed:\n{commit.stdout}{commit.stderr}")
    ledger["branch"] = branch
    ledger["commit"] = _git(work, "rev-parse", "HEAD").stdout.strip()
    if not push:
        ledger["pushed"] = False
        return ledger

    _git(work, "push", "-u", remote, branch)
    body = (
        f"Adds **{manifest['title']}** to the Coursebook store.\n\n"
        f"| field | value |\n| --- | --- |\n"
        f"| pack id | `{pack_id}` |\n"
        + (f"| namespaced from | `{derived_from}` (id already taken by different bytes) |\n" if derived_from else "")
        + f"| version | `{manifest['pack_version']}` |\n"
        f"| mode | `{ledger['mode']}` |\n"
        f"| objectives | {ledger['objectives']} |\n"
        f"| media | {ledger['media']} |\n"
        f"| world plates | {ledger['world_plates']} |\n"
        f"| content hash | `{manifest['content_hash']}` |\n"
        f"| archive sha256 | `{archive_sha}` |\n\n"
        f"The pack passed the importer's own pre-write gate in this run, including the "
        f"presentation rules that make a Game course import with its art. Accepting this pull "
        f"request ships it with the next plugin update; `store/index.json` is regenerated from "
        f"the bytes, so the hash above is the hash a user will import."
    )
    node = _run(
        [
            "gh", "pr", "create", "--repo", _repo_slug(work), "--base", base, "--head", head,
            "--title", f"store: {manifest['title']} ({pack_id})", "--body", body,
        ],
        cwd=work,
    )
    ledger["pull_request"] = node
    return ledger


def _repo_slug(repo: Path) -> str:
    remote = _git(repo, "remote", "get-url", "origin").stdout.strip()
    for prefix in ("https://github.com/", "git@github.com:"):
        if remote.startswith(prefix):
            slug = remote[len(prefix) :]
            return slug[:-4] if slug.endswith(".git") else slug
    raise SystemExit(f"cannot derive a GitHub slug from origin {remote!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pack", type=Path, help="the exported .zip to submit")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--base", default="master")
    parser.add_argument("--dry-run", action="store_true", help="audit and identify, write nothing")
    parser.add_argument("--no-push", action="store_true", help="commit a local branch, no push/PR")
    parser.add_argument(
        "--share",
        action="store_true",
        help="publish a pack that was exported for local use, under an author-shared licence",
    )
    args = parser.parse_args(argv)
    if not args.pack.is_file():
        raise SystemExit(f"{args.pack}: not a file")
    try:
        ledger = submit(
            args.pack, repo=args.repo, remote=args.remote, base=args.base,
            dry_run=args.dry_run, push=not args.no_push, redistribute=args.share,
        )
    except (archive.PackRejected, packs.PackRejected) as exc:
        # A refused pack is a normal answer from the gate, not a crash: the button shows the reason.
        print(json.dumps({"status": "refused", "pack": str(args.pack), "reason": str(exc)}, indent=2))
        return 3
    print(json.dumps(ledger, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
