# cooking — domain pack

> The kitchen brigade is hierarchical, time-bound, and unambiguous about who owns which station. That maps cleanly onto how an AI coding session actually runs.

---

## Roles (who does what)

| Concept | Cooking term | Use when |
|---|---|---|
| User | Chef / chef de cuisine | The decision-maker walking the pass; signs off plates |
| Expert (any tier) | Chef de partie / line cook | Owns a station; runs that station; doesn't reach across |
| Meta-expert | Sous chef / kitchen designer | Designs the brigade; doesn't cook in service |
| Adversarial reviewer | A real critic at the table | Catches what the kitchen missed; not malicious, just precise |
| Subagent | Commis / prep cook | Does the prep work; doesn't plate |
| Domain expert | Sommelier / pastry chef / butcher | Specialist station; called for one thing only |
| Sub-expert pair | Craft pair (head pastry + pastry-coach) | Two voices on the same station, deliberately differing on one axis |

## Gear (the tools and objects)

| Concept | Cooking term | Use when |
|---|---|---|
| Persona file | The job description posted at the station | What this cook is supposed to do, written down |
| Calibration card | Plating standard / portion control sheet | The reference picture for "this is how this dish leaves" |
| Instinct file | The cook's own muscle memory | What fires automatically before conscious thought |
| Notepad / reflex bank | Pre-service briefing card on the wall | Reminders the cook glances at mid-shift |
| Working memory (post-/dream) | Wall cards by the pass | The vivid lessons from last service the cook keeps in eyeline |
| Hook | Service bell / chit printer | Fires automatically when X happens |
| MCP server | The pantry / walk-in / supplier delivery | Where the cook gets the ingredients from |
| Knowledge pack | A cookbook / station playbook | Recipes for one section, written down, version-controlled |
| Skill | A technique / trick of the trade | Knife skills, deglazing, mounting butter — portable across stations |
| Brief | The tasting card / event spec | What this dinner is, before the kitchen starts cooking |
| Project | A menu / a service | The whole offering; lives or dies as a unit |
| Decision queue | The ticket rail | Tickets in order, fire when called |
| Inner voice channel | What the cook mutters under their breath | Self-talk that prevents mistakes |
| Voice marker (🟢/⚪) | "I'm on this" vs "ask the pastry section" | Who's actually firing right now |

## Rhythms (how time and pace work)

| Concept | Cooking term | Use when |
|---|---|---|
| AWE (token effort) | Mise en place + line minutes | The actual cost of doing the thing |
| Session | A service / a shift | One bounded run of the kitchen |
| Session-open | Pre-service briefing | Last reads before the doors open |
| Session-close | Breakdown / cleanup | Mark the dish off the menu, restock, write notes for next service |
| Calibration cycle | Quarterly menu review | Step back, look at what shipped, recalibrate |
| Coaching pass | One-on-one with the sous | Targeted feedback, not the briefing |
| Drift | Recipe creep over many services | What ships now isn't what the spec says |
| Cross-triage | Audit by another head chef | Outside eyes on the station |

## Verbs (what people do)

| Concept | Cooking term | Use when |
|---|---|---|
| Recommend | Plate the dish | Send it to the pass |
| Veto | Send it back | "Refire" or "86 the recommendation" |
| Defer | Hold in the warmer | "We'll come back to this dish when the chef walks through" |
| Approve | Call away | "Go" — the dish leaves |
| Calibrate | Re-taste / re-portion | Adjust the salt, adjust the plate, adjust the timing |
| Iterate | Refire | Cook the same dish again, fix what broke |
| Build (new expert) | Open a new station | Mise en place, hire the cook, write the spec |
| Retire (an expert) | Close a station | Off the menu; the line closes that section |
| Adversarial pass | Run the dish past a critic | Find what the kitchen normalised |
| Stance protocol (Baseline / Creative / Risk) | House recipe / specials board / allergen check | Three different surfaces every plate touches |

## Freeform mappings

- **The pass** — the surface where the user sees the answer. Everything has to cross it. The pass is the chat window.
- **Mise en place** — what's prepped and ready before the answer fires. Tool results, file reads, MCP queries. If mise is bad, service is bad.
- **The walk-in** — your MCP store. Pulled from at the start of service; not a real-time fridge.
- **The chit printer** — the hooks. Tickets fire automatically; cook responds.
- **The dish coming back** — drift signal, plate returned by guest, "this isn't what I ordered."
- **The crowded warming drawer** — open questions / pending DQs that nobody walked past to call.
- **86'd** — retired, killed, off the menu.
- **All-day** — the running total of orders for a single dish across the service. Maps onto cumulative AWE on a workstream.
- **Family meal** — what the kitchen eats before service. Internal-only output; not for guests.
- **Fire** — start cooking the dish (start executing the recommendation).
- **Hold** — wait, don't fire yet (defer).
- **Walking the pass** — the user reading through the answer.

## When the analogy doesn't fit

- Pure infrastructure (port numbers, file paths, env vars): no analogy. Plumbing isn't cooking.
- Single-fact lookups: don't reach for the rack.
- Low-stakes responses: padding ruins the signal — leave the rack on the shelf.
