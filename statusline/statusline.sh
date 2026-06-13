#!/bin/bash
# Claude Code statusline — next-turn replay cost tracker
#
# Reads stdin JSON (Claude Code statusLine contract), outputs one line.
# Format: [emoji] [N] [Y]K next turn [· action] [· err] [· 5h cap] [· wk cap] [· runway]
# [N] is the turn count in brackets. We keep the count compact and omit the word "turns"
# because the headline cost number is the K tokens, not the turn count — turns are a weak
# proxy (a short heavy-context session can replay more per turn than a long lightweight one).
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
#   🚨 NN%·5h→HH:MM       — 5h burst cap, pct ≥ 90% (hard-crit only); reset time appended
#   📊 NN%·wk→Day HH:MM   — 7-day cap, pct ≥ 60%; reset time appended (calm icon,
#                           not a siren — 60% means "start budgeting", not crisis)
#   🕐 Xh working @ avg   — weekly runway in active Claude-hours at average burn.
#                           Shows when runway < 8h OR whenever the wk cap chip is
#                           up, so the cap % always travels with its hours-left
#                           context. Yellow <8h, red <3h. Integer ≥10h, 0.5-h below.
#
# Working-hours runway is the planning signal: when it drops below 8h, the user
# has limited working hours left before the wk cap at current burn rate and
# needs to budget effort. Above 8h there's enough headroom that the chip is
# noise. The chip is NOT gated against wall-clock distance to reset (that
# comparison was apples-to-oranges: active-hours runway vs wall-clock-hours;
# it over-fired whenever the user wasn't on Claude 100% of the wall window).
#
# Cap %·→reset chips fire at hard-crit (≥90% 5h, ≥60% wk). The 5h chip keeps
# the 🚨 siren (90% is a real crisis); the wk chip uses the calmer 📊 (60% is
# a budgeting nudge, not an emergency). The working-hours chip rides alongside
# the wk chip and also fires standalone below 8h runway. 5h burn rate uses a
# short rolling window (compute_5h_runway); wk burn rate is since-reset average
# (compute_runway).
#
# Reset times come from rate_limits.{five_hour,seven_day}.resets_at (unix seconds, local TZ).
# Silent on failure.
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
SMOOTH="/tmp/claude-statusline-${SESSION_ID}.smooth"
now=$(date +%s)

if [ -f "$CACHE" ]; then
  ts=$(stat -f%m "$CACHE" 2>/dev/null || stat -c%Y "$CACHE" 2>/dev/null || echo 0)
  if [ $((now - ts)) -lt 10 ]; then
    cat "$CACHE"
    exit 0
  fi
fi

ACTION="${CLAUDE_CODE_STATUSLINE_ACTION:-/log}"

OUTPUT=$(PCT_5H="$PCT_5H" PCT_WK="$PCT_WK" RST_5H="$RST_5H" RST_WK="$RST_WK" ACTION="$ACTION" SMOOTH_FILE="$SMOOTH" python3 - "$TRANSCRIPT" <<'PYEOF' 2>/dev/null
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

# Hysteresis smoothing — hold the displayed value steady until raw replay R
# drifts >12% (or >10K) from what's already on screen. Kills the per-poll /
# mid-turn jitter (the statusline recomputes every ~10s off the last assistant
# entry, so a long turn made the number crawl); a real move — context growth
# or a session rotation reset — still lands. State persists in a .smooth
# sidecar next to the 10s display cache. (Added 2026-05-19.)
r_display = r
smooth_path = os.environ.get('SMOOTH_FILE', '')
if smooth_path:
    prior = None
    try:
        with open(smooth_path) as sf:
            prior = int(sf.read().strip())
    except Exception:
        prior = None
    if prior is not None and prior > 0:
        band = max(prior * 0.12, 10_000)
        if abs(r - prior) <= band:
            r_display = prior
    try:
        with open(smooth_path, 'w') as sf:
            sf.write(str(r_display))
    except Exception:
        pass

r_fmt = fmt(r_display)
action = os.environ.get('ACTION', '/log')

if r_display < 200_000:
    emoji, action_str = "🟢", ""
elif r_display < 500_000:
    emoji, action_str = "🟡", f" · {action} after task"
elif r_display < 1_000_000:
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

HARD_CRIT_5H = 90.0
HARD_CRIT_WK = 60.0

now_ts = time.time()

forecast_gap = None
slug = os.path.basename(os.path.dirname(path))
try:
    import sys as _fg_sys
    _fg_sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))
    import forecast_gap  # noqa: F811
except Exception:
    forecast_gap = None

cap_segments = []

# 5h cap chip — hard-crit only.
if pct_5h is not None and pct_5h >= HARD_CRIT_5H:
    rs = fmt_reset_short(rst_5h)
    suffix = f"→{rs}" if rs else ""
    cap_segments.append(f"🚨 {int(pct_5h)}%·5h{suffix}")

# wk cap chip — fires at HARD_CRIT_WK (60%). Calm 📊 icon, not the 🚨 siren:
# at 60% of the weekly budget you're being told to start budgeting, not that
# anything is burning. (The 5h chip above keeps 🚨 — that only fires at 90%.)
wk_cap_showing = pct_wk is not None and pct_wk >= HARD_CRIT_WK
if wk_cap_showing:
    rs = fmt_reset_long(rst_wk)
    suffix = f"→{rs}" if rs else ""
    cap_segments.append(f"📊 {int(pct_wk)}%·wk{suffix}")

# wk runway chip — the working-hours planning signal. Shows when runway drops
# below the 8h threshold OR whenever the wk cap chip is up, so the cap % always
# travels with its "N working-hours left @ avg" context (it's no use being told
# you're at 62% if you can't see you've still got 20h of runway). Colour tiers
# unchanged: yellow <8h, red <3h, neutral above. We widened *when* it appears,
# not the thresholds.
WK_RUNWAY_THRESHOLD = 8.0
runway_wk = None
if pct_wk is not None and forecast_gap is not None and rst_wk:
    try:
        runway_wk, _ = forecast_gap.compute_runway(slug, pct_wk, rst_wk)
    except Exception:
        runway_wk = None

if forecast_gap is not None and runway_wk is not None and (runway_wk < WK_RUNWAY_THRESHOLD or wk_cap_showing):
    try:
        chip = forecast_gap.format_chip(runway_wk)
        if chip:
            cap_segments.append(chip)
    except Exception:
        pass

cap_str = (" · " + " · ".join(cap_segments)) if cap_segments else ""

print(f"{emoji} [{turns}] {r_fmt} next turn{action_str}{err_flag}{cap_str}")
PYEOF
)

[ -z "$OUTPUT" ] && exit 0
printf '%s\n' "$OUTPUT" | tee "$CACHE"
