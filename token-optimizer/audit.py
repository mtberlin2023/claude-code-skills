#!/usr/bin/env python3
"""
token-optimizer / audit.py

Reads ~/.claude/projects/*/*.jsonl and prints a per-project + aggregate report:
sessions, turns, output tokens, cache reads, top whales by cache reads, and a
crude upset% / bash-error% per session for the worst N.

No external dependencies. Read-only — never modifies your logs.

Usage:
    python3 audit.py                       # default: scan everything
    python3 audit.py --project myproj      # one project folder only
    python3 audit.py --top 5               # show top 5 whales (default 10)
    python3 audit.py --json                # machine-readable output
    python3 audit.py --since 2026-04-01    # only sessions starting on/after date

Companion to the white paper:
  Self-Discovered Token Efficiency: One Heavy User's 30-Day Audit of Claude Code
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")

UPSET_RE = re.compile(
    r"\b(broken|broke|doesn'?t work|not working|stuck|fail(?:s|ed|ing)?|"
    r"error|bug|fix(?:es|ed|ing)?|wrong|weird|why is|nope|undo|revert)\b",
    re.IGNORECASE,
)
BASH_ERROR_RE = re.compile(
    r"(error|traceback|command not found|no such file or directory|permission denied)",
    re.IGNORECASE,
)


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        # Claude Code timestamps are usually ISO8601 with 'Z'
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def analyse_session(path: str) -> dict | None:
    """Read one .jsonl session file and return per-session metrics."""
    user_msgs: list[dict] = []           # all user records (matches paper's "turns" count)
    text_user_msgs: list[dict] = []      # only those with real text content (used for upset%)
    asst_msgs: list[dict] = []
    tool_results_total = 0
    tool_results_errors = 0
    cache_read = 0
    cache_write = 0
    output_tokens = 0
    uncached_input = 0

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rtype = rec.get("type")
                if rtype == "user":
                    content = rec.get("message", {}).get("content", "")
                    user_msgs.append({"ts": rec.get("timestamp")})
                    if isinstance(content, list):
                        # Walk content blocks: count tool_results, extract text.
                        text_blocks: list[str] = []
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            btype = block.get("type")
                            if btype == "tool_result":
                                tool_results_total += 1
                                bc = block.get("content", "")
                                if isinstance(bc, list):
                                    bc = " ".join(
                                        c.get("text", "") if isinstance(c, dict) else str(c)
                                        for c in bc
                                    )
                                if not isinstance(bc, str):
                                    bc = str(bc)
                                if block.get("is_error") or BASH_ERROR_RE.search(bc[:1000]):
                                    tool_results_errors += 1
                            elif btype == "text":
                                t = block.get("text", "")
                                if isinstance(t, str):
                                    text_blocks.append(t)
                        text = " ".join(text_blocks).strip()
                        if text and not text.startswith("<"):
                            text_user_msgs.append({"ts": rec.get("timestamp"), "text": text})
                    elif isinstance(content, str):
                        if content.strip() and not content.lstrip().startswith("<"):
                            text_user_msgs.append({"ts": rec.get("timestamp"), "text": content})
                elif rtype == "assistant":
                    asst_msgs.append({"ts": rec.get("timestamp")})
                    usage = rec.get("message", {}).get("usage", {}) or {}
                    cache_read += usage.get("cache_read_input_tokens", 0) or 0
                    cache_write += usage.get("cache_creation_input_tokens", 0) or 0
                    output_tokens += usage.get("output_tokens", 0) or 0
                    uncached_input += usage.get("input_tokens", 0) or 0
    except OSError:
        return None

    if not user_msgs and not asst_msgs:
        return None

    # Wall clock + active compute time (cap idle gaps at 2h)
    all_ts = sorted(
        filter(None, (parse_iso(m.get("ts")) for m in user_msgs + asst_msgs))
    )
    wall_clock_h = 0.0
    if len(all_ts) >= 2:
        wall_clock_h = (all_ts[-1] - all_ts[0]).total_seconds() / 3600.0

    active_h = 0.0
    if len(all_ts) >= 2:
        for a, b in zip(all_ts, all_ts[1:]):
            gap = (b - a).total_seconds()
            if gap < 7200:  # 2h cap on idle gaps
                active_h += gap / 3600.0

    idle_ratio = (wall_clock_h - active_h) / wall_clock_h if wall_clock_h > 0 else 0.0

    # Upset percentage — measured against text-bearing user messages only,
    # so tool-result echoes don't dilute the denominator.
    upset_count = sum(1 for m in text_user_msgs if UPSET_RE.search(m["text"]))
    upset_pct = (upset_count / len(text_user_msgs)) if text_user_msgs else 0.0

    # Bash / tool error rate (rough — counts tool_results flagged as errors)
    bash_err_pct = (tool_results_errors / tool_results_total) if tool_results_total else 0.0

    return {
        "path": path,
        "session": os.path.basename(path),
        "project": os.path.basename(os.path.dirname(path)),
        "turns": len(user_msgs),
        "asst_turns": len(asst_msgs),
        "first_ts": all_ts[0].isoformat() if all_ts else None,
        "last_ts": all_ts[-1].isoformat() if all_ts else None,
        "wall_clock_h": round(wall_clock_h, 1),
        "active_h": round(active_h, 1),
        "idle_ratio": round(idle_ratio, 2),
        "cache_read": cache_read,
        "cache_write": cache_write,
        "output_tokens": output_tokens,
        "uncached_input": uncached_input,
        "upset_pct": round(upset_pct * 100, 1),
        "bash_err_pct": round(bash_err_pct * 100, 1),
        "tool_calls": tool_results_total,
        "tool_errors": tool_results_errors,
    }


def fmt_num(n: int | float) -> str:
    if n >= 1e9:
        return f"{n/1e9:.2f} B"
    if n >= 1e6:
        return f"{n/1e6:.1f} M"
    if n >= 1e3:
        return f"{n/1e3:.1f} K"
    return str(int(n))


def main():
    ap = argparse.ArgumentParser(description="Audit Claude Code session logs.")
    ap.add_argument("--projects-dir", default=PROJECTS_DIR,
                    help=f"Path to projects dir (default {PROJECTS_DIR})")
    ap.add_argument("--project", default=None,
                    help="Limit scan to one project folder name")
    ap.add_argument("--top", type=int, default=10,
                    help="How many whale sessions to show (default 10)")
    ap.add_argument("--since", default=None,
                    help="Only sessions whose first timestamp is on/after YYYY-MM-DD")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON instead of a human report")
    ap.add_argument("--chart", default=None, metavar="DIR",
                    help="Emit chart datasets as CSV into DIR (no plotting; "
                         "stays zero-dependency). Writes session_histogram.csv "
                         "and per_turn_replay.csv.")
    ap.add_argument("--forecast-args", action="store_true",
                    help="Emit calibration inputs for the /forecast skill as "
                         "key=value lines (one per line). See "
                         "_shared/process/audit-forecast-contract.md. "
                         "Silent on empty data — widget falls back to defaults.")
    args = ap.parse_args()

    if not os.path.isdir(args.projects_dir):
        print(f"Projects dir not found: {args.projects_dir}", file=sys.stderr)
        print("Is Claude Code installed and have you run at least one session?", file=sys.stderr)
        sys.exit(1)

    pattern = (
        os.path.join(args.projects_dir, args.project, "*.jsonl")
        if args.project
        else os.path.join(args.projects_dir, "*", "*.jsonl")
    )
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"No .jsonl files matched: {pattern}", file=sys.stderr)
        sys.exit(1)

    since_dt = None
    if args.since:
        try:
            since_dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"Bad --since date: {args.since} (expected YYYY-MM-DD)", file=sys.stderr)
            sys.exit(1)

    sessions: list[dict] = []
    for f in files:
        s = analyse_session(f)
        if not s:
            continue
        if since_dt and s["first_ts"]:
            first = parse_iso(s["first_ts"])
            if first and first < since_dt:
                continue
        sessions.append(s)

    if not sessions:
        print("No usable sessions found in window.", file=sys.stderr)
        sys.exit(1)

    # Aggregate
    total_turns = sum(s["turns"] for s in sessions)
    total_output = sum(s["output_tokens"] for s in sessions)
    total_cread = sum(s["cache_read"] for s in sessions)
    total_cwrite = sum(s["cache_write"] for s in sessions)
    total_uncached = sum(s["uncached_input"] for s in sessions)
    total_active_h = sum(s["active_h"] for s in sessions)
    avg_turns = total_turns / len(sessions)
    project_count = len(set(s["project"] for s in sessions))

    first_ts = min(filter(None, (s["first_ts"] for s in sessions)))
    last_ts = max(filter(None, (s["last_ts"] for s in sessions)))

    # Top whales by cache reads
    whales = sorted(sessions, key=lambda s: s["cache_read"], reverse=True)[: args.top]
    whale_share = sum(w["cache_read"] for w in whales) / total_cread if total_cread else 0

    # Vital signs averaged across worst N (by upset+bash_err combined).
    # Filter out tiny sessions where 1-of-1 user messages can blow the metric up to 100%.
    vital_pool = [s for s in sessions if s["turns"] >= 20]
    vital = sorted(
        vital_pool,
        key=lambda s: s["upset_pct"] + s["bash_err_pct"],
        reverse=True,
    )[: args.top]
    avg_upset = sum(v["upset_pct"] for v in vital) / len(vital) if vital else 0
    avg_bash_err = sum(v["bash_err_pct"] for v in vital) / len(vital) if vital else 0

    if args.forecast_args:
        # Calibration emitter for the /forecast skill.
        # Contract: _shared/process/audit-forecast-contract.md
        # Output is key=value lines, stable format, designed for shell
        # consumption (awk -F=) and for the Control Panel widget.
        by_date: dict[str, float] = defaultdict(float)
        for s in sessions:
            first = parse_iso(s.get("first_ts") or "")
            if not first:
                continue
            by_date[first.date().isoformat()] += s.get("active_h", 0.0)

        # /forecast wants "typical hours per working day" in the human sense —
        # wall-clock span from first to last Claude interaction on each worked
        # day. Summed active_h overcounts when sessions run in parallel (can
        # hit 20+ h on a single calendar day). Span is closer to "how long
        # you're at the keyboard" which is the unit the skill expects.
        day_spans: dict[str, list] = defaultdict(list)
        for s in sessions:
            first = parse_iso(s.get("first_ts") or "")
            last = parse_iso(s.get("last_ts") or "")
            if not first or not last:
                continue
            # A session crossing midnight is rare but assign by start date.
            day_spans[first.date().isoformat()].append((first, last))

        daily_span_hours: list[float] = []
        for _, spans in day_spans.items():
            earliest = min(f for f, _ in spans)
            latest = max(l for _, l in spans)
            span_h = (latest - earliest).total_seconds() / 3600.0
            if 0.2 < span_h < 22:    # drop trivially short days + sessions that cross calendar boundary
                daily_span_hours.append(span_h)

        daily_span_hours.sort()
        if not daily_span_hours:
            # Silent on no data — widget should fall back to defaults.
            return
        median_daily = daily_span_hours[len(daily_span_hours) // 2]

        # Keep sum-of-active-h as a second signal so the widget can show both
        # if it wants. Same filter logic, excludes rest days.
        daily_active_sum = sorted(h for h in by_date.values() if h > 0.1)
        median_active_sum = (daily_active_sum[len(daily_active_sum) // 2]
                             if daily_active_sum else 0.0)

        session_hours = sorted(s["active_h"] for s in sessions if s["active_h"] > 0.05)
        median_session = session_hours[len(session_hours) // 2] if session_hours else 0.0

        now_utc = datetime.now(timezone.utc)
        from datetime import timedelta
        seven_days_ago = now_utc - timedelta(days=7)
        last_7d = [s for s in sessions
                   if parse_iso(s.get("first_ts") or "") and
                   parse_iso(s["first_ts"]) >= seven_days_ago]
        last_7d_active = sum(s.get("active_h", 0.0) for s in last_7d)
        last_7d_cache = sum(s.get("cache_read", 0) for s in last_7d)

        print(f"suggested_hours_per_day={median_daily:.1f}")
        print(f"median_daily_active_sum={median_active_sum:.1f}")
        print(f"median_session_active_hours={median_session:.1f}")
        print(f"last_7d_active_hours={last_7d_active:.1f}")
        print(f"last_7d_sessions={len(last_7d)}")
        print(f"last_7d_cache_reads={last_7d_cache}")
        print(f"data_worked_days={len(daily_span_hours)}")
        return

    if args.chart:
        os.makedirs(args.chart, exist_ok=True)

        # Dataset 1: session-length histogram
        # Buckets match the paper's section 5 framing.
        buckets = [
            ("0-25",     0,    25),
            ("25-100",   25,   100),
            ("100-200",  100,  200),
            ("200-500",  200,  500),
            ("500+",     500,  10**9),
        ]
        counts = [0] * len(buckets)
        whale_counts = [0] * len(buckets)
        # Whale threshold = top ~2.7% of sessions by cache reads (paper §5).
        n_whales = max(1, int(round(len(sessions) * 0.027)))
        whale_paths = {w["path"] for w in
                       sorted(sessions, key=lambda s: s["cache_read"], reverse=True)[:n_whales]}
        for s in sessions:
            t = s["turns"]
            for i, (_, lo, hi) in enumerate(buckets):
                if lo <= t < hi:
                    counts[i] += 1
                    if s["path"] in whale_paths:
                        whale_counts[i] += 1
                    break

        hist_path = os.path.join(args.chart, "session_histogram.csv")
        with open(hist_path, "w", encoding="utf-8") as f:
            f.write("bucket,sessions,whales\n")
            for (label, _, _), n, w in zip(buckets, counts, whale_counts):
                f.write(f"{label},{n},{w}\n")

        # Dataset 2: per-turn cache replay curve.
        # First-order model from §8: ~3K new tokens per turn, replayed cumulatively.
        # Replayed at turn N ≈ 3K * N. We emit a sparse log-spaced sweep 1..1000.
        replay_path = os.path.join(args.chart, "per_turn_replay.csv")
        per_turn_new_tokens = 3000
        with open(replay_path, "w", encoding="utf-8") as f:
            f.write("turn,replay_tokens\n")
            for n in [1, 5, 10, 20, 50, 100, 150, 200, 300, 500, 750, 1000]:
                f.write(f"{n},{per_turn_new_tokens * n}\n")

        print(f"Wrote {hist_path}")
        print(f"Wrote {replay_path}")
        return

    if args.json:
        print(json.dumps({
            "scanned_dir": args.projects_dir,
            "first_ts": first_ts,
            "last_ts": last_ts,
            "sessions": len(sessions),
            "projects": project_count,
            "totals": {
                "turns": total_turns,
                "output_tokens": total_output,
                "cache_reads": total_cread,
                "cache_writes": total_cwrite,
                "uncached_input": total_uncached,
                "active_hours": round(total_active_h, 1),
            },
            "avg_turns_per_session": round(avg_turns, 1),
            "top_whales": whales,
            "vital_signs_worst": {
                "avg_upset_pct": round(avg_upset, 1),
                "avg_bash_err_pct": round(avg_bash_err, 1),
            },
        }, indent=2, default=str))
        return

    # Human report
    print()
    print("Token Optimizer — Audit")
    print("========================")
    print(f"Scanned: {args.projects_dir}  ({project_count} project folders, {len(sessions)} sessions)")
    print(f"Window:  {first_ts[:10]} → {last_ts[:10]}")
    print()
    print("Aggregate")
    print("---------")
    print(f"Sessions:                 {len(sessions):>10}")
    print(f"User→assistant turns:     {total_turns:>10,}")
    print(f"Output tokens:            {fmt_num(total_output):>10}")
    print(f"Cache reads:              {fmt_num(total_cread):>10}   ← cost driver")
    print(f"Cache writes:             {fmt_num(total_cwrite):>10}")
    print(f"Uncached input:           {fmt_num(total_uncached):>10}")
    print(f"Active Claude time:       {total_active_h:>9.1f} h")
    print(f"Avg turns / session:      {avg_turns:>10.0f}")
    if total_output:
        print(f"Cache-read : output ratio: {total_cread/total_output:>9.0f} ×")
    print()
    print(f"Top {len(whales)} whales (by cache reads)")
    print("-" * 40)
    for i, w in enumerate(whales, 1):
        print(f" {i:>2}. {w['project'][:24]:<24} {w['turns']:>5} turns  "
              f"{w['wall_clock_h']:>5.1f} h wall  "
              f"{w['active_h']:>4.1f} h active  "
              f"{int(w['idle_ratio']*100):>3}% idle  "
              f"cache {fmt_num(w['cache_read'])}")
    print()
    print(f"Top {len(whales)} sessions = {whale_share*100:.0f}% of all cache reads.")
    print()
    print(f"Vital signs (worst {len(vital)} sessions by upset+bash error)")
    print("-" * 40)
    print(f"  Avg upset %:        {avg_upset:>4.0f}%   (>20% is bug-spiral territory)")
    print(f"  Avg bash error %:   {avg_bash_err:>4.0f}%   (>30% is a tooling fight)")
    print()

    # Crude projected savings: if all whales were split into 100-turn pieces, the
    # quadratic cost curve flattens. Approximate: a 1000-turn session has ~10×
    # the cumulative cache cost of ten 100-turn sessions doing the same work.
    if whales and total_cread:
        whale_total = sum(w["cache_read"] for w in whales)
        # Crude: assume splitting cuts cumulative replay by (1 - 1/N) where N is the
        # split factor (turns/100, capped at 10). Bounded saving estimate.
        est_saving = 0
        for w in whales:
            split_factor = max(1, min(10, w["turns"] // 100))
            if split_factor > 1:
                est_saving += w["cache_read"] * (1 - 1.0 / split_factor)
        pct = est_saving / total_cread * 100
        print(f"Estimated savings if top {len(whales)} whales had been split into 100-turn sessions:")
        print(f"  ~{pct:.0f}% reduction in cache reads (rough estimate)")
        print()

    print("Reading these results: see the companion white paper, sections 4–8.")
    print()


if __name__ == "__main__":
    main()
