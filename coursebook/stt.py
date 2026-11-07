"""Coursebook's own local speech recogniser for pronunciation practice.

This module exists because M3-S1 proved there is **no documented plugin seam** to the host's
configured speech-to-text (``docs/PRONUNCIATION-SEAM.md``). The operator approved the
plugin-owned local fallback on 2026-11-06. The rules that fallback must keep:

* the plugin never reads a provider key, never registers a ``TranscriptionProvider`` and never
  sets ``stt.provider``;
* the provider label is always ``coursebook_local_whisper`` — never "host STT";
* nothing leaves the machine: ``faster-whisper`` runs on CPU with an int8 model cached under the
  plugin data directory. The only network call is the one-time model-weight download from
  Hugging Face when the cache is empty (weights only, no audio);
* missing dependency, missing ``ffmpeg``, missing model or an inference failure raises
  :class:`SttUnavailable` with a bounded reason code. It never invents a transcript or a score.

Decoding note (live finding, 2026-11-06): the ``av`` wheel pinned for Python 3.14 raises
``TypeError: open() got an unexpected keyword argument 'metadata_errors'`` on MP3 input. We do not
pin or downgrade ``av``; instead we decode with the host ``ffmpeg`` binary to 16 kHz mono signed
16-bit PCM and hand ``WhisperModel.transcribe`` a float32 ``numpy`` array. This also gives us a
reliable duration before inference, so the bounded-attempt rule is enforced before model work.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger("coursebook.stt")

#: The provider string recorded on every assessment and attempt row. Deliberately not a host
#: provider name: this is Coursebook's own recogniser.
PROVIDER = "coursebook_local_whisper"

#: Model size, overridable by the operator without a provider key or a config key.
DEFAULT_MODEL = os.environ.get("COURSEBOOK_WHISPER_MODEL", "small").strip() or "small"

#: ffmpeg output format. 16 kHz mono s16le is what Whisper expects before the float conversion.
SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2

#: The bounded attempt: never decode or infer more than this.
MAX_DURATION_SECONDS = 30.0
MAX_PCM_BYTES = SAMPLE_RATE * BYTES_PER_SAMPLE * (int(MAX_DURATION_SECONDS) + 1)
DECODE_TIMEOUT_SECONDS = 60

_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_MODEL_LOCK = threading.Lock()


class SttUnavailable(RuntimeError):
    """No transcript could be produced. ``reason`` is a bounded, log-safe code.

    The text of the exception is for logs only; callers must expose ``reason``, never ``str()``,
    because it may carry a filesystem path or a library message.
    """

    def __init__(self, reason: str) -> None:
        self.reason = str(reason)
        super().__init__(self.reason)


@dataclass(frozen=True)
class Transcription:
    """One real transcript plus the provenance the assessment record needs."""

    text: str
    provider: str = PROVIDER
    model: str = DEFAULT_MODEL
    language: str | None = None
    confidence: float | None = None
    words: tuple[dict[str, Any], ...] = ()
    duration: float | None = None


class SttAdapter(Protocol):
    """The seam :mod:`coursebook.pronunciation` scores through.

    Unit tests inject a fake; production uses :class:`LocalWhisperAdapter`. A test double must
    return a :class:`Transcription` or raise :class:`SttUnavailable` — never an empty success that
    the caller could mistake for a pass.
    """

    def transcribe(self, path: Path, *, language: str | None = None,
                   prompt: str | None = None) -> Transcription:  # pragma: no cover - protocol
        ...


def _import_whisper() -> Any:
    """Import ``faster_whisper`` lazily. Absence is a normal, reportable state."""
    try:
        import faster_whisper  # type: ignore import-not-found
    except Exception as exc:  # noqa: BLE001 - any import failure means unavailable
        raise SttUnavailable("stt_dependency_missing") from exc
    return faster_whisper


class LocalWhisperAdapter:
    """CPU int8 recognition with a per-profile model cache under the plugin data directory."""

    def __init__(self, *, model_name: str | None = None, cache_dir: Path | str | None = None) -> None:
        self.model_name = str(model_name or DEFAULT_MODEL)
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None

    # ── availability ────────────────────────────────────────────────────

    def availability(self) -> tuple[bool, str | None]:
        """Whether this process could attempt inference. Never downloads the model."""
        try:
            _import_whisper()
        except SttUnavailable as exc:
            return False, exc.reason
        if shutil.which("ffmpeg") is None:
            return False, "ffmpeg_missing"
        return True, None

    def model_cached(self) -> bool:
        """Whether a model directory already exists in the cache. Diagnostics only."""
        root = self._resolve_cache_dir()
        return root is not None and root.is_dir() and any(root.iterdir())

    def _resolve_cache_dir(self) -> Path | None:
        if self._cache_dir is not None:
            return self._cache_dir
        try:
            from . import db  # lazy: importing the recogniser must not import the contract stack

            return db.data_root() / "stt-models"
        except Exception:  # noqa: BLE001 - no profile yet: report cached=False, do not invent one
            return None

    def _model(self) -> Any:
        whisper = _import_whisper()
        cache_dir = self._resolve_cache_dir()
        if cache_dir is None:
            raise SttUnavailable("stt_cache_unavailable")
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = (self.model_name, str(cache_dir))
        with _MODEL_LOCK:
            cached = _MODEL_CACHE.get(key)
            if cached is not None:
                return cached
            try:
                model = whisper.WhisperModel(
                    self.model_name,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(cache_dir),
                )
            except Exception as exc:  # noqa: BLE001 - offline/missing model becomes unavailable
                raise SttUnavailable("model_unavailable") from exc
            _MODEL_CACHE[key] = model
            return model

    # ── decode ──────────────────────────────────────────────────────────

    def _decode(self, path: Path) -> bytes:
        """Decode one take to bounded 16 kHz mono PCM using the host ffmpeg binary."""
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise SttUnavailable("ffmpeg_missing")
        command = [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(path),
            "-t", str(int(MAX_DURATION_SECONDS) + 1),
            "-f", "s16le",
            "-ac", "1",
            "-ar", str(SAMPLE_RATE),
            "-",
        ]
        try:
            done = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=DECODE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SttUnavailable("decode_timeout") from exc
        except OSError as exc:
            raise SttUnavailable("decode_failed") from exc
        if done.returncode != 0 or not done.stdout:
            raise SttUnavailable("decode_failed")
        if len(done.stdout) > MAX_PCM_BYTES:
            raise SttUnavailable("audio_too_long")
        return done.stdout

    # ── inference ───────────────────────────────────────────────────────

    def transcribe(self, path: Path, *, language: str | None = None,
                   prompt: str | None = None) -> Transcription:
        pcm = self._decode(Path(path))
        try:
            import numpy as np  # faster-whisper depends on numpy; a missing one is unavailable
        except Exception as exc:  # noqa: BLE001
            raise SttUnavailable("numpy_missing") from exc

        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        duration = float(samples.size) / float(SAMPLE_RATE)
        if duration <= 0.0:
            raise SttUnavailable("decode_empty")
        if duration > MAX_DURATION_SECONDS:
            raise SttUnavailable("audio_too_long")

        model = self._model()
        hint = None
        if language:
            hint = str(language).replace("_", "-").split("-")[0].strip().lower() or None
        try:
            segments, info = model.transcribe(
                samples,
                language=hint,
                initial_prompt=(str(prompt)[:200] if prompt else None),
                beam_size=1,
                vad_filter=True,
                word_timestamps=True,
                condition_on_previous_text=False,
            )
            collected = list(segments)
        except Exception as exc:  # noqa: BLE001 - inference failure is unavailable, never a score
            logger.warning("coursebook stt: inference failed (%s)", type(exc).__name__)
            raise SttUnavailable("transcription_failed") from exc

        text = "".join(str(segment.text or "") for segment in collected).strip()
        words: list[dict[str, Any]] = []
        probabilities: list[float] = []
        for segment in collected:
            for word in getattr(segment, "words", None) or []:
                token = str(getattr(word, "word", "") or "").strip()
                if not token:
                    continue
                probability = getattr(word, "probability", None)
                try:
                    probability = float(probability) if probability is not None else None
                except (TypeError, ValueError):
                    probability = None
                words.append({"word": token, "probability": probability})
                if probability is not None:
                    probabilities.append(probability)
        confidence = round(sum(probabilities) / len(probabilities), 4) if probabilities else None
        detected = getattr(info, "language", None)
        return Transcription(
            text=text,
            provider=PROVIDER,
            model=self.model_name,
            language=str(detected) if detected else hint,
            confidence=confidence,
            words=tuple(words),
            duration=duration,
        )


# ── process-wide adapter seam (injected by tests; production default is local) ──────────────

_ADAPTER: SttAdapter | None = None


def configure(adapter: SttAdapter | None) -> None:
    """Bind the adapter this process scores through. ``None`` restores the local default."""
    global _ADAPTER
    _ADAPTER = adapter


def reset_adapter() -> None:
    configure(None)


def get_adapter() -> SttAdapter:
    adapter = _ADAPTER
    return adapter if adapter is not None else LocalWhisperAdapter()


def described() -> dict[str, Any]:
    """Small honest availability block for diagnostics. Never triggers a model download."""
    adapter = get_adapter()
    if isinstance(adapter, LocalWhisperAdapter):
        available, reason = adapter.availability()
        return {
            "provider": PROVIDER,
            "model": adapter.model_name,
            "available": available,
            "reason": reason,
            "model_cached": adapter.model_cached(),
            "local_only": True,
        }
    return {
        "provider": PROVIDER,
        "model": None,
        "available": True,
        "reason": None,
        "model_cached": None,
        "local_only": True,
    }
