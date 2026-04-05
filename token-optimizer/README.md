# Token Optimizer

**Reduce your Claude Code token usage by 40-70%** through smarter file reading, parallel tool calls, session health monitoring, and automatic model routing.

## Why This Exists

Every message you send in Claude Code includes your entire conversation history. The longer your session, the more tokens each message costs — a response at turn 100 can cost **10-30x** what it cost at turn 5.

Most users don't realize this. They run marathon sessions, re-read files they've already seen, get verbose responses full of filler, and wonder why they're burning through their plan limits.

This skill fixes that with three layers:

1. **Rules** — instructions in CLAUDE.md that change how Claude reads files, writes responses, and plans work
2. **Session monitor** — a hook that counts your turns and warns you before sessions get wasteful
3. **Model router** — a hook that suggests cheaper/faster models for simple tasks

## What It Does

### For Beginners (Free/Pro Plan Users)

If you're hitting your usage limits too fast, this skill helps by:

- **Stopping Claude from reading entire files** when it only needs 10 lines
- **Making responses shorter** — no more "Sure! Let me help you with that. First, I'll..."
- **Warning you when sessions get long** — so you can start fresh instead of wasting tokens
- **Suggesting faster mode** for simple tasks like checking files or running commands

### For Power Users

The full optimization stack:

| Optimization | What It Does | Token Savings |
|-------------|--------------|---------------|
| Surgical reads | Uses `offset`/`limit` on files >100 lines | ~30-50% on file reads |
| Grep before read | Finds the exact line range first, reads only that | ~40-60% on searches |
| Parallel tool calls | Batches independent operations into one message | ~20-30% on multi-step tasks |
| Minimal diffs | Smallest unique `old_string` in edits | ~10-20% on edits |
| No re-reads | Never reads a file already in context | ~15-25% on repeated access |
| Haiku subagents | Routes simple searches to a faster, cheaper model | ~60-80% on lookups |
| Response compression | No preamble, no restating, no trailing summaries | ~20-40% on responses |
| Session health hooks | Warns at 50/100/200 turns with escalating urgency | Prevents 10-30x cost blowup |
| Model routing hooks | Suggests `/fast` mode for routine tasks | ~30-50% on simple sessions |
| Memory hygiene | Prevents saving redundant info that bloats context | ~10-20% on context size |

## Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/mtberlin2023/claude-code-skills.git
cd claude-code-skills/token-optimizer
bash install.sh
```

The install script will:
1. Copy hook scripts to `~/.claude/hooks/`
2. Register hooks in `~/.claude/settings.json` (preserving existing settings)
3. Show you the CLAUDE.md rules to add

### Manual Install

If you prefer to do it yourself:

#### Step 1: Add the hooks

Copy the two hook scripts:

```bash
mkdir -p ~/.claude/hooks
cp hooks/session-monitor.sh ~/.claude/hooks/
cp hooks/model-advisor.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/session-monitor.sh
chmod +x ~/.claude/hooks/model-advisor.sh
```

#### Step 2: Register hooks in settings.json

Add this to your `~/.claude/settings.json` (create the file if it doesn't exist):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/session-monitor.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/model-advisor.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

> **Note:** If you already have a `settings.json`, merge the hooks array — don't overwrite the file.

#### Step 3: Add rules to CLAUDE.md

Copy the contents of [`CLAUDE.md.example`](./CLAUDE.md.example) into your global `~/.claude/CLAUDE.md` or your project's `CLAUDE.md`.

## How It Works

### Session Monitor Hook

Runs on every prompt. Counts your conversation turns by reading the session's JSONL log file, then injects warnings into Claude's context:

| Turns | Level | What Happens |
|-------|-------|-------------|
| < 50 | OK | Nothing — session is efficient |
| 50+ | NOTICE | Claude warns you: "We're at ~50 turns, consider wrapping up after this task" |
| 100+ | WARNING | Claude finishes current task only, provides a handover block, recommends stopping |
| 200+ | CRITICAL | Claude stops taking new work, provides handover, refuses to continue |

### Model Router Hook

Runs on every prompt. Classifies your message as simple or complex:

- **Simple tasks** (file lookups, status checks, deploys): Claude uses cheaper `haiku` subagents and suggests `/fast` mode
- **Complex tasks** (architecture, refactoring, creative work): Claude uses full `opus` reasoning

### CLAUDE.md Rules

The rules work without the hooks — they're instructions Claude follows regardless. The hooks add automated enforcement.

## Customization

### Adjusting Session Thresholds

Edit `~/.claude/hooks/session-monitor.sh` and change the numbers:

```bash
# Default thresholds
if [ "$TURNS" -ge 200 ]; then    # CRITICAL — change to your preference
elif [ "$TURNS" -ge 100 ]; then   # WARNING
elif [ "$TURNS" -ge 50 ]; then    # NOTICE
```

### Adjusting Model Routing

Edit `~/.claude/hooks/model-advisor.sh` to change which keywords trigger simple vs. complex classification:

```bash
# Add your own "simple task" keywords
for pattern in "url" "link" "status" "check" "show me" "deploy" ...

# Add your own "complex task" keywords (these override simple)
for pattern in "build" "create" "implement" "refactor" "design" ...
```

### One Topic Per Session

We recommend keeping each Claude Code session focused on a single project or topic. When you switch to something completely different, start a fresh session. This isn't enforced — it's a practice that keeps your context clean and your costs low.

## Uninstall

```bash
rm ~/.claude/hooks/session-monitor.sh
rm ~/.claude/hooks/model-advisor.sh
```

Then remove the hooks entries from `~/.claude/settings.json` and the rules from your `CLAUDE.md`.

## FAQ

**Q: Does this work on the free plan?**
A: Yes. The CLAUDE.md rules work on any plan. The hooks require Claude Code CLI access.

**Q: Will this break my existing setup?**
A: No. The install script preserves your existing `settings.json`. The CLAUDE.md rules are additive.

**Q: How do I know it's working?**
A: Start a long session. After ~50 turns, you'll see Claude mention session health. For model routing, ask a simple question and check if Claude mentions using haiku subagents.

**Q: Can I use just the rules without the hooks?**
A: Absolutely. The CLAUDE.md rules alone provide significant savings. The hooks add automated enforcement.

## License

MIT
