#!/bin/bash
# Claude Code statusline — next-turn replay cost tracker
#
# Reads stdin JSON (Claude Code statusLine contract), outputs one line.
# Format: [emoji] [N] turns → [Y]K next turn [· action] [· err] [· 5h cap] [· wk cap] [· runway]
#
# Driver: next-turn replay R = last assistant usage.cache_read + cache_creation + input.
# This is the actual cost you pay per turn — a short session that loaded heavy
# context can replay more per turn than a long session of small lookups.
#
# States:
#   🟢 <200K          — healthy
#   🟡 200–499K       — warning; log after current task
#   🔴 500–999K       — critical; log now
#   🔴 ≥1M            — hard cap; log before next message
#
# Action string: the slash command suggested at yellow/red thresholds.
# Defaults to "/log"; override by setting CLAUDE_CODE_STATUSLINE_ACTION in your
# shell environment (e.g. export CLAUDE_CODE_STATUSLINE_ACTION=/compact).
#
# Modifiers:
#   ⚠ NNKB err            — appended when any cached tool_result error >2KB
#   ⚠ NN%·5h→HH:MM        — 5h burst cap 75–89% used; reset time appended
#   🚨 NN%·5h→HH:MM        — 5h burst cap ≥90% used; reset time appended
#   ⚠ NN%·wk→Day HH:MM    — 7-day cap 60–84% used; reset time appended
#   🚨 NN%·wk→Day HH:MM    — 7-day cap ≥85% used; reset time appended
#   🕐 Xh @ avg           — weekly runway in active Claude-hours at average burn;
#                           integer ≥10h, 0.5-h steps below; neutral ≥10h · yellow <10h
#                           · red <3h; gated on wk chip.
#
# Reset times come from rate_limits.{five_hour,seven_day}.resets_at (unix seconds, local TZ).
# Rate-limit segments hidden below thresholds. Silent on failure.
#
# Requires: bash, python3 (3.8+), and ~/.claude/hooks/forecast_gap.py alongside this script.

INPUT=$(cat)
VALS=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
tp = d.get('transcript_path', '') or ''
rl = d.get('rate_limits') or {}
fh = rl.get('five_hour') or {}
sd = rl.get('seven_day') or {}
def num(v):
    try: return str(float(v))
    except Exception: return ''
print(tp)
print(num(fh.get('used_percentage', '')))
print(num(sd.get('used_percentage', '')))
print(num(fh.get('resets_at', '')))
print(num(sd.get('resets_at', '')))
" 2>/dev/null)

{ IFS= read -r TRANSCRIPT; IFS= read -r PCT_5H; IFS= read -r PCT_WK; IFS= read -r RST_5H; IFS= read -r RST_WK; } <<< "$VALS"

[ -z "$TRANSCRIPT" ] && exit 0
[ ! -f "$TRANSCRIPT" ] && exit 0

SESSION_ID=$(basename "$TRANSCRIPT" .jsonl)
CACHE="/tmp/claude-statusline-${SESSION_ID}"
now=$(date +%s)

if [ -f "$CACHE" ]; then
  ts=$(stat -f%m "$CACHE" 2>/dev/null || stat -c%Y "$CACHE" 2>/dev/null || echo 0)
  if [ $((now - ts)) -lt 10 ]; then
    cat "$CACHE"
    exit 0
  fi
fi

ACTION="${CLAUDE_CODE_STATUSLINE_ACTION:-/log}"

OUTPUT=$(PCT_5H="$PCT_5H" PCT_WK="$PCT_WK" RST_5H="$RST_5H" RST_WK="$RST_WK" ACTION="$ACTION" python3 - "$TRANSCRIPT" <<'PYEOF' 2>/dev/null
import json, os, sys, time

path = sys.argv[1]
turns = 0
max_err = 0
r = 0  # next-turn replay: last assistant usage.cache_read + cache_creation + input

SYNTHETIC_PREFIXES = (
    '<command-message>', '<command-name>', '<command-args>',
    '<task-notification>', '<local-command-caveat>', '<system-reminder>',
    '<user-prompt-submit-hook>',
    'Unknown command:',  # system echo for failed slash commands
    'Caveat:',           # local-command caveat preamble
)

def is_synthetic(text):
    if not text:
        return True
    return text.lstrip().startswith(SYNTHETIC_PREFIXES)

try:
    with open(path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get('type')
            if t == 'assistant':
                usage = (obj.get('message') or {}).get('usage') or {}
                if usage:
                    r = (usage.get('cache_read_input_tokens', 0) or 0) \
                      + (usage.get('cache_creation_input_tokens', 0) or 0) \
                      + (usage.get('input_tokens', 0) or 0)
                continue
            if t != 'user':
                continue
            msg = obj.get('message') or {}
            content = msg.get('content')
            has_real = False
            if isinstance(content, str):
                if content.strip() and not is_synthetic(content):
                    has_real = True
            elif isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    itype = item.get('type')
                    if itype == 'tool_result':
                        body = item.get('content', '')
                        if isinstance(body, list):
                            body = ''.join(c.get('text', '') for c in body if isinstance(c, dict))
                        bsize = len(str(body))
                        if bsize > 2048 and item.get('is_error'):
                            if bsize > max_err:
                                max_err = bsize
                    elif itype == 'text':
                        if not is_synthetic(item.get('text', '')):
                            has_real = True
                    else:
                        has_real = True
            if has_real:
                turns += 1
except Exception:
    pass

def fmt(t):
    if t >= 1_000_000:
        return f"{t/1_000_000:.1f}M"
    if t >= 1_000:
        return f"{t//1_000}K"
    return str(t)

r_fmt = fmt(r)
action = os.environ.get('ACTION', '/log')

if r < 200_000:
    emoji, action_str = "🟢", ""
elif r < 500_000:
    emoji, action_str = "🟡", f" · {action} after task"
elif r < 1_000_000:
    emoji, action_str = "🔴", f" · {action} now"
else:
    emoji, action_str = "🔴", f" · {action} before next msg"

err_flag = f" · ⚠ {max_err//1024}KB err" if max_err > 2048 else ""

def parse_pct(s):
    try:
        v = float(s)
        return v if v >= 0 else None
    except Exception:
        return None

pct_5h = parse_pct(os.environ.get('PCT_5H', ''))
pct_wk = parse_pct(os.environ.get('PCT_WK', ''))
rst_5h = parse_pct(os.environ.get('RST_5H', ''))
rst_wk = parse_pct(os.environ.get('RST_WK', ''))

def fmt_reset_short(ts):
    if ts is None or ts <= 0:
        return ""
    lt = time.localtime(ts)
    today = time.localtime()
    if lt.tm_yday == today.tm_yday and lt.tm_year == today.tm_year:
        return time.strftime("%H:%M", lt)
    return time.strftime("%a %H:%M", lt)

def fmt_reset_long(ts):
    if ts is None or ts <= 0:
        return ""
    return time.strftime("%a %H:%M", time.localtime(ts))

cap_segments = []
if pct_5h is not None:
    rs = fmt_reset_short(rst_5h)
    suffix = f"→{rs}" if rs else ""
    if pct_5h >= 90:
        cap_segments.append(f"🚨 {int(pct_5h)}%·5h{suffix}")
    elif pct_5h >= 75:
        cap_segments.append(f"⚠ {int(pct_5h)}%·5h{suffix}")
if pct_wk is not None:
    rs = fmt_reset_long(rst_wk)
    suffix = f"→{rs}" if rs else ""
    if pct_wk >= 85:
        cap_segments.append(f"🚨 {int(pct_wk)}%·wk{suffix}")
    elif pct_wk >= 60:
        cap_segments.append(f"⚠ {int(pct_wk)}%·wk{suffix}")

# Runway chip — gated on the wk chip being shown.
if pct_wk is not None and pct_wk >= 60 and rst_wk:
    try:
        import sys as _fg_sys
        _fg_sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
        import forecast_gap
        slug = os.path.basename(os.path.dirname(path))
        runway, _worked = forecast_gap.compute_runway(slug, pct_wk, rst_wk)
        chip = forecast_gap.format_chip(runway)
        if chip:
            cap_segments.append(chip)
    except Exception:
        pass

cap_str = (" · " + " · ".join(cap_segments)) if cap_segments else ""

turn_word = "turn" if turns == 1 else "turns"
print(f"{emoji} {turns} {turn_word} → {r_fmt} next turn{action_str}{err_flag}{cap_str}")
PYEOF
)

[ -z "$OUTPUT" ] && exit 0
printf '%s\n' "$OUTPUT" | tee "$CACHE"
