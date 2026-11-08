"""Mastery path and checkpoint policy: what a node teaches, what a checkpoint may claim.

This module is the deterministic, side-effect-free half of ``docs/MASTERY-PATH-POLICY.md``. It
decides nothing about a learner and writes nothing; it answers the policy questions the generator,
the review scheduler and the path renderer must answer the same way:

* what five fields a path node carries, and which of them the backend can actually store;
* which checkpoints exist, what evidence each one writes, and which ones the backend may not
  draw yet;
* the pass criterion **per evidence target** (there is no universal "three in a row" rule);
* what a failure does (``needs_review``, never a reset or a lock);
* how a review advances (a failed review keeps its rung, a pass moves exactly one rung);
* how confusable material may be interleaved after acquisition, and never shuffled.

The evidence model itself stays where it already is: only a cold pass reaches
``independent_evidence`` and a cold pass on a due review reaches ``delayed_evidence``
(``coursebook.domain._objective_state_after``). This module never re-labels an attempt and never
projects a score, percentage, streak or mastery label.

Design authority: ``docs/MASTERY-PATH-RESEARCH.md`` (what the learning evidence supports) and
``docs/EXPERIENCE-QUALITY-BAR.md`` Q4/Q6/Q11. The prose contract, including what is spec-only, is
``docs/MASTERY-PATH-POLICY.md``. Keep the two in step: ``tests/test_mastery_path_policy.py``
asserts the mirrored enum and the documented state writes cannot drift.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "BACKEND_CAPABILITIES",
    "CHECKPOINTS",
    "CHECKPOINT_REQUIREMENTS",
    "CHECKPOINT_WRITES",
    "CHECK_FAMILIES",
    "CUMULATIVE_CHECK_REQUIRES",
    "DEFAULT_LADDER",
    "FAILURE_RULE",
    "LADDERS",
    "MISCONCEPTION_FOCUS",
    "NODE_FIELDS",
    "PASS_CRITERIA",
    "STREAK_LENGTH",
    "UnsupportedCheckpoint",
    "checkpoint_supported",
    "drawable_checkpoints",
    "exit_performance_problems",
    "node",
    "node_problems",
    "pass_criterion",
    "plan_checkpoints",
    "plan_policy_lines",
    "review_obligation",
    "review_outcome",
    "review_sequence",
    "review_step",
]

#: Mirrors ``coursebook.generation.EVIDENCE_TARGETS`` / ``coursebook.policy.EVIDENCE_TARGETS``.
#: The copies are asserted against each other in the tests, never imported, so this module stays
#: free of the generation import graph.
CHECK_FAMILIES: tuple[str, ...] = (
    "recall",
    "comprehension",
    "production",
    "discrimination",
    "procedure",
    "transfer",
)

#: The five fields every path node carries (research §2). ``stored_at`` is the only place this
#: policy is allowed to name a storage seam; a field with no seam is spec-only by construction.
NODE_FIELDS: tuple[str, ...] = (
    "exit_performance",
    "prerequisite_units",
    "check_family",
    "misconceptions",
    "review_obligation",
)

#: The capabilities this backend actually has, as of cb.rpc v16 / cb.db v11. This is the honest
#: input to every checkpoint decision: a checkpoint type whose requirement is not in this set may
#: not be drawn, claimed or stored.
BACKEND_CAPABILITIES = frozenset(
    {
        "objective_scoped_check",  # checks.objective_id is NOT NULL; one objective per check
        "delayed_evidence",  # objectives.state has delayed_evidence; L2 kind delayed_retrieval
        "review_ladder",  # coursebook.review derives a due date from L2 passes
        "prerequisite_edges",  # plan_units.prereq_unit_ordinals_json + acquire gate
    }
)

#: What a cumulative checkpoint would need before this product may claim one. There is no
#: unit-scoped check row and no RPC that records a check against a unit: ``checks.objective_id``
#: is required and a check belongs to exactly one objective. Adding it is a separate contract
#: card, not a side effect of a path-policy change.
CUMULATIVE_CHECK_REQUIRES = frozenset({"unit_scoped_check", "cumulative_check"})

#: The three checkpoint types, the question each answers, when it is taken and what state it
#: writes (research §3). ``cumulative`` is recorded here so its refusal is named, not implied.
CHECKPOINTS: dict[str, dict[str, str]] = {
    "gate": {
        "question": "Can they do this now, unaided?",
        "when": "end of the node, on new items",
        "writes": "independent_evidence",
    },
    "delayed": {
        "question": "Does it survive?",
        "when": "at the scheduled cold return",
        "writes": "delayed_evidence",
    },
    "cumulative": {
        "question": "Can they pick the right move among confusable ones?",
        "when": "after several nodes, mixed by confusability",
        "writes": "unit_scoped_evidence",
    },
}

#: A checkpoint type is drawable only when every requirement is a real backend capability.
CHECKPOINT_REQUIREMENTS: dict[str, frozenset[str]] = {
    "gate": frozenset({"objective_scoped_check"}),
    "delayed": frozenset({"objective_scoped_check", "delayed_evidence", "review_ladder"}),
    "cumulative": CUMULATIVE_CHECK_REQUIRES,
}

#: The state word each implemented checkpoint writes. Only the two implemented rows are reachable
#: through :func:`checkpoint_supported` with :data:`BACKEND_CAPABILITIES`.
CHECKPOINT_WRITES: dict[str, str] = {
    kind: str(meta["writes"]) for kind, meta in CHECKPOINTS.items()
}

#: Days until the next cold retrieval, per evidence target. A declared product **heuristic**, not
#: a forgetting curve and not an attainment prediction (``docs/AUDIT.md`` R9/R10). ``review.py``
#: imports this table so there is one ladder, not two.
LADDERS: dict[str, tuple[int, ...]] = {
    "recall": (1, 3, 7, 16, 35),
    "comprehension": (2, 5, 12, 28),
    "production": (3, 7, 16, 35),
    "discrimination": (3, 7, 16, 35),
    "procedure": (3, 7, 16, 35),
    "transfer": (7, 21, 45),
}
DEFAULT_LADDER: tuple[int, ...] = (2, 5, 12, 28)

#: The pass criterion is defined **per evidence target** and shown as a rule. There is
#: deliberately no streak constant: Kulik's mastery programmes support mastery *plus correction*,
#: not a magic number of correct answers in a row (research §3).
STREAK_LENGTH: int | None = None

#: One gate cold pass and one delayed cold pass on an item not seen in that exact form. The delay
#: is the target's first ladder rung; the ladder is the product's rule, not a measured optimum.
PASS_CRITERIA: dict[str, dict[str, Any]] = {
    family: {
        "gate_cold_passes": 1,
        "delayed_cold_passes": 1,
        "min_delay_days": LADDERS[family][0],
        "rule": (
            "one cold pass on an unseen form, then one cold pass after at least "
            f"{LADDERS[family][0]} day(s); hints and shown answers do not count"
        ),
        "probabilistic_claim": False,
    }
    for family in CHECK_FAMILIES
}

#: The misconception class the check for each family must be able to catch. This is guidance for
#: the check author (and a named gap: no backend field stores an authored misconception).
MISCONCEPTION_FOCUS: dict[str, str] = {
    "recall": "confuses two forms that sound or look alike",
    "comprehension": "reads the surface wording without the intended relation",
    "production": "retrieves the form but applies it with the wrong grammar or register",
    "discrimination": "collapses a category boundary that the confusable pair depends on",
    "procedure": "omits or reorders a step, or skips a stop/safety condition",
    "transfer": "matches the surface form of a worked example instead of the underlying rule",
}

#: The failure rule is one miss = ``needs_review``; two misses on **different check forms** =
#: re-teach with a different representation. It never resets the course and never locks the path.
FAILURE_RULE: dict[str, Any] = {
    "miss_state": "needs_review",
    "reteach_after_misses": 2,
    "reteach_requires_different_forms": True,
    "same_form_repeats_do_not_count": True,
    "resets_course": False,
    "locks_path": False,
    "offer": "continue_with_unresolved",
}


class UnsupportedCheckpoint(ValueError):
    """A checkpoint the backend cannot record was requested; drawing it would be a false claim."""


def _family(value: Any) -> str:
    family = str(value or "").strip()
    if family not in CHECK_FAMILIES:
        raise ValueError(f"unknown check family {value!r}; expected one of {CHECK_FAMILIES}")
    return family


def pass_criterion(family: str) -> dict[str, Any]:
    """The declared pass criterion for one check family (a rule, not a scientific law)."""
    key = _family(family)
    return {"check_family": key, **PASS_CRITERIA[key]}


def review_obligation(family: str) -> dict[str, Any]:
    """The review a node creates: its ladder and first due day, derived from its check family."""
    key = _family(family)
    ladder = LADDERS[key]
    return {
        "check_family": key,
        "ladder_days": list(ladder),
        "first_due_days": ladder[0],
        "pass_rule": PASS_CRITERIA[key]["rule"],
        "is_heuristic": True,
    }


def checkpoint_supported(kind: str, capabilities: Iterable[str] = BACKEND_CAPABILITIES) -> bool:
    """True only when this backend can honestly write the checkpoint's evidence."""
    requirements = CHECKPOINT_REQUIREMENTS.get(str(kind or ""))
    if requirements is None:
        return False
    return requirements.issubset(set(capabilities))


def drawable_checkpoints(capabilities: Iterable[str] = BACKEND_CAPABILITIES) -> tuple[str, ...]:
    """The checkpoint types a path renderer may draw, in order. Today: gate and delayed."""
    return tuple(kind for kind in ("gate", "delayed", "cumulative")
                 if checkpoint_supported(kind, capabilities))


def plan_checkpoints(*, capabilities: Iterable[str] = BACKEND_CAPABILITIES,
                     cumulative: bool = False) -> list[dict[str, Any]]:
    """The checkpoint plan for one node.

    ``cumulative`` is refused with a typed error while the unit-scoped check contract does not
    exist: a path must not draw a checkpoint the backend cannot record. The refusal names the
    missing capability so the follow-up card has a concrete target.
    """
    capabilities = set(capabilities)
    wanted = ["gate", "delayed"] + (["cumulative"] if cumulative else [])
    planned: list[dict[str, Any]] = []
    for kind in wanted:
        if not checkpoint_supported(kind, capabilities):
            missing = sorted(CHECKPOINT_REQUIREMENTS[kind] - capabilities)
            raise UnsupportedCheckpoint(
                f"checkpoint {kind!r} needs backend capability {missing}; "
                "it cannot be drawn or claimed until that contract exists"
            )
        planned.append({"kind": kind, **CHECKPOINTS[kind]})
    return planned


#: Coarse writer-side markers for a decorated topic heading. This is not a parser and makes no
#: claim about English grammar; it refuses the exact failure mode research §2 names.
TOPIC_ONLY_PREFIXES: tuple[str, ...] = (
    "introduction to ",
    "overview of ",
    "basics of ",
    "all about ",
    "chapter ",
    "unit ",
    "lesson ",
)
TOPIC_ONLY_SUFFIXES: tuple[str, ...] = (
    " vocabulary",
    " grammar",
    " basics",
    " overview",
    " introduction",
)


def exit_performance_problems(text: Any) -> list[str]:
    """Deterministic refusal of a topic label masquerading as an exit performance."""
    value = " ".join(str(text or "").split())
    if not value:
        return ["a node needs an exit performance; an empty title is not a capability"]
    folded = value.casefold()
    for prefix in TOPIC_ONLY_PREFIXES:
        if folded.startswith(prefix):
            return [f"{value!r} is a topic label, not an exit performance the check can elicit"]
    for suffix in TOPIC_ONLY_SUFFIXES:
        if folded.endswith(suffix):
            return [f"{value!r} is a topic label, not an exit performance the check can elicit"]
    return []


def node(
    *,
    unit: Mapping[str, Any],
    objective: Mapping[str, Any],
    check: Mapping[str, Any] | None = None,
    misconceptions: Sequence[str] | None = None,
    capabilities: Iterable[str] = BACKEND_CAPABILITIES,
) -> dict[str, Any]:
    """Project one stored unit+objective onto the five-field node contract.

    ``exit_performance`` is the objective title; the backend has no separate field. The
    prerequisite edge is the unit's declared edge list, not a difficulty rank. The check family is
    the objective's ``evidence_target``; when a check-plan entry is supplied it must name the same
    family. ``misconceptions`` is empty unless an authoring layer supplied it, because no column
    stores one today — the policy focus is always returned so the gap is visible.
    """
    family = _family(objective.get("evidence_target"))
    prereqs = unit.get("prereq_unit_ordinals", unit.get("prereqs", []))
    if isinstance(prereqs, str):
        raise ValueError("prerequisite units must be a list of ordinals, not a JSON string")
    checkpoints = plan_checkpoints(capabilities=capabilities)
    node_value: dict[str, Any] = {
        "ordinal": int(objective.get("ordinal", 0) or 0),
        "title": str(objective.get("title") or ""),
        "exit_performance": str(objective.get("title") or ""),
        "prerequisite_units": [int(value) for value in prereqs or []],
        "check_family": family,
        "misconceptions": [str(item) for item in (misconceptions or []) if str(item).strip()],
        "misconception_focus": MISCONCEPTION_FOCUS[family],
        "review_obligation": review_obligation(family),
        "checkpoints": [item["kind"] for item in checkpoints],
        "capabilities": sorted(set(capabilities)),
    }
    if check is not None:
        node_value["check_family_source"] = str(check.get("evidence_target") or "")
    return node_value


def node_problems(node_value: Mapping[str, Any], *,
                  check: Mapping[str, Any] | None = None) -> list[str]:
    """Deterministic reasons a projected node breaks the contract; empty means it conforms."""
    problems: list[str] = []
    missing = [field for field in NODE_FIELDS if field not in node_value]
    if missing:
        problems.append(f"node is missing field(s) {missing}")
    problems.extend(exit_performance_problems(node_value.get("exit_performance")))
    family = str(node_value.get("check_family") or "")
    if family not in CHECK_FAMILIES:
        problems.append(f"check family {family!r} is not one of {CHECK_FAMILIES}")
    if check is not None:
        declared = str(check.get("evidence_target") or "")
        if declared != family:
            problems.append(
                f"check targets {declared!r} but the node's capability is {family!r}; "
                "the check must measure the node's own family"
            )
    drawable = set(drawable_checkpoints())
    claimed = [str(kind) for kind in node_value.get("checkpoints") or []]
    fake = [kind for kind in claimed if kind not in drawable]
    if fake:
        problems.append(
            f"node claims checkpoint type(s) {fake} that the backend cannot record; "
            "draw only " + ", ".join(sorted(drawable))
        )
    return problems


def review_outcome(*, misses: int, forms: Sequence[str]) -> str:
    """``needs_review`` for one miss; re-teach only for two misses on different check forms.

    The function can never return ``reset``/``locked``: there is no path-level state to write.
    """
    count = max(0, int(misses))
    distinct = {str(form or "").strip().casefold() for form in forms if str(form or "").strip()}
    if count <= 0:
        return "no_change"
    if count == 1:
        return str(FAILURE_RULE["miss_state"])
    if len(distinct) >= int(FAILURE_RULE["reteach_after_misses"]):
        return "reteach"
    return str(FAILURE_RULE["miss_state"])


def review_step(step: int, *, passed: bool, ladder: Sequence[int]) -> int:
    """Advance a rung on a pass, keep the rung on a miss; never reset, never jump to the end."""
    if not ladder:
        return 0
    current = max(0, min(int(step), len(ladder) - 1))
    if not passed:
        # A failed review keeps its place. It does not restart at the first rung ("day 1").
        return current
    return min(current + 1, len(ladder) - 1)


def review_sequence(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Order review items by confusable set after acquisition; never shuffle or random-mix.

    Each item names ``confusable_set`` and ``acquired``. First acquisition is blocked: an
    unacquired item raises instead of being interleaved. Sets are returned in first-appearance
    order with their members adjacent, which is the only interleaving the evidence supports
    (research §5); vocabulary is never mixed by topic or at random.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if not bool(item.get("acquired")):
            raise ValueError(
                "block first acquisition: an item must be individually retrievable before "
                "it is interleaved with a confusable set"
            )
        key = str(item.get("confusable_set") or "").strip()
        if not key:
            raise ValueError(
                "every interleaved item must name a confusable_set; mixing by topic or at "
                "random is not supported interleaving"
            )
        grouped.setdefault(key, []).append(dict(item))
    return [item for key in grouped for item in grouped[key]]


def plan_policy_lines() -> list[str]:
    """Prompt directives for the v2 plan author. Directives, never evidence or a claim."""
    return [
        "Every objective title is an exit performance: name what the learner can do unaided "
        "at the end of the node, not a topic heading. Write the capability, not the chapter.",
        "Each objective's evidence_target is the node's check family. The matching check_plan "
        "entry must name the same evidence_target; a check that measures a different family "
        "measures something other than this node.",
        "Units are ordered by prerequisite dependency: every unit after unit 1 names the "
        "earlier unit(s) it builds on, or is explicitly independent. Do not rank units by "
        "difficulty.",
        "Name the misconception the check must be able to catch. A wrong answer is a "
        "provisional misconception, never a diagnosis.",
        "Every node creates a review obligation from its evidence_target. Do not promise "
        "mastery percentages, XP, streaks, levels or adaptive difficulty: the backend records "
        "evidence states, not a score.",
        "A gate check writes independent_evidence and a delayed cold check writes "
        "delayed_evidence. A cumulative checkpoint may not be drawn or claimed: the backend "
        "has no unit-scoped check.",
    ]
