"""Journey diff — compare two single-journey runs step-by-step.

Substrate for v1.0 P3 (regression alerts). Loads two artefact directories'
decisions.jsonl + result.json + journey.json (+ optional findings.json,
final-snapshot.json), walks the decision sequences in lock-step until the
first divergence, and emits a diff-result.json describing what changed.

Diff result schema (webwitness/diff/v1):

    {
      "schema": "webwitness/diff/v1",
      "diff_id": "<runA>-vs-<runB>",
      "generated_at": "<ISO8601>",
      "run_a": { "run_id", "verdict", "matcher", "persona", "intent",
                 "target", "iterations", "clicks_used", "duration_ms",
                 "artefacts_dir", "report_href" },
      "run_b": { ... same shape ... },
      "verdict_changed": bool,
      "matcher_changed": bool,
      "journey_changed": bool,        # journey.json intent/target/persona/success diverge
      "first_divergence": {
        "step_index": int | null,     # 1-based; null when sequences are identical
        "kind": "action" | "target_name" | "url" | "length" | "matcher_only" | "none",
        "a": { "iter", "action", "target_role", "target_name", "url",
               "rationale" } | null,
        "b": { ... same shape ... } | null
      },
      "step_table": [
        {
          "idx": int,                 # 1-based step index
          "a": { ... step shape ... } | null,
          "b": { ... step shape ... } | null,
          "divergent": bool,
          "kind": "match" | "action" | "target_name" | "url"
                  | "missing_a" | "missing_b"
        }, ...
      ],
      "findings_diff": {
        "added":   [<finding>, ...],  # in B but not A
        "removed": [<finding>, ...],  # in A but not B
        "shared":  [<finding>, ...]
      }
    }

Comparison keys:
  * Step key:    (action, target_role, target_name, url) — rationale text
                 is LLM prose and intentionally NOT keyed.
  * Finding key: (rule_id, node_repr) — description wording can drift even
                 when the underlying signal is identical.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any


DIFF_SCHEMA = "webwitness/diff/v1"


class DiffError(Exception):
    """Raised when a run directory is missing required artefacts."""


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise DiffError(f"missing artefact: {path}") from e
    except json.JSONDecodeError as e:
        raise DiffError(f"malformed JSON in {path}: {e}") from e


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise DiffError(f"missing artefact: {path}")
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise DiffError(f"malformed JSONL in {path}:{line_no}: {e}") from e
    return rows


def _load_run(run_dir: Path) -> dict:
    """Load all artefacts from a single-journey run directory."""
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        raise DiffError(f"not a directory: {run_dir}")
    if (run_dir / "suite-result.json").exists():
        raise DiffError(
            f"{run_dir.name} is a suite directory; journey-diff operates on "
            "single-journey run dirs (suite-vs-suite is out of scope for v1.0)"
        )

    result = _read_json(run_dir / "result.json")
    journey = _read_json(run_dir / "journey.json")
    decisions = _read_jsonl(run_dir / "decisions.jsonl")

    findings_path = run_dir / "findings.json"
    findings: list[dict] = []
    if findings_path.exists():
        findings_doc = _read_json(findings_path)
        findings = findings_doc.get("findings") or []
    elif isinstance(result.get("findings"), list):
        findings = result["findings"]

    return {
        "run_dir": run_dir,
        "result": result,
        "journey": journey,
        "decisions": decisions,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Step normalisation + comparison
# ---------------------------------------------------------------------------

def _normalise_step(decision: dict) -> dict:
    """Pick the comparison-relevant fields from a decisions.jsonl row."""
    return {
        "iter": decision.get("iter"),
        "action": decision.get("action"),
        "target_role": decision.get("target_role"),
        "target_name": decision.get("target_name"),
        "url": decision.get("url"),
        "rationale": decision.get("rationale"),
    }


def _step_key(step: dict) -> tuple:
    """Hashable identity for divergence detection (rationale excluded)."""
    return (
        step.get("action"),
        step.get("target_role"),
        step.get("target_name"),
        step.get("url"),
    )


def _classify_divergence(a: dict, b: dict) -> str:
    """Return the most specific divergence kind between two normalised steps."""
    if a.get("action") != b.get("action"):
        return "action"
    if a.get("target_name") != b.get("target_name") or a.get("target_role") != b.get("target_role"):
        return "target_name"
    if a.get("url") != b.get("url"):
        return "url"
    return "match"


def _walk_sequences(decisions_a: list[dict], decisions_b: list[dict]) -> tuple[list[dict], dict]:
    """Walk both decision lists in lock-step. Return (step_table, first_divergence)."""
    steps_a = [_normalise_step(d) for d in decisions_a]
    steps_b = [_normalise_step(d) for d in decisions_b]

    n = max(len(steps_a), len(steps_b))
    step_table: list[dict] = []
    first: dict | None = None

    for i in range(n):
        a = steps_a[i] if i < len(steps_a) else None
        b = steps_b[i] if i < len(steps_b) else None

        if a is None:
            kind = "missing_a"
        elif b is None:
            kind = "missing_b"
        else:
            kind = _classify_divergence(a, b)

        divergent = kind != "match"
        step_table.append({
            "idx": i + 1,
            "a": a,
            "b": b,
            "divergent": divergent,
            "kind": kind,
        })

        if divergent and first is None:
            mapped_kind = (
                "length" if kind in ("missing_a", "missing_b") else kind
            )
            first = {
                "step_index": i + 1,
                "kind": mapped_kind,
                "a": a,
                "b": b,
            }

    if first is None:
        first = {"step_index": None, "kind": "none", "a": None, "b": None}

    return step_table, first


# ---------------------------------------------------------------------------
# Findings diff
# ---------------------------------------------------------------------------

def _finding_key(f: dict) -> tuple:
    return (f.get("rule_id"), f.get("node_repr"))


def _diff_findings(findings_a: list[dict], findings_b: list[dict]) -> dict:
    keys_a = {_finding_key(f): f for f in findings_a}
    keys_b = {_finding_key(f): f for f in findings_b}
    added = [keys_b[k] for k in keys_b if k not in keys_a]
    removed = [keys_a[k] for k in keys_a if k not in keys_b]
    shared = [keys_a[k] for k in keys_a if k in keys_b]
    return {"added": added, "removed": removed, "shared": shared}


# ---------------------------------------------------------------------------
# Journey-shape comparison
# ---------------------------------------------------------------------------

def _journey_changed(j_a: dict, j_b: dict) -> bool:
    keys = ("intent", "target", "persona", "success")
    return any(j_a.get(k) != j_b.get(k) for k in keys)


# ---------------------------------------------------------------------------
# Run summary block
# ---------------------------------------------------------------------------

def _run_summary(run: dict) -> dict:
    result = run["result"]
    journey = run["journey"]
    return {
        "run_id": result.get("run_id"),
        "verdict": result.get("verdict"),
        "matcher": result.get("matcher"),
        "persona": journey.get("persona"),
        "intent": journey.get("intent"),
        "target": journey.get("target"),
        "iterations": result.get("iterations"),
        "clicks_used": result.get("clicks_used"),
        "duration_ms": result.get("duration_ms"),
        "artefacts_dir": str(run["run_dir"]),
        "report_href": (
            f"../{run['run_dir'].name}/report.html"
            if (run["run_dir"] / "report.html").exists()
            else f"../{run['run_dir'].name}/"
        ),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def diff_runs(run_dir_a: Path | str, run_dir_b: Path | str) -> dict:
    """Compute the diff between two single-journey runs.

    Returns a payload conforming to the webwitness/diff/v1 schema. Does not
    write to disk — that is the caller's job (see ``write_diff``).
    """
    run_a = _load_run(Path(run_dir_a))
    run_b = _load_run(Path(run_dir_b))

    step_table, first_div = _walk_sequences(run_a["decisions"], run_b["decisions"])
    findings_diff = _diff_findings(run_a["findings"], run_b["findings"])

    sum_a = _run_summary(run_a)
    sum_b = _run_summary(run_b)

    verdict_changed = sum_a["verdict"] != sum_b["verdict"]
    matcher_changed = sum_a["matcher"] != sum_b["matcher"]
    journey_changed = _journey_changed(run_a["journey"], run_b["journey"])

    if first_div["kind"] == "none" and (verdict_changed or matcher_changed):
        first_div = {**first_div, "kind": "matcher_only"}

    diff_id = f"{sum_a['run_id']}-vs-{sum_b['run_id']}"
    return {
        "schema": DIFF_SCHEMA,
        "diff_id": diff_id,
        "generated_at": _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_a": sum_a,
        "run_b": sum_b,
        "verdict_changed": verdict_changed,
        "matcher_changed": matcher_changed,
        "journey_changed": journey_changed,
        "first_divergence": first_div,
        "step_table": step_table,
        "findings_diff": findings_diff,
    }


def write_diff(diff_payload: dict, out_dir: Path) -> Path:
    """Write diff-result.json into ``out_dir`` (creating it). Returns the path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "diff-result.json"
    out_path.write_text(json.dumps(diff_payload, indent=2), encoding="utf-8")
    return out_path


def default_out_dir(artefacts_root: Path, run_a_id: str, run_b_id: str) -> Path:
    """Conventional location for a diff: artefacts_root/diff-<A>-vs-<B>/."""
    return Path(artefacts_root) / f"diff-{run_a_id}-vs-{run_b_id}"


SUITE_DIFF_SCHEMA = "webwitness/suite-diff/v1"


def diff_suite_viewports(
    suite_dir: Path | str,
    baseline_viewport: str | None = None,
) -> dict:
    """Compute viewport-vs-viewport diffs across a P7 suite run.

    Groups journey-row results by ``(file, persona)`` and, within each
    group, diffs every non-baseline viewport against the baseline. Baseline
    defaults to the first viewport seen in suite-result.json (preserves
    site.yaml ordering); pass ``baseline_viewport`` to override.

    Returns a roll-up payload conforming to webwitness/suite-diff/v1. Does
    NOT write per-pair diff-result.json files — that is the caller's job
    via ``write_suite_diff``, which writes both the roll-up + each pair's
    artefacts under ``<suite_dir>/diff-<A>-vs-<B>/``.
    """
    suite_dir = Path(suite_dir).resolve()
    sr_path = suite_dir / "suite-result.json"
    if not sr_path.exists():
        raise DiffError(f"not a suite directory (no suite-result.json): {suite_dir}")
    sr = _read_json(sr_path)

    rows = sr.get("journeys") or []
    if not rows:
        raise DiffError(f"suite-result.json has no journeys: {sr_path}")

    # Group by (file, persona).
    groups: dict[tuple[str, str], list[dict]] = {}
    viewports_in_order: list[str] = []
    for r in rows:
        viewport = (r.get("viewport") or {}).get("label") if r.get("viewport") else None
        if viewport is None:
            # No viewport axis — can't diff, skip.
            continue
        if viewport not in viewports_in_order:
            viewports_in_order.append(viewport)
        key = (r.get("file") or "?", r.get("persona") or "—")
        groups.setdefault(key, []).append(r)

    if not viewports_in_order:
        raise DiffError(
            f"suite at {suite_dir} has no viewport axis — nothing to diff. "
            "Re-run the suite with a `viewports:` block in site.yaml."
        )

    if baseline_viewport is None:
        baseline_viewport = viewports_in_order[0]
    elif baseline_viewport not in viewports_in_order:
        raise DiffError(
            f"baseline viewport '{baseline_viewport}' not present in suite. "
            f"Available: {viewports_in_order}"
        )

    cells: list[dict] = []
    for (file_, persona), rows_in_group in groups.items():
        by_vp: dict[str, dict] = {}
        for r in rows_in_group:
            vp_label = (r.get("viewport") or {}).get("label")
            if vp_label:
                by_vp[vp_label] = r
        baseline_row = by_vp.get(baseline_viewport)
        if baseline_row is None:
            # Cell has no run at baseline viewport — skip with a marker.
            cells.append({
                "file": file_,
                "persona": persona,
                "baseline": None,
                "compared": [],
                "skipped_reason": f"no run at baseline viewport '{baseline_viewport}'",
            })
            continue

        baseline_dir = Path(baseline_row.get("artefacts_dir") or "")
        baseline_summary = _row_summary(baseline_row)

        compared: list[dict] = []
        for vp_label in viewports_in_order:
            if vp_label == baseline_viewport:
                continue
            target_row = by_vp.get(vp_label)
            if target_row is None:
                continue
            target_dir = Path(target_row.get("artefacts_dir") or "")
            try:
                pair = diff_runs(baseline_dir, target_dir)
            except DiffError as e:
                compared.append({
                    "viewport": vp_label,
                    "run_id": target_row.get("run_id"),
                    "verdict": target_row.get("verdict"),
                    "matcher": target_row.get("matcher"),
                    "error": str(e),
                })
                continue
            fd = pair.get("first_divergence") or {}
            fdiff = pair.get("findings_diff") or {}
            compared.append({
                "viewport": vp_label,
                "run_id": target_row.get("run_id"),
                "verdict": target_row.get("verdict"),
                "matcher": target_row.get("matcher"),
                "verdict_changed": pair.get("verdict_changed"),
                "matcher_changed": pair.get("matcher_changed"),
                "first_divergence_kind": fd.get("kind"),
                "first_divergence_step": fd.get("step_index"),
                "added_findings": len(fdiff.get("added") or []),
                "removed_findings": len(fdiff.get("removed") or []),
                "_pair_payload": pair,  # consumed by write_suite_diff; stripped from disk roll-up
            })
        cells.append({
            "file": file_,
            "persona": persona,
            "baseline": baseline_summary,
            "compared": compared,
        })

    return {
        "schema": SUITE_DIFF_SCHEMA,
        "suite_id": sr.get("suite_id") or suite_dir.name.removeprefix("suite-"),
        "site": sr.get("site") or {},
        "baseline_viewport": baseline_viewport,
        "viewports": viewports_in_order,
        "generated_at": _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cells": cells,
    }


def _row_summary(row: dict) -> dict:
    """Summarise a single suite-result.json row for the diff roll-up."""
    vp = row.get("viewport") or {}
    return {
        "viewport": vp.get("label"),
        "run_id": row.get("run_id"),
        "verdict": row.get("verdict"),
        "matcher": row.get("matcher"),
        "iterations": row.get("iterations"),
        "duration_ms": row.get("duration_ms"),
        "artefacts_dir": row.get("artefacts_dir"),
    }


def write_suite_diff(payload: dict, suite_dir: Path, render_html: bool = True) -> Path:
    """Persist a suite-diff roll-up + per-pair diff dirs.

    For every compared cell, writes a per-pair ``diff-<runA>-vs-<runB>/``
    directory under ``suite_dir`` (so the existing reader picks them up
    via the Diffs panel). When ``render_html`` is True (default), each
    per-pair dir also gets a ``diff.html`` via ``reader.diff_report``.
    Returns the path of the roll-up JSON.
    """
    suite_dir = Path(suite_dir)
    if render_html:
        # Imported lazily so the diff module stays importable from contexts
        # that don't have the reader package available.
        from reader.diff_report import generate as _generate_diff_html
    else:
        _generate_diff_html = None  # type: ignore[assignment]

    cells_for_disk: list[dict] = []
    for cell in payload["cells"]:
        compared_for_disk: list[dict] = []
        for cmp in cell.get("compared", []):
            pair = cmp.pop("_pair_payload", None)
            if pair is None:
                compared_for_disk.append(cmp)
                continue
            run_a_id = pair["run_a"]["run_id"]
            run_b_id = pair["run_b"]["run_id"]
            pair_dir = default_out_dir(suite_dir, run_a_id, run_b_id)
            write_diff(pair, pair_dir)
            if _generate_diff_html is not None:
                try:
                    _generate_diff_html(pair_dir)
                except Exception as e:  # noqa: BLE001 — render is non-fatal
                    cmp["render_error"] = str(e)
            cmp["diff_dir"] = pair_dir.name
            cmp["diff_href"] = f"{pair_dir.name}/diff.html"
            compared_for_disk.append(cmp)
        cells_for_disk.append({**cell, "compared": compared_for_disk})

    out = {**payload, "cells": cells_for_disk}
    out_path = suite_dir / "suite-diff-result.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out_path


__all__ = [
    "DIFF_SCHEMA",
    "SUITE_DIFF_SCHEMA",
    "DiffError",
    "diff_runs",
    "diff_suite_viewports",
    "write_diff",
    "write_suite_diff",
    "default_out_dir",
]
