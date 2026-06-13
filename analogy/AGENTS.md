# analogy — AGENTS.md fragment (Codex)

> Append the rules below to your existing `~/.codex/AGENTS.md`. The skill itself lives at `~/.codex/skills/analogy/` (drop the directory or symlink it there); this fragment wires the firing condition into your global Codex instructions.
>
> Parallel to the `CLAUDE.md` fragment in this directory — same content, retargeted from Claude Code's `~/.claude/CLAUDE.md` to Codex's `~/.codex/AGENTS.md`.

---

```
## Conditional Module — Analogy reframe (cooking default)

Trigger on substantive answers — those that include any of:
- Options (≥2 numbered choices, A/B/C, three paths)
- Tradeoff calls ("X risks Y, but Z…")
- Architectural / non-trivial-reasoning explanations (covers >1 conceptual layer)

When the trigger fires, consult the active analogy domain pack before closing the response. Skill location: `~/.codex/skills/analogy/SKILL.md`. Default domain pack: `~/.codex/skills/analogy/domains/cooking.md`.

Output shapes:
- **Closing reframe paragraph** (default for explanations) — one short paragraph after the technical answer, intro line `*In kitchen terms:*` or italic equivalent.
- **Inline option tags** (default for option tables) — short analogy phrase per option ("house recipe" / "specials board" / "new menu").
- **Full reframe** — only when the user explicitly asks.

Hard rule: the analogy lives alongside the technical answer, never instead of it. Technical recommendation lands first; analogy reframes second.

Do NOT trigger on: lookups, file paths, single-fact answers, status reports, progress updates, log confirmations. If the concept doesn't map cleanly to the pack, say so honestly: "no clean cooking analogy fires here." Empty is signal; padding fails.

To switch domains: edit `default_domain` in `SKILL.md` frontmatter, or pass an inline override ("use sailing as the analogy for this one"). Pack-not-found falls back to cooking.
```
