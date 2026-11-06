"""Live probes must send the same fences the studio sends.

The acceptance packet leans on ``scripts/cb011-parent-probe.py`` to prove final approval and
export, so a probe that omits ``expected_revision`` on ``parent.final.approve`` can only ever
prove the contract refusal. These are source-level guards: they keep the probe honest without
starting a backend.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "scripts" / "cb011-parent-probe.py"
DESKTOP = ROOT / "desktop" / "plugin.js"


def function_source(path: Path, name: str) -> str:
    """The text of one Python function, found by its def line and read to the next top-level def."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(f"def {name}("))
    body: list[str] = []
    for line in lines[start:]:
        if body and line and not line[0].isspace() and not line.startswith(")"):
            break
        body.append(line)
    return "\n".join(body)


class ParentProbeFenceTest(unittest.TestCase):
    def test_final_approval_fences_on_the_read_revision(self) -> None:
        source = function_source(PROBE, "phase_approve_and_export")
        self.assertIn("current_revision(", source, "the probe must read the course revision")
        self.assertIn("expected_revision=revision", source, "parent.final.approve is revision-fenced")
        self.assertNotIn("revision = None", source)
        self.assertNotRegex(
            source,
            r"\"parent\.final\.approve\",\s*payload,\s*idempotency_key=",
            "the final approval call must not drop expected_revision",
        )

    def test_current_revision_comes_from_the_parent_listing(self) -> None:
        # course.outline is deliberately revision 0, so the enrollment revision has to be read
        # from library.list: the same field the studio's parent-course rows fence on.
        source = function_source(PROBE, "current_revision")
        self.assertIn("library.list", source)
        self.assertIn("item.get(\"revision\")", source)
        self.assertIn("enrollment_id", source)


class DesktopFinalApprovalFenceTest(unittest.TestCase):
    def test_renderer_sends_expected_revision_with_final_approval(self) -> None:
        source = DESKTOP.read_text(encoding="utf-8")
        anchor = source.index("'parent.final.approve'")
        window = source[anchor : anchor + 1200]
        self.assertIn("expectedRevision", window, "the studio must fence parent.final.approve")
        self.assertIn("staleRevision(response)", window, "a stale fence must refresh the revision")

    def test_export_panel_receives_the_revision(self) -> None:
        source = DESKTOP.read_text(encoding="utf-8")
        anchor = source.index("jsx(StudioExportPanel, {")
        window = source[anchor : anchor + 400]
        self.assertIn("revision", window)
        self.assertIn("onRevision", window)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
