"""
Output-ceiling + artefact-writer fixture (anti-pattern #3 enforcement).

Verifies:
  - emit_verdict never prints more than 3 lines
  - embedded newlines / carriage returns in verdict fields are flattened
    (can't smuggle a 4th line via an adversarial matcher name or path)
  - write_artefact_json / write_artefact_bytes land on disk correctly
  - viewport_subdir sanitises filesystem-unsafe labels
  - ensure_artefacts_dir is idempotent + honours a custom root

From the skill root:
    python3 -m unittest tests.test_output_artefacts -v
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify import (  # noqa: E402
    MAX_STDOUT_LINES,
    emit_verdict,
    ensure_artefacts_dir,
    viewport_subdir,
    write_artefact_bytes,
    write_artefact_json,
)


class TestEmitVerdict(unittest.TestCase):
    """Anti-pattern #3: stdout is a 3-line ceiling, no smuggling."""

    def _capture(self, result):
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit_verdict(result)
        return buf.getvalue().splitlines()

    def test_01_pass_result_three_lines(self):
        lines = self._capture({
            "pass": True, "matcher": "url_pattern",
            "steps_completed": 3, "steps_total": 3,
            "artefacts_dir": "/tmp/run-1",
        })
        self.assertEqual(len(lines), MAX_STDOUT_LINES)
        self.assertTrue(lines[0].startswith("PASS"))

    def test_02_fail_result_three_lines(self):
        lines = self._capture({
            "pass": False, "matcher": None,
            "steps_completed": 2, "steps_total": 5,
            "artefacts_dir": "/tmp/run-2",
        })
        self.assertEqual(len(lines), MAX_STDOUT_LINES)
        self.assertTrue(lines[0].startswith("FAIL"))
        self.assertIn("none", lines[0])

    def test_03_missing_fields_still_three_lines(self):
        lines = self._capture({})
        self.assertEqual(len(lines), MAX_STDOUT_LINES)

    def test_04_embedded_newline_in_matcher_flattened(self):
        lines = self._capture({
            "pass": True, "matcher": "url_pattern\nEVIL: leaked-4th-line",
            "steps_completed": 1, "steps_total": 1,
            "artefacts_dir": "/tmp/x",
        })
        self.assertEqual(len(lines), MAX_STDOUT_LINES)
        # The evil content is smuggled into line 1, flattened — but the
        # line count is still 3. No 4th line on stdout.
        self.assertNotIn("EVIL", "\n".join(lines).split("\n")[3:] if len(lines) > 3 else [])

    def test_05_embedded_carriage_return_in_path_flattened(self):
        lines = self._capture({
            "pass": True, "matcher": "url_pattern",
            "steps_completed": 1, "steps_total": 1,
            "artefacts_dir": "/tmp/x\rEVIL",
        })
        self.assertEqual(len(lines), MAX_STDOUT_LINES)

    def test_06_line_order_stable(self):
        lines = self._capture({
            "pass": True, "matcher": "landmark",
            "steps_completed": 2, "steps_total": 2,
            "artefacts_dir": "/tmp/run-3",
        })
        self.assertTrue(lines[0].startswith("PASS"))
        self.assertTrue(lines[1].startswith("Steps:"))
        self.assertTrue(lines[2].startswith("Artefacts:"))


class TestArtefactWriters(unittest.TestCase):
    """File-system writers — pure stdlib, no MCP dep."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_07_ensure_artefacts_dir_creates(self):
        d = ensure_artefacts_dir("run-abc", root=self.root)
        self.assertTrue(d.is_dir())
        self.assertEqual(d, self.root / "run-abc")

    def test_08_ensure_artefacts_dir_idempotent(self):
        ensure_artefacts_dir("run-xyz", root=self.root)
        # Second call should not raise.
        d = ensure_artefacts_dir("run-xyz", root=self.root)
        self.assertTrue(d.is_dir())

    def test_09_viewport_subdir_creates(self):
        run = ensure_artefacts_dir("r1", root=self.root)
        vp = viewport_subdir(run, "mobile-emu")
        self.assertTrue(vp.is_dir())
        self.assertEqual(vp.name, "viewport-mobile-emu")

    def test_10_viewport_subdir_sanitises_label(self):
        run = ensure_artefacts_dir("r2", root=self.root)
        vp = viewport_subdir(run, "../../../etc/passwd")
        # Slashes + dots stripped. Resulting dir stays inside run_dir.
        self.assertTrue(vp.is_dir())
        self.assertEqual(vp.parent, run)
        self.assertNotIn("..", vp.name)
        self.assertNotIn("/", vp.name)

    def test_11_viewport_subdir_empty_label_falls_back(self):
        run = ensure_artefacts_dir("r3", root=self.root)
        vp = viewport_subdir(run, "!!!")
        self.assertEqual(vp.name, "viewport-unknown")

    def test_12_write_artefact_json(self):
        run = ensure_artefacts_dir("r4", root=self.root)
        p = write_artefact_json(run, "result.json", {"pass": True, "n": 3})
        self.assertTrue(p.is_file())
        data = json.loads(p.read_text())
        self.assertEqual(data["pass"], True)
        self.assertEqual(data["n"], 3)

    def test_13_write_artefact_bytes(self):
        run = ensure_artefacts_dir("r5", root=self.root)
        fake_png = b"\x89PNG\r\n\x1a\nfake"
        p = write_artefact_bytes(run, "screenshot.png", fake_png)
        self.assertTrue(p.is_file())
        self.assertEqual(p.read_bytes(), fake_png)

    def test_14_write_artefact_json_creates_missing_dir(self):
        # dest_dir doesn't exist yet
        dest = self.root / "deep" / "nested" / "dir"
        p = write_artefact_json(dest, "x.json", {"ok": True})
        self.assertTrue(p.is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
