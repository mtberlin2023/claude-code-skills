---
description: Run the token-optimizer audit on ~/.claude/projects/*.jsonl and print a readable report (top whales, upset %, bash error %, projected savings).
---

# /audit

Run the local audit script against the user's Claude Code session logs and display the results.

## What this command does

1. Verify `~/.claude/scripts/audit.py` exists. If not, tell the user the skill isn't installed and point them to `https://github.com/mtberlin2023/claude-code-skills/tree/main/token-optimizer`.
2. Run: `python3 ~/.claude/scripts/audit.py --top 10`
3. Display the output verbatim.
4. After the report, summarise the three things the user should look at first:
   - **Their #1 whale.** Name the project, the turn count, and the cache reads. State whether it's a Pattern A (multi-day workspace), B (project fusion), or C (bug spiral) — see white paper section 6.
   - **Their upset % and bash error %.** If both are above the thresholds, name the offending sessions.
   - **The biggest single saving available.** Usually splitting the top 1–2 whales into 100-turn pieces.

## Optional flags the user might pass

- `/audit since 2026-04-01` → only sessions starting on or after a date. Pass through as `--since 2026-04-01`.
- `/audit project myproj` → limit to one project folder. Pass through as `--project myproj`.
- `/audit json` → emit machine-readable JSON. Pass through as `--json`.

## After the report

Offer the user three follow-ups, in priority order:

1. *"Want me to look at your top whale and tell you what was actually in it?"* — read a sample of that session's `.jsonl`, identify which of Patterns A/B/C it matches, and write a one-paragraph diagnosis.
2. *"Want me to check your `~/.claude/CLAUDE.md` for bloat?"* — read it, count lines, identify which sections could move to on-demand files, and suggest a target line count.
3. *"Want me to set up a weekly re-audit so you can watch the numbers move?"* — install a cron entry or a calendar reminder.

Do NOT automatically take any of these actions. Wait for the user to choose.

## Failure modes

- If `~/.claude/projects/` doesn't exist: the user has never run Claude Code, or runs it in a non-default location. Ask which.
- If the script throws a Python error: capture the traceback, print it, and offer to file a bug report at the skill repo.
- If the script runs but reports zero sessions: the date filter was too aggressive, or the user is in a fresh install. Suggest dropping the `--since` flag.
