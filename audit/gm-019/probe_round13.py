"""Round-13 (GM-019) predicate probe: non-frozen imperative and passive shapes are refused.

The imperative shape is scoped to the procedure grammar (``workshop_manual``), matching the
card's predicate-level repro; the passive shape is refused for every grammar. The grammar-owned
scene carve-outs and native place cues stay legal. Run from the repo root:

    PYTHONPATH=. python3 audit/gm-019/probe_round13.py
"""

from coursebook import world

REFUSED_IMPERATIVE = (
    "Scrub the head",
    "Swap the gasket",
    "Scrape the block",
    "Degrease the block",
    "Rebuild the head",
    "Then scrub the head",
    "Probably scrub the head",
    "Scrub his hands",
    "Scrubbing the head",
)

REFUSED_PASSIVE = (
    "The head is removed",
    "The intake manifold was drained",
    "The block has been degreased",
    "The head was removed carefully",
    "The head is now removed",
    "The block was just degreased",
)

LEGAL = {
    "workshop_manual": (
        "clean service bay",
        "a clean service bay",
        "car on a lift",
        "four-cylinder block",
        "engine block cutaway",
        "the break room",
        "bench under the lamp",
    ),
    "field_atlas": ("clean cafe counter", "Ordering a drink"),
    "kitchen_table": ("recipe card stand", "work surface", "Cook a simple meal at home"),
}

status = 0
for case in REFUSED_IMPERATIVE:
    found = world._plate_text_problems(case, "workshop_manual")
    ok = "presentation_names_procedure_or_value" in found
    status |= 0 if ok else 1
    print(("PASS" if ok else "FAIL"), "refused", "workshop_manual", repr(case), found)

for case in REFUSED_PASSIVE:
    for grammar in world.GRAMMARS:
        found = world._plate_text_problems(case, grammar)
        ok = "presentation_names_procedure_or_value" in found
        status |= 0 if ok else 1
        print(("PASS" if ok else "FAIL"), "refused", grammar, repr(case), found)

for grammar, cases in LEGAL.items():
    for case in cases:
        found = world._plate_text_problems(case, grammar)
        ok = "presentation_names_procedure_or_value" not in found
        status |= 0 if ok else 1
        print(("PASS" if ok else "FAIL"), "legal  ", grammar, repr(case), found)

print("probe", "OK" if status == 0 else "FAILED")
raise SystemExit(status)
