"""
Flow-script loader refuse-to-run fixture (Katarina #464, anti-pattern #2).

A flow without a `goal` is a click-sequence, not a test — refuse to run.
A flow without a `success_state` (url_pattern OR landmark) has no pass/fail
contract — refuse to run. A flow referencing denied or unknown tools has a
known-bad shape — refuse to run.

From the skill root:
    python3 -m unittest tests.test_flow_loader -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify import FlowRefusedError, load_flow  # noqa: E402


def write_flow(tmpdir: Path, data) -> Path:
    p = tmpdir / "flow.json"
    if isinstance(data, str):
        p.write_text(data, encoding="utf-8")
    else:
        p.write_text(json.dumps(data), encoding="utf-8")
    return p


class TestFlowLoader(unittest.TestCase):
    """Katarina refuse-to-run gate. Tests the shape of the rejection, not just
    the rejection itself — caller prints the error verbatim to the user."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _minimal_valid(self):
        return {
            "goal": "User reaches the dashboard",
            "success_state": {"url_pattern": "/dashboard"},
            "steps": [{"tool": "navigate_page", "url": "https://example.com"}],
        }

    # ─── Happy path ─────────────────────────────────────────────────────────

    def test_01_minimal_valid_flow_loads(self):
        p = write_flow(self.tmpdir, self._minimal_valid())
        flow = load_flow(p)
        self.assertEqual(flow["goal"], "User reaches the dashboard")

    def test_02_landmark_only_success_state_ok(self):
        data = self._minimal_valid()
        data["success_state"] = {"landmark": {"role": "heading", "name_matches": "Welcome"}}
        p = write_flow(self.tmpdir, data)
        flow = load_flow(p)
        self.assertIn("landmark", flow["success_state"])

    def test_03_both_url_pattern_and_landmark_ok(self):
        data = self._minimal_valid()
        data["success_state"] = {
            "url_pattern": "/dashboard",
            "landmark": {"role": "heading", "name_matches": "Welcome"},
        }
        p = write_flow(self.tmpdir, data)
        flow = load_flow(p)
        self.assertIn("url_pattern", flow["success_state"])
        self.assertIn("landmark", flow["success_state"])

    def test_04_emulate_tool_allowed_in_steps(self):
        data = self._minimal_valid()
        data["steps"].append({"tool": "emulate", "params": {"networkConditions": "Offline"}})
        p = write_flow(self.tmpdir, data)
        flow = load_flow(p)
        self.assertEqual(len(flow["steps"]), 2)

    # ─── File / JSON rejection ──────────────────────────────────────────────

    def test_05_missing_file(self):
        p = self.tmpdir / "does-not-exist.json"
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("cannot read", str(ctx.exception))

    def test_06_invalid_json(self):
        p = write_flow(self.tmpdir, "{not json")
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_07_top_level_array_rejected(self):
        p = write_flow(self.tmpdir, [])
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("JSON object at top level", str(ctx.exception))

    # ─── Goal rejection (anti-pattern #2 enforcement) ───────────────────────

    def test_08_missing_goal(self):
        data = self._minimal_valid()
        del data["goal"]
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("goal", str(ctx.exception))
        self.assertIn("click-sequence", str(ctx.exception))

    def test_09_empty_goal_string(self):
        data = self._minimal_valid()
        data["goal"] = ""
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    def test_10_goal_is_whitespace(self):
        data = self._minimal_valid()
        data["goal"] = "   "
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    def test_11_goal_wrong_type(self):
        data = self._minimal_valid()
        data["goal"] = 42
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    # ─── success_state rejection ────────────────────────────────────────────

    def test_12_missing_success_state(self):
        data = self._minimal_valid()
        del data["success_state"]
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("success_state", str(ctx.exception))

    def test_13_empty_success_state(self):
        data = self._minimal_valid()
        data["success_state"] = {}
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("url_pattern", str(ctx.exception))
        self.assertIn("landmark", str(ctx.exception))

    def test_14_success_state_wrong_type(self):
        data = self._minimal_valid()
        data["success_state"] = "/dashboard"
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    def test_15_empty_url_pattern(self):
        data = self._minimal_valid()
        data["success_state"] = {"url_pattern": ""}
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    # ─── Steps rejection ────────────────────────────────────────────────────

    def test_16_missing_steps(self):
        data = self._minimal_valid()
        del data["steps"]
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    def test_17_empty_steps_list(self):
        data = self._minimal_valid()
        data["steps"] = []
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    def test_18_denylisted_tool_in_step(self):
        data = self._minimal_valid()
        data["steps"] = [{"tool": "evaluate_script", "script": "alert(1)"}]
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("evaluate_script", str(ctx.exception))
        self.assertIn("deny-list", str(ctx.exception))

    def test_19_execute_in_page_tool_bypass_rejected(self):
        # Hidden escape hatch — smoke-test addendum flagged this as bypass vector.
        data = self._minimal_valid()
        data["steps"] = [{"tool": "execute_in_page_tool", "name": "x", "args": {}}]
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("execute_in_page_tool", str(ctx.exception))

    def test_20_unknown_tool_in_step(self):
        data = self._minimal_valid()
        data["steps"] = [{"tool": "teleport_user", "coords": [0, 0]}]
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("teleport_user", str(ctx.exception))
        self.assertIn("allowlist", str(ctx.exception))

    def test_21_step_missing_tool_field(self):
        data = self._minimal_valid()
        data["steps"] = [{"url": "https://example.com"}]
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    def test_22_step_not_object(self):
        data = self._minimal_valid()
        data["steps"] = ["navigate_page"]
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError):
            load_flow(p)

    # ─── SSRF static gate (Anya #5, 2026-04-21) ─────────────────────────────

    def _with_navigate_url(self, url):
        data = self._minimal_valid()
        data["steps"] = [{"tool": "navigate_page", "url": url}]
        return data

    def test_23_file_scheme_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("file:///etc/passwd"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("scheme", str(ctx.exception))

    def test_24_data_scheme_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("data:text/html,<h1>x"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("scheme", str(ctx.exception))

    def test_25_javascript_scheme_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("javascript:alert(1)"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("scheme", str(ctx.exception))

    def test_26_chrome_scheme_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("chrome://settings"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("scheme", str(ctx.exception))

    def test_27_loopback_ipv4_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://127.0.0.1/admin"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    def test_28_aws_imds_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://169.254.169.254/latest/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    def test_29_private_10net_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://10.0.0.1/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    def test_30_gcp_metadata_host_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://metadata.google.internal/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("cloud-metadata", str(ctx.exception))

    def test_31_https_public_passes(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("https://example.com/path"))
        flow = load_flow(p)
        self.assertEqual(flow["steps"][0]["tool"], "navigate_page")

    def test_32_ipv6_loopback_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://[::1]/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    # ─── Entropy scanner (Anya #10, 2026-04-21) ─────────────────────────────

    def test_33_high_entropy_in_goal_refused(self):
        data = self._minimal_valid()
        data["goal"] = "Leak check: Xp9kQ2vNt8JdL6mZ4bR7cY3wFsHuA1gEiOzP5qT0y"
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("high-entropy", str(ctx.exception))

    def test_34_high_entropy_in_url_refused(self):
        data = self._with_navigate_url(
            "https://example.com/cb?token=Xp9kQ2vNt8JdL6mZ4bR7cY3wFsHuA1gEiOzP5qT0y"
        )
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("high-entropy", str(ctx.exception))

    def test_35_high_entropy_with_allow_flag_loads(self):
        data = self._minimal_valid()
        data["goal"] = "Reach checkout with Xp9kQ2vNt8JdL6mZ4bR7cY3wFsHuA1gEiOzP5qT0y token"
        p = write_flow(self.tmpdir, data)
        flow = load_flow(p, allow_high_entropy=True)
        self.assertTrue(flow["goal"].startswith("Reach"))

    def test_36_natural_language_goal_not_flagged(self):
        data = self._minimal_valid()
        data["goal"] = (
            "User completes signup, lands on the dashboard, and sees the welcome banner"
        )
        p = write_flow(self.tmpdir, data)
        flow = load_flow(p)
        self.assertIn("signup", flow["goal"])

    def test_37_uuid_in_url_flagged(self):
        # UUIDs have entropy ~3.7 bits/char — below our 4.5 threshold.
        # This test codifies the acceptable-false-negative: UUIDs PASS.
        data = self._with_navigate_url(
            "https://example.com/run/550e8400-e29b-41d4-a716-446655440000"
        )
        p = write_flow(self.tmpdir, data)
        flow = load_flow(p)
        self.assertEqual(flow["steps"][0]["tool"], "navigate_page")


if __name__ == "__main__":
    unittest.main(verbosity=2)
