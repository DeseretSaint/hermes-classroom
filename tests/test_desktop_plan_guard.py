"""The Plan view must not offer an action the backend is guaranteed to refuse.

`plan.replan` carries the authored plan document (`gen_plan_documents`) onto a content-preserving
new version, so a replanned plan is authorable and `Generate lessons` is the correct offer there.
What the document cannot cover is a structural add: an objective added through the editor has no
authored section, and a lessons job for that version fails with a typed message
(`plan … has no authored document` or `outline covers objectives [… ] … Re-author the plan`).

No wire field declares authorship, so the studio reads the refusal the job itself returns instead of
guessing from a job checkpoint (a checkpoint inference would wrongly hide the action after a carried
replan). These are source-level assertions: the module is one uncompiled file, so the wiring is
checked where it is written.
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
    def test_authorship_is_not_inferred_from_a_job_checkpoint(self) -> None:
        """A carried replan has no authoring job for its version; a checkpoint guess would lie."""
        source = _source()
        self.assertNotIn("latestPlanJob.checkpoint", source)
        self.assertNotIn("lacksAuthoredDocument", source)

    def test_the_guard_reads_the_typed_lessons_refusal(self) -> None:
        source = _source()
        self.assertIn("lessonDocumentGap", source)
        # Only a lessons job, only a failure, only the two document/coverage messages.
        self.assertRegex(source, r"job\.brief\.stage === 'lessons'")
        self.assertRegex(source, r"no authored document\|outline covers objectives")

    def test_generate_lessons_is_withheld_on_the_proven_gap(self) -> None:
        source = _source()
        guarded = re.search(
            r"!isDraft && !editing && !lessonDocumentGap\s*\?\s*jsx\(sdk\.Button,\s*\{[^}]*onClick: generateLessons",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(guarded, "Generate lessons is not gated on lessonDocumentGap")

    def test_the_withheld_state_is_visible_and_truthful(self) -> None:
        source = _source()
        self.assertIn("'data-cb-plan-document': 'missing'", source)
        self.assertIn("withheld rather than offered as a second failure", source)
        # No invented recovery: the note must not promise an authoring action the UI cannot perform.
        self.assertNotIn("Author this plan version", source)

    def test_a_new_plan_version_clears_the_gap(self) -> None:
        source = _source()
        self.assertRegex(source, r"setLessonDocumentGap\(null\), \[planIdOnScreen\]")


if __name__ == "__main__":
    unittest.main()
