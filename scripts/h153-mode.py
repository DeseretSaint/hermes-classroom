"""Switch the isolated rig's machine UI preference store between light and dark.

The Desktop watches this file (`electron/ui-preferences.ts`, 1500 ms) and applies the change to
every window on that home, so this is the app's own appearance setting, not a CSS override.
"""
import json
import os
import sys
from pathlib import Path

mode = sys.argv[1] if len(sys.argv) > 1 else "light"
assert mode in ("light", "dark"), mode
path = Path(os.environ.get("HERMES_HOME", "")) / "ui-preferences.json"
if not path.parent.is_dir():
    raise SystemExit(f"no home at {path.parent}")
store = json.loads(path.read_text(encoding="utf-8"))
store.setdefault("values", {})["hermes-desktop-mode-v1"] = mode
store["revision"] = int(store.get("revision", 0)) + 1
path.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
print(f"{path} mode={mode} revision={store['revision']}")
