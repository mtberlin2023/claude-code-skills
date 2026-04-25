"""journey.json + personas.json loader. Mirrors verify.load_flow shape:
parse → validate → return dict, or raise JourneyRefusedError on any
validation failure. Never returns an invalid journey."""

from __future__ import annotations

import json
from pathlib import Path

# Re-use verify.py's static gates so journeys can't smuggle in URLs or
# token-shaped strings that flow.json would have refused.
import sys
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
from verify import (  # noqa: E402
    FlowRefusedError,
    _scan_flow_entropy,
    _validate_step_url,
)

PERSONAS_PATH = _HERE / "personas.json"

ALLOWED_TACTICS: frozenset[str] = frozenset({
    "click_nav", "click_cta", "follow_link", "use_search",
    "read_content", "fill_form", "submit", "go_back", "scroll",
})

# Tactics off by default (require explicit allowed_tactics entry).
TACTICS_OFF_BY_DEFAULT: frozenset[str] = frozenset({"fill_form", "submit"})

DEFAULT_ALLOWED_TACTICS: list[str] = [
    "click_nav", "click_cta", "follow_link", "read_content",
    # `scroll` deliberately NOT in default. chrome-devtools-mcp's
    # take_snapshot returns the full a11y tree regardless of viewport
    # position — scroll has no observable effect, and including it
    # invites repeat-scroll dead-end loops (observed undavos mobile-
    # contact run, 2026-04-25). Journeys that legitimately need scroll
    # tracking must opt in explicitly.
]

ALLOWED_SUCCESS_SHAPES: frozenset[str] = frozenset({
    "landed_on", "saw_content", "reached_goal", "llm_judged",
})

DEFAULT_PATIENCE = {
    "max_clicks": 8,
    "max_dead_ends": 3,
    # Two clocks. max_page_wait_ms = user-perceived friction (sums only
    # MCP dispatch + snapshot time). max_duration_ms = hard wall backstop
    # including selector latency and our overhead. Whichever fires first
    # wins. Default page_wait 30s reflects "would a real user have given
    # up by now?"; default duration 180s absorbs Haiku selector latency
    # without prematurely capping (observed undavos acceptance run hit
    # 73s wall on a journey that spent <30s waiting on the page itself).
    "max_page_wait_ms": 30000,
    "max_duration_ms": 180000,
}


class JourneyRefusedError(ValueError):
    """Raised when a journey.json fails validation. Mirrors FlowRefusedError."""


def load_personas(path: Path | None = None) -> dict[str, dict]:
    """Return {persona_id: persona_dict} from personas.json."""
    p = path or PERSONAS_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for entry in raw.get("personas", []):
        pid = entry.get("id")
        if not isinstance(pid, str) or not pid:
            continue
        out[pid] = entry
    return out


def load_journey(path: Path, allow_high_entropy: bool = False) -> dict:
    """Load + validate a journey script. Raises JourneyRefusedError on
    any validation failure."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise JourneyRefusedError(f"cannot read journey at {path}: {e}") from e

    try:
        journey = json.loads(raw)
    except json.JSONDecodeError as e:
        raise JourneyRefusedError(f"journey is not valid JSON: {e}") from e

    if not isinstance(journey, dict):
        raise JourneyRefusedError("journey must be a JSON object at top level")

    intent = journey.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        raise JourneyRefusedError(
            "journey missing required field 'intent' (non-empty string). "
            "Without intent the runner has no goal to select for."
        )

    persona_id = journey.get("persona")
    if not isinstance(persona_id, str) or not persona_id:
        raise JourneyRefusedError("journey missing required field 'persona' (string)")
    personas = load_personas()
    if persona_id not in personas:
        raise JourneyRefusedError(
            f"persona '{persona_id}' not found in personas.json. "
            f"Known: {sorted(personas)}"
        )

    target = journey.get("target")
    if not isinstance(target, str) or not target.strip():
        raise JourneyRefusedError("journey missing required field 'target' (URL string)")
    try:
        _validate_step_url(0, target)
    except FlowRefusedError as e:
        raise JourneyRefusedError(f"target URL refused by SSRF gate: {e}") from e

    allowed = journey.get("allowed_tactics") or list(DEFAULT_ALLOWED_TACTICS)
    if not isinstance(allowed, list) or not all(isinstance(t, str) for t in allowed):
        raise JourneyRefusedError("'allowed_tactics' must be a list of strings")
    for t in allowed:
        if t not in ALLOWED_TACTICS:
            raise JourneyRefusedError(
                f"unknown tactic '{t}'. Known: {sorted(ALLOWED_TACTICS)}"
            )

    forbidden = journey.get("forbidden_tactics") or []
    if not isinstance(forbidden, list) or not all(isinstance(t, str) for t in forbidden):
        raise JourneyRefusedError("'forbidden_tactics' must be a list of strings")
    effective_tactics = [t for t in allowed if t not in set(forbidden)]
    if not effective_tactics:
        raise JourneyRefusedError(
            "no tactics remaining after applying forbidden_tactics — "
            "the runner has nothing it can do"
        )

    success = journey.get("success")
    if not isinstance(success, dict):
        raise JourneyRefusedError("journey missing 'success' (object)")
    shape = success.get("shape")
    if shape not in ALLOWED_SUCCESS_SHAPES:
        raise JourneyRefusedError(
            f"success.shape must be one of {sorted(ALLOWED_SUCCESS_SHAPES)}; "
            f"got {shape!r}"
        )
    if shape in {"landed_on", "reached_goal"}:
        url_pattern = success.get("url_pattern")
        if not isinstance(url_pattern, str) or not url_pattern:
            raise JourneyRefusedError(
                f"success.shape={shape!r} requires success.url_pattern (string)"
            )
    if shape in {"saw_content", "reached_goal"}:
        rc = success.get("required_content")
        landmark = success.get("landmark")
        if not (
            (isinstance(rc, list) and rc)
            or (isinstance(landmark, dict) and landmark)
        ):
            raise JourneyRefusedError(
                f"success.shape={shape!r} requires success.required_content "
                f"(non-empty list) or success.landmark (object)"
            )
    if shape == "llm_judged":
        criterion = success.get("criterion")
        if not isinstance(criterion, str) or not criterion.strip():
            raise JourneyRefusedError(
                "success.shape='llm_judged' requires success.criterion "
                "(non-empty prose describing what 'success' means for the journey)"
            )

    patience = dict(DEFAULT_PATIENCE)
    user_patience = journey.get("patience") or {}
    if not isinstance(user_patience, dict):
        raise JourneyRefusedError("'patience' must be an object")
    for k in ("max_clicks", "max_dead_ends", "max_duration_ms", "max_page_wait_ms"):
        if k in user_patience:
            v = user_patience[k]
            if not isinstance(v, int) or v <= 0:
                raise JourneyRefusedError(
                    f"patience.{k} must be a positive integer; got {v!r}"
                )
            patience[k] = v

    # Entropy / token-shape scan reuses the flow gate (works on any dict).
    _scan_flow_entropy(journey, allow_high_entropy)

    journey["_resolved"] = {
        "persona": personas[persona_id],
        "tactics": effective_tactics,
        "patience": patience,
    }
    return journey
