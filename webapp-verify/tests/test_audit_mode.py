"""
Audit-mode URL gate (Anya #3a, 2026-04-22).

`run_audit_mode(url, …)` skips `load_flow`, so the SSRF gate that fires per
navigate_page step does not apply unless audit-mode re-runs it. Before the
fix, a user who passed `--audit-mode file:///etc/passwd
--confirm-substrate-audit` and hit `y` at the stdin prompt would ship the
file contents to disk. The fix calls `_validate_step_url` immediately after
the `confirmed` check and wraps the FlowRefusedError as AuditRefusedError.

From the skill root:
    python3 -m unittest tests.test_audit_mode -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify import AuditRefusedError, run_audit_mode  # noqa: E402


class TestAuditModeUrlGate(unittest.TestCase):
    """Every URL that `_validate_step_url` would reject must also be rejected
    by `run_audit_mode` — even after `--confirm-substrate-audit` is passed."""

    def test_01_confirmed_false_refuses(self):
        with self.assertRaises(AuditRefusedError) as ctx:
            run_audit_mode("https://example.com/", confirmed=False, non_interactive=True)
        self.assertIn("--confirm-substrate-audit", str(ctx.exception))

    def test_02_file_scheme_refused(self):
        with self.assertRaises(AuditRefusedError) as ctx:
            run_audit_mode("file:///etc/passwd", confirmed=True, non_interactive=True)
        self.assertIn("scheme", str(ctx.exception))

    def test_03_data_scheme_refused(self):
        with self.assertRaises(AuditRefusedError) as ctx:
            run_audit_mode("data:text/html,<h1>x", confirmed=True, non_interactive=True)
        self.assertIn("scheme", str(ctx.exception))

    def test_04_ipv4_loopback_refused(self):
        with self.assertRaises(AuditRefusedError) as ctx:
            run_audit_mode("http://127.0.0.1/", confirmed=True, non_interactive=True)
        self.assertIn("restricted", str(ctx.exception))

    def test_05_shortened_ipv4_loopback_refused(self):
        # The #5a bypass must be closed in audit-mode too.
        with self.assertRaises(AuditRefusedError) as ctx:
            run_audit_mode("http://127.1/", confirmed=True, non_interactive=True)
        self.assertIn("restricted", str(ctx.exception))

    def test_06_aws_imds_refused(self):
        with self.assertRaises(AuditRefusedError) as ctx:
            run_audit_mode(
                "http://169.254.169.254/latest/meta-data/",
                confirmed=True,
                non_interactive=True,
            )
        self.assertIn("restricted", str(ctx.exception))

    def test_07_gcp_metadata_host_refused(self):
        with self.assertRaises(AuditRefusedError) as ctx:
            run_audit_mode(
                "http://metadata.google.internal/",
                confirmed=True,
                non_interactive=True,
            )
        self.assertIn("cloud-metadata", str(ctx.exception))

    def test_08_empty_url_refused(self):
        with self.assertRaises(AuditRefusedError) as ctx:
            run_audit_mode("", confirmed=True, non_interactive=True)
        self.assertIn("missing/empty", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
