"""Round-12 predicate probe for the N1 bare-object fence (maker worktree only).

Every determiner-only scene verb is refused verb-initial with a bare object, while the
grammar-owned scene carve-out and the descriptive number compound stay legal.
"""

from coursebook import world

REFUSED = (
    "Clean head",
    "Refill coolant",
    "Polish lens",
    "Break seal",
    "Then clean head",
    "Clean the head",
)

LEGAL = {
    "workshop_manual": ("clean service bay", "car on a lift", "four-cylinder block"),
    "field_atlas": ("clean cafe counter", "pocket map"),
}

status = 0
for case in REFUSED:
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
