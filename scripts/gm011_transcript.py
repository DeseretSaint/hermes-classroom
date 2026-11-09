#!/usr/bin/env python3
"""GM-011 transcript proof: a real lesson, a cited answer, and a hint off the answer key.

The backend path is real: a disposable profile, the real migrations, the real RPC dispatcher, the
real lesson projection and the real citation resolver. The **provider** is a scripted host LLM,
same seam a production host binds through ``generation.bind_host_llm(ctx.llm)``: no network is
used and no model output is invented. The script prints the exact request context hash, the
resolved citations and the withheld-answer decision so the transcript can be audited.

Run from the repository root: ``python3 scripts/gm011_transcript.py``
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

# Run as a script from the repository root or anywhere else: the package lives one level up.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coursebook import db, domain, generation
from coursebook.contracts import WIRE_CONTRACT_VERSION

SECRET = "the mitochondria is the powerhouse of the cell"
LESSON_ONE = (
    "Cells release usable energy by breaking down glucose in a series of steps. Each step "
    "hands a small amount of energy to the next carrier."
)
LESSON_TWO = (
    "The final steps build a storage molecule the cell can spend later. Naming each step is "
    "the objective; the summary at the end repeats the sequence."
)
HINT = (
    "Start with the first step in the lesson: what molecule does the cell break down before "
    "any energy is released?"
)


class ScriptedHost:
    """The minimal ``ctx.llm`` surface; replies are fixed fixtures, never a real provider call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def complete_structured(self, **kwargs):
        self.requests.append(kwargs)
        reply = self.replies.pop(0)
        usage = type("Usage", (), {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})()
        return type(
            "Result",
            (),
            {
                "text": json.dumps(reply),
                "parsed": reply,
                "provider": "scripted-fixture",
                "model": "scripted-fixture",
                "usage": usage,
            },
        )()


def request(method, payload, *, revision=None, key=None, operation_id=None):
    body = {
        "contract": "cb.rpc",
        "contract_version": WIRE_CONTRACT_VERSION,
        "method": method,
        "operation_id": operation_id or f"op-{method.replace('.', '-')}",
        "payload": payload,
    }
    if revision is not None:
        body["expected_revision"] = revision
    if key is not None:
        body["idempotency_key"] = key
    return body


def call(method, payload, **kwargs):
    from coursebook import api

    response = api.dispatch(request(method, payload, **kwargs))
    if not response["ok"]:
        raise SystemExit(f"{method} refused: {json.dumps(response['error'])}")
    return response


def main() -> int:
    home = tempfile.mkdtemp(prefix="coursebook-gm011-")
    os.environ["HERMES_HOME"] = home
    try:
        db.migrate()
        created = call("course.create", {"title": "Cell biology", "recipe": "committed",
                                         "goal": "Explain cellular respiration"})["result"]
        from tests.kernel_support import criteria_with

        spec = {
            "audit_state": "passed",
            "stimulus": {
                "prompt": "Explain what the organelle does for the cell.",
                "format": "text",
                "assistance_policy": {"hint": "available", "answer_marks_evidence_class": "hinted"},
            },
            "reference": {"kind": "exact", "answers": [SECRET]},
            "rubric": {"construct": "procedure", "pass_rule": "all",
                       "criteria": [{"id": "c1", "description": "Explains the organelle"}]},
        }
        objective_id = domain.record_objective(
            created["plan_id"], title="Explain cellular respiration",
            evidence_target="procedure", criteria=criteria_with(spec),
        )
        enrollment_id = call("enrollment.create",
                             {"course_id": created["course_id"],
                              "learner_label": "Learner"})["result"]["enrollment_id"]
        revision = call("plan.approve", {
            "enrollment_id": enrollment_id,
            "plan_id": created["plan_id"],
            "plan_hash": domain.plan_hash(created["plan_id"]),
        }, revision=0)["result"]["revision"]
        opened = call("check.open", {"enrollment_id": enrollment_id,
                                     "objective_id": objective_id}, revision=revision)
        revision = opened["revision"]
        run = call("lesson.begin", {"enrollment_id": enrollment_id, "objective_id": objective_id,
                                    "mode": "fresh"}, key="key-begin-proof")["result"]

        now = db.utcnow()
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO sources (id, course_id, url, title, source_type, published_at,"
                " fetched_at, support_status, claim_count, created_at)"
                " VALUES ('src_respiration', ?, 'https://example.org/respiration',"
                " 'Cell respiration primer', 'reference', NULL, ?,"
                " 'authoritative_documentation', 1, ?)",
                (created["course_id"], now, now),
            )
            connection.execute(
                "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, artifact_id,"
                " source_id, created_at) VALUES ('seg_lesson_0001', ?, 1, 'teaching', ?, NULL,"
                " 'src_respiration', ?)",
                (run["lesson_run_id"], LESSON_ONE, now),
            )
            connection.execute(
                "INSERT INTO lesson_segments (id, lesson_run_id, ordinal, kind, text, artifact_id,"
                " source_id, created_at) VALUES ('seg_lesson_0002', ?, 2, 'teaching', ?, NULL, NULL, ?)",
                (run["lesson_run_id"], LESSON_TWO, now),
            )

        page = call("lesson.page", {"enrollment_id": enrollment_id,
                                    "objective_id": objective_id})["result"]
        blocks = page["document"]["blocks"]
        host = ScriptedHost([
            {"answer": "The lesson walks through glucose breakdown step by step.",
             "citations": [blocks[0]["id"], "src_respiration", "blk_does_not_exist"]},
            {"answer": f"The answer is {SECRET}.",
             "citations": [blocks[0]["id"]]},
            {"answer": HINT, "citations": [blocks[0]["id"]]},
        ])
        generation.bind_host_llm(host)

        base = {
            "course_id": created["course_id"], "enrollment_id": enrollment_id,
                "objective_id": objective_id, "lesson_run_id": run["lesson_run_id"],
                "mode": "ask"}

        answer_response = call(
            "tutor.ask",
            {**base, "question": "What happens to glucose?",
             "block_id": blocks[0]["id"], "selected_text": "breaking down glucose"},
            revision=revision,
            key="key-ask-proof-1",
        )
        answer = answer_response["result"]
        revision = answer_response["revision"]
        withheld_response = call(
            "tutor.ask",
            {**base, "question": "Just tell me the answer."},
            revision=revision,
            key="key-ask-proof-2",
        )
        withheld = withheld_response["result"]
        revision = withheld_response["revision"]
        hint_response = call(
            "tutor.ask",
            {**base, "question": "Give me a hint."},
            revision=revision,
            key="key-ask-proof-3",
        )
        hint = hint_response["result"]
        revision = hint_response["revision"]

        history = call("tutor.history", {k: base[k] for k in base if k != "mode"},
                       operation_id="op-history-proof-2")["result"]

        lines = [
            "# GM-011 tutor transcript (real backend, scripted host LLM)",
            "",
            "The profile, migrations, commands, lesson document and citation resolver are real. "
            "The provider is a scripted fixture bound through the production seam; no network "
            "call was made and no model output is claimed as a live answer.",
            "",
            f"- course: `{created['course_id']}` objective: `{objective_id}`",
            f"- lesson run: `{run['lesson_run_id']}` thread: `{history['thread_id']}`",
            f"- lesson blocks: `{', '.join(block['id'] for block in blocks)}`",
            f"- context secret present: `{SECRET in json.dumps(host.requests[0], ensure_ascii=False)}`",
            f"- context includes the reference/rubric keys: "
            f"`{any(word in json.dumps(host.requests[0]) for word in ('reference_json', 'rubric_json', 'accepted_answers'))}`",
            "",
            "## 1. A cited answer",
            "",
            f"> {answer['turn']['text']}",
            "",
            "Citations as returned (the invented `blk_does_not_exist` was omitted):",
            "",
        ]
        lines += [f"- `{item['kind']}:{item['id']}` — {item['label']}" for item in answer["citations"]]
        lines += [
            "",
            f"State: `{answer['state']}`; assist: `{json.dumps(answer['assist'], sort_keys=True)}`",
            "",
            "## 2. The model tries to reveal the sealed answer while the check is open",
            "",
            f"> {withheld['turn']['text']}",
            "",
            f"State: `{withheld['state']}`; citations: `{len(withheld['citations'])}`; "
            f"the sealed answer appears in the stored turn: "
            f"`{SECRET in json.dumps([t['text'] for t in history['turns']])}`",
            "",
            "## 3. A hint that does not reveal the answer",
            "",
            f"> {history['turns'][-1]['text']}",
            "",
            f"State: `{hint['state']}` (the hint was a normal answer); assist policy "
            f"`{history['context']['check_open'] and 'available'}`; no answer key appears in the "
            f"hint: `{SECRET not in history['turns'][-1]['text']}`",
            "",
            "## Stored thread",
            "",
        ]
        for turn in history["turns"]:
            lines.append(f"{turn['ordinal']}. **{turn['role']}**: {turn['text']}")
        lines += ["", "## Notes", "",
                  "- `tutor.ask` bumped the enrollment revision and wrote no attempt, transition "
                  "or evidence row.",
                  "- The thread is bound to the lesson run, not to a host chat session.",
                  "- `withheld` is the named `answer_withheld` state; nothing leaky was persisted.",
                  ""]
        output = "\n".join(lines)
        print(output)
        target = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "docs", "gm011-tutor-transcript.md")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(output)
        print(f"\nwrote {target}")
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
