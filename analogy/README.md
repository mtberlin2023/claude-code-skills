# analogy

> Reference implementation of the **Analogy Layer** described in *Analogies as Cognitive Interfaces* (Turrell 2026). A skill that converts substantive AI output into a six-element reframe a user can mentally simulate: summary + mapping table + simulation prompt + limit statement + user-profile mislead tag + separate second-opinion pass.

Cooking is the default pack. Five more ship: construction (layered roles + time), environment (slow feedback + uncontrollable conditions; garden + ecosystem sub-modes), home (cumulative budget), travel (permissions + sequencing), sport (live coordination). Add your own; the rack is the same shape, the spices swap.

**Status: v1.1.** Audit layer wired with the seven-class signal taxonomy and the v1.1 validation gate; corpus is still single-user pending broader dogfood. See `audit/README.md`.

---

## TL;DR

| You get | Why |
|---|---|
| `SKILL.md` — when to fire, how to render the 4-component output | Skill is consulted on options, tradeoffs, non-trivial reasoning. Not on lookups. |
| `domains/cooking.md` (default) | Kitchen brigade, mise en place, the pass, plating — mapped to the concepts an AI coding session actually surfaces (experts, hooks, MCPs, decisions, briefs, drift). |
| `domains/construction.md` | Layered roles + persistent obligations over time (§9b case). For risk-allocation, contracts, finance. |
| `domains/home.md` | Cumulative-budget / household-economics frame (§10 subscription audit). |
| `domains/travel.md` | Airport sub-domain: permissions, sequencing, graceful failure under load. |
| `domains/sport.md` | Team coordination + role specialisation under live load (v3.6 §10.5 case). |
| `domains/environment.md` | Slow indirect feedback + conditions you cannot control + emergent properties (paper §18 wishlist entry). Two anchor sub-modes: garden (cultivated, intervenable) and ecosystem (uncultivated, intervention cascades). |
| `domains/_template.md` — pluggable contract | Add a domain in 4 sections: roles / gear / rhythms / verbs / when-this-doesn't-fit. Below that, freeform. |
| `WORKED_EXAMPLES.md` | Three before/after fixtures from the paper's §8 / §9b / §10 — the layer working, with the delta named. |
| `audit/` — instrumentation | `decisions.jsonl` append-only log + `check.py` rollup against the four §16 proxies AND the v1.1 validation gate (seven-class signal taxonomy + five gate conditions). Lets you ask "did the layer actually help?" and "is it ready for public push?" |
| `CLAUDE.md` / `AGENTS.md` — append-to-global fragments | Wire the firing condition into your harness's global rules. `CLAUDE.md` for Claude Code; `AGENTS.md` for Codex. Same content, retargeted. |

---

## Install

The skill itself is harness-agnostic (`SKILL.md` + `domains/` + `audit/`). Only the firing wire is harness-specific.

### Claude Code

```bash
# 1. Drop the skill at claude-code-skills/analogy/ (already here if you're reading this)
# 2. Append the CLAUDE.md fragment to your ~/.claude/CLAUDE.md
cat claude-code-skills/analogy/CLAUDE.md >> ~/.claude/CLAUDE.md
# 3. Verify the existing "Cooking-analogy close" rule (if present in your global CLAUDE.md) is consistent — this skill is the operational expansion of that rule
```

### Codex

```bash
# 1. Install the skill into ~/.codex/skills/ (symlink keeps it live; copy if you prefer)
ln -s "$PWD/claude-code-skills/analogy" ~/.codex/skills/analogy
# 2. Append the AGENTS.md fragment to your ~/.codex/AGENTS.md
cat claude-code-skills/analogy/AGENTS.md >> ~/.codex/AGENTS.md
# 3. Restart Codex to pick up the new skill (interactive TUI); `codex exec` picks up immediately on the next invocation
```

No installer script — single skill, no Python, no hook. Both harnesses use the same `SKILL.md` description-based discovery; the AGENTS.md / CLAUDE.md fragment is what makes the skill fire on substantive answers rather than waiting to be invoked by name.

---

## Add a domain

```bash
cp claude-code-skills/analogy/domains/_template.md claude-code-skills/analogy/domains/sailing.md
# Fill in sections: roles / gear / rhythms / verbs / freeform mappings
# Set default_domain in SKILL.md frontmatter to your new pack, or pass inline override:
#   "use sailing as the analogy for this one"
```

---

## Examples

See `WORKED_EXAMPLES.md` for the full before/after comparisons. Quick taster:

**Without the layer:**
> Option A is the lean rig — fast to build, low coverage. Option B is the full pack — high coverage, more AWE upfront. Option C is the hybrid.

**With the layer (4 components, cooking pack):**
> Option A is the lean rig — fast to build, low coverage. Option B is the full pack — high coverage, more AWE upfront. Option C is the hybrid.
>
> *In kitchen terms:* (A) is a single dish off the specials board, (B) is putting the new dish on every section's prep list, (C) is running it through specials first and rolling out if it sells.
>
> | Technical | Kitchen | What this means |
> |---|---|---|
> | Lean rig | Specials-board dish | Narrow, fast, easy to pull if it doesn't sell |
> | Full pack | Every-section prep list | Broad coverage, bigger ask on the brigade |
> | Hybrid | Specials → roll-out | Cheap signal first, expensive commit later |
>
> **Run it forward —** what's the brigade's capacity right now? If they're already at capacity, (B) breaks service before it ships value.
>
> **Where this analogy stops —** kitchens have one head chef per shift; if your system has multiple coordinated controllers, the "one boss" framing leaks.

The analogy is *alongside*, not instead. The technical recommendation always lands first.

---

## The audit layer

`audit/check.py` rolls up `decisions.jsonl` against the four §16 proxies:

1. Cadence — how often the skill fires
2. Frame-rejection rate — paper §8's distinctive claim
3. Component completeness — how often all 4 of (summary / mapping / simulation / limit) ship
4. Comfort vs quality — post-hoc outcome labels

Honest about what it cannot tell you: structural soundness of the mapping, the no-layer counterfactual, and whether comfort is masquerading as quality. The log surfaces the question; it does not answer it.

---

## What this skill does NOT do

- **Diagrams.** Visuals were considered in an earlier design call (2026-05-05); the verdict was 95% analogy, no diagrams. If you want diagrams, that's a separate skill.
- **Rich-domain expertise.** Packs are built on commonly-shared vocabulary, not specialist craft. A real chef's lens / a real surveyor's lens would be a different pack.
- **Always-on for everything.** Lookups, progress reports, tool-result confirmations: skill stays out. Padding kills the signal.
- **The paper itself.** This is the reference implementation. The paper explains the *why*; this repo is the *how*.

---

## Versioning

- **v1.1** (2026-05-12) — extends the four-component output to a six-element spec with the §15A.1 false-confidence defences, and expands the audit instrumentation into a measurable validation gate.
  - Shape A: 6 elements (added user-profile mislead tag + separate second-opinion pass)
  - SKILL.md gains a §15A.1 defences subsection: limit statement at equal prominence (rendering rule), user-profile mislead tag (new element), second-opinion pass (new pass rendered alongside)
  - Feedback verbs: 3 → 6 user-callable, mapped to a seven-class signal taxonomy (class 3 — false-confident — is post-hoc only, labelled in `outcome_label`)
  - `audit/decisions.jsonl` schema: new `schema_version` field, `components` extended from 4 to 6 booleans, `outcome_label` gains `false_confident`
  - `audit/check.py` rewritten: seven-class histogram + five-condition validation gate (sample size, class-7 floor, class-2+3 ceiling, class-5 ceiling, frame-rejection floor, components-all-6 floor). Backward compat with v1.0 records (excluded from gate, still counted in cadence / pack distribution)
  - New domain pack: `environment` (sub-modes: garden + ecosystem) — paper §18 wishlist entry, first pack installed on structural-shape grounds rather than validated case material. Probe of the framework's pack-spec claim.
  - `check.py` reports the v1.1 validation gate pass/fail on each rollup.
- **v1.0** (2026-05-12) — reference implementation of the paper.
  - SKILL.md upgraded to the four-component output (summary / mapping / simulation / limit) per §15
  - Four new packs: `construction`, `home`, `travel`, `sport`
  - `audit/` scaffold (decisions.jsonl + check.py + REPORT.md template) — maps to §16
  - `WORKED_EXAMPLES.md` — three before/after fixtures from §8 / §9b / §10
  - Feedback verbs: `redo`, `flag_misleading`, `lock`
- v0.1 (2026-05-05) — first cut. Cooking pack only. Shape A reframe paragraph only (1/4 of the spec).

## Companion rule in global instructions

The existing "Cooking-analogy close" rule (if present in your global `CLAUDE.md` / `AGENTS.md`) fires this skill on complex / architectural explanations. The fragments in this directory extend the firing condition to options + tradeoffs + non-trivial reasoning more broadly. Both rules can co-exist; the fragments are the operational expansion.

**Validated harnesses:** Claude Code (Opus 4.7 + Sonnet); Codex CLI 0.128+ (gpt-5.5). Token overhead ~3K per substantive answer to load the active domain pack.

## Paper

*Analogies as Cognitive Interfaces* (Turrell 2026). Live worked examples at [supermark.live/analogy](https://supermark.live/analogy). Read the paper for the *why*; read this README + `SKILL.md` + `WORKED_EXAMPLES.md` for the *how*.
