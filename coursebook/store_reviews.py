"""The store's own human-review ledger — the only evidence behind ``human_review_recorded``.

A pack manifest can declare ``trust.reviewed_by`` and ``trust.reviewed_at``; those are strings
its author typed, and they are provenance, never evidence. The store that accepts a submission
records a review in ``store/reviews.json`` instead, bound to the exact ``pack_id`` and
``content_hash`` that was read. A record blesses those bytes and nothing else: a changed pack
needs a new review.

This module is the one reader of that file. ``workshop`` uses it for store cards,
``pack_flow.pack_preview``/``pack_inspect`` use it for the pack read surfaces, and both turn the
boolean into a label through :func:`coursebook.packs.trust_labels`. A missing, oversized,
unreadable or malformed ledger proves nothing and must never take a read surface down, so every
failure answers ``False`` rather than raising.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

#: ``coursebook/store_reviews.py`` -> plugin root -> ``store/reviews.json``.
ROOT = Path(__file__).resolve().parent.parent
STORE_REVIEWS_PATH = ROOT / "store" / "reviews.json"
#: Bound on the ledger: a review file is tiny data, and an oversized one is not read.
MAX_STORE_REVIEWS = 64
MAX_STORE_REVIEWS_BYTES = 256_000

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _text(value: Any, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:limit] if text else None


def review_recorded(
    manifest: Mapping[str, Any],
    *,
    path: Path | None = None,
    max_records: int = MAX_STORE_REVIEWS,
    max_bytes: int = MAX_STORE_REVIEWS_BYTES,
) -> bool:
    """Whether the store itself holds a human review of *these exact bytes*.

    The pack's own ``trust.reviewed_by``/``reviewed_at`` are not consulted. A record counts only
    when it names this ``pack_id`` and its ``content_hash`` equals the manifest's own. A broken
    ledger is no evidence: the answer is ``False``, never an exception on a read path.
    """
    ledger = Path(path) if path is not None else STORE_REVIEWS_PATH
    try:
        if ledger.stat().st_size > max_bytes:
            return False
        document = json.loads(ledger.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(document, Mapping):
        return False
    records = document.get("reviews")
    if not isinstance(records, list):
        return False
    pack_id = str(manifest.get("pack_id") or "")
    content_hash = str(manifest.get("content_hash") or "")
    if not pack_id or not _SHA256.match(content_hash):
        return False
    for record in records[:max_records]:
        if not isinstance(record, Mapping):
            continue
        if _text(record.get("pack_id"), limit=128) != pack_id:
            continue
        if str(record.get("content_hash") or "") != content_hash:
            continue
        if not _text(record.get("reviewed_by"), limit=200):
            continue
        if not _text(record.get("reviewed_at"), limit=40):
            continue
        return True
    return False
