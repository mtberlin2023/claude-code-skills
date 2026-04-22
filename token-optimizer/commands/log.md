---
description: Write a HANDOVER.md at the close of the current session, capturing what was done, what's left, and what context the next session needs. Pre-log audit gate before writing.
---

# /log

End-of-session handover writer. The whole point is to make it safe to restart the next session fresh — without losing context, and without the user feeling like they have to keep the current session alive "just in case."

## Pre-log audit (mandatory — do NOT skip)

Before writing anything, ask the user these questions in order. **Wait for answers. Silence is not confirmation. Do not log until the user has replied.**

1. **What did we actually accomplish in this session?**
   *(Listen for the user's framing — that's what goes in the handover, not your own summary.)*
2. **What's still open or in-progress?**
   *(Anything half-done, anything blocked, anything you said you'd come back to.)*
3. **What does the next session need to know that isn't already in the code or git history?**
   *(This is the critical one. The handover exists to capture state that won't be in the diff.)*
4. **Any decisions we made that the next session shouldn't second-guess?**
   *(Lock-in items. Things you don't want re-litigated.)*

If the user confirms with one-line answers, that's enough. You don't need long replies. You DO need replies.

## Writing the handover

Once you have the four answers:

1. Find the project root (look for `CLAUDE.md`, `package.json`, `pyproject.toml`, `.git/`).
2. Create or update `HANDOVER.md` at the project root with this exact structure:

```markdown
# HANDOVER — {YYYY-MM-DD HH:MM}

## What we did this session
{user's answer to Q1, lightly cleaned up}

## What's still open
{user's answer to Q2}

## Context the next session needs
{user's answer to Q3}

## Locked decisions (don't re-litigate)
{user's answer to Q4}

## Session metadata
- Started: {first user message timestamp, if available}
- Ended: {now}
- Turns: {response number / [N]}
- Cache reads (rough): {pull from /audit if recently run, else "not measured"}
```

3. If a `HANDOVER.md` already exists, **prepend** the new entry — newest at the top.
4. Confirm to the user: *"Handover written to {path}. Safe to /clear or close this session. Next time, start fresh and read this file first."*

## What this command MUST NOT do

- Do NOT log without the user's confirmation. The pre-log audit is a hard gate.
- Do NOT write a summary that the user didn't say. The handover is the user's framing of what happened, not yours.
- Do NOT mark the session "complete" if the user says items are still open. The handover documents the state honestly.
- Do NOT automatically run /clear or close the session. The user does that themselves after reading the handover.

## After the handover is written

Offer one follow-up: *"Want me to draft the opening message for tomorrow's fresh session, so you can copy-paste it as the first prompt?"* — if yes, write a 3–5 line "context restore" prompt that points the next session at HANDOVER.md and the relevant files.
