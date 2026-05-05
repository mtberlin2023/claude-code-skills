#!/usr/bin/env python3
"""
audit_weekly.py — time-sliced audit, ISO-week buckets.

Reuses analyse_session() from audit.py and adds:
  - per-session peak cache_read on a single assistant turn (proxy for max-R)
  - per-session first assistant turn cache_read (first-turn replay)
  - per-session tool_error count where the result payload exceeds 2KB
    (the long-session error-amnesty signal)

Then groups every session by the ISO week of its first_ts and prints a
week-by-week table. The point is to see whether early "whale" sessions are
distorting the all-time aggregate — and how the metrics have shifted week
on week.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit import analyse_session, parse_iso, fmt_num, PROJECTS_DIR, BASH_ERROR_RE  # noqa: E402


def extra_metrics(path: str) -> dict:
    """Second pass for things audit.py doesn't track."""
    asst_cache_reads: list[int] = []
    first_turn_cache = 0
    big_error_count = 0  # tool_results >2KB AND flagged as error
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
                if rtype == "assistant":
                    usage = rec.get("message", {}).get("usage", {}) or {}
                    cr = (usage.get("cache_read_input_tokens", 0) or 0)
                    asst_cache_reads.append(cr)
                elif rtype == "user":
                    content = rec.get("message", {}).get("content", "")
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") != "tool_result":
                                continue
                            bc = block.get("content", "")
                            if isinstance(bc, list):
                                bc = " ".join(
                                    c.get("text", "") if isinstance(c, dict) else str(c)
                                    for c in bc
                                )
                            if not isinstance(bc, str):
                                bc = str(bc)
                            if len(bc) > 2048 and (
                                block.get("is_error") or BASH_ERROR_RE.search(bc[:1000])
                            ):
                                big_error_count += 1
    except OSError:
        return {"peak_cache_read": 0, "first_turn_cache": 0, "big_error_count": 0}

    return {
        "peak_cache_read": max(asst_cache_reads) if asst_cache_reads else 0,
        "first_turn_cache": asst_cache_reads[0] if asst_cache_reads else 0,
        "big_error_count": big_error_count,
    }


def iso_week_key(ts: datetime) -> str:
    """Return 'YYYY-Www' for the ISO week of ts."""
    iso = ts.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_monday(week_key: str) -> str:
    """'YYYY-Www' → 'YYYY-MM-DD' (Monday) for display."""
    year_str, week_str = week_key.split("-W")
    monday = datetime.fromisocalendar(int(year_str), int(week_str), 1)
    return monday.date().isoformat()


def median(xs):
    return statistics.median(xs) if xs else 0


def p90(xs):
    if not xs:
        return 0
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * 0.9))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects-dir", default=PROJECTS_DIR)
    ap.add_argument("--project", default=None)
    ap.add_argument("--since", default=None, help="YYYY-MM-DD lower bound")
    args = ap.parse_args()

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
        since_dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)

    sessions = []
    for f in files:
        s = analyse_session(f)
        if not s:
            continue
        if not s.get("first_ts"):
            continue
        first = parse_iso(s["first_ts"])
        if since_dt and first < since_dt:
            continue
        s.update(extra_metrics(f))
        s["_first_dt"] = first
        sessions.append(s)

    if not sessions:
        print("No usable sessions found.", file=sys.stderr)
        sys.exit(1)

    # Bucket by ISO week
    by_week = defaultdict(list)
    for s in sessions:
        by_week[iso_week_key(s["_first_dt"])].append(s)

    weeks = sorted(by_week.keys())
    grand_total_cache = sum(s["cache_read"] for s in sessions)

    # Header
    print()
    print("Token Optimizer — Weekly Audit")
    print("==============================")
    print(f"Scanned: {len(sessions)} sessions, {len(weeks)} ISO weeks, "
          f"{sessions[0]['_first_dt'].date()} → {max(s['_first_dt'] for s in sessions).date()}")
    print(f"Aggregate cache reads (all-time, in window): {fmt_num(grand_total_cache)}")
    print()

    cols = (
        "week         start       sess  turns  cache_rd  out_tok  ratio  "
        "med_t  p90_t  top1%share  med_peak_R  med_first_R  big_errs  "
        "avg_upset  avg_idle"
    )
    print(cols)
    print("-" * len(cols))

    for wk in weeks:
        ws = by_week[wk]
        sess_n = len(ws)
        turns = sum(s["turns"] for s in ws)
        cache = sum(s["cache_read"] for s in ws)
        out = sum(s["output_tokens"] for s in ws)
        ratio = (cache / out) if out else 0
        med_t = median([s["turns"] for s in ws])
        p90_t = p90([s["turns"] for s in ws])
        # Concentration: share taken by the single biggest session that week
        biggest = max(s["cache_read"] for s in ws) if ws else 0
        top1_share = (biggest / cache * 100) if cache else 0
        med_peak = median([s["peak_cache_read"] for s in ws])
        med_first = median([s["first_turn_cache"] for s in ws])
        big_errs = sum(s["big_error_count"] for s in ws)
        # Avg upset / idle on sessions with ≥20 turns (audit.py vital-signs filter)
        big = [s for s in ws if s["turns"] >= 20]
        avg_upset = (sum(s["upset_pct"] for s in big) / len(big)) if big else 0
        avg_idle = (sum(s["idle_ratio"] for s in big) / len(big) * 100) if big else 0

        print(
            f"{wk:<12} {week_monday(wk):<11} {sess_n:>4} {turns:>6} "
            f"{fmt_num(cache):>9} {fmt_num(out):>8} {ratio:>5.0f}× "
            f"{int(med_t):>5} {int(p90_t):>5}  {top1_share:>8.0f}%  "
            f"{fmt_num(med_peak):>10} {fmt_num(med_first):>11} "
            f"{big_errs:>8} {avg_upset:>8.0f}% {avg_idle:>7.0f}%"
        )

    # Compare: drop top-N whales globally and re-aggregate
    print()
    print("Whale-removal sensitivity")
    print("-------------------------")
    whales_sorted = sorted(sessions, key=lambda s: s["cache_read"], reverse=True)
    for n in (0, 2, 5, 10, 20):
        rest = whales_sorted[n:]
        c = sum(s["cache_read"] for s in rest)
        o = sum(s["output_tokens"] for s in rest)
        r = (c / o) if o else 0
        share_dropped = (1 - c / grand_total_cache) * 100 if grand_total_cache else 0
        print(f"  drop top-{n:>2}: cache {fmt_num(c):>8}  out {fmt_num(o):>8}  "
              f"ratio {r:>4.0f}×   ({share_dropped:.0f}% of all cache reads removed)")

    print()
    print("Column key:")
    print("  med_peak_R   = median across sessions of (peak cache_read on a single asst turn).")
    print("                 Proxy for max-R the user faced before /log or split.")
    print("  med_first_R  = median first-assistant-turn cache_read. Spike here means the")
    print("                 session is starting heavy (CLAUDE.md / MCP / harness bloat).")
    print("  big_errs     = count of tool_results that were both >2KB AND flagged as errors.")
    print("                 These are the verbose tool-error payloads that get cached and")
    print("                 replayed forever (long-session error amnesty rule).")
    print("  top1%share   = % of the week's cache reads consumed by the single biggest session.")
    print()


if __name__ == "__main__":
    main()
