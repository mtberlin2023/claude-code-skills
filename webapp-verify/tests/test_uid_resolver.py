"""
15-shape fixture for the uid-resolver surface (Anya #608, 2026-04-23).

Covers the role+name→uid resolver that backs the interactive dispatchers
(click / fill / fill_form) plus the URL-from-snapshot extractor that lets
the url_pattern matcher see POST→302 server-side redirects.

Grouped into three TestCase classes:

  TestCurrentUrlFromSnapshot — RootWebArea regex surface (5 shapes)
  TestSnapshotToText         — text concatenation across shapes (2 shapes)
  TestResolveSelectorToUid   — role+name resolver + ambiguity guards (8)

From the skill root:
    python3 -m unittest tests.test_uid_resolver -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify import (  # noqa: E402
    FlowRefusedError,
    _current_url_from_snapshot,
    _resolve_selector_to_uid,
    _snapshot_to_text,
)


class _FakeContentItem:
    """Duck-typed mcp content item — text attribute only."""
    def __init__(self, text):
        self.text = text


class _FakeSnapshotResult:
    """Duck-typed CallToolResult with a content list."""
    def __init__(self, content):
        self.content = content


class TestCurrentUrlFromSnapshot(unittest.TestCase):
    """RootWebArea line carries the live URL; redirects become visible here."""

    def test_01_root_webarea_url_extracted(self):
        snap = (
            'uid=1_0 RootWebArea "Page Title" url="https://example.com/path"\n'
            'uid=1_1 button "Submit"'
        )
        self.assertEqual(
            _current_url_from_snapshot(snap),
            "https://example.com/path",
        )

    def test_02_empty_snapshot_returns_none(self):
        self.assertIsNone(_current_url_from_snapshot(""))

    def test_03_no_root_webarea_returns_none(self):
        snap = 'uid=1_0 main\nuid=1_1 button "Submit"'
        self.assertIsNone(_current_url_from_snapshot(snap))

    def test_04_empty_url_attribute_returns_empty_string(self):
        snap = 'uid=1_0 RootWebArea "Blank" url=""'
        self.assertEqual(_current_url_from_snapshot(snap), "")

    def test_05_multiple_root_webarea_first_wins(self):
        snap = (
            'uid=1_0 RootWebArea "Tab A" url="https://a.example/"\n'
            'uid=2_0 RootWebArea "Tab B" url="https://b.example/"'
        )
        self.assertEqual(
            _current_url_from_snapshot(snap),
            "https://a.example/",
        )


class TestSnapshotToText(unittest.TestCase):
    """Extractor must handle None, dict-flattened, and object-form results."""

    def test_01_none_returns_empty(self):
        self.assertEqual(_snapshot_to_text(None), "")

    def test_02_dict_form_concatenates_text_items(self):
        result = {
            "content": [
                {"type": "text", "text": "line-1"},
                {"type": "text", "text": "line-2"},
                {"type": "image", "data": "..."},  # non-text item ignored
            ]
        }
        self.assertEqual(_snapshot_to_text(result), "line-1\nline-2")


class TestResolveSelectorToUid(unittest.TestCase):
    """Role+name resolver. Ambiguity is a finding — zero or multi both fail."""

    _SNAPSHOT = (
        'uid=1_0 RootWebArea "Test" url="https://example.com/"\n'
        'uid=1_1 main\n'
        'uid=1_2 navigation "Primary"\n'
        'uid=1_3 combobox\n'
        'uid=1_4 button "Submit"\n'
        'uid=1_5 link "Home"\n'
        'uid=1_6 textbox "Email"\n'
    )

    def test_01_happy_path_role_name_match(self):
        uid = _resolve_selector_to_uid(
            {"role": "button", "name": "Submit"}, self._SNAPSHOT,
        )
        self.assertEqual(uid, "1_4")

    def test_02_zero_match_raises(self):
        with self.assertRaises(FlowRefusedError) as cm:
            _resolve_selector_to_uid(
                {"role": "button", "name": "Cancel"}, self._SNAPSHOT,
            )
        self.assertIn("not found", str(cm.exception))

    def test_03_multi_match_raises(self):
        snap = (
            'uid=1_0 RootWebArea "Dup" url="https://x/"\n'
            'uid=1_1 button "Submit"\n'
            'uid=1_2 button "Submit"\n'
        )
        with self.assertRaises(FlowRefusedError) as cm:
            _resolve_selector_to_uid(
                {"role": "button", "name": "Submit"}, snap,
            )
        msg = str(cm.exception)
        self.assertIn("matched 2", msg)
        self.assertIn("1_1", msg)
        self.assertIn("1_2", msg)

    def test_04_empty_snapshot_raises(self):
        with self.assertRaises(FlowRefusedError) as cm:
            _resolve_selector_to_uid(
                {"role": "button", "name": "Submit"}, "",
            )
        self.assertIn("no snapshot", str(cm.exception).lower())

    def test_05_whitespace_only_snapshot_raises(self):
        with self.assertRaises(FlowRefusedError):
            _resolve_selector_to_uid(
                {"role": "button", "name": "Submit"}, "   \n\t  ",
            )

    def test_06_non_dict_selector_raises(self):
        with self.assertRaises(FlowRefusedError) as cm:
            _resolve_selector_to_uid("button:submit", self._SNAPSHOT)
        self.assertIn("must be a dict", str(cm.exception))

    def test_07_non_string_role_or_name_raises(self):
        with self.assertRaises(FlowRefusedError):
            _resolve_selector_to_uid(
                {"role": 42, "name": "Submit"}, self._SNAPSHOT,
            )
        with self.assertRaises(FlowRefusedError):
            _resolve_selector_to_uid(
                {"role": "button", "name": None}, self._SNAPSHOT,
            )

    def test_08_nameless_structural_role_matches_empty_name(self):
        # `main` and `combobox` nodes in the tree have no quoted name; a
        # selector with name="" must resolve to them via the optional-name
        # capture group collapsing to "".
        uid_main = _resolve_selector_to_uid(
            {"role": "main", "name": ""}, self._SNAPSHOT,
        )
        self.assertEqual(uid_main, "1_1")
        uid_combo = _resolve_selector_to_uid(
            {"role": "combobox", "name": ""}, self._SNAPSHOT,
        )
        self.assertEqual(uid_combo, "1_3")


if __name__ == "__main__":
    unittest.main()
