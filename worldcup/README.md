# World Cup feed for Claude Code

A live football feed in your [Claude Code](https://claude.ai/claude-code) bottom bar — live scores with a ticking clock, goals and cards as they happen, full-time results with scorers, upcoming fixtures with a countdown, and the Golden Boot race.

```
⚽ GER 1–1 ESP  67'  🥅 Wirtz 67'
```

This is the **standalone** install: the football line on its own, no cost-chip statusline. If you also want the next-turn-cost chip (replay tokens, rate-limit caps, weekly runway), install the [statusline](../statusline/) skill instead — its installer offers this exact feed as an add-on (`bash install.sh --worldcup-only` defers right back here, so there's one source of truth either way).

## Install

```bash
git clone https://github.com/mtberlin2023/claude-code-skills.git
cd claude-code-skills/worldcup
bash install.sh
```

The installer:
1. Copies `worldcup-feed.py`, `worldcup.sh`, and `worldcup-statusline.sh` to `~/.claude/hooks/`.
2. Seeds a self-contained **demo** dataset (`worldcup-data.json`) only if one isn't already there — so it works immediately with no API key, and a re-run never clobbers a live pull.
3. Turns the feed on (that's the whole point of a standalone install).
4. Backs up your existing `~/.claude/settings.json` (timestamped) and points `statusLine.command` at the football-only statusline. Your existing hooks, permissions, and other settings are left alone.

Open a new Claude Code session — the feed renders in the bottom-left bar.

## Uninstall

```bash
bash install.sh --uninstall
```

Offers to restore your timestamped backup. If you decline, it strips just the `statusLine` key out of `settings.json` and removes the installed scripts. Your real `.worldcup.env` (API key) and any live-pulled `worldcup-data.json` are kept — delete them by hand if you want them gone.

## Controls

```bash
bash worldcup.sh on              # show the feed
bash worldcup.sh off             # hide it — bar falls back to Claude Code's default
bash worldcup.sh status          # is it on? show the current line
bash worldcup.sh teams GER ENG   # follow only these teams
bash worldcup.sh teams clear     # show all teams again
bash worldcup.sh review GER       # full goal-by-goal card for a team's match
```

(Run these from `~/.claude/hooks/`, where the installer put them.)

## What each rotation state looks like

The feed cycles one line at a time (a new slot every ~10s), interleaving the live match with results, fixtures, and the scorers race. These are the real shapes it renders — each line is clipped to 64 chars to fit the bar:

| State | Example line | When it shows |
|---|---|---|
| **Live — in-play** | `⚽ GER 1–1 ESP  67'  🥅 Wirtz 67'` | A match is on. The clock ticks (`67'`, `HT` at the break); a goal or card surfaces in the tail for ~8 match-minutes, newest event wins — a red card bumps an earlier goal: `⚽ GER 1–1 ESP  72'  🟥 Rüdiger 70'`. |
| **Full-time result** | `🏁 FT  BRA 2–1 ARG  V. Júnior 12', Rodrygo 88' \| L. Messi 55' (p)` | After a match ends. Scorers split `home \| away`; `(p)` = penalty, `(og)` = own goal. |
| **Upcoming fixture** | `⏰ NED v POR  in 2h30m · Semi-final` | A scheduled match. Countdown renders `in 5m`, `in 2h30m`, `in 3d`, or `soon` once kickoff is imminent; the stage tag appears when known. |
| **Golden Boot** | `👟 Golden Boot  K. Mbappé FRA 6` | The scorers race. A runner-up rotates in on its own slot: `👟 H. Kane ENG 5 goals`. |
| **Dormant** | *(nothing — default bar)* | After the tournament's `end_epoch` passes. The feed emits no line and the bar silently falls back — a calling card shouldn't show stale scores. |

`worldcup.sh review <TEAM>` opens the full goal-by-goal card for a finished match, off the bar and in the terminal:

```
⚽  Germany 2–1 Spain  ·  FT  ·  Semi-final

  12'    1–0   Wirtz  (GER)
  34'    1–1   Pedri  (ESP)
  78'    2–1   Havertz  (pen)  (GER)
```

## Live data (API-Football)

The demo seed is fixed sample data. For real scores, plug in an [API-Football](https://www.api-football.com/) key:

1. Sign up at api-football.com. The free tier covers occasional manual pulls; the Pro tier (7,500 requests/day) is plenty for the auto-poller below.
2. In `~/.claude/hooks/`, copy the example env file and add your key:
   ```bash
   cd ~/.claude/hooks
   cp .worldcup.env.example .worldcup.env
   # then edit .worldcup.env →  API_FOOTBALL_KEY=your_key_here
   ```
3. Pull live data:
   ```bash
   bash worldcup.sh pull
   ```

`.worldcup.env` holds a real secret and is gitignored — never commit it. A failed pull (no key, network error, quota) is a no-op: it leaves the existing data untouched, so the feed never goes blank.

**Auto-refresh (optional).** `python3 worldcup-feed.py --poll` is a scheduler tick: it pulls only when the feed is toggled on and the tiered interval has elapsed (60s while a match is live, 900s when idle), and stops once the tournament's `end_epoch` passes. Point a `cron` job or a launchd timer at it every 60s for hands-off updates; without it, `worldcup.sh pull` refreshes on demand.

## When it works

- **No key:** the demo seed rotates through a realistic snapshot (live match looping, results, fixtures, scorers) forever — good for a screenshot or a try-before-you-key.
- **With a key:** `worldcup.sh pull` (or the `--poll` timer) replaces the seed with real fixtures, live scores, results, and the Golden Boot table.
- **After the tournament:** past `end_epoch` in the data, the feed goes dormant and the bar falls back to Claude Code's default. Nothing stale is ever shown.

## Requirements

- macOS or Linux (tested on macOS; Linux likely works but untested).
- `bash` and `python3` 3.8+.
- Claude Code installed at least once so `~/.claude/` exists.

No Python packages required. The feed makes no network calls except the optional live `pull` (to API-Football).

## License

MIT. See `../LICENSE`.

## Author

Mark Turrell — [@mtberlin2023](https://github.com/mtberlin2023)

More tools, experiments, and write-ups at **[SuperMark.live](https://supermark.live)**.
