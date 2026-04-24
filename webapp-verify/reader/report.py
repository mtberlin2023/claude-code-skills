"""Generate report.html for a single artefact run dir.

Usage:
  python -m reader.report <artefact_dir>
  # or from verify.py:
  from reader.report import generate
  generate(Path("artefacts/20260424T094032Z"))

Branding:
  Pass brand={"label": "...", "tagline": "...", "logo_src": "data:image/png;base64,...", "footer": "..."}
  or set WEBWITNESS_BRAND_JSON to a file path with that shape. Empty brand =
  default webwitness label.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from .parse import (
    parse_snapshot_json,
    snapshot_url,
    snapshot_busy,
    Node,
)
from .diff import diff_snapshots, summarise_diff
from .findings import run_rules


def generate(artefact_dir: Path, brand: dict | None = None) -> Path:
    artefact_dir = Path(artefact_dir)
    if not artefact_dir.is_dir():
        raise FileNotFoundError(f"Not a directory: {artefact_dir}")

    flow = _read_json(artefact_dir / "flow.json")
    result = _read_json(artefact_dir / "result.json")

    step_files = _index_steps(artefact_dir)
    snapshots = _load_snapshots(flow, step_files)
    final_snapshot = _load_final_snapshot(artefact_dir)

    diffs = _compute_diffs(snapshots, final_snapshot)
    findings = run_rules(
        flow,
        [(idx, nodes) for idx, _, nodes in snapshots],
        final_snapshot[2] if final_snapshot else None,
    )

    step_durations = result.get("step_durations_ms") or []
    timeline = _build_timeline(flow, step_files, snapshots, artefact_dir, step_durations)
    evidence, missed, why_fail = _build_evidence(flow, result, snapshots, final_snapshot)
    final_screenshot = _load_final_screenshot(artefact_dir, step_files)

    journey = _read_json(artefact_dir / "journey.json") if (artefact_dir / "journey.json").exists() else None
    narrative = _load_narrative(artefact_dir) if journey else None

    payload = {
        "run_id": result.get("run_id") or artefact_dir.name,
        "duration_ms": result.get("duration_ms"),
        "flow": flow,
        "result": result,
        "journey": journey,
        "narrative": narrative,
        "timeline": timeline,
        "evidence": evidence,
        "missed_evidence": missed,
        "why_fail": why_fail,
        "final_screenshot": final_screenshot,
        "snapshots": [{
            "step_index": idx,
            "label": label,
            "nodes": [n.to_dict() for n in nodes],
        } for idx, label, nodes in snapshots],
        "diffs": [{
            "from_step": from_step,
            "to_step": to_step,
            "ops": [op.to_dict() for op in ops],
            "summary": summarise_diff(ops),
        } for from_step, to_step, ops in diffs],
        "findings": [f.to_dict() for f in findings],
        "raw_files": _list_raw_files(artefact_dir),
        "brand": _resolve_brand(brand),
    }

    from .template import render_report
    html_out = render_report(payload)

    out_path = artefact_dir / "report.html"
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def _load_narrative(artefact_dir: Path) -> list[dict]:
    """Read decisions.jsonl from a journey run. Returns [] if absent or
    malformed — Narrative is a soft-fail render."""
    p = artefact_dir / "decisions.jsonl"
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _index_steps(artefact_dir: Path) -> dict[int, dict]:
    """Map step_number (1-based) -> {tool, json_path, png_path (if any)}."""
    index: dict[int, dict] = {}
    for p in sorted(artefact_dir.iterdir()):
        name = p.name
        if not name.startswith("step-"):
            continue
        parts = name.split("-", 2)
        if len(parts) < 3:
            continue
        try:
            step_num = int(parts[1])
        except ValueError:
            continue
        rest = parts[2]
        tool = rest.rsplit(".", 1)[0]
        ext = rest.rsplit(".", 1)[-1] if "." in rest else ""
        entry = index.setdefault(step_num, {"tool": tool})
        if ext == "json":
            entry["json"] = p
        elif ext == "png":
            entry["png"] = p
        entry["tool"] = tool
    return index


def _load_snapshots(flow: dict, step_files: dict) -> list[tuple[int, str, list[Node]]]:
    """Return list of (step_number_1based, label, nodes) for every take_snapshot step."""
    out: list[tuple[int, str, list[Node]]] = []
    steps = flow.get("steps", [])
    label_counter = 1
    for i, step in enumerate(steps):
        step_num = i + 1
        if step.get("tool") != "take_snapshot":
            continue
        entry = step_files.get(step_num)
        if not entry or "json" not in entry:
            continue
        raw = _read_json(entry["json"])
        nodes = parse_snapshot_json(raw)
        label = _label_snapshot(steps, i, label_counter)
        label_counter += 1
        out.append((step_num, label, nodes))
    return out


def _label_snapshot(steps: list, i: int, count: int) -> str:
    prev_action = None
    for j in range(i - 1, -1, -1):
        tool = steps[j].get("tool")
        if tool != "take_snapshot":
            prev_action = tool
            break
    if prev_action is None:
        return "initial"
    return f"post-{prev_action}"


def _load_final_snapshot(artefact_dir: Path):
    p = artefact_dir / "final-snapshot.json"
    if not p.exists():
        return None
    raw = _read_json(p)
    nodes = parse_snapshot_json(raw)
    return ("final", "final", nodes)


def _compute_diffs(snapshots, final_snapshot):
    """Between each consecutive pair, and from last → final if final is distinct."""
    diffs = []
    for i in range(len(snapshots) - 1):
        from_step, _, a = snapshots[i]
        to_step, _, b = snapshots[i + 1]
        ops = diff_snapshots(a, b)
        diffs.append((from_step, to_step, ops))
    if final_snapshot and snapshots:
        last_step, _, last_nodes = snapshots[-1]
        ops = diff_snapshots(last_nodes, final_snapshot[2])
        if any(o.kind != "=" for o in ops):
            diffs.append((last_step, "final", ops))
    return diffs


def _build_timeline(flow: dict, step_files: dict, snapshots, artefact_dir: Path, step_durations: list):
    rows = []
    steps = flow.get("steps", [])
    snap_by_step = {idx: nodes for idx, _, nodes in snapshots}
    last_nodes = None
    for i, step in enumerate(steps):
        step_num = i + 1
        tool = step.get("tool", "?")
        kind = "action"
        detail_html = _action_detail_html(step)
        delta_html = None
        screenshot = None
        if tool == "take_snapshot":
            kind = "snapshot"
            nodes = snap_by_step.get(step_num, [])
            url = _root_url(nodes)
            detail_html = f'{len(nodes)} nodes · url=<span style="font-family:var(--mono)">{_escape(url or "—")}</span>'
            if last_nodes is not None:
                ops = diff_snapshots(last_nodes, nodes)
                summary = summarise_diff(ops)
                delta_html = (
                    f'Δ from previous snapshot: '
                    f'<span class="add">+{summary["+"]}</span> '
                    f'<span class="rem">−{summary["-"]}</span> '
                    f'<span class="chg">~{summary["~"]}</span>'
                )
            last_nodes = nodes
        elif tool == "take_screenshot":
            kind = "screenshot"
            entry = step_files.get(step_num, {})
            png = entry.get("png")
            if png and png.exists():
                screenshot = _png_to_data_url(png)
                detail_html = f'{png.stat().st_size // 1024} KB'
        elif tool == "wait_for_url_change":
            entry = step_files.get(step_num, {})
            if "json" in entry:
                raw = _read_json(entry["json"])
                ms = raw.get("elapsed_ms", "—")
                changed = raw.get("changed", False)
                final_url = raw.get("final_url", "")
                detail_html = (
                    f'{"changed" if changed else "timeout"} after {ms}ms '
                    f'· <span style="font-family:var(--mono)">{_escape(final_url or "—")}</span>'
                )
        duration_ms = step_durations[i] if i < len(step_durations) else None
        rows.append({
            "index": step_num,
            "kind": kind,
            "tool": tool,
            "detail_html": detail_html,
            "delta_html": delta_html,
            "screenshot": screenshot,
            "duration_ms": duration_ms,
        })
    return rows


def _action_detail_html(step: dict) -> str:
    tool = step.get("tool")
    if tool == "navigate_page":
        return _escape(step.get("url", ""))
    if tool == "fill":
        sel = step.get("selector", {})
        sel_s = _selector_repr(sel)
        val = step.get("value", "")
        return f'{sel_s} ← <span style="font-family:var(--mono)">"{_escape(val)}"</span>'
    if tool == "click":
        sel = step.get("selector", {})
        return _selector_repr(sel)
    return ""


def _selector_repr(sel: dict) -> str:
    if not sel:
        return "[selector]"
    bits = []
    for k in ("role", "name"):
        if k in sel and sel[k] != "":
            bits.append(f'{k}={_escape(str(sel[k]))}')
    return "[" + " ".join(bits) + "]" if bits else "[selector]"


def _root_url(nodes: list[Node]) -> str | None:
    for n in nodes:
        if n.depth == 0 and n.role == "RootWebArea":
            return n.url
    return None


def _build_evidence(flow, result, snapshots, final_snapshot):
    evidence = []
    missed = []
    why_fail = None
    success = flow.get("success_state") or {}
    url_pattern = success.get("url_pattern")
    landmark = success.get("landmark")

    final_nodes = final_snapshot[2] if final_snapshot else None
    last_nodes = snapshots[-1][2] if snapshots else []
    last_url = _root_url(last_nodes)
    final_url = _root_url(final_nodes) if final_nodes else None

    if result.get("pass"):
        if url_pattern and last_url and url_pattern in last_url:
            evidence.append(f'URL matches “{url_pattern}” (landed at {last_url})')
        if landmark:
            evidence.append(f'Landmark present: {landmark}')
        flash = _find_success_flash(last_nodes)
        if flash:
            evidence.append(f'Flash message in a11y tree: "{flash}"')
        evidence.append(f'Matcher fired: {result.get("matcher")}')
    else:
        if url_pattern:
            missed.append(f'Expected URL to match “{url_pattern}” — last-eval snapshot URL was {last_url or "unknown"}.')
            if final_url and url_pattern in final_url and (not last_url or url_pattern not in last_url):
                why_fail = (
                    f'Expected URL to match <code>{_escape(url_pattern)}</code>. '
                    f'Last-eval snapshot showed <code>url="{_escape(last_url or "—")}"</code> — click registered '
                    f'but the route change hadn\'t committed. '
                    f'<strong>final-snapshot.json (captured post-verdict) shows <code>url="{_escape(final_url)}"</code> '
                    f'— success arrived after the verdict was written.</strong> '
                    f'Candidate v1.1 fix: <code>wait_for_url_change</code> step with timeout.'
                )
        if landmark:
            missed.append(f'Expected landmark: {landmark}')
        if not url_pattern and not landmark:
            missed.append('Matcher returned no match.')

    return evidence, missed, why_fail


def _find_success_flash(nodes: list[Node]) -> str | None:
    flash_markers = ("welcome", "thanks", "success", "you're", "confirmed", "registered", "submitted")
    for n in nodes[:50]:
        if n.role == "StaticText" and n.name:
            low = n.name.lower()
            if any(m in low for m in flash_markers):
                return n.name
    return None


def _load_final_screenshot(artefact_dir: Path, step_files) -> str | None:
    for step_num in sorted(step_files.keys(), reverse=True):
        entry = step_files[step_num]
        if entry.get("tool") == "take_screenshot" and entry.get("png"):
            return _png_to_data_url(entry["png"])
    return None


def _png_to_data_url(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _list_raw_files(artefact_dir: Path):
    out = []
    for p in sorted(artefact_dir.iterdir()):
        if p.name == "report.html":
            continue
        if p.is_dir():
            continue
        out.append({
            "name": p.name,
            "size": p.stat().st_size,
            "href": p.name,
        })
    return out


def _escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _resolve_brand(brand: dict | None) -> dict:
    if brand is not None:
        return brand
    env_path = os.environ.get("WEBWITNESS_BRAND_JSON")
    if env_path:
        try:
            return json.loads(Path(env_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(prog="reader.report", description="Generate report.html for an artefact run dir.")
    ap.add_argument("artefact_dir", help="Path to a webwitness artefact run directory.")
    ap.add_argument("--brand", help="Path to a brand.json file (overrides WEBWITNESS_BRAND_JSON).")
    args = ap.parse_args()
    brand = None
    if args.brand:
        brand = json.loads(Path(args.brand).read_text(encoding="utf-8"))
    out = generate(Path(args.artefact_dir), brand=brand)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
