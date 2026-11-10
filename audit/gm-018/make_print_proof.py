"""GM-018 proof: the take-home HTML document, the tagged PDF and the clean cover line.

Run from the repository root:

    python3 audit/gm-018/make_print_proof.py

The script builds a disposable profile, creates a real course through the real RPC dispatcher,
stages one validated lesson the way ``generation`` does, drives
preview/create/approve/export, and then measures:

* the exported PDF through ``qpdf --check`` and ``pdftotext`` (selectable text);
* the Tagged-PDF structure with an independent pypdf probe (``/Lang``, ``/MarkInfo``, the Info
  title, ``/StructTreeRoot`` element types and the ``/ParentTree`` MCID map);
* the single clean ``Take-home:`` line on cover page 1;
* the ``takehome.html`` document: self-contained doctype, language, page roles in PDF order,
  presence of the learner page and parent guide, absence of any script/link/fetch construct, and
  the preserved text alternative on the diagram page.

Evidence (the two PDFs, the HTML document, ``evidence.json`` and ``PROOF.md``) is written to
``audit/gm-018/``. The script exits non-zero on any failed assertion. The lesson below is authored
in this file; no provider call is made and no fixture is copied.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pypdf import PdfReader  # noqa: E402

from coursebook import api, db, domain, generation, takehome  # noqa: E402

OUT = Path(__file__).resolve().parent
NOW = "2026-11-09T12:00:00Z"
GEN_HASH = "sha256:" + "b" * 64
ANSWER = "REFERENCE-ONLY: wait until the oil shimmers"
LEARNER = "Watch the oil, then lay the ribs away from you."


def page_document(title: str) -> dict:
    return {
        "section_title": title,
        "lesson_intent": "Sear the meat hard before the liquid goes in.",
        "segments": [
            {"kind": "explain", "heading": "Why the sear matters",
             "body": "Browning builds the flavour the braise carries for two hours."},
            {"kind": "guided", "heading": "Do this next", "body": LEARNER},
        ],
        "worked_example": {"prompt": "The pan is only warm.",
                           "steps": ["Wait until the oil shimmers", "Lay the ribs away from you"],
                           "answer": "Wait for the shimmer"},
        "learner_explanation": "Choose the moment that actually sears the meat.",
        "check": {"kind": "short_answer",
                  "stimulus": {"prompt": "In one sentence, describe the moment the ribs go in.",
                               "format": "short_text"},
                  "learner_instructions": "Write one sentence.",
                  "evidence_target": "production"},
        "sources": [],
        "media": [{"kind": "visual", "role": "schematic", "purpose": "pan position",
                   "text_equivalent": "The pan sits on the back burner with the handle turned in.",
                   "label": "Deterministic burner placement", "facts": {"burner": "back"}}],
        "parent_notes": "Ask why a cold pan cannot sear.",
        "supervision_notes": ["Use the back burner"],
        "procedure": {"steps": ["Heat the pan", "Sear every face", "Lower the heat"],
                      "hazards": ["Hot oil"], "tools": ["Heavy pan"]},
    }


def call(method: str, payload: dict, *, revision: int | None = None, key: str | None = None) -> dict:
    request = {
        "contract": api.RPC_CONTRACT,
        "contract_version": api.RPC_CONTRACT_VERSION,
        "method": method,
        "operation_id": "proof-" + method.replace(".", "-"),
        "payload": payload,
    }
    if revision is not None:
        request["expected_revision"] = revision
    if key is not None:
        request["idempotency_key"] = key
    response = api.dispatch(request)
    assert response["ok"], (method, response.get("error"))
    return response


def structure_probe(data: bytes) -> dict:
    """Independent structure probe: the Tagged-PDF tree, its element types and the MCID map."""
    reader = PdfReader(io.BytesIO(data))
    root = reader.trailer["/Root"]
    struct_root = root["/StructTreeRoot"].get_object()
    parent_tree = struct_root["/ParentTree"].get_object()
    kinds: dict[str, int] = {}
    mcids: list[int] = []

    def walk(node) -> None:
        node = node.get_object() if hasattr(node, "get_object") else node
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not hasattr(node, "get"):
            return
        if str(node.get("/Type", "")) == "/StructElem":
            kind = str(node.get("/S", "")).lstrip("/")
            kinds[kind] = kinds.get(kind, 0) + 1
            kids = node.get("/K")
            if kids is not None and not isinstance(kids, list):
                mcids.append(int(kids))
        walk(node.get("/K")) if node.get("/K") is not None else None

    walk(struct_root.get("/K"))
    nums = parent_tree.get("/Nums") or []
    return {
        "lang": str(root.get("/Lang", "")),
        "marked": bool(root["/MarkInfo"]["/Marked"]),
        "struct_tree_root": bool(struct_root),
        "struct_elements": kinds,
        "marked_content_ids": len(mcids),
        "parent_tree_keys": [int(nums[i]) for i in range(0, len(nums), 2)],
        "info_title": str(reader.metadata.title or ""),
        "display_doc_title": bool(
            root.get("/ViewerPreferences", {}).get("/DisplayDocTitle")
        ),
    }


def pdftotext(path: Path, *args: str) -> str:
    run = subprocess.run(["pdftotext", *args, str(path), "-"],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    return run.stdout


def main() -> int:
    home = tempfile.mkdtemp(prefix="gm018-proof-")
    os.environ["HERMES_HOME"] = home
    db.migrate()
    with db.read() as connection:
        generation.ensure_schema(connection)

    created = call("course.create", {"title": "Braising at home", "recipe": "committed",
                                     "goal": "Braise short ribs without a pressure cooker.",
                                     "locale": "en-US"})["result"]
    course_id, plan_id = created["course_id"], created["plan_id"]
    objective_id = domain.record_objective(
        plan_id, title="Objective 1: sear and braise", evidence_target="production",
        criteria=[{"id": "c1", "description": "Browns every face", "check_spec": {}}],
    )
    with db.transaction() as connection:
        connection.execute(
            "UPDATE objectives SET evidence_criteria_json = ? WHERE id = ?",
            (json.dumps(["Browns the meat on every face", "Keeps the heat steady",
                         "Does not crowd the pan"]), objective_id),
        )
    enrollment_id = call("enrollment.create", {"course_id": course_id,
                                              "learner_label": "Learner"})["result"]["enrollment_id"]
    call("plan.approve", {"enrollment_id": enrollment_id, "plan_id": plan_id,
                          "plan_hash": domain.plan_hash(plan_id)}, revision=0)
    section_id, lesson_id, check_id = f"sec_{plan_id}", f"lsn_{plan_id}", f"chk_{plan_id}"
    with db.transaction() as connection:
        connection.execute(
            "INSERT INTO gen_plan_documents (id, plan_id, course_id, request_fingerprint,"
            " plan_hash, document_json, research_json, generation_state, validation_id,"
            " result_json, created_at) VALUES (?, ?, ?, 'fp', ?, '{}', '{}', 'draft', NULL,"
            " '{}', ?)", (f"gpd_{plan_id}", plan_id, course_id, GEN_HASH, NOW))
        connection.execute(
            "INSERT INTO gen_plan_sections (id, plan_id, ordinal, plan_hash, title,"
            " lesson_intent, objective_refs_json, context_needs_json, source_ids_json)"
            " VALUES (?, ?, 1, ?, 'Section 1: the sear', 'Sear first, then braise.', '[1]',"
            " ?, '[]')", (section_id, plan_id, GEN_HASH,
                          json.dumps(["A heavy pan", "Tongs", "Neutral oil"])))
        connection.execute(
            "INSERT INTO gen_lessons (id, plan_id, section_id, plan_hash, version, state,"
            " page_json, media_json, parent_notes_json, rejection_reasons_json, validation_id,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, 1, 'validated', ?, '[]', ?,"
            " '[]', NULL, ?, ?)",
            (lesson_id, plan_id, section_id, GEN_HASH,
             json.dumps(page_document("Section 1: the sear")),
             json.dumps({"parent_notes": "Ask why a cold pan cannot sear.",
                         "supervision_notes": ["Use the back burner"]}), NOW, NOW))
        connection.execute(
            "INSERT INTO checks (id, objective_id, version, evidence_target, stimulus_json,"
            " rubric_json, reference_json, locale, audit_state, state, created_at)"
            " VALUES (?, ?, 1, 'production', ?, ?, ?, 'en-US', 'passed', 'open', ?)",
            (check_id, objective_id,
             json.dumps({"prompt": "When do the ribs go into the pan?", "format": "selection"}),
             json.dumps({"criteria": [{"criterion": "a", "description": "Browns every face"},
                                      {"criterion": "b", "description": "Keeps the heat steady"},
                                      {"criterion": "c", "description": "Does not crowd the pan"}]}),
             json.dumps({"reference_answer": ANSWER, "accepted_answers": [],
                         "accepted_alternatives": []}), NOW))
        connection.execute(
            "INSERT INTO gen_lesson_checks (lesson_id, check_id, objective_ref) VALUES (?, ?, 1)",
            (lesson_id, check_id))

    version = f"{lesson_id}:v1"
    preview = call("takehome.preview", {"course_id": course_id, "objective_id": objective_id,
                                        "source_lesson_version": version,
                                        "audience": "parent", "kind": "print_pack"})["result"]
    made = call("takehome.create", {"course_id": course_id, "objective_id": objective_id,
                                    "source_lesson_version": version, "audience": "parent",
                                    "kind": "print_pack", "title": "Take-home: searing ribs"},
                revision=0, key="proof-create-1")["result"]
    call("takehome.approve", {"pack_id": made["pack_id"],
                              "preview_hash": preview["preview_hash"]},
         revision=0, key="proof-approve-1")
    exported = call("takehome.export", {"pack_id": made["pack_id"]}, revision=1,
                    key="proof-export-1")["result"]
    pack = call("takehome.read", {"pack_id": made["pack_id"]})["result"]["pack"]
    assert pack["state"] == "exported"
    assert ANSWER not in pack["pages"]["learner_page"]["text"]
    assert ANSWER in pack["pages"]["answer_guide"]["text"]

    # The measured object is the exported artifact itself, byte for byte: the language and tags a
    # screen reader sees must be the ones the wire produced, not a separate re-render.
    with db.read() as connection:
        artifact_row = connection.execute(
            "SELECT * FROM artifacts WHERE id = ?", (exported["artifact_id"],)
        ).fetchone()
    assert artifact_row is not None, exported["artifact_id"]
    exported_bytes = Path(str(artifact_row["path"])).read_bytes()
    exported_sha256 = "sha256:" + hashlib.sha256(exported_bytes).hexdigest()

    html_result = call("takehome.html", {"pack_id": made["pack_id"]})["result"]
    pack_language = html_result["language"]
    assert pack_language == "en-US", pack_language

    evidence: dict = {"pack_id": made["pack_id"], "artifact_id": exported["artifact_id"],
                      "artifact_sha256": exported_sha256,
                      "pack_language": pack_language, "paper": {}}
    pdf_paths = {}
    for paper, size in (("letter", (612, 792)), ("a4", (595, 842))):
        if paper == "letter":
            # Exactly the bytes export adopted into the artifact store.
            data = exported_bytes
            source = "exported artifact bytes (artifacts.path)"
        else:
            # ``takehome.export`` writes Letter only. This file is a re-render of the same bound
            # pages at A4, carrying the pack's stored language; it is not a second export.
            data = takehome.render_pdf({"title": pack["title"], "audience": "parent",
                                        "pages": preview["pages"],
                                        "language": pack_language}, paper=paper)
            source = ("re-render of the same bound pages at A4 "
                      "with the pack's stored language")
        path = OUT / f"gm-018-takehome-{paper}.pdf"
        path.write_bytes(data)
        pdf_paths[paper] = path
        qpdf = subprocess.run(["qpdf", "--check", str(path)], capture_output=True, text=True,
                              check=False)
        assert qpdf.returncode == 0, (paper, qpdf.stdout, qpdf.stderr)
        assert "No syntax or stream encoding errors found" in (qpdf.stdout + qpdf.stderr), qpdf.stdout
        text = pdftotext(path, "-layout")
        cover = pdftotext(path, "-f", "1", "-l", "1", "-layout")
        reader = PdfReader(io.BytesIO(data))
        boxes = [(float(page.mediabox.width), float(page.mediabox.height)) for page in reader.pages]
        assert all(box == size for box in boxes), (paper, boxes)
        probe = structure_probe(data)
        # The language comes from the stored pack content, never from a renderer default.
        assert probe["lang"] == pack_language, (paper, probe)
        assert probe["struct_tree_root"], probe
        assert probe["info_title"] == "Take-home: searing ribs", probe
        assert probe["display_doc_title"], probe
        assert probe["struct_elements"].get("H1", 0) >= 1, probe
        assert probe["struct_elements"].get("H2", 0) >= 1, probe
        assert probe["struct_elements"].get("P", 0) >= 1, probe
        assert probe["marked_content_ids"] >= 10, probe
        assert LEARNER in text and ANSWER in text
        # One clean cover line: exactly one Take-home: prefix, no doubled prefix or suffix.
        assert cover.count("Take-home:") == 1, cover
        assert "Take-home: Take-home" not in cover, cover
        assert "take-home pack - take-home pack" not in cover, cover
        lines = [line.strip() for line in cover.splitlines() if line.strip()]
        assert lines[0].startswith("Take-home: "), lines[:3]
        assert max(len(line) for line in lines) <= 72, max(len(line) for line in lines)
        evidence["paper"][paper] = {
            "file": str(path.relative_to(ROOT)),
            "source": source,
            "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
            "pages": len(boxes),
            "media_boxes": boxes,
            "qpdf_check": "ok",
            "extracted_chars": len(text),
            "cover_first_line": lines[0],
            "cover_take_home_prefixes": cover.count("Take-home:"),
            "structure": probe,
        }

    # ── the HTML document ──────────────────────────────────────────────────
    html_path = OUT / "gm-018-takehome.html"
    html_path.write_text(html_result["html"], encoding="utf-8")
    lowered = html_result["html"].lower()
    assert lowered.startswith("<!doctype html>"), lowered[:40]
    assert re.search(r'<html lang="en(-us)?">', lowered), lowered[:200]
    assert LEARNER in html_result["html"] and ANSWER in html_result["html"]
    assert "Parent guide" in html_result["html"]
    for forbidden in ("<script", " src=", " href=", "<link", "@import", "url(",
                      "<iframe", "<object", "<embed", "javascript:"):
        assert forbidden not in lowered, forbidden
    roles = re.findall(r'<section[^>]*data-role="([a-z_]+)"', html_result["html"])
    assert roles == ["cover", "parent_guide", "learner_page", "plate", "answer_guide"], roles
    assert 'aria-label="Deterministic burner placement"' in html_result["html"]
    assert "The pan sits on the back burner" in html_result["html"]
    assert "<img" not in lowered and "## " not in html_result["html"]

    evidence["html"] = {
        "file": str(html_path.relative_to(ROOT)),
        "mime": html_result["mime"],
        "pages": html_result["pages"],
        "bytes": len(html_result["html"].encode("utf-8")),
        "document_hash": html_result["document_hash"],
        "page_roles": roles,
        "forbidden_constructs": "none",
        "alt_text_region": "aria-label present on the diagram page",
    }
    evidence["artifact_store"] = {
        "pdf_artifact_id": exported["artifact_id"],
        "html_adopted": False,
        "download_handle": "artifact.get is the only download handle; HTML is content",
    }

    (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    letter = evidence["paper"]["letter"]
    a4 = evidence["paper"]["a4"]
    md = [
        "# GM-018 take-home print follow-ups proof",
        "",
        f"- pack: `{made['pack_id']}` state `{pack['state']}`",
        f"- exported PDF artifact: `{exported['artifact_id']}` "
        f"({evidence['artifact_sha256']}), source of the Letter file",
        f"- pack content language: `{evidence['pack_language']}` (from the stored `content_json`)",
        f"- HTML document: `audit/gm-018/gm-018-takehome.html` "
        f"({evidence['html']['bytes']} bytes, `{evidence['html']['document_hash']}`)",
        "",
        "## Tagged PDF (measured, not assumed)",
        "",
        "The Letter file is the exported artifact byte-for-byte (`artifacts.path`); the A4 file "
        "is a labelled re-render of the same bound pages, because `takehome.export` writes "
        "Letter only. Both carry the pack's stored language.",
        "",
        "| Paper | File | Source | Pages | MediaBox | qpdf | /Lang | /Marked | Info /Title | "
        "H1 / H2 / P | MCIDs | ParentTree keys |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for paper, row in (("letter", letter), ("a4", a4)):
        s = row["structure"]
        md.append(
            f"| {paper} | `{row['file']}` | {row['source']} | {row['pages']} | "
            f"{', '.join(f'{w:g}x{h:g}' for w, h in row['media_boxes'])} | {row['qpdf_check']} | "
            f"`{s['lang']}` | {s['marked']} | `{s['info_title']}` | "
            f"{s['struct_elements'].get('H1',0)} / {s['struct_elements'].get('H2',0)} / "
            f"{s['struct_elements'].get('P',0)} | {s['marked_content_ids']} | "
            f"{s['parent_tree_keys']} |"
        )
    md += [
        "",
        "`pdftotext -layout` extracted the authored learner sentence and the answer-guide "
        "reference answer from both files (selectable text, no image of text).",
        "",
        "## Cover line",
        "",
        f"| Paper | Page-1 `Take-home:` count | First line | Longest line (chars, bound 72) |",
        "|---|---|---|---|",
    ]
    for paper, row in (("letter", letter), ("a4", a4)):
        cover = pdftotext(pdf_paths[paper], "-f", "1", "-l", "1", "-layout")
        lines = [line.strip() for line in cover.splitlines() if line.strip()]
        md.append(
            f"| {paper} | {row['cover_take_home_prefixes']} | `{row['cover_first_line']}` | "
            f"{max(len(line) for line in lines)} |"
        )
    md += [
        "",
        "## HTML document",
        "",
        f"- doctype `<!doctype html>`, `lang` from the authored course locale, {evidence['html']['pages']} pages",
        f"- page roles in PDF order: {', '.join(evidence['html']['page_roles'])}",
        "- no `<script>`, `<link>`, `src=`, `href=`, `@import`, `url()`, iframe, object or embed",
        "- the diagram page keeps its text alternative as an accessible region label",
        "- the HTML is returned as content and never adopted into the artifact store: "
        "`artifact.get` remains the only download handle",
        "",
        "## Red evidence (captured before the fix)",
        "",
        "- `audit/gm-018/red-evidence-three-tests.txt` — the three named tests run against "
        "`e1f8e6e` (the GM-005 merge, before any GM-018 source) with this branch's "
        "`tests/test_gm_takehome.py` copied in: "
        "`PYTHONPATH=. python3 -m unittest tests.test_gm_takehome.TakeHomePrintFollowUpTest."
        "test_takehome_exports_standalone_html tests.test_gm_takehome.TakeHomePrintFollowUpTest."
        "test_takehome_pdf_is_tagged tests.test_gm_takehome.TakeHomePrintFollowUpTest."
        "test_takehome_cover_is_single_line` → `Ran 3 tests` / `FAILED (failures=3)`: the v23 "
        "method enum has no `takehome.html`; the PDF carries no `/MarkInfo`; page 1 prints "
        "`Take-home: searing - take-home pack` and `Take-home: Section 1: the sear` (two prefixes).",
        "- `audit/gm-018/red-evidence-language.txt` — the review's language defect reproduced "
        "before the fix: the new `fr-FR` assertion on the **exported artifact** failed with "
        "`AssertionError: 'en' != 'fr-FR'` because `export` built the render pack without the "
        "stored `content_json[\"language\"]`. The same command is green after the fix.",
        "",
        "## Method",
        "",
        "Real `course.create` + `plan.approve` + staged validated `gen_lessons`; "
        "`takehome.preview/create/approve/export` through `api.dispatch`; `takehome.html` for the "
        "document; the Letter PDF is the exported artifact's own bytes and the A4 PDF a labelled "
        "re-render of the same pages at A4 with the pack's stored language; `qpdf --check`, "
        "`pdftotext` and an independent pypdf walk of `/StructTreeRoot` and `/ParentTree`.",
        "",
    ]
    (OUT / "PROOF.md").write_text("\n".join(md), encoding="utf-8")
    print("GM-018 proof: PASS")
    print(json.dumps(evidence["paper"]["letter"]["structure"], indent=1))
    print(evidence["html"]["document_hash"], evidence["html"]["bytes"], "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
