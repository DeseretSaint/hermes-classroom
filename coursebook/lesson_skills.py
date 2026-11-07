"""Which bundled learner skill a chat turn must load — one rule, one place.

The plugin ships two read-only skills (``skills/``) and registers them as
``coursebook:<name>`` at plugin load. Registration is not use: plugin skills are not in the
agent's automatic ``<available_skills>`` index, so a lesson turn only follows one when the
session is *told* to load it. This module decides which, and :func:`attach` puts that
instruction on the turn.

The rule (least surprising, and never a guess)
----------------------------------------------
1. The chat has a **live binding** (``active`` or ``paused``) — it governs a lesson run, so its
   section is in the store: ``coursebook:lesson-tutoring``.
2. The store **knows this chat but has no live binding for it** — a lesson chat whose run was
   superseded or detached. There is no section to read, and the chat is still Coursebook's:
   ``coursebook:learner-coach`` (subject-neutral, needs no lesson row).
3. The store has **no row for this chat at all** — this is an ordinary chat that happens to run
   in the same profile. Nothing is injected. Coursebook never claims a session it did not record.

The membership test is the store's own row for the *stored* session id, never recency and never
"the newest chat". That is what keeps an unrelated conversation clean (``AUDIT.md`` R1).

The store is handed to the turn, not guessed
--------------------------------------------
The binding row that decides the skill also lives in exactly one database, so that file *is* the
store this chat may read. :func:`skill_for_session` returns its absolute path and the bound
``objective_id``, and :func:`instruction` puts both on the turn. The agent never probes candidate
homes: any home on the machine can hold a coursebook DB, so "the one that returns rows" is a
coin-flip between unrelated courses (H-69: a Japanese L0 lesson was taught from a flat-repair
store). A live binding whose objective row is absent from that same store is reported as such and
the turn is told to stand down — never to read a different store instead.

A known boundary, stated rather than papered over
-------------------------------------------------
A brand-new chat has no stored id until its first turn, so turn one of a chat this Desktop is
still starting is *not yet* in the store and gets no instruction. The lesson-start path closes
that gap the honest way: the pane creates the chat through the host, binds it **before** the
first turn, and only then reveals it. See ``desktop/plugin.js::startBoundLessonChat``.

Read-only by construction: every function here is a pure read of ``cb.db``. A missing or
unreadable store answers ``None`` (no instruction), never an exception into the turn.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("coursebook")

#: The proven DB-backed tutor (reads the section from ``cb.db``).
TUTOR_SKILL = "coursebook:lesson-tutoring"
#: The subject-neutral coach (needs no lesson row).
COACH_SKILL = "coursebook:learner-coach"

#: Binding statuses that mean "this chat still governs a lesson".
LIVE_STATUSES = ("active", "paused")

#: Why a skill applies. Kept in the answer so the pane and the log can state it.
REASON_LIVE_BINDING = "lesson_binding"
REASON_NO_LIVE_BINDING = "coursebook_chat_without_live_binding"
REASON_UNRELATED = "unrelated_session"
REASON_NO_STORE = "no_store"
#: A live binding whose objective is not in the store it came from: nothing to teach, say so.
REASON_BOUND_OBJECTIVE_MISSING = "bound_objective_not_in_store"


def decide(binding_status: str | None, *, known_chat: bool) -> tuple[str | None, str]:
    """The rule itself, free of I/O so it is trivially testable.

    ``binding_status`` is the newest binding row's status for this chat (``None`` when the store
    has no row for it). ``known_chat`` says the store recorded this chat at all.
    """
    if binding_status in LIVE_STATUSES:
        return TUTOR_SKILL, REASON_LIVE_BINDING
    if known_chat:
        return COACH_SKILL, REASON_NO_LIVE_BINDING
    return None, REASON_UNRELATED


def store_file_path() -> str:
    """The single database this process may read, as an absolute path — never created.

    ``db.store_root()`` is the read-side resolver (no ``mkdir``): the same ``HERMES_HOME`` /
    single-home pin the connection will use. Naming it on the turn removes the probe entirely.
    """
    from . import db

    return str((db.store_root() / "data.db").resolve())


def skill_for_session(session_id: Any) -> dict[str, Any]:
    """Resolve the skill for one *stored* session id.

    Returns ``{"skill", "reason", "binding_status", "objective_id", "binding_id", "store_path",
    "objective_in_store"}``. Never raises: a hook that cannot read state must not fail the turn,
    and an absent store is the ordinary state of an install nobody has opened yet.

    ``store_path`` is the one database the turn may read and it is always the store the binding
    was found in, so the agent never has to choose between homes (H-69).
    """
    answer: dict[str, Any] = {
        "skill": None,
        "reason": REASON_UNRELATED,
        "binding_status": None,
        "objective_id": None,
        "binding_id": None,
        "store_path": None,
        "objective_in_store": None,
    }
    stored = str(session_id or "").strip()
    if not stored:
        return answer
    try:
        from . import db

        if not db.store_exists():
            answer["reason"] = REASON_NO_STORE
            return answer
        with db.read() as connection:
            row = connection.execute(
                "SELECT id, status, objective_id FROM bindings WHERE stored_session_id = ?"
                " ORDER BY (status IN ('active', 'paused')) DESC, revision DESC, updated_at DESC"
                " LIMIT 1",
                (stored,),
            ).fetchone()
            objective_in_store = None
            if row is not None and row["objective_id"]:
                objective_in_store = (
                    connection.execute(
                        "SELECT 1 FROM objectives WHERE id = ?", (str(row["objective_id"]),)
                    ).fetchone()
                    is not None
                )
    except Exception:  # noqa: BLE001 - a read that fails injects nothing
        answer["reason"] = "unreadable"
        return answer
    status = str(row["status"]) if row is not None else None
    skill, reason = decide(status, known_chat=row is not None)
    objective_id = str(row["objective_id"]) if row is not None and row["objective_id"] else None
    if reason == REASON_LIVE_BINDING and (objective_id is None or objective_in_store is False):
        # A live binding is not a lesson row: without its objective in *this* store there is
        # nothing to teach, and falling back to another home is the defect this guards (H-69).
        reason = REASON_BOUND_OBJECTIVE_MISSING
    answer.update(
        {
            "skill": skill,
            "reason": reason,
            "binding_status": status,
            "objective_id": objective_id,
            "binding_id": str(row["id"]) if row is not None else None,
            "store_path": store_file_path() if skill == TUTOR_SKILL else None,
            "objective_in_store": objective_in_store,
        }
    )
    return answer


def instruction(
    skill: str,
    reason: str = "",
    *,
    store_path: str | None = None,
    objective_id: str | None = None,
    binding_id: str | None = None,
) -> str:
    """The turn-local instruction that makes the agent actually load the skill.

    Plain text on the current user message (``pre_llm_call`` context injection). It names the
    namespaced skill so a same-named user skill in ``~/.hermes/skills`` can never be mistaken
    for the bundled one, and it repeats the two rules a learner turn must never break — both
    skills already carry them, and a reminder on the turn is what makes the load stick.

    For the tutor it also names the **one** store this turn may read, its absolute path and the
    bound objective id. That is the whole H-69 fix: no candidate list, no "use the store that
    returns rows", so a coursebook DB in some other home can never answer for this lesson.
    """
    if skill == TUTOR_SKILL:
        if reason == REASON_BOUND_OBJECTIVE_MISSING:
            scope = (
                f" This chat's binding ({binding_id or 'the live binding'}) names objective"
                f" {objective_id or '(none stored)'}, and the store it belongs to —"
                f" {store_path or 'the store the plugin names'} — has no row for it."
                " Do not teach any section and do not read any other Coursebook store: tell the"
                " learner the bound lesson has no stored content and to reopen it from the course"
                " pane."
            )
        else:
            only_store = (
                f" The only store you may read this turn is `{store_path}`"
                if store_path
                else " The only store you may read is the one the plugin names on this turn"
            )
            bound = f" and it holds the bound objective `{objective_id}`." if objective_id else "."
            scope = (
                " This chat governs a lesson run: read the open section out of the Coursebook"
                " store (objective, check stimulus, reference answer) rather than guessing it."
                + only_store
                + bound
                + " Do not probe, glob, or open any other Coursebook store — another HERMES_HOME,"
                " a QA home or a test home — even if it returns rows for the same shape."
            )
    else:
        scope = (
            " This chat is a Coursebook chat with no live lesson run: ask which course and"
            " section the learner means before teaching anything, and do not invent a lesson."
        )
    return (
        f"[Coursebook] Load the bundled skill `{skill}` before you reply:"
        f' call skill_view(name="{skill}") and follow it for this turn.'
        f"{scope}"
        " Never print the reference answer; end with exactly one check in the section's own"
        " answer format."
    )


def attach(
    hook: Any,
    skill: str | None,
    reason: str = "",
    *,
    store_path: str | None = None,
    objective_id: str | None = None,
    binding_id: str | None = None,
) -> Any:
    """Put the instruction on a ``pre_llm_call`` return value without disturbing the gate.

    A block stays a block (no inference runs, so no skill is needed); a teaching context keeps
    its own words and gains the instruction ahead of them.
    """
    if not skill:
        return hook
    note = instruction(
        skill,
        reason,
        store_path=store_path,
        objective_id=objective_id,
        binding_id=binding_id,
    )
    if hook is None:
        return {"context": note}
    if isinstance(hook, dict) and hook.get("action") == "block":
        return hook
    if isinstance(hook, dict) and isinstance(hook.get("context"), str):
        return {**hook, "context": note + "\n\n" + hook["context"]}
    return hook
