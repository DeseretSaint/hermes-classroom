"""Host-owned media generation for authored lessons.

This module is the production caller that closes ``docs/ARCHITECTURE.md`` §"media generation is
CB-012's": the lesson pipeline may declare media, but until this module existed no caller reached
the artifact producer. It deliberately reuses :mod:`coursebook.artifacts` for the store, cache,
MIME policy, provenance and honest text fallback rather than growing a second media path.

Two boundaries are hard:

* the host owns the provider. ``HostMedia`` calls ``ctx.dispatch_tool("image_generate")`` and
  ``ctx.dispatch_tool("text_to_speech")``; the plugin never reads a provider key or calls a raw
  image/TTS API.
* generation is outside every DB transaction. Bytes are adopted before the lesson row is updated;
  a provider failure leaves a complete text lesson and an explicit degraded state.

The first slice maps the existing lesson ``media`` specs to the existing ``MediaSpec`` roles:
illustration → host image, schematic → deterministic SVG, narration → host TTS. A sourced
technical image is not synthesized; it needs a real source and permission, so it degrades to
text until that path exists.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import artifacts, db
from . import deadline as deadline_mod

#: The preview route caps one inline data URL. Larger media keeps its download handle and text
#: equivalent; a lesson page must never become a multi-megabyte JSON response by accident.
MAX_PREVIEW_BYTES = 4 * 1024 * 1024

#: A lesson may declare at most four media items (the schema cap). A job cap is still useful: a
#: retry or an eight-section course must not silently fan out into thirty provider calls.
MAX_MEDIA_PER_LESSON = 4
MAX_MEDIA_PER_JOB = 12

#: The image tool returns a provider URL. Only these hosts are accepted for the download; this is
#: a narrower allowlist than "any URL returned by a tool", not a general web fetcher.
_ALLOWED_IMAGE_HOSTS = ("fal.media", "fal.run")

_HOST_MEDIA: "HostMedia | None" = None


class MediaGenerationError(RuntimeError):
    """A host media call did not produce usable bytes. Callers degrade to text."""


class MediaTimeout(MediaGenerationError):
    """A host media tool missed its declared deadline (H-66). Callers degrade to text."""

    def __init__(self, message: str, *, tool: str, deadline_s: float) -> None:
        self.tool = str(tool)
        self.deadline_s = float(deadline_s)
        super().__init__(message)


#: Declared deadline for one host image/TTS call. Media is optional for a complete text lesson,
#: so an overrun degrades that item instead of hanging the lesson stage.
MEDIA_TOOL_TIMEOUT_SECONDS = 180.0
MEDIA_TIMEOUT_ENV = "COURSEBOOK_MEDIA_TOOL_TIMEOUT_SECONDS"


def media_tool_timeout_s() -> float:
    raw = os.environ.get(MEDIA_TIMEOUT_ENV, "").strip()
    if not raw:
        return MEDIA_TOOL_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return MEDIA_TOOL_TIMEOUT_SECONDS
    return value if value > 0 else MEDIA_TOOL_TIMEOUT_SECONDS


@dataclass
class MediaGenerationSummary:
    artifact_ids: list[str]
    usage: list[dict[str, Any]]
    generated: int = 0
    reused: int = 0
    degraded: int = 0
    skipped: int = 0

    def as_checkpoint(self) -> dict[str, Any]:
        return {
            "generated": self.generated,
            "reused": self.reused,
            "degraded": self.degraded,
            "skipped": self.skipped,
            "artifact_ids": list(self.artifact_ids),
        }


class HostMedia:
    """The two host seams Coursebook is allowed to use for media bytes."""

    def __init__(
        self,
        dispatch_tool: Callable[[str, dict[str, Any]], Any],
        *,
        timeout_s: float | None = None,
    ) -> None:
        if not callable(dispatch_tool):
            raise TypeError("HostMedia needs a callable ctx.dispatch_tool")
        self._dispatch_tool = dispatch_tool
        self._timeout_s = timeout_s

    def _deadline(self) -> float:
        return float(self._timeout_s) if self._timeout_s is not None else media_tool_timeout_s()

    def _dispatch_json(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            raw = deadline_mod.run_bounded(
                lambda: self._dispatch_tool(name, arguments),
                timeout_s=self._deadline(),
                label=str(name),
            )
        except deadline_mod.DeadlineExceeded as exc:
            raise MediaTimeout(
                f"{name} exceeded its {exc.deadline_s:g}s deadline",
                tool=str(name),
                deadline_s=exc.deadline_s,
            ) from exc
        except deadline_mod.CallCapacityExhausted as exc:
            raise MediaGenerationError(f"{name} unavailable: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - provider/host failure becomes text fallback
            raise MediaGenerationError(f"{name} failed: {type(exc).__name__}: {exc}") from exc
        if isinstance(raw, Mapping):
            return dict(raw)
        if not isinstance(raw, str):
            raise MediaGenerationError(f"{name} returned {type(raw).__name__}, not JSON")
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise MediaGenerationError(f"{name} returned non-JSON output") from exc
        if not isinstance(payload, Mapping):
            raise MediaGenerationError(f"{name} returned a non-object payload")
        return dict(payload)

    def image(self, prompt: str, *, aspect_ratio: str = "landscape") -> tuple[bytes, str]:
        payload = self._dispatch_json(
            "image_generate", {"prompt": str(prompt), "aspect_ratio": aspect_ratio}
        )
        if not payload.get("success"):
            reason = str(payload.get("error") or payload.get("error_type") or "image generation failed")
            raise MediaGenerationError(reason)
        location = payload.get("image")
        if not isinstance(location, str) or not location.strip():
            raise MediaGenerationError("image_generate returned no image")
        data = _read_image_location(location.strip())
        mime = artifacts.sniff_mime(data)
        if mime not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            raise MediaGenerationError(f"image_generate returned {mime}, not a raster image")
        return data, mime

    def speech(
        self,
        text: str,
        *,
        voice: str | None = None,
        language: str | None = None,
        instructions: str | None = None,
    ) -> tuple[bytes, str]:
        body = str(text or "").strip()
        if not body:
            raise MediaGenerationError("narration has no transcript")
        tmp_dir = db.data_root() / "media-tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="coursebook-tts-", suffix=".mp3", dir=tmp_dir)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            args: dict[str, Any] = {"text": body, "output_path": str(temp_path)}
            if voice and str(voice).strip().lower() not in ("", "default", "auto"):
                args["voice_id"] = str(voice)
            spoken_language = str(language or "").strip()
            guidance = str(instructions or "").strip()
            if spoken_language:
                guidance = (guidance + " " if guidance else "") + f"Language: {spoken_language}."
            if guidance:
                args["instructions"] = guidance
            payload = self._dispatch_json("text_to_speech", args)
            if not payload.get("success"):
                reason = str(payload.get("error") or "text_to_speech failed")
                raise MediaGenerationError(reason)
            produced = payload.get("file_path") or payload.get("file_paths")
            if isinstance(produced, list):
                produced = produced[0] if produced else None
            if not isinstance(produced, str) or not produced.strip():
                raise MediaGenerationError("text_to_speech returned no file path")
            path = Path(produced)
            if not path.is_file():
                raise MediaGenerationError("text_to_speech produced a missing file")
            data = path.read_bytes()
            if not data:
                raise MediaGenerationError("text_to_speech produced an empty file")
            mime = artifacts.sniff_mime(data)
            if not mime.startswith("audio/"):
                raise MediaGenerationError(f"text_to_speech produced {mime}, not audio")
            return data, mime
        finally:
            temp_path.unlink(missing_ok=True)


def bind_host_seam(ctx: Any) -> None:
    """Bind the host's media tools once from the agent half's ``register(ctx)``.

    A host without ``dispatch_tool`` remains unbound: generation skips media and the lesson stays
    complete as text. That is the honest bare-test and old-host behaviour.
    """
    dispatch = getattr(ctx, "dispatch_tool", None)
    global _HOST_MEDIA
    _HOST_MEDIA = HostMedia(dispatch) if callable(dispatch) else None


def host_media() -> HostMedia | None:
    return _HOST_MEDIA


def _read_image_location(location: str) -> bytes:
    """Read a local absolute path or download a host-returned image URL under an allowlist."""
    parsed = urllib.parse.urlsplit(location)
    if parsed.scheme in ("", "file"):
        path = Path(urllib.parse.unquote(parsed.path) if parsed.scheme == "file" else location)
        if not path.is_absolute():
            raise MediaGenerationError("image path is not absolute")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise MediaGenerationError(f"image file cannot be read: {exc}") from exc
    if parsed.scheme != "https":
        raise MediaGenerationError("image URL must use https")
    if parsed.username or parsed.password:
        raise MediaGenerationError("image URL must not carry credentials")
    host = (parsed.hostname or "").lower()
    if not _host_allowed(host):
        raise MediaGenerationError(f"image URL host {host!r} is not allowlisted")
    request = urllib.request.Request(location, headers={"User-Agent": "Coursebook/0.1 media"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - allowlisted host
            final = urllib.parse.urlsplit(response.geturl())
            final_host = (final.hostname or "").lower()
            if final.scheme != "https" or not _host_allowed(final_host):
                raise MediaGenerationError("image download redirected outside the allowlist")
            data = response.read(artifacts._MAX_BYTES["visual"] + 1)
    except MediaGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001 - network failure becomes text fallback
        raise MediaGenerationError(f"image download failed: {type(exc).__name__}: {exc}") from exc
    if len(data) > artifacts._MAX_BYTES["visual"]:
        raise MediaGenerationError("image exceeds the visual artifact size ceiling")
    return data


def _host_allowed(host: str) -> bool:
    return any(host == allowed or host.endswith("." + allowed) for allowed in _ALLOWED_IMAGE_HOSTS)


def _media_spec(item: Mapping[str, Any], *, locale: str | None = None) -> artifacts.MediaSpec:
    kind = str(item.get("kind") or "").strip()
    role = str(item.get("role") or ("narration" if kind == "audio" else "illustration")).strip()
    text = str(item.get("text_equivalent") or "").strip()
    if not text:
        raise MediaGenerationError("media item has no text equivalent")
    transcript = item.get("transcript")
    if role == "narration" and not transcript:
        transcript = text
    voice = item.get("voice")
    if role == "narration" and not voice:
        voice = "default"
    language = item.get("language") or locale
    if role == "narration" and not language:
        language = "en"
    facts = item.get("facts")
    if not isinstance(facts, Mapping):
        facts = {}
    return artifacts.MediaSpec(
        kind=kind,
        role=role,
        text_equivalent=text,
        prompt=str(item.get("spec") or "").strip() or None,
        source_ids=tuple(str(value) for value in (item.get("source_ids") or []) if str(value).strip()),
        permission=item.get("permission"),
        voice=str(voice) if voice else None,
        language=str(language) if language else None,
        transcript=str(transcript) if transcript else None,
        technical=bool(item.get("technical")),
        facts=dict(facts),
    )


def _schematic_rows(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = value.get("rows")
    if rows is None:
        rows = value.get("facts")
    if rows is None and value.get("label") is not None:
        rows = [value]
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        result.append(
            {
                "label": str(row.get("label") or ""),
                "value": str(row.get("value") or ""),
                "row": int(row.get("row", index)),
            }
        )
    return result


def producer_for(spec: artifacts.MediaSpec, host: HostMedia | None) -> tuple[Callable[[], bytes], str]:
    """Return ``(producer, expected_mime)`` for one validated spec.

    A missing host or an unsupported role raises ``MediaUnavailable``; the artifact layer then
    records the complete text fallback. It never fabricates a file.
    """
    if spec.kind == "visual" and spec.role == "schematic":
        rows = _schematic_rows(spec.facts)
        if not rows:
            raise MediaGenerationError("schematic needs structured facts")
        title = spec.prompt or spec.text_equivalent or "Schematic"
        return (lambda: artifacts.make_schematic_svg(title, rows)), "image/svg+xml"
    if spec.kind == "visual" and spec.role == "illustration":
        if host is None:
            raise artifacts.MediaUnavailable("no host image provider is bound")
        prompt = spec.prompt or spec.text_equivalent

        def _image() -> bytes:
            data, _mime = host.image(prompt)
            return data

        return _image, "image/png"
    if spec.kind == "audio" and spec.role == "narration":
        if host is None:
            raise artifacts.MediaUnavailable("no host TTS provider is bound")
        transcript = spec.transcript or spec.text_equivalent

        def _speech() -> bytes:
            data, _mime = host.speech(
                transcript,
                voice=spec.voice,
                language=spec.language,
                instructions="Read this lesson material clearly and naturally for a learner.",
            )
            return data

        return _speech, "audio/mpeg"
    if spec.role == "sourced_technical":
        raise artifacts.MediaUnavailable("sourced technical media needs a real cited source")
    raise artifacts.MediaUnavailable(f"no producer for {spec.kind}/{spec.role}")


def _lesson_rows(connection: Any, lesson_ids: Sequence[str]) -> list[dict[str, Any]]:
    if not lesson_ids:
        return []
    placeholders = ",".join("?" for _ in lesson_ids)
    rows = connection.execute(
        "SELECT l.*, p.course_id, d.document_json AS plan_document_json"
        " FROM gen_lessons l"
        " JOIN plans p ON p.id = l.plan_id"
        " LEFT JOIN gen_plan_documents d ON d.plan_id = l.plan_id"
        f" WHERE l.id IN ({placeholders}) ORDER BY l.plan_id, l.section_id",
        tuple(str(lesson_id) for lesson_id in lesson_ids),
    ).fetchall()
    return [dict(row) for row in rows]


def _plan_locale(document_json: Any) -> str | None:
    try:
        document = json.loads(document_json) if isinstance(document_json, str) else document_json
    except (TypeError, ValueError):
        return None
    if isinstance(document, Mapping):
        value = document.get("locale")
        return str(value) if value else None
    return None


def _usage(provider: str, model: str | None, started: float) -> dict[str, Any]:
    return {
        "provider": provider,
        "model": model,
        "tokens": {},
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def generate_for_lessons(
    connection: Any,
    *,
    lesson_ids: Sequence[str],
    job_id: str | None = None,
    host: HostMedia | None = None,
    store: artifacts.ArtifactStore | None = None,
    now: datetime | None = None,
) -> MediaGenerationSummary:
    """Generate and attach media for already-authored, validated lessons.

    Called after ``generation.run_lesson_job`` outside any transaction. Cached artifacts are
    reused by spec/source hash; provider failures are recorded on the media item as a degraded
    text fallback. Each lesson's ``media_json`` is updated in its own short transaction.
    """
    host = host if host is not None else host_media()
    if host is None:
        return MediaGenerationSummary(artifact_ids=[], usage=[], skipped=len(lesson_ids))
    store = store or artifacts.ArtifactStore()
    summary = MediaGenerationSummary(artifact_ids=[], usage=[])
    used = 0
    for row in _lesson_rows(connection, lesson_ids):
        if str(row.get("state")) != "validated":
            summary.skipped += 1
            continue
        try:
            items = json.loads(row.get("media_json") or "[]")
        except (TypeError, ValueError):
            items = []
        if not isinstance(items, list) or not items:
            continue
        locale = _plan_locale(row.get("plan_document_json"))
        changed = False
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("artifact_id"):
                summary.reused += 1
                continue
            if used >= MAX_MEDIA_PER_JOB:
                item["degraded"] = True
                item["reason"] = "media generation budget reached for this job; text equivalent kept"
                summary.skipped += 1
                changed = True
                continue
            try:
                spec = _media_spec(item, locale=locale)
                artifacts.assert_media_ok(spec)
                producer, expected_mime = producer_for(spec, host)
            except Exception as exc:  # noqa: BLE001 - an invalid spec is a text-only item
                item["degraded"] = True
                item["reason"] = f"{type(exc).__name__}: {exc}"
                summary.degraded += 1
                changed = True
                continue
            spec_fp = artifacts.spec_hash(spec.as_cache_spec())
            source_text = [spec.text_equivalent, spec.prompt or "", spec.transcript or ""]
            source_fp = artifacts.source_hash(source_text)
            cached = store.lookup(
                connection,
                kind=spec.kind,
                spec_fingerprint=spec_fp,
                source_fingerprint=source_fp,
            )
            if cached is not None:
                item.update(
                    {
                        "artifact_id": cached["artifact_id"],
                        "content_hash": cached["content_hash"],
                        "mime": cached["mime"],
                        "label": cached.get("provenance", {}).get("label", artifacts.honesty_label(spec)),
                        "degraded": False,
                        "reason": None,
                    }
                )
                summary.reused += 1
                changed = True
                continue
            started = time.monotonic()
            outcome = artifacts.produce_with_fallback(
                store,
                spec,
                producer,
                course_id=row.get("course_id"),
                mime=expected_mime,
                provenance={
                    "generator": "host.image_generate" if spec.kind == "visual" else "host.text_to_speech",
                    "model": "host-configured",
                    "prompt_hash": artifacts.spec_hash({"prompt": spec.prompt, "transcript": spec.transcript}),
                    "source_hash": source_fp,
                    "notes": f"generated for lesson {row.get('id')}" + (f" / job {job_id}" if job_id else ""),
                },
            )
            item.update(
                {
                    "label": outcome.label,
                    "degraded": outcome.degraded,
                    "reason": outcome.reason,
                    "text_equivalent": outcome.text_equivalent,
                }
            )
            if outcome.artifact is not None:
                item.update(
                    {
                        "artifact_id": outcome.artifact["artifact_id"],
                        "content_hash": outcome.artifact["content_hash"],
                        "mime": outcome.artifact["mime"],
                    }
                )
                summary.artifact_ids.append(outcome.artifact["artifact_id"])
                summary.generated += 1
                used += 1
                summary.usage.append(
                    _usage(
                        "image_generate" if spec.kind == "visual" else "text_to_speech",
                        "host-configured",
                        started,
                    )
                )
            else:
                summary.degraded += 1
            changed = True
        if changed:
            stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            with db.transaction() as write:
                write.execute(
                    "UPDATE gen_lessons SET media_json = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(items, ensure_ascii=False, sort_keys=True), stamp, row["id"]),
                )
    return summary


def seed_authored_media(connection: Any, *, lesson_run_id: str, objective_id: str, now: str) -> int:
    """Copy generated media into ``lesson_segments`` when a fresh lesson run is created.

    The chat turn writes teaching segments; this projects the already-approved authored media into
    the same durable page without creating a second store or a second renderer. A media item with
    no artifact still becomes a text segment so the learner sees the equivalent and the reason.
    """
    plan = connection.execute(
        "SELECT plan_id FROM objectives WHERE id = ?", (objective_id,)
    ).fetchone()
    if plan is None:
        return 0
    try:
        document = connection.execute(
            "SELECT plan_hash FROM gen_plan_documents WHERE plan_id = ? ORDER BY created_at DESC LIMIT 1",
            (str(plan["plan_id"]),),
        ).fetchone()
        if document is None:
            return 0
        section = connection.execute(
            "SELECT id FROM gen_plan_sections WHERE plan_id = ? AND plan_hash = ?"
            " AND json_extract(objective_refs_json, '$[0]') = ? ORDER BY ordinal LIMIT 1",
            (str(plan["plan_id"]), str(document["plan_hash"]), _objective_ordinal(connection, objective_id)),
        ).fetchone()
    except sqlite3.OperationalError:
        # A profile that has never run the generation pipeline has no gen_* tables. Opening a
        # lesson is still legal; there is simply no authored media to project.
        return 0
    if section is None:
        return 0
    lesson = connection.execute(
        "SELECT media_json FROM gen_lessons WHERE section_id = ? AND plan_hash = ?"
        " AND state = 'validated' ORDER BY version DESC LIMIT 1",
        (str(section["id"]), str(document["plan_hash"])),
    ).fetchone()
    if lesson is None:
        return 0
    try:
        items = json.loads(lesson["media_json"] or "[]")
    except (TypeError, ValueError):
        items = []
    if not isinstance(items, list) or not items:
        return 0
    max_row = connection.execute(
        "SELECT COALESCE(MAX(ordinal), 0) AS ordinal FROM lesson_segments WHERE lesson_run_id = ?",
        (lesson_run_id,),
    ).fetchone()
    ordinal = int(max_row["ordinal"] if max_row is not None else 0)
    created = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        ordinal += 1
        text = str(item.get("text_equivalent") or item.get("purpose") or "Media").strip()
        connection.execute(
            "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, artifact_id, source_id, created_at)"
            " VALUES (?, ?, ?, 'media', ?, ?, NULL, ?)",
            (
                f"seg_{uuid.uuid4().hex}",
                lesson_run_id,
                ordinal,
                text,
                item.get("artifact_id"),
                now,
            ),
        )
        created += 1
    return created


def _objective_ordinal(connection: Any, objective_id: str) -> int | None:
    row = connection.execute(
        "SELECT ordinal FROM objectives WHERE id = ?", (objective_id,)
    ).fetchone()
    return int(row["ordinal"]) if row is not None else None


def preview_artifact(artifact_id: str) -> dict[str, Any]:
    """Return a bounded inline preview for one visual/audio artifact.

    This is a host route (not a new RPC method). The route is authenticated by the plugin host;
    the artifact id is not a path and the response never contains one. The bytes are re-hashed
    before they are encoded so a changed file cannot be rendered as the approved artifact.
    """
    with db.read() as connection:
        row = connection.execute("SELECT * FROM artifacts WHERE id = ?", (str(artifact_id),)).fetchone()
    if row is None:
        return {"ok": False, "code": "NOT_FOUND", "message": "artifact not found"}
    mime = str(row["mime"] or "")
    if mime not in (
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
        "image/svg+xml",
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
    ):
        return {"ok": False, "code": "UNSUPPORTED_MEDIA", "message": f"{mime or 'unknown'} has no inline preview"}
    size = int(row["bytes"])
    if size <= 0 or size > MAX_PREVIEW_BYTES:
        return {
            "ok": False,
            "code": "PREVIEW_TOO_LARGE",
            "message": "this artifact is too large for an inline preview; use its download handle",
        }
    path = Path(str(row["path"]))
    if not path.is_file():
        return {"ok": False, "code": "NOT_FOUND", "message": "artifact file is missing on disk"}
    data = path.read_bytes()
    if len(data) != size:
        return {"ok": False, "code": "INTERNAL_ERROR", "message": "artifact size does not match its record"}
    digest = hashlib.sha256(data).hexdigest()
    if digest != str(row["content_hash"]):
        return {"ok": False, "code": "INTERNAL_ERROR", "message": "artifact hash does not match its record"}
    provenance = json.loads(row["provenance_json"] or "{}")
    return {
        "ok": True,
        "artifact_id": str(row["id"]),
        "mime": mime,
        "bytes": size,
        "label": provenance.get("label") or "Coursebook media",
        "text_equivalent": provenance.get("text_equivalent") or "",
        # Provenance the reader needs to judge a technical reference: the declared rights and the
        # cited sources, exactly as the artifact store recorded them at generation time.
        "permission": provenance.get("permission"),
        "source_ids": list(provenance.get("source_ids") or []),
        "data_url": f"data:{mime};base64," + base64.b64encode(data).decode("ascii"),
    }
