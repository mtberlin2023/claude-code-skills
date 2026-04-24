"""Journey runner — drives a persona+intent loop against a live URL.

v0.3 alpha note (2026-04-24): persona seeding is deliberately framing-only.
Real cookie / localStorage / referrer planting is blocked by the v0.2
security gate (`evaluate_script` denied, `--user-data-dir` refused, no
cookie tool in the 9-tool allowlist). See BRIEF-032 for the v0.4 re-pass
that unlocks real seeding. For now the persona influences only the LLM
prompt frame; in-browser state starts empty for every persona.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from verify import (  # noqa: E402
    FlowRefusedError,
    MCP_CALL_TIMEOUT,
    _apply_selector_resolution,
    _current_url_from_snapshot,
    _extract_binary_blobs,
    _ext_for_mime,
    _landmark_matches,
    _mcp_session,
    _result_to_dict,
    _snapshot_to_text,
    dispatch_step_async,
    ensure_artefacts_dir,
    new_run_id,
    write_artefact_bytes,
    write_artefact_json,
)

from . import selector as selector_mod  # noqa: E402

# Mapping from selector action → concrete MCP tool. read_content / scroll
# are observation-only in v0.3 alpha (chrome-devtools-mcp's take_snapshot
# returns the whole DOM regardless of scroll position).
ACTION_TO_TOOL: dict[str, str] = {
    "click_nav": "click",
    "click_cta": "click",
    "follow_link": "click",
    "use_search": "click",  # alpha: just clicks the searchbox; full fill/submit deferred
}

OBSERVATION_ONLY_ACTIONS: frozenset[str] = frozenset({"read_content", "scroll"})

# Verdict shapes for journey runs. PASS = success state met. FAIL = hard
# error (network, gate refusal). UNCLEAR = patience exhausted or selector
# said `give_up` — surfaces design issues without claiming the site is
# broken.
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_UNCLEAR = "UNCLEAR"


def run_journey(
    journey: dict,
    run_id: str | None = None,
    artefacts_root: Path | None = None,
) -> dict:
    """Execute a validated journey (output of journeys.loader.load_journey).
    Returns a result dict in flow-runner shape so the reader can render it.

    artefacts_root overrides the default ARTEFACTS_ROOT — used by the
    journey-suite runner to nest per-journey runs inside one suite dir.
    """
    if run_id is None:
        run_id = new_run_id()
    return asyncio.run(_run_journey_async(journey, run_id, artefacts_root))


def _check_success(
    journey: dict, current_url: str | None, snapshot_text: str, snapshot_dict: dict | None
) -> str | None:
    """Return the matcher name that fired, or None."""
    success = journey["success"]
    shape = success["shape"]
    if shape in {"landed_on", "reached_goal"}:
        url_pattern = success.get("url_pattern", "")
        if url_pattern and current_url and url_pattern in current_url:
            if shape == "landed_on":
                return "url_pattern"
            # reached_goal also requires content/landmark check below
        elif shape == "landed_on":
            return None
    if shape in {"saw_content", "reached_goal"}:
        rc = success.get("required_content") or []
        if rc:
            if all(needle.lower() in snapshot_text.lower() for needle in rc):
                if shape == "saw_content":
                    return "required_content"
                if shape == "reached_goal":
                    url_pattern = success.get("url_pattern", "")
                    if url_pattern and current_url and url_pattern in current_url:
                        return "url_pattern+required_content"
                    return None
        landmark = success.get("landmark")
        if landmark and snapshot_dict and _landmark_matches(landmark, snapshot_dict):
            return "landmark"
    return None


def _make_synthetic_flow(journey: dict, executed_steps: list[dict]) -> dict:
    """Synthesise a flow-shaped dict so the existing reader.report can render
    the journey artefact dir without a journey-specific code path."""
    success = journey["success"]
    success_state: dict = {}
    if success.get("url_pattern"):
        success_state["url_pattern"] = success["url_pattern"]
    if success.get("landmark"):
        success_state["landmark"] = success["landmark"]
    if not success_state:
        # required_content-only journeys: fall back to a permissive landmark
        # so the reader's success_state field has SOMETHING to display.
        success_state["url_pattern"] = ""
    return {
        "goal": journey["intent"],
        "success_state": success_state,
        "steps": executed_steps,
        "_journey": True,
    }


async def _run_journey_async(
    journey: dict, run_id: str, artefacts_root: Path | None = None
) -> dict:
    resolved = journey["_resolved"]
    persona = resolved["persona"]
    tactics = list(resolved["tactics"])
    patience = dict(resolved["patience"])

    run_dir = ensure_artefacts_dir(run_id, root=artefacts_root)
    write_artefact_json(run_dir, "journey.json", {
        k: v for k, v in journey.items() if not k.startswith("_")
    })

    server_errlog = run_dir / "server-stderr.log"
    decisions: list[dict] = []
    executed_steps: list[dict] = []  # synthetic flow.steps for reader compat
    step_durations_ms: list[int | None] = []
    final_error: str | None = None
    verdict: str = VERDICT_FAIL  # default until we explicitly set otherwise
    matcher: str | None = None
    last_navigated_url: str | None = None
    snapshot_result: dict | None = None
    last_snapshot_text: str = ""

    clicks_used = 0
    dead_ends = 0
    iterations = 0
    run_start = time.perf_counter()

    def patience_remaining() -> dict:
        return {
            "clicks": patience["max_clicks"] - clicks_used,
            "dead_ends": patience["max_dead_ends"] - dead_ends,
            "duration_ms": patience["max_duration_ms"] - int((time.perf_counter() - run_start) * 1000),
        }

    def write_decision(d: dict) -> None:
        decisions.append(d)
        with (run_dir / "decisions.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    try:
        async with _mcp_session(errlog_path=server_errlog) as session:
            # Step 0 — navigate to target.
            nav_step = {"tool": "navigate_page", "url": journey["target"]}
            executed_steps.append(nav_step)
            step_start = time.perf_counter()
            try:
                raw = await dispatch_step_async(session, nav_step, {}, [])
            except Exception as e:  # noqa: BLE001
                final_error = f"navigate_page: {type(e).__name__}: {e}"
                raise
            step_durations_ms.append(int((time.perf_counter() - step_start) * 1000))
            last_navigated_url = journey["target"]
            write_artefact_json(run_dir, "step-01-navigate_page.json", _result_to_dict(raw))

            # Main loop.
            while True:
                iterations += 1
                pr = patience_remaining()

                # Snapshot before deciding.
                step_start = time.perf_counter()
                try:
                    snap = await asyncio.wait_for(
                        session.call_tool("take_snapshot", {}),
                        timeout=MCP_CALL_TIMEOUT,
                    )
                except Exception as e:  # noqa: BLE001
                    final_error = f"take_snapshot[iter={iterations}]: {type(e).__name__}: {e}"
                    break
                snap_dict = _result_to_dict(snap)
                snapshot_result = snap_dict
                last_snapshot_text = _snapshot_to_text(snap)
                snap_url = _current_url_from_snapshot(last_snapshot_text)
                if snap_url:
                    last_navigated_url = snap_url
                snap_label = f"step-{len(executed_steps) + 1:02d}-take_snapshot"
                executed_steps.append({"tool": "take_snapshot"})
                write_artefact_json(run_dir, f"{snap_label}.json", snap_dict)
                step_durations_ms.append(int((time.perf_counter() - step_start) * 1000))

                # Success check (before patience check — if we're already
                # done, don't waste a click budget on it).
                fired = _check_success(journey, last_navigated_url, last_snapshot_text, snap_dict)
                if fired:
                    matcher = fired
                    verdict = VERDICT_PASS
                    break

                # Patience exhaustion → UNCLEAR.
                if pr["clicks"] <= 0:
                    verdict = VERDICT_UNCLEAR
                    matcher = "patience.max_clicks"
                    break
                if pr["dead_ends"] <= 0:
                    verdict = VERDICT_UNCLEAR
                    matcher = "patience.max_dead_ends"
                    break
                if pr["duration_ms"] <= 0:
                    verdict = VERDICT_UNCLEAR
                    matcher = "patience.max_duration_ms"
                    break

                # Ask the LLM what this persona would do next.
                try:
                    decision = selector_mod.select_next(
                        intent=journey["intent"],
                        persona_framing=persona.get("llm_framing", ""),
                        target_url=last_navigated_url or journey["target"],
                        tactics=tactics,
                        snapshot_text=last_snapshot_text,
                        history=decisions,
                        iteration=iterations,
                        patience_remaining=pr,
                    )
                except selector_mod.SelectorError as e:
                    final_error = f"selector[iter={iterations}]: {e}"
                    break

                action = decision["action"]
                rationale = decision.get("rationale", "")

                # Terminal selector decisions.
                if action == "done":
                    fired = _check_success(journey, last_navigated_url, last_snapshot_text, snap_dict)
                    if fired:
                        matcher = fired
                        verdict = VERDICT_PASS
                    else:
                        # LLM thinks the intent is met but our matchers
                        # don't agree. Honest reading: success criteria
                        # are too narrow OR persona was over-optimistic.
                        # Mark UNCLEAR with matcher 'llm_done_unverified'.
                        matcher = "llm_done_unverified"
                        verdict = VERDICT_UNCLEAR
                    write_decision({
                        "iter": iterations,
                        "action": action,
                        "rationale": rationale,
                        "url": last_navigated_url,
                        "observed": "selector declared done",
                    })
                    break
                if action == "give_up":
                    verdict = VERDICT_UNCLEAR
                    matcher = "selector.give_up"
                    write_decision({
                        "iter": iterations,
                        "action": action,
                        "rationale": rationale,
                        "url": last_navigated_url,
                        "observed": "selector abandoned the journey",
                    })
                    break

                # Observation-only actions: no DOM change, no click cost,
                # but they DO count toward dead-ends if repeated without
                # any URL/content change between them.
                if action in OBSERVATION_ONLY_ACTIONS:
                    write_decision({
                        "iter": iterations,
                        "action": action,
                        "rationale": rationale,
                        "url": last_navigated_url,
                        "observed": "no DOM action — observation only",
                    })
                    # Repeated read_content with no progress → dead end.
                    if (
                        len(decisions) >= 2
                        and decisions[-2].get("action") in OBSERVATION_ONLY_ACTIONS
                        and decisions[-2].get("url") == last_navigated_url
                    ):
                        dead_ends += 1
                    continue

                # All remaining actions need a target. Translate to a click step.
                tool = ACTION_TO_TOOL.get(action)
                if not tool:
                    final_error = f"action {action!r} not implemented in v0.3 alpha runner"
                    write_decision({
                        "iter": iterations,
                        "action": action,
                        "rationale": rationale,
                        "url": last_navigated_url,
                        "observed": f"runner refused: {final_error}",
                    })
                    break

                step = {
                    "tool": tool,
                    "selector": {
                        "role": decision.get("target_role", ""),
                        "name": decision.get("target_name", ""),
                    },
                }
                pre_url = last_navigated_url
                pre_snapshot_len = len(last_snapshot_text)

                try:
                    resolved_step = _apply_selector_resolution(step, last_snapshot_text)
                except FlowRefusedError as e:
                    # Selector chose an element that doesn't exist or is
                    # ambiguous. Counts as a dead end.
                    dead_ends += 1
                    write_decision({
                        "iter": iterations,
                        "action": action,
                        "target_role": decision.get("target_role"),
                        "target_name": decision.get("target_name"),
                        "rationale": rationale,
                        "url": last_navigated_url,
                        "observed": f"selector resolution failed: {e}",
                    })
                    continue

                step_start = time.perf_counter()
                try:
                    raw = await dispatch_step_async(session, resolved_step, {}, [])
                except Exception as e:  # noqa: BLE001
                    final_error = f"{tool}[iter={iterations}]: {type(e).__name__}: {e}"
                    write_decision({
                        "iter": iterations,
                        "action": action,
                        "target_role": decision.get("target_role"),
                        "target_name": decision.get("target_name"),
                        "rationale": rationale,
                        "url": last_navigated_url,
                        "observed": f"dispatch failed: {final_error}",
                    })
                    break
                clicks_used += 1
                step_label = f"step-{len(executed_steps) + 1:02d}-{tool}"
                executed_steps.append(resolved_step)
                write_artefact_json(run_dir, f"{step_label}.json", _result_to_dict(raw))
                blobs = _extract_binary_blobs(raw)
                for j, (mime, data) in enumerate(blobs):
                    suffix = "" if len(blobs) == 1 else f"-{chr(ord('a') + j)}"
                    ext = _ext_for_mime(mime)
                    write_artefact_bytes(run_dir, f"{step_label}{suffix}{ext}", data)
                step_durations_ms.append(int((time.perf_counter() - step_start) * 1000))

                # Observation: did the click change anything?
                observed = "url_unchanged"
                # We snapshot at the top of next loop iteration, so the
                # post-click change check is deferred. For now, log the
                # decision; the dead-end determination happens on next
                # iter when the new snapshot is in hand.
                write_decision({
                    "iter": iterations,
                    "action": action,
                    "target_role": decision.get("target_role"),
                    "target_name": decision.get("target_name"),
                    "rationale": rationale,
                    "url_before": pre_url,
                    "url": pre_url,  # post-snapshot updates this on next iter
                    "snapshot_chars_before": pre_snapshot_len,
                    "observed": "click dispatched — outcome assessed next iter",
                })

    except Exception as e:  # noqa: BLE001 — session-level / nav failure
        if final_error is None:
            final_error = f"session: {type(e).__name__}: {e}"
        verdict = VERDICT_FAIL

    # Post-loop dead-end pass: walk the recorded decisions and back-fill
    # `observed` on click steps using the URL we saw on the snapshot of
    # the NEXT iteration.
    iter_url: dict[int, str | None] = {}
    for d in decisions:
        if "iter" in d and d.get("url") is not None:
            iter_url[d["iter"]] = d["url"]
    for d in decisions:
        if d.get("action") in {"click_nav", "click_cta", "follow_link", "use_search"}:
            next_url = iter_url.get(d["iter"] + 1)
            if next_url is not None and next_url != d.get("url_before"):
                d["observed"] = f"navigated to {next_url}"
            elif next_url is not None:
                d["observed"] = "URL unchanged after click — dead end"

    duration_ms = int((time.perf_counter() - run_start) * 1000)

    # Synthesise flow.json + result.json for reader compat.
    synthetic_flow = _make_synthetic_flow(journey, executed_steps)
    write_artefact_json(run_dir, "flow.json", synthetic_flow)

    if snapshot_result is not None:
        write_artefact_json(run_dir, "final-snapshot.json", snapshot_result)

    result = {
        "run_id": run_id,
        "pass": verdict == VERDICT_PASS,
        "verdict": verdict,
        "matcher": matcher,
        "artefacts_dir": str(run_dir),
        "steps_completed": len(executed_steps),
        "steps_total": len(executed_steps),
        "step_durations_ms": step_durations_ms,
        "duration_ms": duration_ms,
        "iterations": iterations,
        "clicks_used": clicks_used,
        "dead_ends": dead_ends,
        "patience_budget": patience,
        "error": final_error,
        "_journey": True,
    }
    write_artefact_json(run_dir, "result.json", result)
    return result
