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
    _ext_for_mime,
    _extract_binary_blobs,
    _result_to_dict,
    emit_verdict,
    ensure_artefacts_dir,
    viewport_subdir,
    write_artefact_bytes,
    write_artefact_json,
)


class _FakeContentItem:
    """Stand-in for an mcp content item — duck-typed against the real shape."""
    def __init__(self, *, text=None, data=None, mimeType=None, item_type=None):
        if text is not None:
            self.text = text
        if data is not None:
            self.data = data
        if mimeType is not None:
            self.mimeType = mimeType
        if item_type is not None:
            self.type = item_type


class _FakeCallToolResult:
    """Stand-in for mcp.CallToolResult — content list + optional structuredContent."""
    def __init__(self, content=None, structuredContent=None):
        self.content = content or []
        self.structuredContent = structuredContent


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


class TestBinaryBlobExtraction(unittest.TestCase):
    """Path C #A2 fix: screenshot bytes survive the result -> writer round-trip
    instead of being lost in _result_to_dict's blob flattening."""

    def test_15_extract_blob_from_raw_bytes(self):
        png = b"\x89PNG\r\n\x1a\nfake-screenshot-bytes"
        result = _FakeCallToolResult(content=[
            _FakeContentItem(data=png, mimeType="image/png"),
        ])
        blobs = _extract_binary_blobs(result)
        self.assertEqual(len(blobs), 1)
        mime, data = blobs[0]
        self.assertEqual(mime, "image/png")
        self.assertEqual(data, png)

    def test_16_extract_blob_from_base64_string(self):
        import base64
        png = b"\x89PNG\r\n\x1a\nbase64-payload"
        encoded = base64.b64encode(png).decode("ascii")
        result = _FakeCallToolResult(content=[
            _FakeContentItem(data=encoded, mimeType="image/png"),
        ])
        blobs = _extract_binary_blobs(result)
        self.assertEqual(len(blobs), 1)
        self.assertEqual(blobs[0][1], png)

    def test_17_extract_blob_skips_text_items(self):
        result = _FakeCallToolResult(content=[
            _FakeContentItem(text="snapshot text"),
            _FakeContentItem(text="more text"),
        ])
        self.assertEqual(_extract_binary_blobs(result), [])

    def test_18_extract_blob_empty_content(self):
        result = _FakeCallToolResult(content=[])
        self.assertEqual(_extract_binary_blobs(result), [])

    def test_19_extract_blob_default_mime_when_missing(self):
        result = _FakeCallToolResult(content=[
            _FakeContentItem(data=b"some-bytes"),
        ])
        blobs = _extract_binary_blobs(result)
        self.assertEqual(len(blobs), 1)
        self.assertEqual(blobs[0][0], "application/octet-stream")

    def test_20_extract_blob_from_dict_returns_empty(self):
        # Pre-flattened dicts have already lost the bytes.
        flat = {"content": [{"type": "blob", "size": 42}]}
        self.assertEqual(_extract_binary_blobs(flat), [])

    def test_21_extract_blob_invalid_base64_skipped(self):
        result = _FakeCallToolResult(content=[
            _FakeContentItem(data="!!! not base64 !!!", mimeType="image/png"),
        ])
        # Skipped silently rather than blowing up the run.
        self.assertEqual(_extract_binary_blobs(result), [])


class TestExtForMime(unittest.TestCase):
    """File extensions for the per-step screenshot writer."""

    def test_22_ext_png(self):
        self.assertEqual(_ext_for_mime("image/png"), ".png")

    def test_23_ext_jpeg(self):
        self.assertEqual(_ext_for_mime("image/jpeg"), ".jpg")

    def test_24_ext_webp(self):
        self.assertEqual(_ext_for_mime("image/webp"), ".webp")

    def test_25_ext_pdf(self):
        self.assertEqual(_ext_for_mime("application/pdf"), ".pdf")

    def test_26_ext_unknown_falls_back(self):
        self.assertEqual(_ext_for_mime("application/x-novel-format"), ".bin")
        self.assertEqual(_ext_for_mime(""), ".bin")


class TestResultToDictIdempotent(unittest.TestCase):
    """_result_to_dict must accept pre-flattened dicts (refactor rename guard)."""

    def test_27_dict_passes_through(self):
        flat = {"content": [{"type": "text", "text": "hello"}]}
        self.assertEqual(_result_to_dict(flat), flat)

    def test_28_blob_summary_includes_mimetype(self):
        png = b"\x89PNG\r\n\x1a\n"
        result = _FakeCallToolResult(content=[
            _FakeContentItem(data=png, mimeType="image/png"),
        ])
        flat = _result_to_dict(result)
        self.assertEqual(len(flat["content"]), 1)
        self.assertEqual(flat["content"][0]["type"], "blob")
        self.assertEqual(flat["content"][0]["mimeType"], "image/png")
        self.assertEqual(flat["content"][0]["size"], len(png))

    def test_29_text_item_preserved(self):
        result = _FakeCallToolResult(content=[
            _FakeContentItem(text="snapshot text"),
        ])
        flat = _result_to_dict(result)
        self.assertEqual(flat["content"][0]["type"], "text")
        self.assertEqual(flat["content"][0]["text"], "snapshot text")

    def test_30_structured_content_takes_precedence(self):
        result = _FakeCallToolResult(
            content=[_FakeContentItem(text="ignored")],
            structuredContent={"verdict": "ok"},
        )
        flat = _result_to_dict(result)
        self.assertEqual(flat, {"verdict": "ok"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
