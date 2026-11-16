"""The curated visual-kit registry: one validated ``kit.json`` per grammar.

A kit is a **product asset**, not a prompt (``docs/launch/GAME-MODE-VISUAL-KIT.md`` §3). It is
curated once, approved once by the owner, and reused by every course that selects its grammar.
This module is the only reader of ``assets/visual-kits/<grammar>/kit.json``:

* :func:`load_kit` parses and **validates** the manifest: the kit id is ``<grammar>@<version>``,
  the lane is the display-plate lane (never the Press Plate lane, ``UI-DECISIONS`` D-006), every
  declared asset exists, is inside the kit directory, hashes to its declared sha256, decodes to
  its declared pixel size, is marked textless and records ``source = curated_kit``. A manifest
  that fails any of those is refused with a named :class:`KitError`; it is never used on trust.
* :meth:`VisualKit.resolve` walks the manifest's own ``fallbacks`` chain to find the plate for a
  requested role. A v2 kit ships a hero, display covers and one lesson scene but no section
  plates and no per-course master, so a section resolves through the chain to the kit's place
  plate — and the plate records which kit role actually supplied the bytes, so nothing claims to
  be a purpose-built section plate when it is not.
* :func:`register_asset` registers the file as a **content-addressed artifact** with provenance
  ``source = curated_kit`` and ``kit_id = <grammar>@<version>``. Approval in that provenance is
  read from the manifest's own ``status``: only a kit whose status is in
  :data:`OWNER_APPROVED_STATUSES` registers ``approved: True``. A review-status kit
  (``built_for_owner_review``) registers ``approved: False`` and names that status, so a preview
  plate is never mistaken for owner-approved art. The artifact store dedupes on the content hash,
  so two courses in one grammar share one artifact row and one file.

The module imports only the standard library at import time; the artifact store and the database
are imported inside the call that needs them, so a pure policy test can load a kit with no profile.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

#: Environment override, so an installed profile or a test can point at its own kit shelf.
ROOT_ENV = "COURSEBOOK_VISUAL_KITS"

#: The manifest lane a consumable kit must declare. A Press Plate pack cover is never display art.
DISPLAY_LANE = "display_plate"

#: The manifest statuses that mean the owner has approved this kit's art. Only a kit whose status
#: is owner-approved may register a plate with ``approved: True`` / ``curated_kit_approved_once``.
#:
#: Every other status — ``built_for_owner_review``, a missing status, an unknown one — is a review
#: state. Such a kit still *loads*: a world may preview it, and its plates are honestly stored as
#: not owner-approved. What it may never do is turn a preview plate into approved product art.
#:
#: ``owner_rework_of_rejected_v1`` is ``field_atlas@2``, the one kit the owner approved (D-007).
#: ``field_atlas@3`` extends that same owner decision with the adopted Home ground and records it as
#: ``owner_rework_of_rejected_v1_plus_adopted_home_ground``, so the approved lineage is matched by
#: prefix rather than by one exact string; a manifest that names the review explicitly
#: (``built_for_owner_review``) never matches. The plain spellings cover a future manifest that
#: records approval directly.
OWNER_APPROVED_STATUSES: frozenset[str] = frozenset({"approved", "approved_once"})

#: Prefixes of manifest statuses that record an owner-approved rework lineage.
OWNER_APPROVED_PREFIXES: tuple[str, ...] = ("owner_rework_of_rejected_v",)


def is_owner_approved_status(status: str) -> bool:
    """Whether a manifest ``status`` says the owner approved this kit's art.

    Exact owner-approval spellings, or an owner-directed rework lineage. Everything else — a
    review state, an empty status, an unknown word — is not approval, so a preview can never be
    registered as owner-approved product art.
    """
    text = str(status or "").strip().lower()
    if not text:
        return False
    if text in OWNER_APPROVED_STATUSES:
        return True
    return any(text.startswith(prefix) for prefix in OWNER_APPROVED_PREFIXES)


#: Provenance label recorded on a plate whose kit came from the owner-approved set.
APPROVAL_APPROVED = "curated_kit_approved_once"

#: Provenance label recorded on a plate whose kit is still awaiting owner review (or has no
#: recognised approval status). A plate carrying this label is never an approved artifact.
APPROVAL_OWNER_REVIEW = "curated_kit_owner_review"

#: The provenance words a kit row may declare for its own bytes. ``curated_kit`` is art curated for
#: that kit; ``derived`` is a byte-identical copy of a plate the owner already approved for another
#: surface (``field_atlas@3``'s Home ground). Both name owner-approved kit art and neither claims a
#: provider generated the file; any other word is refused rather than mounted.
KIT_SOURCES: tuple[str, ...] = ("curated_kit", "derived")


def is_kit_source(value: Any) -> bool:
    """Whether *value* is a provenance word a curated kit may record for its own bytes."""
    return str(value or "") in KIT_SOURCES


#: Roles a kit may declare. ``style_board`` is not a kit role: concepts are built by the world
#: policy from the grammar, and a curated concept is a kit plate, not a stored style board.
#: ``home_ground`` is the Home *stage backdrop* plate (``desktop/plugin.js`` role
#: ``kit.home_ground.home-ground``); it became a kit role when ``field_atlas@3`` adopted the
#: owner-approved ground, and ``scripts/vq008-kits.py`` reads the same vocabulary.
KIT_ROLES: tuple[str, ...] = (
    "hero", "cover", "section", "lesson_scene", "collectible", "object", "fox", "home_ground",
)

#: The aspect each contract role is mounted at (``coursebook.world._ASPECT``). Used only to pick
#: the closest plate when a kit declares several; it never crops or resizes a kit file.
ROLE_ASPECT: dict[str, str] = {
    "hero": "16:9",
    "cover": "4:5",
    "section": "1:1",
    "lesson_scene": "16:9",
    # The Home stage backdrop is the same full-bleed field as the hero.
    "home_ground": "16:9",
}

#: Fallback chain used when the manifest declares none for a role. Kept here rather than in a
#: screen so the walk is one policy. ``course-master`` and ``background`` are the manifest's own
#: names (see ``fallbacks`` in ``kit.json``); they resolve to an asset id or are skipped.
DEFAULT_FALLBACKS: dict[str, tuple[str, ...]] = {
    "hero": ("background",),
    "cover": ("course-master", "background"),
    "section": ("lesson_scene", "hero"),
    "lesson_scene": ("section", "background"),
    "home_ground": ("background",),
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

#: Tolerance when comparing a plate's own aspect to the role's mounted aspect. 1344x768 is 1.75
#: against a 16:9 1.7778 — the shipped hero is the contract's hero, not a near-miss.
_ASPECT_TOLERANCE = 0.05

_REQUIRED_ASSET_FIELDS: tuple[str, ...] = ("id", "role", "path", "size", "sha256")


class KitError(ValueError):
    """A kit manifest that cannot be used. Carries a stable ``reason`` and the offending detail."""

    def __init__(self, reason: str, message: str, *, detail: str = "") -> None:
        self.reason = str(reason)
        self.message = str(message)
        self.detail = str(detail)
        super().__init__(f"{self.reason}: {self.message}")


@dataclass(frozen=True)
class KitAsset:
    """One declared plate. ``abs_path`` is resolved; every other field is manifest data."""

    kit_id: str
    grammar: str
    version: int
    asset_id: str
    role: str
    path: str
    abs_path: Path
    size: tuple[int, int]
    sha256: str
    textless: bool
    source: str
    course_id: str | None = None
    section_key: str | None = None

    @property
    def ratio(self) -> float:
        width, height = self.size
        return float(width) / float(height) if height else 0.0

    def provenance(self) -> dict[str, Any]:
        """The kit's own recorded provenance for this asset, verbatim and unedited."""
        return {
            "kit_id": self.kit_id,
            "kit_grammar": self.grammar,
            "kit_version": self.version,
            "kit_asset_id": self.asset_id,
            "kit_asset_path": self.path,
            "kit_asset_sha256": self.sha256,
            "kit_asset_size": [int(self.size[0]), int(self.size[1])],
        }


@dataclass(frozen=True)
class KitPlate:
    """A resolved plate: the asset plus the kit role whose bytes actually answer the request."""

    asset: KitAsset
    role_source: str


@dataclass(frozen=True)
class VisualKit:
    kit_id: str
    grammar: str
    version: int
    root: Path
    manifest: Mapping[str, Any]
    roles: Mapping[str, tuple[KitAsset, ...]]
    fallbacks: Mapping[str, tuple[str, ...]]

    # -- reads a screen or the world job needs ---------------------------------

    @property
    def label(self) -> str:
        return str(self.manifest.get("label") or self.grammar.replace("_", " ").title())

    @property
    def status(self) -> str:
        """The manifest's own status, verbatim. Never inferred from a filename or a directory."""
        return str(self.manifest.get("status") or "")

    @property
    def owner_approved(self) -> bool:
        """True only when the manifest status is one the owner has approved the art under."""
        return is_owner_approved_status(self.status)

    @property
    def approval(self) -> str:
        """The provenance approval label this kit's plates carry."""
        return APPROVAL_APPROVED if self.owner_approved else APPROVAL_OWNER_REVIEW

    @property
    def palette(self) -> dict[str, str]:
        palette = self.manifest.get("palette")
        return dict(palette) if isinstance(palette, Mapping) else {}

    @property
    def medium(self) -> str:
        return str(self.manifest.get("medium") or "")

    @property
    def composition(self) -> str:
        return str(self.manifest.get("composition") or "")

    @property
    def ocr_policy(self) -> dict[str, Any]:
        policy = self.manifest.get("ocr_policy")
        return dict(policy) if isinstance(policy, Mapping) else {}

    def assets(self, role: str) -> tuple[KitAsset, ...]:
        return tuple(self.roles.get(str(role)) or ())

    def has_role(self, role: str) -> bool:
        return bool(self.assets(role))

    def resolve(
        self,
        role: str,
        *,
        section_key: str | None = None,
        course_id: str | None = None,
    ) -> KitPlate | None:
        """The plate for *role*, walking the manifest's declared fallback chain.

        Order inside one role: an exact ``course_id`` match, then an exact ``section_key`` match,
        then an asset whose id the chain named (``course-master``), then the plate closest to the
        role's mounted aspect, manifest order breaking ties. A role that resolves through another
        role's plate says so in ``KitPlate.role_source``.
        """
        wanted_aspect = ROLE_ASPECT.get(str(role), "")
        for chain_role in self._chain(str(role)):
            assets = self.assets(chain_role)
            if assets:
                return KitPlate(self._pick(assets, section_key, course_id, wanted_aspect), chain_role)
            named = [asset for asset in self._all_assets() if asset.asset_id == chain_role]
            if named:
                return KitPlate(named[0], chain_role)
        return None

    # -- internals -----------------------------------------------------------

    def _chain(self, role: str) -> tuple[str, ...]:
        declared = self.fallbacks.get(role)
        chain = tuple(str(item) for item in (declared or DEFAULT_FALLBACKS.get(role, ())))
        return (role,) + tuple(item for item in chain if item != role)

    def _all_assets(self) -> tuple[KitAsset, ...]:
        return tuple(asset for role in KIT_ROLES for asset in self.assets(role))

    @staticmethod
    def _pick(
        assets: Sequence[KitAsset],
        section_key: str | None,
        course_id: str | None,
        wanted_aspect: str,
    ) -> KitAsset:
        if course_id:
            for asset in assets:
                if asset.course_id and asset.course_id == course_id:
                    return asset
        if section_key:
            for asset in assets:
                if asset.section_key and asset.section_key == section_key:
                    return asset
        target = _ratio(wanted_aspect)
        if target is None:
            return assets[0]
        best = min(assets, key=lambda asset: abs(asset.ratio - target))
        if abs(best.ratio - target) <= _ASPECT_TOLERANCE or len(assets) == 1:
            return best
        return assets[0]


# ── root and load ───────────────────────────────────────────────────────────

_ROOT: Path | None = None

#: One validated kit per (shelf, grammar, manifest stat) in this process. A world job that builds
#: two plates must not re-hash 29 MB of art for each one; an edited manifest changes its mtime and
#: misses the cache, so a stale kit is never served.
_CACHE: dict[tuple[str, str, int, int], VisualKit] = {}


def default_root() -> Path:
    """``<checkout>/assets/visual-kits`` — the same tree the plugin installs."""
    return Path(__file__).resolve().parent.parent / "assets" / "visual-kits"


def kits_root() -> Path:
    if _ROOT is not None:
        return _ROOT
    override = os.environ.get(ROOT_ENV)
    return Path(override).expanduser() if override else default_root()


def bind_root(path: str | os.PathLike[str] | None) -> None:
    """Bind a kit root for a test or an installed profile. ``None`` restores the default."""
    global _ROOT
    _ROOT = Path(path).expanduser() if path is not None else None
    _CACHE.clear()


def kit_dir(grammar: str) -> Path:
    return kits_root() / str(grammar)


def load_kit(grammar: str, *, root: str | os.PathLike[str] | None = None) -> VisualKit:
    """Load and fully validate one grammar's kit. Raises :class:`KitError` on any defect.

    *root* is the kit **shelf** (``assets/visual-kits``), the same shape ``kits_root()`` returns;
    the manifest is read from ``<shelf>/<grammar>/kit.json``.
    """
    shelf = Path(root).expanduser() if root is not None else kits_root()
    directory = shelf / str(grammar)
    manifest_path = directory / "kit.json"
    if not manifest_path.is_file():
        raise KitError(
            "kit_missing",
            f"no curated visual kit for grammar {grammar!r}.",
            detail=str(manifest_path),
        )
    try:
        stat = manifest_path.stat()
        cache_key = (str(directory), str(grammar), int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        cache_key = (str(directory), str(grammar), 0, 0)
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KitError(
            "kit_unreadable", f"kit.json for {grammar!r} is not readable JSON.", detail=str(exc)
        ) from exc
    if not isinstance(raw, Mapping):
        raise KitError("kit_invalid", f"kit.json for {grammar!r} is not an object.")

    version = raw.get("version")
    kit_id = str(raw.get("kit_id") or "")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise KitError("kit_invalid", f"kit.json for {grammar!r} has no positive integer version.")
    if str(raw.get("grammar") or "") != str(grammar):
        raise KitError(
            "kit_grammar_mismatch",
            f"kit.json in {grammar!r} declares grammar {raw.get('grammar')!r}.",
        )
    if kit_id != f"{grammar}@{version}":
        raise KitError(
            "kit_id_mismatch",
            f"kit.json for {grammar!r} declares kit_id {kit_id!r}, not {grammar}@{version}.",
        )
    lane = str(raw.get("lane") or "")
    if lane != DISPLAY_LANE:
        # D-006: a Press Plate pack cover is never display art. A kit that names another lane is
        # refused rather than mounted on a product surface.
        raise KitError(
            "kit_wrong_lane",
            f"kit {kit_id} declares lane {lane or '<none>'!r}; a display kit must be "
            f"{DISPLAY_LANE!r}.",
        )
    status = str(raw.get("status") or "")
    if status.startswith("rejected") or status.startswith("superseded"):
        raise KitError("kit_rejected", f"kit {kit_id} is {status!r} and is not a consumer kit.")
    # Any other status loads — a review-status kit is previewable — but approval is decided from
    # this same manifest field by ``VisualKit.owner_approved``; it is never assumed here.

    roles_raw = raw.get("roles")
    if not isinstance(roles_raw, Mapping):
        raise KitError("kit_invalid", f"kit {kit_id} declares no roles map.")
    roles: dict[str, list[KitAsset]] = {role: [] for role in KIT_ROLES}
    seen_ids: set[str] = set()
    for role, entries in roles_raw.items():
        if str(role) not in KIT_ROLES:
            raise KitError(
                "kit_unknown_role", f"kit {kit_id} declares unknown role {role!r}."
            )
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise KitError("kit_invalid", f"kit {kit_id} role {role!r} is not an array.")
        for entry in entries:
            asset = _validate_asset(
                entry, kit_id=kit_id, grammar=str(grammar), version=version,
                role=str(role), directory=directory,
            )
            if asset.asset_id in seen_ids:
                raise KitError(
                    "kit_duplicate_asset", f"kit {kit_id} declares asset {asset.asset_id!r} twice."
                )
            seen_ids.add(asset.asset_id)
            roles[str(role)].append(asset)

    if not roles["hero"]:
        raise KitError("kit_incomplete", f"kit {kit_id} declares no hero plate.")

    fallbacks_raw = raw.get("fallbacks")
    fallbacks: dict[str, tuple[str, ...]] = {}
    if isinstance(fallbacks_raw, Mapping):
        for role, chain in fallbacks_raw.items():
            if isinstance(chain, Sequence) and not isinstance(chain, (str, bytes)):
                fallbacks[str(role)] = tuple(str(item) for item in chain)

    kit = VisualKit(
        kit_id=kit_id,
        grammar=str(grammar),
        version=int(version),
        root=directory,
        manifest=dict(raw),
        roles={role: tuple(items) for role, items in roles.items() if items},
        fallbacks=fallbacks,
    )
    _CACHE[cache_key] = kit
    return kit


def kit_available(
    grammar: str, *, root: str | os.PathLike[str] | None = None
) -> tuple[VisualKit | None, dict[str, Any] | None]:
    """``(kit, None)`` when a validated kit exists, else ``(None, named_reason)``.

    A missing kit is not an exception here: the world job has to answer with a *named* unavailable
    reason, and a broken kit is a named refusal too. The reason names the grammar and the defect,
    never a generic failure.
    """
    try:
        return load_kit(grammar, root=root), None
    except KitError as exc:
        return None, {
            "reason": "curated_kit_unavailable",
            "kit_reason": exc.reason,
            "grammar": str(grammar),
            "detail": exc.detail or exc.message,
        }


def kit_approval(
    kit_id: str, *, root: str | os.PathLike[str] | None = None
) -> tuple[bool, str] | None:
    """The **current** manifest approval of a kit the caller already holds plates from.

    ``(owner_approved, status)`` for a kit that still loads, or ``None`` when the shelf no longer
    carries that exact kit (missing, rejected, or a different version). ``None`` means "cannot be
    re-read", never "approved": a caller with no current manifest keeps whatever the artifact
    recorded, and never upgrades it.
    """
    text = str(kit_id or "")
    grammar, _, version = text.partition("@")
    if not grammar or not version:
        return None
    kit, _ = kit_available(grammar, root=root)
    if kit is None or kit.kit_id != text:
        return None
    return kit.owner_approved, kit.status


def _validate_asset(
    entry: Any,
    *,
    kit_id: str,
    grammar: str,
    version: int,
    role: str,
    directory: Path,
) -> KitAsset:
    if not isinstance(entry, Mapping):
        raise KitError("kit_invalid", f"kit {kit_id} role {role!r} has a non-object entry.")
    for field in _REQUIRED_ASSET_FIELDS:
        if field not in entry:
            raise KitError(
                "kit_asset_incomplete",
                f"kit {kit_id} role {role!r} entry is missing {field!r}.",
                detail=str(entry.get("id") or ""),
            )
    asset_id = str(entry.get("id") or "")
    if not asset_id:
        raise KitError("kit_asset_incomplete", f"kit {kit_id} role {role!r} entry has no id.")
    if str(entry.get("role") or "") != role:
        raise KitError(
            "kit_asset_role_mismatch",
            f"kit {kit_id} asset {asset_id!r} is listed under {role!r} but declares "
            f"{entry.get('role')!r}.",
        )
    relative = str(entry.get("path") or "")
    if not relative or Path(relative).is_absolute():
        raise KitError(
            "kit_asset_path_invalid",
            f"kit {kit_id} asset {asset_id!r} must carry a relative path.",
            detail=relative,
        )
    target = (directory / relative).resolve()
    try:
        target.relative_to(directory.resolve())
    except ValueError as exc:
        # A manifest may not point outside its own kit directory: `../` is how a kit would reach
        # another grammar's art or a product source file.
        raise KitError(
            "kit_asset_path_invalid",
            f"kit {kit_id} asset {asset_id!r} resolves outside the kit directory.",
            detail=relative,
        ) from exc
    if not target.is_file():
        raise KitError(
            "kit_asset_missing", f"kit {kit_id} asset {asset_id!r} is not on disk.", detail=relative
        )
    data = target.read_bytes()
    declared_sha = str(entry.get("sha256") or "")
    actual_sha = hashlib.sha256(data).hexdigest()
    if declared_sha != actual_sha:
        raise KitError(
            "kit_asset_hash_mismatch",
            f"kit {kit_id} asset {asset_id!r} hashes to {actual_sha}, not {declared_sha}.",
            detail=relative,
        )
    size = entry.get("size")
    if (
        not isinstance(size, Sequence)
        or isinstance(size, (str, bytes))
        or len(size) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in size)
    ):
        raise KitError(
            "kit_asset_size_invalid", f"kit {kit_id} asset {asset_id!r} declares no [w, h] size."
        )
    actual_size = png_size(data)
    if actual_size is None:
        raise KitError(
            "kit_asset_format_unsupported",
            f"kit {kit_id} asset {asset_id!r} is not a PNG a display plate may ship.",
            detail=relative,
        )
    if (int(size[0]), int(size[1])) != actual_size:
        raise KitError(
            "kit_asset_size_mismatch",
            f"kit {kit_id} asset {asset_id!r} decodes to {actual_size[0]}x{actual_size[1]}, not "
            f"{int(size[0])}x{int(size[1])}.",
            detail=relative,
        )
    if entry.get("textless") is not True:
        # A curated plate that does not state its textless result has not been reviewed for the
        # one rule every product surface depends on.
        raise KitError(
            "kit_asset_not_textless",
            f"kit {kit_id} asset {asset_id!r} does not record textless=true.",
            detail=relative,
        )
    source = str(entry.get("source") or "")
    if not is_kit_source(source):
        # A row must say where its bytes came from, and a display kit only ships art curated for a
        # kit (``curated_kit``) or copied byte-identically from an already-approved plate
        # (``derived``, ``field_atlas@3``'s Home ground). A row with no source, or with a word that
        # claims a provider generated it, is refused rather than mounted.
        raise KitError(
            "kit_asset_source_invalid",
            f"kit {kit_id} asset {asset_id!r} records source {source or '<none>'!r}; a display "
            f"kit row must record one of {', '.join(KIT_SOURCES)}.",
            detail=relative,
        )
    return KitAsset(
        kit_id=kit_id,
        grammar=grammar,
        version=int(version),
        asset_id=asset_id,
        role=role,
        path=relative,
        abs_path=target,
        size=actual_size,
        sha256=actual_sha,
        textless=True,
        source=source,
        course_id=(str(entry["course_id"]) if entry.get("course_id") else None),
        section_key=(str(entry["section_key"]) if entry.get("section_key") else None),
    )


# ── registration ────────────────────────────────────────────────────────────


def artifact_store() -> Any:
    """The one artifact store a world job writes into. Imported here, not at module import."""
    from . import artifacts as artifacts_mod

    return artifacts_mod.ArtifactStore()


def plate_spec(plate: KitPlate, *, requested_role: str, section_key: str) -> str:
    """Content-addressed spec identity for one curated plate insertion."""
    payload = "|".join(
        (
            "curated_kit",
            plate.asset.kit_id,
            plate.asset.asset_id,
            str(requested_role),
            str(section_key),
        )
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _refresh_approval(view: dict[str, Any], kit: VisualKit) -> dict[str, Any]:
    """Re-state a reused artifact's approval from its kit's **current** manifest status.

    The store dedupes by content, so a plate registered while its kit was still
    ``built_for_owner_review`` is the same row after the owner approves that kit. Approval is read
    from the manifest, not from the row, so the row is brought up to the status observed now —
    otherwise an approved kit would stay permanently unusable from a passed review, and a withdrawn
    approval would keep claiming to be approved. Only the three approval keys change; the plate
    identity and the kit's asset facts stay exactly as first recorded.
    """
    from . import db

    provenance = view.get("provenance")
    if not isinstance(provenance, Mapping):
        return dict(view)
    if not is_kit_source(provenance.get("source")):
        return dict(view)
    if str(provenance.get("kit_id") or "") != kit.kit_id:
        return dict(view)
    if (
        provenance.get("approved") == kit.owner_approved
        and str(provenance.get("approval") or "") == kit.approval
        and str(provenance.get("kit_status") or "") == kit.status
    ):
        return dict(view)
    refreshed = dict(provenance)
    refreshed.update(
        {"approved": kit.owner_approved, "approval": kit.approval, "kit_status": kit.status}
    )
    with db.transaction() as connection:
        connection.execute(
            "UPDATE artifacts SET provenance_json = ? WHERE id = ?",
            (json.dumps(refreshed, ensure_ascii=False, sort_keys=True), str(view["artifact_id"])),
        )
    updated = dict(view)
    updated["provenance"] = refreshed
    return updated


def register_asset(
    store: Any,
    *,
    kit: VisualKit,
    plate: KitPlate,
    requested_role: str,
    section_key: str,
    course_id: str | None,
    prompt_hash: str,
    style_hash: str,
) -> dict[str, Any]:
    """Register the kit file as a content-addressed artifact and return the artifact view.

    The bytes are read from the kit and re-hashed before they are stored, so a file that changed
    after validation cannot enter the artifact store under a manifest hash. The artifact store
    dedupes on the content hash, so a second course in the same grammar reuses the same row.
    """
    from . import artifacts as artifacts_mod
    from . import db

    spec = plate_spec(plate, requested_role=requested_role, section_key=section_key)
    with db.read() as connection:
        existing = store.lookup(connection, kind="visual", spec_fingerprint=spec)
    if existing is not None:
        return _refresh_approval(existing, kit)
    data = plate.asset.abs_path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != plate.asset.sha256:
        raise KitError(
            "kit_asset_changed",
            f"kit {kit.kit_id} asset {plate.asset.asset_id!r} changed after validation.",
            detail=plate.asset.path,
        )
    provenance = {
        "role": "orientation",
        # The row's own provenance word, carried verbatim: ``curated_kit`` for art curated for this
        # kit, ``derived`` for a byte-identical copy of an already-approved plate. Claiming
        # ``curated_kit`` for the latter would be a false statement about the file.
        "source": plate.asset.source,
        "provider": plate.asset.source,
        "model": None,
        "generation_ms": 0,
        "textless": True,
        # Approval is read from the manifest's own status, never assumed from the fact that the kit
        # is on the shelf. A review-status kit registers an honest ``approved: False`` with the
        # status it declared, so a preview plate can never be mistaken for owner-approved art.
        "approved": bool(kit.owner_approved),
        "approval": kit.approval,
        "kit_status": kit.status,
        "requested_role": str(requested_role),
        "kit_role": plate.role_source,
        "section_key": str(section_key),
        "prompt_hash": str(prompt_hash),
        "style_hash": str(style_hash),
        "spec_hash": spec,
        **plate.asset.provenance(),
    }
    record = store.save(
        course_id=course_id,
        kind="visual",
        data=data,
        mime="image/png",
        provenance=provenance,
    )
    return dict(record)


# ── small helpers ───────────────────────────────────────────────────────────


def png_size(data: bytes) -> tuple[int, int] | None:
    """``(width, height)`` from a PNG's IHDR, or ``None`` when the bytes are not a PNG.

    Deliberately dependency-free: a kit plate's declared size is checked against the raster header
    on every load, and an installer must not need an imaging library to do that.
    """
    if len(data) < 33 or not data.startswith(_PNG_SIGNATURE):
        return None
    if data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    if width < 1 or height < 1:
        return None
    return int(width), int(height)


def _ratio(aspect: str) -> float | None:
    head, _, tail = str(aspect).partition(":")
    try:
        width, height = float(head), float(tail)
    except ValueError:
        return None
    return width / height if height else None


__all__ = [
    "APPROVAL_APPROVED",
    "APPROVAL_OWNER_REVIEW",
    "DEFAULT_FALLBACKS",
    "DISPLAY_LANE",
    "KIT_ROLES",
    "KIT_SOURCES",
    "OWNER_APPROVED_PREFIXES",
    "OWNER_APPROVED_STATUSES",
    "KitAsset",
    "KitError",
    "KitPlate",
    "ROLE_ASPECT",
    "ROOT_ENV",
    "VisualKit",
    "bind_root",
    "default_root",
    "is_kit_source",
    "is_owner_approved_status",
    "kit_available",
    "kit_approval",
    "kit_dir",
    "kits_root",
    "load_kit",
    "plate_spec",
    "png_size",
    "register_asset",
]
