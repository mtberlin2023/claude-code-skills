"""Unit tests for the journey expander — parser robustness + prompt
shape. The live LLM round-trip is exercised separately by the smoke
test in `journeys/acceptance-undavos-fresh.json` and the `expand` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from journeys.expander import (
    ExpanderError,
    _build_prompt,
    _parse_journey_json,
    _strip_code_fences,
)


# ─── Parser: strict JSON ───────────────────────────────────────────────────

def test_parses_clean_json():
    raw = '{"$schema": "webwitness/journey/v0.3", "intent": "x", "persona": "fresh", "target": "https://e.com/", "success": {"shape": "saw_content", "required_content": ["x"]}}'
    obj = _parse_journey_json(raw)
    assert obj["persona"] == "fresh"


def test_parses_json_with_code_fences():
    raw = '```json\n{"intent": "x"}\n```'
    obj = _parse_journey_json(raw)
    assert obj == {"intent": "x"}


def test_parses_json_with_leading_prose():
    raw = 'Here is the journey:\n{"intent": "x", "persona": "fresh"}\nDone.'
    obj = _parse_journey_json(raw)
    assert obj["persona"] == "fresh"


def test_rejects_non_object_json():
    with pytest.raises(ExpanderError, match="non-object"):
        _parse_journey_json('["not", "a", "dict"]')


def test_rejects_no_json_at_all():
    with pytest.raises(ExpanderError, match="no JSON object"):
        _parse_journey_json("This is just prose with no braces.")


def test_rejects_malformed_json():
    with pytest.raises(ExpanderError):
        _parse_journey_json("{not: valid, json")


def test_strip_code_fences_handles_plain_text():
    assert _strip_code_fences("hello") == "hello"
    assert _strip_code_fences("  hello  ") == "hello"


def test_strip_code_fences_handles_json_fence():
    assert _strip_code_fences("```json\n{}\n```") == "{}"


def test_strip_code_fences_handles_unlabelled_fence():
    assert _strip_code_fences("```\n{}\n```") == "{}"


# ─── Prompt builder: shape + content ───────────────────────────────────────

def test_prompt_includes_prose():
    p = _build_prompt("My designer prose here.", "https://example.com/", None)
    assert "My designer prose here." in p


def test_prompt_includes_target_url():
    p = _build_prompt("...", "https://example.com/foo", None)
    assert "https://example.com/foo" in p


def test_prompt_includes_persona_catalogue():
    p = _build_prompt("...", "https://example.com/", None)
    # All four canonical persona ids should appear in the catalogue block.
    for pid in ("fresh", "returning", "engaged", "authenticated"):
        assert f"`{pid}`" in p


def test_prompt_includes_persona_hint_when_provided():
    p = _build_prompt("...", "https://example.com/", "engaged")
    assert "PRINCIPAL HINT" in p
    assert "`engaged`" in p


def test_prompt_omits_hint_block_when_no_hint():
    p = _build_prompt("...", "https://example.com/", None)
    assert "PRINCIPAL HINT" not in p


def test_prompt_lists_allowed_tactics():
    p = _build_prompt("...", "https://example.com/", None)
    assert "click_nav" in p
    assert "fill_form" in p
    assert "read_content" in p


def test_prompt_documents_success_shapes():
    p = _build_prompt("...", "https://example.com/", None)
    for shape in ("landed_on", "saw_content", "reached_goal"):
        assert shape in p


def test_prompt_rejects_empty_prose_via_expand():
    from journeys.expander import expand
    with pytest.raises(ExpanderError, match="prose"):
        expand(prose="", target_url="https://example.com/")


def test_prompt_rejects_empty_target_via_expand():
    from journeys.expander import expand
    with pytest.raises(ExpanderError, match="target"):
        expand(prose="some prose", target_url="")


# ─── Round-trip: LLM-shaped output passes loader ───────────────────────────

def test_expander_output_shape_validates_via_load_journey(tmp_path):
    """A well-formed expander output should pass `load_journey` validation
    end-to-end. Uses a hand-written journey dict that mirrors what the
    expander is contracted to produce."""
    from journeys.loader import load_journey

    expanded = {
        "$schema": "webwitness/journey/v0.3",
        "intent": "Find out when the summit is and how much it costs.",
        "persona": "fresh",
        "target": "https://example.com/",
        "allowed_tactics": ["click_nav", "click_cta", "follow_link", "read_content", "scroll"],
        "success": {
            "shape": "saw_content",
            "required_content": ["date", "price"]
        },
        "patience": {"max_clicks": 6, "max_dead_ends": 2, "max_duration_ms": 60000},
        "notes": "Fresh visitor sniff-test for event basics."
    }
    out = tmp_path / "expanded.json"
    out.write_text(json.dumps(expanded), encoding="utf-8")

    loaded = load_journey(out)
    assert loaded["persona"] == "fresh"
    assert loaded["_resolved"]["persona"]["id"] == "fresh"
    assert loaded["_resolved"]["patience"]["max_clicks"] == 6
