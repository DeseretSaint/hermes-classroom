"""World-layer fixtures: Japanese L0, head gasket, and the generic-swap probe.

These are *course briefs*, not lessons. They carry only what the prompt builder is allowed to
see (title, subject, end capability, section titles, approved motifs); no check, rubric or
answer key appears here, and the generic-swap fixture exists to prove that a plate which could
serve both courses is rejected.
"""

from __future__ import annotations

JAPANESE_L0_BRIEF: dict = {
    "course_id": "course_ja_l0",
    "title": "Japanese at the cafe",
    "subject_domain": "language",
    "end_capability": "Greet staff, order a drink and thank them at a Tokyo cafe",
    "audience": "adult learner",
    "level": "L0",
    "locale": "en-US",
    "tone": "warm, everyday, unhurried",
    "safety_class": "none",
    "motifs": ["lantern district", "cafe counter", "vending machine", "train platform"],
    "forbidden": ["brand logos", "text"],
    "sections": [
        {"id": "s1", "title": "Before-meal greetings"},
        {"id": "s2", "title": "Ordering a drink"},
        {"id": "s3", "title": "After-meal thanks"},
    ],
}

HEAD_GASKET_BRIEF: dict = {
    "course_id": "course_head_gasket",
    "title": "Replace a head gasket",
    "subject_domain": "technical_procedure",
    "end_capability": "Replace a head gasket on a four-cylinder engine",
    "audience": "adult learner",
    "level": "novice",
    "locale": "en-US",
    "tone": "practical, calm, competent",
    "safety_class": "workshop",
    "motifs": [
        "service bay",
        "car on a lift",
        "tool wall",
        "head gasket",
        "torque wrench",
        "component trays",
    ],
    "forbidden": ["brand logos", "text"],
    "sections": [
        {"id": "s1", "title": "Before you lift the car"},
        {"id": "s2", "title": "Removing the head"},
    ],
}

#: The same visual direction as the Japanese course with the subject swapped for an unrelated
#: field. If art built for one still "passes" for the other, the world is generic and rejected.
GENERIC_SWAP_BRIEF: dict = {
    **JAPANESE_L0_BRIEF,
    "course_id": "course_generic_swap",
    "title": "Cooking at the counter",
    "subject_domain": "cooking",
    "end_capability": "Cook a simple meal at home",
    "motifs": ["lantern district", "cafe counter", "vending machine", "train platform"],
    "sections": [
        {"id": "s1", "title": "Before you cook"},
        {"id": "s2", "title": "Making the meal"},
    ],
}
