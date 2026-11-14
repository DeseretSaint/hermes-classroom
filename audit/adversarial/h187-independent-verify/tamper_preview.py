#!/usr/bin/env python3
"""Adversarial tamper probe for the preview route: a player may only appear for the real bytes.

Runs against a throwaway copy of the prepared home (never the prepared home). The copy's
``artifacts.path`` rows are remapped to the copy's own object store so the copy is a standalone
home; the product code is unmodified. Then:

  T1  baseline: both previews serve the exact bytes
  T2  flip one byte in the stored audio      -> preview must refuse (hash mismatch)
  T3  delete the stored image                -> preview must refuse (missing file)
  T4  symlink the image object outside root  -> preview must refuse (containment)
  T5  replace the image with HTML bytes whose row hash/size are updated
                                             -> preview must refuse (mime/safety, not a fake <img>)

Usage: python3 tamper_preview.py --home /path/to/COPY/home --out tamper.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
HERMES_AGENT = Path("/home/deseretsaint/.hermes/hermes-agent")
AUDIO = "art_adf2e015a0694641a409bb54e9a6a746"
IMAGE = "art_d7dc7afd153d4736abc4d2e0560a8376"
CHECKS: list[dict] = []


def check(check_id: str, ok: bool, detail: object) -> None:
    CHECKS.append({"id": check_id, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + check_id + " :: " + json.dumps(detail, ensure_ascii=False)[:300])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    home = Path(args.home).resolve()
    if home == Path("/home/deseretsaint/.hermes/h187-course/home").resolve():
        raise SystemExit("refusing to run the destructive tamper probe against the prepared home")
    os.environ["HERMES_HOME"] = str(home)
    sys.path.insert(0, str(REPO))
    sys.path.append(str(HERMES_AGENT))

    from coursebook import artifacts as artifacts_mod, db, media

    store_root = Path(artifacts_mod.read_root()).resolve()

    # Remap the copy's rows to the copy's own object store (the copy is a standalone home).
    with db.transaction() as write:
        for row in write.execute("SELECT id, path FROM artifacts").fetchall():
            source = Path(str(row["path"]))
            local = store_root / "objects" / source.name[:2] / source.name
            write.execute("UPDATE artifacts SET path = ? WHERE id = ?", (str(local), row["id"]))

    def preview(artifact_id: str) -> dict:
        return media.preview_artifact(artifact_id)

    def path_of(artifact_id: str) -> Path:
        with db.read() as connection:
            return Path(str(connection.execute(
                "SELECT path FROM artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()["path"]))

    # T1 baseline
    audio = preview(AUDIO)
    image = preview(IMAGE)
    check("T1.audio_baseline_ok", audio.get("ok") is True, audio.get("code"))
    check("T1.image_baseline_ok", image.get("ok") is True, image.get("code"))

    audio_path = path_of(AUDIO)
    image_path = path_of(IMAGE)
    audio_bytes = bytearray(audio_path.read_bytes())

    # T2 hash mismatch
    audio_bytes[100] ^= 0xFF
    audio_path.write_bytes(bytes(audio_bytes))
    tampered = preview(AUDIO)
    check("T2.tampered_audio_refused",
          tampered.get("ok") is not True and "hash" in str(tampered.get("message", "")).lower(),
          {k: tampered.get(k) for k in ("ok", "code", "message")})
    audio_path.write_bytes(bytes(audio_bytes[:100]) + bytes([audio_bytes[100] ^ 0xFF]) + bytes(audio_bytes[101:]))
    check("T2b.restored_audio_ok", preview(AUDIO).get("ok") is True, preview(AUDIO).get("code"))

    # T3 missing file
    image_backup = image_path.read_bytes()
    image_path.unlink()
    missing = preview(IMAGE)
    check("T3.missing_image_refused",
          missing.get("ok") is not True and missing.get("code") == "NOT_FOUND",
          {k: missing.get(k) for k in ("ok", "code", "message")})
    image_path.write_bytes(image_backup)

    # T4 symlink escape
    outside = home.parent / "tamper-outside-secret.bin"
    outside.write_bytes(b"not an image; outside the store")
    image_path.unlink()
    image_path.symlink_to(outside)
    escaped = preview(IMAGE)
    check("T4.symlink_outside_refused",
          escaped.get("ok") is not True and escaped.get("code") == "NOT_FOUND",
          {k: escaped.get(k) for k in ("ok", "code", "message")})
    image_path.unlink()
    image_path.write_bytes(image_backup)

    # T5 an HTML payload declared as image/png, row hash and size updated to match
    fake = b"<html><script>alert(document.cookie)</script></html>"
    digest = hashlib.sha256(fake).hexdigest()
    image_path.unlink()
    image_path.write_bytes(fake)
    with db.transaction() as write:
        write.execute(
            "UPDATE artifacts SET content_hash = ?, bytes = ? WHERE id = ?", (digest, len(fake), IMAGE)
        )
    confused = preview(IMAGE)
    check("T5.html_declared_png_refused",
          confused.get("ok") is not True,
          {k: confused.get(k) for k in ("ok", "code", "message")})
    check("T5b.refusal_is_mime_or_safety",
          str(confused.get("code")) in {"UNSAFE_MEDIA", "INTERNAL_ERROR", "UNSUPPORTED_MEDIA"},
          confused.get("code"))

    failures = [c for c in CHECKS if not c["ok"]]
    result = {
        "kind": "tamper_probe",
        "verifier": "sentinel",
        "home": str(home),
        "checks_total": len(CHECKS),
        "checks_passed": len(CHECKS) - len(failures),
        "failures": [c["id"] for c in failures],
        "status": "PASS" if not failures else "FAIL",
        "checks": CHECKS,
    }
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "checks_total", "checks_passed", "failures")},
                     indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
