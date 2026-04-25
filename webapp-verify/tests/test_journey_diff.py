"""Tests for journeys.diff — single-journey regression diff (P3).

Builds synthetic run directories on disk (decisions.jsonl + result.json +
journey.json + optional findings.json) and asserts the diff payload shape.
No MCP, no LLM — pure logic coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from journeys.diff import (
    DIFF_SCHEMA,
    SUITE_DIFF_SCHEMA,
    DiffError,
    default_out_dir,
    diff_runs,
    diff_suite_viewports,
    write_diff,
    write_suite_diff,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────


def _make_run(
    base: Path,
    run_id: str,
    *,
    decisions: list[dict],
    verdict: str = "PASS",
    matcher: str = "saw_content",
    persona: str = "fresh",
    target: str = "https://example.com/",
    intent: str = "Find what this site is about.",
    success: dict | None = None,
    findings: list[dict] | None = None,
    has_report: bool = False,
) -> Path:
    """Lay out a single-journey run directory with the expected artefacts."""
    run_dir = base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    journey = {
        "$schema": "webwitness/journey/v0.3",
        "intent": intent,
        "persona": persona,
        "target": target,
        "allowed_tactics": ["click_nav", "follow_link", "read_content"],
        "success": success or {"shape": "saw_content", "required_content": ["about"]},
        "patience": {"max_clicks": 4, "max_dead_ends": 2, "max_duration_ms": 30000},
    }
    (run_dir / "journey.json").write_text(json.dumps(journey), encoding="utf-8")

    with (run_dir / "decisions.jsonl").open("w", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps(d) + "\n")

    result = {
        "run_id": run_id,
        "pass": verdict == "PASS",
        "verdict": verdict,
        "matcher": matcher,
        "iterations": len(decisions),
        "clicks_used": sum(1 for d in decisions if d.get("action", "").startswith("click")),
        "duration_ms": 12345,
        "_journey": True,
    }
    (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")

    if findings is not None:
        (run_dir / "findings.json").write_text(
            json.dumps({"findings": findings}), encoding="utf-8"
        )
    if has_report:
        (run_dir / "report.html").write_text("<html>stub</html>", encoding="utf-8")

    return run_dir


def _step(action: str, *, target_name: str | None = None, target_role: str | None = None,
          url: str = "https://example.com/", iter_: int = 1, rationale: str = "rationale text") -> dict:
    out = {"iter": iter_, "action": action, "url": url, "rationale": rationale}
    if target_name is not None:
        out["target_name"] = target_name
    if target_role is not None:
        out["target_role"] = target_role
    return out


# ─── _load_run rejects ──────────────────────────────────────────────────────


def test_rejects_non_directory(tmp_path: Path):
    bogus = tmp_path / "ghost"
    with pytest.raises(DiffError, match="not a directory"):
        diff_runs(bogus, bogus)


def test_rejects_suite_dir(tmp_path: Path):
    suite = tmp_path / "suite-001"
    suite.mkdir()
    (suite / "suite-result.json").write_text("{}", encoding="utf-8")
    real_run = _make_run(tmp_path, "20260425T000000Z",
                         decisions=[_step("done", url="https://example.com/")])
    with pytest.raises(DiffError, match="suite directory"):
        diff_runs(suite, real_run)


def test_rejects_run_missing_decisions(tmp_path: Path):
    run_dir = tmp_path / "incomplete"
    run_dir.mkdir()
    (run_dir / "result.json").write_text("{}", encoding="utf-8")
    (run_dir / "journey.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DiffError, match="missing artefact"):
        diff_runs(run_dir, run_dir)


def test_rejects_malformed_jsonl(tmp_path: Path):
    run_dir = _make_run(tmp_path, "20260425T000000Z",
                        decisions=[_step("done")])
    (run_dir / "decisions.jsonl").write_text("not json\n", encoding="utf-8")
    with pytest.raises(DiffError, match="malformed JSONL"):
        diff_runs(run_dir, run_dir)


# ─── identical runs ─────────────────────────────────────────────────────────


def test_identical_runs_have_no_divergence(tmp_path: Path):
    decisions = [
        _step("click_nav", target_name="About", target_role="link", iter_=1),
        _step("read_content", iter_=2, url="https://example.com/about"),
        _step("done", iter_=3, url="https://example.com/about"),
    ]
    run_a = _make_run(tmp_path, "20260425T070000Z", decisions=decisions)
    run_b = _make_run(tmp_path, "20260425T080000Z", decisions=decisions)

    payload = diff_runs(run_a, run_b)

    assert payload["schema"] == DIFF_SCHEMA
    assert payload["first_divergence"]["kind"] == "none"
    assert payload["first_divergence"]["step_index"] is None
    assert payload["verdict_changed"] is False
    assert payload["matcher_changed"] is False
    assert all(row["divergent"] is False for row in payload["step_table"])
    assert payload["findings_diff"] == {"added": [], "removed": [], "shared": []}


# ─── single-step divergence ─────────────────────────────────────────────────


def test_action_divergence_is_first(tmp_path: Path):
    a_decisions = [_step("click_nav", target_name="About", iter_=1)]
    b_decisions = [_step("read_content", iter_=1)]
    run_a = _make_run(tmp_path, "A", decisions=a_decisions)
    run_b = _make_run(tmp_path, "B", decisions=b_decisions)

    payload = diff_runs(run_a, run_b)

    assert payload["first_divergence"]["kind"] == "action"
    assert payload["first_divergence"]["step_index"] == 1
    assert payload["step_table"][0]["divergent"] is True


def test_target_name_divergence_after_match(tmp_path: Path):
    common = _step("click_nav", target_name="About", iter_=1)
    a_decisions = [common, _step("click_nav", target_name="Pricing", iter_=2)]
    b_decisions = [common, _step("click_nav", target_name="Contact", iter_=2)]
    run_a = _make_run(tmp_path, "A", decisions=a_decisions)
    run_b = _make_run(tmp_path, "B", decisions=b_decisions)

    payload = diff_runs(run_a, run_b)

    assert payload["first_divergence"]["kind"] == "target_name"
    assert payload["first_divergence"]["step_index"] == 2
    assert payload["step_table"][0]["divergent"] is False
    assert payload["step_table"][1]["divergent"] is True


def test_url_divergence_when_action_and_target_match(tmp_path: Path):
    a_decisions = [_step("click_nav", target_name="About", url="https://example.com/old", iter_=1)]
    b_decisions = [_step("click_nav", target_name="About", url="https://example.com/new", iter_=1)]
    run_a = _make_run(tmp_path, "A", decisions=a_decisions)
    run_b = _make_run(tmp_path, "B", decisions=b_decisions)

    payload = diff_runs(run_a, run_b)

    assert payload["first_divergence"]["kind"] == "url"
    assert payload["first_divergence"]["step_index"] == 1


# ─── length mismatch ────────────────────────────────────────────────────────


def test_length_divergence_b_longer(tmp_path: Path):
    common = _step("click_nav", target_name="About", iter_=1)
    a_decisions = [common]
    b_decisions = [common, _step("done", iter_=2, url="https://example.com/about")]
    run_a = _make_run(tmp_path, "A", decisions=a_decisions)
    run_b = _make_run(tmp_path, "B", decisions=b_decisions)

    payload = diff_runs(run_a, run_b)

    assert payload["first_divergence"]["kind"] == "length"
    assert payload["first_divergence"]["step_index"] == 2
    assert payload["step_table"][1]["kind"] == "missing_a"
    assert payload["step_table"][1]["a"] is None
    assert payload["step_table"][1]["b"] is not None


def test_length_divergence_a_longer(tmp_path: Path):
    common = _step("click_nav", target_name="About", iter_=1)
    a_decisions = [common, _step("done", iter_=2, url="https://example.com/about")]
    b_decisions = [common]
    run_a = _make_run(tmp_path, "A", decisions=a_decisions)
    run_b = _make_run(tmp_path, "B", decisions=b_decisions)

    payload = diff_runs(run_a, run_b)

    assert payload["first_divergence"]["kind"] == "length"
    assert payload["step_table"][1]["kind"] == "missing_b"


# ─── matcher_only divergence ────────────────────────────────────────────────


def test_matcher_only_divergence_when_steps_match_but_verdict_differs(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    run_a = _make_run(tmp_path, "A", decisions=decisions, verdict="PASS", matcher="saw_content")
    run_b = _make_run(tmp_path, "B", decisions=decisions, verdict="UNCLEAR", matcher="llm_done_unverified")

    payload = diff_runs(run_a, run_b)

    assert payload["first_divergence"]["kind"] == "matcher_only"
    assert payload["first_divergence"]["step_index"] is None
    assert payload["verdict_changed"] is True
    assert payload["matcher_changed"] is True


# ─── findings diff ──────────────────────────────────────────────────────────


def test_findings_added_and_removed(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    f_old = {"rule_id": "missing-h1", "severity": "warn", "description": "no h1", "node_repr": "DOM root"}
    f_new = {"rule_id": "no-contact-reachable", "severity": "warn",
             "description": "no contact info", "node_repr": "final URL: x"}
    run_a = _make_run(tmp_path, "A", decisions=decisions, findings=[f_old])
    run_b = _make_run(tmp_path, "B", decisions=decisions, findings=[f_new])

    payload = diff_runs(run_a, run_b)
    fd = payload["findings_diff"]

    assert len(fd["added"]) == 1
    assert fd["added"][0]["rule_id"] == "no-contact-reachable"
    assert len(fd["removed"]) == 1
    assert fd["removed"][0]["rule_id"] == "missing-h1"
    assert fd["shared"] == []


def test_findings_shared_when_rule_id_and_node_match(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    f = {"rule_id": "missing-h1", "severity": "warn",
         "description": "wording version 1", "node_repr": "DOM root"}
    f_alt = {"rule_id": "missing-h1", "severity": "warn",
             "description": "wording version 2 — drift", "node_repr": "DOM root"}
    run_a = _make_run(tmp_path, "A", decisions=decisions, findings=[f])
    run_b = _make_run(tmp_path, "B", decisions=decisions, findings=[f_alt])

    payload = diff_runs(run_a, run_b)
    fd = payload["findings_diff"]

    assert fd["added"] == []
    assert fd["removed"] == []
    assert len(fd["shared"]) == 1


# ─── journey-shape changed ──────────────────────────────────────────────────


def test_journey_changed_flagged_when_target_differs(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    run_a = _make_run(tmp_path, "A", decisions=decisions, target="https://example.com/")
    run_b = _make_run(tmp_path, "B", decisions=decisions, target="https://other.example/")

    payload = diff_runs(run_a, run_b)

    assert payload["journey_changed"] is True


def test_journey_unchanged_when_only_run_id_differs(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    run_a = _make_run(tmp_path, "A", decisions=decisions)
    run_b = _make_run(tmp_path, "B", decisions=decisions)

    payload = diff_runs(run_a, run_b)

    assert payload["journey_changed"] is False


# ─── write_diff + default_out_dir ───────────────────────────────────────────


def test_write_diff_creates_dir_and_file(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    run_a = _make_run(tmp_path, "A", decisions=decisions)
    run_b = _make_run(tmp_path, "B", decisions=decisions)

    payload = diff_runs(run_a, run_b)
    out_dir = default_out_dir(tmp_path, "A", "B")
    out_path = write_diff(payload, out_dir)

    assert out_path.exists()
    assert out_path.name == "diff-result.json"
    assert out_path.parent == out_dir
    assert json.loads(out_path.read_text(encoding="utf-8"))["diff_id"] == "A-vs-B"


def test_default_out_dir_naming(tmp_path: Path):
    out = default_out_dir(tmp_path, "A", "B")
    assert out.name == "diff-A-vs-B"
    assert out.parent == tmp_path


# ─── suite-diff (viewport-vs-viewport across a P7 suite) ────────────────────


def _make_suite(
    tmp_path: Path,
    suite_id: str,
    *,
    cells: list[dict],
) -> Path:
    """Lay out a suite-<id>/ directory with one journey-run dir per cell.

    Each cell dict: {file, persona, viewport_label, viewport_w, viewport_h,
                     verdict, matcher, decisions, findings?}
    """
    suite_dir = tmp_path / f"suite-{suite_id}"
    suite_dir.mkdir(parents=True, exist_ok=True)

    journey_rows = []
    for i, c in enumerate(cells):
        run_id = f"r-{i}"
        run_dir = _make_run(
            suite_dir,
            run_id,
            decisions=c["decisions"],
            verdict=c.get("verdict", "PASS"),
            matcher=c.get("matcher", "saw_content"),
            persona=c.get("persona", "fresh"),
            findings=c.get("findings"),
        )
        journey_rows.append({
            "file": c["file"],
            "persona": c.get("persona", "fresh"),
            "viewport": {
                "label": c["viewport_label"],
                "width": c["viewport_w"],
                "height": c["viewport_h"],
            },
            "run_id": run_id,
            "verdict": c.get("verdict", "PASS"),
            "matcher": c.get("matcher", "saw_content"),
            "iterations": len(c["decisions"]),
            "duration_ms": 1234,
            "artefacts_dir": str(run_dir),
        })

    (suite_dir / "suite-result.json").write_text(json.dumps({
        "suite_id": suite_id,
        "site": {"label": "test", "target": "https://example.com/"},
        "journeys": journey_rows,
        "verdict_summary": {"PASS": sum(1 for c in cells if c.get("verdict", "PASS") == "PASS"),
                             "UNCLEAR": sum(1 for c in cells if c.get("verdict") == "UNCLEAR"),
                             "FAIL": sum(1 for c in cells if c.get("verdict") == "FAIL")},
        "duration_ms": 9999,
        "_suite": True,
    }), encoding="utf-8")
    return suite_dir


def test_suite_diff_rejects_dir_without_suite_result(tmp_path: Path):
    bare = tmp_path / "not-a-suite"
    bare.mkdir()
    with pytest.raises(DiffError, match="not a suite directory"):
        diff_suite_viewports(bare)


def test_suite_diff_rejects_suite_without_viewport_axis(tmp_path: Path):
    suite_dir = tmp_path / "suite-noaxis"
    suite_dir.mkdir()
    (suite_dir / "suite-result.json").write_text(json.dumps({
        "suite_id": "noaxis",
        "site": {"label": "x", "target": "https://x.com/"},
        "journeys": [{
            "file": "j1.json", "persona": "fresh", "viewport": None,
            "run_id": "r-0", "verdict": "PASS", "matcher": "x",
            "iterations": 1, "duration_ms": 1, "artefacts_dir": str(suite_dir / "r-0"),
        }],
    }), encoding="utf-8")
    with pytest.raises(DiffError, match="no viewport axis"):
        diff_suite_viewports(suite_dir)


def test_suite_diff_pairs_each_non_baseline_viewport(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    suite_dir = _make_suite(tmp_path, "20260425T120000Z", cells=[
        {"file": "j1.json", "persona": "fresh", "viewport_label": "desktop",
         "viewport_w": 1280, "viewport_h": 800, "decisions": decisions,
         "verdict": "PASS"},
        {"file": "j1.json", "persona": "fresh", "viewport_label": "mobile",
         "viewport_w": 375, "viewport_h": 667, "decisions": decisions,
         "verdict": "UNCLEAR", "matcher": "patience.max_page_wait_ms"},
    ])
    payload = diff_suite_viewports(suite_dir)
    assert payload["schema"] == SUITE_DIFF_SCHEMA
    assert payload["baseline_viewport"] == "desktop"
    assert len(payload["cells"]) == 1
    cell = payload["cells"][0]
    assert cell["baseline"]["viewport"] == "desktop"
    assert len(cell["compared"]) == 1
    cmp = cell["compared"][0]
    assert cmp["viewport"] == "mobile"
    assert cmp["verdict_changed"] is True


def test_suite_diff_baseline_override(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    suite_dir = _make_suite(tmp_path, "20260425T130000Z", cells=[
        {"file": "j1.json", "persona": "fresh", "viewport_label": "desktop",
         "viewport_w": 1280, "viewport_h": 800, "decisions": decisions},
        {"file": "j1.json", "persona": "fresh", "viewport_label": "mobile",
         "viewport_w": 375, "viewport_h": 667, "decisions": decisions},
    ])
    payload = diff_suite_viewports(suite_dir, baseline_viewport="mobile")
    assert payload["baseline_viewport"] == "mobile"
    cell = payload["cells"][0]
    assert cell["baseline"]["viewport"] == "mobile"
    assert cell["compared"][0]["viewport"] == "desktop"


def test_suite_diff_baseline_override_unknown_rejected(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    suite_dir = _make_suite(tmp_path, "20260425T140000Z", cells=[
        {"file": "j1.json", "persona": "fresh", "viewport_label": "desktop",
         "viewport_w": 1280, "viewport_h": 800, "decisions": decisions},
        {"file": "j1.json", "persona": "fresh", "viewport_label": "mobile",
         "viewport_w": 375, "viewport_h": 667, "decisions": decisions},
    ])
    with pytest.raises(DiffError, match="not present"):
        diff_suite_viewports(suite_dir, baseline_viewport="watch")


def test_suite_diff_groups_by_file_and_persona(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    suite_dir = _make_suite(tmp_path, "20260425T150000Z", cells=[
        {"file": "j1.json", "persona": "fresh",     "viewport_label": "desktop", "viewport_w": 1280, "viewport_h": 800, "decisions": decisions},
        {"file": "j1.json", "persona": "fresh",     "viewport_label": "mobile",  "viewport_w": 375,  "viewport_h": 667, "decisions": decisions},
        {"file": "j1.json", "persona": "returning", "viewport_label": "desktop", "viewport_w": 1280, "viewport_h": 800, "decisions": decisions},
        {"file": "j1.json", "persona": "returning", "viewport_label": "mobile",  "viewport_w": 375,  "viewport_h": 667, "decisions": decisions},
        {"file": "j2.json", "persona": "fresh",     "viewport_label": "desktop", "viewport_w": 1280, "viewport_h": 800, "decisions": decisions},
        {"file": "j2.json", "persona": "fresh",     "viewport_label": "mobile",  "viewport_w": 375,  "viewport_h": 667, "decisions": decisions},
    ])
    payload = diff_suite_viewports(suite_dir)
    # 3 cells: (j1, fresh), (j1, returning), (j2, fresh)
    assert len(payload["cells"]) == 3
    assert all(len(c["compared"]) == 1 for c in payload["cells"])


def test_suite_diff_skips_cells_missing_baseline(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    suite_dir = _make_suite(tmp_path, "20260425T160000Z", cells=[
        {"file": "j1.json", "persona": "fresh", "viewport_label": "desktop", "viewport_w": 1280, "viewport_h": 800, "decisions": decisions},
        {"file": "j1.json", "persona": "fresh", "viewport_label": "mobile",  "viewport_w": 375,  "viewport_h": 667, "decisions": decisions},
        # j2 only ran on mobile — no desktop baseline.
        {"file": "j2.json", "persona": "fresh", "viewport_label": "mobile",  "viewport_w": 375,  "viewport_h": 667, "decisions": decisions},
    ])
    payload = diff_suite_viewports(suite_dir)
    j2_cell = next(c for c in payload["cells"] if c["file"] == "j2.json")
    assert j2_cell["baseline"] is None
    assert "skipped_reason" in j2_cell


def test_write_suite_diff_emits_per_pair_dirs(tmp_path: Path):
    decisions = [_step("done", iter_=1)]
    suite_dir = _make_suite(tmp_path, "20260425T170000Z", cells=[
        {"file": "j1.json", "persona": "fresh", "viewport_label": "desktop", "viewport_w": 1280, "viewport_h": 800, "decisions": decisions},
        {"file": "j1.json", "persona": "fresh", "viewport_label": "mobile",  "viewport_w": 375,  "viewport_h": 667, "decisions": decisions},
    ])
    payload = diff_suite_viewports(suite_dir)
    out_path = write_suite_diff(payload, suite_dir)

    assert out_path.exists()
    assert out_path.name == "suite-diff-result.json"

    # Per-pair diff dir was emitted alongside.
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    cmp = on_disk["cells"][0]["compared"][0]
    assert "diff_dir" in cmp
    assert cmp["diff_href"].endswith("/diff.html")
    pair_dir = suite_dir / cmp["diff_dir"]
    assert (pair_dir / "diff-result.json").exists()
    # _pair_payload was stripped from the on-disk roll-up.
    assert "_pair_payload" not in cmp
