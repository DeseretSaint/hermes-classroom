"""Pack manifest seam: identity, hashing, minima, audit, preview and export.

``cb.pack`` is the authority for the pack document. This module owns everything about a pack
*manifest*; :mod:`coursebook.archive` owns bounded archive reading, staging and atomic adopt.

Security posture (``PREBUILD_SPEC.md`` §11, ``AUDIT.md`` R6/H6/H7): a pack is untrusted data.
Its prose never becomes ``AGENTS.md`` policy, never carries executable code or tool calls, and
never contains learning history. Validation is allowlist-first: unknown fields are rejected.

Three decisions recorded here because the frozen contract leaves the mechanism open:

1. **Manifest encodings are canonical.** ``content_hash`` is computed over
   ``json.dumps(document_without_content_hash, sort_keys=True, separators=(",", ":"),
   ensure_ascii=False).encode("utf-8")`` followed by ``path\\0sha256\\n`` for every file record
   in manifest order. ``pack.json`` is **not** listed in ``files``: listing it would make the
   hash self-referential (the manifest would contain its own digest). ``files`` therefore lists
   teaching content only, and the ``manifest`` role is reserved and refused inside ``files``.
2. **Preview never invents a safety verdict.** It returns the manifest, an integrity block and
   the four separate trust labels (``integrity_verified``, ``automated_checks_passed``,
   ``human_review_recorded``, ``model_assessed_support``). There is no "safe" or "true" badge.
3. **Export is rebuilt, never copied.** Every exported field is selected from
   :func:`export_allowlist`; identity, license and trust are set deliberately; no stored
   manifest, transcript, attempt, notebook entry, provider setting or local path can ride
   along because those fields do not exist in the built document.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import warnings as warnings_module
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import segments
from . import rubrics
from .contracts import ContractError, contract, contract_as, validate_as, version_files

CONTRACT_ID = "cb.pack"

#: ``media[]`` entry cap per section, mirrored from ``lesson_document.MAX_MEDIA_PER_BLOCK``.
MAX_MEDIA_PER_SECTION = 8
#: ``media[].caption`` cap, mirrored from ``lesson_document.MAX_PURPOSE`` (the media child's
#: ``purpose`` is filled from the segment text, so the two must not drift).
MAX_MEDIA_CAPTION = 200
#: Roles a ``media[]`` link may name, and the artifact kind each one materializes as.
MEDIA_LINK_ROLES: dict[str, str] = {"narration": "audio", "visual": "visual"}

#: Fields that must never appear in an exported or imported pack, by construction.
EXCLUDED_BY_CONSTRUCTION: tuple[str, ...] = tuple(contract(CONTRACT_ID)["excluded_by_construction"])

#: Roles read by a learner. A reference answer must never be rendered in one of these.
LEARNER_FACING_ROLES: frozenset[str] = frozenset({"section", "learner_page", "visual", "narration"})

#: Roles a pack may hold. Read from the contract so a future revision is a data change here.
FILE_ROLES: tuple[str, ...] = tuple(contract(CONTRACT_ID)["properties"]["files"]["items"]["properties"]["role"]["enum"])

#: MIME types a pack may declare, from the contract.
FILE_MIME_TYPES: tuple[str, ...] = tuple(
    contract(CONTRACT_ID)["properties"]["files"]["items"]["properties"]["mime"]["enum"]
)

#: Media MIME types that always require a per-artifact license record and a text equivalent.
MEDIA_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/webp", "audio/mpeg", "audio/wav", "audio/ogg", "application/pdf"}
)

#: Roles that may be exported. Every role except the reserved ``manifest`` marker.
EXPORTABLE_ROLES: tuple[str, ...] = tuple(role for role in FILE_ROLES if role != "manifest")

#: Top-level keys that must never be produced by export, even if a caller passes them.
PRIVATE_FIELDS: frozenset[str] = frozenset(
    {
        "transcript",
        "transcripts",
        "attempts",
        "attempt",
        "evidence",
        "notebook",
        "notebook_entries",
        "reflection",
        "reflections",
        "provider",
        "model",
        "settings",
        "credentials",
        "api_key",
        "session_id",
        "local_path",
        "path_override",
        "tools",
        "tool_calls",
        "code",
        "script",
    }
)

#: Minimum rubric criteria per check. Schema allows one; a one-line rubric is not a rubric.
MIN_RUBRIC_CRITERIA = 3

_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$")


class PackRejected(ValueError):
    """A pack failed validation or a policy check. Maps to ``PACK_REJECTED``; nothing was adopted."""


# ── Contract access ─────────────────────────────────────────────────────────


def limits() -> dict[str, int]:
    return {key: int(value) for key, value in contract(CONTRACT_ID)["limits"].items()}


def root_file() -> str:
    return str(contract(CONTRACT_ID)["root_file"])


def export_allowlist(version: int | None = None) -> tuple[str, ...]:
    """Top-level manifest fields permitted in an exported pack.

    Export builds a fresh document from these fields; it never copies a stored manifest, which is
    how personal notes, attempts and notebook text stay out by construction. *version* selects the
    schema whose allowlist applies: a v1 pack re-exports as v1 and never gains ``media``.
    """
    document = contract(CONTRACT_ID) if version is None else contract_as(CONTRACT_ID, version)
    return tuple(document["properties"].keys())


def manifest_contract_version(document: Any) -> int:
    """The declared ``contract_version`` of a pack manifest, bounded to the known set.

    Peeked and type-checked before any schema is chosen, so a bogus value is a refusal naming the
    version rather than a schema error at an arbitrary location.
    """
    version = document.get("contract_version") if isinstance(document, Mapping) else None
    if not isinstance(version, int) or isinstance(version, bool):
        raise PackRejected("pack manifest contract_version must be an integer")
    known = version_files(CONTRACT_ID)
    if version not in known:
        raise PackRejected(
            f"pack manifest declares contract_version {version}; this build accepts {sorted(known)}"
        )
    return int(version)


def validate_manifest(document: Any) -> None:
    """Validate a parsed pack manifest against the ``cb.pack`` version it declares.

    A v1 document is judged by the frozen v1 schema and a v2 document by v2; neither inherits the
    other's allowlist. Raises :class:`PackRejected` with the failing location. Callers must not
    adopt any content until this returns cleanly.
    """
    version = manifest_contract_version(document)
    try:
        validate_as(CONTRACT_ID, version, document, what="pack manifest")
    except ContractError as exc:
        raise PackRejected(str(exc)) from exc


# ── Hashing ─────────────────────────────────────────────────────────────────


def canonical_json_bytes(document: Any) -> bytes:
    """Canonical UTF-8 JSON used for every pack digest. Stable across machines and Python builds."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def file_sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_hash(manifest: Mapping[str, Any]) -> str:
    """Pack content hash, exactly as previewed and imported.

    See the module docstring for the formula. The hash does not depend on JSON whitespace,
    key order or the archive container; it depends on the manifest meaning and the content
    digests in manifest order.
    """
    document = {key: value for key, value in manifest.items() if key != "content_hash"}
    digest = hashlib.sha256(canonical_json_bytes(document))
    for entry in document.get("files", []):
        digest.update(b"\n")
        digest.update(str(entry["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry["sha256"]).encode("ascii"))
    return "sha256:" + digest.hexdigest()


def with_content_hash(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of *manifest* carrying the hash its current content implies."""
    document = copy.deepcopy(dict(manifest))
    document.pop("content_hash", None)
    document["content_hash"] = content_hash(document)
    return document


def verify_content_hash(manifest: Mapping[str, Any]) -> None:
    declared = manifest.get("content_hash")
    actual = content_hash(manifest)
    if declared != actual:
        raise PackRejected(
            f"content_hash does not match the manifest and files: declared {declared!r}, computed {actual!r}"
        )


# ── Manifest construction ───────────────────────────────────────────────────


def file_record(
    path: str,
    data: bytes,
    *,
    mime: str,
    role: str,
    text_equivalent: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build one ``files[]`` record from the real bytes. Size and hash always come from *data*."""
    record: dict[str, Any] = {
        "path": path,
        "sha256": file_sha256(data),
        "bytes": len(data),
        "mime": mime,
        "role": role,
    }
    if text_equivalent is not None:
        record["text_equivalent"] = text_equivalent
    if description is not None:
        record["description"] = description
    return record


def build_manifest(
    *,
    pack_id: str,
    pack_version: str,
    title: str,
    recipe: str,
    minimum_coursebook_version: str,
    license: Mapping[str, Any],
    attribution: str,
    objectives: list[dict[str, Any]],
    files: Mapping[str, bytes],
    file_metadata: Mapping[str, Mapping[str, Any]],
    sources: list[dict[str, Any]] | None = None,
    contract_version: int | None = None,
    **optional: Any,
) -> dict[str, Any]:
    """Assemble and validate a manifest from content bytes.

    *file_metadata* is ``path -> {mime, role, text_equivalent?, description?}``. Both sides must
    agree exactly: a declared file with no bytes, or bytes with no declared metadata, is an
    error rather than a silently partial pack.

    *contract_version* defaults to the current ``cb.pack`` version. A builder that must keep
    producing the older document (the bundled demo packs, until the release ships v2) passes it
    explicitly; the schema, allowlist and stamp all follow that version.
    """
    declared = set(files)
    described = set(file_metadata)
    if declared != described:
        missing = sorted(declared - described)
        extra = sorted(described - declared)
        raise PackRejected(f"file bytes and metadata disagree: no metadata for {missing}, no bytes for {extra}")
    if root_file() in declared:
        raise PackRejected(f"{root_file()!r} is the manifest and must not be listed in files")

    records = []
    for path in sorted(files):
        meta = file_metadata[path]
        records.append(
            file_record(
                path,
                files[path],
                mime=str(meta["mime"]),
                role=str(meta["role"]),
                text_equivalent=meta.get("text_equivalent"),
                description=meta.get("description"),
            )
        )

    document: dict[str, Any] = {
        "contract": CONTRACT_ID,
        "contract_version": int(
            contract(CONTRACT_ID)["x-contract-version"] if contract_version is None else contract_version
        ),
        "pack_id": pack_id,
        "pack_version": pack_version,
        "title": title,
        "recipe": recipe,
        "minimum_coursebook_version": minimum_coursebook_version,
        "license": dict(license),
        "attribution": attribution,
        "objectives": copy.deepcopy(objectives),
        "files": records,
    }
    if sources is not None:
        document["sources"] = copy.deepcopy(sources)
    for key, value in optional.items():
        if key not in export_allowlist(document["contract_version"]) or key in document or key in PRIVATE_FIELDS:
            raise PackRejected(f"cannot set manifest field {key!r}")
        document[key] = copy.deepcopy(value)
    document = with_content_hash(document)
    validate_manifest(document)
    validate_minima(document)
    return document


def load_manifest(path: str | Path, *, verify_hash: bool = True) -> dict[str, Any]:
    """Read and validate ``pack.json`` from disk. JSON only — never YAML, never executable."""
    manifest_path = Path(path)
    if manifest_path.name != root_file():
        raise PackRejected(f"pack manifest must be named {root_file()!r}, got {manifest_path.name!r}")
    if manifest_path.is_symlink():
        raise PackRejected("pack manifest must not be a symbolic link")
    try:
        size = manifest_path.stat().st_size
    except OSError as exc:
        raise PackRejected(f"pack manifest is unreadable: {exc}") from exc
    maximum = limits()["max_manifest_bytes"]
    if size > maximum:
        raise PackRejected(f"pack manifest is {size} bytes, over the {maximum}-byte limit")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackRejected(f"pack manifest is unreadable: {exc}") from exc
    validate_manifest(document)
    if verify_hash:
        verify_content_hash(document)
    return document


# ── Version gate ────────────────────────────────────────────────────────────


def semver_core(value: str) -> tuple[int, int, int]:
    match = _SEMVER.match(str(value))
    if match is None:
        raise PackRejected(f"{value!r} is not a semantic version")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def require_minimum_version(manifest: Mapping[str, Any], current_version: str) -> None:
    """Refuse a pack built for a newer Coursebook, naming both versions.

    A prerelease build is older than the matching release; a release satisfies any prerelease of
    the same core version.
    """
    required = str(manifest["minimum_coursebook_version"])
    required_core = semver_core(required)
    current_core = semver_core(current_version)
    required_pre = _SEMVER.match(required).group(4)  # type: ignore[union-attr]
    current_pre = _SEMVER.match(str(current_version)).group(4)  # type: ignore[union-attr]
    if current_core < required_core or (
        current_core == required_core and current_pre is not None and required_pre is None
    ):
        raise PackRejected(
            f"pack requires Coursebook {required}; this build is {current_version}. "
            "Import is refused rather than attempting an incompatible migration."
        )


# ── Policy minima ───────────────────────────────────────────────────────────


def validate_minima(manifest: Mapping[str, Any]) -> None:
    """Checks the schema cannot express: a teachable pack, not merely a legal document."""
    problems = _minima_problems(manifest)
    if problems:
        raise PackRejected("pack does not meet the teaching minima: " + "; ".join(problems))


def _minima_problems(manifest: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    paths = {str(entry["path"]) for entry in manifest["files"]}
    if root_file() in paths:
        problems.append(f"{root_file()} must not be listed in files")
    if any(str(entry["role"]) == "manifest" for entry in manifest["files"]):
        problems.append("the reserved 'manifest' role must not be used in files")

    objective_ids: set[str] = set()
    ordinals: list[int] = []
    check_ids: set[str] = set()
    for index, objective in enumerate(manifest["objectives"]):
        oid = str(objective["objective_id"])
        if oid in objective_ids:
            problems.append(f"duplicate objective_id {oid!r}")
        objective_ids.add(oid)
        ordinals.append(int(objective["ordinal"]))
        checks = objective.get("checks") or []
        if not checks:
            problems.append(f"objective {oid!r} has no check")
        for check in checks:
            cid = str(check["check_id"])
            if cid in check_ids:
                problems.append(f"duplicate check_id {cid!r}")
            check_ids.add(cid)
            if str(check["evidence_target"]) != str(objective["evidence_target"]):
                problems.append(
                    f"check {cid!r} measures {check['evidence_target']!r} but its objective "
                    f"{oid!r} is declared {objective['evidence_target']!r}"
                )
            rubric = check.get("rubric") or []
            # The construct profile is derived from the check's declared evidence target: a pack
            # manifest carries no authored construct, so the target is the authority. The
            # registry's rules (minimum, ceiling, distinctness, observability, no mental states)
            # apply to every pack rubric, not only to generated ones.
            profile = rubrics.default_profile_for(str(check["evidence_target"]))
            for problem in rubrics.validate_rubric(profile, rubric, str(check["evidence_target"])):
                problems.append(f"check {cid!r}: {problem}")
            alternatives = [str(item) for item in check.get("accepted_alternatives") or []]
            if len(set(alternatives)) != len(alternatives):
                problems.append(f"check {cid!r} repeats an accepted alternative")
            if str(check["reference_answer"]) in alternatives:
                problems.append(f"check {cid!r} lists its reference answer as an accepted alternative")
        sections = objective.get("sections") or []
        if not sections:
            problems.append(f"objective {oid!r} has no section")
        section_ids: set[str] = set()
        for section in sections:
            sid = str(section["section_id"])
            if sid in section_ids:
                problems.append(f"objective {oid!r} repeats section_id {sid!r}")
            section_ids.add(sid)
            if str(section["path"]) not in paths:
                problems.append(f"objective {oid!r} points at undeclared section file {section['path']!r}")
    if ordinals and sorted(ordinals) != list(range(1, len(ordinals) + 1)):
        problems.append(f"objective ordinals must be 1..{len(ordinals)} without gaps or repeats")

    source_ids: set[str] = set()
    for source in manifest.get("sources") or []:
        sid = str(source["source_id"])
        if sid in source_ids:
            problems.append(f"duplicate source_id {sid!r}")
        source_ids.add(sid)
        if not source.get("url") and not source.get("publisher"):
            problems.append(f"source {sid!r} has neither a URL nor a publisher")

    all_paths = [str(entry["path"]) for entry in manifest["files"]]
    if len(set(all_paths)) != len(all_paths):
        problems.append("files contains duplicate paths")
    for artifact in manifest["license"].get("per_artifact") or []:
        if str(artifact["path"]) not in paths:
            problems.append(f"per-artifact license names undeclared file {artifact['path']!r}")
    declared = {str(entry["path"]): entry for entry in manifest["files"]}
    licensed = {str(artifact["path"]) for artifact in manifest["license"].get("per_artifact") or []}
    for entry in manifest["files"]:
        path = str(entry["path"])
        role = str(entry["role"])
        mime = str(entry["mime"])
        if _role_mime_mismatch(role, mime):
            problems.append(f"{path!r}: role {role!r} cannot hold MIME {mime!r}")
        if mime in MEDIA_MIME_TYPES and not entry.get("text_equivalent"):
            problems.append(f"{path!r}: media needs a text equivalent for accessibility")
        if mime in MEDIA_MIME_TYPES and path not in licensed:
            problems.append(f"{path!r}: media needs a per-artifact license record")
    problems.extend(_media_link_problems(manifest, declared))
    return problems


def section_paths(manifest: Mapping[str, Any]) -> set[str]:
    """Every section file path any objective declares, i.e. the paths a lesson page can resolve."""
    paths: set[str] = set()
    for objective in manifest.get("objectives") or []:
        for section in objective.get("sections") or []:
            path = str(section.get("path") or "")
            if path:
                paths.add(path)
    return paths


def _media_link_problems(manifest: Mapping[str, Any], declared: Mapping[str, Any]) -> list[str]:
    """M1–M7: the rules that travel with the ``media[]`` link (H-73 §4).

    A link that no page can resolve is a defect, not a no-op: it is refused here rather than
    silently dropped at import, because an author who wrote it believes the learner will hear it.
    """
    problems: list[str] = []
    media = manifest.get("media")
    if media is None:
        return problems
    version = manifest_contract_version(manifest)
    if version < 2:
        problems.append(f"contract_version {version} may not carry a media[] link")
        return problems
    objective_sections = section_paths(manifest)
    seen: set[tuple[str, str]] = set()
    per_section: dict[str, int] = {}
    for index, entry in enumerate(media or []):
        if not isinstance(entry, Mapping):
            problems.append(f"media[{index}] must be an object")
            continue
        path = str(entry.get("path") or "")
        section_path = str(entry.get("section_path") or "")
        caption = str(entry.get("caption") or "")
        # M1: the file must be declared, so its bytes, hash, licence and text equivalent exist.
        file_entry = declared.get(path)
        if file_entry is None:
            problems.append(f"media[{index}]: {path!r} is not a declared file")
            continue
        role = str(file_entry.get("role"))
        # M2: only a narration/visual file may be played, and the role must match the MIME.
        if role not in MEDIA_LINK_ROLES:
            problems.append(
                f"media[{index}]: {path!r} has role {role!r}; only "
                f"{sorted(MEDIA_LINK_ROLES)} may be linked to a lesson page"
            )
        # M3: the section must be one an objective declares, or no page can ever resolve the link.
        if section_path not in objective_sections:
            problems.append(
                f"media[{index}]: section_path {section_path!r} is not a section of any objective"
            )
        # M4: the same file may link to several sections; the same pair twice is a defect.
        pair = (path, section_path)
        if pair in seen:
            problems.append(f"media[{index}]: duplicate link of {path!r} to {section_path!r}")
        seen.add(pair)
        # M5: the caption becomes the media child's ``purpose`` and ``text_equivalent``.
        if not 1 <= len(caption) <= MAX_MEDIA_CAPTION:
            problems.append(
                f"media[{index}]: caption is {len(caption)} characters; the media child cap is "
                f"{MAX_MEDIA_CAPTION}"
            )
        # M6: the block a media child attaches to holds at most eight children.
        per_section[section_path] = per_section.get(section_path, 0) + 1
        if per_section[section_path] > MAX_MEDIA_PER_SECTION:
            problems.append(
                f"media[{index}]: section {section_path!r} links more than "
                f"{MAX_MEDIA_PER_SECTION} media files"
            )
    return problems


def _role_mime_mismatch(role: str, mime: str) -> bool:
    textual = {"section", "check", "rubric", "source_note", "parent_guide", "learner_page", "answer_guide"}
    if role in textual:
        allowed = {"text/markdown", "text/plain", "application/json"}
        if role == "source_note":
            allowed.add("application/pdf")
        return mime not in allowed
    if role == "visual":
        return mime not in {"image/png", "image/jpeg", "image/webp"}
    if role == "narration":
        return mime not in {"audio/mpeg", "audio/wav", "audio/ogg"}
    return role == "manifest"


# ── Audit ───────────────────────────────────────────────────────────────────


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def audit_bundle(directory: str | Path) -> list[str]:
    """Audit extracted pack content on disk. Returns hard problems; empty means clean.

    This is the content audit that runs after schema validation and hash/MIME verification.
    It cannot prove that prose is true or safe; it proves the mechanical guarantees this build
    claims: declared files exist with matching bytes, learner-facing pages do not carry the
    answer key, media carries accessibility text, and licences cover media.
    """
    root = Path(directory)
    problems: list[str] = []
    try:
        manifest = load_manifest(root / root_file())
    except PackRejected as exc:
        return [str(exc)]
    problems.extend(_minima_problems(manifest))

    declared = {str(entry["path"]): entry for entry in manifest["files"]}
    for path, entry in declared.items():
        target = root / path
        if not target.is_file():
            problems.append(f"declared file {path!r} is missing from the pack")
            continue
        data = target.read_bytes()
        if len(data) != int(entry["bytes"]):
            problems.append(f"{path!r}: {len(data)} bytes on disk, manifest declares {entry['bytes']}")
        if file_sha256(data) != entry["sha256"]:
            problems.append(f"{path!r}: sha256 does not match the manifest")
    actual = {
        str(candidate.relative_to(root))
        for candidate in root.rglob("*")
        if candidate.is_file() and candidate.name != root_file()
    }
    for extra in sorted(actual - set(declared)):
        problems.append(f"undeclared file present in pack: {extra!r}")
    for missing in sorted(set(declared) - actual):
        problems.append(f"declared file missing: {missing!r}")

    for entry in manifest["files"]:
        if str(entry["mime"]) in MEDIA_MIME_TYPES and not entry.get("text_equivalent"):
            problems.append(f"{entry['path']!r}: media needs a text equivalent")
    for entry in manifest["files"]:
        if str(entry["mime"]) in MEDIA_MIME_TYPES and not _covered_by_per_artifact(manifest, str(entry["path"])):
            problems.append(f"{entry['path']!r}: media has no per-artifact license record")

    problems.extend(_answer_key_problems(root, manifest))
    return problems


def _covered_by_per_artifact(manifest: Mapping[str, Any], path: str) -> bool:
    return any(str(artifact["path"]) == path for artifact in manifest["license"].get("per_artifact") or [])


def _answer_key_problems(root: Path, manifest: Mapping[str, Any]) -> list[str]:
    """A reference answer must never appear verbatim in learner-facing content."""
    learner_text: dict[str, str] = {}
    for entry in manifest["files"]:
        if str(entry["role"]) in LEARNER_FACING_ROLES and str(entry["mime"]).startswith("text/"):
            learner_text[str(entry["path"])] = _read_text(root / str(entry["path"]))
    problems: list[str] = []
    for objective in manifest["objectives"]:
        for check in objective.get("checks") or []:
            answer = str(check["reference_answer"]).strip()
            if len(answer) < 4:
                continue
            for path, text in learner_text.items():
                if answer in text:
                    problems.append(f"check {check['check_id']!r}: reference answer appears on learner page {path!r}")
    return problems


# ── Authoring warnings ──────────────────────────────────────────────────────


class PackAuthoringWarning(UserWarning):
    """A pack is contract-valid but an authoring bound will make import refuse it.

    A warning, not a refusal: the import path owns refusal (``segments.audit_objective_texts``
    raises ``PACK_REJECTED`` before the first write). Preview, export and the fixture validator
    raise this as a Python warning naming the file and its measured length.
    """


def authoring_warnings(manifest: Mapping[str, Any], files: Mapping[str, bytes]) -> list[str]:
    """Warnings from the content itself, for a manifest and its section bytes."""
    mime_by_path = {str(entry["path"]): str(entry.get("mime") or "") for entry in manifest.get("files") or []}
    texts: dict[str, str] = {}
    for path in segments.declared_section_paths(manifest):
        data = files.get(path)
        if data is None or not mime_by_path.get(path, "").startswith("text/"):
            continue
        try:
            texts[path] = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            continue
    return segments.authoring_warnings(manifest, texts)


def audit_warnings(directory: str | Path, *, manifest: Mapping[str, Any] | None = None) -> list[str]:
    """Authoring warnings for an unpacked pack directory; empty means none.

    Sits beside :func:`audit_bundle`, which returns hard problems. Nothing here is a rejection.
    """
    root = Path(directory)
    if manifest is None:
        try:
            manifest = load_manifest(root / root_file())
        except PackRejected:
            return []
    files: dict[str, bytes] = {}
    for path in segments.declared_section_paths(manifest):
        candidate = root / path
        if candidate.is_file():
            files[path] = candidate.read_bytes()
    return authoring_warnings(manifest, files)


def warn_authoring_bound(manifest: Mapping[str, Any], files: Mapping[str, bytes]) -> list[str]:
    """Emit :class:`PackAuthoringWarning` for every file over the lesson-section bound."""
    found = authoring_warnings(manifest, files)
    for message in found:
        warnings_module.warn(message, PackAuthoringWarning, stacklevel=3)
    return found


# ── Trust and preview ───────────────────────────────────────────────────────


def trust_labels(
    manifest: Mapping[str, Any],
    *,
    integrity_verified: bool,
    automated_checks_passed: bool,
) -> list[str]:
    """Four independent dimensions. No label implies the others and none means "safe"."""
    labels: list[str] = []
    if integrity_verified:
        labels.append("integrity_verified")
    if automated_checks_passed:
        labels.append("automated_checks_passed")
    recorded = manifest.get("trust") or {}
    if recorded.get("reviewed_by") and recorded.get("reviewed_at"):
        labels.append("human_review_recorded")
    if any(str(source.get("support_status")) == "model_assessed" for source in manifest.get("sources") or []):
        labels.append("model_assessed_support")
    return labels


def preview(
    manifest: Mapping[str, Any],
    *,
    integrity: Mapping[str, Any] | None = None,
    automated_checks_passed: bool = True,
) -> dict[str, Any]:
    """Build the contract-shaped ``pack.preview`` response.

    ``cb.rpc`` permits exactly ``manifest``, ``integrity`` and ``trust``. Author, outcomes,
    sources/support, licences, notes and media size are all carried by those three objects —
    the manifest itself plus ``integrity.expanded_bytes``. Nothing is summarised away.
    """
    integrity_block = {
        "hashes_match": bool((integrity or {}).get("hashes_match", False)),
        "file_count": int((integrity or {}).get("file_count", len(manifest["files"]))),
        "expanded_bytes": int(
            (integrity or {}).get("expanded_bytes", sum(int(entry["bytes"]) for entry in manifest["files"]))
        ),
    }
    labels = trust_labels(
        manifest,
        integrity_verified=integrity_block["hashes_match"],
        automated_checks_passed=automated_checks_passed,
    )
    # cb.rpc v2 narrowed `trust` to labels only; reviewer identity stays in the manifest's own
    # `trust` block, where it is provenance rather than a response field.
    trust: dict[str, Any] = {"labels": labels}
    return {
        "manifest": copy.deepcopy(dict(manifest)),
        "integrity": integrity_block,
        "trust": trust,
    }


# ── Export ──────────────────────────────────────────────────────────────────


def contains_private_fields(document: Any, *, path: str = "") -> list[str]:
    """Return every location where a private field name appears. Used to audit exports."""
    found: list[str] = []
    if isinstance(document, Mapping):
        for key, value in document.items():
            here = f"{path}/{key}" if path else str(key)
            if str(key) in PRIVATE_FIELDS:
                found.append(here)
            found.extend(contains_private_fields(value, path=here))
    elif isinstance(document, list):
        for index, value in enumerate(document):
            found.extend(contains_private_fields(value, path=f"{path}/{index}"))
    return found


def build_export(
    manifest: Mapping[str, Any],
    files: Mapping[str, bytes],
    *,
    pack_id: str | None = None,
    pack_version: str | None = None,
    license: Mapping[str, Any] | None = None,
    attribution: str | None = None,
    contributors: list[dict[str, Any]] | None = None,
    trust_labels_override: Iterable[str] | None = None,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Build an allowlisted export from a validated pack and its content bytes.

    Private learning data cannot be included: the source mapping passed here is content only,
    and the output document is assembled field-by-field from :func:`export_allowlist`. A local
    fork gets a new ``pack_id``/``pack_version`` and keeps ``derived_from``; passing the original
    identity re-exports unchanged material under the same identity (used by roundtrip tests).
    """
    validate_manifest(manifest)
    validate_minima(manifest)
    version = manifest_contract_version(manifest)

    declared = {str(entry["path"]): entry for entry in manifest["files"]}
    provided = {str(path): bytes(data) for path, data in files.items()}
    if set(provided) != set(declared):
        missing = sorted(set(declared) - set(provided))
        extra = sorted(set(provided) - set(declared))
        raise PackRejected(f"export bytes must match the manifest exactly: missing {missing}, undeclared {extra}")
    for path, entry in declared.items():
        if str(entry["role"]) not in EXPORTABLE_ROLES:
            raise PackRejected(f"cannot export {path!r}: role {entry['role']!r} is not exportable")
        if file_sha256(provided[path]) != str(entry["sha256"]):
            raise PackRejected(f"cannot export {path!r}: bytes do not match the declared hash")
        if len(provided[path]) != int(entry["bytes"]):
            raise PackRejected(f"cannot export {path!r}: bytes do not match the declared size")

    # Authoring bound: an over-long lesson section is still exportable (the pack is contract-valid
    # and export is not the refusal seam), but the author is warned here, naming the file and its
    # measured length, before the bytes leave Coursebook. Import owns the refusal.
    warn_authoring_bound(manifest, provided)

    source = {key: copy.deepcopy(manifest[key]) for key in export_allowlist(version) if key in manifest}
    source.pop("files", None)
    source.pop("content_hash", None)
    source.pop("trust", None)
    # The re-export keeps the version the source declared: a v1 pack must not acquire a v2 stamp
    # (and therefore a different content hash) just because this build speaks v2.
    source["contract_version"] = version

    source["pack_id"] = pack_id if pack_id is not None else str(manifest["pack_id"])
    source["pack_version"] = pack_version if pack_version is not None else str(manifest["pack_version"])
    if pack_id is not None or pack_version is not None:
        source["derived_from"] = {
            "pack_id": str(manifest["pack_id"]),
            "pack_version": str(manifest["pack_version"]),
        }
    if license is not None:
        source["license"] = copy.deepcopy(dict(license))
    if attribution is not None:
        source["attribution"] = attribution
    if contributors is not None:
        source["contributors"] = copy.deepcopy(contributors)

    records = []
    for path in sorted(declared):
        entry = declared[path]
        record = file_record(
            path,
            provided[path],
            mime=str(entry["mime"]),
            role=str(entry["role"]),
            text_equivalent=entry.get("text_equivalent"),
            description=entry.get("description"),
        )
        records.append(record)
    source["files"] = records

    if trust_labels_override is not None:
        labels = [str(label) for label in trust_labels_override]
        if not labels:
            source.pop("trust", None)
        else:
            source["trust"] = {"labels": labels}
    else:
        source.pop("trust", None)

    document = with_content_hash(source)
    validate_manifest(document)
    validate_minima(document)
    leaked = contains_private_fields(document)
    if leaked:
        raise PackRejected(f"export would carry private fields: {sorted(set(leaked))}")
    return document, provided
