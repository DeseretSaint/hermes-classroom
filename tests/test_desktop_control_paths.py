"""H-64: no dead controls — route/section handler paths and the create-flow state.

Three checks, all against the shipped module rather than a fixture:

1. **Every rendered button/link has a handler path.** Every ``jsx(sdk.Button, …)``,
   ``jsx('button', …)`` and ``jsx('a', …)`` object in ``desktop/plugin.js`` must carry
   ``onClick``/``href``, be an ``asChild`` trigger (the trigger owns the behaviour), or be
   explicitly ``disabled``. This is the source-level half of the live inventory in
   ``scripts/h64-controls.mjs``: the live walk proves what each control *does*, this proves a new
   control cannot land without a path at all.

2. **A fresh lesson run never opens a blank chat.** ``beginLessonFor`` must arm the exact run and
   return; it must not call ``startLessonChat``. ``host.newChat`` swaps the route to ``#/`` by SDK
   design, which is exactly the dead end H-64 fixes.

3. **The scope step is a real choice.** ``CreateCourseFlow`` step 1 renders the whole option card
   as one ``role="option"`` control with a visible selected state, and its Continue button is
   disabled — with a described reason — until a scope is chosen.

What this does NOT prove: that the live Desktop window renders those nodes. That is
``scripts/h64-controls.mjs``'s job (``audit/h64/inventory.json``), which runs against CDP 9337.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

BUTTON_PATTERN = re.compile(r"jsxs?\(\s*(sdk\.Button|'button'|\"button\"|'a'|\"a\")\s*,\s*\{")
HANDLER_KEYS = ("onClick", "href", "asChild", "type: 'submit'", 'type: "submit"', "formAction")
DISABLED_KEYS = ("disabled",)

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { CreateCourseFlow } from './plugin.js'

const html = renderToStaticMarkup(
  React.createElement(CreateCourseFlow, { onCancel: () => {}, onCreated: () => {} })
)
process.stdout.write(html)
"""


def _object_at(source: str, brace: int) -> tuple[str, int]:
    """Return the balanced ``{...}`` object that starts at ``brace`` and its end index.

    Strings, template literals and comments are skipped so a brace inside copy never moves the
    depth counter. Template literals are skipped whole: their interpolations cannot contain an
    unbalanced brace that would escape.
    """
    depth = 0
    index = brace
    quote = None
    while index < len(source):
        char = source[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
            index += 1
            continue
        if char == "/" and index + 1 < len(source):
            nxt = source[index + 1]
            if nxt == "/":
                end = source.find("\n", index)
                index = len(source) if end == -1 else end + 1
                continue
            if nxt == "*":
                end = source.find("*/", index + 2)
                index = len(source) if end == -1 else end + 2
                continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[brace:index + 1], index + 1
        index += 1
    raise AssertionError("unbalanced object literal in desktop/plugin.js")


def _handlers(source: str | None = None) -> list[dict]:
    source = source if source is not None else PLUGIN_JS.read_text(encoding="utf-8")
    found = []
    for match in BUTTON_PATTERN.finditer(source):
        brace = match.end() - 1
        body, _ = _object_at(source, brace)
        line = source[: match.start()].count("\n") + 1
        found.append({"line": line, "tag": match.group(1), "body": body})
    return found


def _function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    if start == -1:
        raise AssertionError(f"missing {signature!r} in desktop/plugin.js")
    if signature.lstrip().startswith(("function", "async function")):
        # A declared function: its parameter list is the first balanced group after the name.
        paren = source.find("(", start)
        depth = 0
        index = paren
        while index < len(source):
            if source[index] == "(":
                depth += 1
            elif source[index] == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        scan_from = index + 1
    else:
        # A callback: the signature ends at the callee's `(`; the callback's own head follows.
        scan_from = start + len(signature)
    # The body brace is the first `{` at paren depth 0: a destructured or arrow parameter list
    # sits inside parentheses, so its braces do not count.
    depth = 0
    index = scan_from
    quote = None
    while index < len(source):
        char = source[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "{" and depth == 0:
            body, _ = _object_at(source, index)
            return body
        index += 1
    raise AssertionError(f"no body brace after {signature!r}")


def _trigger_owned(source: str, match_start: int) -> bool:
    """A Button rendered as a trigger child is driven by the trigger, not by its own props."""
    window = source[max(0, match_start - 600):match_start]
    return bool(
        re.search(
            r"(DropdownMenuTrigger|TooltipTrigger|DialogTrigger|PopoverTrigger)[\s\S]{0,240}?asChild\s*:\s*true",
            window,
        )
    )


class ControlHandlerPathTest(unittest.TestCase):
    """No rendered control may exist without a path: the static half of the live inventory."""

    def test_every_button_has_a_handler_or_is_disabled(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        missing = [
            row for row in _handlers(source)
            if not any(key in row["body"] for key in HANDLER_KEYS + DISABLED_KEYS)
            and not _trigger_owned(source, source.find(row["body"]))
        ]
        self.assertEqual(
            [],
            [(row["line"], row["tag"], row["body"][:160]) for row in missing],
            "visible enabled controls with no handler path",
        )

    def test_as_child_buttons_name_the_trigger_or_link_that_owns_them(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        for row in _handlers(source):
            if "asChild" not in row["body"]:
                continue
            self.assertTrue(
                "href:" in row["body"] or _trigger_owned(source, source.find(row["body"])),
                f"asChild button at line {row['line']} has neither a trigger nor a link child",
            )

    def test_the_scan_actually_sees_the_shell(self) -> None:
        # A scanner that silently matches nothing would pass every assertion above.
        rows = _handlers()
        self.assertGreater(len(rows), 150, "the Button scan stopped matching the module")
        onclicks = sum(1 for row in rows if "onClick" in row["body"])
        self.assertGreater(onclicks, 120)


class LessonStartHasAVisibleResultTest(unittest.TestCase):
    """A fresh run arms the exact chat and keeps the page; it never calls `host.newChat`."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_begin_lesson_arms_the_run_and_does_not_open_a_chat(self) -> None:
        body = _function_body(self.source, "async function beginLessonFor(")
        self.assertIn("armPendingBind(", body)
        self.assertNotIn("startLessonChat(", body)
        self.assertIn("armed: true", body)
        self.assertIn("objectiveTitle", body)

    def test_begin_lesson_never_reaches_new_chat(self) -> None:
        # The exact seam that broke H-64 is `host.newChat`: it swaps the route to `#/`. Assert on
        # the seam itself, not only on the helper that wraps it, so a future inline call fails.
        body = _function_body(self.source, "async function beginLessonFor(")
        self.assertNotIn("host.newChat(", body)
        self.assertNotIn("newChat(", body)
        # And the helper is not quietly re-exported into this path under another name.
        self.assertNotIn("revealCoursebookPane(", body)

    def test_the_armed_bind_carries_the_returned_lesson_run_id(self) -> None:
        body = _function_body(self.source, "async function beginLessonFor(")
        armed = re.search(r"armPendingBind\(\{([\s\S]*?)\n  \}\)", body)
        if armed is None:
            self.fail("beginLessonFor no longer arms a bind")
        self.assertIn("lessonRunId: outcome.lesson_run_id", armed.group(1))
        # The returned contract names the same run so each surface can show what it armed.
        self.assertEqual(body.count("lessonRunId: outcome.lesson_run_id"), 2)
        self.assertIn("lessonRunId: outcome.lesson_run_id,", body)
        # pendingBindFor only returns a bind that carries a run id: no armed state without one.
        bind = _function_body(self.source, "function armPendingBind(")
        self.assertIn("lessonRunId,", bind)
        self.assertIn("if (!enrollmentId || !objectiveId || !lessonRunId)", bind)

    def test_course_detail_start_opens_the_section(self) -> None:
        body = _function_body(self.source, "const startLesson = useCallback(")
        self.assertIn("openSection(target)", body)
        self.assertIn("outcome.armed", body)

    def test_section_view_start_uses_the_shared_begin(self) -> None:
        body = _function_body(self.source, "const begin = useCallback(")
        self.assertIn("beginLessonFor(", body)
        # The only place this component may open a chat is the explicit notice action the learner
        # clicks; the run itself never navigates away.
        self.assertEqual(body.count("startLessonChat("), 1)
        self.assertIn("run: () => startLessonChat(", body)

    def test_the_pane_names_an_armed_run_instead_of_a_blank_draft(self) -> None:
        body = _function_body(self.source, "function CoursebookPane(")
        self.assertIn("pendingBindFor(scopeProfile)", body)
        self.assertIn("Lesson run ready", body)


class CreateFlowScopeChoiceTest(unittest.TestCase):
    """Step 1 is one full-card option per scope, with a disabled, described Continue."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-controls-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(
            SDK_STUB.replace(
                "onClick: props.onClick",
                "'aria-describedby': props['aria-describedby'] || null,\n    onClick: props.onClick",
            ),
            encoding="utf-8",
        )
        cls.root = root
        result = subprocess.run(
            ["node", str(root / "harness.mjs")],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-2000:])
        cls.html = result.stdout

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_each_scope_is_one_option_card(self) -> None:
        for scope_id in ("single", "short", "full"):
            self.assertIn(f'data-cb-scope-option="{scope_id}"', self.html)
        self.assertEqual(self.html.count('role="option"'), 3)
        self.assertEqual(self.html.count('aria-selected="false"'), 3)

    def test_the_whole_card_carries_the_label_and_the_consequence(self) -> None:
        cards = re.findall(r'<button[^>]*role="option"[^>]*>(.*?)</button>', self.html, re.S)
        self.assertEqual(len(cards), 3, self.html[:800])
        expected = {
            "single": ("A single lesson", "task in front of you today"),
            "short": ("A short course (a few sessions)", "build on each other"),
            "full": ("A full course (weeks or months)", "split into units")
        }
        for scope_id, (label, consequence) in expected.items():
            match = re.search(
                rf'data-cb-scope-option="{scope_id}"[^>]*>(.*?)</button>', self.html, re.S
            )
            self.assertIsNotNone(match, scope_id)
            card = match.group(1)
            self.assertIn(label, card)
            self.assertIn(consequence, card)
            self.assertIn("Choose", card)

    def test_continue_is_disabled_with_a_described_reason(self) -> None:
        self.assertIn('aria-describedby="cb-scope-time"', self.html)
        self.assertRegex(self.html, r'<button[^>]*disabled[^>]*>Continue</button>')
        self.assertIn("Choose one option above to continue", self.html)

    def test_the_selected_state_is_words_not_only_colour(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("'aria-selected': selected", source)
        self.assertIn("children: selected ? 'Selected' : 'Choose'", source)


if __name__ == "__main__":
    unittest.main()
