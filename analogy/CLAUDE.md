# analogy — CLAUDE.md fragment

> Append the rules below to your existing `~/.claude/CLAUDE.md`. The skill itself lives at `claude-code-skills/analogy/`; this fragment wires the firing condition into your global rules.
>
> If you already have a "Cooking-analogy close" rule in your global CLAUDE.md, this fragment is its operational expansion — they coexist cleanly.

---

```
# ─── analogy START ──────────────────────────────────────────────────────────

## Conditional Module — Analogy reframe (cooking default)

Trigger on substantive answers — those that include any of:
- Options (≥2 numbered choices, A/B/C, three paths)
- Tradeoff calls ("X risks Y, but Z…")
- Architectural / non-trivial-reasoning explanations (covers >1 conceptual layer)
- Redesign or fresh-reasoning moments

When the trigger fires, consult the active analogy domain pack before closing
the response. Skill location: `claude-code-skills/analogy/SKILL.md`. Default
domain pack: `claude-code-skills/analogy/domains/cooking.md`.

Output shapes (full v1.1 spec in `claude-code-skills/analogy/SKILL.md`):
- **Closing reframe paragraph** — one short kitchen-frame paragraph after
  the technical answer (light default for short explanations).
- **Shape A — full six-element reframe** — default for substantive answers
  hitting the firing conditions above. Six elements: summary, mapping table,
  simulation prompt, limit statement at equal prominence, "would mislead a
  user like you" tag, separate second-opinion pass.
- **Shape B — inline option tags** — short analogy phrase per option, when
  Shape A is too heavy ("house recipe" / "specials board" / "new menu").
- **Shape C — Shape A applied end-to-end inside every option** — only when
  the user explicitly asks ("explain my options using cooking as an analogy").

Feedback verbs (user-callable mid-stream): `flag unfamiliar` / `flag misleading`
/ `flag bleed` / `drop analogy` / `redo with <domain>` / `lock this`. Each maps
to one class in the seven-class signal taxonomy. Class 3 (false-confident) is
post-hoc only — set `outcome_label: false_confident` on review.

Audit: append one record per invocation to
`claude-code-skills/analogy/audit/decisions.jsonl` with
`schema_version: "1.1"`. Schema in `audit/README.md`. The skill's validation
gate clears via `audit/check.py` once enough v1.1 records accumulate.

Hard rule: the analogy lives **alongside** the technical answer, never
instead of it. Technical recommendation lands first; analogy reframes second.

Do NOT trigger on:
- Lookups (file paths, ports, single-fact answers)
- Status reports, progress updates, log confirmations
- Single-sentence answers, pure tool-result reporting
- Anything where the technical answer is already short and self-evident

If the concept doesn't map cleanly to the pack, say so honestly:
"no clean cooking analogy fires here." Empty is signal; padding fails.

To switch domains: edit `default_domain` in `SKILL.md` frontmatter, or pass
an inline override ("use environment as the analogy for this one").
Pack-not-found falls back to cooking. Available domains: cooking (default),
construction, environment, home, travel, sport.

# ─── analogy END ────────────────────────────────────────────────────────────
```
