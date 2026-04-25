"""LLM-in-loop step selector. Shells out to `claude --print --model haiku`
with the current snapshot + intent + persona framing + allowed tactics, and
expects strict-JSON `{action, target_role, target_name, rationale}` back.

Architecture choice (2026-04-24): subprocess to the harness-installed
`claude` CLI rather than importing the Anthropic SDK. Keeps verify.py's
runtime dependency surface unchanged (Anya #11) and re-uses harness auth.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any

# Decision schema returned by the selector. The runner translates these
# into MCP tool calls (or treats `done`/`give_up` as terminal).
DECISION_ACTIONS: frozenset[str] = frozenset({
    "click_nav", "click_cta", "follow_link", "use_search", "read_content",
    "fill_form", "submit", "go_back", "scroll", "dismiss_consent",
    "done", "give_up",
})

# Tactics that need an element target (role + name).
TACTICS_NEED_TARGET: frozenset[str] = frozenset({
    "click_nav", "click_cta", "follow_link", "use_search",
    "fill_form", "submit", "dismiss_consent",
})

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TIMEOUT_S = 60
MAX_SNAPSHOT_CHARS = 12_000  # truncate the accessibility tree for the prompt


class SelectorError(RuntimeError):
    """Raised when the selector subprocess fails or returns unparseable output."""


def _build_prompt(
    *,
    intent: str,
    persona_framing: str,
    target_url: str,
    tactics: list[str],
    snapshot_text: str,
    history: list[dict],
    iteration: int,
    patience_remaining: dict,
) -> str:
    snap = snapshot_text
    if len(snap) > MAX_SNAPSHOT_CHARS:
        snap = snap[:MAX_SNAPSHOT_CHARS] + f"\n…[snapshot truncated, {len(snapshot_text) - MAX_SNAPSHOT_CHARS} more chars]"

    hist_lines = []
    for i, h in enumerate(history[-6:], start=max(1, len(history) - 5)):
        observed = h.get("observed", "")
        hist_lines.append(
            f"  step {i}: action={h.get('action')!r} target={h.get('target_name', '')!r} "
            f"rationale={h.get('rationale', '')!r} observed={observed!r}"
        )
    history_block = "\n".join(hist_lines) if hist_lines else "  (no prior steps)"

    return f"""You are choosing the next action for a simulated user visiting a website.

PERSONA FRAMING:
{persona_framing}

INTENT (what this user is trying to do):
{intent}

CURRENT URL: {target_url}

ALLOWED TACTICS (you may pick one of these, plus `done` or `give_up`):
{', '.join(tactics)}

Tactic semantics:
- click_nav: click a link/button in the site nav or header
- click_cta: click a prominent call-to-action button or link
- follow_link: click a link in the main content area
- use_search: locate the search box, fill it, submit
- read_content: take no action — just observe the current page (use this if the page itself answers the intent)
- scroll: scroll down to see more (no element target needed)
- dismiss_consent: click an Accept / Reject / Dismiss button on a cookie / privacy / consent banner — pre-task friction; the persona framing decides whether to accept or reject. Pick this BEFORE click_nav / click_cta when a consent banner is visible — banner content typically blocks interaction with the rest of the page.
- go_back: browser back
- done: success — the intent has been met by what you can see now
- give_up: this user would abandon the journey at this point

PATIENCE BUDGET REMAINING:
  clicks: {patience_remaining.get('clicks')}
  dead_ends: {patience_remaining.get('dead_ends')}
  duration_ms: {patience_remaining.get('duration_ms')}

DECISIONS SO FAR:
{history_block}

CURRENT PAGE (accessibility tree, truncated):
```
{snap}
```

OUTPUT FORMAT (strict JSON, no markdown, no prose, no code fences):
{{
  "action": "<one of: {', '.join(sorted(DECISION_ACTIONS))}>",
  "target_role": "<role from the snapshot, e.g. 'link' or 'button'; omit if action is read_content/scroll/go_back/done/give_up>",
  "target_name": "<exact visible name string of the element, copied verbatim from the snapshot; same omission rule>",
  "rationale": "<one short sentence in the persona's voice — why this user would do this next>"
}}

Pick exactly ONE action. If the intent is already met, pick `done`. If the persona would abandon (confused, no obvious next step within their patience), pick `give_up`. Iteration: {iteration}.
""".rstrip() + "\n"


def _strip_code_fences(s: str) -> str:
    """Remove ``` ... ``` wrappers if present. Selector prompt asks for raw
    JSON, but defensive — Haiku occasionally adds fences anyway."""
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_decision(raw: str) -> dict:
    text = _strip_code_fences(raw)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        # Try to find first {...} block.
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise SelectorError(f"selector returned no JSON object; raw={raw!r}") from e
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e2:
            raise SelectorError(f"selector JSON parse failed: {e2}; raw={raw!r}") from e2

    if not isinstance(obj, dict):
        raise SelectorError(f"selector returned non-object JSON: {obj!r}")
    action = obj.get("action")
    if action not in DECISION_ACTIONS:
        raise SelectorError(
            f"selector returned unknown action {action!r}; "
            f"expected one of {sorted(DECISION_ACTIONS)}"
        )
    out: dict[str, Any] = {
        "action": action,
        "rationale": str(obj.get("rationale", "")).strip(),
    }
    if action in TACTICS_NEED_TARGET:
        role = obj.get("target_role")
        name = obj.get("target_name")
        if not isinstance(role, str) or not role:
            raise SelectorError(f"action {action!r} requires target_role; got {role!r}")
        if not isinstance(name, str):
            raise SelectorError(f"action {action!r} requires target_name; got {name!r}")
        out["target_role"] = role
        out["target_name"] = name
    return out


def _build_judge_prompt(
    *,
    intent: str,
    criterion: str,
    persona_framing: str,
    target_url: str,
    decisions: list[dict],
    final_snapshot_text: str,
) -> str:
    """Prompt for the post-loop semantic judge. Asks Haiku to grade the
    journey against the criterion, returning {met, evidence, why_not}."""
    snap = final_snapshot_text
    if len(snap) > MAX_SNAPSHOT_CHARS:
        snap = snap[:MAX_SNAPSHOT_CHARS] + f"\n…[snapshot truncated, {len(final_snapshot_text) - MAX_SNAPSHOT_CHARS} more chars]"
    decision_lines = []
    for i, d in enumerate(decisions, start=1):
        decision_lines.append(
            f"  step {i}: {d.get('action')} target={d.get('target_name', '')!r} "
            f"rationale={d.get('rationale', '')!r}"
        )
    history_block = "\n".join(decision_lines) if decision_lines else "  (no actions taken)"
    return f"""You are a strict but fair judge for a website-design review tool. A simulated user just ran a journey on a site. Your job is to grade whether the success criterion was met, based on the final page state and the actions the user took.

PERSONA FRAMING:
{persona_framing}

INTENT:
{intent}

SUCCESS CRITERION (what counts as having succeeded):
{criterion}

FINAL URL: {target_url}

ACTIONS TAKEN:
{history_block}

FINAL PAGE (accessibility tree, truncated):
```
{snap}
```

Grade the journey strictly against the criterion. Be specific in your evidence — quote actual content from the snapshot, not generic claims. Do not invent content that isn't in the snapshot. If the criterion is partially met, that's a "met=false" with a clear "why_not" explaining what was missing.

OUTPUT FORMAT (strict JSON, no markdown, no prose, no code fences):
{{
  "met": true | false,
  "evidence": "<one or two sentences quoting specific snapshot content that supports your verdict>",
  "why_not": "<if met=false, one short sentence on what's missing; empty string if met=true>"
}}
""".rstrip() + "\n"


def _parse_judgment(raw: str) -> dict:
    text = _strip_code_fences(raw)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise SelectorError(f"judge returned no JSON object; raw={raw!r}") from e
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e2:
            raise SelectorError(f"judge JSON parse failed: {e2}; raw={raw!r}") from e2
    if not isinstance(obj, dict):
        raise SelectorError(f"judge returned non-object JSON: {obj!r}")
    if not isinstance(obj.get("met"), bool):
        raise SelectorError(f"judge.met must be bool; got {obj.get('met')!r}")
    return {
        "met": obj["met"],
        "evidence": str(obj.get("evidence", "")).strip(),
        "why_not": str(obj.get("why_not", "")).strip(),
    }


def judge_journey(
    *,
    intent: str,
    criterion: str,
    persona_framing: str,
    target_url: str,
    decisions: list[dict],
    final_snapshot_text: str,
    model: str = DEFAULT_MODEL,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Post-loop semantic judge for shape='llm_judged' journeys. Returns
    {met: bool, evidence: str, why_not: str}."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise SelectorError(
            "`claude` CLI not on PATH — judge requires Claude Code installed."
        )
    prompt = _build_judge_prompt(
        intent=intent,
        criterion=criterion,
        persona_framing=persona_framing,
        target_url=target_url,
        decisions=decisions,
        final_snapshot_text=final_snapshot_text,
    )
    cmd = [claude_bin, "--print", "--model", model]
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env={k: v for k, v in os.environ.items() if k in {
                "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "USER",
                "ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME",
            }},
        )
    except subprocess.TimeoutExpired as e:
        raise SelectorError(f"judge timed out after {timeout_s}s") from e
    if proc.returncode != 0:
        raise SelectorError(
            f"`claude --print` exited {proc.returncode}: stderr={proc.stderr.strip()[:500]!r}"
        )
    return _parse_judgment(proc.stdout)


def select_next(
    *,
    intent: str,
    persona_framing: str,
    target_url: str,
    tactics: list[str],
    snapshot_text: str,
    history: list[dict],
    iteration: int,
    patience_remaining: dict,
    model: str = DEFAULT_MODEL,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Ask the selector LLM what to do next. Returns parsed decision dict."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise SelectorError(
            "`claude` CLI not on PATH — selector requires Claude Code installed. "
            "Install via npm: `npm i -g @anthropic-ai/claude-code`."
        )
    prompt = _build_prompt(
        intent=intent,
        persona_framing=persona_framing,
        target_url=target_url,
        tactics=tactics,
        snapshot_text=snapshot_text,
        history=history,
        iteration=iteration,
        patience_remaining=patience_remaining,
    )
    # `claude --print` reads the prompt from stdin when none is given on
    # argv; safer than passing huge accessibility-tree text via argv.
    cmd = [claude_bin, "--print", "--model", model]
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env={k: v for k, v in os.environ.items() if k in {
                "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "USER",
                "ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME",
            }},
        )
    except subprocess.TimeoutExpired as e:
        raise SelectorError(f"selector timed out after {timeout_s}s") from e
    if proc.returncode != 0:
        raise SelectorError(
            f"`claude --print` exited {proc.returncode}: stderr={proc.stderr.strip()[:500]!r}"
        )
    return _parse_decision(proc.stdout)
