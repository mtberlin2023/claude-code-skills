# token-optimizer — CLAUDE.md fragment

> Append the rules below to your existing `~/.claude/CLAUDE.md`. The installer does this for you (with a backup of your original first). If you're installing manually, paste everything between the START and END markers.
>
> These rules are deliberately small. They're the ones that, in the audit data behind the companion white paper, accounted for the majority of the savings. Read the paper if you want the why; this file is the what.

---

```
# ─── token-optimizer START ──────────────────────────────────────────────────

## Critical Friction Rule — Session Lifespan Cap
Trigger on **next-turn replay tokens (R)**, never on turn/call counts, MB,
or wall-clock hours. R = the tokens the next call will read from cache
(cache_read_input_tokens + cache_creation_input_tokens + input_tokens from
the most recent assistant message).

Thresholds:
  R ≥ 200K — soft check. Audit cache for bloat sources (verbose tool errors,
             large MCP results, big unread-but-cached files, redundant reads).
  R ≥ 500K — recommend /log after current task. Never mid-task.
  R ≥ 1M   — hard cap. Split before the next substantive task. Never mid-task.

When a threshold fires, surface this exact warning and wait for user decision
(the headline is tokens — do NOT substitute turns, calls, MB, or hours):

  ⚠ Your next turn will replay approximately **{K}K tokens** of accumulated
  context as cache reads. A fresh session replays ~10–20K. **You're paying
  ~{multiplier}× per turn to keep this session going.** Continue, or /log
  and restart fresh?

Turn counts are NOT thresholds. An 8-turn session that loaded three PDFs can
blow past R ≥ 1M; a clean 150-turn session can stay under 200K. Trigger on
the token metric. State the tokens, not feelings.

## Critical Friction Rule — Bash Discipline
Bash is a last resort. Exhaust dedicated tools first:
  - Read instead of cat / head / tail
  - Edit instead of sed / awk
  - Glob instead of find / ls
  - Grep instead of grep / rg
  - Write instead of echo redirection / heredoc
Use Bash only for genuine system operations (git, package managers, running
scripts, starting servers, network probes).

One-strike rule on bash: after a single bash failure, switch approach — do
NOT retry the same command with variants. Read the actual error, change
strategy.

Always use absolute paths in bash. Never `cd && ...` or rely on pwd. Working-
directory drift causes a large fraction of bash failures.

## Response Numbering
Prefix every response with [N] where N = current user turn, counted from [1]
(count genuine user messages you've received this session — not tool cycles,
not sub-agent calls). Don't track call count in the prefix; it's not
reliably knowable from inside a turn, and the slash-unknown is just noise.
The session-health hook reports both user turns and model calls as a
secondary diagnostic line when the R thresholds fire.

Drift checks fire off R, not off turn count. At R ≥ 200K, audit the cache
for bloat sources (verbose tool errors, large MCP results, big unread-but-
cached files, redundant reads) and surface a brief note listing the likely
culprits. At R ≥ 500K, recommend /log after the current task. At R ≥ 1M,
hard cap — split before the next substantive task. Never mid-task.

## Slash commands
/audit — run the token-optimizer audit script against ~/.claude/projects
         and print the user's own version of the white paper's section 4
         table. See ~/.claude/commands/audit.md.

/log   — write a HANDOVER.md at the close of the current session, capturing
         what was done, what's left, and what context the next session
         needs. Run pre-log audit first (see commands/log.md). Wait for
         user confirmation before logging. Silence is not confirmation.

# ─── token-optimizer END ────────────────────────────────────────────────────
```
