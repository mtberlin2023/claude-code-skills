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
