"""Tests for the index generator's suite detection. Verifies that
suite-<id>/ dirs are read via suite-result.json and surfaced as a
matrix-shaped payload entry, while flat run dirs continue to populate
the regular `runs[]` list."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reader.index import generate


def _write_flat_run(root: Path, run_id: str, host_target: str, goal: str, passed: bool) -> Path:
    d = root / run_id
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({
        "run_id": run_id, "pass": passed, "verdict": "PASS" if passed else "FAIL",
        "steps_completed": 2, "steps_total": 2,
    }), encoding="utf-8")
    (d / "flow.json").write_text(json.dumps({
        "goal": goal, "steps": [{"url": host_target}],
    }), encoding="utf-8")
    return d


def _write_suite_run(
    root: Path,
    suite_id: str,
    label: str,
    target: str,
    journey_specs: list[tuple[str, str, str]],  # (file, persona, verdict)
) -> Path:
    suite_dir = root / f"suite-{suite_id}"
    suite_dir.mkdir(parents=True)
    journeys_payload = []
    for i, (jf, persona, verdict) in enumerate(journey_specs):
        run_id = f"r-{i}"
        run_subdir = suite_dir / run_id
        run_subdir.mkdir()
        # Write a stub report.html so the report_href check finds it.
        (run_subdir / "report.html").write_text("<html></html>", encoding="utf-8")
        journeys_payload.append({
            "file": jf,
            "persona": persona,
            "persona_override": None,
            "intent": f"intent for {jf}",
            "run_id": run_id,
            "verdict": verdict,
            "matcher": "fake",
            "iterations": 2,
            "clicks_used": 1,
            "dead_ends": 0,
            "duration_ms": 100,
            "error": None,
            "artefacts_dir": str(run_subdir),
        })
    (suite_dir / "suite-result.json").write_text(json.dumps({
        "suite_id": suite_id,
        "site": {"label": label, "target": target},
        "journeys": journeys_payload,
        "verdict_summary": {
            "PASS": sum(1 for _, _, v in journey_specs if v == "PASS"),
            "FAIL": sum(1 for _, _, v in journey_specs if v == "FAIL"),
            "UNCLEAR": sum(1 for _, _, v in journey_specs if v == "UNCLEAR"),
        },
        "duration_ms": 5000,
        "artefacts_dir": str(suite_dir),
    }), encoding="utf-8")
    return suite_dir


def _index_payload(root: Path) -> dict:
    """Generate the index and parse the embedded JSON payload back out."""
    out = generate(root)
    text = out.read_text(encoding="utf-8")
    marker = '<script id="index-data" type="application/json">'
    i = text.find(marker)
    j = text.find('</script>', i)
    return json.loads(text[i + len(marker):j])


def test_flat_runs_unchanged(tmp_path: Path):
    _write_flat_run(tmp_path, "20260424T100000Z", "https://e.com/", "g1", True)
    payload = _index_payload(tmp_path)
    assert len(payload["runs"]) == 1
    assert payload["suites"] == []
    assert payload["runs"][0]["pass"] is True


def test_suite_dir_detected(tmp_path: Path):
    _write_suite_run(
        tmp_path,
        "20260424T120000Z",
        "undavos prod",
        "https://undavos.com/",
        [
            ("journeys/fresh-evaluating.json", "fresh", "PASS"),
            ("journeys/keyboard-only.json", "fresh", "UNCLEAR"),
            ("journeys/returning-action.json", "returning", "PASS"),
        ],
    )
    payload = _index_payload(tmp_path)
    assert payload["runs"] == []
    assert len(payload["suites"]) == 1
    s = payload["suites"][0]
    assert s["label"] == "undavos prod"
    assert s["target_host"] == "undavos.com"
    assert s["verdict_summary"]["PASS"] == 2
    assert s["verdict_summary"]["UNCLEAR"] == 1
    assert sorted(s["personas"]) == ["fresh", "returning"]
    assert len(s["files"]) == 3


def test_suite_journey_report_href_relative(tmp_path: Path):
    _write_suite_run(
        tmp_path,
        "20260424T130000Z",
        "site",
        "https://site.com/",
        [("j1.json", "fresh", "PASS")],
    )
    payload = _index_payload(tmp_path)
    j = payload["suites"][0]["journeys"][0]
    assert j["report_href"] == "suite-20260424T130000Z/r-0/report.html"


def test_flat_and_suite_coexist(tmp_path: Path):
    _write_flat_run(tmp_path, "20260424T100000Z", "https://e.com/", "flat goal", False)
    _write_suite_run(
        tmp_path,
        "20260424T120000Z",
        "site",
        "https://site.com/",
        [("j1.json", "fresh", "PASS")],
    )
    payload = _index_payload(tmp_path)
    assert len(payload["runs"]) == 1
    assert len(payload["suites"]) == 1
    # Flat run for e.com, suite for site.com — different hosts surfaced.
    hosts = {payload["runs"][0]["target_host"], payload["suites"][0]["target_host"]}
    assert hosts == {"e.com", "site.com"}


def test_malformed_suite_result_skipped(tmp_path: Path):
    suite_dir = tmp_path / "suite-broken"
    suite_dir.mkdir()
    (suite_dir / "suite-result.json").write_text("{not json", encoding="utf-8")
    _write_flat_run(tmp_path, "20260424T100000Z", "https://e.com/", "g1", True)
    payload = _index_payload(tmp_path)
    # Broken suite is silently skipped; flat run remains.
    assert payload["suites"] == []
    assert len(payload["runs"]) == 1


def test_suite_dir_without_marker_is_ignored(tmp_path: Path):
    # Dir name doesn't start with `suite-` even though it has a suite-result.json
    # — should NOT be treated as a suite (defensive: avoids confusing rogue
    # files in user-managed dirs).
    odd = tmp_path / "weird-dir"
    odd.mkdir()
    (odd / "suite-result.json").write_text("{}", encoding="utf-8")
    payload = _index_payload(tmp_path)
    assert payload["suites"] == []


# ─── diff dirs (P3) ────────────────────────────────────────────────────────


def _write_diff_dir(
    root: Path,
    diff_id: str,
    *,
    run_a_id: str = "20260425T070000Z",
    run_b_id: str = "20260425T080000Z",
    verdict_a: str = "PASS",
    verdict_b: str = "UNCLEAR",
    first_kind: str = "action",
    first_step: int | None = 1,
    has_html: bool = True,
) -> Path:
    diff_dir = root / f"diff-{diff_id}"
    diff_dir.mkdir(parents=True)
    payload = {
        "schema": "webwitness/diff/v1",
        "diff_id": diff_id,
        "generated_at": "2026-04-25T10:00:00Z",
        "run_a": {"run_id": run_a_id, "verdict": verdict_a, "matcher": "x"},
        "run_b": {"run_id": run_b_id, "verdict": verdict_b, "matcher": "y"},
        "verdict_changed": verdict_a != verdict_b,
        "matcher_changed": True,
        "first_divergence": {"step_index": first_step, "kind": first_kind},
        "step_table": [],
        "findings_diff": {"added": [{"rule_id": "x"}], "removed": [], "shared": []},
    }
    (diff_dir / "diff-result.json").write_text(json.dumps(payload), encoding="utf-8")
    if has_html:
        (diff_dir / "diff.html").write_text("<html>stub</html>", encoding="utf-8")
    return diff_dir


def test_diff_dir_detected(tmp_path: Path):
    _write_diff_dir(tmp_path, "A-vs-B")
    payload = _index_payload(tmp_path)
    assert payload["runs"] == []
    assert payload["suites"] == []
    assert len(payload["diffs"]) == 1
    d = payload["diffs"][0]
    assert d["diff_id"] == "A-vs-B"
    assert d["verdict_changed"] is True
    assert d["first_divergence_kind"] == "action"
    assert d["first_divergence_step"] == 1
    assert d["added_findings"] == 1
    assert d["diff_href"] == "diff-A-vs-B/diff.html"


def test_diff_dir_without_html_falls_back_to_dir(tmp_path: Path):
    _write_diff_dir(tmp_path, "A-vs-B", has_html=False)
    payload = _index_payload(tmp_path)
    assert payload["diffs"][0]["diff_href"] == "diff-A-vs-B/"


def test_diff_dir_without_marker_is_ignored(tmp_path: Path):
    # Dir name doesn't start with `diff-` — defensive against rogue files.
    odd = tmp_path / "weirdo"
    odd.mkdir()
    (odd / "diff-result.json").write_text("{}", encoding="utf-8")
    payload = _index_payload(tmp_path)
    assert payload["diffs"] == []


def test_diffs_runs_suites_coexist(tmp_path: Path):
    _write_flat_run(tmp_path, "20260425T070000Z", "https://e.com/", "g1", True)
    _write_suite_run(tmp_path, "20260425T080000Z", "site", "https://site.com/",
                     [("j1.json", "fresh", "PASS")])
    _write_diff_dir(tmp_path, "A-vs-B")
    payload = _index_payload(tmp_path)
    assert len(payload["runs"]) == 1
    assert len(payload["suites"]) == 1
    assert len(payload["diffs"]) == 1


def test_malformed_diff_result_skipped(tmp_path: Path):
    diff_dir = tmp_path / "diff-broken"
    diff_dir.mkdir()
    (diff_dir / "diff-result.json").write_text("{not json", encoding="utf-8")
    payload = _index_payload(tmp_path)
    assert payload["diffs"] == []


# ─── suite_diff badge payload (suite-header v1.0 lift) ─────────────────────


def _write_suite_diff_result(
    suite_dir: Path,
    *,
    baseline_viewport: str = "desktop",
    cells_spec: list[tuple[str, list[tuple[str, bool, bool]]]],
    # cells_spec: list of (file, [(compared_viewport, verdict_changed, matcher_changed), ...])
) -> Path:
    cells_payload = []
    for i, (jf, compared) in enumerate(cells_spec):
        compared_payload = []
        for j, (vp, vchanged, mchanged) in enumerate(compared):
            diff_dirname = f"diff-base{i}-vs-cmp{i}{j}"
            (suite_dir / diff_dirname).mkdir(exist_ok=True)
            compared_payload.append({
                "viewport": vp,
                "run_id": f"cmp-{i}-{j}",
                "verdict": "UNCLEAR" if vchanged else "PASS",
                "matcher": "y" if mchanged else "x",
                "verdict_changed": vchanged,
                "matcher_changed": mchanged,
                "first_divergence_kind": "action",
                "first_divergence_step": 1,
                "added_findings": 0,
                "removed_findings": 0,
                "diff_dir": diff_dirname,
                "diff_href": f"{diff_dirname}/diff.html",
            })
        cells_payload.append({
            "file": jf,
            "persona": "fresh",
            "baseline": {"viewport": baseline_viewport, "run_id": f"base-{i}",
                         "verdict": "PASS", "matcher": "x"},
            "compared": compared_payload,
        })
    sd_path = suite_dir / "suite-diff-result.json"
    sd_path.write_text(json.dumps({
        "schema": "webwitness/suite-diff/v1",
        "suite_id": suite_dir.name.removeprefix("suite-"),
        "baseline_viewport": baseline_viewport,
        "cells": cells_payload,
    }), encoding="utf-8")
    return sd_path


def test_suite_diff_badge_absent_without_file(tmp_path: Path):
    _write_suite_run(tmp_path, "20260425T100000Z", "site", "https://s.com/",
                     [("j.json", "fresh", "PASS")])
    payload = _index_payload(tmp_path)
    assert payload["suites"][0]["suite_diff"] is None


def test_suite_diff_badge_stable(tmp_path: Path):
    suite_dir = _write_suite_run(tmp_path, "20260425T110000Z", "s", "https://s.com/",
                                 [("j.json", "fresh", "PASS")])
    _write_suite_diff_result(suite_dir, cells_spec=[
        ("j.json", [("mobile", False, False), ("tablet", False, False)]),
    ])
    payload = _index_payload(tmp_path)
    sd = payload["suites"][0]["suite_diff"]
    assert sd["compared_total"] == 2
    assert sd["verdict_changed"] == 0
    assert sd["matcher_changed"] == 0
    assert sd["baseline_viewport"] == "desktop"
    assert sd["first_diff_href"] == "suite-20260425T110000Z/diff-base0-vs-cmp00/diff.html"


def test_suite_diff_badge_alert_counts(tmp_path: Path):
    suite_dir = _write_suite_run(tmp_path, "20260425T120000Z", "s", "https://s.com/",
                                 [("a.json", "fresh", "PASS"), ("b.json", "fresh", "PASS")])
    _write_suite_diff_result(suite_dir, cells_spec=[
        ("a.json", [("mobile", True, False), ("tablet", False, True)]),
        ("b.json", [("mobile", True, True),  ("tablet", False, False)]),
    ])
    payload = _index_payload(tmp_path)
    sd = payload["suites"][0]["suite_diff"]
    assert sd["compared_total"] == 4
    assert sd["verdict_changed"] == 2
    assert sd["matcher_changed"] == 2


def test_suite_diff_badge_malformed_file_treated_as_none(tmp_path: Path):
    suite_dir = _write_suite_run(tmp_path, "20260425T130000Z", "s", "https://s.com/",
                                 [("j.json", "fresh", "PASS")])
    (suite_dir / "suite-diff-result.json").write_text("{not json", encoding="utf-8")
    payload = _index_payload(tmp_path)
    assert payload["suites"][0]["suite_diff"] is None


def test_suite_diff_badge_empty_cells_treated_as_none(tmp_path: Path):
    # File present but no compared cells (e.g. single-viewport suite where
    # the diff was attempted but found nothing to compare against baseline).
    suite_dir = _write_suite_run(tmp_path, "20260425T140000Z", "s", "https://s.com/",
                                 [("j.json", "fresh", "PASS")])
    (suite_dir / "suite-diff-result.json").write_text(json.dumps({
        "schema": "webwitness/suite-diff/v1",
        "baseline_viewport": "desktop",
        "cells": [],
    }), encoding="utf-8")
    payload = _index_payload(tmp_path)
    assert payload["suites"][0]["suite_diff"] is None
