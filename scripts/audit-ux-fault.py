"""Write the audit fault file from a JSON argument (used by ad-hoc probes)."""
import json
import pathlib
import sys

path = pathlib.Path("audit/ux/fault.json")
path.write_text(json.dumps(json.loads(sys.argv[1]), indent=2) + "\n")
print(path.read_text())
