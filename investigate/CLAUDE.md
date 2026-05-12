# investigate — CLAUDE.md fragment

> Append the rules below to your existing `~/.claude/CLAUDE.md`. The skill itself lives at `claude-code-skills/investigate/`; this fragment wires the trigger phrasing and the storage discipline into global rules.

---

```
# ─── investigate START ──────────────────────────────────────────────────────

## Conditional Module — /investigate (narrow-scope harness review)

Skill location: `claude-code-skills/investigate/SKILL.md`. Stance-shaped output
(Baseline / Creative / Risk + Spin-out). Skill-as-thin-orchestrator over
existing storage — expert_log_interaction (type=investigation), decision_log,
idea_log. No new tables; no new mechanism class.

### Trigger forms

- Principal direct call: `/investigate <topic>`.
- Cadence: `/schedule investigate <topic> <interval>` (uses the existing
  `/schedule` skill).
- Optional Phase 1 nudge hook (warn-only, threshold-promoted at ≥20 fires
  across ≥10 distinct sessions per `akira_trigger_guard.py` precedent):
  - UserPromptSubmit on Principal phrasing — "audit X", "let's review X",
    "take a look at X" where X is a named harness artefact.
  - PreToolUse on harness paths — `_shared/process/*.md`, CLAUDE.md files,
    `_shared/claude0/hooks/*.py`, `claude-code-skills/*/SKILL.md`.
  - Nudge text: "recent /investigate on this topic? cite the entry."

### Topic scope (hard rule)

One topic = one named harness artefact (one skill, one rule, one process doc,
one expert, one brief category, one hook). Multi-artefact investigations
split. Cross-skill convergence becomes its own systems-shape investigation
routed to Akira [MT-GM01].

### Primary expert routing

| Topic class | Primary |
|---|---|
| Brief / method | Vera [MT-GR02] |
| Skill / hook / harness rule / process doc | Sid [MT-GT04] |
| System shape / cross-primitive | Akira [MT-GM01] |
| Lifecycle / promotion / retirement | Erik [MT-GT01] |
| Per-expert calibration | route to `/calibrate` |

Ambiguous → default to Sid (harness layer touches everything).

### Storage discipline (mandatory per firing)

1. `expert_log_interaction` with `interaction_type='investigation'`,
   `domain='investigation:<topic>'`, stance shape in inner_voice_payload.
2. `decision_log` verdict with `domain='investigation:<topic>'`. One verdict
   per firing — change | leave | promote | retire | reshape. No ballots.
3. `idea_log` rows for each spin-out, `domain='investigation-spinout:<topic>'`.

Missing any of the three = firing is invalid.

### Stance discipline

Three H2s in order: Baseline / Creative / Risk. Creative must extend Baseline
and carry `[fit-stretch]` markers per Renzo's stance reflex. Risk must split
`[now]` / `[downstream]` with quoted evidence; no theoretical risks. Spin-out
is a sub-section of Risk and routes EVERY surfaced improvement to a named
destination — never "address later".

### Out of scope

- Per-expert calibration → `/calibrate`.
- Broad portfolio scans → propose a brief, don't `/investigate`.
- Pre-close session audits → that's `/log` audit territory.
- One-line fact lookups → just answer.

# ─── investigate END ────────────────────────────────────────────────────────
```
