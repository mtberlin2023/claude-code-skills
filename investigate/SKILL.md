---
name: investigate
description: Narrow-scope review of one SuperMark harness artefact (one skill, one rule, one process doc, one expert, one brief category). Output is stance-shaped — Baseline / Creative / Risk — with explicit spin-out routing to ideas, briefs, and decision log. Skill-as-thin-orchestrator over existing storage; no new tables.
version: 1.0
default_expert_routing:
  brief: MT-GR02         # Vera — research-synthesist
  method: MT-GR02        # Vera
  harness-rule: MT-GT04  # Sid — claude-engineering-expert
  skill: MT-GT04         # Sid
  hook: MT-GT04          # Sid
  process-doc: MT-GT04   # Sid (default; Vera if method-heavy)
  system-shape: MT-GM01  # Akira — expert-system-architect
  lifecycle: MT-GT01     # Erik — life-cycle / promotion-and-retirement
  expert-calibration: ROUTE-TO-CALIBRATE  # /calibrate skill, NOT this one
session: 471
---

# Investigate — Narrow-Scope Harness Review

A skill that runs a stance-shaped investigation on **one** named harness artefact and routes the output across the existing logging primitives. Designed for cadence pull-throughs ("review the brief process", "audit the analogy paper convention") and ad-hoc nudges ("before we touch this hook again, investigate").

The investigation produces three reads of the artefact (Baseline / Creative / Risk) plus an explicit *spin-out* section for downstream improvements that should not be solved inside this investigation.

## When this fires

- Principal call: `/investigate <topic>` (interactive) — full firing, ~15–25K replay.
- Cadence wrapper: `/schedule investigate <topic> <interval>` — uses existing `/schedule` skill; one firing per scheduled invocation. *Phase 1 caveat: `/schedule` invokes remote agents — verify the remote context has local SuperMark repo + supermark MCP access before relying on cadence runs. Local one-shot scheduling ("once at <time>") is the safer first test.*
- Phase 1 nudge hook (warn-only, threshold-promoted per `akira_trigger_guard.py` precedent — ≥20 fires across ≥10 sessions before considering soft-block): UserPromptSubmit hook at `_shared/claude0/hooks/investigate_nudge.py` fires on Principal phrasing like "audit X", "review X process/skill/hook/rule/expert", "let's take a look at X", "investigate X" where X resembles a named harness artefact (slash command, BRIEF-NNN, MT-code, `_shared/...` path, `claude-code-skills/...`, CLAUDE.md, or `<name> skill/hook/rule/brief/process/expert`). Out-of-scope filter: PR/copy/wording/prose/design talk suppresses the nudge. Log: `~/.claude/hooks/investigate-nudge.log`. Does not block.

## When this does NOT fire

- Per-expert calibration → route to `/calibrate`. This skill is for harness *artefacts*, not the personas working through them.
- Broad portfolio scans / cross-cutting audits → out of scope; spin out to a brief instead.
- Pre-close session audits → that's `/log` audit territory.
- One-line fact lookups, status reports, "is X live?" — no stance needed.

## Topic scope — what counts as ONE investigation

**One topic = one named harness artefact.** That is exactly one of:

- One skill (`claude-code-skills/<slug>/`)
- One rule from a CLAUDE.md (named anchor: rule title, not the file)
- One process doc (`_shared/process/<name>.md`)
- One expert persona
- One brief category (e.g. "all `BRIEF-*-scp-*.md`") — category counts as one if it has a coherent shape
- One hook (`_shared/claude0/hooks/<file>.py`)

**Multi-artefact investigations split.** Two skills = two `/investigate` calls. Cross-skill convergence becomes its own *systems-shape* investigation routed to Akira [MT-GM01].

If the topic isn't reducible to one of the above, the investigation should not start — propose a brief instead.

## Output shape — stance protocol (Baseline / Creative / Risk)

Three H2s, mandatory, in order. Mirrors the project's expert-stance reflex (`feedback_expert_stances_objective_fit_and_downstream_risk.md`) so the output is structurally familiar.

### Baseline
Honest read of *now*. Quote evidence from the artefact and from any logged history (`expert_query_history`, `decision_query`). What is it doing? What is it not doing that its frontmatter / spec / brief claims? Lead with the load-bearing facts; no future tense.

### Creative
Generative read of *what could extend*. Must extend Baseline (not duplicate it), must fit the artefact's existing shape (not propose a different artefact class), must include a `[fit-stretch]` marker on each move with two values: a tight extension and a maximally-viable expansion. Renzo-flavoured per the stance reflex doc.

### Risk
Adversarial read across two horizons:
- `[now]` — what breaks today / in the next firing.
- `[downstream]` — what compounds 5–20 firings out; what subtle drift accumulates.

Each risk entry pairs *what* with *evidence* (a quoted log line, a counter-example, a missed gate). No theoretical risks without trace data.

### Spin-out

Single sub-section under Risk, prefixed `### Spin-out — routed to elsewhere`. Lists improvements that surfaced but should NOT be solved inside this investigation. Each line names the target: *"→ idea_log: <one line>"*, *"→ brief: <slug + one-line scope>"*, *"→ /calibrate <expert>"*. Investigation is verdict-only; spin-outs land in their own homes.

## Topic → primary expert routing

The expert whose domain matches the topic runs first, with full load (Read + `expert_query_history` + `expert_log_interaction`). Secondary experts loaded only if the first responder explicitly asks for a peer.

| Topic class | Primary expert | Rationale |
|---|---|---|
| Brief / brief category / method doc | Vera [MT-GR02] (research-synthesist) | Method discipline + adversarial framing |
| Skill / hook / harness rule / process doc | Sid [MT-GT04] (claude-engineering-expert) | Harness layer + Four Properties pass |
| System shape / cross-primitive question / accretion guard | Akira [MT-GM01] (expert-system-architect) | Systems shape, only the architect |
| Lifecycle / promotion / retirement / threshold | Erik [MT-GT01] (life-cycle) | Promotion & retirement gates |
| Per-expert calibration | *route to `/calibrate`* | Out of scope here |

If the topic class is ambiguous, default to **Sid** — the harness layer touches everything else.

## Storage routing — three existing primitives, zero new tables

Single firing writes to all three:

1. **Investigation journal** → `mcp__supermark__expert_log_interaction`
   - `expert_code`: primary expert who ran the investigation.
   - `interaction_type`: `"investigation"` (registered separately in MCP server — see CLAUDE.md fragment).
   - `domain`: `"investigation:<topic>"`.
   - `summary`: one-paragraph synthesis of the three stances.
   - `inner_voice_payload`: JSON with the stance shape — `{"baseline": "...", "creative": "...", "risk_now": "...", "risk_downstream": "..."}`. Queryable verbatim.

2. **Investigation verdict** → `mcp__supermark__decision_log`
   - `decision`: the actionable call (change | leave | promote | retire | reshape).
   - `rationale`: pointer to the journal entry + the load-bearing reason.
   - `domain`: `"investigation:<topic>"`.
   - `expert_code`: same primary expert.
   - `project`: same project as the artefact's home.

3. **Spin-outs** → `mcp__supermark__idea_log` (one row each)
   - `summary`: the spin-out line.
   - `domain`: `"investigation-spinout:<topic>"` (tagged with parent topic so an audit view can pull the tree).

Topic-level audit trail is then a single `decision_query` + `expert_query_history` + `idea_query` filtered to the same `domain:` prefix. No new view, no new table.

## Cost

| Mode | Replay cost | When to use |
|---|---|---|
| Full firing | ~15–25K | First investigation on a topic, or after substantial drift since last firing |
| Lightweight | ~8K | Cadence re-runs where Baseline is mostly diff-against-last-firing; Creative + Risk + Spin-out are the substantive sections |

Per the *cost driver* feedback rule: the meaningful kill criterion is *session control* (turns × cache replay), not generation-token count. Investigation is one orchestrated firing — single design room, no recursion.

## Naming alternatives

`investigate` is the default. Open alternatives for the Principal: `audit` (overloaded with `/log` audit), `probe` (lighter framing), `review-area` (long; overloaded with PR review). Recommendation: keep `investigate` unless overloaded with a Mark-side concept.

## Output discipline

- Stance H2s mandatory; missing one = output is invalid.
- Spin-outs MUST be tagged to a destination (idea / brief / /calibrate). "Address later" is not a valid spin-out.
- The investigation closes with one explicit verdict (the `decision_log` entry). No ballot, no punt — per *synthesis ships decisions, not ballots*.
- Kitchen-analogy close optional; fires when the investigation surfaces ≥2 architectural options (per `feedback_kitchen_analogy_leads_options.md`).
