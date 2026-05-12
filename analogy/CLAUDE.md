# analogy — CLAUDE.md fragment

> Append the rules below to your existing `~/.claude/CLAUDE.md`. The skill itself lives at `claude-code-skills/analogy/`; this fragment wires the firing condition into your global rules.
>
> If you already have a "Cooking-analogy close" rule in your global CLAUDE.md (the original SuperMark one), this fragment is its operational expansion — they coexist cleanly.

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

Output shapes:
- **Closing reframe paragraph** (default for explanations) — one short
  paragraph after the technical answer, intro line `*In kitchen terms:*`
  or italic equivalent.
- **Inline option tags** (default for option tables) — short analogy phrase
  per option ("house recipe" / "specials board" / "new menu").
- **Full reframe** — only when the user explicitly asks ("explain my options
  using cooking as an analogy").

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
an inline override ("use sailing as the analogy for this one"). Pack-not-found
falls back to cooking.

# ─── analogy END ────────────────────────────────────────────────────────────
```
