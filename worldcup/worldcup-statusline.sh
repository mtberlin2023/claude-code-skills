#!/usr/bin/env bash
#
# worldcup-statusline.sh — standalone World Cup statusline.
#
# Renders ONLY the live football feed line in the Claude Code bottom bar. Use this
# when you want the World Cup feed WITHOUT the cost-chip statusline. `install.sh`
# in this directory sets it as your `statusLine.command`.
#
# Behaviour:
#   • Respects the same on/off toggle `worldcup.sh` writes (.worldcup-feed-on).
#     Toggle off → prints nothing → the bar falls back to Claude Code's default.
#   • Prints nothing once the tournament ends (feed dormant past end_epoch).
#   • Silent on any failure — a statusline must never spill a traceback into the bar.
#   • 10s cache (same cadence the feed rotates on) so screen renders stay cheap.
#     The cache file matches worldcup.sh's `/tmp/claude-statusline-*` clear glob,
#     so `worldcup.sh on/off/refresh/teams` invalidate it.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLAG="$DIR/.worldcup-feed-on"
FEED="$DIR/worldcup-feed.py"
CACHE="/tmp/claude-statusline-worldcup"

# Feed toggled off → nothing to show.
[ -f "$FLAG" ] || exit 0

# Serve a fresh (<10s) cache without spawning python.
if [ -f "$CACHE" ]; then
  mtime=$(stat -f %m "$CACHE" 2>/dev/null || stat -c %Y "$CACHE" 2>/dev/null || echo 0)
  now=$(date +%s)
  if [ "$((now - mtime))" -lt 10 ]; then
    cat "$CACHE"
    exit 0
  fi
fi

LINE=$(python3 "$FEED" 2>/dev/null) || LINE=""
# Feed lines already carry their own leading glyph (⚽ live / 🏁 FT / ⏰ fixture /
# 👟 scorers), so print as-is — no extra prefix to double-stamp.
if [ -n "$LINE" ]; then
  printf '%s\n' "$LINE" | tee "$CACHE"
else
  # Dormant / no data — cache the emptiness so we don't re-spawn python every render.
  : > "$CACHE"
fi
exit 0
