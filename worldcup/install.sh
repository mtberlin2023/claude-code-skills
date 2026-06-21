#!/usr/bin/env bash
#
# worldcup / install.sh
#
# Standalone installer for the World Cup feed — the live football statusline,
# WITHOUT the cost-chip statusline. Use this if you only want the football line.
# (If you also want the next-turn-cost chip, install ../statusline instead; its
#  installer offers the same feed as an add-on via `install.sh --worldcup-only`.)
#
# What it does (idempotent — safe to re-run):
#   1. Creates ~/.claude/hooks/ if missing.
#   2. Copies worldcup-feed.py, worldcup.sh, worldcup-statusline.sh, the demo seed
#      + env example to ~/.claude/hooks/, seeding worldcup-data.json if absent.
#   3. Turns the feed ON (writes .worldcup-feed-on) — that's the whole point here.
#   4. Backs up ~/.claude/settings.json (timestamped) and sets statusLine.command
#      to the football-only statusline. Existing hooks / other settings untouched.
#   5. Prints a verification summary.
#
# Uninstall:   bash install.sh --uninstall
# Test target: set CLAUDE_HOME=/tmp/fake-claude before running.
# Requires:    bash, python3 (3.8+).

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
  c_yellow "Uninstalling World Cup statusline..."

  # Restore most recent worldcup-* backup; else strip the statusLine key if it
  # points at the football statusline.
  if [[ -f "$SETTINGS" ]]; then
    latest_backup=$(ls -1t "$SETTINGS".worldcup-backup-* 2>/dev/null | head -n1 || true)
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
    if "worldcup-statusline.sh" in cmd:
        d.pop("statusLine", None)
        with open(p, "w") as f:
            json.dump(d, f, indent=2)
            f.write("\n")
PYEOF
        c_green "Removed statusLine entry from $SETTINGS"
      fi
    fi
  fi

  rm -f "$HOOKS_DIR/worldcup-statusline.sh"
  rm -f "$HOOKS_DIR/worldcup-feed.py"
  rm -f "$HOOKS_DIR/worldcup.sh"
  rm -f "$HOOKS_DIR/worldcup-data.example.json"
  rm -f "$HOOKS_DIR/.worldcup.env.example"
  rm -f "$HOOKS_DIR/.worldcup-feed-on"
  rm -f /tmp/claude-statusline-worldcup
  c_green "Removed installed scripts."
  c_dim "Your .worldcup.env (API key) and pulled worldcup-data.json were kept — delete them by hand if you want them gone."
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
  c_dim "Is Claude Code installed? Run it once before installing this."
  exit 1
fi

mkdir -p "$HOOKS_DIR"

# ── 1. Copy scripts ──────────────────────────────────────────────────────────
cp "$SKILL_DIR/worldcup-feed.py"           "$HOOKS_DIR/worldcup-feed.py"
cp "$SKILL_DIR/worldcup.sh"                "$HOOKS_DIR/worldcup.sh"
cp "$SKILL_DIR/worldcup-statusline.sh"     "$HOOKS_DIR/worldcup-statusline.sh"
cp "$SKILL_DIR/worldcup-data.example.json" "$HOOKS_DIR/worldcup-data.example.json"
cp "$SKILL_DIR/.worldcup.env.example"      "$HOOKS_DIR/.worldcup.env.example"
chmod +x "$HOOKS_DIR/worldcup.sh" "$HOOKS_DIR/worldcup-statusline.sh"
c_green "✓ Installed worldcup-feed.py        → $HOOKS_DIR/worldcup-feed.py"
c_green "✓ Installed worldcup.sh             → $HOOKS_DIR/worldcup.sh"
c_green "✓ Installed worldcup-statusline.sh  → $HOOKS_DIR/worldcup-statusline.sh"

# Seed demo data only if absent — never clobber a live pull.
if [[ ! -f "$HOOKS_DIR/worldcup-data.json" ]]; then
  cp "$SKILL_DIR/worldcup-data.example.json" "$HOOKS_DIR/worldcup-data.json"
  c_dim "  Seeded worldcup-data.json from the demo (delete it + run 'worldcup.sh pull' for live data)."
fi

# Turn the feed on by default — a standalone install exists to show football.
: > "$HOOKS_DIR/.worldcup-feed-on"
rm -f /tmp/claude-statusline-worldcup 2>/dev/null || true
c_green "✓ Feed toggled ON (.worldcup-feed-on)"

# ── 2. Patch settings.json ───────────────────────────────────────────────────
TARGET_CMD="bash $HOOKS_DIR/worldcup-statusline.sh"

if [[ -f "$SETTINGS" ]]; then
  backup="$SETTINGS.worldcup-backup-$(date +%Y%m%d-%H%M%S)"
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
c_green " World Cup statusline installed (standalone)"
c_green "──────────────────────────────────────────────────────"
echo
c_dim "Next step:"
echo "  Open a new Claude Code session. The bottom-left bar will show:"
echo "    ⚽ GER 1–1 ESP  67'  🥅 Wirtz 67'"
echo
c_dim "Controls:"
echo "  bash $HOOKS_DIR/worldcup.sh off       # hide the feed"
echo "  bash $HOOKS_DIR/worldcup.sh on        # show it again"
echo "  bash $HOOKS_DIR/worldcup.sh teams GER ENG   # follow only these teams"
echo "  bash $HOOKS_DIR/worldcup.sh review GER      # goal-by-goal card"
echo
c_dim "Live data (optional — demo seed works with no key):"
echo "  cp $HOOKS_DIR/.worldcup.env.example $HOOKS_DIR/.worldcup.env"
echo "  # add your API-Football key, then:"
echo "  bash $HOOKS_DIR/worldcup.sh pull"
echo
c_dim "Uninstall:"
echo "  bash $SKILL_DIR/install.sh --uninstall"
echo
