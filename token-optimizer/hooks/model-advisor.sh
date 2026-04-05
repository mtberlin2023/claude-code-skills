#!/bin/bash
# Model Advisor — classifies prompts and suggests optimal model usage
# Runs on UserPromptSubmit; stdout is injected into Claude's context
#
# Install: copy to ~/.claude/hooks/ and register in settings.json
# See README.md for details.

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('prompt', ''))
" 2>/dev/null)

if [ -z "$PROMPT" ]; then
  exit 0
fi

# Classify prompt complexity (simple heuristics)
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')
WORD_COUNT=$(echo "$PROMPT" | wc -w | tr -d ' ')

# Simple task indicators
IS_SIMPLE=false
for pattern in "url" "link" "status" "is it working" "is it running" "where is" "what is the" "open " "check " "show me" "list " "find " "search for" "deploy" "restart" "commit" "push" "git "; do
  if echo "$PROMPT_LOWER" | grep -qi "$pattern"; then
    IS_SIMPLE=true
    break
  fi
done

# Complex task indicators override simple
IS_COMPLEX=false
for pattern in "build " "create " "implement" "refactor" "design " "architect" "review " "analyze" "write a " "develop" "plan " "strategy" "rewrite"; do
  if echo "$PROMPT_LOWER" | grep -qi "$pattern"; then
    IS_COMPLEX=true
    IS_SIMPLE=false
    break
  fi
done

if [ "$IS_SIMPLE" = true ] && [ "$WORD_COUNT" -lt 20 ]; then
  cat << EOF
<model-routing hint="simple-task">
This appears to be a simple/routine task. Use haiku subagents for any file searches or lookups needed. Keep responses brief. If the user hasn't enabled /fast mode, consider suggesting it for sessions focused on routine tasks.
</model-routing>
EOF
fi
