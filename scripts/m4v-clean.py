"""Remove stale M4-V audit output before a clean regeneration (audit dir only)."""
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent.parent / "audit" / "visual" / "m4-visual"
if OUT.is_dir():
    for png in OUT.glob("*.png"):
        png.unlink()
    chromium = OUT / ".chromium"
    if chromium.is_dir():
        shutil.rmtree(chromium, ignore_errors=True)
print("cleaned", OUT)
