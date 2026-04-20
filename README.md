# Claude Code Skills

A collection of reusable skills, hooks, and configurations for [Claude Code](https://claude.ai/claude-code) — Anthropic's CLI for AI-assisted development.

## Available Skills

| Skill | Description | Difficulty |
|-------|-------------|------------|
| [statusline](./statusline/) | Bottom-left status chip showing next-turn replay cost, rate-limit caps, and weekly runway. Companion to `token-optimizer`. | Beginner-friendly |
| [token-optimizer](./token-optimizer/) | Reduce token usage by 40-70% through smarter tool use, session management, and model routing. | Beginner-friendly |
| [ui-ux-pro-max](./ui-ux-pro-max/) | Searchable design-intelligence databases (UI styles, color palettes, typography, charts) with CLI. Bundled copy of the upstream [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) skill. | Intermediate |
| [frontend-skills-pack](./frontend-skills-pack/) | Drop-in `CLAUDE.md` that steers Claude toward production-grade Next.js frontends using 21st.dev components — no "AI slop" defaults. | Beginner-friendly |

## What Are Claude Code Skills?

Skills are reusable configurations that change how Claude Code behaves. They can include:

- **CLAUDE.md rules** — instructions Claude follows during your session
- **Hooks** — shell scripts that run automatically on events (e.g., every prompt submission)
- **Status line scripts** — chips in Claude Code's bottom-left bar that surface session state
- **Skill files** — structured prompts that add capabilities

## Installation

Each skill has its own README with install instructions. Most follow this pattern:

```bash
# Clone the repo
git clone https://github.com/mtberlin2023/claude-code-skills.git

# Run the skill's install script (pick whichever skill you want)
cd claude-code-skills/statusline
bash install.sh
```

## Contributing

PRs welcome. Each skill should include:
- `README.md` with clear install instructions
- A beginner-friendly explanation of what it does and why
- An install script or clear manual steps

## License

MIT

## Author

Mark Turrell — [@mtberlin2023](https://github.com/mtberlin2023)
