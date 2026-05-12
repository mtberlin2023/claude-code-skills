---
name: analogy
description: Reframe options, decisions, or non-trivial reasoning using a domain analogy (cooking default; construction / home / travel / sport / pluggable). Lives alongside the technical answer, never instead of it. Reference implementation of the Analogy Layer paper (Turrell 2026).
version: 1.0
default_domain: cooking
available_domains: [cooking, construction, home, travel, sport]
paper: ../../projects/writing/whitepaper_studio/versions/analogy-layer/v2_0_full_paper.md
---

# Analogy — Spice Rack on the Pass

A skill that consults the active domain pack when answering with options, tradeoffs, or non-trivial reasoning, and drops a four-component analogy reframe alongside the technical answer.

This is the reference implementation of the *Analogy Layer* model: the output is structured so the user can mentally simulate the answer, not just read it. The four components below correspond directly to §15 of the paper.

## When this fires

- Any answer that includes **options** (≥2 numbered choices, A/B/C, three paths, etc.)
- Any answer with a **tradeoff call** ("X risks Y, but…")
- Any **architectural / non-trivial-reasoning** explanation (covers >1 conceptual layer)
- Any **redesign / fresh-reasoning** moment

## When this does NOT fire

- Quick lookups (file paths, port numbers, single-fact answers)
- Status reports, progress updates, log confirmations
- Single-sentence answers, pure tool-result reporting
- Anything where the technical answer is already short and self-evident

## How to use

1. **Read the active domain pack** at `domains/<active>.md` (default: `cooking`).
2. **Pick the right domain.** Default holds for most work. Override structurally — not for novelty — when the problem has features the default pack doesn't carry:
   - Layered roles + persistent obligations over time → `construction`
   - Cumulative budget / household-economics decisions → `home`
   - Permissions, sequencing, graceful failure under load → `travel` (airport sub-domain)
   - Team coordination, role specialisation, shared state → `sport`
   - When switching, say *why* in one line so the user can veto: "switching to construction because cooking won't carry the multi-party time-bound structure."
3. **Map the technical concept** to the closest term in the pack.
4. **Place the analogy alongside the technical answer**, never instead of it. Technical recommendation lands first; analogy reframes second.
5. **Don't manufacture analogies.** If nothing maps cleanly: *"no clean <domain> analogy fires here."* Empty is signal; padding fails.
6. **Log the invocation** (when audit is on): append a one-line record to `audit/decisions.jsonl` — see `audit/README.md`.

## Output shapes

**Shape A — full four-component reframe (default for substantive answers):**

> *In kitchen terms:* one or two sentences establishing the parallel rendering.
>
> | Technical | Kitchen | What this means |
> |---|---|---|
> | <concept 1> | <pack term> | <one-line gloss> |
> | <concept 2> | <pack term> | <one-line gloss> |
>
> **Run it forward —** one or two simulation questions the user can answer against the analogy: *"What happens if the kitchen is short-staffed?" "Which station fails first under load?"*
>
> **Where this analogy stops —** one short line on the edge of the mapping: *"This frame doesn't carry [X]; for that, look at [substrate / a different pack]."*

**Shape B — inline option tags (for option tables, when full Shape A is too heavy):**
> Option 1 — *house recipe* | Option 2 — *specials board* | Option 3 — *new menu*

**Shape C — full reframe (when explicitly asked):**
> "Explain my options using cooking as an analogy" → render every option end-to-end inside the analogy. Still include the *Where this analogy stops* line.

## Feedback verbs

The user can call any of these mid-answer; the skill responds in-line:

- **`redo with <domain>`** — render the same reframe in a different pack. Used when the current pack doesn't clarify.
- **`flag misleading`** — record (and stop using) the current frame. Different from *unfamiliar* — a misleading frame produced a wrong simulation, not just an opaque one. Logged for audit.
- **`lock this`** — pin the current pack as preferred for problems of this shape going forward. Updates `audit/locks.jsonl`.

## Switching the active domain

Set `default_domain` in this file's frontmatter, OR pass an inline override: *"use sailing as the analogy for this one."* Pack-not-found falls back to cooking.

## Adding a domain

Drop a new file at `domains/<name>.md` matching the contract in `domains/_template.md`. The pack must cover at minimum: roles (who does what), gear (the tools/objects), rhythms (how time / pace works), verbs (what people do), and a *When this analogy doesn't fit* section. Below that, free-form mappings welcome.

A pack is worth adding when it passes the §12 criteria from the paper: operative familiarity, structural richness, extensibility across scales, bounded mapping, value alignment, consistency potential.

## Audit / measurement

See `audit/README.md`. The skill is instrumented so that invocations can be reviewed for whether the layer actually changed the decision (paper §16). A v1.0 deployment without audit is a 3-component skill in 4-component clothing.

## Worked examples

See `WORKED_EXAMPLES.md` for three before/after fixtures: the kitchen sub-agent case (§8), the ESG-construction case (§9b), and the subscription audit (§10). Each shows the same decision rendered without the analogy layer and with it, with the four components surfaced explicitly.
