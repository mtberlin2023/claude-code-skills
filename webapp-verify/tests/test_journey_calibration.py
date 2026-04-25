"""Tests for the 2026-04-25 calibration changes:
- scroll dropped from DEFAULT_ALLOWED_TACTICS
- llm_judged success shape (validation only — judge call is offline-mocked)
- max_page_wait_ms patience field validation"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from journeys.loader import (
    DEFAULT_ALLOWED_TACTICS,
    DEFAULT_PATIENCE,
    JourneyRefusedError,
    load_journey,
)


def _write_journey(tmp_path: Path, **overrides) -> Path:
    base = {
        "$schema": "webwitness/journey/v0.3",
        "intent": "x",
        "persona": "fresh",
        "target": "https://e.com/",
        "success": {"shape": "saw_content", "required_content": ["x"]},
    }
    base.update(overrides)
    p = tmp_path / "j.json"
    p.write_text(json.dumps(base), encoding="utf-8")
    return p


# ─── scroll dropped from default ─────────────────────────────────────────


def test_scroll_not_in_default_tactics():
    assert "scroll" not in DEFAULT_ALLOWED_TACTICS
    # core navigation tactics still there
    for t in ("click_nav", "click_cta", "follow_link", "read_content"):
        assert t in DEFAULT_ALLOWED_TACTICS


def test_journey_without_allowed_tactics_uses_default(tmp_path: Path):
    p = _write_journey(tmp_path)
    j = load_journey(p)
    assert "scroll" not in j["_resolved"]["tactics"]
    assert "click_nav" in j["_resolved"]["tactics"]


def test_journey_can_still_opt_into_scroll_explicitly(tmp_path: Path):
    p = _write_journey(tmp_path, allowed_tactics=["click_nav", "scroll"])
    j = load_journey(p)
    assert "scroll" in j["_resolved"]["tactics"]


# ─── llm_judged shape ────────────────────────────────────────────────────


def test_llm_judged_requires_criterion(tmp_path: Path):
    p = _write_journey(tmp_path, success={"shape": "llm_judged"})
    with pytest.raises(JourneyRefusedError, match="criterion"):
        load_journey(p)


def test_llm_judged_rejects_empty_criterion(tmp_path: Path):
    p = _write_journey(tmp_path, success={"shape": "llm_judged", "criterion": "   "})
    with pytest.raises(JourneyRefusedError, match="criterion"):
        load_journey(p)


def test_llm_judged_rejects_non_string_criterion(tmp_path: Path):
    p = _write_journey(tmp_path, success={"shape": "llm_judged", "criterion": ["a", "b"]})
    with pytest.raises(JourneyRefusedError, match="criterion"):
        load_journey(p)


def test_llm_judged_with_valid_criterion(tmp_path: Path):
    p = _write_journey(tmp_path, success={
        "shape": "llm_judged",
        "criterion": "The simulated user understood the site's positioning and target audience.",
    })
    j = load_journey(p)
    assert j["success"]["shape"] == "llm_judged"
    assert "positioning" in j["success"]["criterion"]


# ─── max_page_wait_ms patience field ─────────────────────────────────────


def test_default_patience_includes_page_wait():
    assert "max_page_wait_ms" in DEFAULT_PATIENCE
    assert DEFAULT_PATIENCE["max_page_wait_ms"] > 0
    assert DEFAULT_PATIENCE["max_duration_ms"] >= DEFAULT_PATIENCE["max_page_wait_ms"]


def test_max_page_wait_ms_validates_positive(tmp_path: Path):
    p = _write_journey(tmp_path, patience={"max_page_wait_ms": -1})
    with pytest.raises(JourneyRefusedError, match="max_page_wait_ms"):
        load_journey(p)


def test_max_page_wait_ms_validates_int(tmp_path: Path):
    p = _write_journey(tmp_path, patience={"max_page_wait_ms": "30s"})
    with pytest.raises(JourneyRefusedError, match="max_page_wait_ms"):
        load_journey(p)


def test_max_page_wait_ms_user_override(tmp_path: Path):
    p = _write_journey(tmp_path, patience={"max_page_wait_ms": 5000})
    j = load_journey(p)
    assert j["_resolved"]["patience"]["max_page_wait_ms"] == 5000


def test_journey_without_patience_block_inherits_both_clocks(tmp_path: Path):
    p = _write_journey(tmp_path)
    j = load_journey(p)
    assert "max_page_wait_ms" in j["_resolved"]["patience"]
    assert "max_duration_ms" in j["_resolved"]["patience"]


# ─── dismiss_consent tactic (P8) ────────────────────────────────────────


def test_dismiss_consent_in_default_tactics():
    assert "dismiss_consent" in DEFAULT_ALLOWED_TACTICS


def test_dismiss_consent_resolves_for_default_journey(tmp_path: Path):
    p = _write_journey(tmp_path)
    j = load_journey(p)
    assert "dismiss_consent" in j["_resolved"]["tactics"]


def test_dismiss_consent_can_be_explicitly_listed(tmp_path: Path):
    p = _write_journey(tmp_path, allowed_tactics=["click_nav", "dismiss_consent"])
    j = load_journey(p)
    assert "dismiss_consent" in j["_resolved"]["tactics"]
    assert "click_nav" in j["_resolved"]["tactics"]


def test_dismiss_consent_can_be_forbidden(tmp_path: Path):
    p = _write_journey(tmp_path, forbidden_tactics=["dismiss_consent"])
    j = load_journey(p)
    assert "dismiss_consent" not in j["_resolved"]["tactics"]


def test_dismiss_consent_recognised_by_selector_decision_set():
    from journeys.selector import DECISION_ACTIONS, TACTICS_NEED_TARGET
    assert "dismiss_consent" in DECISION_ACTIONS
    assert "dismiss_consent" in TACTICS_NEED_TARGET  # needs role+name like a click


def test_dismiss_consent_mapped_to_click_in_runner():
    from journeys.runner import ACTION_TO_TOOL, PATIENCE_FREE_TACTICS
    assert ACTION_TO_TOOL.get("dismiss_consent") == "click"
    assert "dismiss_consent" in PATIENCE_FREE_TACTICS
