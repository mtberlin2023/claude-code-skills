"""Natural-language → journey.json expander.

Designer types prose: "A new user heard about this on LinkedIn and wants
to find out when the summit is and how much it costs." Plus a target URL.
This module shells `claude --print --model haiku` with the prose + the
v0.3 journey schema + the persona catalogue, and parses a strict-JSON
journey back. The journey is then validated via `load_journey` before
being written to disk — guaranteeing the output is schema-valid or the
expand fails loudly.

Architecture parity with `selector.py`: subprocess to the harness
`claude` CLI rather than importing the Anthropic SDK. Same env whitelist,
same model default, same parser shape.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .loader import (
    ALLOWED_TACTICS,
    ALLOWED_SUCCESS_SHAPES,
    DEFAULT_PATIENCE,
    load_personas,
)
from .selector import DEFAULT_MODEL, DEFAULT_TIMEOUT_S


class ExpanderError(RuntimeError):
    """Raised when the expander subprocess fails or returns unparseable output."""


def _personas_summary() -> str:
    """Compact one-line-per-persona summary for the prompt — full personas.json
    is too verbose, but the LLM needs the id + framing + when-to-use signal."""
    personas = load_personas()
    lines: list[str] = []
    for pid, p in personas.items():
        framing = p.get("llm_framing", "").strip()
        # Trim framing to first sentence for the prompt — full text wastes tokens.
        first_sentence = framing.split(". ")[0].rstrip(".") + "."
        lines.append(f"- `{pid}` ({p.get('label', pid)}): {first_sentence}")
    return "\n".join(lines)


def _build_prompt(prose: str, target_url: str, persona_hint: str | None) -> str:
    personas_block = _personas_summary()
    hint_block = f"\nPRINCIPAL HINT — prefer persona `{persona_hint}` unless the prose strongly contradicts it.\n" if persona_hint else ""
    return f"""You are converting a designer's natural-language description of a website-evaluation journey into a strict JSON file matching the webwitness journey schema v0.3.

DESIGNER'S DESCRIPTION:
\"\"\"
{prose.strip()}
\"\"\"

TARGET URL: {target_url}
{hint_block}
PERSONA CATALOGUE (pick exactly one `id`):
{personas_block}

JOURNEY SCHEMA (v0.3):
- `intent` (string, required): a one-sentence rephrasing of the designer's description as the user's first-person goal. Keep it short.
- `persona` (string, required): one of the persona ids above. Pick the one whose framing best matches the description.
- `target` (string, required): copy the TARGET URL above verbatim.
- `allowed_tactics` (list of strings): which actions the runner may take. Default: ["click_nav", "click_cta", "follow_link", "read_content", "scroll"]. Add `use_search` if the description mentions searching. Add `fill_form` AND `submit` only if the description explicitly involves filling out a form (signup, contact, registration, etc.). Add `go_back` only if the description involves backtracking.
- `success` (object, required): how to know the user got what they came for.
  - `success.shape`: one of {sorted(ALLOWED_SUCCESS_SHAPES)}.
    - `landed_on` = the user reached a specific URL (use when the description names a concrete page like "the pricing page" or "the contact form")
    - `saw_content` = the user saw specific text (use when the description names information like "find out the date" or "understand who it's for")
    - `reached_goal` = both URL and content (use for committed actions like "register", "buy", "subscribe")
  - `success.url_pattern` (string, required if shape is `landed_on` or `reached_goal`): a substring of the URL that indicates success (e.g. "/pricing", "/contact", "/thank-you").
  - `success.required_content` (list of strings, required if shape is `saw_content` or `reached_goal`): 1-3 short lowercase substrings that must appear in the page text. Pick concrete words the user is looking for (e.g. ["price", "$", "month"] for pricing info; ["date", "venue"] for event info). Be specific to the description — don't use generic words like "about" or "info".
- `patience` (object, optional, has defaults {DEFAULT_PATIENCE}): how patient this user is.
  - `max_clicks` (int): typical 4-6 for casual visitors, 6-10 for engaged researchers, 8-12 for committed buyers.
  - `max_dead_ends` (int): typical 2 for casual, 3-4 for engaged.
  - `max_duration_ms` (int): typical 45000-90000 (45-90s wall clock).
- `notes` (string, optional): one short sentence capturing what this journey is testing — written for the human reading the report.

ALLOWED TACTICS REFERENCE: {sorted(ALLOWED_TACTICS)}

OUTPUT FORMAT (strict JSON, no markdown, no prose, no code fences):

{{
  "$schema": "webwitness/journey/v0.3",
  "intent": "...",
  "persona": "...",
  "target": "{target_url}",
  "allowed_tactics": [...],
  "success": {{...}},
  "patience": {{...}},
  "notes": "..."
}}

Output exactly one JSON object. No explanation. No markdown fences.
""".rstrip() + "\n"


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_journey_json(raw: str) -> dict:
    text = _strip_code_fences(raw)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise ExpanderError(f"expander returned no JSON object; raw={raw!r}") from e
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e2:
            raise ExpanderError(f"expander JSON parse failed: {e2}; raw={raw!r}") from e2
    if not isinstance(obj, dict):
        raise ExpanderError(f"expander returned non-object JSON: {obj!r}")
    return obj


def expand(
    *,
    prose: str,
    target_url: str,
    persona_hint: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Expand a prose description into a journey dict. Returns the raw
    expanded dict (NOT yet schema-validated — caller passes it through
    `load_journey` to validate before saving).
    """
    if not prose or not prose.strip():
        raise ExpanderError("prose description is empty")
    if not target_url or not target_url.strip():
        raise ExpanderError("target URL is empty")

    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise ExpanderError(
            "`claude` CLI not on PATH — expander requires Claude Code installed. "
            "Install via npm: `npm i -g @anthropic-ai/claude-code`."
        )

    prompt = _build_prompt(prose, target_url, persona_hint)
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
        raise ExpanderError(f"expander timed out after {timeout_s}s") from e
    if proc.returncode != 0:
        raise ExpanderError(
            f"`claude --print` exited {proc.returncode}: stderr={proc.stderr.strip()[:500]!r}"
        )
    return _parse_journey_json(proc.stdout)


def expand_to_file(
    *,
    prose: str,
    target_url: str,
    out_path: Path,
    persona_hint: str | None = None,
    model: str = DEFAULT_MODEL,
) -> Path:
    """Expand prose → validate via load_journey → write to out_path.
    Returns the written path. Raises ExpanderError on any failure
    (expansion or validation)."""
    from .loader import load_journey, JourneyRefusedError

    raw = expand(
        prose=prose, target_url=target_url, persona_hint=persona_hint, model=model
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    # Round-trip validation. If the LLM produced invalid output, we want
    # to fail loudly — but we leave the file on disk so the user can
    # inspect what was wrong.
    try:
        load_journey(out_path)
    except JourneyRefusedError as e:
        raise ExpanderError(
            f"expanded journey failed schema validation — file written to {out_path} "
            f"for inspection. Validation error: {e}"
        ) from e
    return out_path
