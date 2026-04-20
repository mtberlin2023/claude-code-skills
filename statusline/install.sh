#!/usr/bin/env bash
#
# statusline / install.sh
#
# One-shot installer for the Claude Code statusline.
#
# What it does (idempotent — safe to re-run):
#   1. Creates ~/.claude/hooks/ if missing.
#   2. Copies statusline.sh and forecast_gap.py to ~/.claude/hooks/.
#   3. Backs up ~/.claude/settings.json (timestamped) and sets statusLine.command
#      to point at the installed script. Existing hooks / other settings untouched.
#   4. Prints a verification summary.
#
# Uninstall:
#   bash install.sh --uninstall
#
# Override target dir (for testing): set CLAUDE_HOME=/tmp/fake-claude before running.
#
# Requires: bash, python3 (3.8+).

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS="$CLAUDE_DIR/settings.json"

c_green()  { printf '\033[0;32m%s\033[0m\n' "$1"; }
c_yellow() { printf '\033[0;33m%s\033[0m\n' "$1"; }
c_red()    { printf '\033[0;31m%s\033[0m\n' "$1"; }
c_dim()    { printf '\033[2m%s\033[0m\n'    "$1"; }

require() {
  command -v "$1" >/dev/null 2>&1 || { c_red "Missing required command: $1"; exit 1; }
}

uninstall() {
  c_yellow "Uninstalling statusline..."

  # Try to restore most recent statusline-* backup; else strip the statusLine key.
  if [[ -f "$SETTINGS" ]]; then
    latest_backup=$(ls -1t "$SETTINGS".statusline-backup-* 2>/dev/null | head -n1 || true)
    if [[ -n "$latest_backup" ]]; then
      c_yellow "Found backup: $latest_backup"
      read -r -p "Restore this backup over $SETTINGS? [y/N] " ans
      if [[ "$ans" =~ ^[Yy]$ ]]; then
        cp "$latest_backup" "$SETTINGS"
        c_green "Restored from backup."
      else
        python3 - "$SETTINGS" <<'PYEOF'
import json, sys
p = sys.argv[1]
try:
    with open(p) as f: d = json.load(f)
except Exception:
    sys.exit(0)
if isinstance(d, dict) and isinstance(d.get("statusLine"), dict):
    cmd = d["statusLine"].get("command", "")
    if "statusline.sh" in cmd:
        d.pop("statusLine", None)
        with open(p, "w") as f:
            json.dump(d, f, indent=2)
            f.write("\n")
PYEOF
        c_green "Removed statusLine entry from $SETTINGS"
      fi
    fi
  fi

  rm -f "$HOOKS_DIR/statusline.sh"
  rm -f "$HOOKS_DIR/forecast_gap.py"
  rm -f "$HOOKS_DIR/.forecast-cache.json"
  c_green "Removed installed scripts."
  c_dim "Your Claude Code transcripts (~/.claude/projects/) were not touched."
  exit 0
}

if [[ "${1:-}" == "--uninstall" ]]; then
  uninstall
fi

# ── Pre-flight ───────────────────────────────────────────────────────────────
require python3
require bash

if [[ ! -d "$CLAUDE_DIR" ]]; then
  c_red "$CLAUDE_DIR does not exist."
  c_dim "Is Claude Code installed? Run it once before installing this statusline."
  exit 1
fi

mkdir -p "$HOOKS_DIR"

# ── 1. Copy scripts ──────────────────────────────────────────────────────────
cp "$SKILL_DIR/statusline.sh"   "$HOOKS_DIR/statusline.sh"
cp "$SKILL_DIR/forecast_gap.py" "$HOOKS_DIR/forecast_gap.py"
chmod +x "$HOOKS_DIR/statusline.sh"
c_green "✓ Installed statusline.sh   → $HOOKS_DIR/statusline.sh"
c_green "✓ Installed forecast_gap.py → $HOOKS_DIR/forecast_gap.py"

# ── 2. Patch settings.json ───────────────────────────────────────────────────
TARGET_CMD="bash $HOOKS_DIR/statusline.sh"

if [[ -f "$SETTINGS" ]]; then
  backup="$SETTINGS.statusline-backup-$(date +%Y%m%d-%H%M%S)"
  cp "$SETTINGS" "$backup"
  c_dim "  Backed up settings.json → $backup"

  python3 - "$SETTINGS" "$TARGET_CMD" <<'PYEOF'
import json, sys
p, cmd = sys.argv[1], sys.argv[2]
try:
    with open(p) as f: d = json.load(f)
except Exception:
    d = {}
if not isinstance(d, dict): d = {}
d["statusLine"] = {"type": "command", "command": cmd}
with open(p, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
PYEOF
  c_green "✓ Patched $SETTINGS (statusLine.command)"
else
  python3 - "$SETTINGS" "$TARGET_CMD" <<'PYEOF'
import json, sys
p, cmd = sys.argv[1], sys.argv[2]
with open(p, "w") as f:
    json.dump({"statusLine": {"type": "command", "command": cmd}}, f, indent=2)
    f.write("\n")
PYEOF
  c_green "✓ Created $SETTINGS with statusLine entry"
fi

# ── 3. Verification ──────────────────────────────────────────────────────────
echo
c_green "──────────────────────────────────────────────────────"
c_green " statusline installed"
c_green "──────────────────────────────────────────────────────"
echo
c_dim "Next step:"
echo "  Open a new Claude Code session. The bottom-left bar will show:"
echo "    🟢 N turns → XK next turn [· action] [· 5h cap] [· wk cap] [· runway]"
echo
c_dim "Customise the action slash command (optional):"
echo "  export CLAUDE_CODE_STATUSLINE_ACTION=/compact   # default: /log"
echo
c_dim "Uninstall:"
echo "  bash $SKILL_DIR/install.sh --uninstall"
echo
