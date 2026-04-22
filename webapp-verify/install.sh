#!/usr/bin/env bash
# webapp-verify / install.sh
#
# Install pinned runtime dependencies for verify.py.
# Anya #7 (security-review log, 2026-04-21): supply-chain posture requires
# explicit version pin + sha256 hash verification + no auto-upgrade.
#
# Usage:
#     bash install.sh            # installs into the current Python env
#     PYTHON=python3.11 bash install.sh
#
# The chrome-devtools-mcp server is fetched at runtime via `npx -y
# chrome-devtools-mcp@latest` — that version is pinned in verify.py's
# MCP_LAUNCH_CMD constant, not here. Run `verify.py --check-install` after
# this script to confirm npx can reach it.

set -euo pipefail

PYTHON="${PYTHON:-python3}"

# Pinned versions — bump deliberately, never auto-upgrade.
MCP_VERSION="1.27.0"
MCP_WHEEL_SHA256="5ce1fa81614958e267b21fb2aa34e0aea8e2c6ede60d52aba45fd47246b4d741"
MCP_SDIST_SHA256="d3dc35a7eec0d458c1da4976a48f982097ddaab87e278c5511d5a4a56e852b83"

REQ_FILE="$(mktemp -t webapp-verify-requirements.XXXXXX)"
trap 'rm -f "$REQ_FILE"' EXIT

cat >"$REQ_FILE" <<EOF
mcp==${MCP_VERSION} \\
    --hash=sha256:${MCP_WHEEL_SHA256} \\
    --hash=sha256:${MCP_SDIST_SHA256}
EOF

echo "webapp-verify install:"
echo "  python:  $("$PYTHON" --version)"
echo "  mcp:     ${MCP_VERSION}"
echo "  hashes:  wheel + sdist pinned"
echo

"$PYTHON" -m pip install \
    --require-hashes \
    --no-deps \
    --requirement "$REQ_FILE"

# mcp SDK's own transitive deps — install without hash-pin (their hashes
# change on upstream patch releases). If Anya tightens the posture later,
# expand this file to hash-pin the closure.
"$PYTHON" -m pip install "mcp==${MCP_VERSION}" >/dev/null

echo "OK: mcp ${MCP_VERSION} installed with hash verification."
echo "Run: verify.py --check-install   # confirms chrome-devtools-mcp reachable"
