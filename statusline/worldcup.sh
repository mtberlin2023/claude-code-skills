#!/usr/bin/env bash
# Toggle the World Cup feed in the Claude Code statusline tip line.
# When ON, the tip line shows live scores / results / fixtures / scorers
# instead of the normal spinner tips. When OFF, normal tips return.
#
#   worldcup.sh on              # show the football feed in the tip line
#   worldcup.sh off             # back to normal tips
#   worldcup.sh status          # is it on? show a sample of the current feed
#   worldcup.sh pull            # fetch the free live source → worldcup-data.json
#   worldcup.sh refresh         # clear the 10s statusline caches (after editing data)
#   worldcup.sh teams           # show which teams the feed is filtered to
#   worldcup.sh teams GER ENG   # follow only these teams (rotation narrows to them)
#   worldcup.sh teams clear     # drop the filter — show all teams again
#   worldcup.sh review GER       # full goal-by-goal review of a team's match
#
# The feed itself lives in worldcup-feed.py; data in worldcup-data.json.
set -euo pipefail
# All feed files (toggle flag, feed script, data) live beside this script, wherever
# it is installed. The statusline reads the same toggle file from this directory, so
# keep worldcup.sh, worldcup-feed.py and worldcup-data.json together.
HOOKS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLAG="$HOOKS/.worldcup-feed-on"
FEED="$HOOKS/worldcup-feed.py"

case "${1:-status}" in
  on)
    : > "$FLAG"
    rm -f /tmp/claude-statusline-* 2>/dev/null || true
    echo "⚽ World Cup feed ON — tip line now shows live scores. Sample rotation:"
    python3 "$FEED" --all 2>/dev/null | head -6
    ;;
  off)
    rm -f "$FLAG"
    rm -f /tmp/claude-statusline-* 2>/dev/null || true
    echo "World Cup feed OFF — normal spinner tips restored."
    ;;
  refresh)
    rm -f /tmp/claude-statusline-* 2>/dev/null || true
    echo "Statusline caches cleared — feed will re-read worldcup-data.json on next poll."
    ;;
  pull)
    # Fetch the free live source and rewrite worldcup-data.json (no-op on failure).
    if python3 "$FEED" --pull; then
      echo "⚽ Pulled live data. Current rotation sample:"
      python3 "$FEED" --all 2>/dev/null | head -6
    else
      echo "Pull failed — manual snapshot left untouched. (See stderr above.)"
    fi
    ;;
  review)
    shift
    if [ "$#" -eq 0 ]; then
      echo "Usage: worldcup.sh review <TEAM>   e.g. worldcup.sh review GER"
    else
      python3 "$FEED" --review "$1" 2>/dev/null || echo "Could not produce review for $1."
    fi
    ;;
  teams)
    shift
    DATA="$HOOKS/worldcup-data.json"
    if [ "$#" -eq 0 ]; then
      python3 -c "import json; d=json.load(open('$DATA')); f=d.get('followed',[]); print('Following: '+(' '.join(f) if f else '(all teams — no filter)'))"
    elif [ "$1" = "clear" ]; then
      python3 -c "import json; d=json.load(open('$DATA')); d.pop('followed',None); json.dump(d,open('$DATA','w'),indent=2,ensure_ascii=False)"
      rm -f /tmp/claude-statusline-* 2>/dev/null || true
      echo "Team filter cleared — feed shows all teams."
    else
      CODES="$(printf '%s ' "$@" | tr '[:lower:]' '[:upper:]')"
      python3 -c "import json,sys; d=json.load(open('$DATA')); d['followed']=sys.argv[1].split(); json.dump(d,open('$DATA','w'),indent=2,ensure_ascii=False); print('Now following: '+' '.join(d['followed']))" "$CODES"
      rm -f /tmp/claude-statusline-* 2>/dev/null || true
    fi
    ;;
  status|*)
    if [ -f "$FLAG" ]; then
      LINE=$(python3 "$FEED" 2>/dev/null)
      if [ -n "$LINE" ]; then
        echo "⚽ World Cup feed: ON. Current line:"
        echo "$LINE"
      else
        echo "⚽ World Cup feed: ON but DORMANT — tournament has ended (past end_epoch)."
        echo "Normal tips are showing. Run 'worldcup.sh off' to retire the toggle."
      fi
    else
      echo "World Cup feed: OFF (normal tips). Turn on with: worldcup.sh on"
    fi
    ;;
esac
