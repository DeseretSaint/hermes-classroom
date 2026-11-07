import json
from pathlib import Path

OUT = Path("audit/adversarial/generic-harness-v2/evidence")
for name in ("single", "short", "full"):
    d = json.loads((OUT / f"{name}.json").read_text())
    obs = d["observations"]
    print(f"== {name} ==")
    for key in ("schema_name", "prompt_version", "plan_scope", "validation_verdict",
                "plan_state_before_approval", "plan_state_after_approval", "units",
                "objectives", "checks", "lessons", "sections", "outline_units"):
        print(f"  {key}: {obs[key]}")
    print("  outline_unit_states:", json.dumps(obs["outline_unit_states"]))
    print("  chained unit stages:", [u["chained_a_job"] for u in d["steps"]["unit_stages"]])
    print("  chained lesson stages:", [u["chained_a_job"] for u in d["steps"]["lesson_stages"]])
    print("  approve wrong hash:", json.dumps(d["steps"]["approve_wrong_hash"]))
    print("  approve provenance:", d["steps"]["approve"].get("approval_provenance"))
    print("  request rules:", json.dumps(d["steps"]["plan_job"]["request"]))
    print("  attempts:", json.dumps(obs["attempt_rows"]))
    print("  lane kinds:", sorted({r["reference_kind"] for r in obs["check_lanes"]}))
    print("  unit prereqs:", [(u["ordinal"], u["prereq_unit_ordinals_json"]) for u in obs["unit_rows"]])
