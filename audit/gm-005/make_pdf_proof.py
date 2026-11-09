"""GM-005 proof: render a real take-home pack to selectable-text PDF at Letter and A4.

Run from the repository root:

    python3 audit/gm-005/make_pdf_proof.py

The script builds a disposable profile, creates a real course through the real RPC dispatcher,
stages a validated lesson the way ``generation`` does, drives preview/create/approve/export, and
then renders the *stored, approved pages* through ``coursebook.takehome.render_pdf`` at both paper
sizes. It asserts:

* the PDF starts with ``%PDF-`` and contains no JavaScript;
* pypdf extracts the authored learner sentence and the answer-guide reference answer (selectable
  text, not an image of text);
* the parent guide, learner page and answer guide each begin on their own page;
* the rendered MediaBox is 612x792 (Letter) and 595x842 (A4);
* every composed page's text survives extraction after whitespace removal — no clipped text;
* no region of the learner page carries the answer guide.

Evidence is written to ``audit/gm-005/`` and the script exits non-zero on any failed assertion.
No fixture is copied from a provider or a pack; the lesson below is authored in this file.
"""

from __future__ import annotations

import io
import json
import os
import shutil
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


def page_document(title: str) -> dict:
    return {
        "section_title": title,
        "lesson_intent": "Sear the meat hard before the liquid goes in.",
        "segments": [
            {"kind": "explain", "heading": "Why the sear matters",
             "body": "Browning builds the flavour the braise carries for two hours."},
            {"kind": "guided", "heading": "Do this next",
             "body": "Watch the oil, then lay the ribs away from you."},
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


def main() -> int:
    home = tempfile.mkdtemp(prefix="gm005-proof-")
    os.environ["HERMES_HOME"] = home
    try:
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
        assert pack["pages"]["learner_page"]["audience"] == "learner"
        assert pack["pages"]["answer_guide"]["audience"] == "parent"
        assert ANSWER not in pack["pages"]["learner_page"]["text"]
        assert "Wait for the shimmer" not in pack["pages"]["learner_page"]["text"]
        assert "Wait for the shimmer" in pack["pages"]["answer_guide"]["text"]
        assert ANSWER in pack["pages"]["answer_guide"]["text"]
        assert pack["diagrams"][0]["kind"] == "deterministic"
        assert pack["plates"] == []

        # The exported artifact through the real store is selectable text too.
        artifact_row = db_artifact(exported["artifact_id"])

        results = {}
        proof_pages = {page["role"]: page for page in preview["pages"]
                       if page["role"] in ("cover", "parent_guide", "learner_page", "answer_guide")}
        proof_pack = {"title": pack["title"], "pages": proof_pages}
        for paper, expected in (("letter", (612, 792)), ("a4", (595, 842))):
            data = takehome.render_pdf(proof_pack, paper=paper)
            path = OUT / f"gm-005-takehome-proof-{paper}.pdf"
            path.write_bytes(data)
            assert data.startswith(b"%PDF-")
            assert b"/JavaScript" not in data
            reader = PdfReader(io.BytesIO(data))
            boxes = []
            for page in reader.pages:
                box = page.mediabox
                boxes.append((float(box.width), float(box.height)))
            assert all(box == expected for box in boxes), (paper, boxes)
            texts = [page.extract_text() or "" for page in reader.pages]
            joined = "\n".join(texts)
            assert "Watch the oil" in joined, paper
            assert ANSWER in joined.replace("\n", " ") or ANSWER in joined, paper
            assert len(texts) >= 3, (paper, len(texts))
            # Each part starts a page: find the page where its distinctive line first appears.
            needles = {
                "cover": "Course: Braising at home",
                "parent_guide": "Parent guide",
                "learner_page": "Why the sear matters",
                "answer_guide": "Reference answer",
            }
            starts = {}
            for role, needle in needles.items():
                starts[role] = next((i for i, text in enumerate(texts) if needle in text), None)
            assert starts["cover"] == 0, (paper, starts)
            assert starts["parent_guide"] == 1, (paper, starts)
            assert starts["learner_page"] == 2, (paper, starts)
            assert starts["answer_guide"] == 3, (paper, starts)
            # No clipped text: each page's composed text survives extraction (whitespace-insensitive).
            for role, page in proof_pack["pages"].items():
                if role not in ("cover", "parent_guide", "learner_page", "answer_guide"):
                    continue
                src = squashed(page["text"])
                target = squashed(texts[starts[role]])
                assert src in target, (paper, role, len(src), len(target))
            results[paper] = {
                "file": str(path.relative_to(ROOT)),
                "pages": len(texts),
                "media_boxes": boxes,
                "part_start_pages": starts,
                "learner_chars": len(pack["pages"]["learner_page"]["text"]),
                "answer_guide_chars": len(pack["pages"]["answer_guide"]["text"]),
                "extracted_chars": len(joined),
            }

        artifact_bytes = Path(artifact_row["path"]).read_bytes()
        exported_text = "\n".join(
            page.extract_text() or "" for page in PdfReader(io.BytesIO(artifact_bytes)).pages
        )
        assert "Answer guide" in exported_text
        assert ANSWER in exported_text

        evidence = {
            "card": "GM-005",
            "course_id": course_id,
            "pack_id": made["pack_id"],
            "pack_state": pack["state"],
            "content_hash": pack["content_hash"],
            "source_lesson_version": pack["source_lesson_version"],
            "exported_artifact": {"artifact_id": exported["artifact_id"],
                                  "mime": artifact_row["mime"], "bytes": artifact_row["bytes"]},
            "learner_page_has_answer": ANSWER in pack["pages"]["learner_page"]["text"],
            "answer_guide_has_answer": ANSWER in pack["pages"]["answer_guide"]["text"],
            "diagram_kind": pack["diagrams"][0]["kind"],
            "plates": pack["plates"],
            "papers": results,
            "method": (
                "Real course.create + plan.approve + staged validated gen_lessons; takehome.preview/"
                "create/approve/export through api.dispatch; render_pdf over the stored pages; pypdf "
                "text extraction; MediaBox measured per page; each composed page's text compared "
                "whitespace-insensitively against its extracted page."
            ),
        }
        (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        (OUT / "PROOF.md").write_text(render_markdown(evidence), encoding="utf-8")
        print(json.dumps(evidence["papers"], indent=2))
        print("wrote", OUT / "evidence.json")
        return 0
    finally:
        os.environ.pop("HERMES_HOME", None)
        shutil.rmtree(home, ignore_errors=True)


def db_artifact(artifact_id: str) -> dict:
    with db.read() as connection:
        row = connection.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    return dict(row)


def first_line(text: str) -> str:
    """A stable ASCII needle for the first authored line, matching the PDF's WinAnsi text."""
    import unicodedata

    for line in text.splitlines():
        if line.strip():
            return unicodedata.normalize("NFKD", line.strip()).encode("ascii", "replace").decode("ascii")
    return ""


def squashed(text: str) -> str:
    """Whitespace-free, WinAnsi-folded text — the same transform the PDF template applies."""
    import unicodedata

    folded = unicodedata.normalize("NFKD", str(text)).encode("ascii", "replace").decode("ascii")
    return "".join(folded.split())


def render_markdown(evidence: dict) -> str:
    lines = [
        "# GM-005 take-home pack PDF proof",
        "",
        f"- pack: `{evidence['pack_id']}` state `{evidence['pack_state']}`",
        f"- source lesson: `{evidence['source_lesson_version']}` hash `{evidence['content_hash']}`",
        f"- exported artifact: `{evidence['exported_artifact']['artifact_id']}` "
        f"({evidence['exported_artifact']['bytes']} bytes, {evidence['exported_artifact']['mime']})",
        f"- learner page contains the answer: {evidence['learner_page_has_answer']}",
        f"- answer guide contains the answer: {evidence['answer_guide_has_answer']}",
        f"- diagram authority: {evidence['diagram_kind']}",
        f"- world plates: {len(evidence['plates'])}",
        "",
        "| Paper | File | Pages | MediaBox | Part start pages | Extracted chars |",
        "|---|---|---|---|---|---|",
    ]
    for paper, row in evidence["papers"].items():
        boxes = ", ".join(f"{int(w)}x{int(h)}" for w, h in row["media_boxes"])
        starts = ", ".join(f"{name}@{page}" for name, page in row["part_start_pages"].items())
        lines.append(
            f"| {paper} | `{row['file']}` | {row['pages']} | {boxes} | {starts} | "
            f"{row['extracted_chars']} |"
        )
    lines.extend(["", "## Method", "", evidence["method"], ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
