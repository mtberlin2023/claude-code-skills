#!/usr/bin/env python3
"""
Analogy-layer audit check.

Reads decisions.jsonl and reports on the four §16 proxy measures:
  1. Invocation count + cadence (decision-speed proxy)
  2. Frame-rejection rate (§8's distinctive claim)
  3. Component completeness — fraction shipping all four of
     (summary, mapping_table, simulation_prompt, limit_statement)
  4. Comfort-vs-quality split from outcome_label

Stdlib only. Python 3.10+.

Usage:
  python3 audit/check.py
  python3 audit/check.py --write
  python3 audit/check.py --since 2026-05-01
  python3 audit/check.py --pack construction
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "decisions.jsonl"
REPORT = HERE / "REPORT.md"

REQUIRED_COMPONENTS = ("summary", "mapping_table", "simulation_prompt", "limit_statement")


def load(since: str | None, pack: str | None) -> list[dict]:
    if not LOG.exists():
        return []
    since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc) if since else None
    out: list[dict] = []
    for line in LOG.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"WARN: skipping malformed line: {e}", file=sys.stderr)
            continue
        if since_dt:
            try:
                rec_dt = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if rec_dt < since_dt:
                continue
        if pack and rec.get("domain_used") != pack:
            continue
        out.append(rec)
    return out


def pct(n: int, total: int) -> str:
    return f"{(100 * n / total):.1f}%" if total else "n/a"


def summarise(records: list[dict]) -> str:
    n = len(records)
    if n == 0:
        return "No invocations logged. Run the skill, or add records by hand to decisions.jsonl."

    pack_counts = Counter(r.get("domain_used", "unknown") for r in records)
    trigger_counts: Counter[str] = Counter()
    for r in records:
        for t in r.get("trigger_conditions") or []:
            trigger_counts[t] += 1

    frame_rejected = sum(1 for r in records if r.get("frame_rejection"))
    flag_misleading = sum(1 for r in records if (r.get("user_feedback") or "").startswith("flag_misleading"))
    redo_any = sum(1 for r in records if (r.get("user_feedback") or "").startswith("redo"))
    locks = sum(1 for r in records if r.get("user_feedback") == "lock")

    complete = 0
    component_hits: Counter[str] = Counter()
    for r in records:
        comps = r.get("components") or {}
        if all(comps.get(k) for k in REQUIRED_COMPONENTS):
            complete += 1
        for k in REQUIRED_COMPONENTS:
            if comps.get(k):
                component_hits[k] += 1

    outcome_counts = Counter((r.get("outcome_label") or "unlabelled") for r in records)
    decision_class_counts = Counter((r.get("decision_class") or "unclassified") for r in records)

    ts_first = min((r.get("ts") for r in records if r.get("ts")), default=None)
    ts_last = max((r.get("ts") for r in records if r.get("ts")), default=None)

    lines: list[str] = []
    lines.append(f"# Analogy Audit — Rollup")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(f"Invocations: **{n}**  ·  First: {ts_first}  ·  Last: {ts_last}")
    lines.append("")
    lines.append("## §16-proxy 1 — Cadence")
    lines.append(f"Total invocations: **{n}**")
    if ts_first and ts_last and ts_first != ts_last:
        try:
            d_first = datetime.fromisoformat(ts_first.replace("Z", "+00:00"))
            d_last = datetime.fromisoformat(ts_last.replace("Z", "+00:00"))
            span_days = max((d_last - d_first).days, 1)
            lines.append(f"Span: {span_days} day(s)  ·  Mean rate: {n / span_days:.2f} invocations/day")
        except ValueError:
            pass
    lines.append("")
    lines.append("## §16-proxy 2 — Frame rejection")
    lines.append(f"Frame-rejected: **{frame_rejected}** of {n} ({pct(frame_rejected, n)})")
    lines.append(f"This is §8's most distinctive claim. n=1 cannot validate; n>20 starts to inform.")
    lines.append("")
    lines.append("## §16-proxy 3 — Component completeness")
    lines.append(f"Invocations shipping all four §15 components: **{complete}** of {n} ({pct(complete, n)})")
    lines.append("")
    lines.append("| Component | Hits | % |")
    lines.append("|---|---|---|")
    for k in REQUIRED_COMPONENTS:
        lines.append(f"| `{k}` | {component_hits[k]} | {pct(component_hits[k], n)} |")
    lines.append("")
    lines.append("## §16-proxy 4 — Comfort vs quality (post-hoc labels)")
    for label, count in sorted(outcome_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{label}` — {count} ({pct(count, n)})")
    lines.append("")
    lines.append("> Labels are post-hoc and self-reported. Comfort labels likely outnumber quality labels in real-world use; watch the distribution closely.")
    lines.append("")
    lines.append("## Pack distribution")
    for pack_name, count in sorted(pack_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{pack_name}` — {count} ({pct(count, n)})")
    lines.append("")
    lines.append("## Trigger conditions")
    for t, count in sorted(trigger_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{t}` — {count}")
    lines.append("")
    lines.append("## Decision class")
    for dc, count in sorted(decision_class_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{dc}` — {count}")
    lines.append("")
    lines.append("## Feedback verbs")
    lines.append(f"- `redo:*` — {redo_any}")
    lines.append(f"- `flag_misleading` — {flag_misleading}")
    lines.append(f"- `lock` — {locks}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**What this rollup does not tell you:** see `audit/README.md` § *What the audit cannot tell you*.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", help="ISO date filter")
    parser.add_argument("--pack", help="Filter by domain pack name")
    parser.add_argument("--write", action="store_true", help="Write rollup into REPORT.md")
    args = parser.parse_args()

    records = load(args.since, args.pack)
    report = summarise(records)

    if args.write:
        REPORT.write_text(report + "\n")
        print(f"Wrote {REPORT}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
