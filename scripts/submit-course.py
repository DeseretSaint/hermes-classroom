#!/usr/bin/env python3
"""Submit one exported course pack to the Coursebook store as a pull request.

This is the backend of the "Share to the store" button. It performs every step a person would do by
hand and stops at the same gate:

1. **Audit** the archive with the importer's own pre-write gate (``pack_flow.validate_and_audit``):
   manifest rules, minima, content hash, media bytes, presentation rules, bundled-version floor. A
   pack that would be refused on import is refused here, before a branch exists.
2. **Place** it at ``store/packs/<pack_id>.zip`` and rebuild ``store/index.json`` with
   ``scripts/store_index.py`` (generated, never hand-edited).
3. **Publish** a branch, push it to the fork, and open one pull request. The owner accepts it with
   the normal GitHub merge; the pack then ships with the next plugin update.

Nothing in this path invents metadata: every field the PR carries is read out of the pack's own
manifest, and the archive's sha256 is computed from the bytes being submitted.

Usage:
    python3 scripts/submit-course.py course.zip --dry-run
    python3 scripts/submit-course.py course.zip
    python3 scripts/submit-course.py course.zip --repo /path/to/clone --remote origin
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from coursebook import archive, pack_flow  # noqa: E402


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _audit(archive_path: Path) -> dict[str, Any]:
    """Run the importer's own gate on the archive; return its manifest."""
    with tempfile.TemporaryDirectory(prefix="cb-submit-") as temporary:
        target = Path(temporary) / "pack"
        manifest = archive.extract_archive(archive_path, target)
        roots = [child for child in target.iterdir() if child.is_dir()]
        if len(roots) != 1:
            raise SystemExit("the archive must carry exactly one root directory")
        staged = archive.StagedPack(
            staged_id="store-submission",
            directory=roots[0],
            manifest=manifest,
            integrity={},
            granted_from=str(archive_path),
        )
        pack_flow.validate_and_audit(staged)
        return manifest


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(command, capture_output=True, text=True, cwd=None if cwd is None else str(cwd))
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(command)} failed:\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def submit(
    archive_path: Path,
    *,
    repo: Path = ROOT,
    remote: str = "origin",
    base: str = "master",
    dry_run: bool = False,
) -> dict[str, Any]:
    manifest = _audit(archive_path)
    pack_id = str(manifest["pack_id"])
    destination = repo / "store" / "packs" / f"{pack_id}.zip"

    with tempfile.TemporaryDirectory(prefix="cb-submit-index-") as temporary:
        # Index the shelf as it will look after this submission, without touching the working tree
        # on a dry run.
        staged = Path(temporary) / "repo"
        staged.mkdir()
        (staged / "bundled").symlink_to(repo / "bundled")
        (staged / "coursebook").symlink_to(repo / "coursebook")
        (staged / "contracts").symlink_to(repo / "contracts")
        (staged / "store" / "packs").mkdir(parents=True)
        (staged / "scripts").mkdir()
        shutil.copy2(repo / "scripts" / "store_index.py", staged / "scripts" / "store_index.py")
        sys.path.insert(0, str(repo))
        for existing in sorted((repo / "store" / "packs").glob("*.zip")) if (repo / "store" / "packs").is_dir() else []:
            shutil.copy2(existing, staged / "store" / "packs" / existing.name)
        shutil.copy2(archive_path, staged / "store" / "packs" / f"{pack_id}.zip")
        preview = _run([sys.executable, str(staged / "scripts" / "store_index.py")], cwd=staged)
    if dry_run:
        return {
            "pack_id": pack_id,
            "pack_version": manifest["pack_version"],
            "title": manifest["title"],
            "objectives": len(manifest.get("objectives") or []),
            "content_hash": manifest["content_hash"],
            "archive_sha256": _sha256_file(archive_path),
            "would_write": str(destination.relative_to(repo)),
            "index_preview": preview,
            "dry_run": True,
        }
    if not destination.parent.is_dir():
        destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive_path, destination)
    _run([sys.executable, str(repo / "scripts" / "store_index.py")], cwd=repo)
    index = json.loads((repo / "store" / "index.json").read_text(encoding="utf-8"))
    entry = next((row for row in index["packs"] if row["pack_id"] == pack_id), None)
    if entry is None:
        raise SystemExit(f"{pack_id} was not indexed after submission; the store is inconsistent")

    ledger = {
        "pack_id": pack_id,
        "pack_version": manifest["pack_version"],
        "title": manifest["title"],
        "objectives": len(manifest.get("objectives") or []),
        "content_hash": manifest["content_hash"],
        "archive_sha256": entry["archive_sha256"],
        "path": str(destination.relative_to(repo)),
        "index_preview": preview,
    }
    changes = _git(repo, "status", "--porcelain", "--", "store").stdout.strip().splitlines()
    if not changes:
        raise SystemExit("the store already carries this exact pack; nothing to submit")
    branch = f"store/{pack_id}-{manifest['pack_version']}".replace(".", "-")
    _git(repo, "checkout", "-B", branch)
    _git(repo, "add", "store")
    _git(
        repo,
        "commit",
        "-m",
        f"store: add {manifest['title']} ({pack_id} {manifest['pack_version']})\n\n"
        f"content-hash: {manifest['content_hash']}\n"
        f"archive-sha256: {entry['archive_sha256']}\n"
        f"objectives: {len(manifest.get('objectives') or [])}\n"
        f"submitted by scripts/submit-course.py",
    )
    _git(repo, "push", "-u", remote, branch)
    body = (
        f"Adds **{manifest['title']}** to the Coursebook store.\n\n"
        f"| field | value |\n| --- | --- |\n"
        f"| pack id | `{pack_id}` |\n| version | `{manifest['pack_version']}` |\n"
        f"| objectives | {len(manifest.get('objectives') or [])} |\n"
        f"| mode | `{(manifest.get('presentation') or {}).get('mode', 'textbook')}` |\n"
        f"| content hash | `{manifest['content_hash']}` |\n"
        f"| archive sha256 | `{entry['archive_sha256']}` |\n\n"
        f"The pack passed the importer's own pre-write gate in this run. Accepting this pull request "
        f"ships it with the next plugin update; `store/index.json` is regenerated from the bytes, so "
        f"the hash above is the hash a user will import."
    )
    url = _run(
        [
            "gh", "pr", "create", "--repo", _repo_slug(repo), "--base", base, "--head", branch,
            "--title", f"store: {manifest['title']} ({pack_id})", "--body", body,
        ]
    )
    ledger["branch"] = branch
    ledger["pull_request"] = url
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
    parser.add_argument("pack", type=Path, help="the exported .zip / .zip to submit")
    parser.add_argument("--repo", type=Path, default=ROOT, help="checkout to commit into (default: this one)")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--base", default="master")
    parser.add_argument("--dry-run", action="store_true", help="audit and index, write no branch")
    args = parser.parse_args(argv)
    if not args.pack.is_file():
        raise SystemExit(f"{args.pack}: not a file")
    print(json.dumps(submit(args.pack, repo=args.repo, remote=args.remote, base=args.base, dry_run=args.dry_run), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
