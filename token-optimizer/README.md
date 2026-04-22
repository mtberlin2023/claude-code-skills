# token-optimizer

> Stop your Claude Code Max plan from being eaten alive by long-lived sessions, bloated `CLAUDE.md` files, and bug spirals you didn't notice.

A drop-in skill for [Claude Code](https://claude.ai/claude-code) that audits your own session logs, ranks your worst sessions ("whales"), and adds the lifecycle rules + behavioural nudges that make heavy multi-project usage actually affordable on a Max plan.

Companion to the white paper *["Self-Discovered Token Efficiency: One Heavy User's 30-Day Audit of Claude Code"](https://github.com/mtberlin2023/claude-code-skills/blob/main/token-optimizer/PAPER.md)* — read that for the why; this is the how.

---

## TL;DR — what it does

| You get | Why it matters |
|---|---|
| **`/audit`** slash command | One command shows your top 3 whale sessions, your upset %, your cache-read-to-output ratio, and your projected savings if you cut the whales. Works on your existing logs — no setup. |
| **`/log`** slash command | Writes a HANDOVER.md at the close of any session so you can safely restart the next one fresh, without losing context. |
| **CLAUDE.md fragment** | A copy-pasteable block of rules — Session Lifespan Cap, Bash Discipline, Behavioural Nudge, Response Numbering checkpoints — that enforce the recommendations from the paper inside Claude Code itself. |
| **`audit.py`** script | The 50-line Python analyser. Runs against `~/.claude/projects/*.jsonl`. No dependencies. |
| **Vital signs hook** *(optional)* | A pre-prompt hook that surfaces upset % and bash error rate at the `[20]` and `[30]` response checkpoints, so you see a session degrading in real time instead of after the fact. |

If you only do one thing: run `python3 audit.py` against your own logs, look at your top three sessions, and see for yourself whether the white paper applies to you.

---

## Install

```bash
# Clone the repo
git clone https://github.com/mtberlin2023/claude-code-skills.git
cd claude-code-skills/token-optimizer

# Run the install script
bash install.sh
```

The installer:

1. Copies `audit.py` and the slash-command definitions to `~/.claude/`.
2. Appends the CLAUDE.md fragment to your `~/.claude/CLAUDE.md` (with a backup of the original first).
3. Optionally installs the vital-signs hook.
4. Tells you what it did and what to verify.

You can also do all of this manually — every file in this directory is plain text and the README explains what each one is for.

---

## Manual install (if you don't want to run a bash script)

1. **Audit script.** Copy `audit.py` to `~/.claude/scripts/audit.py` (or anywhere on your `$PATH`). Run it with `python3 ~/.claude/scripts/audit.py`. It needs nothing other than Python 3.
2. **CLAUDE.md rules.** Open `CLAUDE.md` in this directory. Append the contents to your own `~/.claude/CLAUDE.md`. Read it first — most of it is rules about session lifecycle, bash discipline, and the behavioural nudge format.
3. **Slash commands.** Copy `commands/audit.md` and `commands/log.md` to `~/.claude/commands/`. Claude Code will pick them up automatically and they'll appear as `/audit` and `/log`.
4. **Hook (optional).** Copy `hooks/vital-signs.sh` to `~/.claude/hooks/` and register it in your `~/.claude/settings.json` as a `PreToolUse` or `UserPromptSubmit` hook. See the file for the exact `settings.json` snippet.

---

## What the audit shows you

Running `python3 audit.py` on a real heavy-user installation produces something like this:

```
Token Optimizer — Audit
========================
Scanned: ~/.claude/projects/  (12 project folders, 301 sessions)
Window:  2026-03-10 → 2026-04-09  (30 days)

Aggregate
---------
Sessions:                    301
User→assistant turns:     34,275
Output tokens:               8.8 M
Cache reads:                 7.35 B   ← cost driver
Uncached input:              0.8 M
Active Claude time:          148 h
Avg turns / session:         114
Median turn time:            51 s

Top whales (by cache reads)
---------------------------
  1. qrshareme         1,884 turns   140 h wall   8.6 h active   94% idle
  2. fiction-writer    1,449 turns    44 h wall   7.1 h active   84% idle
  3. supermark-deep      650 turns   128 h wall   2.0 h active   98% idle

Top 2 sessions = 34% of the entire month's cache reads.

Vital signs (worst 10 sessions)
-------------------------------
  Avg upset %:        16%   (>20% is bug-spiral territory)
  Avg bash error %:   22%   (>30% is a tooling fight)

Estimated savings if all top-10 whales were split into 100-turn sessions:
  ~52% reduction in cache reads
  ~36% reduction in equivalent API cost

Reading these results: see the companion white paper, sections 4–8.
```

The point of running this is *not* to feel bad about your numbers. It's to find the two or three sessions in your own data that are quietly draining your plan, so you can target the fix at them specifically. Most of the savings in heavy-user workloads come from the long tail, not from the average session.

---

## What's inside

```
token-optimizer/
├── README.md              ← you are here
├── PAPER.md               ← the companion white paper (in full)
├── install.sh             ← one-shot installer
├── audit.py               ← the 50-line analyser
├── CLAUDE.md              ← rules fragment to merge into your global CLAUDE.md
├── commands/
│   ├── audit.md           ← /audit slash command definition
│   └── log.md             ← /log slash command definition
└── hooks/
    └── vital-signs.sh     ← optional pre-turn vital-signs check
```

---

## What it does NOT do

- It does not modify any of your `.jsonl` log files. The audit is read-only.
- It does not send any data anywhere. Everything runs locally.
- It does not change your Claude Code settings beyond appending to `~/.claude/CLAUDE.md` (with a backup) and copying files into `~/.claude/`.
- It does not require an Anthropic API key. The audit reads your local logs. The slash commands run inside your existing Claude Code session.
- It does not enforce the rules — Claude Code does. The skill just installs them.

---

## Uninstall

```bash
bash install.sh --uninstall
```

This restores your original `~/.claude/CLAUDE.md` from the backup made at install time, removes the slash commands, and removes the audit script. Your `.jsonl` logs are not touched.

---

## Reporting back

If you run the audit on your own logs and the numbers tell an interesting story — especially if your distribution looks very different from mine, or if a particular item from the Top 10 worked unusually well or unusually badly for you — open an issue on the repo. I'm collecting before/after data from installers as a follow-up to the white paper. Anonymous summaries are welcome; full logs are not requested or needed.

---

## License

MIT. Use it, fork it, rip out the bits you want, ignore the bits you don't.

---

*Built by [@mtberlin2023](https://github.com/mtberlin2023) — companion to the white paper Self-Discovered Token Efficiency.*
