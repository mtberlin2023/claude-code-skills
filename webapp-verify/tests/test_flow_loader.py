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

    # ─── Abbreviated / alternative IPv4 SSRF bypass (Anya #5a, 2026-04-22) ──
    # Python's strict `ipaddress.ip_address()` rejects these forms; Chrome's
    # WHATWG URL parser normalises every one of them to 127.0.0.1 and loads
    # the page. `_canonicalise_ip_host()` closes the gap via socket.inet_aton.

    def test_38_ipv4_shortened_dot_form_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://127.1/admin"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    def test_39_ipv4_decimal_form_refused(self):
        # 2130706433 == 0x7f000001 == 127.0.0.1
        p = write_flow(self.tmpdir, self._with_navigate_url("http://2130706433/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    def test_40_ipv4_hex_form_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://0x7f000001/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    def test_41_ipv4_octal_form_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://0177.0.0.1/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    def test_42_ipv6_mapped_ipv4_loopback_refused(self):
        # ::ffff:127.0.0.1 is the IPv4-mapped IPv6 form of loopback.
        p = write_flow(self.tmpdir, self._with_navigate_url("http://[::ffff:127.0.0.1]/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("restricted", str(ctx.exception))

    def test_43_dns_name_starting_with_digit_ok(self):
        # `1password.com` starts with a digit but is a legitimate DNS name;
        # the canonicaliser's regex prevents false-positive IP parsing.
        p = write_flow(self.tmpdir, self._with_navigate_url("https://1password.com/"))
        flow = load_flow(p)
        self.assertEqual(flow["steps"][0]["tool"], "navigate_page")

    def test_44_dns_name_pure_hex_letters_ok(self):
        # `abc.def.com` contains only chars in `[0-9a-fA-FxX.]` but is a
        # legitimate DNS name; inet_aton correctly rejects it.
        p = write_flow(self.tmpdir, self._with_navigate_url("https://abc.def.com/"))
        flow = load_flow(p)
        self.assertEqual(flow["steps"][0]["tool"], "navigate_page")

    # ─── Well-known loopback hostnames (Anya #5c, 2026-04-22) ───────────────
    # `_canonicalise_ip_host` correctly returns None for DNS names (no
    # resolution in a static gate), but `localhost` / `ip6-localhost` /
    # `ip6-loopback` / `broadcasthost` are universally mapped to loopback via
    # /etc/hosts. The hostname denylist, not the IP canonicaliser, is the
    # right gate for this class.

    def test_54_localhost_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://localhost/admin"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("refused", str(ctx.exception))
        self.assertIn("localhost", str(ctx.exception))

    def test_55_ip6_localhost_refused(self):
        p = write_flow(self.tmpdir, self._with_navigate_url("http://ip6-localhost/"))
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("refused", str(ctx.exception))

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

    # ─── Canonical token-shape library (Anya #10a, 2026-04-22) ──────────────
    # Entropy alone only catches random-base64 (5.36 bits/char). Real-world
    # token formats sit below the 4.5 threshold: MD5 hex 3.48, SHA-256 3.81,
    # AWS 3.68, GitHub PAT 4.14, JWT 4.36. TOKEN_SHAPE_PATTERNS closes the
    # gap.

    def test_45_aws_access_key_refused(self):
        data = self._minimal_valid()
        data["goal"] = "Verify deploy using AKIAIOSFODNN7EXAMPLE credentials"
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("AWS access key", str(ctx.exception))

    def test_46_github_pat_refused(self):
        # GitHub PAT format: `ghp_` + exactly 36 base62 chars.
        data = self._with_navigate_url(
            "https://example.com/cb?t=ghp_16C7e42F292c6912E7710c838347Ae178B4a"
        )
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("GitHub PAT", str(ctx.exception))

    def test_47_jwt_refused(self):
        data = self._minimal_valid()
        data["goal"] = (
            "Test SSO with "
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NSJ9.abcdefghijk"
        )
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("JWT", str(ctx.exception))

    def test_48_sha256_hex_in_goal_refused(self):
        data = self._minimal_valid()
        data["goal"] = (
            "Verify commit "
            "5ce1fa81614958e267b21fb2aa34e0aea8e2c6ede60d52aba45fd47246b4d741"
        )
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("SHA-256 hex", str(ctx.exception))

    def test_49_pem_header_refused(self):
        data = self._minimal_valid()
        data["goal"] = (
            "Rotate key: -----BEGIN RSA PRIVATE KEY----- MIIEowIBAAKCAQ..."
        )
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("PEM private key", str(ctx.exception))

    def test_50_anthropic_key_refused(self):
        data = self._minimal_valid()
        data["goal"] = "Run experiment with sk-ant-api03-abcdefghijklmnopqrst-xxx"
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("Anthropic", str(ctx.exception))

    def test_51_slack_token_refused(self):
        data = self._minimal_valid()
        data["goal"] = "Post to channel with xoxb-1234567890-abcdefghij"
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("Slack", str(ctx.exception))

    def test_52_token_shape_with_allow_flag_loads(self):
        data = self._minimal_valid()
        data["goal"] = "Leak test with AKIAIOSFODNN7EXAMPLE (intentional)"
        p = write_flow(self.tmpdir, data)
        flow = load_flow(p, allow_high_entropy=True)
        self.assertIn("AKIA", flow["goal"])

    def test_53_hex_like_lowercase_string_not_flagged(self):
        # 32 lowercase letters that happen to all be in [a-f] would match
        # the 32-char-hex regex. "deadbeefcafebabe..." is contrived but
        # verifies the word-boundary guards work for natural prose mixed
        # with shorter hex strings.
        data = self._minimal_valid()
        data["goal"] = "Dashboard shows deadbeef at top (not a full 32-hex run)"
        p = write_flow(self.tmpdir, data)
        flow = load_flow(p)
        self.assertIn("deadbeef", flow["goal"])

    # ─── Uppercase hex in token-shape regex (Anya #10b, 2026-04-22) ─────────
    # SHA-256 / 32-char-hex regexes previously used `[0-9a-f]` only; widened
    # to `[0-9a-fA-F]` so uppercase hex (e.g. BSD sha256sum(1) output, some
    # Windows tooling) is detected. Boundary guards widened to the same class
    # to preserve "no mid-hex-sequence match" semantics on both cases.

    def test_56_uppercase_sha256_in_goal_refused(self):
        data = self._minimal_valid()
        data["goal"] = (
            "Verify commit "
            "5CE1FA81614958E267B21FB2AA34E0AEA8E2C6EDE60D52ABA45FD47246B4D741"
        )
        p = write_flow(self.tmpdir, data)
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("SHA-256 hex", str(ctx.exception))

    def test_57_uppercase_32char_hex_in_url_refused(self):
        # 32 uppercase hex chars (MD5-shaped cache-buster). Previously slipped
        # past because the character class was [0-9a-f] only.
        p = write_flow(
            self.tmpdir,
            self._with_navigate_url(
                "https://example.com/asset?v=5CE1FA81614958E267B21FB2AA34E0AE"
            ),
        )
        with self.assertRaises(FlowRefusedError) as ctx:
            load_flow(p)
        self.assertIn("32-char hex", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
