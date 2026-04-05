#!/bin/bash
# Session Monitor — warns Claude when sessions get too long
# Runs on UserPromptSubmit; stdout is injected into Claude's context
#
# Install: copy to ~/.claude/hooks/ and register in settings.json
# See README.md for details.

# Read hook input from stdin
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
  exit 0
fi

# Find the session's JSONL file
JSONL=""
for dir in ~/.claude/projects/*/; do
  candidate="${dir}${SESSION_ID}.jsonl"
  if [ -f "$candidate" ]; then
    JSONL="$candidate"
    break
  fi
done

if [ -z "$JSONL" ] || [ ! -f "$JSONL" ]; then
  exit 0
fi

# Count user messages (each user message = one turn)
USER_MSGS=$(grep -c '"type":"user"' "$JSONL" 2>/dev/null || grep -c '"type": "user"' "$JSONL" 2>/dev/null || echo "0")
FILE_SIZE=$(stat -f%z "$JSONL" 2>/dev/null || stat -c%s "$JSONL" 2>/dev/null || echo "0")
SIZE_MB=$(echo "scale=1; $FILE_SIZE / 1048576" | bc 2>/dev/null || echo "0")

TURNS=$USER_MSGS

# Thresholds — output to stdout is injected into Claude's context
if [ "$TURNS" -ge 200 ]; then
  cat << EOF
<session-health status="CRITICAL">
SESSION CRITICAL: ${TURNS} turns, ${SIZE_MB}MB. This session is extremely long — each turn now costs 15-30x what it did at the start. You MUST:
1. Tell the user: "This session has ${TURNS} turns. Token cost per turn is now extreme. Let me save a handover and we should start fresh."
2. Provide a handover block immediately
3. Do NOT continue working on new tasks in this session
</session-health>
EOF
elif [ "$TURNS" -ge 100 ]; then
  cat << EOF
<session-health status="WARNING">
SESSION WARNING: ${TURNS} turns, ${SIZE_MB}MB. Token efficiency is degrading significantly (~5-10x cost per turn vs start). After completing the current task:
1. Recommend the user start a fresh session
2. Offer a handover block
3. Do NOT start new topics in this session
</session-health>
EOF
elif [ "$TURNS" -ge 50 ]; then
  cat << EOF
<session-health status="NOTICE">
SESSION NOTICE: ${TURNS} turns, ${SIZE_MB}MB. Approaching efficiency threshold. Plan to wrap up within ~50 more turns. Avoid starting large new tasks — suggest a fresh session for anything major.
</session-health>
EOF
fi
