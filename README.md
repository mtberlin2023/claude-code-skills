# Claude Code Skills

A collection of reusable skills, hooks, and configurations for [Claude Code](https://claude.ai/claude-code) — Anthropic's CLI for AI-assisted development.

## Available Skills

| Skill | Description | Difficulty |
|-------|-------------|------------|
| [token-optimizer](./token-optimizer/) | Reduce token usage by 40-70% through smarter tool use, session management, and model routing | Beginner-friendly |

## What Are Claude Code Skills?

Skills are reusable configurations that change how Claude Code behaves. They can include:

- **CLAUDE.md rules** — instructions Claude follows during your session
- **Hooks** — shell scripts that run automatically on events (e.g., every prompt submission)
- **Skill files** — structured prompts that add capabilities

## Installation

Each skill has its own README with install instructions. Most follow this pattern:

```bash
# Clone the repo
git clone https://github.com/mtberlin2023/claude-code-skills.git

# Run the skill's install script
cd claude-code-skills/token-optimizer
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
