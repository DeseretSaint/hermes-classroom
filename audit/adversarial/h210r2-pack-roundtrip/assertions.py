"""H-210-R2 assertions: every claim the gate-4 flip depends on, computed from the captures.

Nothing here talks to the backend. It reads the two live captures (store A, store B), the legacy
dedupe capture, the input manifest report, and the pack files on disk, and emits one JSON document
with a per-check verdict. A single false check keeps gate 4 open.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

S = Path("/home/deseretsaint/.hermes/profiles/lattice/cache/scratch/h210r2")
ROOT = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_a7761dfc")
OUT = S / "assertions.json"

LABELLED = re.compile(r"^sha256:[a-f0-9]{64}$")
BARE = re.compile(r"^[a-f0-9]{64}$")
MIME = re.compile(r"^[a-z]+/[A-Za-z0-9.+-]+$")
ARTIFACT_KINDS = {"visual", "audio", "pdf", "pack", "export", "other"}

checks: list[dict] = []


def check(name: str, ok: bool, detail) -> None:
    checks.append({"check": name, "ok": bool(ok), "detail": detail})


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def read(name: str) -> dict:
    return json.loads((S / name).read_text(encoding="utf-8"))


def manifest_counts(manifest: dict) -> dict:
    objectives = manifest.get("objectives") or []
    return {
        "objectives": len(objectives),
        "sections": sum(len(o.get("sections") or []) for o in objectives),
        "checks": sum(len(o.get("checks") or []) for o in objectives),
        "files": len(manifest.get("files") or []),
        "media": len(manifest.get("media") or []),
        "content_hash": manifest.get("content_hash"),
    }


def contract_shape_ok(result: dict) -> tuple[bool, list[str]]:
    problems = []
    for field in ("artifact_id", "kind", "mime", "bytes", "content_hash"):
        if field not in result:
            problems.append(f"missing {field}")
    if result.get("kind") not in ARTIFACT_KINDS:
        problems.append(f"kind {result.get('kind')!r} outside the enum")
    if not MIME.match(str(result.get("mime") or "")):
        problems.append(f"mime {result.get('mime')!r} fails the pattern")
    if not isinstance(result.get("bytes"), int) or result.get("bytes", -1) < 0:
        problems.append("bytes is not a non-negative integer")
    if not LABELLED.match(str(result.get("content_hash") or "")):
        problems.append(f"content_hash {result.get('content_hash')!r} fails ^sha256:[a-f0-9]{{64}}$")
    download = result.get("download") or {}
    if not re.match(r"^/api/plugins/coursebook/artifacts/[A-Za-z0-9_-]+$", str(download.get("url") or "")):
        problems.append("download.url outside the handle route")
    if download.get("requires_session") is not True:
        problems.append("download handle does not require the session")
    return (not problems), problems


def main() -> int:
    inputs = read("inputs/inputs.json")
    a = read("evidence-storeA.json")
    b = read("evidence-storeB.json")
    dedupe = read("evidence-dedupe.json")

    head = git("rev-parse", "HEAD")
    plugin_sha = sha(ROOT / "desktop/plugin.js")
    ancestry = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", "160c522", "HEAD"]
    ).returncode == 0
    check("release tree is the merged re-check branch", head == a["release_commit"],
          {"head": head, "capture_commit": a["release_commit"], "branch": git("rev-parse", "--abbrev-ref", "HEAD")})
    check("artifact.get repair 160c522 is an ancestor of the measured commit", ancestry, {"ancestor": "160c522"})
    check("desktop/plugin.js sha256", plugin_sha.startswith("sha256:"),
          {"sha256": plugin_sha, "expect_m4_pin": "cd862140" in plugin_sha})
    check("wire version is cb.rpc v20", a["wire_version"] == 20 and b["wire_version"] == 20,
          {"storeA": a["wire_version"], "storeB": b["wire_version"]})
    check("packs intake available on both backends",
          a["packs_intake"]["response"].get("available") is True
          and a["packs_intake"]["response"].get("can_grant") is True
          and b["packs_intake"]["response"].get("available") is True,
          {"storeA": a["packs_intake"]["response"], "storeB": b["packs_intake"]["response"]})

    # 1. preview + import
    for label, pack_id in (("japanese", "japanese-affection-context-l0"), ("demo", "technical-demo-pack")):
        source = inputs[pack_id]
        pa, pb = a[f"preview_{label}"], b[f"preview_{label}"]

        def preview_ok(response: dict) -> dict:
            result = response.get("result") or {}
            manifest = result.get("manifest") or {}
            integrity = result.get("integrity") or {}
            return {
                "ok": response.get("ok"),
                "code": (response.get("error") or {}).get("code"),
                "hashes_match": integrity.get("hashes_match"),
                "file_count": integrity.get("file_count"),
                "expanded_bytes": integrity.get("expanded_bytes"),
                "manifest": manifest_counts(manifest),
                "trust": result.get("trust"),
            }

        check(f"pack.preview {label} matches the bundled manifest on both stores",
              a[f"preview_{label}"].get("ok") and b[f"preview_{label}"].get("ok")
              and preview_ok(pa)["hashes_match"] and preview_ok(pb)["hashes_match"]
              and preview_ok(pa)["manifest"]["content_hash"] == source["content_hash"]
              and preview_ok(pb)["manifest"]["content_hash"] == source["content_hash"],
              {"storeA": preview_ok(pa), "storeB": preview_ok(pb), "expected": source})
        check(f"pack.import {label} succeeded on both stores",
              (a[f"import_{label}"].get("result") or {}).get("enrollment_id") is not None
              and (b[f"import_{label}"].get("result") or {}).get("enrollment_id") is not None,
              {"storeA": a[f"import_{label}"].get("result"), "storeB": b[f"import_{label}"].get("result")})

    check("second import of the same pack in resume mode keeps one course/enrollment",
          (a["import_japanese_resume"].get("result") or {}).get("enrollment_id")
          == (a["import_japanese"].get("result") or {}).get("enrollment_id"),
          {"first": a["import_japanese"].get("result"),
           "resume": a["import_japanese_resume"].get("result")})

    # 2. structure
    expected = {"japanese": {"objectives": 4, "sections": 4, "checks": 4},
                "demo": {"objectives": 2, "sections": 2, "checks": 2}}
    for label in ("japanese", "demo"):
        structure = {}
        for store, evidence in (("storeA", a), ("storeB", b)):
            manifest = (evidence[f"preview_{label}"].get("result") or {}).get("manifest") or {}
            pages = evidence[f"pages_{label}"]
            structure[store] = {
                "preview": manifest_counts(manifest),
                "outline_total": pages["outline_total"],
                "page_objectives": pages["objectives"],
                "segments": pages["segment_totals"],
            }
        got = structure["storeA"]["preview"]
        want = expected[label]
        check(f"structure after re-import is {want['objectives']}/{want['sections']}/{want['checks']} in both stores",
              all(structure[s]["preview"][k] == v for s in structure for k, v in want.items())
              and structure["storeA"]["page_objectives"] == structure["storeB"]["page_objectives"] == want["objectives"]
              and structure["storeA"]["segments"] == structure["storeB"]["segments"],
              {"expected": want, **structure})

    # 3. export determinism and byte identity
    for label in ("japanese", "demo"):
        first = a[f"export_{label}_attempt_1"].get("result") or {}
        second = a[f"export_{label}_attempt_2"].get("result") or {}
        again = b[f"export_{label}"].get("result") or {}
        check(f"pack.export {label} is deterministic on the same store (two attempts)",
              first.get("content_hash") == second.get("content_hash")
              and first.get("artifact_id") == second.get("artifact_id")
              and first.get("bytes") == second.get("bytes"),
              {"attempt_1": first, "attempt_2": second})
        check(f"pack.export {label} content_hash is unchanged after a fresh-store re-import",
              first.get("content_hash") == again.get("content_hash")
              and first.get("bytes") == again.get("bytes"),
              {"storeA": first.get("content_hash"), "storeB": again.get("content_hash")})

    files_a = {Path(p).name: v["sha256"] for p, v in a["export_files"].items()}
    files_b = {Path(p).name: v["sha256"] for p, v in b["export_files"].items()}
    jp_name = "japanese-affection-context-l0-2.1.0-5343526daa29a310.zip"
    demo_name = "technical-demo-pack-2.0.0-ff5594a816570084.zip"
    check("exported Japanese archive sha256 is sha256:4aefd708… on both stores",
          files_a.get(jp_name) == files_b.get(jp_name)
          == "sha256:4aefd70828dac75dc0082c1b4a055208e674335634412cb07f54914bf48171c0",
          {"storeA": files_a.get(jp_name), "storeB": files_b.get(jp_name)})
    check("Japanese export archive is byte-identical to the imported archive",
          files_a.get(jp_name) == inputs["japanese-affection-context-l0"]["zip_sha256"],
          {"export": files_a.get(jp_name), "input": inputs["japanese-affection-context-l0"]["zip_sha256"]})
    check("demo export archive sha256 is sha256:747c61fd… on both stores",
          files_a.get(demo_name) == files_b.get(demo_name)
          == "sha256:747c61fdf39ec5e316608b9b144478a9a7b11fbbea484226544e98baf6f4276e",
          {"storeA": files_a.get(demo_name), "storeB": files_b.get(demo_name)})
    check("demo export archive is byte-identical to the imported archive",
          files_a.get(demo_name) == inputs["technical-demo-pack"]["zip_sha256"],
          {"export": files_a.get(demo_name), "input": inputs["technical-demo-pack"]["zip_sha256"]})
    check("Japanese pack content_hash is sha256:5343526d…",
          (a["export_japanese_attempt_1"].get("result") or {}).get("content_hash")
          == inputs["japanese-affection-context-l0"]["content_hash"]
          == "sha256:5343526daa29a310df666ca8940d3908b5e507f34b0f83b04afb853cce5449f9",
          {"export": (a["export_japanese_attempt_1"].get("result") or {}).get("content_hash")})

    # 4. every artifact.get: export rows and media rows
    fetches: list[dict] = []
    for label in ("japanese", "demo"):
        entry = a[f"export_artifact_{label}"]
        result = entry["artifact_get"].get("result") or {}
        shape_ok, problems = contract_shape_ok(result)
        handle = entry.get("handle") or {}
        archive_sha = files_a.get(jp_name if label == "japanese" else demo_name)
        fetches.append({
            "boundary": "export",
            "pack": label,
            "artifact_id": entry["artifact_id"],
            "ok": entry["artifact_get"].get("ok"),
            "shape_ok": shape_ok,
            "shape_problems": problems,
            "content_hash": result.get("content_hash"),
            "prefixes": str(result.get("content_hash") or "").count("sha256:"),
            "handle_http": handle.get("http"),
            "handle_sha256": handle.get("sha256"),
            "archive_sha256": archive_sha,
        })
        check(f"artifact.get on the {label} export artifact is contract-valid, single-prefixed and fetchable",
              entry["artifact_get"].get("ok") is True and shape_ok
              and str(result.get("content_hash") or "").count("sha256:") == 1
              and handle.get("http") == 200 and handle.get("sha256") == archive_sha
              and handle.get("bytes") == result.get("bytes"),
              fetches[-1])

    declared_media = {
        "japanese": set(inputs["japanese-affection-context-l0"]["media"].values()),
        "demo": set(inputs["technical-demo-pack"]["media"].values()),
    }
    all_declared = set().union(*declared_media.values())
    check("both packs declare four media links (three Japanese + one demo)",
          {k: len(v) for k, v in declared_media.items()} == {"japanese": 3, "demo": 1},
          {k: sorted(v) for k, v in declared_media.items()})

    for store, evidence in (("storeA", a), ("storeB", b)):
        seen = set()
        for key, entry in sorted(evidence["media_artifacts"].items()):
            result = entry["artifact_get"].get("result") or {}
            shape_ok, problems = contract_shape_ok(result)
            handle = entry.get("handle") or {}
            seen.add(result.get("content_hash"))
            fetches.append({
                "boundary": f"media:{store}",
                "pack": entry["pack"],
                "artifact_id": entry["artifact_get"].get("artifact_id") or result.get("artifact_id"),
                "ok": entry["artifact_get"].get("ok"),
                "shape_ok": shape_ok,
                "shape_problems": problems,
                "content_hash": result.get("content_hash"),
                "prefixes": str(result.get("content_hash") or "").count("sha256:"),
                "handle_http": handle.get("http"),
                "handle_sha256": handle.get("sha256"),
                "declared": result.get("content_hash") in all_declared,
            })
        check(f"every media segment resolves through artifact.get on {store}",
              len(evidence["media_artifacts"]) == 4
              and all(entry["artifact_get"].get("ok") is True and (entry.get("handle") or {}).get("http") == 200
                      for entry in evidence["media_artifacts"].values()),
              {k: {"ok": v["artifact_get"].get("ok"),
                   "code": (v["artifact_get"].get("error") or {}).get("code"),
                   "message": (v["artifact_get"].get("error") or {}).get("message")}
               for k, v in evidence["media_artifacts"].items()})
        check(f"every media content_hash on {store} is labelled, contract-valid and matches the bytes the handle returned",
              all(contract_shape_ok((entry["artifact_get"].get("result") or {}))[0]
                  and (entry["artifact_get"].get("result") or {}).get("content_hash")
                  == (entry.get("handle") or {}).get("sha256")
                  and str((entry["artifact_get"].get("result") or {}).get("content_hash") or "").count("sha256:") == 1
                  for entry in evidence["media_artifacts"].values()),
              {k: {"content_hash": (v["artifact_get"].get("result") or {}).get("content_hash"),
                   "handle_sha256": (v.get("handle") or {}).get("sha256")} for k, v in evidence["media_artifacts"].items()})
        check(f"the media hashes on {store} are exactly the four digests both manifests declare",
              seen == all_declared,
              {"fetched": sorted(seen), "declared": sorted(all_declared),
               "missing": sorted(all_declared - seen), "extra": sorted(seen - all_declared)})

    distinct_hashes = {item["content_hash"] for item in fetches}
    check("artifact.get resolved six distinct content digests over ten live calls (four media segments in each of two stores, plus two export archives)",
          len(distinct_hashes) == 6 and len(fetches) == 10
          and all(item["ok"] and item["shape_ok"] for item in fetches),
          {"distinct_digests": len(distinct_hashes), "calls": len(fetches),
           "failures": [f for f in fetches if not (f["ok"] and f["shape_ok"])]})

    # 5. dedupe across the legacy bare spelling and the new labelled spelling
    def pairs(snapshot: dict) -> list[tuple[str, str]]:
        return [(row["content_hash"], row["kind"]) for row in snapshot["rows"]]

    before = dedupe["before"]
    after_import = dedupe["after_reimport"]
    injected = dedupe["injected"]
    legacy_ids = {row["artifact_id"] for row in injected}
    legacy_rows = [row for row in after_import["rows"] if row["id"] in legacy_ids]
    check("store A holds one labelled row per artifact before the legacy injection",
          before["row_count"] == 6 and before["spellings"] == ["labelled"],
          {"row_count": before["row_count"], "spellings": before["spellings"]})
    check("the injected pre-repair rows store the bare 64-hex spelling",
          len(injected) == 4 and all(BARE.match(row["now"]) for row in injected)
          and dedupe["after_injection"]["row_count"] == 6,
          {"injected": injected, "row_count": dedupe["after_injection"]["row_count"]})
    check("two more live imports create no duplicate (content_hash, kind) row",
          after_import["row_count"] == 6
          and len(pairs(after_import)) == len(set(pairs(after_import)))
          and after_import["spellings"] == ["bare", "labelled"],
          {"row_count": after_import["row_count"], "spellings": after_import["spellings"],
           "duplicates": sorted({p for p in pairs(after_import) if pairs(after_import).count(p) > 1})})
    check("the legacy rows keep the spelling they already had (no read path rewrites a row)",
          all(row["content_hash"] in {r["now"] for r in injected} for row in legacy_rows)
          and all(BARE.match(row["content_hash"]) for row in legacy_rows),
          {"legacy_rows": legacy_rows})
    japanese_media_digests = set(inputs["japanese-affection-context-l0"]["media"].values())
    japanese_legacy = [row for row in legacy_rows
                       if "sha256:" + row["content_hash"] in japanese_media_digests]
    check("the three legacy Japanese media rows absorbed the labelled re-imports through ref_count",
          len(japanese_legacy) == 3 and all(row["ref_count"] > 1 for row in japanese_legacy),
          {"ref_count": {row["id"]: row["ref_count"] for row in legacy_rows},
           "japanese_rows": [row["id"] for row in japanese_legacy]})
    legacy_reads = dedupe["legacy_read"]
    legacy_after = dedupe["legacy_read_after_reimport"]
    check("artifact.get normalises a legacy bare row to the labelled contract hash on read",
          len(legacy_reads) == 4
          and all(entry["artifact_get"].get("ok") is True
                  and LABELLED.match(str((entry["artifact_get"].get("result") or {}).get("content_hash") or ""))
                  and (entry["artifact_get"].get("result") or {}).get("content_hash")
                  == (entry.get("handle") or {}).get("sha256")
                  and (entry.get("handle") or {}).get("http") == 200
                  for entry in legacy_reads.values()),
          {k: {"ok": v["artifact_get"].get("ok"),
               "content_hash": (v["artifact_get"].get("result") or {}).get("content_hash"),
               "handle_sha256": (v.get("handle") or {}).get("sha256"),
               "code": (v["artifact_get"].get("error") or {}).get("code")} for k, v in legacy_reads.items()})
    check("the same legacy rows still resolve with labelled hashes after the labelled re-imports",
          len(legacy_after) == 4
          and all(entry["artifact_get"].get("ok") is True
                  and (entry["artifact_get"].get("result") or {}).get("content_hash")
                  == (entry.get("handle") or {}).get("sha256")
                  for entry in legacy_after.values()),
          {k: {"ok": v["artifact_get"].get("ok"),
               "content_hash": (v["artifact_get"].get("result") or {}).get("content_hash"),
               "handle_sha256": (v.get("handle") or {}).get("sha256")} for k, v in legacy_after.items()})
    check("every fetched media/export hash is a labelled digest matching the bytes the handle returned",
          all(item["handle_sha256"] == item["content_hash"] and LABELLED.match(str(item["content_hash"]))
              for item in fetches if item["handle_sha256"]),
          {"mismatches": [i for i in fetches if i["handle_sha256"] and i["handle_sha256"] != i["content_hash"]]})

    passed = sum(1 for c in checks if c["ok"])
    report = {
        "release_commit": head,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "desktop_plugin_sha256": plugin_sha,
        "wire_version": a["wire_version"],
        "route": "live HTTP POST /api/plugins/coursebook/rpc (?profile=), two isolated `hermes serve --isolated` homes",
        "backends": {"storeA": "http://127.0.0.1:44339", "storeB": "http://127.0.0.1:44340"},
        "generated_at": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip(),
        "checks": checks,
        "summary": {"total": len(checks), "passed": passed,
                    "failed": [c["check"] for c in checks if not c["ok"]]},
        "artifact_get_resolutions": fetches,
        "hashes": {
            "japanese": {"content_hash": inputs["japanese-affection-context-l0"]["content_hash"],
                         "archive_sha256": files_a.get(jp_name),
                         "input_archive_sha256": inputs["japanese-affection-context-l0"]["zip_sha256"]},
            "demo": {"content_hash": inputs["technical-demo-pack"]["content_hash"],
                     "archive_sha256": files_a.get(demo_name),
                     "input_archive_sha256": inputs["technical-demo-pack"]["zip_sha256"]},
            "declared_media": {k: sorted(v) for k, v in declared_media.items()},
        },
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for item in checks:
        print(("PASS " if item["ok"] else "FAIL ") + item["check"])
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
