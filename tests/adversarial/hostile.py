"""Hostile pack builders for the CB-014 adversarial pass.

Every builder produces a real file on disk. Nothing here is a mock: the attacks are handed to
the production staging path exactly as a local file grant would hand them over.
"""

from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def bundled() -> tuple[dict[str, Any], dict[str, bytes]]:
    from coursebook import archive

    source = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
    manifest, files = archive.read_directory(source)
    return copy.deepcopy(manifest), dict(files)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def rehash(manifest: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    """Recompute file hashes and the manifest content hash after a mutation."""
    from coursebook import packs

    for entry in manifest["files"]:
        data = files[str(entry["path"])]
        entry["sha256"] = _sha(data)
        entry["bytes"] = len(data)
    manifest.pop("content_hash", None)
    manifest["content_hash"] = packs.content_hash(manifest)
    return manifest


def valid_with(mutate_files: dict[str, bytes] | None = None,
               mutate_manifest=None) -> tuple[dict[str, Any], dict[str, bytes]]:
    """A structurally valid pack whose bytes may be replaced before hashes are recomputed."""
    from coursebook import packs

    manifest, files = bundled()
    if mutate_files:
        files.update(mutate_files)
    if mutate_manifest:
        mutate_manifest(manifest)
    for entry in manifest["files"]:
        data = files[entry["path"]]
        entry["sha256"] = _sha(data)
        entry["bytes"] = len(data)
    manifest.pop("content_hash", None)
    manifest["content_hash"] = packs.content_hash(manifest)
    return manifest, files


def write(destination: Path, manifest: dict[str, Any], files: dict[str, bytes]) -> Path:
    from coursebook import archive

    return archive.write_archive(destination, manifest, files)


def raw_zip(destination: Path, entries: list[tuple[str, bytes]],
            *, method: int = zipfile.ZIP_DEFLATED) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=method) as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = method
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return destination


def good_entries(manifest: dict[str, Any], files: dict[str, bytes], *,
                 root: str | None = None) -> list[tuple[str, bytes]]:
    from coursebook import packs

    root = root or f"{manifest['pack_id']}-{manifest['pack_version']}"
    entries = [(f"{root}/{path}", data) for path, data in sorted(files.items())]
    entries.append((f"{root}/{packs.root_file()}", packs.canonical_json_bytes(manifest) + b"\n"))
    return entries


def zip_with_extra(basename: str, extra: list[tuple[str, bytes]]) -> Path:
    """A real valid pack archive plus extra members appended verbatim."""
    manifest, files = bundled()
    work = ROOT / "tests" / "adversarial" / "packs"
    base = write(work / "_base.zip", manifest, files)
    destination = work / basename
    with zipfile.ZipFile(base) as source, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as out:
        for info in source.infolist():
            out.writestr(info, source.read(info.filename))
        for name, data in extra:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            out.writestr(info, data)
    return destination


def zip_with_symlink(basename: str, link_name: str, target: str) -> Path:
    manifest, files = bundled()
    work = ROOT / "tests" / "adversarial" / "packs"
    base = write(work / "_base.zip", manifest, files)
    destination = work / basename
    with zipfile.ZipFile(base) as source, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as out:
        for info in source.infolist():
            out.writestr(info, source.read(info.filename))
        info = zipfile.ZipInfo(link_name, date_time=(1980, 1, 1, 0, 0, 0))
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        out.writestr(info, target)
    return destination


def zip_bomb(basename: str, *, declared_bytes: int = 512 * 1024 * 1024) -> Path:
    """One deflated member of highly compressible bytes, appended outside the manifest."""
    manifest, files = bundled()
    work = ROOT / "tests" / "adversarial" / "packs"
    base = write(work / "_base.zip", manifest, files)
    destination = work / basename
    payload = b"\0" * declared_bytes
    with zipfile.ZipFile(base) as source, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED,
                                                         compresslevel=9) as out:
        for info in source.infolist():
            out.writestr(info, source.read(info.filename))
        info = zipfile.ZipInfo("bomb.bin", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        out.writestr(info, payload)
    return destination


def giant_file(basename: str, size: int) -> Path:
    """A structurally valid pack whose one text member exceeds the single-file bound."""
    patch_path = "content/section-01-two-ways.md"
    manifest, files = valid_with({patch_path: b"a" * size})
    work = ROOT / "tests" / "adversarial" / "packs"
    return write(work / basename, manifest, files)


def raw_validish(basename: str, *, mutate_files: dict[str, bytes] | None = None,
                 mutate_manifest=None, declared_bytes: dict[str, int] | None = None) -> Path:
    """Write a raw archive that bypasses client-side validation (the attacker crafts bytes).

    Hashes are recomputed so hash mismatch is not the thing being tested; only the server-side
    schema/bounds/active-content checks stand between this file and adopted storage.
    """
    from coursebook import packs

    manifest, files = bundled()
    if mutate_files:
        files.update(mutate_files)
    if mutate_manifest:
        mutate_manifest(manifest)
    for entry in manifest["files"]:
        data = files.get(str(entry["path"]), b"")
        entry["sha256"] = _sha(data)
        entry["bytes"] = (declared_bytes or {}).get(str(entry["path"]), len(data))
    manifest.pop("content_hash", None)
    manifest["content_hash"] = packs.content_hash(manifest)
    root = f"{manifest['pack_id']}-{manifest['pack_version']}"
    entries = [(f"{root}/{path}", data) for path, data in sorted(files.items())]
    entries.append((f"{root}/{packs.root_file()}", packs.canonical_json_bytes(manifest) + b"\n"))
    destination = ROOT / "tests" / "adversarial" / "packs" / basename
    return raw_zip(destination, entries)


def save_json(destination: Path, document: Any) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return destination
