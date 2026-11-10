"""GM-019 false-positive sweep: authored grammar vocabulary and native scenes stay legal.

Every authored motif and subject cue of every grammar, plus the Japanese L0 field-atlas brief and
the cooking generic-swap brief (title, capability, section titles), must not be refused as a
procedure by the GM-019 shape fence. Run from the repo root:

    PYTHONPATH=. python3 audit/gm-019/probe_falsepositives.py

One value is expected to fail, and it fails identically at the GM-003 base commit `7ff9f4a`:
the authored ``studio_bench`` motif ``cutting mat`` is refused by the *pre-existing* frozen
gerund rule (``cutting`` -> ``cut``). GM-019 does not introduce or widen that over-refusal; it is
recorded in ``audit/gm-019/README.md`` as a residual.
"""

from coursebook import world
from tests.world_fixtures import GENERIC_SWAP_BRIEF, JAPANESE_L0_BRIEF

#: Refused at `7ff9f4a` too — the frozen gerund rule, not the GM-019 shape fence.
PRE_EXISTING_FROZEN_OVER_REFUSAL = {"cutting mat"}

status = 0
cases: list[tuple[str, str]] = []
for grammar, record in world.GRAMMARS.items():
    for item in (*record.motifs, *record.subject_cues):
        cases.append((grammar, item))
for grammar, brief in (
    ("field_atlas", JAPANESE_L0_BRIEF),
    ("kitchen_table", GENERIC_SWAP_BRIEF),
):
    for field in ("title", "end_capability", "audience"):
        if brief.get(field):
            cases.append((grammar, str(brief[field])))
    for section in brief.get("sections", ()):
        cases.append((grammar, str(section["title"])))

for grammar, value in cases:
    found = world._plate_text_problems(value, grammar)
    refused = "presentation_names_procedure_or_value" in found
    expected_refused = value in PRE_EXISTING_FROZEN_OVER_REFUSAL
    ok = refused == expected_refused
    status |= 0 if ok else 1
    label = "PASS" if ok else "FAIL"
    note = " (pre-existing frozen gerund; recorded residual)" if expected_refused else ""
    print(label, grammar, repr(value), found, note)

print(f"swept {len(cases)} authored values")
print("probe", "OK" if status == 0 else "FAILED")
raise SystemExit(status)
