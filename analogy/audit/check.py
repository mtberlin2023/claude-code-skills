#!/usr/bin/env python3
"""
Analogy-layer audit check (v1.1 schema).

Reads decisions.jsonl and reports on:
  - The §16 proxy measures (cadence, frame-rejection, component completeness,
    outcome labels)
  - The 7-class signal taxonomy from §15A's feedback loop, extended
  - The five-condition validation gate (v1.1 records only)

Backward compat: records without `schema_version` or with `schema_version: "1.0"`
are treated as v1.0 and excluded from the v1.1 gate metrics. They still count
toward cadence and pack distribution.

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

V1_1_COMPONENTS = (
    "summary",
    "mapping_table",
    "simulation_prompt",
    "limit_statement",
    "mislead_tag",
    "second_opinion_pass",
)
V1_0_COMPONENTS = (
    "summary",
    "mapping_table",
    "simulation_prompt",
    "limit_statement",
)

# user_feedback string → signal class. Class 3 is post-hoc only (see outcome_label).
FEEDBACK_TO_CLASS = {
    "flag_unfamiliar": 1,
    "flag_misleading": 2,
    "flag_bleed": 4,
    "drop_analogy": 5,
    "lock": 7,
}
# `redo:<domain>` and `redo_scale:<scale>` both map to class 6 (sub-mode / scale mismatch)
REDO_PREFIXES = ("redo:", "redo_scale:")

CLASS_LABELS = {
    1: "unfamiliar (didn't clarify)",
    2: "misleading (wrong inference)",
    3: "false-confident (post-hoc)",
    4: "substrate bleed",
    5: "analogy capture (didn't need one)",
    6: "sub-mode / scale mismatch",
    7: "worked — locked",
}

# v1.1 validation-gate thresholds. Adjust here if you want to tune the gate.
GATE_MIN_N = 40
GATE_CLASS_7_MIN_PCT = 30.0
GATE_CLASS_2_3_MAX_PCT = 15.0
GATE_CLASS_5_MAX_PCT = 10.0
GATE_FRAME_REJECTION_MIN_PCT = 15.0
GATE_COMPONENTS_MIN_PCT = 80.0


def schema_version(rec: dict) -> str:
    return str(rec.get("schema_version") or "1.0")


def feedback_class(rec: dict) -> int | None:
    """Map a record's feedback or outcome label to a signal class 1-7, or None."""
    fb = rec.get("user_feedback") or ""
    if fb in FEEDBACK_TO_CLASS:
        return FEEDBACK_TO_CLASS[fb]
    if any(fb.startswith(p) for p in REDO_PREFIXES):
        return 6
    if rec.get("outcome_label") == "false_confident":
        return 3
    return None


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


def gate_line(name: str, value_pct: float, threshold: float, min_or_max: str, passed: bool) -> str:
    marker = "✓ PASS" if passed else "✗ FAIL"
    op = "≥" if min_or_max == "min" else "≤"
    return f"- **{name}** — {value_pct:.1f}% (gate: {op} {threshold:.0f}%) — {marker}"


def summarise(records: list[dict]) -> str:
    n = len(records)
    if n == 0:
        return "No invocations logged. Run the skill, or add records by hand to decisions.jsonl."

    v1_1 = [r for r in records if schema_version(r) == "1.1"]
    v1_0 = [r for r in records if schema_version(r) != "1.1"]
    n_v11 = len(v1_1)
    n_v10 = len(v1_0)

    pack_counts = Counter(r.get("domain_used", "unknown") for r in records)
    register_counts = Counter((r.get("register") or "unrecorded") for r in records)
    trigger_counts: Counter[str] = Counter()
    for r in records:
        for t in r.get("trigger_conditions") or []:
            trigger_counts[t] += 1

    frame_rejected_all = sum(1 for r in records if r.get("frame_rejection"))
    frame_rejected_v11 = sum(1 for r in v1_1 if r.get("frame_rejection"))

    complete_v11 = 0
    component_hits_v11: Counter[str] = Counter()
    for r in v1_1:
        comps = r.get("components") or {}
        if all(comps.get(k) for k in V1_1_COMPONENTS):
            complete_v11 += 1
        for k in V1_1_COMPONENTS:
            if comps.get(k):
                component_hits_v11[k] += 1

    class_counts_v11: Counter[int] = Counter()
    for r in v1_1:
        c = feedback_class(r)
        if c is not None:
            class_counts_v11[c] += 1

    outcome_counts = Counter((r.get("outcome_label") or "unlabelled") for r in records)
    decision_class_counts = Counter((r.get("decision_class") or "unclassified") for r in records)

    ts_first = min((r.get("ts") for r in records if r.get("ts")), default=None)
    ts_last = max((r.get("ts") for r in records if r.get("ts")), default=None)

    lines: list[str] = []
    lines.append("# Analogy Audit — Rollup")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(f"Invocations: **{n}** total  ·  v1.1: **{n_v11}**  ·  v1.0 legacy: **{n_v10}**")
    lines.append(f"First: {ts_first}  ·  Last: {ts_last}")
    lines.append("")

    # ─── v1.1 validation gate ────────────────────────────────────────────
    lines.append("## v1.1 Validation gate")
    if n_v11 == 0:
        lines.append("_No v1.1 records yet. Gate cannot evaluate._")
        lines.append("")
    else:
        c2 = class_counts_v11[2]
        c3 = class_counts_v11[3]
        c5 = class_counts_v11[5]
        c7 = class_counts_v11[7]
        c23 = c2 + c3

        c7_pct = 100.0 * c7 / n_v11
        c23_pct = 100.0 * c23 / n_v11
        c5_pct = 100.0 * c5 / n_v11
        frame_pct = 100.0 * frame_rejected_v11 / n_v11
        comp_pct = 100.0 * complete_v11 / n_v11

        sample_pass = n_v11 >= GATE_MIN_N
        c7_pass = c7_pct >= GATE_CLASS_7_MIN_PCT
        c23_pass = c23_pct <= GATE_CLASS_2_3_MAX_PCT
        c5_pass = c5_pct <= GATE_CLASS_5_MAX_PCT
        frame_pass = frame_pct >= GATE_FRAME_REJECTION_MIN_PCT
        comp_pass = comp_pct >= GATE_COMPONENTS_MIN_PCT

        all_pass = all((sample_pass, c7_pass, c23_pass, c5_pass, frame_pass, comp_pass))

        marker = "✓ PASS" if sample_pass else "✗ FAIL"
        lines.append(f"- **Sample size** — {n_v11} of {GATE_MIN_N} required — {marker}")
        lines.append(gate_line("Class 7 (worked, locked)", c7_pct, GATE_CLASS_7_MIN_PCT, "min", c7_pass))
        lines.append(gate_line("Class 2 + 3 (misleading + false-confident)", c23_pct, GATE_CLASS_2_3_MAX_PCT, "max", c23_pass))
        lines.append(gate_line("Class 5 (analogy capture)", c5_pct, GATE_CLASS_5_MAX_PCT, "max", c5_pass))
        lines.append(gate_line("Frame-rejection rate", frame_pct, GATE_FRAME_REJECTION_MIN_PCT, "min", frame_pass))
        lines.append(gate_line("Component completeness (all 6)", comp_pct, GATE_COMPONENTS_MIN_PCT, "min", comp_pass))
        lines.append("")
        verdict = "✓ PASS — ready for public push" if all_pass else "✗ FAIL — continue dogfood"
        lines.append(f"**Overall gate:** {verdict}")
        lines.append("")

    # ─── 7-class signal taxonomy histogram ───────────────────────────────
    lines.append("## 7-class signal taxonomy (v1.1 records only)")
    if n_v11 == 0:
        lines.append("_No v1.1 records yet._")
    else:
        lines.append("")
        lines.append("| Class | Label | Count | % of v1.1 |")
        lines.append("|---|---|---|---|")
        for cls in range(1, 8):
            count = class_counts_v11[cls]
            lines.append(f"| {cls} | {CLASS_LABELS[cls]} | {count} | {pct(count, n_v11)} |")
        unlabelled = n_v11 - sum(class_counts_v11.values())
        lines.append(f"| — | (no feedback / no class label) | {unlabelled} | {pct(unlabelled, n_v11)} |")
    lines.append("")

    # ─── §16 proxies ─────────────────────────────────────────────────────
    lines.append("## §16-proxy — Cadence")
    lines.append(f"Total invocations: **{n}** ({n_v11} v1.1, {n_v10} v1.0 legacy)")
    if ts_first and ts_last and ts_first != ts_last:
        try:
            d_first = datetime.fromisoformat(ts_first.replace("Z", "+00:00"))
            d_last = datetime.fromisoformat(ts_last.replace("Z", "+00:00"))
            span_days = max((d_last - d_first).days, 1)
            lines.append(f"Span: {span_days} day(s)  ·  Mean rate: {n / span_days:.2f} invocations/day")
        except ValueError:
            pass
    lines.append("")
    lines.append("## §16-proxy — Frame rejection")
    lines.append(f"All records: **{frame_rejected_all}** of {n} ({pct(frame_rejected_all, n)})")
    lines.append(f"v1.1 only: **{frame_rejected_v11}** of {n_v11} ({pct(frame_rejected_v11, n_v11)})")
    lines.append("")
    lines.append("## §16-proxy — Component completeness (v1.1 records)")
    lines.append(f"Invocations shipping all six v1.1 components: **{complete_v11}** of {n_v11} ({pct(complete_v11, n_v11)})")
    if n_v11:
        lines.append("")
        lines.append("| Component | Hits (v1.1) | % |")
        lines.append("|---|---|---|")
        for k in V1_1_COMPONENTS:
            lines.append(f"| `{k}` | {component_hits_v11[k]} | {pct(component_hits_v11[k], n_v11)} |")
    lines.append("")
    lines.append("## §16-proxy — Comfort vs quality (post-hoc labels)")
    for label, count in sorted(outcome_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{label}` — {count} ({pct(count, n)})")
    lines.append("")
    lines.append("> Labels are post-hoc and self-reported. Comfort labels likely outnumber quality labels in real-world use; watch the distribution.")
    lines.append("")
    lines.append("## Pack distribution")
    for pack_name, count in sorted(pack_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{pack_name}` — {count} ({pct(count, n)})")
    lines.append("")
    lines.append("## Register distribution")
    for reg_name, count in sorted(register_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{reg_name}` — {count} ({pct(count, n)})")
    lines.append("")
    lines.append("> Register-balance proxy (added 2026-05-24). A pack skewing hard to one register across many invocations is the subsystem-monoculture signal the dual-register rebuild fixed.")
    lines.append("")
    lines.append("## Trigger conditions")
    for t, count in sorted(trigger_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{t}` — {count}")
    lines.append("")
    lines.append("## Decision class")
    for dc, count in sorted(decision_class_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{dc}` — {count}")
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
