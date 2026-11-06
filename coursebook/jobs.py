"""Job-state machine, read from ``cb.jobs``.

The transitions map and state list are contract data, not code constants: the backend implements
this module instead of inventing its own state names. ``PREBUILD_SPEC.md`` §12 and ``AUDIT.md``
H2/H3 are the reasons the states are this specific — cancelling a job is not the same as knowing
the in-flight provider call stopped.
"""

from __future__ import annotations

from typing import Any

from .contracts import ContractError, contract

CONTRACT_ID = "cb.jobs"


def states() -> tuple[str, ...]:
    return tuple(contract(CONTRACT_ID)["states"])


def terminal_states() -> frozenset[str]:
    return frozenset(contract(CONTRACT_ID)["terminal_states"])


def transitions() -> dict[str, list[str]]:
    return {state: list(targets) for state, targets in contract(CONTRACT_ID)["transitions"].items()}


def allowed_targets(state: str) -> tuple[str, ...]:
    table = transitions()
    if state not in table:
        raise ContractError(f"unknown job state {state!r}", contract_id=CONTRACT_ID)
    return tuple(table[state])


def can_transition(current: str, target: str) -> bool:
    try:
        return target in allowed_targets(current)
    except ContractError:
        return False


def assert_transition(current: str, target: str) -> None:
    """Raise ``JOB_STATE_INVALID``-worthy failure when a worker tries an illegal move."""
    from .api import RpcError

    if current not in states():
        raise RpcError.of("JOB_STATE_INVALID", f"unknown job state {current!r}")
    if target not in states():
        raise RpcError.of("JOB_STATE_INVALID", f"unknown job state {target!r}")
    if not can_transition(current, target):
        raise RpcError.of("JOB_STATE_INVALID", f"job cannot move from {current} to {target}")


def is_terminal(state: str) -> bool:
    return state in terminal_states()


def cancellable(state: str) -> bool:
    """Whether a *new* cancel request is meaningful right now.

    ``cancelling`` answers False on purpose: cancellation is already in progress, so offering it
    again would be a control that does nothing.
    """
    try:
        targets = allowed_targets(state)
    except ContractError:
        return False
    # `queued` cancels directly; anything already running needs a cancel *request*. A job that is
    # already `cancel_requested`/`cancelling` must not offer the action a second time.
    return state == "queued" or "cancel_requested" in targets


def job_schema() -> dict[str, Any]:
    return contract(CONTRACT_ID)["job"]
