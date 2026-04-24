# journey.json — schema (v0.3 draft)

A journey is intent + persona, not a step list. The runner fills in the steps by asking Claude what a user with this persona would do next, bounded by `allowed_tactics` and the existing same-origin + allowlist gates. Compare to `flow.json`, which is a fixed script.

## Schema

```json
{
  "$schema": "webwitness/journey/v0.3",
  "intent": "Short human sentence describing what the persona is trying to accomplish.",
  "persona": "fresh | returning | engaged | authenticated | <custom id>",
  "target": "https://example.com/",
  "allowed_tactics": ["click_nav", "click_cta", "follow_link", "use_search", "read_content"],
  "forbidden_tactics": ["fill_form", "submit"],
  "success": {
    "shape": "landed_on | saw_content | reached_goal",
    "url_pattern": "/programs",
    "landmark": {"role": "heading", "name_contains": "Programs"},
    "required_content": ["sessions", "dates"]
  },
  "patience": {
    "max_clicks": 8,
    "max_dead_ends": 3,
    "max_duration_ms": 45000
  },
  "notes": "Optional free text for the designer."
}
```

## Field semantics

| Field | Required | Purpose |
|---|---|---|
| `intent` | yes | Natural-language goal. Fed to the step-selection LLM as "the user is trying to…". Kept short — one or two sentences. |
| `persona` | yes | Id from `personas.json`. Controls cookie/storage seeding and LLM framing ("you are a first-time visitor who has never heard of this site"). |
| `target` | yes | Starting URL. Same validation as `flow.json` navigate_page. |
| `allowed_tactics` | no | Whitelist of actions the runner may choose. Default: `["click_nav", "click_cta", "follow_link", "read_content"]`. Forms + submit are off unless explicitly allowed. |
| `forbidden_tactics` | no | Hard block. Wins over `allowed_tactics` if both list the same tactic. |
| `success.shape` | yes | `landed_on` = URL match; `saw_content` = specific StaticText appeared in snapshot; `reached_goal` = both. |
| `success.url_pattern` | cond | Required if shape is `landed_on` or `reached_goal`. |
| `success.landmark` | no | Optional landmark requirement (same shape as flow.json). |
| `success.required_content` | no | List of substrings that must appear in the final snapshot's StaticText nodes. |
| `patience.max_clicks` | no | Aborts as UNCLEAR (not FAIL) when hit. Default 8. |
| `patience.max_dead_ends` | no | A dead-end = click that didn't change URL OR didn't reveal new content. Default 3. |
| `patience.max_duration_ms` | no | Wall-clock ceiling. Default 45000ms. |

## Verdicts

- `PASS` — success shape met within patience budget.
- `FAIL` — hard error (network, gate refusal, navigation blocked).
- `UNCLEAR` — patience exhausted without success. Report surfaces the abandonment point. NOT a bug in the site necessarily; often a UX signal ("a fresh user couldn't figure out where to go in 8 clicks").

## Tactics taxonomy

| Tactic | What the runner may do |
|---|---|
| `click_nav` | Click any `role=link` inside `role=navigation` or `role=banner`. |
| `click_cta` | Click any prominent `role=button` or `role=link` whose name matches CTA patterns (`^(Get|Start|Book|Sign|Join|Buy|Try|Learn)`). |
| `follow_link` | Click any `role=link` in the main content area (`role=main`). |
| `use_search` | Locate `role=searchbox`, fill, submit. |
| `read_content` | No action — just capture a snapshot. Used to mark "what the user read before deciding." |
| `fill_form` | Fill `role=textbox`/`combobox` — off by default, only on for journeys that explicitly involve form submission. |
| `submit` | Click submit button after fill_form. Off by default. |
| `go_back` | Browser back. Counts as a click toward `max_clicks`. |
| `scroll` | Captures further content below fold. No cost toward clicks. |

## Status

- **v0.3 alpha (2026-04-24):** schema frozen, runner shipped as `verify.py journey <journey.json>`. Output artefact dir identical to flow runs (writes `flow.json` + `result.json` + per-step files); `report.html` adds a Narrative section that consumes `decisions.jsonl`.
- **Persona seeding is FRAMING-ONLY in v0.3 alpha.** The cookie / localStorage / referrer recipes in `personas.json` are NOT applied to the browser — the persona only influences the LLM prompt frame fed to the step selector. All four personas behave identically in-browser (empty state, no referrer); only the framing (`llm_framing`) and patience defaults differ. Real seeding is blocked by the v0.2 security gate (`evaluate_script` denied, `--user-data-dir` refused, no cookie tool in the 9-tool allowlist) and queued for v0.4 via **BRIEF-032**.
- **Honest reading:** for journeys that depend on real persona state — anything keyed off `engaged`'s prior visits or `authenticated`'s session token — the v0.3 alpha verdict is not trustworthy. Use `fresh` for the alpha; the other three become real once BRIEF-032 lands.
- **Selector model:** `claude --print --model claude-haiku-4-5-20251001` (subprocess; honours model-routing.md "subagents default to Haiku" without adding an Anthropic SDK dep to the security-reviewed wrapper).

## Related files

- `journeys/personas.json` — the 4 starter personas with cookie/storage seed recipes
- `journeys/templates/*.json` — P5 template library
- `_pocs/technical/webwitness-vs-playwright/results/READER-ROADMAP.md` — where journeys fit in the three-wave plan
