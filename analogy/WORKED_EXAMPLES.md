# Worked Examples

Three before/after fixtures that show the analogy layer doing the work it claims to do. Drawn directly from the paper's case studies — Sections 8, 9b, and 10 — rendered here as paired examples so a reader (and the `audit/check.py` rollup) can see the difference.

**How to read these.** Each example shows the **same decision twice**: once as a typical AI answer (Shape 0, no layer), once with the four-component layer applied (Shape A, with `summary` / `mapping table` / `simulation prompt` / `limit statement`). What changed is named explicitly at the bottom of each.

---

## Example 1 — Kitchen sub-agent (paper §8, real)

**Context.** Building a system of specialised AI experts orchestrated as sub-agents (Claude Code, Codex, or any equivalent agent framework). The experts kept losing track of project context mid-task. The user asked the AI: how do I fix this?

### BEFORE — no analogy layer

> Three approaches commonly fix expert-drift problems in agent systems:
>
> 1. **Retrain the underlying expert briefings** — enrich each expert's persona file with more project context, more examples, and tighter scope language. This is the "fix it at the source" approach.
> 2. **Front-load context per invocation** — pin the relevant project state to the front of every expert prompt at runtime, so the expert always opens with current state regardless of what it remembered.
> 3. **Add a guardrail / verification layer** — a meta-agent that watches each expert's output, flags drift, and either re-prompts or corrects in place.
>
> Each has trade-offs around maintenance burden, latency, and how invasive the change is. Option 2 is generally the cheapest to implement.

*The user picks option 2.*

### AFTER — analogy layer applied (pack: `cooking`)

> Three approaches commonly fix this:
>
> 1. **Retrain the underlying expert briefings** — enrich each persona with more context, examples, tighter scope.
> 2. **Front-load context per invocation** — pin the relevant project state to the front of every expert prompt at runtime.
> 3. **Add a guardrail / verification layer** — a meta-agent that watches output, flags drift, and corrects.
>
> *In kitchen terms:* the three options are *send the chefs on a training course*, *pin the day's instructions on the kitchen door*, and *hire a manager to keep the chefs on task*.
>
> | Technical | Kitchen | What this means |
> |---|---|---|
> | Retrain briefings | Training course | Expensive, slow, fundamental; right when the underlying skill is wrong |
> | Front-load context | Pinned door instructions | Cheap, immediate; easily ignored under pressure |
> | Guardrail layer | Hire a manager | Adds a role and overhead; only worth it if the kitchen can't self-correct |
>
> **Run it forward —** what's the problem the chefs are actually having? Is the recipe ambiguous? Are the orders arriving in a form that's hard to act on? Are the right ingredients out of reach? If the answer is any of those, all three options above are about *disciplining staff for a structural failure* — none of them touch the real cause.
>
> **Where this analogy stops —** kitchens have one head chef per shift; sub-agent systems can have multiple coordinated controllers. The "one boss" frame doesn't generalise; ignore it past this decision.

*The user reads the simulation question, recognises that all three options share an assumption (the experts are the right unit of organisation; discipline is the answer), and pauses the decision. Comes back later with a different framing: change how context flows through the system, not how the experts are policed.*

### Delta

- **Frame rejection** — yes. This is the canonical case. The simulation question made the shared assumption visible.
- **Decision class** — `build`
- **Outcome label** — `quality` (the eventual decision was different and demonstrably better, judged retrospectively against what option 2 would have produced).
- **Components shipped** — 4 of 4.

---

## Example 2 — ESG instrument explanation (paper §9b, real)

**Context.** Writing a chapter on sustainability-linked finance for a mixed audience (finance professionals + general business readers). Needs to explain what a *sustainability-linked loan* is and why it exists, without losing non-finance readers in the substrate.

### BEFORE — no analogy layer

> A sustainability-linked loan (SLL) is a corporate loan whose financial terms — typically the interest margin — adjust based on the borrower's performance against pre-defined sustainability performance targets (SPTs). The targets are linked to KPIs that are material to the borrower's business (e.g. emissions intensity, water consumption, board diversity). Independent verification of KPI performance is required at each review date. SLLs are general-purpose-of-proceeds instruments, distinguishing them from use-of-proceeds instruments like green bonds.

*The reader who works in finance follows this. The reader who doesn't has bounced.*

### AFTER — analogy layer applied (pack: `construction`)

> A sustainability-linked loan is a corporate loan whose interest rate moves up or down depending on whether the borrower hits agreed sustainability targets — emissions, water, board diversity, whatever's material to them.
>
> *In construction terms:* a developer building a hotel agrees the rent steps down if the building hits its energy-efficiency targets, and steps up if it misses them. The lender is taking a position on operational performance, not just on whether the building gets built.
>
> | Technical | Construction | What this means |
> |---|---|---|
> | Sustainability performance target | Energy-efficiency clause in the lease | A measurable promise about how the asset will run |
> | Margin step-up / step-down | Rent goes up or down | The lender shares in the upside if targets are hit, suffers if missed |
> | Verification at review date | Inspector visits the building | Outside eyes confirm the claim before the financial change applies |
> | General-purpose-of-proceeds | The loan funds whatever the developer needs | Unlike a green bond, which has to fund verified-green works only |
>
> **Run it forward —** what happens if the building underperforms in the third review cycle but the market for hotels has shifted in a way nobody foresaw? Who eats the difference — the developer (who built honestly), or the lender (who priced the risk in)? Real SLLs have answered this question in their contracts; the answer shapes whether the instrument is a sharp tool or a blunt one.
>
> **Where this analogy stops —** a real building has physical inspection and depreciation curves; an SLL's targets are usually accounting-based and forward-looking. Don't push the metaphor into balance-sheet treatment or impairment.

*The non-finance reader now has a structural picture of why this instrument exists. The finance reader's eyes don't glaze over because the technical content is still right there.*

### Delta

- **Frame rejection** — no, but not the goal here. This is delegation-analogy on the production side (paper §9b).
- **Decision class** — `explanation`
- **Outcome label** — `quality` (the reader can ask a better next question — "who eats the variance?" — which is the right next question whether they read it in the analogy or in the substrate).
- **Components shipped** — 4 of 4.

---

## Example 3 — Subscription audit (paper §10, constructed but representative)

**Context.** A knowledge worker, deep into the current generation of AI tools, with seven or eight subscriptions accumulated. None individually expensive; collectively significant. Nobody has audited the whole. The user asks the AI: should I keep these?

### BEFORE — no analogy layer

> Based on usage frequency and overlap, the following recommendations:
>
> | Tool | Plan | Use/mo | Cost-per-use | Recommendation |
> |---|---|---|---|---|
> | ChatGPT Plus | $20/mo | 80+ | low | keep |
> | Perplexity Pro | $20/mo | 15 | high | consider cancelling |
> | Midjourney | $30/mo | 4 | very high | cancel |
> | DALL-E (via Plus) | included | 2 | n/a | already covered |
> | GitHub Copilot | $19/mo | 60+ | low | keep |
> | Otter.ai | $17/mo | 12 | medium | review |
> | Asana AI add-on | $11/mo | 0 (long unused) | infinite | cancel |
> | Fireflies | $19/mo | 10 | medium | review |
>
> Estimated savings: $61/month if you cancel the three flagged tools.

*The user reads the table, doesn't cancel anything, closes the tab.*

### AFTER — analogy layer applied (pack: `cooking`, with `home` as a secondary lens)

> Here's the inventory:
>
> *(same table as above, kept inline so the technical content is still present)*
>
> *In kitchen terms:* this isn't an inventory question, it's a staffing question. You're running a kitchen.
>
> | Tool | Kitchen role | What that role costs you |
> |---|---|---|
> | ChatGPT Plus | Head chef — does most things competently, on the line every service | Indispensable. Justified. |
> | Perplexity Pro | Senior cook hired for one specific cuisine | Useful when you cook that cuisine; expensive when you don't. Are you still cooking it? |
> | Midjourney + DALL-E | Two pastry chefs on the same station | One of them is on the schedule out of habit. The kitchen doesn't need both. |
> | GitHub Copilot | Sous-chef who only works certain dishes but is excellent at them | Indispensable for the dishes they cover. |
> | Otter / Fireflies | Two prep cooks doing slightly different mise en place | They're not redundant *exactly* — they specialise — but the head chef could probably do most of this prep. Worth asking whether you actually need two. |
> | Asana AI add-on | Specialist supplier on retainer for an ingredient you haven't ordered in a long stretch | Cancel. The retainer is paying for nothing. |
>
> **Run it forward —** if you cancel Perplexity (the senior cook), are you actually going to stop cooking that cuisine? Or will you start asking the head chef to do the senior cook's job, and discover after the next billing cycle that the head chef does it badly at scale? That happens with cancellations; it's not always cheaper, just smaller-looking on the bill.
>
> **Where this analogy stops —** real kitchens don't have free trials that quietly convert. The drifting-renewal pathology is more household than kitchen — if that's the shape of the problem, switch packs to `home` and look at the standing-orders list as a budget question.

*The user cancels Asana (clear retainer), keeps Perplexity for another billing cycle and watches whether they actually cook that cuisine, consolidates the prep-cook station by choosing Fireflies over Otter, and leaves the rest alone. The total cut is smaller than the bare table recommended ($30/mo vs $61/mo), but it's intentional rather than mechanical.*

### Delta

- **Frame rejection** — no. The frame held; the simulation just produced more nuanced choices.
- **Decision class** — `audit`
- **Outcome label** — `comfort` — the user engaged with the audit they'd been avoiding, the cost change is modest, the *relationship* to the cost is what shifted.
- **Components shipped** — 4 of 4.

### Footnote — the comfort / quality caveat

This case sits on the comfort side of the comfort/quality split. The paper's central evidence problem is exactly this: a paper making a quality claim that rests on one quality-adjacent case and two comfort-adjacent cases has an evidence gap. Naming it honestly in the audit schema (`outcome_label`) is the point.

The audit log (`audit/decisions.jsonl`) is shaped to surface this question — `outcome_label` is the field that names it. If your real-world use of the skill consistently logs `comfort` and rarely `quality`, that is a finding, not a failure. The paper says so.

---

## How these examples relate to the audit

Each of the three examples maps to a row that could be logged in `audit/decisions.jsonl`:

```jsonl
{"ts": "...", "domain_used": "cooking",      "components": {"summary": true, "mapping_table": true, "simulation_prompt": true, "limit_statement": true}, "frame_rejection": true,  "decision_class": "build",       "outcome_label": "quality"}
{"ts": "...", "domain_used": "construction", "components": {"summary": true, "mapping_table": true, "simulation_prompt": true, "limit_statement": true}, "frame_rejection": false, "decision_class": "explanation", "outcome_label": "quality"}
{"ts": "...", "domain_used": "cooking",      "components": {"summary": true, "mapping_table": true, "simulation_prompt": true, "limit_statement": true}, "frame_rejection": false, "decision_class": "audit",       "outcome_label": "comfort"}
```

Three records, three different `decision_class` values, two different `outcome_label` values, one `frame_rejection`. That is what a healthy log looks like.
