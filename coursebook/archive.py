"""Bounded archive reading, hostile-input rejection, staging and atomic adopt.

A pack archive is untrusted bytes. This module is the only code that opens one. It enforces,
in this order and before anything reaches adopted storage:

* a real filesystem path supplied by a host file grant — never a ``file://`` URL, never a path
  from the wire (``PREBUILD_SPEC.md`` §12);
* one root directory, normalized unique relative paths, no links/devices/directories-as-files,
  no absolute paths, no ``..``, no backslashes, no control characters, no case-folded duplicates;
* entry-count, single-file, total-expanded and per-entry compression-ratio bounds from
  :func:`coursebook.packs.limits`;
* manifest schema + teaching minima + content hash against the extracted bytes;
* magic-byte MIME validation against the declared MIME, Unicode-validated text, and active
  content (HTML/SVG/script/PDF-JS/remote images) rejected outright;
* staging outside adopted storage, full audit, then a single atomic rename into the library.

A rejected import removes its staging directory and adopts nothing. Interrupted staging is
reconciled on startup by :meth:`StagingArea.reconcile`.

**Staging transport decision (open question 3 in docs/CONTRACTS.md).** The RPC payload carries
only a ``staged_id`` minted by this process. A host that has a local file picker calls
:meth:`StagingArea.grant_local_file` with the chosen path; that is the *only* way a path enters
the pack pipeline. A remote caller has no method that accepts a path, and a stored
``file://``-style string is refused even if one is passed to the grant. This is the explicit
local file-grant flow, not an invented upload route.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import stat
import tempfile
import time
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from . import packs
from .packs import (
    MEDIA_MIME_TYPES,
    PackRejected,
    canonical_json_bytes,
    content_hash,
    file_sha256,
    load_manifest,
    root_file,
    validate_minima,
)

#: Only these zip methods are understood. No BZIP2/LZMA surprises, no stored-plus-encrypted.
ALLOWED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})

#: Expanded:compressed ceiling per entry and for the archive as a whole.
MAX_COMPRESSION_RATIO = 200

#: Slack for directory entries on top of ``max_files``.
DIRECTORY_SLACK = 64

#: A path segment set that cannot escape, and matches the contract's path shape.
_MEMBER = re.compile(r"^[A-Za-z0-9._-]+$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

_TEXT_MIMES = frozenset({"text/markdown", "text/plain", "application/json", "text/html"})

_ACTIVE_MARKUP = re.compile(
    r"(?is)<\s*(script|iframe|object|embed|svg|style|img|video|audio|source|link|meta|form|base|math)\b"
    r"|javascript\s*:"
    r"|vbscript\s*:"
    r"|data\s*:\s*(text/html|image/svg\+xml|application/xhtml\+xml)"
    r"|\son[a-z]+\s*="
)
_REMOTE_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*(?:https?:)?//", re.IGNORECASE)

#: PRINT-2 (t_6418b9dd): cb.pack v4 admits ``text/html`` for the four print roles. A print
#: document is static — one sheet of type and geometry — so the archive refuses the constructs
#: that would make it executable or fetch anything when the print path opens it. ``<style>`` and
#: inline ``<svg>`` stay legal: they are the page. ``<link>``, ``<script>``, frames, forms and
#: event handlers do not.
_HTML_ACTIVE = re.compile(
    r"(?is)<\s*(script|iframe|object|embed|form|base|link|video|audio|source|math)\b"
    r"|javascript\s*:"
    r"|vbscript\s*:"
    r"|data\s*:\s*(text/html|image/svg\+xml|application/xhtml\+xml)"
    r"|\son[a-z]+\s*="
)

_PDF_ACTIVE = (
    b"/JavaScript",
    b"/JS",
    b"/Launch",
    b"/EmbeddedFile",
    b"/OpenAction",
    b"/AA",
    b"/RichMedia",
    b"/XFA",
    b"/Encrypt",
)


# ── MIME validation ─────────────────────────────────────────────────────────


def _looks_like_mp3(data: bytes) -> bool:
    if data[:3] == b"ID3":
        return True
    return len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def detect_mime(data: bytes) -> str | None:
    """Magic-byte detection for the MIME types ``cb.pack`` allows. ``None`` if unknown."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:4] == b"OggS":
        return "audio/ogg"
    if _looks_like_mp3(data):
        return "audio/mpeg"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _decode_text(path: str, data: bytes) -> str:
    if b"\x00" in data:
        raise PackRejected(f"{path!r}: text file contains a NUL byte (binary or disguised content)")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackRejected(f"{path!r}: text file is not valid UTF-8: {exc}") from exc


def verify_mime(path: str, declared: str, data: bytes) -> None:
    """Reject a declared MIME the bytes do not support, and active content inside text/PDF."""
    if declared not in packs.FILE_MIME_TYPES:
        raise PackRejected(f"{path!r}: MIME {declared!r} is not allowed by cb.pack")
    detected = detect_mime(data)
    if detected is not None:
        if declared != detected:
            raise PackRejected(f"{path!r}: bytes are {detected} but the manifest declares {declared}")
    elif declared not in _TEXT_MIMES:
        raise PackRejected(f"{path!r}: bytes do not match the declared MIME {declared}")

    if declared in ("text/markdown", "text/plain"):
        text = _decode_text(path, data)
        if declared == "text/markdown":
            match = _ACTIVE_MARKUP.search(text)
            if match:
                raise PackRejected(f"{path!r}: active markup {match.group(0)!r} is not allowed in markdown")
            if _REMOTE_IMAGE.search(text):
                raise PackRejected(f"{path!r}: markdown embeds a remote image; packs render no remote media")
    elif declared == "application/json":
        text = _decode_text(path, data)
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise PackRejected(f"{path!r}: declared JSON does not parse: {exc}") from exc
    elif declared == "application/pdf":
        for marker in _PDF_ACTIVE:
            if marker in data:
                raise PackRejected(f"{path!r}: PDF contains active/embedded content marker {marker!r}")
    elif declared == "text/html":
        text = _decode_text(path, data)
        match = _HTML_ACTIVE.search(text)
        if match:
            raise PackRejected(f"{path!r}: a print document may not carry active content {match.group(0)!r}")


# ── Path normalization ──────────────────────────────────────────────────────


def normalize_member(name: str) -> str:
    """Return a safe relative member path or raise. Directory entries keep their trailing slash."""
    if not isinstance(name, str) or not name:
        raise PackRejected("archive contains an empty member name")
    if "\\" in name:
        raise PackRejected(f"archive member {name!r} contains a backslash")
    if name.startswith("/"):
        raise PackRejected(f"archive member {name!r} is an absolute path")
    if "://" in name or ":" in name.split("/")[0]:
        raise PackRejected(f"archive member {name!r} looks like a URL or drive path")
    if _CONTROL.search(name):
        raise PackRejected(f"archive member {name!r} contains a control character")
    if len(name) > 500:
        raise PackRejected("archive member name is longer than 500 characters")
    if unicodedata.normalize("NFC", name) != name:
        raise PackRejected(f"archive member {name!r} is not Unicode NFC; duplicate-equivalent names are refused")
    is_dir = name.endswith("/")
    body = name[:-1] if is_dir else name
    segments = body.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise PackRejected(f"archive member {name!r} has an empty, '.' or '..' segment")
    for segment in segments:
        if not _MEMBER.match(segment):
            raise PackRejected(f"archive member {name!r} has a segment outside [A-Za-z0-9._-]")
        if segment.startswith(".") and segment not in (".",):
            # dotfiles are legal in general, but a pack has no reason to hide content
            raise PackRejected(f"archive member {name!r} uses a hidden path")
    return name


# ── Archive reading ────────────────────────────────────────────────────────


def _open_zip(path: Path) -> zipfile.ZipFile:
    if path.is_symlink():
        raise PackRejected("pack archive must not be a symbolic link")
    if not path.is_file():
        raise PackRejected(f"pack archive is not a regular file: {path}")
    if path.suffix.lower() != ".zip":
        raise PackRejected(f"pack archive must have a .zip suffix, got {path.suffix!r}")
    try:
        return zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise PackRejected(f"pack archive is unreadable: {exc}") from exc


def _check_member(
    info: zipfile.ZipInfo, *, count: int, total: int, members: int | None = None
) -> None:
    maximum = packs.limits()
    if count > maximum["max_files"] + DIRECTORY_SLACK:
        raise PackRejected(f"archive declares more than {maximum['max_files']} files")
    # Directory entries are not files, but they are not free either: a 17 MB archive of 100 000
    # empty directories used to be accepted and cost ~136 MB of RSS before any pack work began.
    if members is not None and members > maximum["max_files"] * 4:
        raise PackRejected(
            f"archive declares more than {maximum['max_files'] * 4} entries (files and directories)"
        )
    if info.flag_bits & 0x1:
        raise PackRejected(f"archive member {info.filename!r} is encrypted")
    if info.compress_type not in ALLOWED_COMPRESSION:
        raise PackRejected(f"archive member {info.filename!r} uses unsupported compression {info.compress_type}")
    mode = info.external_attr >> 16
    if mode:
        file_type = stat.S_IFMT(mode)
        if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise PackRejected(f"archive member {info.filename!r} is a link or device, not a regular file")
    if info.is_dir():
        return
    if info.file_size > maximum["max_single_file_bytes"]:
        raise PackRejected(
            f"archive member {info.filename!r} expands to {info.file_size} bytes, over the "
            f"{maximum['max_single_file_bytes']}-byte limit"
        )
    if total + info.file_size > maximum["max_expanded_bytes"]:
        raise PackRejected(f"archive expands beyond the {maximum['max_expanded_bytes']}-byte limit")
    if info.file_size and not info.compress_size:
        raise PackRejected(f"archive member {info.filename!r} declares content with zero compressed bytes")
    if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
        raise PackRejected(
            f"archive member {info.filename!r} has a {info.file_size // info.compress_size}:1 expansion ratio"
        )


def extract_archive(source: str | Path, destination: str | Path) -> dict[str, Any]:
    """Validate and extract one pack archive into a fresh directory. Returns its manifest.

    The destination must not exist. On any failure the partially written tree is removed before
    the error propagates, so a rejection leaves no residue.
    """
    archive_path = Path(source)
    target = Path(destination)
    if target.exists():
        raise PackRejected(f"staging destination already exists: {target}")
    maximum = packs.limits()
    counter = {"files": 0, "bytes": 0}
    roots: set[str] = set()
    seen: dict[str, str] = {}

    target.mkdir(parents=True, mode=0o700)
    try:
        with _open_zip(archive_path) as archive:
            if archive_path.stat().st_size > maximum["max_expanded_bytes"]:
                raise PackRejected("pack archive file is larger than the expanded-byte limit")
            infos = archive.infolist()
            if not infos:
                raise PackRejected("pack archive is empty")
            names: list[str] = []
            for info in infos:
                name = normalize_member(info.filename)
                names.append(name)
                root = name.split("/", 1)[0]
                roots.add(root)
                folded = name.casefold()
                if folded in seen:
                    raise PackRejected(f"archive members {seen[folded]!r} and {name!r} collide by case")
                seen[folded] = name
                counter["members"] = counter.get("members", 0) + 1
                if not info.is_dir():
                    counter["files"] += 1
                _check_member(
                    info,
                    count=counter["files"],
                    total=counter["bytes"],
                    members=counter["members"],
                )
                if not info.is_dir():
                    counter["bytes"] += info.file_size
            if len(roots) != 1:
                raise PackRejected(f"pack archive must contain exactly one root directory, found {sorted(roots)}")
            root_name = next(iter(roots))
            for name in names:
                body = name.rstrip("/")
                if body != root_name and "/" not in body:
                    raise PackRejected("pack archive has entries outside its single root directory")

            for info in infos:
                if info.is_dir():
                    continue
                relative = str(Path(info.filename))
                out_path = target / relative
                if target.resolve() not in out_path.resolve().parents:
                    raise PackRejected(f"archive member {info.filename!r} escapes the staging directory")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info) as source_file, out_path.open("xb") as out_file:
                    while True:
                        chunk = source_file.read(65536)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > maximum["max_single_file_bytes"]:
                            raise PackRejected(f"archive member {info.filename!r} grew past the per-file limit")
                        out_file.write(chunk)
                if written != info.file_size:
                    raise PackRejected(
                        f"archive member {info.filename!r} produced {written} bytes, header declared {info.file_size}"
                    )

        root_dir = target / next(iter(roots))
        manifest_path = root_dir / root_file()
        if not manifest_path.is_file():
            raise PackRejected(f"pack archive has no {root_file()} at its root")
        manifest = load_manifest(manifest_path)
        _verify_extracted(root_dir, manifest)
        return manifest
    except PackRejected:
        shutil.rmtree(target, ignore_errors=True)
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise PackRejected(f"pack archive could not be read: {exc}") from exc


def _verify_extracted(root: Path, manifest: Mapping[str, Any]) -> None:
    """Hash, size and MIME verification of extracted content, then the teaching audit."""
    declared = {str(entry["path"]): entry for entry in manifest["files"]}
    actual: dict[str, Path] = {}
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise PackRejected(f"extracted tree contains a symbolic link: {candidate.name}")
        if candidate.is_file():
            relative = candidate.relative_to(root).as_posix()
            if relative != root_file():
                actual[relative] = candidate
    if set(actual) != set(declared):
        missing = sorted(set(declared) - set(actual))
        extra = sorted(set(actual) - set(declared))
        raise PackRejected(f"archive content does not match the manifest: missing {missing}, undeclared {extra}")
    for path, entry in declared.items():
        data = actual[path].read_bytes()
        if len(data) != int(entry["bytes"]):
            raise PackRejected(f"{path!r}: {len(data)} bytes, manifest declares {entry['bytes']}")
        if file_sha256(data) != str(entry["sha256"]):
            raise PackRejected(f"{path!r}: sha256 does not match the manifest")
        verify_mime(path, str(entry["mime"]), data)
    validate_minima(manifest)
    problems = packs.audit_bundle(root)
    if problems:
        raise PackRejected("pack content audit failed: " + "; ".join(problems))


# ── Archive writing ────────────────────────────────────────────────────────


def write_archive(destination: str | Path, manifest: Mapping[str, Any], files: Mapping[str, bytes]) -> Path:
    """Write a deterministic pack archive: one root, sorted entries, fixed timestamps."""
    packs.validate_manifest(manifest)
    packs.validate_minima(manifest)
    packs.verify_content_hash(manifest)
    declared = {str(entry["path"]): entry for entry in manifest["files"]}
    if set(files) != set(declared):
        raise PackRejected("archive bytes must match the manifest file list exactly")
    for path, data in files.items():
        if file_sha256(data) != str(declared[path]["sha256"]):
            raise PackRejected(f"{path!r}: bytes do not match the declared hash")

    out = Path(destination)
    if out.suffix.lower() != ".zip":
        raise PackRejected("exported pack must be a .zip archive")
    out.parent.mkdir(parents=True, exist_ok=True)
    root = f"{manifest['pack_id']}-{manifest['pack_version']}"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(f"{root}/{path}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[path])
        info = zipfile.ZipInfo(f"{root}/{root_file()}", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, canonical_json_bytes(manifest) + b"\n")
    return out


def read_directory(directory: str | Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Read a bundled/unpacked pack directory and apply the same checks as an archive."""
    root = Path(directory)
    if root.is_symlink():
        raise PackRejected("pack directory must not be a symbolic link")
    manifest = load_manifest(root / root_file())
    _verify_extracted(root, manifest)
    files: dict[str, bytes] = {}
    for entry in manifest["files"]:
        files[str(entry["path"])] = (root / str(entry["path"])).read_bytes()
    return manifest, files


# ── Staging and adopt ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class StagedPack:
    """A validated pack held outside adopted storage, ready to preview or import."""

    staged_id: str
    directory: Path
    manifest: dict[str, Any]
    integrity: dict[str, Any]
    granted_from: str = ""
    created_at: float = field(default_factory=time.time)

    @property
    def content_hash(self) -> str:
        return str(self.manifest["content_hash"])


class PackLibrary:
    """Adopted pack storage. Identity is ``pack_id`` + immutable version + content hash."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.packs_dir = self.root / "packs"
        self.index_path = self.root / "index.json"

    def _records(self) -> list[dict[str, Any]]:
        try:
            document = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return list(document.get("packs", []))

    def _write_records(self, records: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"packs": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.index_path)

    def list(self) -> list[dict[str, Any]]:
        return self._records()

    def path_for(self, pack_id: str, version: str) -> Path:
        if not _MEMBER.match(pack_id) or not _VERSION.match(version):
            raise PackRejected(f"unsafe pack identity {pack_id!r} {version!r}")
        return self.packs_dir / pack_id / version

    def adopt(self, staged: StagedPack, *, source: str = "local") -> dict[str, Any]:
        """Atomically adopt a staged pack. Re-adopting the same content is a no-op."""
        destination = self.path_for(str(staged.manifest["pack_id"]), str(staged.manifest["pack_version"]))
        records = self._records()
        for record in records:
            if record["pack_id"] == staged.manifest["pack_id"] and record["version"] == staged.manifest["pack_version"]:
                if record["manifest_hash"] != staged.content_hash:
                    raise PackRejected(
                        f"pack {staged.manifest['pack_id']} {staged.manifest['pack_version']} is already "
                        "adopted with different content; a published version is immutable"
                    )
                shutil.rmtree(staged.directory, ignore_errors=True)
                _drop_staging(staged)
                return {**record, "duplicate": True}

        if destination.exists():
            existing = load_manifest(destination / root_file())
            if content_hash(existing) != staged.content_hash:
                raise PackRejected("adopted directory holds different content under the same version; refusing to overwrite")
            record = self._record(staged, destination, source, duplicate=True)
            records = [item for item in records if not _same_identity(item, record)] + [record]
            self._write_records(records)
            shutil.rmtree(staged.directory, ignore_errors=True)
            _drop_staging(staged)
            return record

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(staged.directory, destination)
        except OSError:
            # Different filesystem: build beside the destination, then rename atomically.
            partial = destination.with_name(destination.name + ".partial")
            shutil.rmtree(partial, ignore_errors=True)
            shutil.copytree(staged.directory, partial)
            os.replace(partial, destination)
            shutil.rmtree(staged.directory, ignore_errors=True)

        record = self._record(staged, destination, source, duplicate=False)
        records = [item for item in records if not _same_identity(item, record)] + [record]
        self._write_records(records)
        _drop_staging(staged)
        return record

    def _record(self, staged: StagedPack, destination: Path, source: str, *, duplicate: bool) -> dict[str, Any]:
        return {
            "pack_id": str(staged.manifest["pack_id"]),
            "version": str(staged.manifest["pack_version"]),
            "manifest_hash": staged.content_hash,
            "license": staged.manifest["license"],
            "derived_from": staged.manifest.get("derived_from"),
            "source": source,
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "state": "installed",
            "revision": 0,
            "directory": str(destination),
            "duplicate": duplicate,
        }

    def read(self, pack_id: str, version: str) -> tuple[dict[str, Any], dict[str, bytes]]:
        directory = self.path_for(pack_id, version)
        if not directory.is_dir():
            raise PackRejected(f"pack {pack_id} {version} is not in the library")
        return read_directory(directory)


def _same_identity(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left.get("pack_id") == right.get("pack_id") and left.get("version") == right.get("version")


_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$")


def _drop_staging(staged: StagedPack) -> None:
    """Remove the staging envelope after its content was adopted or discarded."""
    parent = staged.directory.parent
    if parent.name == staged.staged_id:
        shutil.rmtree(parent, ignore_errors=True)


class StagingArea:
    """Granted-file staging outside adopted storage, with TTL and startup reconciliation."""

    def __init__(self, root: str | Path, *, ttl_seconds: int = 3600, clock=time.time) -> None:
        self.root = Path(root)
        self.ttl_seconds = int(ttl_seconds)
        self.clock = clock
        self._grants: dict[str, dict[str, Any]] = {}
        self._staged: dict[str, StagedPack] = {}

    def grant_local_file(self, path: str | Path) -> str:
        """Register an explicit host file grant and return its ``staged_id``.

        Only a host adapter that actually holds a local file (a native picker, a bundled pack
        installer, a CLI argument) calls this. The returned id is the only thing that may cross
        the RPC boundary. ``file://`` strings, relative paths and symlinks are refused.
        """
        raw = os.fspath(path)
        if not isinstance(raw, str):
            raise PackRejected("local file grant requires a filesystem path")
        if "://" in raw:
            raise PackRejected("local file grant requires a path, not a URL")
        candidate = Path(raw)
        if not candidate.is_absolute():
            raise PackRejected("local file grant requires an absolute path")
        if candidate.is_symlink():
            raise PackRejected("local file grant must not be a symbolic link")
        if not candidate.is_file():
            raise PackRejected(f"local file grant is not a regular file: {candidate}")
        staged_id = "stg-" + secrets.token_hex(16)
        self._grants[staged_id] = {
            "path": str(candidate),
            "expires_at": self.clock() + self.ttl_seconds,
        }
        return staged_id

    def stage_directory(self, directory: str | Path) -> str:
        """Stage one bundled/unpacked pack directory and return its ``staged_id``.

        H-196: the bundled installer. The caller names a directory it already resolved; this method
        takes no path over the wire. The directory is read through :func:`read_directory`, which
        validates the manifest and re-hashes every declared file, and only the declared files (plus
        the manifest) are copied into staging — an undeclared file beside the pack is never adopted.
        The result is cached on this instance exactly like a granted archive, so ``pack.import`` can
        consume it once.
        """
        source = Path(directory)
        if source.is_symlink():
            raise PackRejected("a bundled pack directory must not be a symbolic link")
        manifest, files = read_directory(source)
        staged_id = "stg-" + secrets.token_hex(16)
        self.root.mkdir(parents=True, exist_ok=True)
        envelope = self.root / staged_id
        staged_directory = envelope / "pack"
        staged_directory.mkdir(parents=True, exist_ok=True)
        try:
            (staged_directory / root_file()).write_bytes((source / root_file()).read_bytes())
            for relative, payload in files.items():
                target = staged_directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
        except OSError as exc:
            shutil.rmtree(envelope, ignore_errors=True)
            raise PackRejected(f"bundled pack could not be staged: {exc}") from exc
        staged = StagedPack(
            staged_id=staged_id,
            directory=staged_directory,
            manifest=manifest,
            integrity={
                "hashes_match": True,
                "file_count": len(manifest["files"]),
                "expanded_bytes": sum(int(entry["bytes"]) for entry in manifest["files"]),
            },
            granted_from=str(source),
        )
        self._staged[staged_id] = staged
        self._write_record(staged)
        return staged_id

    def stage(self, staged_id: str) -> StagedPack:
        """Validate the granted archive and publish a staged record, or reject with no residue."""
        cached = self._staged.get(staged_id)
        if cached is not None and cached.directory.is_dir():
            return cached
        grant = self._grants.get(staged_id)
        if grant is None:
            raise PackRejected("unknown staged_id; a local file grant must be registered by the host")
        if grant["expires_at"] < self.clock():
            self._grants.pop(staged_id, None)
            raise PackRejected("staged_id expired; grant the file again")
        self.root.mkdir(parents=True, exist_ok=True)
        partial = self.root / f"{staged_id}.partial"
        final = self.root / staged_id
        shutil.rmtree(partial, ignore_errors=True)
        manifest = extract_archive(grant["path"], partial)
        inner = next(iter(partial.iterdir()), None)
        if inner is None or not inner.is_dir():
            shutil.rmtree(partial, ignore_errors=True)
            raise PackRejected("staged archive has no root directory")
        os.replace(partial, final)
        staged = StagedPack(
            staged_id=staged_id,
            directory=final / inner.name,
            manifest=manifest,
            integrity={
                "hashes_match": True,
                "file_count": len(manifest["files"]),
                "expanded_bytes": sum(int(entry["bytes"]) for entry in manifest["files"]),
            },
            granted_from=str(grant["path"]),
        )
        self._grants.pop(staged_id, None)
        self._staged[staged_id] = staged
        self._write_record(staged)
        return staged

    def get(self, staged_id: str) -> StagedPack | None:
        staged = self._staged.get(staged_id)
        return staged if staged is not None and staged.directory.is_dir() else None

    def discard(self, staged_id: str) -> None:
        staged = self._staged.pop(staged_id, None)
        if staged is not None:
            shutil.rmtree(staged.directory.parent, ignore_errors=True)
        self._grants.pop(staged_id, None)
        shutil.rmtree(self.root / f"{staged_id}.partial", ignore_errors=True)

    def _write_record(self, staged: StagedPack) -> None:
        record = {
            "staged_id": staged.staged_id,
            "pack_id": staged.manifest["pack_id"],
            "pack_version": staged.manifest["pack_version"],
            "content_hash": staged.content_hash,
            "file_count": staged.integrity["file_count"],
            "expanded_bytes": staged.integrity["expanded_bytes"],
            "created_at": staged.created_at,
        }
        path = staged.directory.parent / "staged.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def reconcile(self) -> list[str]:
        """Remove expired or interrupted staging directories. Call once at backend startup."""
        removed: list[str] = []
        if not self.root.is_dir():
            return removed
        now = self.clock()
        for entry in self.root.iterdir():
            if not entry.is_dir():
                continue
            if entry.name.endswith(".partial"):
                shutil.rmtree(entry, ignore_errors=True)
                removed.append(entry.name)
                continue
            record_path = entry / "staged.json"
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
                created = float(record.get("created_at", 0))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                created = 0.0
            if now - created > self.ttl_seconds:
                shutil.rmtree(entry, ignore_errors=True)
                removed.append(entry.name)
        self._grants.clear()
        self._staged.clear()
        return removed


def temporary_staging_root() -> tempfile.TemporaryDirectory[str]:
    """A staging root for tests/CLI use. Plugin code passes the plugin-data directory instead."""
    return tempfile.TemporaryDirectory(prefix="coursebook-staging-")
