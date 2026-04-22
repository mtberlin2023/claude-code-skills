"""
28-shape smuggling fixture for Anya #1 (allowlist-bypass, all three shapes).

Runs without external deps — stdlib unittest only. From the skill root:
    python3 -m unittest tests.test_dispatcher_smuggling -v

Grouped into three TestCase classes matching the three bypass shapes
Anya flagged after the smoke-test addendum:

  TestEmulateDispatcher     — parameter-level bypass (20 shapes)
  TestAllowlistMembership   — tool-level bypass + in-page escape hatches (4)
  TestServerFlagRefusal     — server-start flag smuggling (4)

Total: 28 shapes. A future Anya consult will extend this fixture; this is
the v1 baseline.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify import (  # noqa: E402
    ALLOWLIST,
    DENYLIST,
    EMULATE_PARAM_GATES,
    build_server_command,
    dispatch_emulate,
)


class TestEmulateDispatcher(unittest.TestCase):
    """Shapes 1–20: parameter-level bypass on the `emulate` mega-tool."""

    # ─── Defaults-allowed params ────────────────────────────────────────────

    def test_01_empty_params(self):
        accepted, rejected = dispatch_emulate({})
        self.assertEqual(accepted, {})
        self.assertEqual(rejected, [])

    def test_02_single_allowed_network(self):
        accepted, rejected = dispatch_emulate({"networkConditions": "Offline"})
        self.assertEqual(accepted, {"networkConditions": "Offline"})
        self.assertEqual(rejected, [])

    def test_03_single_allowed_viewport(self):
        vp = {"width": 1280, "height": 800}
        accepted, rejected = dispatch_emulate({"viewport": vp})
        self.assertEqual(accepted, {"viewport": vp})
        self.assertEqual(rejected, [])

    def test_04_both_allowed_together(self):
        accepted, rejected = dispatch_emulate(
            {"networkConditions": "Slow 3G", "viewport": {"width": 375, "height": 667}}
        )
        self.assertEqual(len(accepted), 2)
        self.assertEqual(rejected, [])

    # ─── Default-rejected params without unlock ─────────────────────────────

    def test_05_cpu_throttle_rejected(self):
        accepted, rejected = dispatch_emulate({"cpuThrottlingRate": 4})
        self.assertEqual(accepted, {})
        self.assertEqual(len(rejected), 1)
        self.assertIn("cpuThrottlingRate", rejected[0])

    def test_06_geolocation_rejected(self):
        accepted, rejected = dispatch_emulate({"geolocation": {"latitude": 0, "longitude": 0}})
        self.assertEqual(accepted, {})
        self.assertIn("geolocation", rejected[0])

    def test_07_user_agent_rejected(self):
        accepted, rejected = dispatch_emulate({"userAgent": "evil-spoof/1.0"})
        self.assertEqual(accepted, {})
        self.assertIn("userAgent", rejected[0])

    def test_08_color_scheme_rejected(self):
        accepted, rejected = dispatch_emulate({"colorScheme": "dark"})
        self.assertEqual(accepted, {})
        self.assertIn("colorScheme", rejected[0])

    # ─── Mixed allowed + rejected ───────────────────────────────────────────

    def test_09_mix_allowed_and_rejected(self):
        accepted, rejected = dispatch_emulate(
            {"networkConditions": "Offline", "cpuThrottlingRate": 4}
        )
        self.assertEqual(accepted, {"networkConditions": "Offline"})
        self.assertEqual(len(rejected), 1)
        self.assertIn("cpuThrottlingRate", rejected[0])

    # ─── Unlock flags from flow allowances ──────────────────────────────────

    def test_10_cpu_throttle_unlocked(self):
        accepted, rejected = dispatch_emulate(
            {"cpuThrottlingRate": 4},
            flow_allowances={"allow_cpu_throttle": True},
        )
        self.assertEqual(accepted, {"cpuThrottlingRate": 4})
        self.assertEqual(rejected, [])

    def test_11_geolocation_unlocked(self):
        accepted, rejected = dispatch_emulate(
            {"geolocation": {"latitude": 52, "longitude": 13}},
            flow_allowances={"allow_geolocation": True},
        )
        self.assertIn("geolocation", accepted)
        self.assertEqual(rejected, [])

    def test_12_user_agent_unlocked(self):
        accepted, rejected = dispatch_emulate(
            {"userAgent": "Mozilla/5.0 TestBot"},
            flow_allowances={"allow_user_agent_override": True},
        )
        self.assertIn("userAgent", accepted)
        self.assertEqual(rejected, [])

    def test_13_color_scheme_unlocked(self):
        accepted, rejected = dispatch_emulate(
            {"colorScheme": "dark"},
            flow_allowances={"allow_color_scheme_override": True},
        )
        self.assertIn("colorScheme", accepted)
        self.assertEqual(rejected, [])

    # ─── Unknown / injected keys ────────────────────────────────────────────

    def test_14_unknown_key_rejected(self):
        accepted, rejected = dispatch_emulate({"unknown_param": "x"})
        self.assertEqual(accepted, {})
        self.assertEqual(len(rejected), 1)
        self.assertIn("unknown_param", rejected[0])

    def test_15_known_plus_unknown(self):
        accepted, rejected = dispatch_emulate(
            {"networkConditions": "Offline", "unknown_param": "x"}
        )
        self.assertEqual(accepted, {"networkConditions": "Offline"})
        self.assertEqual(len(rejected), 1)

    def test_16_prototype_pollution_key(self):
        accepted, rejected = dispatch_emulate({"__proto__": {"isAdmin": True}})
        self.assertEqual(accepted, {})
        self.assertIn("__proto__", rejected[0])

    def test_17_dotted_key_injection(self):
        accepted, rejected = dispatch_emulate({"networkConditions.injected": "x"})
        self.assertEqual(accepted, {})
        self.assertIn("networkConditions.injected", rejected[0])

    # ─── Allowance-noise cases ──────────────────────────────────────────────

    def test_18_allowance_without_matching_param_is_noop(self):
        accepted, rejected = dispatch_emulate(
            {"networkConditions": "Offline"},
            flow_allowances={"allow_cpu_throttle": True},
        )
        self.assertEqual(accepted, {"networkConditions": "Offline"})
        self.assertEqual(rejected, [])

    def test_19_nonsense_allowance_key_ignored(self):
        accepted, rejected = dispatch_emulate(
            {"cpuThrottlingRate": 4},
            flow_allowances={"allow_evil": True},
        )
        self.assertEqual(accepted, {})
        self.assertEqual(len(rejected), 1)

    def test_20_all_allowances_true_empty_params(self):
        accepted, rejected = dispatch_emulate(
            {},
            flow_allowances={
                "allow_cpu_throttle": True,
                "allow_geolocation": True,
                "allow_user_agent_override": True,
                "allow_color_scheme_override": True,
            },
        )
        self.assertEqual(accepted, {})
        self.assertEqual(rejected, [])


class TestAllowlistMembership(unittest.TestCase):
    """Shapes 21–24: tool-level bypass + in-page escape hatches.

    These don't run the dispatcher — they assert the ALLOWLIST/DENYLIST
    constants refuse known-dangerous tools. If a refactor silently drops
    a tool from the deny-list, these fail.
    """

    def test_21_execute_in_page_tool_denied(self):
        self.assertNotIn("execute_in_page_tool", ALLOWLIST)
        self.assertIn("execute_in_page_tool", DENYLIST)

    def test_22_evaluate_script_denied(self):
        self.assertNotIn("evaluate_script", ALLOWLIST)
        self.assertIn("evaluate_script", DENYLIST)

    def test_23_install_extension_denied(self):
        self.assertNotIn("install_extension", ALLOWLIST)
        self.assertIn("install_extension", DENYLIST)

    def test_24_handle_dialog_denied(self):
        self.assertNotIn("handle_dialog", ALLOWLIST)
        self.assertIn("handle_dialog", DENYLIST)


class TestServerFlagRefusal(unittest.TestCase):
    """Shapes 25–32: server-start flag smuggling.

    --slim and --experimentalScreencast expose tools outside the allowlist
    (arbitrary JS via renamed evaluate, screencast capture). --user-data-dir,
    --profileDirectory, --executablePath, --chromeArg defeat --isolated or
    redirect Chrome itself. build_server_command must refuse all of them
    before npx launch — including the --flag=value form.
    """

    def test_25_slim_refused(self):
        with self.assertRaises(ValueError) as ctx:
            build_server_command(["--slim"])
        self.assertIn("--slim", str(ctx.exception))

    def test_26_experimental_screencast_refused(self):
        with self.assertRaises(ValueError) as ctx:
            build_server_command(["--experimentalScreencast"])
        self.assertIn("--experimentalScreencast", str(ctx.exception))

    def test_27_refused_flag_hidden_among_others(self):
        with self.assertRaises(ValueError):
            build_server_command(["--some-ok-flag", "--slim", "--another"])

    def test_28_allowed_flag_passes_through(self):
        # --debug-adapter is not refused (not in REFUSED_SERVER_FLAGS).
        # Should produce a command including it. No exception.
        cmd = build_server_command(["--debug-adapter"])
        self.assertIn("--debug-adapter", cmd)
        self.assertIn("--isolated", cmd)  # forced flag present

    # ─── Anya #8a (2026-04-21): --isolated can be defeated by a later flag ──
    # REFUSED_SERVER_FLAGS extended + equals-form handled in build_server_command.

    def test_29_user_data_dir_refused(self):
        with self.assertRaises(ValueError) as ctx:
            build_server_command(["--user-data-dir", "/evil"])
        self.assertIn("user-data-dir", str(ctx.exception))

    def test_30_user_data_dir_equals_form_refused(self):
        # The critical case: exact-match string check pre-fix would miss this.
        with self.assertRaises(ValueError) as ctx:
            build_server_command(["--user-data-dir=/Users/mark/Library/Chrome"])
        self.assertIn("user-data-dir", str(ctx.exception))

    def test_31_executable_path_refused(self):
        with self.assertRaises(ValueError):
            build_server_command(["--executablePath=/tmp/rogue-chrome"])

    def test_32_chromeArg_refused(self):
        with self.assertRaises(ValueError):
            build_server_command(["--chromeArg", "--no-sandbox"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
