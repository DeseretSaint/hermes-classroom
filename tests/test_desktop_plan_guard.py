"""The Plan view must not offer an action the backend is guaranteed to refuse.

`plan.replan` writes outline rows for the new version but not the authored plan document
(`gen_plan_documents`, written only by the plan-authoring job). A lessons job for such a version
fails `INTERNAL_ERROR: plan … has no authored document`. The Desktop cannot read the document row
directly, so it derives authorship from the latest plan-kind job's checkpoint and withholds the
lessons action on a proven mismatch. These are source-level assertions: the module is one
uncompiled file, so the wiring is checked where it is written.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "desktop" / "plugin.js"


def _source() -> str:
    return PLUGIN.read_text(encoding="utf-8")


class PlanDocumentGuardTest(unittest.TestCase):
    def test_authorship_is_read_from_the_plan_job_checkpoint(self) -> None:
        source = _source()
        self.assertIn("studio-plan-job-", source)
        self.assertRegex(source, r"'jobs\.get'\s*,\s*\{\s*job_id: planJobId\s*\}")
        # The checkpoint, not a guess: only a completed authoring job names an authored plan_id.
        self.assertIn("latestPlanJob.checkpoint", source)
        self.assertIn("authoredPlanId !== plan.plan_id", source)

    def test_generate_lessons_is_withheld_on_a_proven_mismatch(self) -> None:
        source = _source()
        guarded = re.search(
            r"!isDraft && !editing && !lacksAuthoredDocument\s*\?\s*jsx\(sdk\.Button,\s*\{[^}]*onClick: generateLessons",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(guarded, "Generate lessons is not gated on lacksAuthoredDocument")

    def test_the_withheld_state_is_visible_and_truthful(self) -> None:
        source = _source()
        self.assertIn("'data-cb-plan-document': 'missing'", source)
        self.assertIn("not carried forward", source)
        # No invented recovery: the note must not promise an authoring action the UI cannot perform.
        self.assertNotIn("Author this plan version", source)


if __name__ == "__main__":
    unittest.main()
