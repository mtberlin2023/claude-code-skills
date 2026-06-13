# cooking — domain pack

> Cooking runs in two registers. The **restaurant brigade** is hierarchical, time-bound, and unambiguous about who owns which station — reach for it when the point is coordination under the clock. **Home cooking** is one person deciding for themselves: the recipe card in the drawer, the everyday version, the leftovers in the fridge — reach for it when the point is a single judgment or something that quietly accumulates. Both map onto how an AI coding session runs; offer both and let the concept pick.

---

## Register axis

This pack carries two registers. Offer both — the model picks the right one per concept *when both are on the table* (validated on the SCP control-panel example, where one response drew brigade for a handoff and home for a single judgment without the two bleeding together).

| Register | Feel | Reach for it when the concept is about… |
|---|---|---|
| **Brigade / restaurant** (subsystem) | a professional service under the clock, many cooks in parallel | hierarchy, handoff, time-pressure, who-owns-which-station, parallel work |
| **Home / everyday** (universe) | one cook deciding for themselves, the same meal on repeat | a single person's judgment, everyday repetition, leftovers, the card you keep, the cheap-and-cheerful version |

**Selection cue:** *subsystem when the point is coordination; home when the point is one judgment or something that accumulates.* When in doubt offer both terms and let the sentence pick — but never mix the two in one breath (no "the sous chef checks the leftovers").

---

## Roles (who does what)

| Concept | Brigade / restaurant | Home / everyday | Reach for… |
|---|---|---|---|
| User | Chef de cuisine — walks the pass, signs off plates | The person cooking dinner — has to actually eat it | brigade for sign-off + hierarchy; home for "lives with the result" |
| Expert (any tier) | Chef de partie / line cook — owns a station, doesn't reach across | The friend who's just better at one dish — called for that one thing | brigade when stations matter; home for one-off specialist help |
| Meta-expert | Sous chef / kitchen designer — designs the brigade, doesn't cook in service | Whoever taught you to cook — set your habits, isn't at the stove now | brigade for structure; home for inherited instinct |
| Adversarial reviewer | A critic at the table — precise, not malicious | A blunt friend who says "this is too salty" | brigade for formal review; home for an honest gut check |
| Subagent | Commis / prep cook — does the prep, doesn't plate | Kids chopping veg — one task, supervised | brigade in service; home for a delegated chore |
| Domain expert | Sommelier / pastry chef / butcher — one station only | The neighbour who actually knows bread | brigade for a named station; home for borrowed know-how |
| Sub-expert pair | Craft pair (head pastry + pastry-coach), differing on one axis | Two cooks arguing over the same recipe | either — two voices on one thing, deliberately differing |

## Gear (the tools and objects)

| Concept | Brigade / restaurant | Home / everyday | Reach for… |
|---|---|---|---|
| Persona file | The job description posted at the station | The note on the fridge: "you're on veg duty" | brigade for a formal role; home for ad-hoc |
| Calibration card | Plating standard / portion-control sheet | The recipe card you actually follow, splatters and all | brigade for a house standard; home for a kept reference |
| Instinct file | The cook's own muscle memory | Knowing the pasta's done without looking at a timer | either — what fires before conscious thought |
| Notepad / reflex bank | Pre-service briefing card on the wall | The shopping list stuck to the fridge | brigade mid-shift; home for everyday reminders |
| Working memory (post-/dream) | Wall cards by the pass | "We burned it last time — watch the heat" | brigade for service lessons; home for kitchen history |
| Hook | Service bell / chit printer | The oven timer going off | brigade for ticket-driven firing; home for one trigger |
| MCP server | The walk-in / supplier delivery | The pantry / store cupboard | brigade for the supply chain; home for what's already in |
| Knowledge pack | A station playbook | The family recipe book | brigade for a section's procedure; home for how-we-do-it |
| Skill | A technique (deglazing, mounting butter) | Knowing how to make a roux | either — portable across stations / kitchens |
| Brief | The tasting card / event spec | "We've got people coming over" | brigade for a service spec; home for an everyday plan |
| Project | A menu / a service | Dinner | brigade for the whole offering; home for one meal |
| Decision queue | The ticket rail | The meal plan stuck on the counter | brigade for fire-when-called; home for a backlog |
| Inner voice channel | What the cook mutters at the pass | Talking yourself through a tricky recipe | either — self-talk that prevents mistakes |
| Voice marker (🟢/⚪) | "I'm on this" vs "ask pastry" | "I've got dinner" vs "you sort it" | either — who's actually firing right now |

## Rhythms (how time and pace work)

| Concept | Brigade / restaurant | Home / everyday | Reach for… |
|---|---|---|---|
| AWE (token effort) | Mise en place + line minutes | The shop, the prep, and the washing-up | either — the real cost of doing the thing |
| Session | A service / a shift | Cooking one meal start to finish | brigade for a bounded team run; home for one sitting |
| Session-open | Pre-service briefing | Checking what's in the fridge before you start | brigade for the team brief; home for the solo check |
| Session-close | Breakdown / cleanup | Doing the dishes, putting the leftovers away | either — tidy, restock, note for next time |
| Calibration cycle | Quarterly menu review | "We eat too much pasta — let's rethink" | brigade for a menu rethink; home for a habit review |
| Coaching pass | One-on-one with the sous | Showing someone how you do it | brigade for targeted feedback; home for teaching |
| Drift | Recipe creep over many services | The recipe you've slowly changed until it's not Grandma's any more | brigade for spec deviation; home for habit drift |
| Cross-triage | Audit by another head chef | "Try this — does it taste off to you?" | brigade for a formal outside read; home for a second tongue |

## Verbs (what people do)

| Concept | Brigade / restaurant | Home / everyday | Reach for… |
|---|---|---|---|
| Recommend | Plate it / send it to the pass | "Shall we have this?" | brigade for sending it; home for suggesting it |
| Veto | Send it back / 86 it | "Not making that again" | brigade for a refire; home for a hard no |
| Defer | Hold it in the warmer | "Let's save it for later" | either — wait, don't fire yet |
| Approve | Call away — "Go" | "Yeah, let's do it" | brigade for the green light; home for a casual yes |
| Calibrate | Re-taste / re-portion | Adjust the seasoning to taste | either — adjust the salt, the plate, the timing |
| Iterate | Refire | Make it again, fix what was off | either — same dish, fix what broke |
| Build (new expert) | Open a new station | Learn a new dish | brigade for a new section; home for a new skill |
| Retire (an expert) | Close a station — off the menu | Stop making a dish | brigade for closing a line; home for dropping a regular |
| Adversarial pass | Run it past a critic | Cook it for your harshest friend | brigade for a formal critic; home for a blunt taster |
| Stance protocol (Baseline / Creative / Risk) | House recipe / specials board / allergen check | "The usual / something new / is it safe to eat?" | either — three surfaces every plate touches |

## Freeform mappings

**Brigade / restaurant** (coordination under the clock):

- **The pass** — the surface where the user sees the answer. Everything has to cross it. The pass is the chat window.
- **Mise en place** — what's prepped before the answer fires: tool results, file reads, MCP queries. Bad mise, bad service.
- **The walk-in** — your MCP store. Pulled from at the start of service; not a real-time fridge.
- **The chit printer** — the hooks. Tickets fire automatically; the cook responds.
- **The dish coming back** — drift signal, plate returned by guest, "this isn't what I ordered."
- **The crowded warming drawer** — open questions / pending DQs that nobody walked past to call.
- **86'd** — retired, killed, off the menu.
- **All-day** — the running total of one dish across the service. Maps onto cumulative AWE on a workstream.
- **Family meal** — what the kitchen eats before service. Internal-only output; not for guests.
- **Fire** / **Hold** — start cooking now / wait, don't fire yet.
- **Walking the pass** — the user reading through the answer.

**Home / everyday** (one cook, repetition, accumulation):

- **Leftovers** — reaching for what you already made instead of cooking fresh. Reusing a cached result or a prior artefact.
- **The recipe card in the drawer** — the kept reference you actually follow, not the pristine spec. The lived-in calibration card.
- **The everyday version** — the no-fuss cut of a dish, when the full brigade is overkill. The throwaway-POC path.
- **Cook once, eat twice** — do the prep once and reuse it across meals. Building a reusable skill or pack instead of re-cooking each time.
- **Eyeballing it / tasting as you go** — cooking by judgment instead of measuring; continuous calibration mid-cook, not just a check at the pass.
- **Using up what's in the fridge** — constraint-driven cooking: work with what you actually have, not an ideal shop. Working within the tools and context already loaded.

## When the analogy doesn't fit

- Pure infrastructure (port numbers, file paths, env vars): no analogy. Plumbing isn't cooking.
- Single-fact lookups: don't reach for the rack.
- Low-stakes responses: padding ruins the signal — leave the rack on the shelf.
- **Don't mix the two registers in one breath.** Brigade *or* home per concept, never "the sous chef checks the leftovers." Offer both in the pack; pick one in the sentence.
