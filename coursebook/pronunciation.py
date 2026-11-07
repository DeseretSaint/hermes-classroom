"""Bounded pronunciation attempts: audio in, typed assessment out, evidence recorded separately.

The product rule (``docs/VISUAL_MEDIA_PLAN.md`` §7 and the operator decision of 2026-11-06) is
narrow on purpose:

* one **explicit** record action carries a bounded audio data URL; nothing is captured in the
  background;
* the MIME type is sniffed from bytes against a small allowlist, the byte count is capped, and the
  decoded duration is capped before inference;
* the take is written to a private temporary file, scored, and deleted in a ``finally`` block. This
  slice never retains audio at all, so a take cannot reach a pack, export, notebook or telemetry;
* recognition is Coursebook's own local recogniser (:mod:`coursebook.stt`), labelled
  ``coursebook_local_whisper``. Missing dependency/model/binary, silence or an inference error is
  ``practice_only`` — ``recorded: false`` and no attempt row. There is never a fabricated score;
* a real transcript produces a typed assessment and one row in ``pronunciation_attempts`` with
  ``evidence_class = 'model_assessed'``. That is a practice measurement, **not** verified
  pronunciation, mastery, a graded pass or a reason to advance the objective. The attempt table is
  separate from ``attempts`` (a text/selection answer) and no transition or revision is written;
* a dispute is appended to the attempt's own record and never rewrites the verdict.

The handler is revision-fenced: the caller sends the enrollment revision it saw before recording.
If the enrollment moved while the take was in flight the result is ``STALE_REVISION`` and nothing is
written. Duplicate submissions are handled twice: an identical idempotency key replays the stored
result, and a repeated ``attempt_nonce`` returns the original attempt id.
"""

from __future__ import annotations

import base64
import difflib
import hashlib
import json
import logging
import os
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Callable

from . import db, stt
from .api import RpcError
from .contracts import method_names

logger = logging.getLogger("coursebook.pronunciation")

#: One take may not exceed this many bytes on the wire (decoded). A 30 s Opus take is far smaller.
MAX_AUDIO_BYTES = 3 * 1024 * 1024
#: The contract caps the data URL at 5,000,000 characters; enforce it before base64 decoding.
MAX_DATA_URL_CHARS = 5_000_000
#: The recogniser refuses longer decoded audio (``coursebook.stt`` enforces the same bound).
MAX_DURATION_SECONDS = stt.MAX_DURATION_SECONDS
#: A practice phrase, not an essay.
MAX_TARGET_CHARS = 200
MAX_WORDS = 200
MAX_NOTE_CHARS = 1_000

#: MIME types a take may declare. The declared type must also agree with the sniffed bytes.
DECLARED_MIME = {
    "audio/wav": "audio/wav",
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/webm": "audio/webm",
    "audio/ogg": "audio/ogg",
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mpeg",
}

#: Comparison unit by language. Japanese/Chinese have no word spaces, so a character comparison is
#: the honest unit; the response says which unit was used instead of pretending both are "words".
_CHARACTER_LANGUAGES = {"ja", "zh", "yue", "th"}

MEETS_TARGET = 0.9
CLOSE = 0.6

EVIDENCE_CLASS = "model_assessed"
VERDICTS = ("meets_target", "close", "needs_practice", "unavailable")


def _kernel() -> Any:
    """The kernel's fence helpers, imported lazily to avoid an import cycle with ``domain``."""
    from . import domain

    return domain


def _reject(reason: str, message: str, **details: Any) -> RpcError:
    return RpcError.of("VALIDATION_FAILED", message, reason=reason, **details)


# ── audio envelope ──────────────────────────────────────────────────────────


def _sniff_audio(data: bytes) -> str | None:
    """Magic-byte MIME sniff for the allowlisted containers. Extension/declared type is irrelevant."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:4] == b"\x1aE\xdf\xa3":
        return "audio/webm"
    if data[:4] == b"OggS":
        return "audio/ogg"
    if data[:3] == b"ID3" or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    return None


def decode_data_url(value: Any) -> tuple[bytes, str]:
    """Decode one bounded audio data URL or raise ``VALIDATION_FAILED`` with a reason code.

    A URL, a path, a bare base64 string and a mismatched declared type are all refused. The caller
    never supplies a filesystem path.
    """
    if not isinstance(value, str) or not value.strip():
        raise _reject("not_a_data_url", "a take must be an audio data URL.")
    if len(value) > MAX_DATA_URL_CHARS:
        raise _reject("audio_too_large", "this take is too large for one attempt.")
    header, separator, body = value.partition(",")
    if not separator or not header.startswith("data:"):
        raise _reject("not_a_data_url", "a take must be an audio data URL, not a URL or a path.")
    fields = header[len("data:"):].split(";")
    declared = fields[0].strip().lower()
    if "base64" not in [field.strip().lower() for field in fields[1:]]:
        raise _reject("not_base64", "a take must be base64-encoded.")
    canonical = DECLARED_MIME.get(declared)
    if canonical is None:
        raise _reject("unsupported_mime", "that audio type is not allowed for a take.")
    try:
        data = base64.b64decode(body, validate=True)
    except (ValueError, TypeError) as exc:
        raise _reject("invalid_base64", "the audio payload is not valid base64.") from exc
    if not data:
        raise _reject("empty_audio", "the take is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise _reject("audio_too_large", "this take is too large for one attempt.")
    sniffed = _sniff_audio(data)
    if sniffed is None:
        raise _reject("unsupported_mime", "the take is not a supported audio container.")
    if sniffed != canonical:
        raise _reject(
            "mime_mismatch",
            "the declared audio type does not match the take's bytes.",
            declared=declared,
            detected=sniffed,
        )
    return data, sniffed


def _stage_take(data: bytes) -> Path:
    """Write the take to a private temp file under the plugin data directory (mode 0600)."""
    root = db.data_root() / "pronunciation-tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"take-{uuid.uuid4().hex}.bin"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def _discard_take(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:  # pragma: no cover - a locked temp file is logged, never fatal
        logger.warning("pronunciation: could not remove a temporary take")


# ── comparison ──────────────────────────────────────────────────────────────


def comparison_unit(locale: str) -> str:
    primary = str(locale or "").replace("_", "-").split("-")[0].strip().lower()
    return "character" if primary in _CHARACTER_LANGUAGES else "word"


def normalize_text(text: str) -> str:
    """NFKC, case-fold and turn punctuation/space runs into single separators."""
    folded = unicodedata.normalize("NFKC", str(text or "")).casefold()
    pieces: list[str] = []
    for char in folded:
        category = unicodedata.category(char)
        pieces.append(" " if category[0] in {"P", "Z", "C"} else char)
    return " ".join("".join(pieces).split())


def tokenize(text: str, unit: str) -> list[str]:
    normalized = normalize_text(text)
    if unit == "character":
        return [char for char in normalized if not char.isspace()]
    return normalized.split()


def _heard_confidences(transcription: stt.Transcription, unit: str, heard: list[str]) -> list[float | None]:
    """Per-heard-token confidence when the recogniser gave a 1:1 split; otherwise nulls."""
    tokens: list[str] = []
    values: list[float | None] = []
    for word in transcription.words:
        token = str(word.get("word") or "")
        for piece in tokenize(token, unit):
            tokens.append(piece)
            probability = word.get("probability")
            try:
                values.append(float(probability) if probability is not None else None)
            except (TypeError, ValueError):
                values.append(None)
    if len(tokens) == len(heard) and tokens == heard:
        return values
    return [None] * len(heard)


def _verdict(accuracy: float) -> str:
    if accuracy >= MEETS_TARGET:
        return "meets_target"
    if accuracy >= CLOSE:
        return "close"
    return "needs_practice"


def assess_transcription(transcription: stt.Transcription, target: str, locale: str) -> dict[str, Any]:
    """Deterministic word/character comparison. Never returns a pass/fail grade or mastery claim."""
    unit = comparison_unit(locale)
    expected = tokenize(target, unit)
    heard = tokenize(transcription.text, unit)
    confidences = _heard_confidences(transcription, unit, heard)

    entries: list[dict[str, Any]] = []
    matcher = difflib.SequenceMatcher(None, expected, heard, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            continue
        span = max(i2 - i1, j2 - j1)
        for offset in range(span):
            left = expected[i1 + offset] if i1 + offset < i2 else ""
            right = heard[j1 + offset] if j1 + offset < j2 else None
            matched = bool(left) and left == right
            confidence = confidences[j1 + offset] if (j1 + offset < j2 and matched) else None
            entries.append(
                {
                    "expected": left,
                    "heard": right,
                    "match": matched,
                    "confidence": confidence,
                }
            )

    denominator = max(len(expected), len(heard)) or 1
    accuracy = round(sum(1 for entry in entries if entry["match"]) / denominator, 4)
    verdict = _verdict(accuracy)
    confidence = transcription.confidence
    return {
        "transcript": transcription.text,
        "target": target,
        "locale": locale,
        "provider": transcription.provider or stt.PROVIDER,
        "model": transcription.model,
        "language": transcription.language,
        "unit": unit,
        "word_accuracy": accuracy,
        "phoneme_accuracy": None,
        "confidence": None if confidence is None else round(float(confidence), 4),
        "words": entries[:MAX_WORDS],
        "verdict": verdict,
        "evidence_class": EVIDENCE_CLASS,
    }


def unavailable_assessment(
    *, target: str, locale: str, reason: str, model: str | None = None
) -> dict[str, Any]:
    """A typed result that claims nothing: no transcript, no accuracy, verdict ``unavailable``."""
    return {
        "transcript": None,
        "target": target,
        "locale": locale,
        "provider": stt.PROVIDER,
        "model": model,
        "language": None,
        "unit": comparison_unit(locale),
        "word_accuracy": None,
        "phoneme_accuracy": None,
        "confidence": None,
        "words": [],
        "verdict": "unavailable",
        "evidence_class": EVIDENCE_CLASS,
    }


# ── persistence ─────────────────────────────────────────────────────────────


def _row(connection, sql: str, params: tuple = ()) -> Any:
    return connection.execute(sql, params).fetchone()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_load(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _context(connection, payload: dict[str, Any], expected_revision: int):
    """Resolve and fence the enrollment/objective for one attempt. No write, no bump."""
    kernel = _kernel()
    enrollment = kernel._enrollment(connection, str(payload["enrollment_id"]))
    objective = _row(connection, "SELECT * FROM objectives WHERE id = ?", (str(payload["objective_id"]),))
    if objective is None:
        raise kernel._not_found("objective", str(payload["objective_id"]))
    plan = _row(connection, "SELECT * FROM plans WHERE id = ?", (objective["plan_id"],))
    if plan is None or plan["course_id"] != enrollment["course_id"] or plan["state"] != "approved":
        raise RpcError.of(
            "VALIDATION_FAILED",
            "that objective is not part of the enrollment's approved plan.",
            field="objective_id",
            reason="objective_not_in_approved_plan",
        )
    if int(enrollment["revision"]) != int(expected_revision):
        raise kernel._stale(
            "the enrollment moved on before this take was scored.", int(enrollment["revision"])
        )
    return enrollment, objective


def _prior(connection, enrollment_id: str, nonce: str):
    return _row(
        connection,
        "SELECT * FROM pronunciation_attempts WHERE enrollment_id = ? AND attempt_nonce = ?",
        (enrollment_id, nonce),
    )


def _result_from_row(row, revision: int) -> dict[str, Any]:
    assessment = _json_load(row["assessment_json"], {})
    if not isinstance(assessment, dict) or not assessment:
        # A stored attempt without its assessment is corrupt; echo the stored columns rather than
        # invent a transcript or an accuracy.
        assessment = unavailable_assessment(
            target=str(row["target"]), locale=str(row["locale"]), reason="stored_assessment_missing",
            model=row["model"],
        )
    return {
        "status": "assessed",
        "recorded": True,
        "attempt_id": row["id"],
        "revision": int(revision),
        "assessment": assessment,
        "reason": None,
    }


def _remember_outcome(method: str, envelope: dict[str, Any], payload_hash: str, result: dict[str, Any],
                      revision: int) -> tuple[int, dict[str, Any]]:
    """Store an idempotent no-evidence outcome (unavailable/empty) without writing an attempt."""
    kernel = _kernel()
    key = envelope.get("idempotency_key")
    with db.transaction() as connection:
        replay = kernel._idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        kernel._remember(
            connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result
        )
    return revision, result


# ── commands ────────────────────────────────────────────────────────────────


def attempt(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Score one bounded take and record a separate ``model_assessed`` practice attempt."""
    db.ensure_schema()
    kernel = _kernel()
    expected_revision = kernel._require_revision(envelope)
    method = "pronunciation.attempt"
    payload_hash = kernel._payload_hash(method, payload)
    key = envelope.get("idempotency_key")

    target = str(payload.get("target") or "").strip()
    locale = str(payload.get("locale") or "").strip()
    if not target:
        raise _reject("empty_target", "a pronunciation attempt needs the target phrase.", field="target")
    if len(target) > MAX_TARGET_CHARS:
        raise _reject("target_too_long", "the target phrase is too long for one attempt.", field="target")
    if not locale:
        raise _reject("missing_locale", "a pronunciation attempt needs a locale.", field="locale")

    with db.read() as connection:
        replay = kernel._idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment, _objective = _context(connection, payload, expected_revision)
        revision = int(enrollment["revision"])
        prior = _prior(connection, str(enrollment["id"]), str(payload["attempt_nonce"]))
        if prior is not None:
            return revision, _result_from_row(prior, revision)

    audio, mime = decode_data_url(payload.get("audio_data_url"))
    take = _stage_take(audio)
    failure: str | None = None
    transcription: stt.Transcription | None = None
    try:
        adapter = stt.get_adapter()
        try:
            transcription = adapter.transcribe(
                take, language=locale, prompt=(str(payload.get("prompt")) if payload.get("prompt") else None)
            )
        except stt.SttUnavailable as exc:
            failure = exc.reason
        except Exception as exc:  # noqa: BLE001 - a recogniser bug must not become a score
            logger.warning("pronunciation: recogniser raised %s", type(exc).__name__)
            failure = "transcription_failed"
    finally:
        _discard_take(take)

    if failure is not None or transcription is None:
        reason = failure or "transcription_failed"
        assessment = unavailable_assessment(target=target, locale=locale, reason=reason)
        result = {
            "status": "unavailable",
            "recorded": False,
            "attempt_id": None,
            "revision": int(expected_revision),
            "assessment": assessment,
            "reason": reason,
        }
        return _remember_outcome(method, envelope, payload_hash, result, int(expected_revision))

    if not transcription.text.strip():
        assessment = unavailable_assessment(target=target, locale=locale, reason="empty_transcript")
        result = {
            "status": "empty",
            "recorded": False,
            "attempt_id": None,
            "revision": int(expected_revision),
            "assessment": assessment,
            "reason": "empty_transcript",
        }
        return _remember_outcome(method, envelope, payload_hash, result, int(expected_revision))

    assessment = assess_transcription(transcription, target, locale)
    attempt_id = f"prn_{uuid.uuid4().hex}"
    digest = "sha256:" + hashlib.sha256(audio).hexdigest()
    logger.info(
        "pronunciation: provider=%s bytes=%d mime=%s take=%s verdict=%s",
        assessment["provider"], len(audio), mime, digest[:19], assessment["verdict"],
    )

    with db.transaction() as connection:
        replay = kernel._idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        enrollment, _objective = _context(connection, payload, expected_revision)
        revision = int(enrollment["revision"])
        prior = _prior(connection, str(enrollment["id"]), str(payload["attempt_nonce"]))
        if prior is not None:
            return revision, _result_from_row(prior, revision)
        connection.execute(
            "INSERT INTO pronunciation_attempts (id, enrollment_id, objective_id, attempt_nonce,"
            " target, locale, transcript, provider, model, language, unit, word_accuracy,"
            " phoneme_accuracy, confidence, verdict, evidence_class, assessment_json,"
            " disputes_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, '[]', ?)",
            (
                attempt_id,
                enrollment["id"],
                str(payload["objective_id"]),
                str(payload["attempt_nonce"]),
                target,
                locale,
                assessment["transcript"],
                assessment["provider"],
                assessment["model"],
                assessment["language"],
                assessment["unit"],
                assessment["word_accuracy"],
                assessment["confidence"],
                assessment["verdict"],
                EVIDENCE_CLASS,
                _json_dump(assessment),
                db.utcnow(),
            ),
        )
        result = {
            "status": "assessed",
            "recorded": True,
            "attempt_id": attempt_id,
            "revision": revision,
            "assessment": assessment,
            "reason": None,
        }
        kernel._remember(
            connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result
        )
    return revision, result


def dispute(payload: dict[str, Any], envelope: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Append a dispute to the attempt's own record; the verdict and evidence class never change."""
    db.ensure_schema()
    kernel = _kernel()
    method = "pronunciation.dispute"
    payload_hash = kernel._payload_hash(method, payload)
    key = envelope.get("idempotency_key")
    note = str(payload.get("note") or "").strip()
    if not note:
        raise _reject("empty_note", "a dispute needs a note saying what was wrong.", field="note")
    if len(note) > MAX_NOTE_CHARS:
        raise _reject("note_too_long", "the dispute note is too long.", field="note")

    with db.transaction() as connection:
        replay = kernel._idempotent_lookup(connection, key, method, payload_hash)
        if replay is not None:
            return replay
        attempt_row = _row(
            connection,
            "SELECT * FROM pronunciation_attempts WHERE id = ? AND enrollment_id = ?",
            (str(payload["attempt_id"]), str(payload["enrollment_id"])),
        )
        if attempt_row is None:
            raise kernel._not_found("pronunciation attempt", str(payload["attempt_id"]))
        enrollment = kernel._enrollment(connection, str(payload["enrollment_id"]))
        disputes = _json_load(attempt_row["disputes_json"], [])
        if not isinstance(disputes, list):
            disputes = []
        dispute_id = f"dsp_{uuid.uuid4().hex}"
        disputes.append(
            {"id": dispute_id, "state": "open", "note": note, "created_at": db.utcnow()}
        )
        connection.execute(
            "UPDATE pronunciation_attempts SET disputes_json = ? WHERE id = ?",
            (_json_dump(disputes), attempt_row["id"]),
        )
        revision = int(enrollment["revision"])
        result = {"dispute_id": dispute_id, "state": "open", "revision": revision}
        kernel._remember(
            connection, key, method, payload_hash, envelope.get("operation_id", ""), revision, result
        )
    return revision, result


HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], tuple[int, dict[str, Any]]]] = {
    "pronunciation.attempt": attempt,
    "pronunciation.dispute": dispute,
}


def ensure_registered() -> tuple[str, ...]:
    available = set(method_names())
    registered: list[str] = []
    for method, handler in HANDLERS.items():
        if method in available:
            from . import api

            api.register_handler(method, handler)
            registered.append(method)
    return tuple(sorted(registered))


ensure_registered()
