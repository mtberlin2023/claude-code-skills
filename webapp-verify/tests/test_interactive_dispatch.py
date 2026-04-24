"""
8-shape fixture for the interactive-tool uid-substitution layer
(Anya #608, 2026-04-23).

chrome-devtools-mcp's click / fill / fill_form / type_text tools require
`uid` arguments pulled from the accessibility-tree snapshot — not CSS
selectors. `_apply_selector_resolution` rewrites each step so the flow-
script author can write role+name selectors; the runner converts them
to uids before dispatch. Raw-uid steps skip the resolver; non-interactive
tools pass through untouched.

Grouped into one TestCase class:

  TestApplySelectorResolution — per-tool substitution + error paths (8)

From the skill root:
    python3 -m unittest tests.test_interactive_dispatch -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify import (  # noqa: E402
    FlowRefusedError,
    _apply_selector_resolution,
)


_SNAPSHOT = (
    'uid=1_0 RootWebArea "Test" url="https://example.com/"\n'
    'uid=1_4 button "Submit"\n'
    'uid=1_6 textbox "Email"\n'
    'uid=1_7 textbox "Password"\n'
)


class TestApplySelectorResolution(unittest.TestCase):
    """uid-substitution gate between flow-script authoring and MCP dispatch."""

    def test_01_click_with_raw_uid_passthrough(self):
        # Raw uid skips the resolver — honours the disambiguation escape
        # hatch when role+name collide.
        step = {"tool": "click", "uid": "1_4"}
        resolved = _apply_selector_resolution(step, _SNAPSHOT)
        self.assertEqual(resolved, step)

    def test_02_click_with_selector_resolves_to_uid(self):
        step = {"tool": "click", "selector": {"role": "button", "name": "Submit"}}
        resolved = _apply_selector_resolution(step, _SNAPSHOT)
        self.assertEqual(resolved["tool"], "click")
        self.assertEqual(resolved["uid"], "1_4")
        # Original selector key retained — caller strips at MCP dispatch.
        self.assertEqual(resolved["selector"], {"role": "button", "name": "Submit"})

    def test_03_click_missing_both_uid_and_selector_raises(self):
        with self.assertRaises(FlowRefusedError) as cm:
            _apply_selector_resolution({"tool": "click"}, _SNAPSHOT)
        self.assertIn("missing both", str(cm.exception))

    def test_04_fill_with_selector_resolves(self):
        step = {
            "tool": "fill",
            "selector": {"role": "textbox", "name": "Email"},
            "value": "a@b.co",
        }
        resolved = _apply_selector_resolution(step, _SNAPSHOT)
        self.assertEqual(resolved["uid"], "1_6")
        self.assertEqual(resolved["value"], "a@b.co")

    def test_05_fill_form_mixed_uid_and_selector_elements(self):
        step = {
            "tool": "fill_form",
            "elements": [
                {"uid": "1_7", "value": "secret"},
                {"selector": {"role": "textbox", "name": "Email"}, "value": "a@b.co"},
            ],
        }
        resolved = _apply_selector_resolution(step, _SNAPSHOT)
        self.assertEqual(
            resolved["elements"],
            [
                {"uid": "1_7", "value": "secret"},
                {"uid": "1_6", "value": "a@b.co"},
            ],
        )

    def test_06_fill_form_non_dict_element_raises(self):
        step = {"tool": "fill_form", "elements": ["not-a-dict"]}
        with self.assertRaises(FlowRefusedError) as cm:
            _apply_selector_resolution(step, _SNAPSHOT)
        self.assertIn("must be a dict", str(cm.exception))

    def test_07_fill_form_element_missing_both_keys_raises(self):
        step = {"tool": "fill_form", "elements": [{"value": "orphan"}]}
        with self.assertRaises(FlowRefusedError) as cm:
            _apply_selector_resolution(step, _SNAPSHOT)
        self.assertIn("missing both", str(cm.exception))

    def test_08_non_interactive_tool_untouched(self):
        # take_snapshot / navigate_page / type_text are NOT in the
        # uid-needing set — resolver is a no-op for them.
        step = {"tool": "navigate_page", "url": "https://example.com/"}
        resolved = _apply_selector_resolution(step, _SNAPSHOT)
        self.assertIs(resolved, step)


if __name__ == "__main__":
    unittest.main()
