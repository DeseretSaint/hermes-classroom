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
* an illustration is judged before it ships. The bytes are dispatched to the host's
  ``vision_analyze`` tool for a typed verdict (subject match, legible text, depicted procedure); a
  rejection is re-prompted once and then replaced by the text equivalent, and a host with no vision
  seam records ``unreviewed`` rather than a silent approval.

The first slice maps the existing lesson ``media`` specs to the existing ``MediaSpec`` roles:
illustration → host image, schematic → deterministic SVG, narration → host TTS. A sourced
technical image is not synthesized; it needs a real source and permission, so it degrades to
text until that path exists.

Two things are decided here rather than forwarded from the author's prose:

* **the prompt.** :func:`lesson_illustration_prompt` builds an editorial teaching illustration
  request — subject from the spec, composition, medium and palette, a textless block and a
  negative list — and its hash is recorded on the artifact, so a lesson's plate cannot drift
  silently. Text a learner must read is page text the UI draws, never something the image model
  is asked to paint.
* **the geometry.** :func:`figure_aspect_ratio` picks the plate by role (illustration 4:3, a
  person-facing illustration 3:4, schematic 4:3) at a 1024 px width floor, and the ratio is part
  of the cache spec so a portrait plate can never be served from a landscape artifact.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
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

#: Lesson states whose page may generate media. ``validated`` is an independent pass;
#: ``model_assessed`` is a readable page that only the author's own model assessed, so its media is
#: content, never evidence, and the page-level provenance warning travels with it. ``needs_review``
#: and rejected pages generate nothing: a page a learner cannot open has no media to deliver.
MEDIA_ELIGIBLE_LESSON_STATES = frozenset({"validated", "model_assessed"})

#: The image tool returns a provider URL. Only these hosts are accepted for the download; this is
#: a narrower allowlist than "any URL returned by a tool", not a general web fetcher.
_ALLOWED_IMAGE_HOSTS = ("fal.media", "fal.run")

#: The host tool that can look at a picture. It is asked for a typed verdict, never for prose.
REVIEW_TOOL_NAME = "vision_analyze"

#: What the reviewer must answer, and the only JSON shape this module accepts. The two hazard
#: checks exist because generated art is context: readable text becomes a spec, and a depicted
#: step or measurement becomes a procedure the learner may follow.
REVIEW_QUESTION = (
    "You are adversarially reviewing a generated illustration for a course lesson. The picture is "
    "context art only; it must never carry a procedure, a measurement or a number. Answer with one "
    "JSON object and nothing else:\n"
    '{{"subject_matches": true|false, "contains_legible_text": true|false, '
    '"depicts_procedure_or_measurement": true|false, "reason": "one short sentence"}}\n'
    "Judge strictly:\n"
    "- subject_matches: does the picture show the subject this prompt asked for: {prompt!r}?\n"
    "- contains_legible_text: any readable word, label, number, gauge, unit or annotation a learner "
    "could read as a fact. Garbled or invented text still counts.\n"
    "- depicts_procedure_or_measurement: ordered steps, hands performing a step, a tool setting, a "
    "torque value, a measurement or a safety instruction a learner could follow as authority.\n"
    "When you cannot tell, answer true for the hazard and false for subject_matches."
)

#: A correction appended to the prompt for the one re-prompt a rejection earns.
REVIEW_REVISION_RULE = (
    "Revise the illustration. It is context art for a lesson, not an instruction: show no readable "
    "text, labels, numbers, gauges, tool settings or ordered steps, and do not depict a measurement "
    "or a procedure being performed."
)

_MAX_REVIEW_REPLY_CHARS = 4000


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


# ── the review verdict: typed, bounded, defensively parsed ──────────────────
#
# The host's vision tool is not a verdict API: one host path answers in prose, another attaches the
# picture to the conversation and returns an envelope with no text at all. This parser accepts only
# the typed JSON object the question asks for and turns everything else into ``unreviewed`` with a
# reason — a vision call that did not answer has not approved anything.

_FENCED_BLOCK = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)
_TRUE_WORDS = frozenset({"true", "yes", "y", "1", "pass", "matches"})
_FALSE_WORDS = frozenset({"false", "no", "n", "0", "fail", "mismatch"})


def _review_text(raw: Any) -> tuple[str | None, str | None]:
    """``(text, problem)``: the reviewer's answer as text, or why there is no text answer."""
    if isinstance(raw, str):
        return raw, None
    if isinstance(raw, Mapping):
        for key in ("analysis", "text", "content", "result", "description", "message"):
            value = raw.get(key)
            if isinstance(value, Mapping):
                return json.dumps(value, ensure_ascii=False), None
            if isinstance(value, str) and value.strip():
                return value, None
        if raw.get("success") is False:
            detail = str(raw.get("error") or raw.get("error_type") or "no detail")
            return None, f"the host vision tool reported failure ({detail[:200]})"
        if raw.get("error"):
            return None, f"the host vision tool reported an error ({str(raw['error'])[:200]})"
        if raw.get("_multimodal") is not None:
            return None, (
                "the host vision tool attached the picture to the conversation instead of returning "
                "a text verdict"
            )
        return None, "the host vision tool returned no text verdict"
    return None, f"the host vision tool returned {type(raw).__name__}, not a verdict"


def _review_payload(text: str) -> Mapping[str, Any] | None:
    """The first JSON object in ``text``, tolerant of fences and prose around it.

    ``raw_decode`` from every ``{`` is deliberate: a regex that assumes the first brace opens the
    object breaks on a reply like ``"Here {is} my verdict: {...}"``, and the answer must be parsed
    exactly as the model wrote it rather than reshaped.
    """
    fenced = _FENCED_BLOCK.search(text)
    candidates = [fenced.group(1)] if fenced is not None else []
    candidates.append(text)
    decoder = json.JSONDecoder()
    attempts = 0
    for candidate in candidates:
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            attempts += 1
            if attempts > 32:  # a reply full of braces is not a verdict; stop scanning
                return None
            try:
                payload, _end = decoder.raw_decode(candidate[index:])
            except ValueError:
                continue
            if isinstance(payload, Mapping):
                return payload
    return None


def _review_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE_WORDS:
            return True
        if text in _FALSE_WORDS:
            return False
        return None
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


def parse_review_verdict(raw: Any) -> dict[str, Any]:
    """Turn one vision-tool answer into ``{state, reasons}``. Never raises, never flatters."""
    text, problem = _review_text(raw)
    if problem is not None:
        return artifacts.unreviewed_review(problem)
    payload = _review_payload((text or "")[:_MAX_REVIEW_REPLY_CHARS])
    if payload is None:
        return artifacts.unreviewed_review(
            "the vision tool returned no parseable JSON verdict; the illustration was not reviewed"
        )
    if not any(key in payload for key in artifacts.REVIEW_CHECKS):
        # The registry answers an unknown tool with a JSON error body; that body is the honest
        # reason, not a verdict.
        detail = str(payload.get("error") or payload.get("error_type") or "").strip()
        if payload.get("success") is False or detail:
            return artifacts.unreviewed_review(
                f"the host vision tool reported failure ({detail[:200] or 'no detail'})"
            )
        return artifacts.unreviewed_review(
            "the vision tool returned no typed verdict; the illustration was not reviewed"
        )
    checks: dict[str, bool] = {}
    missing: list[str] = []
    for key in artifacts.REVIEW_CHECKS:
        value = _review_bool(payload.get(key))
        if value is None:
            missing.append(key)
        else:
            checks[key] = value
    if missing:
        return artifacts.unreviewed_review(
            f"the vision verdict omitted {', '.join(sorted(missing))}; the illustration was not reviewed"
        )
    reason = " ".join(str(payload.get("reason") or "").split())[:400]
    failures: list[str] = []
    if not checks["subject_matches"]:
        failures.append("the picture does not show the subject the prompt asked for")
    if checks["contains_legible_text"]:
        failures.append("the picture contains legible text or numbers a learner could read as a fact")
    if checks["depicts_procedure_or_measurement"]:
        failures.append(
            "the picture depicts a procedure or measurement and could be read as authority"
        )
    if failures:
        return artifacts.review_record("rejected", failures + ([reason] if reason else []))
    return artifacts.review_record(
        "approved",
        [
            reason
            or "the picture matches the prompt and shows no legible text, procedure or measurement"
        ],
    )


@dataclass
class MediaGenerationSummary:
    artifact_ids: list[str]
    usage: list[dict[str, Any]]
    generated: int = 0
    reused: int = 0
    degraded: int = 0
    skipped: int = 0
    #: Illustrations the vision gate approved in this run, and illustrations it rejected and
    #: replaced with their text equivalent. Reported so a job checkpoint shows the gate's work.
    reviewed: int = 0
    rejected: int = 0

    def as_checkpoint(self) -> dict[str, Any]:
        return {
            "generated": self.generated,
            "reused": self.reused,
            "degraded": self.degraded,
            "skipped": self.skipped,
            "reviewed": self.reviewed,
            "rejected": self.rejected,
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

    def _dispatch_raw(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch one host tool with the media deadline, returning its raw answer.

        Unlike :meth:`_dispatch_json` this does not demand a JSON object: the vision tool answers
        in prose on one host path and in an envelope on another, and the caller parses defensively.
        """
        try:
            return deadline_mod.run_bounded(
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
        except Exception as exc:  # noqa: BLE001 - a review failure becomes unreviewed, never fatal
            raise MediaGenerationError(f"{name} failed: {type(exc).__name__}: {exc}") from exc

    def review_image(
        self,
        data: bytes,
        *,
        mime: str,
        prompt: str,
        text_equivalent: str = "",
    ) -> dict[str, Any]:
        """Ask the host's vision tool for a typed, adversarial verdict on one generated picture.

        The bytes travel as a ``data:`` URL so no temporary path is written for the host to read.
        Every failure mode (no tool, tool error, native-mode envelope, unparseable prose) returns
        ``unreviewed`` with its reason — this seam can never manufacture an approval.
        """
        subject = str(prompt or "").strip() or str(text_equivalent or "").strip()
        if not subject:
            return artifacts.unreviewed_review("the illustration has no prompt to review against")
        if mime not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            return artifacts.unreviewed_review(f"the host vision tool cannot review {mime}")
        image_url = "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")
        question = REVIEW_QUESTION.format(prompt=subject[:600])
        try:
            raw = self._dispatch_raw(
                REVIEW_TOOL_NAME, {"image_url": image_url, "question": question}
            )
        except MediaGenerationError as exc:
            return artifacts.unreviewed_review(f"the host vision tool is unavailable ({exc})")
        return parse_review_verdict(raw)

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
    prompt = str(item.get("spec") or "").strip() or None
    return artifacts.MediaSpec(
        kind=kind,
        role=role,
        text_equivalent=text,
        prompt=prompt,
        source_ids=tuple(str(value) for value in (item.get("source_ids") or []) if str(value).strip()),
        permission=item.get("permission"),
        voice=str(voice) if voice else None,
        language=str(language) if language else None,
        transcript=str(transcript) if transcript else None,
        technical=bool(item.get("technical")),
        facts=dict(facts),
        # Geometry is chosen here, never by the author: an item cannot ask for a ratio the role
        # does not have, and the choice is part of the cache key so a 3:4 plate never reuses a 4:3
        # artifact.
        aspect_ratio=figure_aspect_ratio(kind, role, f"{prompt or ''} {text}"),
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


# ── Lesson figure geometry and the built illustration prompt ─────────────────
#
# Two decisions this module used to leave to prose. Every lesson figure was requested landscape,
# and the author's own spec sentence was forwarded to the image model unchanged; the model painted
# labels and gauge numerals, the review gate rejected on legible text, and the picture was dropped.
# Geometry and prompt are chosen here, and both are hashed into the artifact's provenance.

#: The plate width a lesson figure is requested at least. The Desktop renders the figure in the
#: prose column; below this the smallest label-level detail is not legible at 2x.
MIN_FIGURE_WIDTH_PX = 1024

#: Role-based geometry (item 30). A 4:3 plate gives a teaching illustration room for a subject and
#: a quiet field to one side; a person-facing subject is portrait so the figure is not cropped at
#: the shoulders; a schematic is read as a table, so it stays 4:3 and is never stretched.
ILLUSTRATION_ASPECT = "4:3"
PORTRAIT_ASPECT = "3:4"
SCHEMATIC_ASPECT = "4:3"

#: Words that name a subject a reader faces rather than an object beside them. A lookup, not a
#: classifier: the default is the landscape plate and only a named person changes it.
_PORTRAIT_SUBJECT = re.compile(
    r"\b(portrait|person|people|learner|student|child|children|worker|mechanic|technician|"
    r"operator|speaker|face|hands)\b",
    re.IGNORECASE,
)


def figure_aspect_ratio(kind: str, role: str, text: str = "") -> str | None:
    """The ratio a media item is requested at, or ``None`` when the medium has no plate.

    Chosen by role, never by the author: an illustration is 4:3, a person-facing illustration is
    3:4, and a schematic (or a cited source scanned into the same frame) is 4:3. ``text`` is the
    spec sentence plus its text equivalent, which is where "portrait" or the person is named.
    """
    if kind != "visual":
        return None
    if role in ("schematic", "sourced_technical"):
        return SCHEMATIC_ASPECT
    if _PORTRAIT_SUBJECT.search(str(text or "")):
        return PORTRAIT_ASPECT
    return ILLUSTRATION_ASPECT


#: The illustration prompt's own version. Bumping it re-hashes every plate request, so a change to
#: the wording is visible in provenance instead of silently repainting an approved lesson.
ILLUSTRATION_PROMPT_VERSION = "illustration-prompt.v1"

#: One medium, one palette, one line: an editorial teaching illustration, not a photograph and not
#: a chart. The same discipline the world lane's art bible sets (``world.py``), scaled to a plate
#: that sits inside a lesson rather than on a cover.
ILLUSTRATION_MEDIUM = (
    "a flat editorial teaching illustration: opaque gouache shapes with a warm ink contour, on warm "
    "paper, with no gradient, glow, glass or photographic texture"
)
ILLUSTRATION_PALETTE = (
    "a warm paper ground (#f7f1e4), ochre (#7b4b0a), field green (#2f6047), coral (#9c2e1c) and a "
    "single dark ink line, at most five pigments and no colour outside them"
)
ILLUSTRATION_COMPOSITION = (
    "the subject sits off-centre in the lower two thirds, whole and uncropped, with a quiet "
    "low-detail field on one side where the page draws its caption"
)
ILLUSTRATION_COMPOSITION_PORTRAIT = (
    "a vertical composition: the figure is centred, whole and uncropped, with quiet air above and "
    "below it and its face turned toward the learner"
)

#: The textless block. The picture carries the scene; every word a learner reads is page text the
#: UI draws afterwards, because a model that paints a label garbles it into a false fact.
ILLUSTRATION_TEXTLESS = (
    "The plate contains no words at all: no title, no caption, no label, no lettering, no numbers "
    "and no pseudo-text. Anything a learner must read — a label, a number, a callout — is page "
    "text drawn by the product UI over the picture, never painted into it."
)

#: The negative list. Each entry restates one way a picture becomes a spec: text a learner could
#: read as fact, a measurement, a step, or a piece of UI chrome.
ILLUSTRATION_NEGATIVES: tuple[str, ...] = (
    "no text",
    "no letters, words or labels",
    "no numbers, numerals or measurements",
    "no arrows or callout markers",
    "no watermark, signature or logo",
    "no user interface, buttons, panels or frames",
    "no pseudo-text or symbols that resemble letters",
    "no gauges, dials or tool settings a learner could read as a fact",
    "no depicted procedure, ordered steps or hands performing a step",
)

#: A clause that asks for text *inside* the picture. The authoring prompt forbids it, but a spec
#: that asks anyway is rewritten here rather than forwarded: the request is dropped from the
#: subject and the negative list still refuses the labels.
_TEXT_REQUEST = re.compile(
    r"\b(labels?|labell?ed|labell?ing|labeling|lettering|text|words?|numbers?|numbered|"
    r"numerals?|arrows?|callouts?|captions?|annotations?|annotated|titles?)\b",
    re.IGNORECASE,
)
_LABEL_ADJECTIVE = re.compile(r"\b(labell?ed|numbered|annotated)\b", re.IGNORECASE)
_LABEL_TAIL = re.compile(r"\s+(?:with|showing|including|that\s+shows|and\s+with)\b.*$", re.IGNORECASE)
#: "An editorial illustration of …" is the author naming the medium, not the subject. The builder
#: supplies the medium, so the preamble is cut and "The picture shows a workshop bench" reads as
#: one instruction instead of two.
_SUBJECT_PREAMBLE = re.compile(
    r"^(?:an?\s+|the\s+)?(?:editorial\s+)?(?:teaching\s+)?"
    r"(?:illustration|picture|image|drawing|sketch|scene|visual|artwork)"
    r"\s+(?:of|showing|that\s+shows)\s+",
    re.IGNORECASE,
)


def _illustration_subject(spec: artifacts.MediaSpec) -> str:
    """The subject clause of ``spec``, with any request for drawn text rewritten out of it.

    A spec is prose an author wrote, and an author sometimes asks for labels ("a bench with the
    parts labelled"). Text is drawn afterwards, so the request is removed rather than forwarded:
    a labelling adjective is stripped from the subject it modified, a clause that is only the
    request is dropped, and a request tail is cut. The result is bounded, because the model reads
    one sentence and the archive keeps the spec itself.
    """
    raw = str(spec.prompt or "").strip() or str(spec.text_equivalent or "").strip()
    if not raw:
        return "the subject this lesson teaches"
    clauses = [part.strip(" .") for part in re.split(r"[,;]", raw) if part.strip(" .")]
    kept: list[str] = []
    for clause in clauses:
        if _TEXT_REQUEST.search(clause) is None:
            kept.append(clause)
            continue
        if kept:
            # A later clause is the request ("with labels on each part"); dropping it whole keeps
            # the subject intact.
            continue
        stripped = _LABEL_TAIL.sub("", _LABEL_ADJECTIVE.sub("", clause)).strip(" ,;.")
        if stripped:
            kept.append(stripped)
    subject = ", ".join(kept) or str(spec.text_equivalent or "").strip() or "the subject this lesson teaches"
    subject = _SUBJECT_PREAMBLE.sub("", " ".join(subject.split()))
    # "A workshop bench" reads as a new sentence after "The picture shows"; only the article is
    # lowered, so a proper noun in the subject keeps its capital.
    subject = re.sub(r"^(A|An|The)\b", lambda found: found.group(1).lower(), subject)
    # Removing an adjective can leave a double space; the model reads one clean sentence.
    return " ".join(subject.split())[:400] or "the subject this lesson teaches"


@dataclass(frozen=True, slots=True)
class LessonIllustrationPrompt:
    """One built illustration request, with the hash an artifact records."""

    prompt: str
    negative_prompt: str
    subject: str
    aspect_ratio: str
    prompt_hash: str
    prompt_version: str = ILLUSTRATION_PROMPT_VERSION


def lesson_illustration_prompt(spec: artifacts.MediaSpec) -> LessonIllustrationPrompt:
    """Build the illustration prompt: subject, composition, medium and palette, textless, negatives.

    Modelled on :func:`coursebook.world.build_prompt`: the author's sentence supplies the *subject*
    and nothing else. Composition follows the plate ratio, the medium and palette are the house
    style, and the textless block plus the negative list are fixed. The hash covers every block, so
    the same lesson cannot drift: a prompt change re-hashes the request and provenance shows it.
    """
    subject = _illustration_subject(spec)
    aspect = spec.aspect_ratio or figure_aspect_ratio(
        spec.kind, spec.role, f"{spec.prompt or ''} {spec.text_equivalent}"
    )
    composition = (
        ILLUSTRATION_COMPOSITION_PORTRAIT if aspect == PORTRAIT_ASPECT else ILLUSTRATION_COMPOSITION
    )
    negative = "; ".join(ILLUSTRATION_NEGATIVES)
    prompt = (
        "Textless editorial teaching illustration. "
        f"The picture shows {subject}. "
        f"It is composed as {composition}. "
        f"The medium is {ILLUSTRATION_MEDIUM}, and the palette is {ILLUSTRATION_PALETTE}. "
        f"{ILLUSTRATION_TEXTLESS} "
        f"Avoid everything in this list: {negative}."
    )
    payload = {
        "prompt_version": ILLUSTRATION_PROMPT_VERSION,
        "subject": subject,
        "composition": composition,
        "medium": ILLUSTRATION_MEDIUM,
        "palette": ILLUSTRATION_PALETTE,
        "aspect_ratio": aspect,
        "negative": list(ILLUSTRATION_NEGATIVES),
    }
    return LessonIllustrationPrompt(
        prompt=prompt,
        negative_prompt=negative,
        subject=subject,
        aspect_ratio=str(aspect),
        prompt_hash=artifacts.spec_hash(payload),
    )


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
        # Rendered at the same width floor every lesson figure is requested at, so the recorded
        # ``min_width_px`` is a fact about the bytes rather than a wish.
        return (
            lambda: artifacts.make_schematic_svg(title, rows, width=MIN_FIGURE_WIDTH_PX)
        ), "image/svg+xml"
    if spec.kind == "visual" and spec.role == "illustration":
        # Both an illustration and the context art beside a procedure's authority visual are this
        # role, and both take the built prompt: the author's sentence is a subject, never the whole
        # request.
        if host is None:
            raise artifacts.MediaUnavailable("no host image provider is bound")
        built = lesson_illustration_prompt(spec)

        def _image() -> bytes:
            data, _mime = host.image(built.prompt, aspect_ratio=built.aspect_ratio)
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


def revision_prompt(prompt: str, review: Mapping[str, Any] | None = None) -> str:
    """The one corrective re-prompt a rejected illustration earns.

    It restates the context-art rule and carries the reviewer's reasons, so the second attempt is a
    different request rather than the same prompt hoping for a different sample.
    """
    base = str(prompt or "").strip()
    reasons = "; ".join(str(reason) for reason in (review or {}).get("reasons") or [])[:600]
    revised = f"{base}. {REVIEW_REVISION_RULE}" if base else REVIEW_REVISION_RULE
    if reasons:
        revised = f"{revised} The previous attempt was rejected: {reasons}."
    return revised


def reviewer_for(
    spec: artifacts.MediaSpec, host: "HostMedia | None"
) -> tuple[Callable[[bytes], dict[str, Any]], Callable[[dict[str, Any]], bytes]] | None:
    """``(review, regenerate)`` for a generated illustration, or ``None`` when it is not gated.

    Only a host-generated illustration is reviewed: a deterministic schematic is rendered from
    structured facts, and narration is read from its transcript, so neither needs a picture judged.
    A host object without ``review_image`` (an older host, or a duck-typed test double) returns
    ``None`` and the artifact layer records ``unreviewed`` instead of pretending it was approved.
    """
    if spec.kind != "visual" or spec.role != "illustration" or host is None:
        return None
    review_method = getattr(host, "review_image", None)
    if not callable(review_method):
        return None
    prompt = spec.prompt or spec.text_equivalent

    def _review(data: bytes) -> dict[str, Any]:
        verdict = review_method(
            data,
            mime=artifacts.sniff_mime(data),
            prompt=prompt,
            text_equivalent=spec.text_equivalent,
        )
        if not isinstance(verdict, Mapping):
            return artifacts.unreviewed_review("the host vision tool returned no verdict object")
        return dict(verdict)

    def _regenerate(review: dict[str, Any]) -> bytes:
        # Re-prompt from the *built* request, not the author's sentence: a retry that dropped the
        # textless block and the negative list would repaint the same defect.
        built = lesson_illustration_prompt(spec)
        data, _mime = host.image(
            revision_prompt(built.prompt, review), aspect_ratio=built.aspect_ratio
        )
        return data

    return _review, _regenerate


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
    """Generate and attach media for authored lessons a learner can open.

    Called after ``generation.run_lesson_job`` outside any transaction. Both ``validated`` and
    ``model_assessed`` pages are eligible (see ``MEDIA_ELIGIBLE_LESSON_STATES``); a ``needs_review``
    or rejected page is skipped. An artifact generated for a model-assessed page records that
    state in its own provenance and is never labelled as independently validated. Cached artifacts
    are reused by spec/source hash; provider failures are recorded on the media item as a degraded
    text fallback. Each lesson's ``media_json`` is updated in its own short transaction.
    """
    host = host if host is not None else host_media()
    if host is None:
        return MediaGenerationSummary(artifact_ids=[], usage=[], skipped=len(lesson_ids))
    store = store or artifacts.ArtifactStore()
    summary = MediaGenerationSummary(artifact_ids=[], usage=[])
    used = 0
    for row in _lesson_rows(connection, lesson_ids):
        lesson_state = str(row.get("state"))
        if lesson_state not in MEDIA_ELIGIBLE_LESSON_STATES:
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
                cached_provenance = cached.get("provenance") or {}
                cached_review = cached_provenance.get("review")
                if spec.kind == "visual" and spec.role == "illustration" and not isinstance(
                    cached_review, Mapping
                ):
                    # An artifact written before the gate has no verdict. The bytes still ship —
                    # they passed size/MIME/render safety — but the item says unreviewed, never
                    # nothing at all, so a reader cannot mistake silence for approval.
                    cached_review = artifacts.unreviewed_review(
                        "the cached illustration predates the review gate; it has no recorded review"
                    )
                item.update(
                    {
                        "artifact_id": cached["artifact_id"],
                        "content_hash": cached["content_hash"],
                        "mime": cached["mime"],
                        "label": cached_provenance.get("label", artifacts.honesty_label(spec)),
                        "degraded": False,
                        "reason": None,
                        # The verdict recorded when these bytes were produced travels with the
                        # reuse: a cache hit never upgrades an unreviewed picture to approved.
                        "review": cached_review,
                    }
                )
                summary.reused += 1
                changed = True
                continue
            started = time.monotonic()
            gated = reviewer_for(spec, host)
            built_prompt = (
                lesson_illustration_prompt(spec)
                if spec.kind == "visual" and spec.role == "illustration"
                else None
            )
            # The prompt hash is the *built* request for an illustration and the author's own text
            # for anything else, so two lessons with the same spec sentence but a different style
            # block cannot share a provenance record without saying so.
            prompt_record = (
                {"prompt_hash": built_prompt.prompt_hash, "prompt_version": built_prompt.prompt_version}
                if built_prompt is not None
                else {
                    "prompt_hash": artifacts.spec_hash(
                        {"prompt": spec.prompt, "transcript": spec.transcript}
                    )
                }
            )
            geometry: dict[str, Any] = {}
            if spec.kind == "visual":
                geometry = {
                    "aspect_ratio": spec.aspect_ratio,
                    "min_width_px": MIN_FIGURE_WIDTH_PX,
                }
            outcome = artifacts.produce_with_fallback(
                store,
                spec,
                producer,
                course_id=row.get("course_id"),
                mime=expected_mime,
                provenance={
                    "generator": "host.image_generate" if spec.kind == "visual" else "host.text_to_speech",
                    "model": "host-configured",
                    **prompt_record,
                    **geometry,
                    "source_hash": source_fp,
                    # The page's own provenance travels with the bytes: a model-assessed lesson's
                    # media must never read as independently validated evidence.
                    "lesson_id": str(row.get("id")),
                    "lesson_state": lesson_state,
                    "independent": lesson_state == "validated",
                    "notes": f"generated for lesson {row.get('id')}" + (f" / job {job_id}" if job_id else ""),
                },
                reviewer=gated[0] if gated is not None else None,
                regenerate=gated[1] if gated is not None else None,
            )
            item.update(
                {
                    "label": outcome.label,
                    "degraded": outcome.degraded,
                    "reason": outcome.reason,
                    "text_equivalent": outcome.text_equivalent,
                }
            )
            if outcome.review is not None:
                item["review"] = outcome.review
                if outcome.review.get("state") == "approved":
                    summary.reviewed += 1
                elif outcome.review.get("state") == "rejected":
                    summary.rejected += 1
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
        "SELECT media_json, state FROM gen_lessons WHERE section_id = ? AND plan_hash = ?"
        " AND state IN ('validated', 'model_assessed') ORDER BY version DESC LIMIT 1",
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
    # Containment first: an ``artifacts`` row is a record, not a warrant. Only a file inside this
    # profile's own artifact store may be served, so a row (written by a compromised local
    # process, a stale row, or a hand-edited db) cannot name ``/etc/passwd`` or another profile's
    # media. Symlinks are resolved, so a link inside the store pointing outside is refused too.
    if not db.within(path, artifacts.read_root()):
        return {
            "ok": False,
            "code": "NOT_FOUND",
            "message": "artifact file is outside this profile's artifact store",
        }
    if not path.is_file():
        return {"ok": False, "code": "NOT_FOUND", "message": "artifact file is missing on disk"}
    # Compare the on-disk size before reading: the row's ``bytes`` is the claim being checked, so
    # it cannot bound the read, and an inline preview must never load an unbounded file.
    try:
        on_disk = path.stat().st_size
    except OSError:
        return {"ok": False, "code": "NOT_FOUND", "message": "artifact file is missing on disk"}
    if on_disk != size:
        return {"ok": False, "code": "INTERNAL_ERROR", "message": "artifact size does not match its record"}
    data = path.read_bytes()
    if len(data) != size:
        return {"ok": False, "code": "INTERNAL_ERROR", "message": "artifact size does not match its record"}
    digest = hashlib.sha256(data).hexdigest()
    if digest != artifacts.bare_hash(row["content_hash"]):
        return {"ok": False, "code": "INTERNAL_ERROR", "message": "artifact hash does not match its record"}
    # Re-derive the type from the bytes and demand they are render-safe. The hash only proves the
    # file matches the row; it says nothing about whether the row's ``mime`` describes the file.
    # ``sniff_mime`` refuses a declared type that the magic bytes contradict, and
    # ``assert_render_safe`` refuses active content (script/event/foreign markup), so HTML declared
    # as ``image/svg+xml`` cannot become an inline ``data:`` URL.
    try:
        detected = artifacts.sniff_mime(data, mime)
        artifacts.assert_render_safe(data, detected)
    except artifacts.UnsafeMedia:
        return {
            "ok": False,
            "code": "UNSAFE_MEDIA",
            "message": "artifact bytes are not the declared, render-safe media type",
        }
    provenance = json.loads(row["provenance_json"] or "{}")
    return {
        "ok": True,
        "artifact_id": str(row["id"]),
        "mime": detected,
        "bytes": size,
        "label": provenance.get("label") or "Coursebook media",
        "text_equivalent": provenance.get("text_equivalent") or "",
        # Provenance the reader needs to judge a technical reference: the declared rights and the
        # cited sources, exactly as the artifact store recorded them at generation time.
        "permission": provenance.get("permission"),
        "source_ids": list(provenance.get("source_ids") or []),
        # H-137 (H-73 §7): additive rights keys. ``null`` when the artifact recorded no licence;
        # an older Desktop ignores both. A pack-authored narration carries the pack's own licence
        # and attribution, so the reader can see whose bytes these are.
        "license_id": provenance.get("license_id") or None,
        "attribution": provenance.get("attribution") or None,
        # H-169: the page's provenance travels with the bytes. ``None`` on an older artifact that
        # recorded none; a reader must not infer "validated" from its absence.
        "lesson_state": provenance.get("lesson_state") or None,
        "independent": provenance.get("independent") if "independent" in provenance else None,
        # Geometry the bytes were requested at, so a reader can tell a portrait plate from a
        # landscape one and know the width floor the figure was generated for.
        "aspect_ratio": provenance.get("aspect_ratio") or None,
        "min_width_px": provenance.get("min_width_px") or None,
        # The adversarial verdict the illustration earned when it was generated. ``None`` for a
        # medium that is not reviewed; the Desktop can show "unreviewed" rather than imply a pass.
        "review": provenance.get("review") if "review" in provenance else None,
        "data_url": f"data:{detected};base64," + base64.b64encode(data).decode("ascii"),
    }
