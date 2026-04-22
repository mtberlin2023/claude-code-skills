#!/usr/bin/env bash
# webapp-verify / install.sh
#
# Install pinned runtime dependencies for verify.py.
# Anya #7 (security-review log, 2026-04-21): supply-chain posture requires
# explicit version pin + sha256 hash verification + no auto-upgrade.
# Anya #7a (2026-04-22): the transitive closure is now hash-pinned too,
# not just the primary dep. Lock file: mcp-1.27.0-lock.txt
#
# Usage:
#     bash install.sh            # installs into the current Python env
#     PYTHON=python3.11 bash install.sh
#
# The chrome-devtools-mcp server is fetched at runtime via `npx -y
# chrome-devtools-mcp@latest` — that version is pinned in verify.py's
# MCP_LAUNCH_CMD constant, not here. Run `verify.py --check-install` after
# this script to confirm npx can reach it.
#
# ── Platform scope ────────────────────────────────────────────────────────
# mcp-1.27.0-lock.txt was resolved on darwin-arm64 (Apple Silicon, 2026-04-22).
# Pure-Python wheels in the closure work cross-platform; four compiled
# wheels are arm64-specific: pydantic_core, rpds_py, cffi, cryptography.
# On any other platform (darwin-x86_64, linux-*, windows), `--require-hashes`
# will fail loudly on those four packages rather than silently pulling
# unpinned bits — that is the intended safety.
#
# TBD — multi-platform deployment: this skill is planned for GitHub publication
# for wider community use. Before publishing, regenerate the lock file with
# hashes covering darwin-arm64 + darwin-x86_64 + linux-x86_64 (and sdist
# fallbacks where compilation toolchains are assumed). Handover:
# `_handover/continue--webapp-verify-multiplatform-lock.md`. Tracking in
# `_shared/experts/security-review-log.md` v1.1 backlog.
# ──────────────────────────────────────────────────────────────────────────

set -euo pipefail

PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK_FILE="${SCRIPT_DIR}/mcp-1.27.0-lock.txt"

if [[ ! -f "$LOCK_FILE" ]]; then
    echo "error: lock file not found at $LOCK_FILE" >&2
    exit 1
fi

echo "webapp-verify install:"
echo "  python:  $("$PYTHON" --version)"
echo "  lock:    mcp-1.27.0-lock.txt (full closure, hash-pinned, darwin-arm64)"
echo

"$PYTHON" -m pip install \
    --require-hashes \
    --requirement "$LOCK_FILE"

echo "OK: mcp 1.27.0 + transitive closure installed with hash verification."
echo "Run: verify.py --check-install   # confirms chrome-devtools-mcp reachable"
