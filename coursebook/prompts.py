"""Frozen prompt directives shared by the lesson author and the teaching chat.

`docs/ASSESSMENT-BREADTH.md` §7.4 freezes one rule for 0.1.0: the product has no execution,
recording or image-inspection capability, so no prompt may let prose claim one. The rule is
prompt text, not check JSON — it never enters `checks.reference_json`, the contract or the
database schema.

Keeping it in one constant means the lesson author (which writes the learner page) and the
continuation prompt (which drives the teaching chat after a committed verdict) cannot drift into
two slightly different promises of the same non-existent capability.
"""

from __future__ import annotations

#: `docs/ASSESSMENT-BREADTH.md` §7.4, verbatim. A hard rule, not guidance.
CHAT_CAPABILITY_RULE = (
    "Never claim that Coursebook ran code, heard a recording, or inspected a photo. You may "
    "discuss code, describe how to test it, and ask the learner to explain their result. "
    "Coursebook's check verdicts come only from the check surface."
)

__all__ = ["CHAT_CAPABILITY_RULE"]
