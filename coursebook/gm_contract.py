"""Frozen, additive Game Mode contract (GM-001).

This module is the single source of truth for the names the Game Mode program is built
against: the course presentation mode, the world grammar/role vocabulary, the take-home,
homework, engagement and tutor enums, and the ``cb.rpc`` method manifest that every later
backend card implements.

It is a *pure* contract module. It imports no provider SDK, opens no database and touches no
UI. A value here is a name or a rule, never a behaviour: the handler that uses it lives in
``coursebook.domain``, and the migration that stores it is
``coursebook/migrations/0013_game_mode_contracts.sql``.

Rules this module encodes (``docs/GM-CONTRACT.md`` is the prose form):

* ``PresentationMode`` is durable on the course and nullable in the database. A NULL or
  unrecognised stored value reads as ``textbook``; there is no backfill.
* ``WorldGrammar`` is a subject grammar, not a fantasy skin; the default is ``field_atlas``
  only because it is the house style, not permission to use it for a technical procedure.
* ``WorldRole`` is the world asset budget, enforced by the backend (one hero, one cover, at
  most six section cards, at most two lesson scenes).
* ``TakeHomeAudience``, ``HomeworkKind`` and ``HomeworkState`` never express a grade:
  homework completion is ``self_reported_done`` or ``parent_reported_done``, never a pass.
* ``TutorMode`` separates Ask from Practice; both live in the same lesson-bound thread.
"""

from __future__ import annotations

from enum import Enum

#: Manifest version. Bumped only for a renamed/retyped entry, never for a new method.
GM_CONTRACT_VERSION = 1

#: The migration that creates the storage for every name below.
GM_MIGRATION = "0013_game_mode_contracts.sql"


class _Frozen(str, Enum):
    """A ``str`` enum whose members serialize as their bare value on the wire."""

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return str(self.value)


class PresentationMode(_Frozen):
    """The durable course mode (``courses.presentation_mode``)."""

    GAME = "game"
    TEXTBOOK = "textbook"


#: The read fallback for a NULL or unrecognised stored mode. An old course has no approved
#: world, so claiming it is a game course would be a fabricated fact.
DEFAULT_PRESENTATION_MODE = PresentationMode.TEXTBOOK


class WorldGrammar(_Frozen):
    """Subject visual grammars (plan §4.3). A grammar is chosen deterministically."""

    FIELD_ATLAS = "field_atlas"
    WORKSHOP_MANUAL = "workshop_manual"
    OBSERVATORY = "observatory"
    KITCHEN_TABLE = "kitchen_table"
    ARCHIVE_DESK = "archive_desk"
    STUDIO_BENCH = "studio_bench"
    LAB_BENCH = "lab_bench"
    INSTRUMENT_BOARD = "instrument_board"


#: House style for an unknown subject. A starting point, not a universal skin.
DEFAULT_WORLD_GRAMMAR = WorldGrammar.FIELD_ATLAS


class WorldRole(_Frozen):
    """One world plate's role in the course-level kit."""

    HERO = "hero"
    COVER = "cover"
    SECTION = "section"
    LESSON_SCENE = "lesson_scene"


#: Backend-enforced asset budget (plan §4.5). A retry reuses these; it never pays twice for the
#: same ``style_hash + course_hash + role + section_id``.
WORLD_ROLE_LIMITS: dict[str, int] = {
    WorldRole.HERO.value: 1,
    WorldRole.COVER.value: 1,
    WorldRole.SECTION.value: 6,
    WorldRole.LESSON_SCENE.value: 2,
}

#: Hard negatives every world prompt carries (plan §4.2/§4.7).
WORLD_PROMPT_FORBIDDEN: tuple[str, ...] = (
    "text",
    "letters",
    "labels",
    "numbers",
    "logos",
    "watermarks",
    "ui chrome",
    "invented measurements",
    "depicted safety procedure",
)


class WorldState(_Frozen):
    """World Studio state machine (``course_worlds.state``)."""

    NOT_REQUESTED = "not_requested"
    CONCEPTS_GENERATING = "concepts_generating"
    CONCEPTS_READY = "concepts_ready"
    STYLE_SELECTED = "style_selected"
    KIT_GENERATING = "kit_generating"
    KIT_READY = "kit_ready"
    APPROVED = "approved"
    FAILED = "failed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class TakeHomeAudience(_Frozen):
    """Who a take-home pack or homework task is written for."""

    LEARNER = "learner"
    PARENT = "parent"


class TakeHomeKind(_Frozen):
    """The three take-home deliverables. None is a course or a ``cb.pack``."""

    PRINT_PACK = "print_pack"
    ACTIVITY_PLAN = "activity_plan"
    HOMEWORK_SHEET = "homework_sheet"


class TakeHomeState(_Frozen):
    """Take-home lifecycle. Export requires an approved row for the previewed pages."""

    DRAFT = "draft"
    PREVIEWED = "previewed"
    APPROVED = "approved"
    EXPORTED = "exported"
    SUPERSEDED = "superseded"


class HomeworkKind(_Frozen):
    """Away-from-screen task kinds (plan §10A.4)."""

    REAL_WORLD_USE = "real_world_use"
    OBSERVE = "observe"
    LABEL = "label"
    PRACTICE = "practice"
    MAKE = "make"
    TEACH_BACK = "teach_back"


class HomeworkState(_Frozen):
    """Homework task lifecycle. Completion is reported, never graded."""

    PROPOSED = "proposed"
    ASSIGNED = "assigned"
    SELF_REPORTED_DONE = "self_reported_done"
    PARENT_REPORTED_DONE = "parent_reported_done"
    SKIPPED = "skipped"
    EXPIRED = "expired"


#: The only two completion states. Neither is a pass, a transition or a mastery claim.
HOMEWORK_COMPLETION_STATES: tuple[str, ...] = (
    HomeworkState.SELF_REPORTED_DONE.value,
    HomeworkState.PARENT_REPORTED_DONE.value,
)

#: The bounded task length. "Practise for ten minutes" is not a task.
HOMEWORK_MINUTES_MIN = 3
HOMEWORK_MINUTES_MAX = 10


class HomeworkEventKind(_Frozen):
    """Append-only event trail (``homework_events.kind``)."""

    PROPOSED = "proposed"
    ASSIGNED = "assigned"
    EDITED = "edited"
    SELF_REPORTED = "self_reported"
    PARENT_REPORTED = "parent_reported"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class EngagementAction(_Frozen):
    """A real action XP may be awarded for (plan §10B.2). No timers, no page opens."""

    LESSON_STEP = "lesson_step"
    CHECK_SUBMITTED = "check_submitted"
    REVIEW = "review"
    HOMEWORK_COMPLETED = "homework_completed"
    RETURNED = "returned"


class TutorMode(_Frozen):
    """The two modes of the one tutor rail.

    Ask is lesson Q&A; Practice reuses the existing ``practice.*`` scene inside the same
    thread. Neither writes an attempt, a transition or evidence.
    """

    ASK = "ask"
    PRACTICE = "practice"


class TutorTurnRole(_Frozen):
    """A persisted turn's speaker (``tutor_turns.role``)."""

    LEARNER = "learner"
    TUTOR = "tutor"


def read_presentation_mode(stored: object) -> str:
    """The course mode a read reports for *stored* ``courses.presentation_mode``.

    NULL means "never chose", not "textbook was chosen": both read as Textbook, and the caller
    must not write a value back. An unknown stored string is treated the same way rather than
    leaking a value no contract defines.
    """
    if isinstance(stored, str) and stored == PresentationMode.GAME.value:
        return PresentationMode.GAME.value
    return PresentationMode.TEXTBOOK.value


#: Game tables whose bytes are *art*. A world kit's plates are course-level orientation art: they
#: carry no teaching fact, no check, no attempt, no evidence and no player state, so ``cb.pack`` v3
#: may carry them in its ``presentation`` block and an import may rebuild the world rows. This is
#: the only exception to the rule below, and it is art-only by construction: there is no field on
#: ``course_worlds``/``world_assets`` that can hold a verdict, a score or a play event.
GM_ART_TABLES: tuple[str, ...] = ("course_worlds", "world_assets")

#: Tables that exist for the Game Mode program. None may be joined by an evidence, parent, pack or
#: export read, except the art tables above (asserted by ``tests/test_gm_contract.py``).
GM_TABLES: tuple[str, ...] = (
    "course_worlds",
    "world_assets",
    "takehome_packs",
    "homework_tasks",
    "homework_events",
    "game_engagement",
    "tutor_threads",
    "tutor_turns",
)

#: The Game tables no pack, export or evidence read may ever name: gameplay, homework and tutor
#: state are not content, and exporting them would turn a course package into a history leak.
GM_NEVER_EXPORTED_TABLES: tuple[str, ...] = tuple(
    table for table in GM_TABLES if table not in GM_ART_TABLES
)

#: Columns/names that must never appear on a Game Mode table: a second evidence store is a
#: refusal, not an implementation detail (plan §13).
GM_FORBIDDEN_COLUMNS: tuple[str, ...] = (
    "evidence_class",
    "evidence_id",
    "verdict",
    "passed",
    "score",
    "mastery",
    "grade",
    "rating",
    "stars",
)

#: The 18 ``cb.rpc`` methods this card freezes, in the order the card names them.
CARD_GM_METHODS: tuple[str, ...] = (
    "world.read",
    "world.style.preview",
    "world.generate",
    "world.approve",
    "takehome.sources",
    "takehome.preview",
    "takehome.create",
    "takehome.approve",
    "takehome.export",
    "takehome.read",
    "homework.create",
    "homework.read",
    "homework.complete",
    "homework.skip",
    "engagement.read",
    "engagement.award",
    "tutor.ask",
    "tutor.history",
)

#: One extra method is frozen here because plan §3.3/§9.3 requires a durable mode switch and no
#: card in the DAG owns it: the Home/mode card (GM-002) calls it. Freezing the name now stops a
#: later worker inventing ``course.mode.switch`` or writing ``courses.presentation_mode`` directly.
EXTRA_GM_METHODS: tuple[str, ...] = ("course.mode.set",)


def _method(
    *,
    request: tuple[str, ...],
    response: tuple[str, ...],
    errors: tuple[str, ...],
    kind: str = "read",
    idempotent: bool = True,
    expected_revision: bool = False,
    spends_provider: bool = False,
    job: str | None = None,
    note: str = "",
) -> dict[str, object]:
    return {
        "kind": kind,
        "idempotent": idempotent,
        "requires_expected_revision": expected_revision,
        "spends_provider": spends_provider,
        "job": job,
        "request": request,
        "response": response,
        "errors": errors,
        "note": note,
    }


_READ_ERRORS = ("VALIDATION_FAILED", "NOT_FOUND")
_WRITE_ERRORS = ("VALIDATION_FAILED", "NOT_FOUND", "STALE_REVISION", "IDEMPOTENCY_CONFLICT")

#: ``method -> manifest entry``. Field tuples are the *closed* request/response key sets a
#: handler must accept and return; a key outside them is a contract bug, not an extension.
GM_RPC_METHODS: dict[str, dict[str, object]] = {
    "world.read": _method(
        request=("course_id",),
        response=("course_id", "presentation_mode", "world", "fallback", "revision"),
        errors=_READ_ERRORS,
        note="GET-shaped. `fallback` names the Textbook presentation when no world is approved; "
             "the read never generates art and never writes presentation_mode.",
    ),
    "world.style.preview": _method(
        request=("course_id", "world_id"),
        response=("course_id", "world_id", "concepts", "selected_concept_id", "revision"),
        errors=_READ_ERRORS + ("POLICY_VIOLATION",),
        note="Reads the stored concept boards and the deterministic recommended grammar. No "
             "provider call: concept generation is world.generate(stage=concepts).",
    ),
    "world.generate": _method(
        request=("course_id", "stage", "style_id", "brief_patch", "expected_revision"),
        response=("job_id", "state", "world_id"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION", "HOST_UNAVAILABLE"),
        kind="mutate",
        expected_revision=True,
        spends_provider=True,
        job="media",
        note="A `kind=media` job with brief.stage world_concepts|world_kit. It is never a lesson "
             "job; artifacts are staged before rows, and a retry reuses the cache key.",
    ),
    "world.approve": _method(
        request=("course_id", "world_id", "stage", "approved_hash", "expected_revision"),
        response=("world", "state", "style_hash", "kit_hash", "approved_hash", "assets"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION",),
        kind="mutate",
        expected_revision=True,
        note="Hash-fenced. `stage=style` records the selected concept; `stage=final` accepts the "
             "actual kit and freezes approved_hash. It never approves a partial world.",
    ),
    "takehome.sources": _method(
        request=("course_id", "query"),
        response=("course_id", "objectives", "presentation_mode"),
        errors=_READ_ERRORS,
        note="The Parent Studio picker over one existing course: objective, validated lesson "
             "version, content hash and whether a world plate exists. Read-only.",
    ),
    "takehome.preview": _method(
        request=("course_id", "objective_id", "source_lesson_version", "audience", "kind"),
        response=("content_hash", "preview_hash", "pages", "sources"),
        errors=_READ_ERRORS + ("POLICY_VIOLATION",),
        note="Renders the exact source lesson without persisting an approval. The learner page "
             "never contains the answer guide.",
    ),
    "takehome.create": _method(
        request=("course_id", "objective_id", "source_lesson_version", "audience", "kind",
                 "title", "expected_revision"),
        response=("pack_id", "state", "revision", "content_hash"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION",),
        kind="mutate",
        expected_revision=True,
        note="Binds the new pack row to source_course_id/source_objective_id/"
             "source_lesson_version/content_hash. It never mutates the source course.",
    ),
    "takehome.approve": _method(
        request=("pack_id", "preview_hash", "expected_revision"),
        response=("pack_id", "state", "approval_hash", "approved_at"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION",),
        kind="mutate",
        expected_revision=True,
        note="Hash-fenced on preview_hash: an edit after preview invalidates the approval, not "
             "the source course.",
    ),
    "takehome.export": _method(
        request=("pack_id", "expected_revision"),
        response=("pack_id", "state", "artifact_id", "exported_at"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION", "HOST_UNAVAILABLE"),
        kind="mutate",
        expected_revision=True,
        note="Renders selectable-text PDF/print bytes from an approved pack. No provider call; a "
             "failed render leaves the pack approved with no artifact.",
    ),
    "takehome.read": _method(
        request=("pack_id",),
        response=("pack",),
        errors=_READ_ERRORS,
        note="Reads the stored pack, its sections and its export state. It returns no attempts, "
             "tutor turns or private learner history.",
    ),
    "homework.create": _method(
        request=("course_id", "enrollment_id", "objective_id", "audience",
                 "source_lesson_version", "context", "expected_revision"),
        response=("task_id", "task", "state", "revision"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION", "HOST_UNAVAILABLE"),
        kind="mutate",
        expected_revision=True,
        spends_provider=True,
        note="Proposes one task with one target and one observable success criterion; a generic "
             "task is refused with POLICY_VIOLATION reason=generic_task.",
    ),
    "homework.read": _method(
        request=("task_id",),
        response=("task", "events"),
        errors=_READ_ERRORS,
        note="Reads one task and its append-only events. It is not a course and not a chat.",
    ),
    "homework.complete": _method(
        request=("task_id", "actor", "note", "expected_revision"),
        response=("task", "state", "completed_at"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION",),
        kind="mutate",
        expected_revision=True,
        note="Writes self_reported_done or parent_reported_done plus a homework_events row. It "
             "never writes a pass, a transition or evidence; XP is engagement.award's job.",
    ),
    "homework.skip": _method(
        request=("task_id", "actor", "expected_revision"),
        response=("task", "state"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION",),
        kind="mutate",
        expected_revision=True,
        note="Records an honest skip. No penalty, streak loss or fabricated completion.",
    ),
    "engagement.read": _method(
        request=("course_id", "enrollment_id"),
        response=("xp_total", "level", "progress", "recent_events"),
        errors=_READ_ERRORS,
        note="The Game header read model only. Never returned by an evidence, parent, pack or "
             "export read; Textbook and Guided call nothing here.",
    ),
    "engagement.award": _method(
        request=("course_id", "enrollment_id", "action_kind", "action_id"),
        response=("awarded", "points", "xp_total", "level"),
        errors=("VALIDATION_FAILED", "NOT_FOUND", "IDEMPOTENCY_CONFLICT", "POLICY_VIOLATION"),
        kind="mutate",
        idempotent=True,
        expected_revision=False,
        note="Idempotent per (enrollment_id, action_kind, action_id). An action that is not a "
             "real recorded action is refused; no timer and no page-open award.",
    ),
    "tutor.ask": _method(
        request=("course_id", "enrollment_id", "objective_id", "lesson_run_id", "question",
                 "block_id", "selected_text", "mode", "expected_revision"),
        response=("turn", "thread_id", "citations", "assist", "state"),
        errors=_WRITE_ERRORS + ("POLICY_VIOLATION", "HOST_UNAVAILABLE"),
        kind="mutate",
        expected_revision=True,
        spends_provider=True,
        note="One bounded context envelope, no tools. While a check is open the answer is not "
             "revealed; a hint records through the existing assist path. No attempt/evidence write.",
    ),
    "tutor.history": _method(
        request=("course_id", "enrollment_id", "objective_id", "lesson_run_id"),
        response=("thread_id", "turns", "context"),
        errors=_READ_ERRORS,
        note="Reads the persisted thread for one lesson run. Tutor turns are never exported and "
             "never graded.",
    ),
    "course.mode.set": _method(
        request=("course_id", "mode", "expected_revision"),
        response=("mode", "world_state", "requires_world"),
        errors=_WRITE_ERRORS,
        kind="mutate",
        expected_revision=True,
        note="Durable switch. game without an approved world returns requires_world=true and a "
             "reason instead of changing the mode; switching never rewrites lessons or evidence.",
    ),
}

#: Every frozen method name, card list first then the documented extra.
GM_METHOD_NAMES: tuple[str, ...] = CARD_GM_METHODS + EXTRA_GM_METHODS

#: Request/response keys that would be a second evidence store if they ever appeared.
FORBIDDEN_METHOD_KEYS: tuple[str, ...] = (
    "evidence_class",
    "verdict",
    "passed",
    "score",
    "mastery",
    "grade",
    "rating",
    "stars",
)


def method_manifest(method: str) -> dict[str, object]:
    """The frozen entry for *method*; raise ``KeyError`` for a name no card may invent."""
    return GM_RPC_METHODS[method]


def manifest_methods() -> tuple[str, ...]:
    return tuple(GM_RPC_METHODS)


__all__ = [
    "CARD_GM_METHODS",
    "DEFAULT_PRESENTATION_MODE",
    "DEFAULT_WORLD_GRAMMAR",
    "EXTRA_GM_METHODS",
    "EngagementAction",
    "FORBIDDEN_METHOD_KEYS",
    "GM_CONTRACT_VERSION",
    "GM_ART_TABLES",
    "GM_NEVER_EXPORTED_TABLES",
    "GM_FORBIDDEN_COLUMNS",
    "GM_METHOD_NAMES",
    "GM_MIGRATION",
    "GM_RPC_METHODS",
    "GM_TABLES",
    "HOMEWORK_COMPLETION_STATES",
    "HOMEWORK_MINUTES_MAX",
    "HOMEWORK_MINUTES_MIN",
    "HomeworkEventKind",
    "HomeworkKind",
    "HomeworkState",
    "PresentationMode",
    "TakeHomeAudience",
    "TakeHomeKind",
    "TakeHomeState",
    "TutorMode",
    "TutorTurnRole",
    "WORLD_PROMPT_FORBIDDEN",
    "WORLD_ROLE_LIMITS",
    "WorldGrammar",
    "WorldRole",
    "WorldState",
    "manifest_methods",
    "method_manifest",
    "read_presentation_mode",
]
