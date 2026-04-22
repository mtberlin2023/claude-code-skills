#!/usr/bin/env bash
#
# token-optimizer / install.sh
#
# One-shot installer for the token-optimizer Claude Code skill.
#
# What it does (idempotent — safe to re-run):
#   1. Creates ~/.claude/scripts/ and ~/.claude/commands/ if missing.
#   2. Copies audit.py to ~/.claude/scripts/.
#   3. Copies commands/audit.md and commands/log.md to ~/.claude/commands/.
#   4. Backs up ~/.claude/CLAUDE.md (timestamped) and appends the
#      token-optimizer fragment if not already present.
#   5. Prints a verification summary.
#
# Uninstall:
#   bash install.sh --uninstall
#
# Requires: bash, python3 (3.8+), and an existing ~/.claude/ directory.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
SCRIPTS_DIR="$CLAUDE_DIR/scripts"
COMMANDS_DIR="$CLAUDE_DIR/commands"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
MARK_START="# ─── token-optimizer START ──────────────────────────────────────────────────"
MARK_END="# ─── token-optimizer END ────────────────────────────────────────────────────"

c_green() { printf '\033[0;32m%s\033[0m\n' "$1"; }
c_yellow() { printf '\033[0;33m%s\033[0m\n' "$1"; }
c_red() { printf '\033[0;31m%s\033[0m\n' "$1"; }
c_dim() { printf '\033[2m%s\033[0m\n' "$1"; }

require() {
  command -v "$1" >/dev/null 2>&1 || { c_red "Missing required command: $1"; exit 1; }
}

uninstall() {
  c_yellow "Uninstalling token-optimizer..."
  rm -f "$SCRIPTS_DIR/audit.py"
  rm -f "$COMMANDS_DIR/audit.md"
  rm -f "$COMMANDS_DIR/log.md"

  if [[ -f "$CLAUDE_MD" ]]; then
    # Find the most recent token-optimizer backup and offer to restore.
    latest_backup=$(ls -1t "$CLAUDE_MD".token-optimizer-backup-* 2>/dev/null | head -n1 || true)
    if [[ -n "$latest_backup" ]]; then
      c_yellow "Found backup: $latest_backup"
      read -r -p "Restore this backup over $CLAUDE_MD? [y/N] " ans
      if [[ "$ans" =~ ^[Yy]$ ]]; then
        cp "$latest_backup" "$CLAUDE_MD"
        c_green "Restored from backup."
      else
        # Strip the fragment in place instead.
        if grep -qF "$MARK_START" "$CLAUDE_MD"; then
          tmp="$(mktemp)"
          awk -v s="$MARK_START" -v e="$MARK_END" '
            $0==s {skip=1; next}
            $0==e {skip=0; next}
            skip!=1 {print}
          ' "$CLAUDE_MD" > "$tmp"
          mv "$tmp" "$CLAUDE_MD"
          c_green "Stripped token-optimizer fragment from $CLAUDE_MD"
        fi
      fi
    fi
  fi

  c_green "Uninstall complete."
  c_dim "Your ~/.claude/projects/*.jsonl logs were not touched."
  exit 0
}

if [[ "${1:-}" == "--uninstall" ]]; then
  uninstall
fi

# ── Pre-flight ───────────────────────────────────────────────────────────────
require python3
require awk

if [[ ! -d "$CLAUDE_DIR" ]]; then
  c_red "$CLAUDE_DIR does not exist."
  c_dim "Is Claude Code installed? Run it once before installing this skill."
  exit 1
fi

mkdir -p "$SCRIPTS_DIR" "$COMMANDS_DIR"

# ── 1. Copy audit.py ─────────────────────────────────────────────────────────
cp "$SKILL_DIR/audit.py" "$SCRIPTS_DIR/audit.py"
chmod +x "$SCRIPTS_DIR/audit.py"
c_green "✓ Installed audit script → $SCRIPTS_DIR/audit.py"

# ── 2. Copy slash commands ───────────────────────────────────────────────────
cp "$SKILL_DIR/commands/audit.md" "$COMMANDS_DIR/audit.md"
cp "$SKILL_DIR/commands/log.md" "$COMMANDS_DIR/log.md"
c_green "✓ Installed slash commands → /audit and /log"

# ── 3. Append CLAUDE.md fragment ─────────────────────────────────────────────
if [[ -f "$CLAUDE_MD" ]]; then
  if grep -qF "$MARK_START" "$CLAUDE_MD"; then
    c_yellow "✓ token-optimizer fragment already present in $CLAUDE_MD — skipping append."
  else
    backup="$CLAUDE_MD.token-optimizer-backup-$(date +%Y%m%d-%H%M%S)"
    cp "$CLAUDE_MD" "$backup"
    c_dim "  Backed up existing CLAUDE.md → $backup"

    # Extract just the fragment block from the skill's CLAUDE.md (between ``` fences)
    fragment="$(awk '/^```$/{f=!f; next} f' "$SKILL_DIR/CLAUDE.md")"
    {
      printf '\n\n'
      printf '%s\n' "$fragment"
    } >> "$CLAUDE_MD"
    c_green "✓ Appended token-optimizer fragment to $CLAUDE_MD"
  fi
else
  c_yellow "No existing $CLAUDE_MD — creating one with just the fragment."
  fragment="$(awk '/^```$/{f=!f; next} f' "$SKILL_DIR/CLAUDE.md")"
  {
    printf '# CLAUDE.md\n\n'
    printf '%s\n' "$fragment"
  } > "$CLAUDE_MD"
  c_green "✓ Created $CLAUDE_MD with token-optimizer fragment."
fi

# ── 4. Verification ──────────────────────────────────────────────────────────
echo
c_green "──────────────────────────────────────────────────────"
c_green " token-optimizer installed"
c_green "──────────────────────────────────────────────────────"
echo
c_dim "Try it out:"
echo "  python3 $SCRIPTS_DIR/audit.py --top 5"
echo
c_dim "Inside Claude Code:"
echo "  /audit       — see your own session metrics"
echo "  /log         — write a handover before closing the session"
echo
c_dim "Read the white paper:"
echo "  $SKILL_DIR/PAPER.md"
echo
c_dim "Uninstall:"
echo "  bash $SKILL_DIR/install.sh --uninstall"
echo
