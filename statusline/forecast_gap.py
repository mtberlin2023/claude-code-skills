"""
Compute remaining weekly-budget runway in active Claude-work hours.

Scans ~/.claude/projects/<slug>/*.jsonl for event timestamps since the last
weekly reset, groups them into active blocks with a 10-min gap rule, derives
burn rate from %used, returns:

    remaining_runway_hours = (100 - %used) / burn_rate
    burn_rate              = %used / active_hours_worked_since_reset

Cached at ~/.claude/hooks/.forecast-cache.json keyed by (project_slug,
reset_epoch), 5-min TTL. Silent on any failure — statusline must never crash
because of this module.

Called from statusline.sh when the weekly %wk chip is rendered (pct_wk >= 60).
"""

import json
import time
from datetime import datetime
from pathlib import Path

CACHE_PATH = Path.home() / ".claude" / "hooks" / ".forecast-cache.json"
CACHE_TTL_SECONDS = 300
GAP_SECONDS = 600  # 10-min gap rule for active-block detection
WEEK_SECONDS = 7 * 86400


def _iter_event_timestamps(project_slug, since_epoch):
    base = Path.home() / ".claude" / "projects" / project_slug
    if not base.is_dir():
        return
    for path in base.glob("*.jsonl"):
        try:
            with path.open() as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    ts = ev.get("timestamp")
                    if not ts:
                        continue
                    try:
                        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        continue
                    ep = dt.timestamp()
                    if ep >= since_epoch:
                        yield ep
        except OSError:
            continue


def _active_hours(project_slug, since_epoch):
    timestamps = sorted(_iter_event_timestamps(project_slug, since_epoch))
    if not timestamps:
        return 0.0
    total = 0.0
    block_start = timestamps[0]
    last = timestamps[0]
    for t in timestamps[1:]:
        if t - last > GAP_SECONDS:
            total += last - block_start
            block_start = t
        last = t
    total += last - block_start
    return total / 3600.0


def _load_cache():
    try:
        with CACHE_PATH.open() as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(data):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(data, f)
        tmp.replace(CACHE_PATH)
    except OSError:
        pass


def compute_runway(project_slug, pct_used, reset_epoch):
    """Returns (runway_hours_or_None, active_hours_worked)."""
    try:
        pct_used = float(pct_used)
        reset_epoch = float(reset_epoch)
    except (TypeError, ValueError):
        return None, 0.0

    cache_key = f"{project_slug}:{int(reset_epoch)}"
    cache = _load_cache()
    now = time.time()
    entry = cache.get(cache_key)
    if isinstance(entry, dict) and (now - entry.get("cached_at", 0)) < CACHE_TTL_SECONDS:
        return entry.get("runway"), entry.get("worked", 0.0)

    window_start = reset_epoch - WEEK_SECONDS
    worked = _active_hours(project_slug, window_start)

    if worked < 0.1 or pct_used <= 0:
        runway = None
    elif pct_used >= 100:
        runway = 0.0
    else:
        burn_rate = pct_used / worked  # % per active hour
        runway = (100.0 - pct_used) / burn_rate if burn_rate > 0 else None

    cache[cache_key] = {"runway": runway, "worked": worked, "cached_at": now}
    _save_cache(cache)
    return runway, worked


def format_chip(runway, colour=True):
    """Return the chip text (with optional ANSI colour), or None if undefined.

    Display: integer hours above 10h; 0.5-hour increments below 10h
    (finer precision is not behaviourally meaningful for work-time
    allocation). Suffix `@ avg` = remaining active hours at the average
    weekly burn rate.
    """
    if runway is None:
        return None

    if runway < 3:
        colour_class = "red"
    elif runway < 10:
        colour_class = "yellow"
    else:
        colour_class = "neutral"

    if runway >= 10:
        raw = f"\U0001F550 {int(round(runway))}h @ avg"
    else:
        half_steps = round(runway * 2)
        rounded = half_steps / 2
        if rounded <= 0:
            raw = "\U0001F550 0h @ avg"
        elif half_steps % 2 == 0:
            raw = f"\U0001F550 {int(rounded)}h @ avg"
        else:
            raw = f"\U0001F550 {rounded}h @ avg"

    if not colour or colour_class == "neutral":
        return raw
    if colour_class == "red":
        return f"\033[31m{raw}\033[0m"
    return f"\033[33m{raw}\033[0m"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("usage: forecast_gap.py <project_slug> <pct_used> <reset_epoch>", file=sys.stderr)
        sys.exit(2)
    slug = sys.argv[1]
    pct = sys.argv[2]
    reset = sys.argv[3]
    runway, worked = compute_runway(slug, pct, reset)
    chip = format_chip(runway, colour=False)
    print(f"worked={worked:.2f}h runway={runway}", file=sys.stderr)
    if chip:
        print(chip)
