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
    for d in sorted(artefacts_root.iterdir(), reverse=True):
        if not d.is_dir():
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

    payload = {"runs": runs, "count": len(runs)}
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
