"""Tests for the journey-suite loader + runner. The runner is exercised
with run_journey monkeypatched so tests stay offline (no MCP, no LLM).

Live end-to-end coverage lives in `verify.py journey-suite <yaml>`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from journeys import suite as suite_mod
from journeys.suite import (
    SUITE_SCHEMA,
    SuiteRefusedError,
    load_suite,
    run_suite,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────


def _write_journey(dir_: Path, name: str, **overrides) -> Path:
    base = {
        "$schema": "webwitness/journey/v0.3",
        "intent": "Find what this site is about",
        "persona": "fresh",
        "target": "REPLACE_ME",
        "allowed_tactics": ["click_nav", "follow_link", "read_content"],
        "success": {"shape": "saw_content", "required_content": ["about"]},
        "patience": {"max_clicks": 4, "max_dead_ends": 2, "max_duration_ms": 30000},
    }
    base.update(overrides)
    p = dir_ / name
    p.write_text(json.dumps(base), encoding="utf-8")
    return p


def _write_suite(dir_: Path, name: str, doc: dict) -> Path:
    p = dir_ / name
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return p


# ─── load_suite: validation rejects ────────────────────────────────────────


def test_rejects_non_yaml_file(tmp_path: Path):
    p = tmp_path / "broken.yaml"
    p.write_text("::: not valid yaml :::", encoding="utf-8")
    with pytest.raises(SuiteRefusedError, match="not valid YAML"):
        load_suite(p)


def test_rejects_top_level_list(tmp_path: Path):
    p = _write_suite(tmp_path, "list.yaml", [{"target": "x"}])  # type: ignore[arg-type]
    with pytest.raises(SuiteRefusedError, match="mapping at top level"):
        load_suite(p)


def test_rejects_missing_target(tmp_path: Path):
    p = _write_suite(tmp_path, "no-target.yaml", {"journeys": []})
    with pytest.raises(SuiteRefusedError, match="'target'"):
        load_suite(p)


def test_rejects_empty_journeys(tmp_path: Path):
    p = _write_suite(tmp_path, "empty.yaml", {"target": "https://e.com/", "journeys": []})
    with pytest.raises(SuiteRefusedError, match="non-empty list"):
        load_suite(p)


def test_rejects_journey_file_missing(tmp_path: Path):
    p = _write_suite(tmp_path, "missing.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": "does-not-exist.json"}],
    })
    with pytest.raises(SuiteRefusedError, match="not found"):
        load_suite(p)


def test_rejects_unknown_persona_override(tmp_path: Path):
    j = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "bad-persona.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": j.name, "persona": "ghost"}],
    })
    with pytest.raises(SuiteRefusedError, match="persona 'ghost'"):
        load_suite(p)


def test_rejects_schema_mismatch(tmp_path: Path):
    j = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "bad-schema.yaml", {
        "schema": "webwitness/site/v0.99",
        "target": "https://e.com/",
        "journeys": [{"file": j.name}],
    })
    with pytest.raises(SuiteRefusedError, match="schema mismatch"):
        load_suite(p)


def test_rejects_journey_with_invalid_persona_in_file(tmp_path: Path):
    # The journey file itself names a non-existent persona — should
    # surface the journey-loader error wrapped as SuiteRefusedError.
    j = _write_journey(tmp_path, "j1.json", persona="ghost")
    p = _write_suite(tmp_path, "ok.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": j.name}],
    })
    with pytest.raises(SuiteRefusedError, match="failed validation"):
        load_suite(p)


# ─── load_suite: happy path ────────────────────────────────────────────────


def test_loads_minimal_suite(tmp_path: Path):
    j = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "ok.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": j.name}],
    })
    suite = load_suite(p)
    assert suite["schema"] == SUITE_SCHEMA
    assert suite["target"] == "https://e.com/"
    assert len(suite["journeys"]) == 1
    row = suite["journeys"][0]
    assert row["file"] == "j1.json"
    assert row["_journey"]["persona"] == "fresh"
    # Suite-level target was applied to the journey doc.
    assert row["_journey"]["target"] == "https://e.com/"


def test_persona_override_applied_before_validation(tmp_path: Path):
    j = _write_journey(tmp_path, "j1.json", persona="fresh")
    p = _write_suite(tmp_path, "ok.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": j.name, "persona": "returning"}],
    })
    suite = load_suite(p)
    row = suite["journeys"][0]
    assert row["persona_override"] == "returning"
    assert row["_journey"]["persona"] == "returning"


def test_target_overrides_template_placeholder(tmp_path: Path):
    # Templates use REPLACE_ME_WITH_TARGET_URL — that would fail SSRF
    # validation alone. With the suite target, it should pass.
    j = _write_journey(tmp_path, "j1.json", target="REPLACE_ME_WITH_TARGET_URL")
    p = _write_suite(tmp_path, "ok.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": j.name}],
    })
    suite = load_suite(p)
    assert suite["journeys"][0]["_journey"]["target"] == "https://e.com/"


def test_resolves_paths_relative_to_yaml_dir(tmp_path: Path):
    sub = tmp_path / "j"
    sub.mkdir()
    j = _write_journey(sub, "j1.json")
    p = _write_suite(tmp_path, "ok.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": "j/j1.json"}],
    })
    suite = load_suite(p)
    assert suite["journeys"][0]["_path"] == j.resolve()


# ─── run_suite: shape + verdict roll-up ────────────────────────────────────


def _fake_runner_factory(verdicts: list[str]):
    """Return a run_journey replacement that hands out the given
    verdicts in order, one per call."""
    calls = {"i": 0}

    def fake_run_journey(journey, run_id=None, artefacts_root=None, viewport=None):
        v = verdicts[calls["i"]]
        calls["i"] += 1
        run_id = run_id or f"fake-{calls['i']}"
        # Mirror what the real runner writes — the suite reads back from
        # the result dict, not from disk, so we can skip artefact writes.
        return {
            "run_id": run_id,
            "verdict": v,
            "matcher": "fake",
            "iterations": 2,
            "clicks_used": 1,
            "dead_ends": 0,
            "duration_ms": 100,
            "viewport": viewport,
            "artefacts_dir": str((artefacts_root or Path("/tmp")) / run_id),
            "error": None,
            "pass": v == "PASS",
        }

    return fake_run_journey


def test_run_suite_rolls_up_verdicts(tmp_path: Path, monkeypatch, ):
    j1 = _write_journey(tmp_path, "j1.json")
    j2 = _write_journey(tmp_path, "j2.json", intent="Different intent")
    p = _write_suite(tmp_path, "ok.yaml", {
        "label": "test site",
        "target": "https://e.com/",
        "journeys": [{"file": j1.name}, {"file": j2.name, "persona": "returning"}],
    })
    suite = load_suite(p)

    # Redirect ARTEFACTS_ROOT to tmp so we don't pollute the real one.
    import verify
    monkeypatch.setattr(verify, "ARTEFACTS_ROOT", tmp_path / "artefacts")
    monkeypatch.setattr(suite_mod, "run_journey", _fake_runner_factory(["PASS", "UNCLEAR"]))

    result = run_suite(suite, suite_id="20260424T120000Z")
    assert result["site"]["label"] == "test site"
    assert result["site"]["target"] == "https://e.com/"
    assert result["verdict_summary"] == {"PASS": 1, "FAIL": 0, "UNCLEAR": 1}
    assert len(result["journeys"]) == 2
    assert result["journeys"][0]["persona"] == "fresh"
    assert result["journeys"][1]["persona"] == "returning"
    assert result["journeys"][1]["persona_override"] == "returning"

    # Suite dir + suite-result.json + suite.json were written.
    suite_dir = tmp_path / "artefacts" / "suite-20260424T120000Z"
    assert suite_dir.is_dir()
    assert (suite_dir / "suite.json").is_file()
    assert (suite_dir / "suite-result.json").is_file()

    # suite-result.json round-trips.
    on_disk = json.loads((suite_dir / "suite-result.json").read_text())
    assert on_disk["verdict_summary"]["PASS"] == 1


def test_run_suite_all_pass_returns_clean_summary(tmp_path: Path, monkeypatch):
    j1 = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "ok.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": j1.name}],
    })
    suite = load_suite(p)

    import verify
    monkeypatch.setattr(verify, "ARTEFACTS_ROOT", tmp_path / "artefacts")
    monkeypatch.setattr(suite_mod, "run_journey", _fake_runner_factory(["PASS"]))

    result = run_suite(suite)
    assert result["verdict_summary"] == {"PASS": 1, "FAIL": 0, "UNCLEAR": 0}


# ─── P7: viewport axis ─────────────────────────────────────────────────────


def test_suite_without_viewports_is_unaffected(tmp_path: Path):
    j1 = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "no-vp.yaml", {
        "target": "https://e.com/",
        "journeys": [{"file": j1.name}],
    })
    suite = load_suite(p)
    assert suite["viewports"] is None
    plans = suite_mod.expand_rows(suite)
    assert len(plans) == 1
    assert plans[0]["viewport"] is None


def test_suite_level_viewports_expand_rows(tmp_path: Path):
    j1 = _write_journey(tmp_path, "j1.json")
    j2 = _write_journey(tmp_path, "j2.json", intent="Other intent")
    p = _write_suite(tmp_path, "vp.yaml", {
        "target": "https://e.com/",
        "viewports": [
            {"label": "desktop", "width": 1280, "height": 800},
            {"label": "mobile", "width": 375, "height": 667},
        ],
        "journeys": [{"file": j1.name}, {"file": j2.name}],
    })
    suite = load_suite(p)
    assert len(suite["viewports"]) == 2
    plans = suite_mod.expand_rows(suite)
    # 2 journeys × 2 viewports = 4 plans.
    assert len(plans) == 4
    labels = [(plan["row"]["file"], plan["viewport"]["label"]) for plan in plans]
    assert labels == [
        ("j1.json", "desktop"), ("j1.json", "mobile"),
        ("j2.json", "desktop"), ("j2.json", "mobile"),
    ]


def test_per_row_viewports_override_site_level(tmp_path: Path):
    j1 = _write_journey(tmp_path, "j1.json")
    j2 = _write_journey(tmp_path, "j2.json")
    p = _write_suite(tmp_path, "mixed.yaml", {
        "target": "https://e.com/",
        "viewports": [{"label": "desktop", "width": 1280, "height": 800}],
        "journeys": [
            {"file": j1.name},  # uses site-level (desktop only)
            {"file": j2.name, "viewports": [
                {"label": "mobile", "width": 375, "height": 667},
                {"label": "tablet", "width": 768, "height": 1024},
            ]},
        ],
    })
    suite = load_suite(p)
    plans = suite_mod.expand_rows(suite)
    assert len(plans) == 3  # 1 + 2
    assert plans[0]["viewport"]["label"] == "desktop"
    assert plans[1]["viewport"]["label"] == "mobile"
    assert plans[2]["viewport"]["label"] == "tablet"


def test_viewports_validation_rejects_non_list(tmp_path: Path):
    j1 = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "bad.yaml", {
        "target": "https://e.com/",
        "viewports": "desktop",
        "journeys": [{"file": j1.name}],
    })
    with pytest.raises(SuiteRefusedError, match="non-empty list"):
        load_suite(p)


def test_viewports_validation_rejects_missing_dimensions(tmp_path: Path):
    j1 = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "bad.yaml", {
        "target": "https://e.com/",
        "viewports": [{"label": "x", "width": 100}],  # no height
        "journeys": [{"file": j1.name}],
    })
    with pytest.raises(SuiteRefusedError, match="height"):
        load_suite(p)


def test_viewports_validation_rejects_duplicate_labels(tmp_path: Path):
    j1 = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "bad.yaml", {
        "target": "https://e.com/",
        "viewports": [
            {"label": "x", "width": 100, "height": 100},
            {"label": "x", "width": 200, "height": 200},
        ],
        "journeys": [{"file": j1.name}],
    })
    with pytest.raises(SuiteRefusedError, match="duplicated"):
        load_suite(p)


def test_run_suite_passes_viewport_to_runner_and_records_in_row(
    tmp_path: Path, monkeypatch,
):
    j1 = _write_journey(tmp_path, "j1.json")
    p = _write_suite(tmp_path, "vp.yaml", {
        "target": "https://e.com/",
        "viewports": [
            {"label": "desktop", "width": 1280, "height": 800},
            {"label": "mobile", "width": 375, "height": 667},
        ],
        "journeys": [{"file": j1.name}],
    })
    suite = load_suite(p)

    import verify
    monkeypatch.setattr(verify, "ARTEFACTS_ROOT", tmp_path / "artefacts")

    seen_viewports: list[dict | None] = []

    def capturing_runner(journey, run_id=None, artefacts_root=None, viewport=None):
        seen_viewports.append(viewport)
        return {
            "run_id": run_id or "x",
            "verdict": "PASS",
            "matcher": "fake",
            "iterations": 1,
            "clicks_used": 0,
            "dead_ends": 0,
            "duration_ms": 1,
            "viewport": viewport,
            "artefacts_dir": str((artefacts_root or Path("/tmp")) / (run_id or "x")),
            "error": None,
            "pass": True,
        }

    monkeypatch.setattr(suite_mod, "run_journey", capturing_runner)

    result = run_suite(suite)
    # Runner saw both viewports.
    assert [v["label"] for v in seen_viewports] == ["desktop", "mobile"]
    # suite-result rows carry the viewport.
    assert [row["viewport"]["label"] for row in result["journeys"]] == ["desktop", "mobile"]


def test_run_journey_accepts_viewport_kwarg():
    """Smoke: run_journey signature accepts viewport= without exploding.
    Doesn't actually run — just verifies the kwarg is in the signature."""
    import inspect
    from journeys.runner import run_journey
    sig = inspect.signature(run_journey)
    assert "viewport" in sig.parameters
