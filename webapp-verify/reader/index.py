"""Generate index.html — the multi-run index across all artefact dirs.

Usage:
  python -m reader.index                          # scans <skill>/artefacts/
  python -m reader.index <artefacts_root>         # custom root
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse


def generate(artefacts_root: Path) -> Path:
    artefacts_root = Path(artefacts_root)
    if not artefacts_root.is_dir():
        raise FileNotFoundError(f"Not a directory: {artefacts_root}")

    runs = []
    suites = []
    diffs = []
    for d in sorted(artefacts_root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        suite_result_path = d / "suite-result.json"
        if suite_result_path.exists() and d.name.startswith("suite-"):
            suite_row = _suite_row(d)
            if suite_row:
                suites.append(suite_row)
            continue
        diff_result_path = d / "diff-result.json"
        if diff_result_path.exists() and d.name.startswith("diff-"):
            diff_row = _diff_row(d)
            if diff_row:
                diffs.append(diff_row)
            continue
        result_path = d / "result.json"
        flow_path = d / "flow.json"
        if not (result_path.exists() and flow_path.exists()):
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
            flow = json.loads(flow_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        runs.append(_row(d, result, flow))

    payload = {"runs": runs, "suites": suites, "diffs": diffs, "count": len(runs)}
    from .template import render_index
    html_out = render_index(payload)
    out_path = artefacts_root / "index.html"
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def _row(run_dir: Path, result: dict, flow: dict) -> dict:
    run_id = result.get("run_id") or run_dir.name
    target = (flow.get("steps") or [{}])[0].get("url", "")
    host = urlparse(target).hostname or "—"
    goal = flow.get("goal") or "(no goal)"
    date = _run_id_to_date(run_id)
    findings_count = _count_findings(run_dir)
    has_report = (run_dir / "report.html").exists()
    return {
        "run_id": run_id,
        "date": date,
        "goal": goal,
        "target_host": host,
        "pass": bool(result.get("pass")),
        "steps": f'{result.get("steps_completed", "?")}/{result.get("steps_total", "?")}',
        "findings": findings_count,
        "report_href": f'{run_dir.name}/report.html' if has_report else f'{run_dir.name}/',
    }


def _suite_row(suite_dir: Path) -> dict | None:
    """Build the index payload entry for a suite-<id>/ directory.

    Reads suite-result.json (the roll-up) and walks each journey's
    artefact dir to confirm report.html paths and pick up final verdict.
    Returns None if suite-result.json is missing/malformed."""
    sr_path = suite_dir / "suite-result.json"
    try:
        sr = json.loads(sr_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    site = sr.get("site") or {}
    target = site.get("target") or ""
    host = urlparse(target).hostname or "—"
    label = site.get("label") or host

    journey_rows: list[dict] = []
    personas_seen: list[str] = []
    files_seen: list[str] = []
    viewports_seen: list[str] = []
    has_viewports = False
    for jr in sr.get("journeys") or []:
        run_id = jr.get("run_id") or ""
        # The journey runner wrote into suite-<id>/<run_id>/.
        run_subdir = suite_dir / run_id
        report_rel = (
            f"{suite_dir.name}/{run_id}/report.html"
            if (run_subdir / "report.html").exists()
            else f"{suite_dir.name}/{run_id}/"
        )
        f = jr.get("file") or "?"
        persona = jr.get("persona") or "—"
        viewport = jr.get("viewport") or None
        viewport_label = (viewport or {}).get("label", "") if viewport else ""
        if viewport:
            has_viewports = True
            if viewport_label not in viewports_seen:
                viewports_seen.append(viewport_label)
        if persona not in personas_seen:
            personas_seen.append(persona)
        if f not in files_seen:
            files_seen.append(f)
        journey_rows.append({
            "file": f,
            "persona": persona,
            "persona_override": jr.get("persona_override"),
            "viewport": viewport_label,
            "intent": jr.get("intent") or "",
            "verdict": jr.get("verdict") or "FAIL",
            "matcher": jr.get("matcher"),
            "iterations": jr.get("iterations"),
            "duration_ms": jr.get("duration_ms"),
            "run_id": run_id,
            "report_href": report_rel,
        })

    suite_id = sr.get("suite_id") or suite_dir.name.removeprefix("suite-")
    return {
        "suite_id": suite_id,
        "label": label,
        "target": target,
        "target_host": host,
        "date": _run_id_to_date(suite_id),
        "verdict_summary": sr.get("verdict_summary") or {},
        "duration_ms": sr.get("duration_ms"),
        "journeys": journey_rows,
        "files": files_seen,
        "personas": personas_seen,
        "viewports": viewports_seen,
        "has_viewports": has_viewports,
    }


def _diff_row(diff_dir: Path) -> dict | None:
    """Build the index payload entry for a diff-<A>-vs-<B>/ directory.

    Reads diff-result.json and surfaces the headline divergence + verdict
    delta. Returns None if diff-result.json is missing/malformed."""
    dr_path = diff_dir / "diff-result.json"
    try:
        dr = json.loads(dr_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    a = dr.get("run_a") or {}
    b = dr.get("run_b") or {}
    fd = dr.get("first_divergence") or {}
    fdiff = dr.get("findings_diff") or {}
    diff_id = dr.get("diff_id") or diff_dir.name.removeprefix("diff-")
    has_html = (diff_dir / "diff.html").exists()
    return {
        "diff_id": diff_id,
        "date": _run_id_to_date(a.get("run_id") or ""),
        "run_a_id": a.get("run_id") or "",
        "run_b_id": b.get("run_id") or "",
        "verdict_a": a.get("verdict") or "—",
        "verdict_b": b.get("verdict") or "—",
        "verdict_changed": bool(dr.get("verdict_changed")),
        "matcher_changed": bool(dr.get("matcher_changed")),
        "first_divergence_kind": fd.get("kind") or "none",
        "first_divergence_step": fd.get("step_index"),
        "added_findings": len(fdiff.get("added") or []),
        "removed_findings": len(fdiff.get("removed") or []),
        "diff_href": (
            f"{diff_dir.name}/diff.html" if has_html else f"{diff_dir.name}/"
        ),
    }


def _run_id_to_date(run_id: str) -> str:
    # run_id format: YYYYMMDDTHHMMSSZ
    if len(run_id) >= 15 and run_id[8] == "T":
        return f'{run_id[:4]}-{run_id[4:6]}-{run_id[6:8]} {run_id[9:11]}:{run_id[11:13]}'
    return run_id


def _count_findings(run_dir: Path) -> int:
    # Lightweight: parse the report.html if present for a marker.
    # Otherwise 0. Keeps index generation cheap (no snapshot re-parsing).
    report = run_dir / "report.html"
    if not report.exists():
        return 0
    try:
        text = report.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    marker = '"findings":['
    i = text.find(marker)
    if i < 0:
        return 0
    j = i + len(marker)
    depth = 1
    count = 0
    saw_object = False
    while j < len(text) and depth > 0:
        c = text[j]
        if c == '{':
            if depth == 1 and not saw_object:
                count += 1
                saw_object = True
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 1:
                saw_object = False
        elif c == ']' and depth == 1:
            break
        elif c == ',' and depth == 1:
            saw_object = False
        j += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(prog="reader.index", description="Generate index.html across artefact dirs.")
    default_root = Path(__file__).parent.parent / "artefacts"
    ap.add_argument("artefacts_root", nargs="?", default=str(default_root),
                    help=f"Artefacts root (default: {default_root})")
    args = ap.parse_args()
    out = generate(Path(args.artefacts_root))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
