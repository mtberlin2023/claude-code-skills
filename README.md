# Claude Code Skills

A small collection of reusable skills for [Claude Code](https://claude.ai/claude-code) — Anthropic's CLI for AI-assisted development.

## Available Skills

| Skill | Description | Difficulty |
|-------|-------------|------------|
| [analogy](./analogy/) | Reference implementation of the **Analogy Layer** — converts substantive AI output into a six-element reframe the reader can mentally simulate (mapping table + simulation prompt + limit statement + mislead tag + second-opinion pass). Six pluggable domain packs (cooking default). | Intermediate |
| [statusline](./statusline/) | Bottom-left status chip showing your next-turn replay cost, the 5-hour/weekly rate-limit caps with reset times, and weekly runway. | Beginner-friendly |

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

# Follow the skill's README (analogy is install-free; statusline has an install script)
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
