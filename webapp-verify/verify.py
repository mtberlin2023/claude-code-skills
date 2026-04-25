#!/usr/bin/env python3
"""
webapp-verify / verify.py — v1 behavioural

Subprocess wrapper around Chrome DevTools MCP (chrome-devtools-mcp on npm).
Runs a scripted flow against a live URL and writes verification artefacts
to disk. Honesty anti-patterns live in SKILL.md — read them first.

Usage:
    verify.py <flow-script.json>                       # run a flow
    verify.py <flow-script.json> --allow-high-entropy  # opt into known-secret flow fields
    verify.py --audit-mode <url> --confirm-substrate-audit
                                                       # substrate-shape dump (PII-scoped)
    verify.py --list-allowlist                         # print allowlist + deny-list + gates
    verify.py --check-install                          # verify npx + SDK + version pin

Pairs with:
  SKILL.md                                                 (product spine + honesty anti-patterns)
  install.sh                                               (hash-pinned mcp SDK install)
  _shared/briefs/BRIEF-028-webapp-verify-PANEL-SYNTHESIS.md (D1 + D2 outcomes)

Runtime deps (single dep by design — Anya #7, 2026-04-21):
  mcp == 1.27.0  (hash-pinned in install.sh)
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urlsplit
from importlib.metadata import version as _pkg_version, PackageNotFoundError

try:
    import mcp as _mcp_pkg  # noqa: F401  (kept for future probes; version read via metadata)
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError as e:
    sys.stderr.write(
        "mcp Python SDK not installed. Run `bash install.sh` from the skill dir.\n"
        f"ImportError: {e}\n"
    )
    sys.exit(2)


def _installed_mcp_version() -> str:
    """Read the mcp package version via importlib.metadata. The mcp package
    does not expose __version__ as a module attribute (1.27.0). Returns "?"
    when the metadata cannot be read."""
    try:
        return _pkg_version("mcp")
    except PackageNotFoundError:
        return "?"

# ─── Constants ──────────────────────────────────────────────────────────────

MCP_PACKAGE = "chrome-devtools-mcp"
MCP_LAUNCH_CMD = ["npx", "-y", f"{MCP_PACKAGE}@latest"]

# Pin the SDK version so a transitive upgrade doesn't silently widen the trust
# surface. Anya #7 (security-review log 2026-04-21): supply-chain posture
# requires explicit version pin + hash verification + no auto-upgrade.
MCP_SDK_VERSION = "1.27.0"
_installed_sdk_at_import = _installed_mcp_version()
if _installed_sdk_at_import != MCP_SDK_VERSION:
    # Soft fail at startup — the hash-pinned install.sh is authoritative;
    # this check exists so a dev who pip-installs from an unpinned source
    # sees the mismatch immediately, not inside a review gate.
    sys.stderr.write(
        f"WARNING: mcp SDK version drift "
        f"(installed {_installed_sdk_at_import}, expected {MCP_SDK_VERSION}). "
        f"Re-run install.sh to restore hash-pinned version.\n"
    )

# 9-tool allowlist (per D1 outcome, CDP MCP names). `fill` added 2026-04-23
# after first interactive-flow live exercise (fan-form POST) surfaced that
# chrome-devtools-mcp uses uid semantics (from take_snapshot accessibility
# tree), not CSS selectors. `fill` is the focus-less single-element equivalent
# of `fill_form`; kept separate because single-element flows are the common
# case and composing a 1-element `fill_form` is needlessly verbose.
ALLOWLIST: frozenset[str] = frozenset({
    "navigate_page",
    "click",
    "fill",
    "type_text",
    "fill_form",
    "take_snapshot",
    "list_console_messages",
    "list_network_requests",
    "take_screenshot",
})

# 14-tool deny-list at default load (post-smoke-test addendum).
# execute_in_page_tool and evaluate_script are the two critical escape hatches.
DENYLIST: frozenset[str] = frozenset({
    "evaluate_script",
    "list_in_page_tools",
    "execute_in_page_tool",
    "install_extension",
    "uninstall_extension",
    "list_extensions",
    "reload_extension",
    "trigger_extension_action",
    "take_memory_snapshot",
    "lighthouse_audit",
    "performance_start_trace",
    "performance_stop_trace",
    "upload_file",
    "handle_dialog",
})

# Flag-gated tools — refuse the server-start flags that would expose them.
FLAG_GATED_TOOLS: dict[str, str] = {
    "screencast_start": "--experimentalScreencast",
    "screencast_stop": "--experimentalScreencast",
}

# Verify-level step types — synthesised by the runner, not MCP tool calls.
# Safe by construction (no DOM mutation, no network egress); bypass ALLOWLIST.
VERIFY_STEPS: frozenset[str] = frozenset({
    "wait_for_url_change",
})

# Free-text metadata paths that bypass the entropy gate but still get
# token-shape scanning. Natural-language prose (goals, intents) routinely
# trips Shannon entropy thresholds without being secrets.
ENTROPY_SKIP_LEAVES: frozenset[str] = frozenset({
    "goal", "description", "intent", "notes", "rationale", "persona",
})

# Server-start flags the wrapper forces on every invocation.
FORCED_SERVER_FLAGS: list[str] = [
    "--isolated",
    "--no-usageStatistics",
    "--no-category-extensions",
]

# Server-start flags the wrapper refuses (exit non-zero before launch).
# Extended 2026-04-21 (Anya #8a): --user-data-dir / --profileDirectory defeat
# --isolated; --executablePath points npx at a non-Chrome binary; --chromeArg
# passes arbitrary args to Chrome (e.g. --no-sandbox).
REFUSED_SERVER_FLAGS: frozenset[str] = frozenset({
    "--slim",
    "--experimentalScreencast",
    "--user-data-dir",
    "--profileDirectory",
    "--executablePath",
    "--chromeArg",
})

# `emulate` is a mega-tool. Each parameter has a default gate.
# Per-flow allowances unlock gated params if the flow explicitly declares them.
EMULATE_PARAM_GATES: dict[str, dict] = {
    "networkConditions": {"default": "allowed", "unlock_flag": None},
    "viewport": {"default": "allowed", "unlock_flag": None},
    "cpuThrottlingRate": {"default": "rejected", "unlock_flag": "allow_cpu_throttle"},
    "geolocation": {"default": "rejected", "unlock_flag": "allow_geolocation"},
    "userAgent": {"default": "rejected", "unlock_flag": "allow_user_agent_override"},
    "colorScheme": {"default": "rejected", "unlock_flag": "allow_color_scheme_override"},
}

# Three viewports used by --audit-mode.
AUDIT_VIEWPORTS: list[tuple[str, int, int]] = [
    ("mobile-emu", 375, 667),
    ("tablet-emu", 768, 1024),
    ("desktop-emu", 1280, 800),
]

ARTEFACTS_ROOT = Path(__file__).parent / "artefacts"
SUBSTRATE_AUDIT_ROOT = ARTEFACTS_ROOT / "substrate-audit"
MAX_STDOUT_LINES = 3

# SSRF static gate (Anya #5, 2026-04-21). Scheme and hostname deny-lists are
# the first line; ipaddress checks are the second line for host-by-IP
# smuggling. Called from load_flow per navigate_page step.
ALLOWED_URL_SCHEMES: frozenset[str] = frozenset({"http", "https"})
BLOCKED_HOSTNAMES: frozenset[str] = frozenset({
    "metadata.google.internal",
    "metadata",
    "instance-data",
    # Anya #5c, 2026-04-22: well-known loopback DNS names. `_canonicalise_ip_host`
    # correctly returns None for DNS (no resolution in a static gate), but these
    # names are universally mapped to loopback via /etc/hosts. Hostname denylist,
    # not IP canonicaliser, is the right gate for this class.
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "broadcasthost",
})

# Entropy scanner (Anya #10, 2026-04-21). Bench: natural-language sentences
# sit near 3.5 bits/char; random base64 tokens climb past 5.0. Threshold
# tuned per #495 close-out.
#
# Anya #10a, 2026-04-22: entropy alone misses most real token shapes — MD5
# hex at 3.48, SHA-256 hex at 3.81, AWS keys at 3.68, JWTs at 4.36, GitHub
# PATs at 4.14 all slip past a 4.5 threshold because hex and most
# base64url-ish alphabets don't climb that high. Keep entropy as one signal
# for random-ish base64, add TOKEN_SHAPE_PATTERNS below as the complement.
HIGH_ENTROPY_THRESHOLD = 4.5
MIN_HIGH_ENTROPY_LEN = 20

# Canonical token shapes — if any flow string matches any of these patterns,
# refuse the flow unless --allow-high-entropy is passed. Closes the gap
# between Shannon entropy (which only trips on random base64) and real-world
# secret formats.
TOKEN_SHAPE_PATTERNS: dict[str, re.Pattern] = {
    "AWS access key":       re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "AWS session key":      re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    "GitHub PAT":           re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    "GitHub OAuth":         re.compile(r"\bgho_[A-Za-z0-9]{36}\b"),
    "GitHub fine-grained":  re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
    "Anthropic API key":    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "OpenAI API key":       re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "JWT":                  re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\."),
    # Anya #10b, 2026-04-22: hex classes widened to [0-9a-fA-F]. Lowercase-only
    # missed uppercase SHA-256 / 32-char hex (e.g. sha256sum(1) output on BSD).
    # Boundary guards widened to same class to keep "no mid-hex-sequence match"
    # semantics case-consistent on both sides.
    "SHA-256 hex":          re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])"),
    "32-char hex":          re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])"),
    "PEM private key":      re.compile(r"-----BEGIN[ A-Z]*PRIVATE KEY-----"),
    "Slack token":          re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "Google OAuth":         re.compile(r"\bya29\.[A-Za-z0-9_-]{20,}\b"),
}

# Subprocess env whitelist (Anya #11, 2026-04-22). The previous implementation
# passed `env={**os.environ, …}` to the chrome-devtools-mcp Node subprocess,
# handing over the entire caller environment — any ANTHROPIC_API_KEY,
# GITHUB_TOKEN, AWS_SECRET_ACCESS_KEY, NOTION_TOKEN, etc. A process that's
# out of our trust boundary (Node + npm telemetry + Chrome crash reports)
# now sees only what it needs. Add keys here only with a documented reason.
_SUBPROCESS_ENV_KEYS = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "USER")

# Substrate-audit gates (Anya #3, 2026-04-21). Audit mode writes network
# captures + console dumps + snapshots to disk — PII-adjacent by construction.
# Five of Anya's seven mitigations retained: --confirm-substrate-audit flag,
# stdin y/N gate, same-origin net filter, console entropy redaction, retention
# cleanup, 0o600/0o700 file perms.
# Sixth (SAFE_AUDIT_URL_ALLOWLIST) dropped by Principal 2026-04-22 — tool
# must remain generalizable; explicit flag + stdin prompt judged sufficient.
# Decision logged in security-review-log.md for Anya's re-pass.
SUBSTRATE_AUDIT_RETENTION_SECONDS = 7 * 24 * 3600  # one calendar week

# MCP call timeout (seconds). Generous on first read; tighten if session
# stalls become a pattern.
MCP_CALL_TIMEOUT = 60.0


# ─── Errors ─────────────────────────────────────────────────────────────────

class FlowRefusedError(ValueError):
    """Raised when a flow script fails the refuse-to-run gate.
    Error message identifies the first failed assertion; caller prints verbatim.
    """


class AuditRefusedError(ValueError):
    """Raised when audit-mode prerequisites fail (missing confirm flag, user
    declines the stdin prompt).
    """


# ─── Entropy scanner (Anya #10, honesty-critical) ───────────────────────────

def _shannon_entropy(s: str) -> float:
    """Shannon entropy in bits/char. 0 for empty / single-char strings.
    Used to flag token-shaped strings (base64, hex, random secrets) in flow
    scripts and console output — not a cryptographic test, a smell test.
    """
    if not s or len(s) < 2:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _is_high_entropy(s: str) -> bool:
    """Practical predicate: long enough to be a secret, dense enough to be one."""
    return len(s) >= MIN_HIGH_ENTROPY_LEN and _shannon_entropy(s) >= HIGH_ENTROPY_THRESHOLD


def _matches_token_shape(s: str) -> str | None:
    """Return the name of the first TOKEN_SHAPE_PATTERNS rule that matches a
    substring of `s`, or None. Closes the #10a gap where entropy alone misses
    AWS keys, GitHub PATs, JWTs, hex tokens, PEM headers, etc.
    """
    for name, pattern in TOKEN_SHAPE_PATTERNS.items():
        if pattern.search(s):
            return name
    return None


def _scan_flow_entropy(flow: dict, allow_high_entropy: bool) -> None:
    """Walk all string leaves in the flow object. Raise FlowRefusedError on
    the first leaf that either (a) has high Shannon entropy or (b) matches a
    canonical token-shape regex. Caller opts out with --allow-high-entropy.

    Rationale (Anya #10 + #10a): flow scripts are copied to
    artefacts/<run>/flow.json on every run. A dev who hard-codes a session
    token in a goal string or a URL puts it on disk and in git. Entropy
    catches random base64; the regex library catches every canonical token
    format that sits below the entropy threshold (MD5, SHA-256, AWS, GitHub,
    JWT, PEM, Slack, Google OAuth).
    """
    if allow_high_entropy:
        return

    def _walk(node, path: str) -> None:
        if isinstance(node, str):
            token_kind = _matches_token_shape(node)
            if token_kind is not None:
                raise FlowRefusedError(
                    f"flow field '{path}' matches a canonical token shape "
                    f"({token_kind}). Looks like a secret. If intentional, "
                    f"pass --allow-high-entropy; otherwise move the value to "
                    f"an env var."
                )
            last_leaf = path.rsplit(".", 1)[-1].split("[")[0]
            if last_leaf in ENTROPY_SKIP_LEAVES:
                # Free-text prose field: check each whitespace-delimited token
                # individually. Natural English words never trip the threshold;
                # a long token-shaped blob embedded in prose still does.
                for token in node.split():
                    if _is_high_entropy(token):
                        raise FlowRefusedError(
                            f"flow field '{path}' contains a high-entropy token "
                            f"inside a free-text field ('{token[:24]}…', "
                            f"{len(token)} chars). Looks like a secret embedded in "
                            f"prose. If intentional, pass --allow-high-entropy; "
                            f"otherwise remove the token."
                        )
                return
            if _is_high_entropy(node):
                raise FlowRefusedError(
                    f"flow field '{path}' contains a high-entropy string "
                    f"({len(node)} chars, entropy>={HIGH_ENTROPY_THRESHOLD} bits/char). "
                    f"Looks like a secret/token. If intentional, pass "
                    f"--allow-high-entropy; otherwise move the value to an env var."
                )
            return
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}")
            return
        if isinstance(node, list):
            for i, v in enumerate(node):
                _walk(v, f"{path}[{i}]")
            return

    _walk(flow, "<flow>")


# ─── SSRF static gate (Anya #5, honesty-critical) ───────────────────────────

def _validate_step_url(step_index: int, url: str) -> None:
    """Reject URLs that would push the browser into internal networks or
    non-http(s) schemes. First line: scheme + hostname deny-lists. Second
    line: ipaddress is_private / is_loopback / is_link_local checks to
    catch host-by-IP smuggling (e.g. 169.254.169.254 for AWS IMDS).

    Called from load_flow for navigate_page steps ONLY — other allowlisted
    tools don't take a URL at the step level.
    """
    if not isinstance(url, str) or not url.strip():
        raise FlowRefusedError(
            f"step[{step_index}] navigate_page missing/empty 'url' field"
        )

    try:
        parts = urlsplit(url)
    except ValueError as e:
        raise FlowRefusedError(
            f"step[{step_index}] navigate_page url not parseable: {e}"
        ) from e

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_URL_SCHEMES:
        raise FlowRefusedError(
            f"step[{step_index}] navigate_page scheme '{scheme}' is refused; "
            f"allowed: {sorted(ALLOWED_URL_SCHEMES)}. "
            f"file://, data://, javascript://, chrome:// all rejected by design."
        )

    host = (parts.hostname or "").lower()
    if not host:
        raise FlowRefusedError(
            f"step[{step_index}] navigate_page url has no hostname"
        )

    if host in BLOCKED_HOSTNAMES:
        raise FlowRefusedError(
            f"step[{step_index}] navigate_page host '{host}' is refused "
            f"(cloud-metadata or loopback endpoint)"
        )

    ip = _canonicalise_ip_host(host)
    if ip is None:
        # Not an IP literal in any parseable form. Name-based hosts don't get
        # DNS-resolved here — that would be a side-channel in a static gate.
        # Accept and let the runtime MCP call surface any network error.
        return

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        raise FlowRefusedError(
            f"step[{step_index}] navigate_page IP '{host}' (canonical {ip}) "
            f"is in a restricted range (private/loopback/link-local/reserved)"
        )


def _canonicalise_ip_host(host: str):
    """Return an ipaddress.IPv4Address / IPv6Address for any IP-shaped host,
    including the shortened / decimal / hex / octal forms that Python's strict
    `ipaddress.ip_address()` rejects but WHATWG URL (the browser) normalises.

    Anya #5a, 2026-04-22: without this, `http://127.1/`, `http://2130706433/`,
    `http://0x7f000001/`, `http://0177.0.0.1/` all slip past the strict parser
    and Chrome resolves them to 127.0.0.1. `socket.inet_aton()` accepts the
    legacy shortened forms and returns the 4-byte canonical representation;
    re-parsing that through `ipaddress` gives us the is_private / is_loopback
    predicates on the canonical form.

    Returns None if the host is not IP-shaped (a DNS name).
    """
    # Strict parse first — canonical dotted-quad and IPv6 text forms.
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass

    # IPv4 lenient parse. inet_aton accepts 127.1, 2130706433, 0x7f000001,
    # 0177.0.0.1 and similar legacy forms. Only attempt if the host looks
    # numeric-ish (digits, hex markers, dots) — avoids inet_aton accepting
    # strings like "0" (valid — becomes 0.0.0.0) when the host is clearly
    # a DNS name starting with a digit like "1password.com".
    if re.fullmatch(r"[0-9a-fA-FxX.]+", host):
        try:
            packed = socket.inet_aton(host)
            return ipaddress.IPv4Address(socket.inet_ntoa(packed))
        except OSError:
            pass

    # IPv6 lenient parse — inet_pton accepts the bracket-stripped form
    # including IPv4-mapped addresses like ::ffff:127.0.0.1.
    if ":" in host:
        try:
            packed = socket.inet_pton(socket.AF_INET6, host)
            return ipaddress.IPv6Address(packed)
        except OSError:
            pass

    return None


# ─── Flow-script loader (refuse-to-run gate, Katarina #464) ─────────────────

def load_flow(path: Path, allow_high_entropy: bool = False) -> dict:
    """Load + validate a flow script. Refuse anything missing `goal` or
    `success_state`, anything with SSRF-shaped URLs, or anything carrying
    high-entropy string leaves (unless allow_high_entropy=True).

    Raises FlowRefusedError on any validation failure. Never returns an
    invalid flow.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise FlowRefusedError(f"cannot read flow script at {path}: {e}") from e

    try:
        flow = json.loads(raw)
    except json.JSONDecodeError as e:
        raise FlowRefusedError(f"flow script is not valid JSON: {e}") from e

    if not isinstance(flow, dict):
        raise FlowRefusedError("flow script must be a JSON object at top level")

    goal = flow.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise FlowRefusedError(
            "flow missing required field 'goal' (non-empty string). "
            "A flow without a goal is a click-sequence, not a test."
        )

    success_state = flow.get("success_state")
    if not isinstance(success_state, dict):
        raise FlowRefusedError(
            "flow missing required field 'success_state' (object with url_pattern and/or landmark)"
        )
    has_url_pattern = isinstance(success_state.get("url_pattern"), str) and success_state["url_pattern"]
    has_landmark = isinstance(success_state.get("landmark"), dict) and success_state["landmark"]
    if not (has_url_pattern or has_landmark):
        raise FlowRefusedError(
            "success_state requires at least one of: url_pattern (string) or landmark (object)"
        )

    steps = flow.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise FlowRefusedError("flow missing 'steps' (non-empty list)")

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise FlowRefusedError(f"step[{i}] must be an object")
        tool = step.get("tool")
        if not isinstance(tool, str) or not tool:
            raise FlowRefusedError(f"step[{i}] missing 'tool' (string)")
        if tool in DENYLIST:
            raise FlowRefusedError(
                f"step[{i}] tool '{tool}' is in the default deny-list. "
                f"See SKILL.md 'Deny-list' for rationale."
            )
        if tool not in ALLOWLIST and tool != "emulate" and tool not in VERIFY_STEPS:
            raise FlowRefusedError(
                f"step[{i}] tool '{tool}' is not in the allowlist. "
                f"Allowed: {sorted(ALLOWLIST)} + 'emulate' + "
                f"verify-level {sorted(VERIFY_STEPS)}."
            )
        if tool == "navigate_page":
            _validate_step_url(i, step.get("url", ""))

    _scan_flow_entropy(flow, allow_high_entropy)

    return flow


# ─── Parameter-gated emulate dispatcher (Anya #1, honesty-critical) ─────────

def dispatch_emulate(
    params: dict,
    flow_allowances: dict | None = None,
) -> tuple[dict, list[str]]:
    """Gate each parameter of an `emulate` call against EMULATE_PARAM_GATES.

    Returns (accepted, rejected_reasons):
      accepted         — dict of params to forward to the MCP call (may be empty)
      rejected_reasons — human-readable list, one entry per dropped param

    Unexpected keys (not in the 6-key gate map) are rejected unconditionally,
    which defuses prototype-pollution-style injection ({"__proto__": ...}) and
    dotted-key injection ({"networkConditions.injected": ...}) at the gate.

    Caller is responsible for logging rejected_reasons to
    artefacts/<run-id>/dispatcher.log. Decoupled so the gate is unit-testable.
    """
    allowances = flow_allowances or {}
    accepted: dict = {}
    rejected: list[str] = []
    for key, value in params.items():
        gate = EMULATE_PARAM_GATES.get(key)
        if gate is None:
            rejected.append(f"unknown param '{key}' rejected unconditionally")
            continue
        if gate["default"] == "allowed":
            accepted[key] = value
            continue
        unlock_flag = gate["unlock_flag"]
        if unlock_flag and allowances.get(unlock_flag) is True:
            accepted[key] = value
        else:
            rejected.append(
                f"param '{key}' default-rejected; flow did not declare {unlock_flag}: true"
            )
    return accepted, rejected


# ─── MCP session lifecycle (async) ──────────────────────────────────────────

@asynccontextmanager
async def _mcp_session(
    extra_args: list[str] | None = None,
    errlog_path: Path | None = None,
) -> AsyncIterator[ClientSession]:
    """Open an initialized ClientSession to the CDP MCP server over stdio.

    Yields an initialized ClientSession; exits clean on context teardown.
    Replaces the pre-SDK-study start_mcp_server(cmd) -> Popen stub — the
    official mcp SDK owns the subprocess lifecycle via stdio_client, so the
    caller gets the session, not the process.

    If errlog_path is provided, the chrome-devtools-mcp subprocess's stderr
    is redirected to that file (chmod 0o600) instead of leaking past the
    wrapper's 3-line stdout cap onto the user's terminal. Server stderr
    remains available for postmortem.
    """
    cmd = build_server_command(extra_args)
    params = StdioServerParameters(
        command=cmd[0],
        args=cmd[1:],
        env=_build_subprocess_env(),
    )
    if errlog_path is not None:
        errlog_path.parent.mkdir(parents=True, exist_ok=True)
        errlog_path.parent.chmod(0o700)
        with errlog_path.open("a", encoding="utf-8") as errlog:
            errlog_path.chmod(0o600)
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
    else:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


def _build_subprocess_env() -> dict[str, str]:
    """Whitelist-only env for the chrome-devtools-mcp subprocess (Anya #11,
    2026-04-22). The Node/npx/Chrome process is out of our trust boundary;
    passing the full caller environment would leak ANTHROPIC_API_KEY,
    GITHUB_TOKEN, AWS_SECRET_ACCESS_KEY, etc. to npm telemetry / Chrome
    crash reports / any error path that serialises `process.env`.
    """
    env = {k: os.environ[k] for k in _SUBPROCESS_ENV_KEYS if k in os.environ}
    env["CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS"] = "1"
    return env


# ─── Single-step dispatcher (async) ─────────────────────────────────────────

async def dispatch_step_async(
    session: ClientSession,
    step: dict,
    flow: dict,
    dispatcher_log_lines: list[str],
):
    """Route a single flow step through allowlist + deny-list + (for emulate)
    parameter gate. Dispatch via the MCP client. Deny-list hits raise before
    any MCP call.

    Returns the raw mcp.CallToolResult — the caller decides whether to flatten
    via _result_to_dict (JSON-safe) and/or extract binaries via
    _extract_binary_blobs (screenshot bytes). Returning the raw result lets
    the runner persist BOTH the JSON view and the binary content without
    a second MCP call.

    For the `emulate` skip case (all parameters rejected), returns a plain
    dict marker rather than a CallToolResult — caller normalises both via
    _result_to_dict.
    """
    tool = step.get("tool")
    if not isinstance(tool, str):
        raise ValueError("step missing 'tool' (string)")

    # Belt-and-braces: load_flow already checked this, but dispatch_step is
    # the honesty boundary — fail closed if a malformed step slips through.
    if tool in DENYLIST:
        raise ValueError(f"tool '{tool}' is in the deny-list; refuses to dispatch")

    if tool == "emulate":
        params_in = step.get("params", {}) or {}
        allowances = flow.get("allowances", {}) or {}
        accepted, rejected = dispatch_emulate(params_in, allowances)
        for r in rejected:
            dispatcher_log_lines.append(f"emulate: {r}")
        if not accepted:
            return {"skipped": True, "reason": "all emulate params rejected"}
        result = await asyncio.wait_for(
            session.call_tool("emulate", accepted),
            timeout=MCP_CALL_TIMEOUT,
        )
        return result

    if tool not in ALLOWLIST:
        raise ValueError(
            f"tool '{tool}' is not in the allowlist; allowed: {sorted(ALLOWLIST)}"
        )

    # Per-tool dispatch — explicit, no generic pass-through (Anya #1).
    # Interactive tools (click, fill, fill_form) require a uid resolved from
    # the latest take_snapshot accessibility tree. The runner is responsible
    # for resolving the flow-script's selector dict into a uid BEFORE calling
    # this function — the step carries the resolved "uid" key on arrival.
    args: dict = {}
    if tool == "navigate_page":
        args = {"url": step["url"]}
    elif tool == "click":
        args = {"uid": step["uid"]}
    elif tool == "fill":
        args = {"uid": step["uid"], "value": step.get("value", "")}
    elif tool == "type_text":
        # chrome-devtools-mcp `type_text` types into the previously-focused
        # element — no uid on the tool itself. Chain: click uid → type_text.
        args = {"text": step.get("text", "")}
        if "submitKey" in step:
            args["submitKey"] = step["submitKey"]
    elif tool == "fill_form":
        args = {"elements": step.get("elements", [])}
    elif tool == "take_snapshot":
        args = {}
    elif tool == "list_console_messages":
        args = {}
    elif tool == "list_network_requests":
        args = {}
    elif tool == "take_screenshot":
        args = {"fullPage": bool(step.get("fullPage", False))}
    else:
        # Unreachable given the ALLOWLIST check above; fail closed.
        raise ValueError(f"no dispatch mapping for tool '{tool}'")

    result = await asyncio.wait_for(
        session.call_tool(tool, args),
        timeout=MCP_CALL_TIMEOUT,
    )
    return result


def _result_to_dict(result) -> dict:
    """Flatten an mcp CallToolResult (or pre-flattened dict) into a JSON-safe
    dict for artefact writing. Binary blob content is summarised to
    {"type": "blob", "mimeType": ..., "size": N} — the bytes themselves are
    NOT preserved here; the caller must use _extract_binary_blobs on the
    raw result for that.
    """
    if isinstance(result, dict):
        return result
    if hasattr(result, "structuredContent") and result.structuredContent:
        return dict(result.structuredContent)
    content = getattr(result, "content", None)
    if not content:
        return {"content": []}
    out = []
    for item in content:
        if hasattr(item, "text") and getattr(item, "text", None) is not None:
            out.append({"type": "text", "text": item.text})
        elif hasattr(item, "data") and getattr(item, "data", None) is not None:
            data = item.data
            size = len(data) if isinstance(data, (bytes, bytearray)) else len(str(data))
            mime = getattr(item, "mimeType", None) or "application/octet-stream"
            out.append({"type": "blob", "mimeType": mime, "size": size})
        else:
            out.append({"type": getattr(item, "type", "unknown")})
    return {"content": out}


def _extract_binary_blobs(result) -> list[tuple[str, bytes]]:
    """Pull binary content (e.g. screenshots) from an MCP CallToolResult.
    Returns a list of (mime_type, bytes) tuples — empty if no binary content
    or if the input is a pre-flattened dict (which has lost the bytes).

    Handles both raw bytes and base64-encoded strings (MCP often base64s
    binary content in JSON responses).
    """
    if isinstance(result, dict):
        return []
    out: list[tuple[str, bytes]] = []
    content = getattr(result, "content", None) or []
    for item in content:
        data = getattr(item, "data", None)
        if data is None:
            continue
        mime = getattr(item, "mimeType", None) or "application/octet-stream"
        if isinstance(data, (bytes, bytearray)):
            out.append((mime, bytes(data)))
            continue
        if isinstance(data, str):
            try:
                import base64
                out.append((mime, base64.b64decode(data, validate=True)))
            except Exception:
                continue
    return out


def _ext_for_mime(mime: str) -> str:
    """Map MIME types to file extensions for binary persistence."""
    if mime == "image/png":
        return ".png"
    if mime == "image/jpeg":
        return ".jpg"
    if mime == "image/webp":
        return ".webp"
    if mime == "application/pdf":
        return ".pdf"
    return ".bin"


# ─── Selector → uid resolver ────────────────────────────────────────────────
#
# chrome-devtools-mcp's interactive tools (click, fill, fill_form) identify
# target elements by `uid` strings (e.g. `1_80`) pulled from the most recent
# `take_snapshot` accessibility tree. The tree's textual format is:
#
#     uid=X_Y <role> "<name>" [...trailing attrs]
#
# Flow scripts authored by humans should NOT have to parse snapshots or
# hand-copy uids. They author with role+name tuples:
#
#     {"tool": "click", "selector": {"role": "button", "name": "GET MY NUMBER"}}
#     {"tool": "fill",  "selector": {"role": "textbox", "name": "your@email.com"}, "value": "..."}
#
# The runner resolves selector → uid using the latest snapshot before dispatch.
# Flow scripts may also pass a raw `uid` directly (for advanced / debugging
# cases, or when role+name aren't unique); raw uids skip the resolver.

# The accessibility tree format is `uid=X_Y <role>` followed by an OPTIONAL
# quoted name then optional trailing attributes. Most interactive nodes (link,
# button, textbox, option, heading) carry a quoted name; structural nodes
# (main, navigation, combobox) may not. Match both shapes; absent name
# resolves to empty string, and a selector with name="" matches name-less
# rows (disambiguated by role uniqueness via the multi-match guard).
_UID_LINE_RE = re.compile(
    r'^\s*uid=(?P<uid>\d+_\d+)\s+(?P<role>[A-Za-z][A-Za-z0-9_]*)(?:\s+"(?P<name>(?:[^"\\]|\\.)*)")?',
    re.MULTILINE,
)

# The RootWebArea line carries the actual current URL of the browser tab.
# Shape: `uid=X_Y RootWebArea "<title>" url="<url>"`. Used as the source of
# truth for the URL matcher, because `last_navigated_url` tracks only
# explicit `navigate_page` steps — it cannot see server-side redirects
# triggered by click / fill / fill_form (e.g. form POST → 302 redirect).
_ROOT_URL_RE = re.compile(
    r'^\s*uid=\d+_\d+\s+RootWebArea\s+"(?:[^"\\]|\\.)*"\s+url="(?P<url>[^"]*)"',
    re.MULTILINE,
)


def _current_url_from_snapshot(snapshot_text: str) -> str | None:
    """Extract the current browser URL from a snapshot's RootWebArea line.
    Returns None if the snapshot is empty or has no RootWebArea (e.g. the
    snapshot was taken before the first navigate — chrome-devtools-mcp's
    initial blank tab has no RootWebArea).
    """
    if not snapshot_text:
        return None
    m = _ROOT_URL_RE.search(snapshot_text)
    return m.group("url") if m else None


def _snapshot_to_text(snapshot_result) -> str:
    """Extract the concatenated text from a snapshot CallToolResult or its
    flattened dict form. chrome-devtools-mcp returns the accessibility tree
    as one or more text content items inside `content[].text`.
    """
    if snapshot_result is None:
        return ""
    if isinstance(snapshot_result, dict):
        content = snapshot_result.get("content") or []
        return "\n".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    content = getattr(snapshot_result, "content", None) or []
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts)


def _resolve_selector_to_uid(selector, snapshot_text: str) -> str:
    """Resolve a {role, name} selector against the accessibility tree text.

    Returns the uid string (e.g. "1_80") of the FIRST line matching both role
    AND name exactly. Raises FlowRefusedError on zero matches, on multiple
    matches (ambiguity), or on an empty snapshot.

    Ambiguity-is-a-finding: if two elements share role+name (e.g. two buttons
    both labelled "Submit"), the flow script must disambiguate by passing the
    raw `uid` key instead of `selector`. Silent first-match would let a UI
    change route a click to the wrong element without notice.
    """
    if not isinstance(selector, dict):
        raise FlowRefusedError(
            f"selector must be a dict with 'role' and 'name' keys; got {type(selector).__name__}"
        )
    role = selector.get("role")
    name = selector.get("name")
    if not isinstance(role, str) or not isinstance(name, str):
        raise FlowRefusedError(
            f"selector requires string 'role' and 'name'; got role={role!r} name={name!r}"
        )
    if not snapshot_text.strip():
        raise FlowRefusedError(
            "no snapshot available for selector resolution; ensure a take_snapshot step "
            "runs before any interactive step (click / fill / fill_form)"
        )
    # An absent quoted name in the snapshot line resolves to None via the
    # optional capture group; normalise to "" so a selector with name=""
    # matches name-less rows cleanly.
    matches = [
        m.group("uid") for m in _UID_LINE_RE.finditer(snapshot_text)
        if m.group("role") == role and (m.group("name") or "") == name
    ]
    if not matches:
        raise FlowRefusedError(
            f"selector role={role!r} name={name!r} not found in latest snapshot; "
            f"check the accessibility tree in the last step-NN-take_snapshot.json"
        )
    if len(matches) > 1:
        raise FlowRefusedError(
            f"selector role={role!r} name={name!r} matched {len(matches)} elements "
            f"(uids: {matches}); disambiguate by passing a raw 'uid' key instead"
        )
    return matches[0]


_INTERACTIVE_TOOLS_NEEDING_UID = frozenset({"click", "fill"})


def _apply_selector_resolution(step: dict, snapshot_text: str) -> dict:
    """Return a copy of `step` with selector dicts resolved to uid strings for
    interactive tools. No-op for non-interactive tools or already-resolved
    steps. Raises FlowRefusedError on resolution failure.
    """
    tool = step.get("tool")
    if tool == "fill_form":
        # elements: [{uid|selector, value}, ...] — resolve each element that
        # carries a selector instead of a raw uid.
        elements_in = step.get("elements", []) or []
        resolved_elements = []
        for idx, el in enumerate(elements_in):
            if not isinstance(el, dict):
                raise FlowRefusedError(
                    f"fill_form elements[{idx}] must be a dict; got {type(el).__name__}"
                )
            if "uid" in el:
                resolved_elements.append({"uid": el["uid"], "value": el.get("value", "")})
                continue
            if "selector" not in el:
                raise FlowRefusedError(
                    f"fill_form elements[{idx}] missing both 'uid' and 'selector'"
                )
            uid = _resolve_selector_to_uid(el["selector"], snapshot_text)
            resolved_elements.append({"uid": uid, "value": el.get("value", "")})
        return {**step, "elements": resolved_elements}
    if tool in _INTERACTIVE_TOOLS_NEEDING_UID:
        if "uid" in step:
            return step
        if "selector" not in step:
            raise FlowRefusedError(
                f"{tool} step missing both 'uid' and 'selector'"
            )
        uid = _resolve_selector_to_uid(step["selector"], snapshot_text)
        return {**step, "uid": uid}
    return step


# ─── Flow runner (sync wrapper + async impl) ────────────────────────────────

def run_flow(flow: dict, run_id: str, allow_high_entropy: bool = False) -> dict:
    """Execute a validated flow against a live URL, write artefacts, return
    the verdict dict with pass/fail + which success_state matcher fired.
    """
    return asyncio.run(_run_flow_async(flow, run_id, allow_high_entropy))


async def _run_flow_async(flow: dict, run_id: str, allow_high_entropy: bool) -> dict:
    run_dir = ensure_artefacts_dir(run_id)
    write_artefact_json(run_dir, "flow.json", flow)
    server_errlog = run_dir / "server-stderr.log"

    dispatcher_log: list[str] = []
    steps = flow["steps"]
    steps_completed = 0
    last_navigated_url: str | None = None
    snapshot_result: dict | None = None
    final_error: str | None = None
    step_durations_ms: list[int | None] = []
    run_start = time.perf_counter()

    # Latest accessibility-tree text for selector → uid resolution. Updated
    # after every take_snapshot; stale after interactive steps that mutate
    # the DOM (click / fill / fill_form / navigate_page). Runner auto-takes
    # a snapshot before an interactive step if the latest tree is stale.
    last_snapshot_text: str = ""
    snapshot_fresh: bool = False

    try:
        async with _mcp_session(errlog_path=server_errlog) as session:
            for i, step in enumerate(steps):
                tool = step.get("tool")
                step_start = time.perf_counter()

                # Verify-level step: wait_for_url_change. Poll take_snapshot
                # until the RootWebArea URL differs from the pre-step URL, or
                # the timeout expires. Written as a synthetic step artefact.
                if tool == "wait_for_url_change":
                    timeout_ms = int(step.get("timeout_ms", 3000))
                    poll_ms = int(step.get("poll_interval_ms", 200))
                    initial_url = last_navigated_url
                    polls = 0
                    changed = False
                    final_url = initial_url
                    wait_start = time.perf_counter()
                    while (time.perf_counter() - wait_start) * 1000 < timeout_ms:
                        polls += 1
                        try:
                            snap = await asyncio.wait_for(
                                session.call_tool("take_snapshot", {}),
                                timeout=MCP_CALL_TIMEOUT,
                            )
                        except Exception as e:  # noqa: BLE001
                            final_error = f"step[{i}] wait_for_url_change: poll failed: {type(e).__name__}: {e}"
                            dispatcher_log.append(final_error)
                            break
                        snap_text = _snapshot_to_text(snap)
                        snap_url = _current_url_from_snapshot(snap_text)
                        if snap_url and snap_url != initial_url:
                            final_url = snap_url
                            changed = True
                            last_snapshot_text = snap_text
                            last_navigated_url = snap_url
                            snapshot_fresh = True
                            break
                        await asyncio.sleep(poll_ms / 1000.0)
                    if final_error is not None:
                        break
                    elapsed_ms = int((time.perf_counter() - wait_start) * 1000)
                    steps_completed += 1
                    step_label = f"step-{i + 1:02d}-{tool}"
                    write_artefact_json(run_dir, f"{step_label}.json", {
                        "initial_url": initial_url,
                        "final_url": final_url,
                        "changed": changed,
                        "elapsed_ms": elapsed_ms,
                        "polls": polls,
                        "timeout_ms": timeout_ms,
                    })
                    step_durations_ms.append(int((time.perf_counter() - step_start) * 1000))
                    continue

                # Interactive tools need a uid — resolve from the latest
                # snapshot. If no fresh snapshot is available, auto-take one
                # so the flow-script author doesn't have to interleave manual
                # take_snapshot calls around every click/fill.
                step_for_dispatch = step
                if tool in _INTERACTIVE_TOOLS_NEEDING_UID or tool == "fill_form":
                    needs_resolve = (
                        ("selector" in step and "uid" not in step)
                        or (tool == "fill_form" and any(
                            isinstance(el, dict) and "selector" in el and "uid" not in el
                            for el in (step.get("elements") or [])
                        ))
                    )
                    if needs_resolve and not snapshot_fresh:
                        try:
                            auto_snap = await asyncio.wait_for(
                                session.call_tool("take_snapshot", {}),
                                timeout=MCP_CALL_TIMEOUT,
                            )
                        except Exception as e:  # noqa: BLE001
                            final_error = (
                                f"step[{i}] {tool}: auto-snapshot for uid resolution failed: "
                                f"{type(e).__name__}: {e}"
                            )
                            dispatcher_log.append(final_error)
                            break
                        last_snapshot_text = _snapshot_to_text(auto_snap)
                        snapshot_fresh = True
                        # Refresh URL tracker from the auto-snapshot too —
                        # a server-side redirect (e.g. form POST→302) from
                        # the previous interactive step is visible here.
                        auto_url = _current_url_from_snapshot(last_snapshot_text)
                        if auto_url:
                            last_navigated_url = auto_url
                    if needs_resolve:
                        try:
                            step_for_dispatch = _apply_selector_resolution(step, last_snapshot_text)
                        except FlowRefusedError as e:
                            final_error = f"step[{i}] {tool}: {type(e).__name__}: {e}"
                            dispatcher_log.append(final_error)
                            break

                try:
                    raw = await dispatch_step_async(session, step_for_dispatch, flow, dispatcher_log)
                except Exception as e:  # noqa: BLE001 — capture + flatten
                    final_error = f"step[{i}] {tool}: {type(e).__name__}: {e}"
                    dispatcher_log.append(final_error)
                    break
                steps_completed += 1
                if tool == "navigate_page":
                    last_navigated_url = step.get("url")

                # Snapshot freshness tracking. take_snapshot refreshes;
                # DOM-mutating tools stale the tree.
                if tool == "take_snapshot":
                    last_snapshot_text = _snapshot_to_text(raw)
                    snapshot_fresh = True
                    # Refresh URL tracker — a server-side redirect from the
                    # previous interactive step becomes visible here.
                    snap_url = _current_url_from_snapshot(last_snapshot_text)
                    if snap_url:
                        last_navigated_url = snap_url
                elif tool in {"click", "fill", "fill_form", "navigate_page", "type_text"}:
                    snapshot_fresh = False

                # Path C per-step persistence — every step's result lands on
                # disk so the wrapper is auditable for every step, not just
                # the final URL match. Closes the SKILL.md anti-pattern #3
                # honesty gap (a recording goes green when 6/7 frames are
                # missing). Step number is 1-indexed, zero-padded to 2 digits
                # (handles flows up to 99 steps).
                step_label = f"step-{i + 1:02d}-{tool}"
                write_artefact_json(run_dir, f"{step_label}.json", _result_to_dict(raw))
                # Binary content (screenshots) — _result_to_dict drops bytes
                # by design (JSON safety). Extract from raw and write as
                # separate files. Multi-blob results get -A / -B suffixes.
                blobs = _extract_binary_blobs(raw)
                for j, (mime, data) in enumerate(blobs):
                    suffix = "" if len(blobs) == 1 else f"-{chr(ord('a') + j)}"
                    ext = _ext_for_mime(mime)
                    write_artefact_bytes(run_dir, f"{step_label}{suffix}{ext}", data)
                step_durations_ms.append(int((time.perf_counter() - step_start) * 1000))

            # After the scripted steps, capture a snapshot for success_state
            # evaluation (landmark matcher needs it; url-pattern matcher uses
            # the last-navigated URL). Persisted as final-snapshot.json — kept
            # distinct from per-step snapshot files to avoid overlap with the
            # step-NN-take_snapshot.json pattern.
            if final_error is None:
                try:
                    snap = await asyncio.wait_for(
                        session.call_tool("take_snapshot", {}),
                        timeout=MCP_CALL_TIMEOUT,
                    )
                    snapshot_result = _result_to_dict(snap)
                    # Capture the actual current URL from the post-flow
                    # snapshot — catches redirects triggered by the final
                    # scripted step (e.g. the form submit click above).
                    final_url = _current_url_from_snapshot(_snapshot_to_text(snap))
                    if final_url:
                        last_navigated_url = final_url
                except Exception as e:  # noqa: BLE001
                    dispatcher_log.append(f"post-flow snapshot failed: {e}")
    except Exception as e:  # noqa: BLE001 — session-level failure
        final_error = f"session: {type(e).__name__}: {e}"
        dispatcher_log.append(final_error)

    # Success evaluation.
    matcher: str | None = None
    passed = False
    success_state = flow["success_state"]
    if final_error is None:
        url_pattern = success_state.get("url_pattern")
        if url_pattern and last_navigated_url and url_pattern in last_navigated_url:
            matcher = "url_pattern"
            passed = True
        else:
            landmark = success_state.get("landmark")
            if landmark and snapshot_result and _landmark_matches(landmark, snapshot_result):
                matcher = "landmark"
                passed = True

    # Write artefacts. The post-flow snapshot is named final-snapshot.json
    # (not snapshot.json) so the per-step pattern step-NN-take_snapshot.json
    # owns the unprefixed namespace cleanly.
    if snapshot_result is not None:
        write_artefact_json(run_dir, "final-snapshot.json", snapshot_result)
    if dispatcher_log:
        (run_dir / "dispatcher.log").write_text(
            "\n".join(dispatcher_log) + "\n", encoding="utf-8"
        )
        (run_dir / "dispatcher.log").chmod(0o600)

    result = {
        "run_id": run_id,
        "pass": passed,
        "matcher": matcher,
        "artefacts_dir": str(run_dir),
        "steps_completed": steps_completed,
        "steps_total": len(steps),
        "step_durations_ms": step_durations_ms,
        "duration_ms": int((time.perf_counter() - run_start) * 1000),
        "error": final_error,
    }
    write_artefact_json(run_dir, "result.json", result)
    return result


def _landmark_matches(landmark: dict, snapshot: dict) -> bool:
    """Best-guess landmark detector against an un-locked snapshot shape.
    Walks all dicts in the snapshot tree, looks for one that has `role`
    matching landmark['role'] and a name/text field matching
    `name_matches` by substring. Graceful NO on shape drift.
    """
    want_role = landmark.get("role")
    want_name = landmark.get("name_matches") or ""
    if not want_role:
        return False

    def _walk(node) -> bool:
        if isinstance(node, dict):
            role = node.get("role")
            if role == want_role:
                for field in ("name", "text", "label", "accessibleName"):
                    v = node.get(field)
                    if isinstance(v, str) and (not want_name or want_name in v):
                        return True
            for v in node.values():
                if _walk(v):
                    return True
        elif isinstance(node, list):
            for v in node:
                if _walk(v):
                    return True
        return False

    return _walk(snapshot)


# ─── Audit mode (D2 DESIGNED-IN) + Anya #3 mitigations ──────────────────────

def run_audit_mode(
    url: str,
    *,
    confirmed: bool,
    non_interactive: bool = False,
) -> Path:
    """Dump snapshot/network/console across the 3 audit viewports to
    artefacts/substrate-audit/YYYY-MM-DD/<viewport>-*.json.

    Six Anya #3 mitigations retained (seventh — URL allowlist — dropped by
    Principal 2026-04-22 for generalizability):
      1. --confirm-substrate-audit flag required (enforced by caller; this
         function rejects confirmed=False with AuditRefusedError).
      2. Interactive stdin y/N gate (unless non_interactive=True for tests).
      3. File perms 0o600 / dir perms 0o700 (via ensure_artefacts_dir +
         write_artefact_json writers).
      4. list_network_requests output filtered to same-origin-as-url only
         (strips auth-cookie replays from redirect chains / embedded resources).
      5. Console messages matching high-entropy pattern are redacted in-place.
      6. Retention sweep: rm -rf artefacts/substrate-audit/<dir> older than
         SUBSTRATE_AUDIT_RETENTION_SECONDS (one calendar week).
    """
    if not confirmed:
        raise AuditRefusedError(
            "--audit-mode requires --confirm-substrate-audit. "
            "Audit mode writes snapshot/network/console JSON to disk; "
            "PII, tokens, and secrets on the target URL land on disk."
        )

    # Anya #3a, 2026-04-22: audit-mode skips load_flow, so the SSRF gate
    # that normally fires per-navigate_page step has to be applied here too.
    # Without this, `--audit-mode file:///etc/passwd --confirm-substrate-audit`
    # → `y` would ship /etc/passwd to disk. Run before the stdin prompt so
    # bad URLs fail fast, not after the user has already typed `y`.
    try:
        _validate_step_url(-1, url)
    except FlowRefusedError as e:
        raise AuditRefusedError(f"audit URL refused: {e}") from e

    if not non_interactive:
        sys.stderr.write(
            "This writes network.json, console.json, snapshot.json to disk.\n"
            "PII / tokens / secrets on the target URL land on disk. y/N required: "
        )
        sys.stderr.flush()
        reply = sys.stdin.readline().strip().lower()
        if reply != "y":
            raise AuditRefusedError("audit declined at stdin prompt")

    _cleanup_audit_retention()
    return asyncio.run(_run_audit_mode_async(url))


def _cleanup_audit_retention() -> None:
    """Hard-delete substrate-audit/<dir> older than the retention threshold."""
    if not SUBSTRATE_AUDIT_ROOT.exists():
        return
    cutoff = time.time() - SUBSTRATE_AUDIT_RETENTION_SECONDS
    for child in SUBSTRATE_AUDIT_ROOT.iterdir():
        if not child.is_dir():
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            shutil.rmtree(child, ignore_errors=True)


async def _run_audit_mode_async(url: str) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dump_root = SUBSTRATE_AUDIT_ROOT / today
    dump_root.mkdir(parents=True, exist_ok=True)
    dump_root.chmod(0o700)

    for label, w, h in AUDIT_VIEWPORTS:
        viewport_errlog = dump_root / f"server-stderr-{label}.log"
        async with _mcp_session(errlog_path=viewport_errlog) as session:
            # Apply viewport via emulate (both networkConditions + viewport
            # are in the default-allowed gate).
            await asyncio.wait_for(
                session.call_tool("emulate", {"viewport": {"width": w, "height": h}}),
                timeout=MCP_CALL_TIMEOUT,
            )
            await asyncio.wait_for(
                session.call_tool("navigate_page", {"url": url}),
                timeout=MCP_CALL_TIMEOUT,
            )
            await asyncio.sleep(2)  # let the page settle

            snap = _result_to_dict(
                await asyncio.wait_for(
                    session.call_tool("take_snapshot", {}),
                    timeout=MCP_CALL_TIMEOUT,
                )
            )
            net = _result_to_dict(
                await asyncio.wait_for(
                    session.call_tool("list_network_requests", {}),
                    timeout=MCP_CALL_TIMEOUT,
                )
            )
            console = _result_to_dict(
                await asyncio.wait_for(
                    session.call_tool("list_console_messages", {}),
                    timeout=MCP_CALL_TIMEOUT,
                )
            )

        net_filtered = _filter_same_origin_network(net, url)
        console_redacted = _redact_console_entropy(console)

        write_artefact_json(dump_root, f"{label}-snapshot.json", snap)
        write_artefact_json(dump_root, f"{label}-network.json", net_filtered)
        write_artefact_json(dump_root, f"{label}-console.json", console_redacted)

    return dump_root


def _same_origin(a: str, b: str) -> bool:
    try:
        pa, pb = urlsplit(a), urlsplit(b)
    except ValueError:
        return False
    return (
        (pa.scheme or "").lower() == (pb.scheme or "").lower()
        and (pa.hostname or "").lower() == (pb.hostname or "").lower()
    )


def _filter_same_origin_network(net: dict, origin_url: str) -> dict:
    """Drop requests whose URL origin differs from origin_url. Walks dicts /
    lists to find anything that looks like a request record with a URL field.
    Conservative: retained on no-url-found (shape may drift; we'd rather
    over-retain the dump-mode payload than strip it to nothing)."""
    def _retain(node) -> bool:
        if isinstance(node, dict):
            for field in ("url", "requestUrl", "documentURL"):
                v = node.get(field)
                if isinstance(v, str):
                    return _same_origin(v, origin_url)
        return True

    def _walk(node):
        if isinstance(node, list):
            return [_walk(v) for v in node if _retain(v)]
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        return node

    return _walk(net)


def _redact_console_entropy(console: dict) -> dict:
    """Replace high-entropy substrings in console message text with a
    stable placeholder. Reuses _is_high_entropy; scanning by whitespace
    token keeps natural-language text readable while scrubbing obvious
    tokens / bearer strings."""
    def _redact_str(s: str) -> str:
        if not s:
            return s
        parts = re.split(r"(\s+)", s)
        return "".join(
            "[REDACTED-HIGH-ENTROPY]" if (p and not p.isspace() and _is_high_entropy(p)) else p
            for p in parts
        )

    def _walk(node):
        if isinstance(node, str):
            return _redact_str(node)
        if isinstance(node, list):
            return [_walk(v) for v in node]
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        return node

    return _walk(console)


# ─── Artefacts writer + 3-line output ceiling ───────────────────────────────

def new_run_id() -> str:
    """UTC ISO timestamp, safe for filesystem."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_artefacts_dir(run_id: str, root: Path | None = None) -> Path:
    """Create <root>/<run_id>/ (and the root if missing) and return it.
    Root defaults to ARTEFACTS_ROOT; overridable for tests.

    Dir is chmod'd to 0o700 — artefacts may contain network captures, console
    messages, or snapshots with session-scoped PII. Anya #4a, 2026-04-21.
    """
    base = root if root is not None else ARTEFACTS_ROOT
    d = base / run_id
    d.mkdir(parents=True, exist_ok=True)
    d.chmod(0o700)
    return d


def viewport_subdir(run_dir: Path, label: str) -> Path:
    """Return <run_dir>/viewport-<label>/, creating it if missing.
    Label is sanitised — only alphanumerics, dash, underscore. Anything else
    is stripped. Keeps filesystem-safe names even if a flow script passes
    adversarial input.
    """
    safe = "".join(c for c in label if c.isalnum() or c in "-_")
    if not safe:
        safe = "unknown"
    d = run_dir / f"viewport-{safe}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_artefact_json(dest_dir: Path, name: str, data) -> Path:
    """Write JSON data to <dest_dir>/<name>. Returns the written path.
    JSON is pretty-printed (indent=2) for diff-ability in git.

    File is chmod'd 0o600 and parent dir 0o700 (Anya #4a, 2026-04-21) —
    artefacts can contain network captures / console messages / screenshots
    with session-scoped PII.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.chmod(0o700)
    path = dest_dir / name
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    path.chmod(0o600)
    return path


def write_artefact_bytes(dest_dir: Path, name: str, data: bytes) -> Path:
    """Write binary data (e.g. PNG screenshot) to <dest_dir>/<name>.

    File is chmod'd 0o600 and parent dir 0o700 (Anya #4a, 2026-04-21).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.chmod(0o700)
    path = dest_dir / name
    path.write_bytes(data)
    path.chmod(0o600)
    return path


def emit_verdict(result: dict) -> None:
    """3-line stdout ceiling (anti-pattern #3 enforcement).
    Line 1: PASS or FAIL + matcher name.
    Line 2: steps-completed / steps-total.
    Line 3: artefacts directory path.

    Each line is flattened to a single physical line (embedded newlines /
    carriage returns stripped) to prevent a misbehaving matcher name or
    artefact path from smuggling a 4th line onto stdout.
    """
    lines = [
        f"{'PASS' if result.get('pass') else 'FAIL'} via {result.get('matcher') or 'none'}",
        f"Steps: {result.get('steps_completed', 0)}/{result.get('steps_total', 0)}",
        f"Artefacts: {result.get('artefacts_dir', '(none)')}",
    ]
    for line in lines[:MAX_STDOUT_LINES]:
        flat = line.replace("\r", " ").replace("\n", " ")
        print(flat)


# ─── Server command + install check ─────────────────────────────────────────

def build_server_command(extra_args: list[str] | None = None) -> list[str]:
    """Assemble the npx invocation with forced flags appended.
    Validates that no REFUSED_SERVER_FLAGS appear in extra_args.

    Accepts both bare (``--user-data-dir``) and equals (``--user-data-dir=/x``)
    forms by splitting on ``=`` before the set membership test.
    """
    extra = extra_args or []
    for a in extra:
        flag_name = a.split("=", 1)[0]
        if flag_name in REFUSED_SERVER_FLAGS:
            raise ValueError(
                f"Refused server-start flag: {a}. "
                f"See SKILL.md 'Refused server-start flags' for rationale."
            )
    return MCP_LAUNCH_CMD + FORCED_SERVER_FLAGS + extra


def check_install() -> int:
    """Verify `npx chrome-devtools-mcp@latest --help` succeeds within 30s
    AND the mcp Python SDK is at the pinned version.
    Returns 0 on success, 1 on failure. Prints one-line status.
    """
    installed_sdk = _installed_mcp_version()
    if installed_sdk != MCP_SDK_VERSION:
        print(
            f"FAIL: mcp SDK version drift (installed {installed_sdk}, "
            f"expected {MCP_SDK_VERSION}). Run install.sh."
        )
        return 1
    try:
        r = subprocess.run(
            MCP_LAUNCH_CMD + ["--help"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        print("FAIL: npx not on PATH — install Node.js first.")
        return 1
    except subprocess.TimeoutExpired:
        print("FAIL: npx fetch timed out at 30s — check network + npm cache.")
        return 1
    if r.returncode == 0:
        print(f"OK: {MCP_PACKAGE} reachable via npx; mcp SDK {MCP_SDK_VERSION} pinned.")
        return 0
    print(f"FAIL: npx {MCP_PACKAGE} exited {r.returncode}. Stderr: {r.stderr[:200].strip()}")
    return 1


# ─── List allowlist (diagnostic) ────────────────────────────────────────────

def list_allowlist() -> None:
    """Print allowlist + deny-list + emulate parameter gates + audit gates."""
    print(f"Allowlist ({len(ALLOWLIST)} tools):")
    for t in sorted(ALLOWLIST):
        print(f"  + {t}")
    print()
    print(f"Deny-list ({len(DENYLIST)} tools at default load):")
    for t in sorted(DENYLIST):
        print(f"  - {t}")
    print()
    print(f"Flag-gated tools ({len(FLAG_GATED_TOOLS)}):")
    for t, flag in FLAG_GATED_TOOLS.items():
        print(f"  ? {t}  (only loaded under {flag} — refused)")
    print()
    print("Emulate parameter gates:")
    for param, gate in EMULATE_PARAM_GATES.items():
        unlock = gate["unlock_flag"] or "(always allowed)"
        print(f"  {param:20s} default={gate['default']:10s} unlock={unlock}")
    print()
    print(f"Forced server flags:  {' '.join(FORCED_SERVER_FLAGS)}")
    print(f"Refused server flags: {' '.join(sorted(REFUSED_SERVER_FLAGS))}")
    print()
    print(f"URL schemes allowed in navigate_page: {sorted(ALLOWED_URL_SCHEMES)}")
    print(f"Hostnames blocked in navigate_page:   {sorted(BLOCKED_HOSTNAMES)}")
    print()
    print(f"Audit-mode retention:   {SUBSTRATE_AUDIT_RETENTION_SECONDS}s")
    print(f"Flow-entropy threshold: ≥{HIGH_ENTROPY_THRESHOLD} bits/char on strings ≥{MIN_HIGH_ENTROPY_LEN} chars")


# ─── main() ─────────────────────────────────────────────────────────────────

def main() -> int:
    # Backward compat: `verify.py <flow.json>` (no subcommand) still works.
    # If argv[1] doesn't match a known subcommand or top-level flag, treat
    # it as a flow path and inject `flow` for the parser. Subcommands are
    # `flow` (default) and `journey` (v0.3 LLM-in-loop runner).
    KNOWN_SUBCMDS = {"flow", "journey", "journey-suite", "journey-diff", "suite-diff", "expand"}
    TOP_LEVEL_FLAGS = {
        "--audit-mode", "--list-allowlist", "--check-install",
        "-h", "--help",
    }
    argv = list(sys.argv[1:])
    if argv and argv[0] not in KNOWN_SUBCMDS and not any(
        argv[0] == f or argv[0].startswith(f + "=") for f in TOP_LEVEL_FLAGS
    ):
        argv = ["flow"] + argv

    ap = argparse.ArgumentParser(
        prog="verify.py",
        description="Run a scripted flow or journey against a live URL via Chrome DevTools MCP.",
    )
    ap.add_argument("--audit-mode", metavar="URL", default=None,
                    help="Dump substrate shape (snapshot/network/console × 3 viewports) and exit.")
    ap.add_argument("--confirm-substrate-audit", action="store_true",
                    help="Required to run --audit-mode (PII-gate).")
    ap.add_argument("--list-allowlist", action="store_true",
                    help="Print allowlist + deny-list + parameter gates and exit.")
    ap.add_argument("--check-install", action="store_true",
                    help="Verify chrome-devtools-mcp is reachable via npx and exit.")

    sub = ap.add_subparsers(dest="cmd", required=False)

    flow_p = sub.add_parser("flow", help="Run a flow-script JSON file (default).")
    flow_p.add_argument("flow", nargs="?", default=None,
                        help="Path to a flow-script JSON file.")
    flow_p.add_argument("--allow-high-entropy", action="store_true",
                        help="Bypass the flow-script entropy scanner.")
    flow_p.add_argument("--no-report", action="store_false", dest="report",
                        help="Skip report.html + index.html regeneration after the run.")
    flow_p.add_argument("--no-index", action="store_false", dest="index",
                        help="Skip index.html regeneration.")
    flow_p.set_defaults(report=True, index=True)

    j_p = sub.add_parser("journey", help="Run a journey JSON file (v0.3 LLM-in-loop).")
    j_p.add_argument("journey", help="Path to a journey JSON file.")
    j_p.add_argument("--allow-high-entropy", action="store_true",
                     help="Bypass the journey entropy scanner.")
    j_p.add_argument("--no-report", action="store_false", dest="report",
                     help="Skip report.html + index.html regeneration after the run.")
    j_p.add_argument("--no-index", action="store_false", dest="index",
                     help="Skip index.html regeneration.")
    j_p.set_defaults(report=True, index=True)

    s_p = sub.add_parser(
        "journey-suite",
        help="Run a site.yaml — N journeys × shared target sequentially (v1.0 J5).",
    )
    s_p.add_argument("suite", help="Path to a site.yaml file.")
    s_p.add_argument("--allow-high-entropy", action="store_true",
                     help="Bypass the per-journey entropy scanner.")
    s_p.add_argument("--no-report", action="store_false", dest="report",
                     help="Skip per-journey report.html regeneration after the run.")
    s_p.add_argument("--no-index", action="store_false", dest="index",
                     help="Skip top-level index.html regeneration.")
    s_p.set_defaults(report=True, index=True)

    d_p = sub.add_parser(
        "journey-diff",
        help="Diff two single-journey runs step-by-step (v1.0 P3 regression alerts).",
    )
    d_p.add_argument("run_a", help="Path to the first journey run dir (baseline).")
    d_p.add_argument("run_b", help="Path to the second journey run dir (candidate).")
    d_p.add_argument("--out", default=None, metavar="PATH",
                     help="Output dir for diff-result.json + diff.html. Default: artefacts/diff-<A>-vs-<B>/.")
    d_p.add_argument("--no-report", action="store_false", dest="report",
                     help="Skip diff.html generation (only emit diff-result.json).")
    d_p.add_argument("--no-index", action="store_false", dest="index",
                     help="Skip top-level index.html regeneration.")
    d_p.set_defaults(report=True, index=True)

    sd_p = sub.add_parser(
        "suite-diff",
        help="Diff every (file × persona) cell across viewports in a P7 suite run.",
    )
    sd_p.add_argument("suite_dir", help="Path to a suite-<id>/ artefacts directory.")
    sd_p.add_argument("--baseline", default=None, metavar="VIEWPORT",
                      help="Baseline viewport label (default: first viewport in site.yaml order).")
    sd_p.add_argument("--no-index", action="store_false", dest="index",
                      help="Skip top-level index.html regeneration.")
    sd_p.set_defaults(index=True)

    e_p = sub.add_parser("expand", help="Expand prose into a journey JSON via LLM (v1.0 P1).")
    e_p.add_argument("prose", nargs="?", default=None,
                     help="Natural-language description of the journey. Use - to read from stdin.")
    e_p.add_argument("--target", required=True, metavar="URL",
                     help="Target URL for the journey.")
    e_p.add_argument("--out", default=None, metavar="PATH",
                     help="Output path for the expanded journey JSON. Default: journeys/expanded-<slug>.json.")
    e_p.add_argument("--persona-hint", default=None, metavar="ID",
                     help="Suggested persona id (fresh|returning|engaged|authenticated). LLM may override if prose contradicts.")
    e_p.add_argument("--run", action="store_true",
                     help="After successful expand, immediately run the journey.")

    args = ap.parse_args(argv)

    if args.list_allowlist:
        list_allowlist()
        return 0
    if args.check_install:
        return check_install()

    if args.audit_mode:
        try:
            out = run_audit_mode(args.audit_mode, confirmed=args.confirm_substrate_audit)
            print(f"Audit dump: {out}")
            return 0
        except AuditRefusedError as e:
            print(f"Audit refused: {e}", file=sys.stderr)
            return 3

    if args.cmd == "journey":
        return _main_journey(args)
    if args.cmd == "journey-suite":
        return _main_journey_suite(args)
    if args.cmd == "journey-diff":
        return _main_journey_diff(args)
    if args.cmd == "suite-diff":
        return _main_suite_diff(args)
    if args.cmd == "expand":
        return _main_expand(args)

    # Default / explicit `flow` subcommand path.
    if not getattr(args, "flow", None):
        ap.print_help()
        return 1

    flow_path = Path(args.flow)
    if not flow_path.exists():
        print(f"Flow script not found: {flow_path}", file=sys.stderr)
        return 1

    try:
        flow = load_flow(flow_path, allow_high_entropy=args.allow_high_entropy)
    except FlowRefusedError as e:
        print(f"Flow refused: {e}", file=sys.stderr)
        return 1

    run_id = new_run_id()
    result = run_flow(flow, run_id, allow_high_entropy=args.allow_high_entropy)
    emit_verdict(result)
    if args.report:
        _emit_reports(result, include_index=args.index)
    return 0 if result.get("pass") else 1


def _main_journey(args) -> int:
    from journeys.loader import load_journey, JourneyRefusedError
    from journeys.runner import run_journey

    journey_path = Path(args.journey)
    if not journey_path.exists():
        print(f"Journey not found: {journey_path}", file=sys.stderr)
        return 1
    try:
        journey = load_journey(journey_path, allow_high_entropy=args.allow_high_entropy)
    except JourneyRefusedError as e:
        print(f"Journey refused: {e}", file=sys.stderr)
        return 1

    result = run_journey(journey)
    verdict = result.get("verdict", "FAIL" if not result.get("pass") else "PASS")
    print(
        f"Journey {verdict}: matcher={result.get('matcher')!r} "
        f"iters={result.get('iterations')} clicks={result.get('clicks_used')} "
        f"dead_ends={result.get('dead_ends')} duration_ms={result.get('duration_ms')}"
    )
    if result.get("error"):
        print(f"  error: {result['error']}", file=sys.stderr)
    print(f"  artefacts: {result.get('artefacts_dir')}")
    if args.report:
        _emit_reports(result, include_index=args.index)
    return 0 if result.get("pass") else 1


def _main_journey_suite(args) -> int:
    from journeys.suite import load_suite, run_suite, SuiteRefusedError

    suite_path = Path(args.suite)
    if not suite_path.exists():
        print(f"Suite not found: {suite_path}", file=sys.stderr)
        return 1
    try:
        suite = load_suite(suite_path, allow_high_entropy=args.allow_high_entropy)
    except SuiteRefusedError as e:
        print(f"Suite refused: {e}", file=sys.stderr)
        return 1

    result = run_suite(suite)
    summary = result["verdict_summary"]
    label = result["site"].get("label") or result["site"]["target"]
    print(
        f"Suite {label}: PASS={summary.get('PASS', 0)} "
        f"UNCLEAR={summary.get('UNCLEAR', 0)} FAIL={summary.get('FAIL', 0)} "
        f"duration_ms={result['duration_ms']}"
    )
    for row in result["journeys"]:
        print(
            f"  • {row['file']} [{row['persona']}] → {row['verdict']} "
            f"(matcher={row.get('matcher')!r}, iters={row.get('iterations')}, "
            f"duration_ms={row.get('duration_ms')})"
        )
        if row.get("error"):
            print(f"    error: {row['error']}", file=sys.stderr)
    print(f"  artefacts: {result.get('artefacts_dir')}")

    if args.report:
        # Emit per-journey reports + one top-level index over the whole
        # ARTEFACTS_ROOT (so the user sees both the suite dir and any
        # prior run dirs in one navigable index).
        for row in result["journeys"]:
            _emit_reports(row, include_index=False)
        if args.index:
            try:
                from reader.index import generate as generate_index
                index_path = generate_index(ARTEFACTS_ROOT)
                print(f"Index:  {index_path}")
            except Exception as e:
                print(f"[reader] index generation failed: {e}", file=sys.stderr)

    # Suite passes only if every journey passed.
    return 0 if summary.get("FAIL", 0) == 0 and summary.get("UNCLEAR", 0) == 0 else 1


def _main_journey_diff(args) -> int:
    from journeys.diff import (
        DiffError,
        default_out_dir,
        diff_runs,
        write_diff,
    )

    run_a = Path(args.run_a)
    run_b = Path(args.run_b)
    for label, p in (("run_a", run_a), ("run_b", run_b)):
        if not p.is_dir():
            print(f"journey-diff: {label} is not a directory: {p}", file=sys.stderr)
            return 1

    try:
        payload = diff_runs(run_a, run_b)
    except DiffError as e:
        print(f"journey-diff failed: {e}", file=sys.stderr)
        return 1

    if args.out:
        out_dir = Path(args.out)
    else:
        out_dir = default_out_dir(
            ARTEFACTS_ROOT,
            payload["run_a"]["run_id"] or run_a.name,
            payload["run_b"]["run_id"] or run_b.name,
        )

    diff_path = write_diff(payload, out_dir)

    fd = payload.get("first_divergence") or {}
    kind = fd.get("kind") or "none"
    idx = fd.get("step_index")
    n_added = len((payload.get("findings_diff") or {}).get("added") or [])
    n_removed = len((payload.get("findings_diff") or {}).get("removed") or [])
    print(
        f"Diff {payload['run_a']['run_id']} → {payload['run_b']['run_id']}: "
        f"first_divergence={kind}"
        + (f" @step {idx}" if idx else "")
        + (f", verdict {payload['run_a']['verdict']}→{payload['run_b']['verdict']}"
           if payload.get("verdict_changed") else "")
        + (f", findings +{n_added}/-{n_removed}" if (n_added or n_removed) else "")
    )
    print(f"  diff-result: {diff_path}")

    if args.report:
        try:
            from reader.diff_report import generate as generate_diff_html
            html_path = generate_diff_html(out_dir)
            print(f"  diff.html:   {html_path}")
        except Exception as e:
            print(f"[reader] diff render failed: {e}", file=sys.stderr)
        if args.index:
            try:
                from reader.index import generate as generate_index
                index_path = generate_index(ARTEFACTS_ROOT)
                print(f"  Index:       {index_path}")
            except Exception as e:
                print(f"[reader] index generation failed: {e}", file=sys.stderr)

    # Exit code: 0 if sequences match exactly AND verdicts match; otherwise 1.
    if kind == "none" and not payload.get("verdict_changed") and not payload.get("matcher_changed"):
        return 0
    return 1


def _main_suite_diff(args) -> int:
    from journeys.diff import (
        DiffError,
        diff_suite_viewports,
        write_suite_diff,
    )

    suite_dir = Path(args.suite_dir)
    if not suite_dir.is_dir():
        print(f"suite-diff: not a directory: {suite_dir}", file=sys.stderr)
        return 1

    try:
        payload = diff_suite_viewports(suite_dir, baseline_viewport=args.baseline)
    except DiffError as e:
        print(f"suite-diff failed: {e}", file=sys.stderr)
        return 1

    out_path = write_suite_diff(payload, suite_dir)

    n_cells = len(payload["cells"])
    diffs_emitted = sum(len(c.get("compared", [])) for c in payload["cells"])
    verdict_changed = sum(
        1
        for c in payload["cells"]
        for cmp in c.get("compared", [])
        if cmp.get("verdict_changed")
    )
    print(
        f"Suite diff {payload['suite_id']}: baseline={payload['baseline_viewport']}, "
        f"{n_cells} cells, {diffs_emitted} per-pair diffs"
        + (f", {verdict_changed} verdict-changed" if verdict_changed else "")
    )
    print(f"  roll-up: {out_path}")

    if args.index:
        try:
            from reader.index import generate as generate_index
            index_path = generate_index(ARTEFACTS_ROOT)
            print(f"  Index:   {index_path}")
        except Exception as e:
            print(f"[reader] index generation failed: {e}", file=sys.stderr)

    # Exit code: 0 if every compared cell was verdict-stable; 1 otherwise.
    return 0 if verdict_changed == 0 else 1


def _slugify_for_filename(text: str, max_len: int = 40) -> str:
    """Lower-case, hyphenated, alnum-only slug for default filenames."""
    import re as _re
    s = _re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].rstrip("-")) or "journey"


def _main_expand(args) -> int:
    from journeys.expander import expand_to_file, ExpanderError
    from journeys.runner import run_journey
    from journeys.loader import load_journey

    prose = args.prose
    if prose == "-" or prose is None:
        prose = sys.stdin.read()
    if not prose or not prose.strip():
        print("expand: prose is empty (pass it as an arg or pipe via stdin with `-`)", file=sys.stderr)
        return 1

    if args.out:
        out_path = Path(args.out)
    else:
        slug = _slugify_for_filename(prose.split(".")[0])
        out_path = Path(__file__).parent / "journeys" / f"expanded-{slug}.json"

    try:
        written = expand_to_file(
            prose=prose,
            target_url=args.target,
            out_path=out_path,
            persona_hint=args.persona_hint,
        )
    except ExpanderError as e:
        print(f"Expand failed: {e}", file=sys.stderr)
        return 1

    print(f"Expanded journey: {written}")
    if not args.run:
        print("  (run with: verify.py journey " + str(written) + ")")
        return 0

    journey = load_journey(written)
    result = run_journey(journey)
    verdict = result.get("verdict", "FAIL" if not result.get("pass") else "PASS")
    print(
        f"Journey {verdict}: matcher={result.get('matcher')!r} "
        f"iters={result.get('iterations')} clicks={result.get('clicks_used')} "
        f"dead_ends={result.get('dead_ends')} duration_ms={result.get('duration_ms')}"
    )
    if result.get("error"):
        print(f"  error: {result['error']}", file=sys.stderr)
    print(f"  artefacts: {result.get('artefacts_dir')}")
    _emit_reports(result, include_index=True)
    return 0 if result.get("pass") else 1


def _emit_reports(result: dict, include_index: bool) -> None:
    artefacts_dir = result.get("artefacts_dir")
    if not artefacts_dir:
        return
    try:
        from reader.report import generate as generate_report
        report_path = generate_report(Path(artefacts_dir))
        print(f"Report: {report_path}")
        if include_index:
            from reader.index import generate as generate_index
            index_path = generate_index(Path(artefacts_dir).parent)
            print(f"Index:  {index_path}")
    except Exception as e:
        print(f"[reader] report generation failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
