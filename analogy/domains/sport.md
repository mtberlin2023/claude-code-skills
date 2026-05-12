# sport — domain pack

> Team sport — football, basketball, rugby, hockey — runs on shared state, role specialisation, and live coordination. This is the pack to reach for when the problem is *who's covering what right now, where the gaps are, and how the team adapts when one position breaks down*. Matches the §10.5 "hooks-as-team-sport" case from v3.6 and any problem where coordination under live load is the substance.

> Value-alignment note (per §12): sport imports a win/lose frame. That's correct for some problems and quietly poisonous for others. Don't reach for sport when the work is collaborative, exploratory, or zero-sum thinking would distort the call.

---

## Roles (who does what)

| Concept | Sport term | Use when |
|---|---|---|
| Principal | Captain (on the pitch) / head coach (above it) | The decision-maker — captain in the moment, coach across matches |
| Expert (any tier) | Position player / specialist (striker, defender, keeper) | Owns one position; runs it; doesn't drift across the pitch |
| Meta-expert | Head coach / manager | Sets the system; doesn't take the kicks |
| Adversarial reviewer | Match referee / opposition scout / video analyst | Catches what the team normalised |
| Subagent (Haiku/Sonnet) | Substitute / training-ground player | On the bench, ready, not in play |
| Domain expert | Specialist coach (set-piece, goalkeeping, fitness) | One narrow craft, deep practice |
| Sub-expert pair | Two players competing for the same shirt | Deliberately differing on one axis; one starts, one waits |

## Gear (the tools and objects)

| Concept | Sport term | Use when |
|---|---|---|
| Persona file | Position card / role brief | What this player is supposed to do, written down |
| Calibration card | The tactical playbook | The reference for "this is how we play this game" |
| Instinct file | Trained reflexes / muscle memory | What fires before conscious thought |
| Notepad / reflex bank | Halftime team-talk notes | Reminders the coach surfaces between halves |
| Working memory (post-/dream) | Post-match analysis bank | Vivid lessons from past matches the squad holds |
| Hook (Claude Code) | The whistle / VAR check / substitution window | Fires automatically on a known trigger |
| MCP server | The bench / academy / training ground | Where the ready resources sit, not in play yet |
| Knowledge pack | Team playbook / set-piece routines | Written plays for one class of situation |
| Skill | A technique (free kicks, tackling, passing) | Portable across positions and matches |
| Brief | The match plan | What this game is, before kick-off |
| Project | A season | A long-arc commitment; multiple matches, one trajectory |
| Decision queue | Tactical decisions during play | Open calls waiting on real-time state |

## Rhythms (how time and pace work)

| Concept | Sport term | Use when |
|---|---|---|
| AWE (token effort) | Minutes on the pitch + energy spent | The cost extracted from the squad |
| Session | A match | One bounded contest |
| Session-open | Pre-match warm-up + team talk | Last reads before kick-off |
| Session-close | Final whistle + cool-down + debrief | The match ends; state persists into the next |
| Calibration cycle | Mid-season review | Step back, audit form across multiple matches |
| Coaching pass | One-on-one with the position coach | Targeted feedback on one player, not the team talk |
| Drift | Tactical drift across matches | The system being played isn't the system on the whiteboard |
| Cross-triage | Pundit / opposition scout's view | Outside eyes on the team's shape |

## Verbs (what people do)

| Concept | Sport term | Use when |
|---|---|---|
| Recommend | Make the pass / call the play | Put the move on |
| Veto | "No, hold position" | Don't make that move |
| Defer | "Wait for the run" | Hold; the right window hasn't opened |
| Approve | "Go!" | Green-light the move |
| Calibrate | Tactical adjustment at halftime | Adjust the shape based on what's happening |
| Iterate | Try a different formation | Same opponent, new system |
| Build (new expert) | Bring on a new player | Sub in / sign in the transfer window |
| Retire | Drop / transfer out | Off the squad; that role passes to someone else |
| Adversarial pass | Tactical analysis session | Bring in someone outside the dressing room |
| Stance protocol | Attack / defend / control | Three modes every passage of play falls into |

## Freeform mappings

- **The pitch** — the live arena. Everything in the analysis room is dress rehearsal until play starts here.
- **The bench** — your reserves; not in play but available. Maps onto sub-agents kept warm.
- **The dressing room** — internal space, not for spectators. The pre-match team-talk and the post-match honesty both live here.
- **Set pieces** — pre-built routines that fire on a known trigger (corners, free-kicks). Maps onto skills and hooks; the team rehearsed them precisely so they don't have to think when the trigger comes.
- **The transfer window** — limited time to reshape the squad. Outside the window, you play with what you've got.
- **The captain's armband** — pinned authority on the pitch. The manager still owns tactics; the captain owns moments.
- **The video room** — post-match adversarial review. Where the team gets honest about what actually happened.
- **The training ground** — where new patterns get rehearsed before they reach the pitch. Stuff that fails here is cheap; stuff that fails on the pitch is not.
- **Marking** — assigned responsibility for a specific risk (one player, one zone, one threat). Maps onto trigger-guards and ownership.
- **Off the ball** — what's happening when the action's elsewhere. Often where the real work is — the runs that create space, the cover that doesn't need to be used.
- **The bench-clear moment** — the formation collapses, everyone reacts; rare, costly, mostly a sign of upstream failure.

## When this analogy doesn't fit

- **Long-cycle structural decisions.** Use construction. Sport is sessional, not durable.
- **Aesthetic / craft work.** Use cooking. Sport is procedural and adversarial.
- **Solo / sequential tasks.** Sport assumes a team and concurrent play.
- **Collaborative, exploratory, non-zero-sum work.** Sport imports win/lose framing that will distort the call. This is a §12 value-alignment failure, not a structural one.
- **Reflective / slow work.** Sport runs at match-pace. Reaching for it can over-accelerate decisions that warrant pause.
