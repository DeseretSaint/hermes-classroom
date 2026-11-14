#!/usr/bin/env python3
"""Render the SHIPPED Desktop module for the two real served states and assert what the learner sees.

Two payloads, both taken from product output (never hand-authored):

  good     — lesson.page for the generated gen_lang_1 page + the real /media/ preview result
  degraded — lesson.page from degrade_audio.py, where the provider refused

Then the assertions are on the rendered DOM:
  good: a real <audio controls src="data:audio/mpeg;base64,..."> appears for the artifact
  degraded: no <audio>, no data: URL, no controls; an honest text-only message, the degraded
            reason, and the text equivalent are present.

Run: python3 run_ui_probe.py --home /path/to/prepared/home --degraded-page served.json --out ui.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
HERMES_AGENT = Path("/home/deseretsaint/.hermes/hermes-agent")
PROBE = HERE.parent / "ui_probe.mjs"

ENROLLMENT_ID = "enr_22c18bf3305a4b0ca769b8219e0036dd"
OBJECTIVE_ID = "obj_903c89f63e4940d7a8220082e4d68429"
AUDIO_ARTIFACT_ID = "art_adf2e015a0694641a409bb54e9a6a746"

TECH_ENROLLMENT_ID = "enr_5906d9d5f01a420cba6d2d202db8da53"
TECH_OBJECTIVE_ID = "obj_75056df1acb84e4ea637b30421c5cca9"
IMAGE_ARTIFACT_ID = "art_d7dc7afd153d4736abc4d2e0560a8376"

CHECKS: list[dict] = []


def check(check_id: str, ok: bool, detail: object) -> None:
    CHECKS.append({"id": check_id, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + check_id + " :: " + json.dumps(detail, ensure_ascii=False)[:300])


def run_node(root: Path, payload_path: Path) -> dict:
    proc = subprocess.run(
        ["node", str(root / "ui_probe.mjs"), str(payload_path)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"node failed rc={proc.returncode}\nSTDERR:\n{proc.stderr[-3000:]}")
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--degraded-page", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--work", default=None)
    args = parser.parse_args()

    home = Path(args.home).resolve()
    os.environ["HERMES_HOME"] = str(home)
    sys.path.insert(0, str(REPO))
    sys.path.append(str(HERMES_AGENT))

    import coursebook.domain  # noqa: F401
    from coursebook import api, contracts, media

    good_served = api.dispatch(
        {
            "contract": "cb.rpc",
            "contract_version": contracts.WIRE_CONTRACT_VERSION,
            "method": "lesson.page",
            "operation_id": "sentinel-ui-good",
            "payload": {"enrollment_id": ENROLLMENT_ID, "objective_id": OBJECTIVE_ID},
        }
    )
    if not good_served.get("ok"):
        raise SystemExit(f"good lesson.page failed: {good_served.get('error')}")
    good_page = good_served["result"]

    previews = {}
    for block in (good_page.get("document") or {}).get("blocks") or []:
        for child in block.get("media") or []:
            artifact_id = child.get("artifact_id")
            if artifact_id and artifact_id not in previews:
                preview = media.preview_artifact(artifact_id)
                if preview.get("ok") is True:
                    previews[artifact_id] = preview

    image_served = api.dispatch(
        {
            "contract": "cb.rpc",
            "contract_version": contracts.WIRE_CONTRACT_VERSION,
            "method": "lesson.page",
            "operation_id": "sentinel-ui-good-image",
            "payload": {"enrollment_id": TECH_ENROLLMENT_ID, "objective_id": TECH_OBJECTIVE_ID},
        }
    )
    if not image_served.get("ok"):
        raise SystemExit(f"image lesson.page failed: {image_served.get('error')}")
    image_page = image_served["result"]
    image_previews = {}
    for block in (image_page.get("document") or {}).get("blocks") or []:
        for child in block.get("media") or []:
            artifact_id = child.get("artifact_id")
            if artifact_id and artifact_id not in image_previews:
                preview = media.preview_artifact(artifact_id)
                if preview.get("ok") is True:
                    image_previews[artifact_id] = preview

    degraded_page = json.loads(Path(args.degraded_page).read_text(encoding="utf-8"))

    root = Path(args.work) if args.work else Path(tempfile.mkdtemp(prefix="cb-ui-probe-"))
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "desktop" / "plugin.js", root / "plugin.js")
    shutil.copyfile(PROBE, root / "ui_probe.mjs")
    node_modules = root / "node_modules"
    node_modules.mkdir(exist_ok=True)
    for name in ("react", "react-dom", "scheduler", "jsdom"):
        source = HERMES_AGENT / "node_modules" / name
        target = node_modules / name
        if source.exists() and not target.exists():
            target.symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True, exist_ok=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
    )
    from tests.test_desktop_lesson_views import SDK_STUB
    (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    good_payload = {
        "enrollment_id": ENROLLMENT_ID,
        "objective_id": OBJECTIVE_ID,
        "title": "Bike-shop Japanese",
        "page": good_page,
        "previews": previews,
    }
    degraded_payload = {
        "enrollment_id": ENROLLMENT_ID,
        "objective_id": OBJECTIVE_ID,
        "title": "Bike-shop Japanese",
        "page": degraded_page,
        "previews": {},
    }
    (root / "payload_good.json").write_text(json.dumps(good_payload, ensure_ascii=False), encoding="utf-8")
    (root / "payload_good_image.json").write_text(json.dumps({
        "enrollment_id": TECH_ENROLLMENT_ID,
        "objective_id": TECH_OBJECTIVE_ID,
        "title": "Workshop procedure",
        "page": image_page,
        "previews": image_previews,
    }, ensure_ascii=False), encoding="utf-8")
    (root / "payload_degraded.json").write_text(json.dumps(degraded_payload, ensure_ascii=False), encoding="utf-8")
    (root / "payload_good_missing.json").write_text(json.dumps({
        "enrollment_id": ENROLLMENT_ID,
        "objective_id": OBJECTIVE_ID,
        "title": "Bike-shop Japanese",
        "page": good_page,
        "previews": {},
    }, ensure_ascii=False), encoding="utf-8")

    good = run_node(root, root / "payload_good.json")
    good_image = run_node(root, root / "payload_good_image.json")
    degraded = run_node(root, root / "payload_degraded.json")
    missing = run_node(root, root / "payload_good_missing.json")

    # ── the generated page: a real player, backed by the real bytes ────────────────────
    ghtml = good["html"]
    check("good.block_media_present", f'data-cb-block-media="{AUDIO_ARTIFACT_ID}"' in ghtml,
          "data-cb-block-media marker")
    check("good.audio_element_rendered", "<audio" in ghtml, ghtml.count("<audio"))
    check("good.audio_has_controls", "controls" in ghtml, "controls attribute present")
    check("good.audio_src_is_real_mpeg", 'src="data:audio/mpeg;base64,' in ghtml,
          "data:audio/mpeg;base64 src")
    check("good.audio_aria_label", "aria-label=" in ghtml and "こんにちは" in ghtml,
          "aria-label carries the phrase")
    check("good.no_degraded_message", "No generated artifact is attached" not in ghtml, None)
    check("good.no_degraded_notice", "Media is degraded" not in ghtml, None)
    check("good.text_equivalent_visible",
          "こんにちは (konnichiwa) — the standard daytime greeting" in good["text"],
          "text equivalent is the visible caption beside the player")
    check("good.media_route_was_called", any(f"/media/{AUDIO_ARTIFACT_ID}" == c for c in good["rest_calls"]),
          good["rest_calls"])
    check("good.preview_served_bytes", previews.get(AUDIO_ARTIFACT_ID, {}).get("bytes") == 41088,
          previews.get(AUDIO_ARTIFACT_ID, {}).get("bytes"))

    # ── the generated illustration: a real <img>, backed by the real bytes ──────────────
    ihtml = good_image["html"]
    check("good_image.block_media_present", f'data-cb-block-media="{IMAGE_ARTIFACT_ID}"' in ihtml, None)
    check("good_image.img_rendered", "<img" in ihtml, ihtml.count("<img"))
    check("good_image.img_src_is_real_png", 'src="data:image/png;base64,' in ihtml,
          "data:image/png;base64 src")
    check("good_image.img_has_alt", 'alt="' in ihtml, "alt attribute present")
    check("good_image.no_degraded_notice", "Media is degraded" not in ihtml, None)
    check("good_image.media_route_called",
          any(f"/media/{IMAGE_ARTIFACT_ID}" == c for c in good_image["rest_calls"]),
          good_image["rest_calls"])

    # ── the refused provider: no player, no fake controls, honest text ─────────────────
    dhtml = degraded["html"]
    dtext = degraded["text"]
    check("degraded.block_media_text_only", 'data-cb-block-media="text-only"' in dhtml, None)
    check("degraded.no_audio_element", "<audio" not in dhtml, dhtml.count("<audio"))
    check("degraded.no_controls_attribute", "controls=" not in dhtml, None)
    check("degraded.no_data_url", "data:audio/" not in dhtml, None)
    check("degraded.no_media_route_call",
          not any(c.startswith("/media/") for c in degraded["rest_calls"]), degraded["rest_calls"])
    check("degraded.honest_text_only_message",
          "No generated artifact is attached; the text equivalent is shown." in dtext, None)
    check("degraded.reason_rendered", "Media is degraded:" in dtext, None)
    check("degraded.reason_names_generation_failure",
          "media generation failed" in dtext, None)
    check("degraded.text_equivalent_rendered", "こんにちは (konnichiwa)" in dtext, None)
    check("degraded.no_claim_of_playback",
          not any(word in dtext.lower() for word in ("listen now", "play the audio", "0:00")), None)

    # ── the artifact row exists but the bytes are gone (stale reference) ──────────────
    mhtml = missing["html"]
    mtext = missing["text"]
    check("missing_bytes.no_audio_element", "<audio" not in mhtml, mhtml.count("<audio"))
    check("missing_bytes.no_data_url", "data:audio/" not in mhtml, None)
    check("missing_bytes.route_was_attempted",
          any(c.startswith("/media/") for c in missing["rest_calls"]), missing["rest_calls"])
    check("missing_bytes.honest_fallback",
          "artifact not found" in mtext or "This media could not be previewed" in mtext,
          [line for line in mtext.split("\n") if "artifact" in line.lower()][:2])
    check("missing_bytes.text_equivalent_still_visible",
          "こんにちは (konnichiwa)" in mtext, None)

    failures = [c for c in CHECKS if not c["ok"]]
    result = {
        "kind": "ui_degradation_render_probe",
        "verifier": "sentinel",
        "plugin_sha256": __import__("hashlib").sha256((REPO / "desktop" / "plugin.js").read_bytes()).hexdigest(),
        "good_served_page_state": (good_page.get("document") or {}).get("state"),
        "degraded_served_block_media": None,
        "checks_total": len(CHECKS),
        "checks_passed": len(CHECKS) - len(failures),
        "failures": [c["id"] for c in failures],
        "status": "PASS" if not failures else "FAIL",
        "checks": CHECKS,
        "good_html_sha256": __import__("hashlib").sha256(ghtml.encode()).hexdigest(),
        "image_html_sha256": __import__("hashlib").sha256(ihtml.encode()).hexdigest(),
        "degraded_html_sha256": __import__("hashlib").sha256(dhtml.encode()).hexdigest(),
    }
    out_path = Path(args.out)
    out_dir = out_path.parent / "evidence"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "rendered_good_audio.html").write_text(ghtml, encoding="utf-8")
    (out_dir / "rendered_good_image.html").write_text(ihtml, encoding="utf-8")
    (out_dir / "rendered_degraded_audio.html").write_text(dhtml, encoding="utf-8")
    (out_dir / "rendered_missing_bytes.html").write_text(mhtml, encoding="utf-8")
    result["rendered_html"] = {
        "good_audio": str(out_dir / "rendered_good_audio.html"),
        "good_image": str(out_dir / "rendered_good_image.html"),
        "degraded_audio": str(out_dir / "rendered_degraded_audio.html"),
        "missing_bytes": str(out_dir / "rendered_missing_bytes.html"),
    }
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "checks_total", "checks_passed", "failures")},
                     indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
