# Claude Code statusline

A bottom-left status chip for [Claude Code](https://claude.ai/claude-code) that shows the **actual cost of your next turn** — not just turn count, not just elapsed time, but the replay token bill the next prompt will run up.

![live statusline chip rendered in a real Claude Code session](screenshots/live.png)

It also surfaces the 5-hour and weekly caps with reset times, a warning when an error has bloated your session cache, and a runway chip that tells you how many active Claude-hours remain in your weekly budget.

![reference image showing every chip state the statusline can render](screenshots/reference.png)

## Why this exists

Every turn in a long Claude Code session replays the entire accumulated context as cache reads. A short, token-heavy session (three PDFs + a verbose traceback in the transcript) can cost more per turn than a long, clean session of small lookups. Turn count is a weak proxy. Elapsed time is a weak proxy. The only number that maps 1:1 to cost is **R**, the replay token load of the next turn:

```
R = cache_read_input_tokens + cache_creation_input_tokens + input_tokens
```

This statusline reads `R` from the most recent assistant message in the live transcript and renders a colour-coded chip:

| State | R range | Chip | What it means |
|---|---|---|---|
| healthy | `< 200K` | 🟢 | Normal working range. |
| soft warn | `200K – 499K` | 🟡 | Cache is getting expensive; finish this task and log. |
| critical | `500K – 999K` | 🔴 | Each remaining turn replays ~500K+ tokens a fresh session would replay at 10–20K. |
| hard cap | `≥ 1M` | 🔴 | Log before the next message. |

The action at the right-hand side (`/log after task`, `/log now`, `/log before next msg`) is the slash command suggested when you cross a threshold. It defaults to `/log` but is [configurable](#customise-the-action-slash-command) — use `/compact`, `/clear`, or any command that fits your workflow.

## What every chip means

**Base state.** `🟢 [5] 42K next turn` — turn count in brackets (counted from genuine user messages, not tool cycles), then next-turn replay in K or M. The count is bracketed and the word "turns" is dropped on purpose: the headline cost is the K tokens, not the turn count.

**Error chip** — `⚠ 4KB err` — a cached `tool_result` error over 2 KB is sitting in your transcript. Every remaining turn replays it. A single 8 KB traceback plus 1,000 more turns is several million tokens of pure waste. The chip tells you it's there; `/log` clears it.

**5-hour cap chip** — `⚠ 82%·5h→18:30` or `🚨 94%·5h→18:30` — the 5-hour burst limit, with its reset time. Fires only when the projection says you won't make it to reset: burn rate (averaged over the last half-hour of activity) times wall-clock time until reset would push you past 100% — with a 20% headroom buffer. Tier is `🚨` at ≥90% used, `⚠` otherwise.

**Weekly cap chip** — `⚠ 67%·wk→Thu 21:00` or `🚨 91%·wk→Thu 21:00` — the 7-day limit, with its reset time (day-of-week because it's usually more than a day away). Same projection gate, using the since-reset burn rate. Tier is `🚨` at ≥85% used, `⚠` otherwise.

Each cap projects independently. Below the old 75%/60% numbers the chip can still fire if the projection says unsafe; above them it can still be hidden if the projection clears. When there isn't enough activity data yet to compute a runway (fresh reset, quiet start), the chip falls back to the old pure-% trigger so a cold-start session still warns you.

**Runway chip** — `🕐 16h @ avg` — how many active Claude-hours remain in your weekly budget at the current burn rate. Integer above 10h, 0.5h increments below. Only rendered when the weekly cap chip is visible (below the warning threshold, the number isn't behaviourally interesting yet). Colour-coded: neutral above 10h, yellow below 10h, red below 3h.

## Install

```bash
git clone https://github.com/mtberlin2023/claude-code-skills.git
cd claude-code-skills/statusline
bash install.sh
```

The installer:
1. Copies `statusline.sh` and `forecast_gap.py` to `~/.claude/hooks/`.
2. Copies the optional [World Cup feed](#world-cup-feed-optional) (scripts + demo seed) alongside them, seeding `worldcup-data.json` only if it isn't already there.
3. Backs up your existing `~/.claude/settings.json` (timestamped) and sets `statusLine.command` to point at the installed script. Your existing hooks, permissions, and other settings are left alone.
4. Prints a verification summary.

Open a new Claude Code session — the chip renders in the bottom-left bar.

## Uninstall

```bash
bash install.sh --uninstall
```

Offers to restore your timestamped backup. If you decline, it strips just the `statusLine` key out of `settings.json` and removes the installed scripts.

## Customise the action slash command

By default the chip suggests `/log` at the yellow and red thresholds. If you use a different command to wrap up a session, override it:

```bash
export CLAUDE_CODE_STATUSLINE_ACTION=/compact
```

Add the line to your shell rc file so it sticks. The statusline caches its output for 10 seconds, so after changing the env var you may see the old chip until the cache expires.

## World Cup feed (optional)

A toggleable extra: turn the tip line into a live football feed during a tournament. When it's on, the bottom bar appends a rotating line — live match (clock ticking, goals popping in), latest results, upcoming fixtures, and the Golden Boot race:

```
🟢 [12] 48K next turn · /log  ⏷ ⚽ GER 1–1 ESP  67'  🥅 Wirtz 67'
```

> **Want only the football line, without the cost chip?** Install the standalone [worldcup](../worldcup/) skill instead — `bash worldcup/install.sh`. Or, from this directory, `bash install.sh --worldcup-only` defers straight to it. The feed scripts live in `../worldcup/` (one source of truth); this installer just copies them alongside the chip.

`install.sh` copies the feed scripts next to the statusline and seeds a self-contained **demo** dataset, so it works immediately with no API key:

```bash
bash worldcup.sh on              # show the feed in the tip line
bash worldcup.sh off             # back to the normal statusline
bash worldcup.sh status          # is it on? show the current line
bash worldcup.sh teams GER ENG   # follow only these teams
bash worldcup.sh teams clear     # show all teams again
bash worldcup.sh review GER       # full goal-by-goal card for a team's match
```

(Run these from `~/.claude/hooks/`, where the installer put them.)

### What each rotation state looks like

The feed cycles one line at a time (a new slot every ~10s), interleaving the live match with results, fixtures, and the scorers race. These are the real shapes it renders — each line is clipped to 64 chars to fit the bar:

| State | Example line | When it shows |
|---|---|---|
| **Live — in-play** | `⚽ GER 1–1 ESP  67'  🥅 Wirtz 67'` | A match is on. The clock ticks (`67'`, `HT` at the break); a goal or card surfaces in the tail for ~8 match-minutes, newest event wins — a red card bumps an earlier goal: `⚽ GER 1–1 ESP  72'  🟥 Rüdiger 70'`. |
| **Full-time result** | `🏁 FT  BRA 2–1 ARG  V. Júnior 12', Rodrygo 88' \| L. Messi 55' (p)` | After a match ends. Scorers split `home \| away`; `(p)` = penalty, `(og)` = own goal. |
| **Upcoming fixture** | `⏰ NED v POR  in 2h30m · Semi-final` | A scheduled match. Countdown renders `in 5m`, `in 2h30m`, `in 3d`, or `soon` once kickoff is imminent; the stage tag (`Semi-final`, `Final`…) appears when known. |
| **Golden Boot** | `👟 Golden Boot  K. Mbappé FRA 6` | The scorers race. A runner-up rotates in on its own slot: `👟 H. Kane ENG 5 goals`. |
| **Dormant** | *(nothing — normal tip line)* | After the tournament's `end_epoch` passes. The feed emits no line and the bar silently falls back to its usual tip — a calling card shouldn't show stale scores. |

When you turn it on with `worldcup.sh on`, the live line leads and the bar reads like:

```
🟢 [12] 48K next turn · /log  ⏷ ⚽ GER 1–1 ESP  67'  🥅 Wirtz 67'
```

`worldcup.sh review <TEAM>` opens the full goal-by-goal card for a finished match, off the bar and in the terminal:

```
⚽  Germany 2–1 Spain  ·  FT  ·  Semi-final

  12'    1–0   Wirtz  (GER)
  34'    1–1   Pedri  (ESP)
  78'    2–1   Havertz  (pen)  (GER)
```

### Live data (API-Football)

The demo seed is fixed sample data. For real scores, plug in an [API-Football](https://www.api-football.com/) key:

1. Sign up at api-football.com. The free tier covers occasional manual pulls; the Pro tier (7,500 requests/day) is plenty for the auto-poller below.
2. In `~/.claude/hooks/`, copy the example env file and add your key:
   ```bash
   cd ~/.claude/hooks
   cp .worldcup.env.example .worldcup.env
   # then edit .worldcup.env →  API_FOOTBALL_KEY=your_key_here
   ```
3. Pull live data and turn the feed on:
   ```bash
   bash worldcup.sh pull
   bash worldcup.sh on
   ```

`.worldcup.env` holds a real secret and is gitignored — never commit it. A failed pull (no key, network error, quota) is a no-op: it leaves the existing data untouched, so the feed never goes blank.

**Auto-refresh (optional).** `python3 worldcup-feed.py --poll` is a scheduler tick: it pulls only when the feed is toggled on and the tiered interval has elapsed (60s while a match is live, 900s when idle), and stops once the tournament's `end_epoch` passes. Point a `cron` job or a launchd timer at it every 60s for hands-off updates; without it, `worldcup.sh pull` refreshes on demand.

When the tournament ends (past `end_epoch` in the data), the feed goes dormant and the tip line silently falls back to normal — a calling card shouldn't show stale scores.

## Requirements

- macOS or Linux (tested on macOS; Linux likely works but untested).
- `bash` and `python3` 3.8+.
- Claude Code installed at least once so `~/.claude/` exists.

No Python packages required. The core statusline makes no network calls; only the optional World Cup feed's live `pull` reaches out (to API-Football).

## How it works

Claude Code invokes the `statusLine.command` on every screen render and pipes a JSON blob to stdin (session id, transcript path, rate-limit fields). The script:

1. Reads the transcript (a JSONL file) and scans the most recent `assistant` message for `usage.cache_read_input_tokens + cache_creation_input_tokens + input_tokens` — that's `R`.
2. Counts genuine user turns (filtering out synthetic system reminders and tool-cycle echoes).
3. Scans the transcript for any cached `tool_result` error over 2 KB.
4. Pulls `%used` and `resets_at` for both rate-limit windows from the stdin JSON.
5. If weekly cap is visible, calls `forecast_gap.py` to compute remaining runway: scans JSONL events in the current project, groups them into active blocks with a 10-minute gap rule, derives burn rate from `%used / active_hours`, returns `(100 – %used) / burn_rate`.
6. Caches the final rendered chip at `/tmp/claude-statusline-<session>` for 10 seconds to keep terminal renders cheap.

Silent on failure. If anything breaks, the chip just disappears — your terminal never sees a traceback from the statusline.

## Further reading

- **Write-up:** the full cost model — why R is the only number that matters, replay-cost data across 37 sessions, and what changes when you put the number on-screen — at **[SuperMark.live](https://supermark.live)**.

## License

MIT. See `../LICENSE`.

## Author

Mark Turrell — [@mtberlin2023](https://github.com/mtberlin2023)

## Stay in touch

More tools, experiments, and write-ups at **[SuperMark.live](https://supermark.live)** — follow along, or join the newsletter for new skills as they land.
