import json, pathlib, re

ROOT = pathlib.Path('.')
OLD_FULL = "035597017a19b77cae14f65eb37fd90c6868ba6f94dd0fc5d6977dd8d6b97b5d"
NEW_FULL = "9735300e197a0c6a1fb85ba7f15ec40b156283394a795399b9b9e2ba49f25547"
FILES = ["README.md", "docs/SUBMISSION.md", "docs/RELEASE-EVIDENCE.md",
         "docs/M4-VISUAL-MEDIA-AUDIT.md", "docs/HARNESS-STATUS.md", "docs/INSTALL.md"]

for name in FILES:
    p = ROOT / name
    s = p.read_text()
    before = s
    s = s.replace(OLD_FULL, NEW_FULL)
    s = s.replace("0355970\u2026c5d6977dd8d6b97b5d", "9735300e\u2026b9e2ba49f25547")
    s = s.replace("0355970\u2026", "9735300e\u2026")
    s = re.sub(r"\b1968\b", "1984", s)
    s = s.replace("328.553s", "310.621s")
    if s != before:
        p.write_text(s)
        print("updated", name)

ev = json.loads((ROOT / "docs/release-evidence.json").read_text())
ev["measured_commit"] = "39659b7609375d791f3f251d3d0fb0041864d0a9"
ev["measured_commit_short"] = "39659b7"
ev["merge_commit"] = "39659b7609375d791f3f251d3d0fb0041864d0a9"
ev["tests"]["ran"] = 1984
ev["plugin"]["sha256"] = NEW_FULL
ev["m4"]["text_nodes"] = 2282
ev["m4_repro"]["plugin_sha256"] = NEW_FULL
pins = [p for p in ev["historical_plugin_pins"] if p["sha256"] != OLD_FULL]
pins.insert(0, {"sha256": OLD_FULL, "commit": "c6b658e", "path": "desktop/plugin.js"})
ev["historical_plugin_pins"] = pins
(ROOT / "docs/release-evidence.json").write_text(json.dumps(ev, indent=2) + "\n")
print("evidence updated")
