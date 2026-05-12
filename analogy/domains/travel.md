# travel — domain pack

> Travel — specifically the airport sub-domain — is built around permissions, sequencing, queues, and graceful failure under load. Per §12, travel as a whole is too fragmented to be a primary frame (one person's holiday is another's logistical chore), but the airport slice carries a structural shape that maps cleanly onto permissions / authorisation / sequencing problems and onto pipelines that have to fail gracefully.

---

## Roles (who does what)

| Concept | Travel term | Use when |
|---|---|---|
| Principal | The traveller | The one whose journey it is; holds the ticket and the consequences |
| Expert (any tier) | A gatekeeper at one checkpoint (gate agent, immigration officer, check-in) | Owns one stage; can stop you, can't see the rest of the journey |
| Meta-expert | Travel planner / corporate-travel desk | Designs the itinerary; doesn't show up at the gate |
| Adversarial reviewer | Security / customs officer | Catches what the check-in waved through |
| Subagent (Haiku/Sonnet) | Bag handler / driver / porter | Moves things; doesn't decide where they go |
| Domain expert | Visa specialist / immigration lawyer | One narrow rules question, deep expertise |
| Sub-expert pair | Codeshare partners / two airlines on a connection | Two parties responsible for adjacent legs of the same journey |

## Gear (the tools and objects)

| Concept | Travel term | Use when |
|---|---|---|
| Persona file | Passport / boarding pass / loyalty profile | Who you are, certified, at each checkpoint |
| Calibration card | Visa rules / fare conditions | The reference the checkpoint actually checks against |
| Instinct file | "How I travel" — packing habits, queue choices | What fires automatically without conscious thought |
| Notepad / reflex bank | The itinerary in your pocket | Reminders that catch you between legs |
| Working memory (post-/dream) | Frequent-flyer history; remembered shortcuts | What you bring forward from previous trips |
| Hook (Claude Code) | Boarding call / gate change announcement / TSA Pre-check lane | Fires automatically on a known trigger |
| MCP server | The duty-free shop / lounge / departures board | A pulled-from resource, not a real-time feed |
| Knowledge pack | Country-specific entry rules / airline policy doc | Written procedure for one class of crossing |
| Skill | Packing strategy, hand-luggage discipline, language phrases | Portable across destinations |
| Brief | The trip purpose | What this journey is for, before booking |
| Project | The whole journey (multi-leg) | Lives or dies as a unit; one missed connection breaks the chain |
| Decision queue | Connection windows + standby positions | Open decisions waiting on real-time signal |

## Rhythms (how time and pace work)

| Concept | Travel term | Use when |
|---|---|---|
| AWE (token effort) | Time + cash + jet lag | The actual cost the journey extracts |
| Session | A flight segment | One bounded leg |
| Session-open | Check-in + security | Last reads before you commit to the leg |
| Session-close | Customs clearance / hotel check-in | The leg completes, state persists into the next |
| Calibration cycle | Loyalty-tier review / annual passport check | Step back and audit the standing permissions |
| Coaching pass | A friend's "you should always do X when flying Y" | Targeted travel-craft transfer |
| Drift | Itinerary creep / fare class downgrade | The journey on paper isn't the journey at the gate |
| Cross-triage | Asking the gate agent "should I rebook?" | Outside eyes on the active plan |

## Verbs (what people do)

| Concept | Travel term | Use when |
|---|---|---|
| Recommend | Book the flight | Put the option on the itinerary |
| Veto | Refuse boarding / deny entry | The checkpoint stops you |
| Defer | Standby / waitlist | Held, not approved, position pending |
| Approve | Cleared / stamped through | Permission granted, next leg unlocked |
| Calibrate | Re-route / rebook | Adjust the plan to what's actually possible |
| Iterate | Try a different airline / fare class | Same destination, new path |
| Build (new expert) | Add a leg / extend the trip | New stage in the journey |
| Retire | Cancel the booking | Off the itinerary |
| Adversarial pass | Customs interview / secondary screening | Pulled aside for closer inspection |
| Stance protocol | On-time / cost / comfort | Three lenses every booking gets checked under |

## Freeform mappings

- **The gate** — where the next decision fires. Everything before it is preparation; everything after it is consequence.
- **The connection** — the most fragile bit. One delay cascades into a re-plan.
- **Standby** — held but not approved. The permission you might get if conditions clear.
- **TSA Pre-check / Global Entry** — stored permissions. The speed-pass past the recurring check, *because the check already happened once*.
- **The gate change** — late-breaking drift signal. Plan was good at booking, no longer holds at boarding.
- **The layover** — built-in slack for graceful failure. Tight connection = no slack = fragile.
- **Lost baggage** — silent failure, recovered after the fact. The pipeline kept going without it.
- **Re-routing** — rebuilding the plan mid-journey when the original breaks.
- **Overhead bin space** — a limited shared resource, first-come, first-served, with consequences for late arrivals.
- **The boarding sequence** — strict ordering with consequences if you miss your slot.
- **The transit lounge** — held in-between state; not in the source country, not in the destination, governed by neither.
- **The visa stamp** — durable permission with an expiry. Different from the boarding pass (single-use).

## When this analogy doesn't fit

- **Long-term ownership / contractual problems.** Use construction. Travel is transactional.
- **Aesthetic / craft / brand work.** Use cooking. Travel is procedural.
- **Day-to-day household ops.** Use home. Travel is episodic; home is continuous.
- **Adversarial-only frames.** Travel imports authority-relations (gates, officers) that can over-formalise collaborative work.
