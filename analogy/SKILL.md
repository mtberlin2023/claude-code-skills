---
name: analogy
description: Reframe options, decisions, or non-trivial reasoning using a domain analogy (cooking default; construction / environment / home / travel / sport / pluggable). Lives alongside the technical answer, never instead of it. Output ships six elements per §15A and the §15A.1 defences of the Analogy Layer paper (Turrell 2026): summary, mapping table, simulation prompt, limit statement, user-profile mislead tag, separate second-opinion pass.
version: 1.1
default_domain: cooking
available_domains: [cooking, construction, environment, home, travel, sport]
---

# Analogy — Spice Rack on the Pass

A skill that consults the active domain pack when answering with options, tradeoffs, or non-trivial reasoning, and drops a four-component analogy reframe alongside the technical answer.

This is the reference implementation of the *Analogy Layer* model: the output is structured so the user can mentally simulate the answer, not just read it. The four components below correspond directly to §15 of the paper.

## When this fires

- Any answer that includes **options** (≥2 numbered choices, A/B/C, three paths, etc.)
- Any answer with a **tradeoff call** ("X risks Y, but…")
- Any **architectural / non-trivial-reasoning** explanation (covers >1 conceptual layer)
- Any **redesign / fresh-reasoning** moment

## When this does NOT fire

- Quick lookups (file paths, port numbers, single-fact answers)
- Status reports, progress updates, log confirmations
- Single-sentence answers, pure tool-result reporting
- Anything where the technical answer is already short and self-evident

## How to use

1. **Read the active domain pack** at `domains/<active>.md` (default: `cooking`).
2. **Pick the right domain.** Default holds for most work. Override structurally — not for novelty — when the problem has features the default pack doesn't carry:
   - Layered roles + persistent obligations over time → `construction`
   - Cumulative budget / household-economics decisions → `home`
   - Permissions, sequencing, graceful failure under load → `travel` (airport sub-domain)
   - Team coordination, role specialisation, shared state → `sport`
   - When switching, say *why* in one line so the user can veto: "switching to construction because cooking won't carry the multi-party time-bound structure."
3. **Map the technical concept** to the closest term in the pack.
4. **Place the analogy alongside the technical answer**, never instead of it. Technical recommendation lands first; analogy reframes second.
5. **Don't manufacture analogies.** If nothing maps cleanly: *"no clean <domain> analogy fires here."* Empty is signal; padding fails.
6. **Log the invocation** (when audit is on): append a one-line record to `audit/decisions.jsonl` — see `audit/README.md`.

## Output shapes

**Shape A — full six-element reframe (default for substantive answers):**

Five elements ship in the main rendering; the sixth is a separate pass rendered alongside. All six count toward `components` in the audit log. See the False-confidence defences section below for the rendering rules.

> *In kitchen terms:* one or two sentences establishing the parallel rendering.
>
> | Technical | Kitchen | What this means |
> |---|---|---|
> | <concept 1> | <pack term> | <one-line gloss> |
> | <concept 2> | <pack term> | <one-line gloss> |
>
> **Run it forward —** one or two simulation questions the user can answer against the analogy: *"What happens if the kitchen is short-staffed?" "Which station fails first under load?"*
>
> **Where this analogy stops —** one short line on the edge of the mapping, rendered at the **same visual weight as the mapping table** (not a footer, hover-tip, or fine print): *"This frame doesn't carry [X]; for that, look at [substrate / a different pack]."*
>
> **Where this would mislead a user like you —** one short line specific to the user's operative-familiarity profile, generated from user-model state (which packs they've locked, which substrate concepts they have hands-on experience of, which classes of flag they've raised before). Boilerplate is a failure of this element. Shape example: *"Because you've never worked with [substrate concept], the analogy makes [Y] feel like a checklist item, but in practice it operates as a gating decision."*

**Separate pass rendered alongside, not folded in — second-opinion check:** one short paragraph addressing *"Where might this analogy mislead? What structural feature of the target does the rendering under-represent? What failure mode would not be visible from inside the analogy?"* A different prompt against the same model, post-rendering. Appears below the main reframe, never inline.

**Shape B — inline option tags (for option tables, when full Shape A is too heavy):**
> Option 1 — *house recipe* | Option 2 — *specials board* | Option 3 — *new menu*

**Shape C — full reframe (when explicitly asked):**
> "Explain my options using cooking as an analogy" → render every option end-to-end inside the analogy. Still include the *Where this analogy stops* line.

## False-confidence defences (§15A.1)

Class 3 — false-confident — is the most dangerous failure of the layer: the simulation feels coherent, the decision is made with confidence, and the substrate behaves in ways the analogy did not predict. By definition the user cannot flag this mid-stream — the symptom is the user *feeling* the analogy worked. The output spec carries three structural defences to close the gap as far as system-side design can. Two are visible elements folded into Shape A above; the third is a separate pass rendered alongside.

1. **Limit statement at equal prominence.** The "Where this analogy stops" line ships at the same visual weight as the mapping table — never as a footer, hover-tip, or fine print. A warning at lower prominence than the analogy gets skipped past; one at equal prominence gets read. This is a UX rule, not a content rule.

2. **"Would mislead a user like you" tag.** A user-profile-specific line, generated from user-model state — not a generic disclaimer. The element most likely to make the user pause before acting on a confidently-rendered analogy that maps onto exactly the dimension of the substrate the user has the least operative experience of.

3. **Second-opinion pass.** A separate post-output check — different prompt against the same model — asking what the rendering under-represents and what failure modes are invisible from inside the analogy. Rendered below the main reframe, never inline.

None of these is complete. Class 3 will still occur. The point is to leave the named-but-undefended state v1.0 was in. Audit metrics tracked: `components.mislead_tag` and `components.second_opinion_pass` (the `limit_statement` boolean existed in v1.0 — what is new in v1.1 is the equal-prominence rendering rule, which is a Shape A property not a separate boolean).

## Feedback verbs

Six user-callable verbs the user can call mid-answer; the skill responds in-line. Each maps to one class in the seven-class signal taxonomy. **Class 3 — false-confident — is post-hoc only and not user-callable mid-stream**, because by definition its symptom is the user *feeling* the simulation was coherent; it is labelled retrospectively in `outcome_label`.

- **`flag unfamiliar`** *(class 1 — didn't clarify)* — current pack did not connect to the user's operative experience. System response: offer to render in a different pack. Different from *misleading*: unfamiliar means **opaque**, not **wrong**. Logged.
- **`flag misleading`** *(class 2 — pointed at the wrong inference)* — the rendering connected, but pointed the user at the wrong decision. Either the structural mapping was off or the limit statement was buried. System response: re-render with a stronger limit statement, or switch pack. Logged.
- **`flag bleed`** *(class 4 — substrate bleed)* — the analogy and the technical content got inline-mixed in the same sentence, so neither read cleanly. System response: re-render with separated blocks (analogy block, then substrate block, never interleaved). Logged.
- **`drop analogy`** *(class 5 — analogy capture)* — the layer fired where no analogy was needed (lookup, status report, single-fact answer). System response: drop the rendering on the current turn and raise the trigger threshold locally for this user. Logged.
- **`redo with <domain>`** or **`redo at <scale>`** *(class 6 — sub-mode / scale mismatch)* — right go-to, wrong pack or wrong scale (single-restaurant vs restaurant-group vs supply-chain). System response: re-render in the named pack or at the named scale. Logged.
- **`lock this`** *(class 7 — worked, reusable)* — the rendering succeeded and should be reused on similar substrates. System response: append to `audit/locks.jsonl` with a problem signature so the skill can suggest the same pack on similar future problems. Logged.

**Class 3 — false-confident (post-hoc only).** The user felt the simulation was coherent, the decision was made with confidence, and the actual system behaved in ways the analogy did not predict. Labelled retrospectively as `outcome_label: false_confident` on the audit record, ideally surfaced by the false-confidence defence pass specified in the paper (§15A.1) or by a later review. The defences in the output spec — a second-opinion pass, an equal-prominence limit statement, and a *"would mislead a user like you"* tag — exist specifically because this class cannot be flagged mid-stream.

## Switching the active domain

Set `default_domain` in this file's frontmatter, OR pass an inline override: *"use sailing as the analogy for this one."* Pack-not-found falls back to cooking.

## Adding a domain

Drop a new file at `domains/<name>.md` matching the contract in `domains/_template.md`. The pack must cover at minimum: roles (who does what), gear (the tools/objects), rhythms (how time / pace works), verbs (what people do), and a *When this analogy doesn't fit* section. Below that, free-form mappings welcome.

A pack is worth adding when it passes the §12 criteria from the paper: operative familiarity, structural richness, extensibility across scales, bounded mapping, value alignment, consistency potential.

## Audit / measurement

See `audit/README.md`. The skill is instrumented so that invocations can be reviewed for whether the layer actually changed the decision (paper §16). A v1.0 deployment without audit is a 3-component skill in 4-component clothing.

## Worked examples

See `WORKED_EXAMPLES.md` for three before/after fixtures: the kitchen sub-agent case (§8), the ESG-construction case (§9b), and the subscription audit (§10). Each shows the same decision rendered without the analogy layer and with it, with the four components surfaced explicitly.
