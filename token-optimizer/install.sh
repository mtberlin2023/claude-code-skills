#!/bin/bash
# Token Optimizer — Install Script
# Copies hooks and registers them in Claude Code settings

set -e

HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS_FILE="$HOME/.claude/settings.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Token Optimizer Installer ==="
echo ""

# Step 1: Create hooks directory
mkdir -p "$HOOKS_DIR"

# Step 2: Copy hook scripts
echo "Copying hooks..."
cp "$SCRIPT_DIR/hooks/session-monitor.sh" "$HOOKS_DIR/"
cp "$SCRIPT_DIR/hooks/model-advisor.sh" "$HOOKS_DIR/"
chmod +x "$HOOKS_DIR/session-monitor.sh"
chmod +x "$HOOKS_DIR/model-advisor.sh"
echo "  -> session-monitor.sh"
echo "  -> model-advisor.sh"

# Step 3: Update settings.json
echo ""
echo "Updating settings.json..."

if [ ! -f "$SETTINGS_FILE" ]; then
  # No settings file — create one
  cat > "$SETTINGS_FILE" << 'SETTINGS'
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/session-monitor.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/model-advisor.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
SETTINGS
  echo "  -> Created new settings.json"
else
  # Settings file exists — check if hooks are already registered
  if grep -q "session-monitor.sh" "$SETTINGS_FILE" && grep -q "model-advisor.sh" "$SETTINGS_FILE"; then
    echo "  -> Hooks already registered in settings.json (skipped)"
  else
    echo ""
    echo "  !! Your settings.json already exists but doesn't have these hooks."
    echo "  !! Please add the following to your settings.json manually:"
    echo ""
    echo '  Add to "hooks" -> "UserPromptSubmit" -> first entry -> "hooks" array:'
    echo ""
    echo '    {'
    echo '      "type": "command",'
    echo '      "command": "bash ~/.claude/hooks/session-monitor.sh",'
    echo '      "timeout": 5'
    echo '    },'
    echo '    {'
    echo '      "type": "command",'
    echo '      "command": "bash ~/.claude/hooks/model-advisor.sh",'
    echo '      "timeout": 5'
    echo '    }'
    echo ""
    echo "  See README.md for the full settings.json structure."
  fi
fi

# Step 4: Remind about CLAUDE.md
echo ""
echo "=== Almost done! ==="
echo ""
echo "The hooks are installed. One more step:"
echo ""
echo "  Copy the rules from CLAUDE.md.example into your CLAUDE.md:"
echo ""
echo "    cat $SCRIPT_DIR/CLAUDE.md.example >> ~/.claude/CLAUDE.md"
echo ""
echo "  Or copy specific sections — see CLAUDE.md.example for details."
echo ""
echo "=== Installation complete ==="
