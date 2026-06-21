#!/usr/bin/env python3
"""World Cup statusline feed.

Emits ONE football line per call, rotating every ~10s through:
  live match (clock ticks, goals pop in) · latest results · upcoming fixtures · top scorers.

Data comes from worldcup-data.json (same dir as this script). Copy
worldcup-data.example.json to worldcup-data.json to start with a self-contained
demo, or run `worldcup.sh pull` to fill it live from API-Football. The demo's
synthetic match loops forever so the feed always has something live to show: its
minute is derived from wall-clock vs kickoff_epoch, mod a full match cycle.

Called from statusline.sh's tip line, behind a `.worldcup-feed-on` toggle file
that sits beside this script (see worldcup.sh). Returns nothing on any error so
the statusline cleanly falls back to its normal tips.

Flags:
  (no flag)      print the current rotating line (what the statusline calls)
  --all          print every line in the rotation, one per row
  --at EPOCH     pretend "now" is EPOCH (to watch the live match advance)
  --pull         fetch live data from API-Football → rewrite worldcup-data.json
  --poll         scheduler tick: pull only if toggled on and the interval has elapsed
  --interval     print seconds until the next poll is due (60 while live / 900 idle)
  --review CODE  full goal-by-goal card for a team's match, e.g. --review GER
"""
import datetime
import json
import os
import re
import sys
import time

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worldcup-data.json")
DASH = "–"  # en-dash, e.g. 2–1
MAXLEN = 64
FULL_MINUTES = 95  # 90 + ~5 stoppage before the loop resets
# Flag emoji in the statusline are OFF by design. Country flags are two-codepoint
# regional-indicator sequences (🇨🇭 = "CH" indicators) that the CLI statusline
# renderer doesn't reliably compose — they degrade to spaced letters ("C H"). The
# feed keeps single-codepoint symbols (⚽🏁⏰👟), which render reliably. Verified
# 2026-06-15 + corroborated by external review (grapheme/width handling, UAX #29).
# Flip to True only if a render context is confirmed to compose flag sequences.
SHOW_FLAGS = False

# Code → full name, for the (wide) review output. Falls back to the code itself.
# Full 48-team World Cup 2026 set so a live pull never shows a bare code.
NAMES = {
    "ALG": "Algeria", "ARG": "Argentina", "AUS": "Australia", "AUT": "Austria",
    "BEL": "Belgium", "BIH": "Bosnia & Herzegovina", "BRA": "Brazil", "CAN": "Canada",
    "CPV": "Cape Verde", "COL": "Colombia", "CRO": "Croatia", "CUR": "Curaçao",
    "CZE": "Czech Republic", "COD": "DR Congo", "ECU": "Ecuador", "EGY": "Egypt",
    "ENG": "England", "FRA": "France", "GER": "Germany", "GHA": "Ghana",
    "HAI": "Haiti", "IRN": "Iran", "IRQ": "Iraq", "CIV": "Côte d'Ivoire",
    "JPN": "Japan", "JOR": "Jordan", "MEX": "Mexico", "MAR": "Morocco",
    "NED": "Netherlands", "NZL": "New Zealand", "NOR": "Norway", "PAN": "Panama",
    "PAR": "Paraguay", "POR": "Portugal", "QAT": "Qatar", "KSA": "Saudi Arabia",
    "SCO": "Scotland", "SEN": "Senegal", "RSA": "South Africa", "KOR": "South Korea",
    "ESP": "Spain", "SWE": "Sweden", "SUI": "Switzerland", "TUN": "Tunisia",
    "TUR": "Türkiye", "USA": "USA", "URU": "Uruguay", "UZB": "Uzbekistan",
}


def _name(code):
    return NAMES.get(str(code).upper(), str(code))


# Code → flag emoji. FIFA codes ≠ ISO for some (GER/NED/SUI/TUR), so map explicitly.
FLAGS = {
    "ALG": "🇩🇿", "ARG": "🇦🇷", "AUS": "🇦🇺", "AUT": "🇦🇹", "BEL": "🇧🇪",
    "BIH": "🇧🇦", "BRA": "🇧🇷", "CAN": "🇨🇦", "CPV": "🇨🇻", "COL": "🇨🇴",
    "CRO": "🇭🇷", "CUR": "🇨🇼", "CZE": "🇨🇿", "COD": "🇨🇩", "ECU": "🇪🇨",
    "EGY": "🇪🇬", "ENG": "🇬🇧", "FRA": "🇫🇷", "GER": "🇩🇪", "GHA": "🇬🇭",
    "HAI": "🇭🇹", "IRN": "🇮🇷", "IRQ": "🇮🇶", "CIV": "🇨🇮", "JPN": "🇯🇵",
    "JOR": "🇯🇴", "MEX": "🇲🇽", "MAR": "🇲🇦", "NED": "🇳🇱", "NZL": "🇳🇿",
    "NOR": "🇳🇴", "PAN": "🇵🇦", "PAR": "🇵🇾", "POR": "🇵🇹", "QAT": "🇶🇦",
    "KSA": "🇸🇦", "SCO": "🇬🇧", "SEN": "🇸🇳", "RSA": "🇿🇦", "KOR": "🇰🇷",
    "ESP": "🇪🇸", "SWE": "🇸🇪", "SUI": "🇨🇭", "TUN": "🇹🇳", "TUR": "🇹🇷",
    "USA": "🇺🇸", "URU": "🇺🇾", "UZB": "🇺🇿",
}

# Full English team name (as the worldcup26.ir API spells it) → our 3-letter code.
# Aliases included for the spellings the API uses that differ from NAMES above.
NAME2CODE = {
    "Algeria": "ALG", "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT",
    "Belgium": "BEL", "Bosnia and Herzegovina": "BIH", "Brazil": "BRA",
    "Canada": "CAN", "Cape Verde": "CPV", "Colombia": "COL", "Croatia": "CRO",
    "Curaçao": "CUR", "Curacao": "CUR", "Czech Republic": "CZE", "Czechia": "CZE",
    "Democratic Republic of the Congo": "COD", "DR Congo": "COD",
    "Ecuador": "ECU", "Egypt": "EGY", "England": "ENG", "France": "FRA",
    "Germany": "GER", "Ghana": "GHA", "Haiti": "HAI", "Iran": "IRN", "Iraq": "IRQ",
    "Ivory Coast": "CIV", "Côte d'Ivoire": "CIV", "Cote d'Ivoire": "CIV",
    "Japan": "JPN", "Jordan": "JOR", "Mexico": "MEX", "Morocco": "MAR",
    "Netherlands": "NED", "New Zealand": "NZL", "Norway": "NOR", "Panama": "PAN",
    "Paraguay": "PAR", "Portugal": "POR", "Qatar": "QAT", "Saudi Arabia": "KSA",
    "Scotland": "SCO", "Senegal": "SEN", "South Africa": "RSA",
    "South Korea": "KOR", "Korea Republic": "KOR", "Spain": "ESP", "Sweden": "SWE",
    "Switzerland": "SUI", "Tunisia": "TUN", "Turkey": "TUR", "Türkiye": "TUR",
    "United States": "USA", "USA": "USA", "Uruguay": "URU", "Uzbekistan": "UZB",
}


def _code(team_name):
    """API full team name → our code. Falls back to an upper 3-char slug."""
    if not team_name:
        return "?"
    c = NAME2CODE.get(team_name.strip())
    if c:
        return c
    # Unknown team: best-effort 3-letter code so the feed still renders.
    return "".join(ch for ch in team_name.upper() if ch.isalpha())[:3] or "?"


def _flag(code):
    return FLAGS.get(str(code).upper(), "")


def _tc(code):
    """3-letter code for compact feed lines (e.g. 'GER'), with a flag prefix only
    when SHOW_FLAGS is on. Flags are OFF for the statusline because country flags
    are two-codepoint regional-indicator sequences and the statusline renderer
    doesn't reliably compose them (they degrade to 'C H' / 'M X')."""
    code = str(code).upper()
    if SHOW_FLAGS:
        return f"{FLAGS.get(code, '')} {code}".strip()
    return code


def _tn(code):
    """Full name for the wide review (e.g. 'Germany'), flag prefix only when on."""
    if SHOW_FLAGS:
        return f"{_flag(code)} {_name(code)}".strip()
    return _name(code)


def _now():
    for i, a in enumerate(sys.argv):
        if a == "--at" and i + 1 < len(sys.argv):
            return float(sys.argv[i + 1])
    return time.time()


def _clip(s):
    return s if len(s) <= MAXLEN else s[: MAXLEN - 1].rstrip() + "…"


def _rel(kickoff, now):
    """Human countdown to a future kickoff."""
    d = int(kickoff - now)
    if d <= 0:
        return "soon"
    if d < 3600:
        return f"in {d // 60}m"
    if d < 86400:
        return f"in {d // 3600}h{(d % 3600) // 60:02d}m"
    return f"in {d // 86400}d"


def build_live(live, now):
    """Return (line, minute) for the synthetic live match, or None if disabled.

    Loops: a full match runs for FULL_MINUTES*spm seconds, then an FT pause,
    then it kicks off again — so the feed is never stale.
    """
    if not live or not live.get("enabled"):
        return None
    spm = float(live.get("seconds_per_match_minute", 9))
    pause = float(live.get("ft_pause_seconds", 90))
    loop = live.get("loop", True)
    match_secs = FULL_MINUTES * spm
    raw = now - float(live.get("kickoff_epoch", now))
    if raw < 0:
        return None  # real match hasn't kicked off yet
    if loop:
        # Synthetic demo mode: loop forever so the feed is never stale.
        elapsed = raw % (match_secs + pause)
    else:
        # Real match: real-time pace (set spm=60), holds at FT — no restart.
        elapsed = raw

    h, a = _tc(live["home"]), _tc(live["away"])
    goals = sorted(live.get("goals", []), key=lambda g: g["minute"])

    def score_at(minute):
        hs = sum(1 for g in goals if g["team"] == "home" and g["minute"] <= minute)
        as_ = sum(1 for g in goals if g["team"] == "away" and g["minute"] <= minute)
        return hs, as_

    if elapsed >= match_secs:
        # Full-time pause before the loop restarts.
        hs, as_ = score_at(FULL_MINUTES)
        return _clip(f"🏁 FT  {h} {hs}{DASH}{as_} {a}"), FULL_MINUTES

    minute = int(elapsed / spm)
    minute = max(0, min(FULL_MINUTES, minute))
    hs, as_ = score_at(minute)
    clock = "HT" if 45 <= minute < 46 else f"{minute}'"

    # Something notable just happened? Surface it for ~8 match-minutes. Goals and
    # discrete events (red card, penalty award, yellow) share ONE tail slot, so the
    # newest thing on the pitch always wins — a 60' red card bumps a 54' goal.
    scored = [g for g in goals if g["minute"] <= minute]
    recent = [(g["minute"], f"🥅 {g['scorer']} {g['minute']}'") for g in scored]
    for e in live.get("events", []):
        if e.get("minute", 99) <= minute:
            glyph = {"red": "\U0001F7E5", "pen": "\U0001F3AF PEN",
                     "yellow": "\U0001F7E8"}.get(e.get("type"), "•")
            who = e.get("player") or e.get("scorer") or ""
            recent.append((e["minute"], f"{glyph} {who} {e['minute']}'".replace("  ", " ").strip()))
    tail = ""
    if recent:
        recent.sort(key=lambda x: x[0])
        last_m, last_txt = recent[-1]
        if minute - last_m <= 8:
            tail = f"  {last_txt}"
    return _clip(f"⚽ {h} {hs}{DASH}{as_} {a}  {clock}{tail}"), minute


def _result_scorers(goals):
    """Compact 'home-scorers | away-scorers' tail for a finished result line.
    Each goal renders as 'name min'' with a (p)/(og) marker; sides are split
    on the en-dash to mirror the 'HOME s–s AWAY' score order. Empty if no goals."""
    def fmt(side):
        evs = [g for g in goals if g.get("team") == side]
        parts = []
        for g in sorted(evs, key=lambda x: _parse_minute(x["minute"])[1]):
            mark = " (p)" if g.get("pen") else " (og)" if g.get("og") else ""
            parts.append(f"{g.get('scorer', '?')} {g['minute']}'{mark}")
        return ", ".join(parts)
    home, away = fmt("home"), fmt("away")
    if not home and not away:
        return ""
    return f"  {home} | {away}".rstrip(" |").rstrip()


def build_results(results):
    out = []
    for r in results:
        line = f"🏁 FT  {_tc(r['home'])} {r['hs']}{DASH}{r['as']} {_tc(r['away'])}"
        line += _result_scorers(r.get("goals", []))
        out.append(_clip(line))
    return out


def build_fixtures(fixtures, now):
    out = []
    for fx in fixtures:
        rel = _rel(fx.get("kickoff_epoch", now), now)
        stage = fx.get("stage", "")
        stg = f" · {stage}" if stage else ""
        out.append(_clip(f"⏰ {_tc(fx['home'])} v {_tc(fx['away'])}  {rel}{stg}"))
    return out


def build_scorers(scorers):
    out = []
    if scorers:
        top = scorers[0]
        out.append(_clip(f"\U0001F45F Golden Boot  {top['name']} {_tc(top['team'])} {top['goals']}"))
    # one extra rotating "and also" line if there's a runner-up
    if len(scorers) > 1:
        r = scorers[1]
        out.append(_clip(f"\U0001F45F {r['name']} {_tc(r['team'])} {r['goals']} goals"))
    return out


def _match(codes, followed):
    """True if the followed set is empty (show all) or any team code is followed."""
    return (not followed) or any(c in followed for c in codes)


def _rotation(data, now, followed):
    live_data = data.get("live")
    if live_data and not _match(
        [str(live_data.get("home", "")).upper(), str(live_data.get("away", "")).upper()],
        followed,
    ):
        live_data = None
    live = build_live(live_data, now)
    results = [r for r in data.get("results", [])
               if _match([str(r["home"]).upper(), str(r["away"]).upper()], followed)]
    fixtures = [fx for fx in data.get("fixtures", [])
                if _match([str(fx["home"]).upper(), str(fx["away"]).upper()], followed)]
    scorers = [s for s in data.get("top_scorers", [])
               if (not followed or str(s["team"]).upper() in followed)]
    others = []
    others += build_results(results)
    others += build_fixtures(fixtures, now)
    others += build_scorers(scorers)
    if not others and not live:
        return []
    if not live:
        return others
    live_line = live[0]
    if not others:
        return [live_line]
    # Interleave the live match every other slot so it stays prominent.
    out = []
    for o in others:
        out.append(live_line)
        out.append(o)
    return out


def rotation(data, now):
    # `followed` (set via `worldcup.sh teams GER ENG`) narrows the rotation to the
    # teams the user cares about. Empty = show everything.
    followed = {str(c).upper() for c in data.get("followed", []) if str(c).strip()}
    lines = _rotation(data, now, followed)
    if not lines and followed:
        # Following teams, but nothing about them right now — never go blank; show all.
        lines = _rotation(data, now, set())
    return lines


def _review_finished(r):
    """Full goal-by-goal card for a finished match (the post-game 'review')."""
    home, away = str(r["home"]).upper(), str(r["away"]).upper()
    lines = []
    head = f"⚽  {_tn(home)} {r['hs']}–{r['as']} {_tn(away)}  ·  FT"
    if r.get("stage"):
        head += f"  ·  {r['stage']}"
    lines.append(head)
    lines.append("")
    goals = r.get("goals")
    if goals:
        sh = sa = 0
        for g in goals:
            if g.get("team") == "home":
                sh += 1
            else:
                sa += 1
            mn = f"{g.get('minute', '')}'"
            mark = " (pen)" if g.get("pen") else (" (o.g.)" if g.get("og") else "")
            side = _tc(home) if g.get("team") == "home" else _tc(away)
            lines.append(f"  {mn:<6} {sh}–{sa}   {g.get('scorer', '?')}{mark}  ({side})")
    elif r.get("scorers"):
        for s in r["scorers"]:
            lines.append(f"  • {s}")
    else:
        lines.append("  (goal-by-goal detail not pulled for this match)")
    return "\n".join(lines)


def review(data, code):
    """Return a multi-line review for `code` — finished game, live state, or next fixture."""
    code = str(code).upper()
    for r in data.get("results", []):
        if code in (str(r["home"]).upper(), str(r["away"]).upper()):
            return _review_finished(r)
    live = data.get("live")
    if live and live.get("enabled"):
        if code in (str(live.get("home", "")).upper(), str(live.get("away", "")).upper()):
            line = build_live(live, _now())
            txt = line[0] if line else f"{_tn(live['home'])} v {_tn(live['away'])}"
            return (f"⚽  {_tn(live['home'])} v {_tn(live['away'])} is LIVE now.\n\n"
                    f"  {txt}\n\n"
                    f"  (live scores update on the statusline; re-pull + `worldcup.sh refresh` for goals)")
    now = _now()
    for fx in data.get("fixtures", []):
        if code in (str(fx["home"]).upper(), str(fx["away"]).upper()):
            stg = f"  ·  {fx['stage']}" if fx.get("stage") else ""
            return (f"⏰  {_tn(fx['home'])} v {_tn(fx['away'])}  "
                    f"{_rel(fx.get('kickoff_epoch', now), now)}{stg}\n\n"
                    f"  Not played yet — no review available.")
    return f"No match for '{code}' in the current feed data. Try a 3-letter code, e.g. GER."


# ── Live pull (API-Football → worldcup-data.json) ───────────────────────────
# Source: API-Football v3 (v3.football.api-sports.io), World Cup = league 1.
# Key lives in .worldcup.env beside this script (API_FOOTBALL_KEY) — copy
# .worldcup.env.example to .worldcup.env and paste your key. Never commit the real
# .worldcup.env. Every pull is best-effort: any API/parse failure returns False
# and leaves the existing snapshot untouched.
#
# Quota discipline (Pro = 7,500 req/day): the fixtures list is one call; per-
# fixture goal events are fetched only for LIVE and newly-finished matches
# (finished goals are cached in _events_cache and never re-fetched); top-scorers
# and the group map are time-gated (~5 min / ~1 h). next_interval() lets the
# scheduler poll tightly (60s) while a match is live, loosely (900s) when idle.

API_BASE = "https://v3.football.api-sports.io"
WC_LEAGUE = 1
WC_SEASON = 2026
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".worldcup.env")

# status.short buckets (API-Football). Anything else (NS/TBD/PST/CANC…) = upcoming.
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"}
DONE_STATUSES = {"FT", "AET", "PEN"}


def _api_key():
    """Read API_FOOTBALL_KEY from the local env file (surrounding quotes stripped).
    Falls back to the process env. Returns None if unset."""
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("API_FOOTBALL_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"") or None
    except OSError:
        pass
    return os.environ.get("API_FOOTBALL_KEY") or None


def _api_get(path, key, timeout=25):
    """GET an API-Football endpoint → its `response` list. None on any failure
    (network, non-JSON, or a non-empty `errors` payload e.g. quota/auth)."""
    import urllib.request
    try:
        req = urllib.request.Request(API_BASE + path, headers={"x-apisports-key": key})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"api-get {path}: {e}\n")
        return None
    errs = payload.get("errors")
    if errs:  # dict {"requests": "..."} or non-empty list → quota/auth/param error
        sys.stderr.write(f"api-get {path}: errors {errs}\n")
        return None
    return payload.get("response", [])


def _short_name(name):
    """'Raul Jimenez' → 'R. Jimenez'. Leaves already-abbreviated names untouched."""
    name = (name or "").strip()
    parts = name.split()
    if len(parts) >= 2 and not parts[0].endswith(".") and len(parts[0]) > 1:
        return f"{parts[0][0]}. {' '.join(parts[1:])}"
    return name or "?"


def _events_to_goals(events, home_id, away_id):
    """API-Football event list → ordered goal dicts
    [{minute, minute_n, team:'home'|'away', scorer, pen, og}].

    Guards two footguns: `type=Goal, detail='Missed Penalty'` is NOT a goal
    (skipped); an Own Goal credits the OPPOSING side, not the scorer's team."""
    out = []
    for e in events or []:
        if e.get("type") != "Goal":
            continue
        detail = e.get("detail") or ""
        if detail == "Missed Penalty":
            continue
        og = detail == "Own Goal"
        pen = detail == "Penalty"
        tid = (e.get("team") or {}).get("id")
        if og:
            side = "away" if tid == home_id else "home"
        else:
            side = "home" if tid == home_id else "away"
        t = e.get("time") or {}
        el, ex = t.get("elapsed"), t.get("extra")
        if el is None:
            disp, n = "", 0
        elif ex:
            disp, n = f"{el}+{ex}", el
        else:
            disp, n = str(el), el
        out.append({"minute": disp, "minute_n": n, "team": side,
                    "scorer": _short_name((e.get("player") or {}).get("name")),
                    "pen": pen, "og": og})
    out.sort(key=lambda g: g["minute_n"])
    return out


def _parse_minute(token):
    """'90+5' / '45+5' / '27' → ('90+5', 90). The int key is the base minute,
    used both for sort order and for the live score_at() comparison."""
    m = re.search(r"(\d+)(?:\s*\+\s*(\d+))?", token or "")
    if not m:
        return "", 0
    base = int(m.group(1))
    extra = int(m.group(2)) if m.group(2) else 0
    return (f"{base}+{extra}" if extra else str(base)), base


def _group_map(key, existing, now):
    """team_id → 'Group A' from /standings, cached ~1 h (group assignments are
    static). Returns (map, ts) so the caller can persist the cache + timestamp."""
    cached = {int(k): v for k, v in (existing.get("_group_map") or {}).items()}
    age = now - (existing.get("_group_map_ts") or 0)
    if cached and age <= 3600:
        return cached, existing.get("_group_map_ts") or 0
    st = _api_get(f"/standings?league={WC_LEAGUE}&season={WC_SEASON}", key)
    if not st:
        return cached, existing.get("_group_map_ts") or 0
    try:
        gmap = {}
        for grp in st[0]["league"]["standings"]:
            for row in grp:
                gmap[row["team"]["id"]] = row.get("group") or ""
        return (gmap or cached), now
    except (KeyError, IndexError, TypeError):
        return cached, existing.get("_group_map_ts") or 0


def pull():
    """Fetch World Cup data from API-Football → rewrite worldcup-data.json in place.

    Best-effort: returns False and leaves the file untouched on any API/parse
    failure, so the manually-curated snapshot always survives a bad pull. Only
    fetches per-fixture goal events for live + newly-finished matches (finished
    goals are cached in _events_cache), staying well under the daily quota.
    """
    key = _api_key()
    if not key:
        sys.stderr.write("pull: no API_FOOTBALL_KEY in .worldcup.env; keeping manual snapshot\n")
        return False

    games = _api_get(f"/fixtures?league={WC_LEAGUE}&season={WC_SEASON}", key)
    if not games:
        sys.stderr.write("pull: no fixtures from API; keeping manual snapshot\n")
        return False

    try:
        with open(DATA) as f:
            existing = json.load(f)
    except Exception:
        existing = {}

    now = int(_now())
    ev_cache = dict(existing.get("_events_cache") or {})   # str(fixture_id) -> goals list
    group_map, gm_ts = _group_map(key, existing, now)

    live = None
    results = []   # (kickoff_ts, dict)
    fixtures = []  # (kickoff_ts, dict)

    def _stage(fx, hid, aid):
        rnd = (fx.get("league") or {}).get("round") or ""
        if rnd.startswith("Group Stage"):
            return group_map.get(hid) or group_map.get(aid) or "Group Stage"
        return rnd

    for fx in games:
        finfo = fx.get("fixture") or {}
        status = (finfo.get("status") or {}).get("short") or ""
        fid = finfo.get("id")
        ts = finfo.get("timestamp") or 0
        home = (fx.get("teams") or {}).get("home") or {}
        away = (fx.get("teams") or {}).get("away") or {}
        hc, ac = _code(home.get("name")), _code(away.get("name"))
        hid, aid = home.get("id"), away.get("id")
        stage = _stage(fx, hid, aid)
        gh = (fx.get("goals") or {}).get("home")
        ga = (fx.get("goals") or {}).get("away")

        if status in LIVE_STATUSES:
            goals = _events_to_goals(_api_get(f"/fixtures/events?fixture={fid}", key) or [], hid, aid)
            live = {
                "enabled": True, "loop": False,
                "home": hc, "away": ac,
                "home_full": home.get("name"), "away_full": away.get("name"),
                "stage": stage,
                "kickoff_epoch": ts or now,
                "seconds_per_match_minute": 60, "ft_pause_seconds": 0,
                "status": status, "elapsed": (finfo.get("status") or {}).get("elapsed") or 0,
                # live goals carry an int minute (rotation's score_at() compares numerically)
                "goals": [{"minute": g["minute_n"], "team": g["team"], "scorer": g["scorer"]} for g in goals],
                "events": [],
            }
        elif status in DONE_STATUSES:
            sid = str(fid)
            goals = ev_cache.get(sid)
            if goals is None:  # fetch once, then cache — finished goals never change
                goals = [{"minute": g["minute"], "team": g["team"], "scorer": g["scorer"],
                          **({"pen": True} if g["pen"] else {}),
                          **({"og": True} if g["og"] else {})}
                         for g in _events_to_goals(_api_get(f"/fixtures/events?fixture={fid}", key) or [], hid, aid)]
                ev_cache[sid] = goals
            results.append((ts, {"home": hc, "away": ac, "hs": int(gh or 0), "as": int(ga or 0),
                                 "stage": stage, "goals": goals}))
        else:  # NS / TBD / PST / CANC … → upcoming
            f_ = {"home": hc, "away": ac, "stage": stage}
            if ts:
                f_["kickoff_epoch"] = ts
            fixtures.append((ts or (1 << 62), f_))

    results.sort(key=lambda x: -x[0])               # most-recent finished first
    fixtures.sort(key=lambda x: x[0])               # nearest kickoff first
    results = [r for _, r in results][:10]
    fixtures = [f for _, f in fixtures][:8]

    # Top scorers — direct endpoint, time-gated (~5 min) so live polling stays cheap.
    top = existing.get("top_scorers") or []
    ts_at = existing.get("_topscorers_ts") or 0
    if not top or (now - ts_at) > 300:
        rows = _api_get(f"/players/topscorers?league={WC_LEAGUE}&season={WC_SEASON}", key)
        if rows:
            top = []
            for row in rows[:10]:
                stat = (row.get("statistics") or [{}])[0]
                top.append({"name": _short_name((row.get("player") or {}).get("name")),
                            "team": _code((stat.get("team") or {}).get("name")),
                            "goals": (stat.get("goals") or {}).get("total") or 0})
            ts_at = now

    out = dict(existing)  # preserve tournament / anchor_epoch / end_epoch / followed
    out["_note"] = (f"AUTO-PULLED from API-Football (league {WC_LEAGUE}, season {WC_SEASON}). "
                    f"{len(results)} results, {len(fixtures)} fixtures, "
                    f"{'1 live' if live else 'no live match'}. Re-run `worldcup.sh pull` to refresh.")
    out["live"] = live or {"enabled": False}
    out["results"] = results
    out["fixtures"] = fixtures
    out["top_scorers"] = top
    out["_events_cache"] = ev_cache
    out["_topscorers_ts"] = ts_at
    out["_group_map"] = {str(k): v for k, v in group_map.items()}
    out["_group_map_ts"] = gm_ts
    out["_pulled_at"] = now

    with open(DATA, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    for p in __import__("glob").glob("/tmp/claude-statusline-*"):
        try:
            os.remove(p)
        except OSError:
            pass
    sys.stderr.write(f"pull: wrote {len(results)} results, {len(fixtures)} fixtures, "
                     f"{len(top)} scorers, live={'yes' if live else 'no'}; "
                     f"next poll in {next_interval(out)}s\n")
    return True


def next_interval(data):
    """Tiered cadence for the scheduler: 60s while a match is live, 900s when idle."""
    return 60 if (data.get("live") or {}).get("enabled") else 900


def main():
    if "--pull" in sys.argv:
        sys.exit(0 if pull() else 1)  # exit code lets worldcup.sh detect a failed pull
    if "--poll" in sys.argv:
        # Scheduler tick (launchd fires this every 60s). Pull ONLY if the feed is
        # toggled on AND the tiered interval has elapsed since the last pull — so a
        # fixed 60s timer yields 60s-live / 900s-idle cadence with near-zero waste.
        flag = os.path.join(os.path.dirname(DATA), ".worldcup-feed-on")
        if not os.path.exists(flag):
            return  # feed off → no API calls at all
        try:
            with open(DATA) as f:
                d = json.load(f)
        except Exception:
            d = {}
        end_epoch = d.get("end_epoch")
        if end_epoch and _now() >= float(end_epoch):
            return  # tournament over → stop polling
        if _now() >= (d.get("_pulled_at") or 0) + next_interval(d):
            sys.exit(0 if pull() else 1)
        return
    try:
        with open(DATA) as f:
            data = json.load(f)
    except Exception:
        return
    if "--review" in sys.argv:
        i = sys.argv.index("--review")
        if i + 1 < len(sys.argv):
            print(review(data, sys.argv[i + 1]))
        return
    if "--interval" in sys.argv:  # scheduler asks: how soon to poll again?
        print(next_interval(data))
        return
    now = _now()
    # Tournament cutoff: after end_epoch the feed goes dormant — emit nothing so
    # the statusline falls back to normal tips. A calling card must not show stale
    # scores once the event is over.
    end_epoch = data.get("end_epoch")
    if end_epoch and now >= float(end_epoch):
        return
    lines = rotation(data, now)
    if not lines:
        return
    if "--all" in sys.argv:
        for ln in lines:
            print(ln)
        return
    idx = int(now // 10) % len(lines)
    print(lines[idx])


if __name__ == "__main__":
    main()
