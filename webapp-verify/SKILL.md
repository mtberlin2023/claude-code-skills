---
name: webapp-verify
status: v0.3.1 shipped — journey runner + site health matrix + regression alerts live; v0.3α persona seeding (LLM-framing only) — real cookie/storage seeding deferred to v0.4 per BRIEF-032
substrate: chrome-devtools-mcp (npm, unscoped)
runtime_dep: mcp == 1.27.0 (hash-pinned in install.sh)
parent_brief: _shared/briefs/BRIEF-028-webapp-verify-token-efficient-testing.md
panel_synthesis: _shared/briefs/BRIEF-028-webapp-verify-PANEL-SYNTHESIS.md
---

# webapp-verify

> A subprocess wrapper around Chrome DevTools MCP that drives a live URL via either a deterministic flow script (v1) or an LLM-in-loop journey (v0.3+) and writes verification artefacts to disk. Honesty-first: this tool runs a flow or journey — it does not tell you whether your UX is good.

**Status:** v0.3.1. Two complementary modes ship in this skill:

- **Flow mode (v1):** deterministic scripted steps with a `goal` + `success_state` detector. Refuses to run without both. PASS / FAIL / refuse semantics.
- **Journey mode (v0.3+):** persona + intent + `success` shape (`saw_content` / `clicked_target` / `llm_judged`). Claude Haiku picks each next action from the live a11y tree; per-iteration decisions log to `decisions.jsonl`; PASS / UNCLEAR / FAIL semantics with a patience budget that surfaces real friction signals. Suite mode (`journey-suite <site.yaml>`) runs N journeys against one target; diff mode (`journey-diff <run_a> <run_b>`) is the v1.0 P3 regression-alerts substrate.
- **Reader:** every run dir gets a self-contained `report.html`; the artefacts root grows an `index.html` that surfaces flat runs, suite matrices (journeys × personas), and diff dirs alongside each other.

223 tests green. Single runtime dep: `mcp` Python SDK, hash-pinned. v0.2 line-level Anya pass cleared. Live smoke validated against undavos.com (calibration session 2026-04-25 surfaced four real signals: tooling overhead in patience budgets, brittle literal-string matchers, dead-end scroll loops, and a synthetic `no-contact-reachable` finding for missing reachable contact info).

**Install:** `bash install.sh` from this directory. Verify with `verify.py --check-install`.

---

## Five honesty anti-patterns (product spine)

These are the things this skill will NOT do. If you want any of them, you want a different tool.

### 1. A tool that runs a flow ≠ a tool that verifies UX

`webapp-verify` can click buttons, fill forms, take screenshots, and capture network requests. It cannot tell you whether your interface is confusing, whether your copy is clear, whether your conversion funnel leaks, or whether your users will enjoy the experience. Running a flow to completion is a *precondition* for UX quality. It is not the thing.

If your CI label reads "webapp-verify PASS" and you ship that as a UX claim, you are lying to yourself and your team.

### 2. A flow without a `goal` is a click-sequence — refuse to run

Every flow script MUST declare a `goal` (string) and a `success_state` (detector). Flows missing either are refused at load time, before any MCP call. Rationale: a script that drives a browser without stating what it's trying to achieve is a recording, not a test. Recordings go green when the app has silently broken around them.

This is enforced by the flow-script loader, not by convention. `goal: ""` or a missing field fails with a specific error. There is no `--skip-validation` flag.

### 3. The Pass label refers to the CDP trace, not the UI

When the wrapper reports PASS, it means: the scripted actions completed without the CDP MCP substrate throwing, and the declared `success_state` detector fired. It does NOT mean the UI looked right, that the state persisted, that the network traffic was secure, or that a real user could have done the same thing.

Screenshots are artefacts, not verdicts. A human reviews them. The wrapper does not.

### 4. A skill that ships without its honesty anti-patterns is marketing, not engineering

This section exists because the product spine of this skill is what it refuses to claim. Removing this section converts the skill from an honest tool into a marketing asset. If you are reading a fork of `webapp-verify` without this section, read the original panel synthesis (`BRIEF-028-webapp-verify-PANEL-SYNTHESIS.md`) before trusting it.

### 5. An allowlist without a fixture is a comment, not a security control

This skill's 8-tool allowlist, 14-tool deny-list, 6-parameter emulate gate, and 6-entry refused-server-flag list are each enforced by unit tests (`tests/test_dispatcher_smuggling.py`, 32 shapes at v1). A contributor who drops a tool from `DENYLIST`, adds one to `ALLOWLIST`, loosens a parameter gate, or removes an entry from `REFUSED_SERVER_FLAGS` must extend the fixture in the same commit — a code change without the matching fixture change is refused at review.

Security theatre: "we only allow these tools" in prose.
Security control: `self.assertIn("evaluate_script", DENYLIST)` in a test that runs on every commit.

The difference is whether a typo in the constant name silently disables enforcement. A fixture catches that. A sentence does not.

---

## Universal gap — accessibility-tree shape not yet locked

The `take_snapshot` tool in Chrome DevTools MCP returns accessibility-tree data. The shape of that output is not documented in the published MCP docs as of v0.21.0. This affects:

- `success_state.landmark` detector — implemented v1 as best-guess against the observed shape from the first `--audit-mode` run. Graceful degradation to `url_pattern`-only if the landmark shape doesn't match.
- Any future per-project UX-manual consistency check (v2 concern).

**Mitigation:** run `verify.py --audit-mode <safe-url>` before trusting landmark detection on a real flow. Commit the dump to `artefacts/substrate-audit/YYYY-MM-DD/` and compare against the shape assumed by the loader.

---

## CLI surface

### Flow mode (v1 — deterministic)

```
verify.py <flow-script.json>                                   # run a flow
verify.py flow <flow-script.json> --allow-high-entropy         # opt into high-entropy flow fields (UUIDs, hashes)
verify.py --audit-mode <url> --confirm-substrate-audit         # dump substrate shape (×3 viewports, PII-gated)
verify.py --list-allowlist                                     # print full gate surface
verify.py --check-install                                      # verify SDK version + chrome-devtools-mcp reachable
```

### Journey mode (v0.3+ — LLM-in-loop)

```
verify.py journey <journey.json>                                # run one persona+intent journey
verify.py journey-suite <site.yaml>                             # run N journeys against one target (P7: × M viewports)
verify.py journey-diff <run_a_dir> <run_b_dir>                  # P3 regression alerts: walk both runs step-by-step
verify.py suite-diff <suite_dir> [--baseline <viewport>]        # auto-pair every (file × persona) cell across viewports
verify.py expand "<prose>" --target <url> [--persona-hint id]   # P1 natural-language → schema-valid journey.json
```

`--audit-mode` writes snapshot/network/console dumps to `artefacts/substrate-audit/<date>/`. It is **PII-gated**: requires `--confirm-substrate-audit` on the CLI *and* an interactive `y/N` prompt. Use it to inspect what the substrate returns (schema discovery, new CDP MCP version check), not as a general-purpose run.

`journey-diff` writes `diff-result.json` (schema `webwitness/diff/v1`) plus a self-contained `diff.html` showing both runs side-by-side, the merged step table with the first divergence outlined in red, and a findings diff (added findings highlighted yellow, removed findings struck through). Default output dir: `artefacts/diff-<runA>-vs-<runB>/`.

`suite-diff` runs over a P7 suite (one with a `viewports:` axis in site.yaml). It groups journey rows by `(file, persona)`, picks a baseline viewport (first one in suite.yaml order, override with `--baseline`), and emits a per-pair `diff-<runA>-vs-<runB>/` for each non-baseline cell plus a `suite-diff-result.json` roll-up. The reader's Diffs panel auto-discovers the per-pair dirs — no extra wiring. Returns exit 0 only if every compared cell is verdict-stable across viewports.

**Forced server-start flags (non-negotiable):**

- `--isolated` — temp user-data-dir per run, auto-cleanup. Closes Anya #5 (browser context reuse).
- `--no-usageStatistics` (or env `CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1`) — default is ON, sends data to Google. Privacy honesty blocker.
- `--no-category-extensions` — disables entire extensions category at server start. Belt-and-braces with the 5-tool deny entries.

**Refused server-start flags (wrapper exits non-zero; bare and `--flag=value` forms both refused):**

- `--slim` — exposes `evaluate` (arbitrary JS) under a renamed tool.
- `--experimentalScreencast` — enables 2 additional tools outside the allowlist.
- `--user-data-dir` — would defeat `--isolated` by pointing Chrome at a persistent profile (session cookies, logged-in accounts).
- `--profileDirectory` — same risk class as `--user-data-dir` via profile-switching.
- `--executablePath` — lets the caller point npx at a non-Chrome binary.
- `--chromeArg` — passes arbitrary args to Chrome itself (e.g. `--chromeArg --no-sandbox`).

---

## Allowlist (9 tools)

| Tool | Category | Purpose |
|---|---|---|
| `navigate_page` | Navigation | URL navigation |
| `click` | Input | Element click |
| `fill` | Input | Single-field text entry |
| `type_text` | Input | Keyboard input |
| `fill_form` | Input | Multi-field form submission |
| `take_snapshot` | Debugging | Accessibility-tree snapshot |
| `list_console_messages` | Debugging | Read-only console log |
| `list_network_requests` | Network | Read-only request list |
| `take_screenshot` | Debugging | Image artefact |

## Deny-list (14 tools at default load)

`evaluate_script`, `list_in_page_tools`, `execute_in_page_tool`, `install_extension`, `uninstall_extension`, `list_extensions`, `reload_extension`, `trigger_extension_action`, `take_memory_snapshot`, `lighthouse_audit`, `performance_start_trace`, `performance_stop_trace`, `upload_file`, `handle_dialog`.

`execute_in_page_tool` is the hidden escape hatch — it calls `window.__dtmcp.executeTool(name, args)` via Puppeteer `page.evaluate()`, equivalent to arbitrary JS. It MUST be in the deny-list AND fixture-tested.

## Parameter-gated tool (`emulate`)

`emulate` is a mega-tool with six parameters:

| Parameter | Default gate | Notes |
|---|---|---|
| `networkConditions` | allowed | 5 presets: Offline / Slow 3G / Fast 3G / Slow 4G / Fast 4G |
| `viewport` | allowed | required for three-viewport audit mode |
| `cpuThrottlingRate` | rejected unless flow declares `allow_cpu_throttle: true` | perf-testing only |
| `geolocation` | rejected unless flow declares `allow_geolocation: true` | PII-adjacent |
| `userAgent` | rejected unless flow declares `allow_user_agent_override: true` | identity-spoofing |
| `colorScheme` | rejected unless flow declares `allow_color_scheme_override: true` | cosmetic |

Unexpected parameters (not in the 6-key list) are rejected unconditionally. Rejections log to `artefacts/<run-id>/dispatcher.log`.

---

## Flow-script contract

```json
{
  "goal": "User can complete the signup form and land on the dashboard",
  "success_state": {
    "url_pattern": "/dashboard",
    "landmark": {
      "role": "heading",
      "name_matches": "Welcome"
    }
  },
  "viewport": { "width": 1280, "height": 800 },
  "steps": [
    { "tool": "navigate_page", "url": "https://example.com/signup" },
    { "tool": "fill_form", "fields": { "email": "test@example.com" } },
    { "tool": "click", "selector": "[data-testid=submit]" }
  ]
}
```

- `goal` and `success_state` are **mandatory**. Missing → refuse to run.
- `success_state.url_pattern` is primary. `success_state.landmark` is best-guess v1 (see universal gap above).
- `steps[].tool` must appear in the allowlist. Steps referencing denied or unknown tools → refuse to run.
- `navigate_page` URLs are SSRF-gated: `http`/`https` only; private/loopback/link-local IPs refused; cloud-metadata hostnames (`169.254.169.254`, `metadata.google.internal`) refused.
- Any string field containing a high-entropy token (≥20 chars, ≥4.5 bits/char Shannon entropy) is refused unless `--allow-high-entropy` is passed. Rationale: flow scripts are copied to `artefacts/<run-id>/flow.json`; a hard-coded session token lands on disk and in git.

---

## Artefact layout

```
artefacts/
  <run-id>/                            # flow run — UTC-ISO timestamp
    flow.json                          # copy of the flow script
    result.json                        # pass/fail + which success_state matcher fired
    dispatcher.log                     # emulate-parameter rejections, denied-tool attempts
    viewport-<N>/
      snapshot.json
      network.json
      console.json
      screenshot.png
  <run-id>/                            # journey run — same UTC-ISO format
    journey.json                       # copy of the journey (with _resolved persona)
    decisions.jsonl                    # one line per LLM iteration (action + rationale + observed)
    step-NN-<action>.json              # per-step MCP call payload + result
    final-snapshot.json                # last a11y snapshot when the loop terminated
    findings.json                      # synthetic findings (e.g. no-contact-reachable)
    flow.json                          # synthesised flow shape for reader compat
    result.json                        # PASS/UNCLEAR/FAIL + matcher + patience usage + judgment
    report.html                        # self-contained per-run reader page
  suite-<id>/                          # journey-suite run
    suite.json                         # copy of the site.yaml as JSON
    suite-result.json                  # roll-up: site + per-journey verdict rows + duration_ms
    <run-id-1>/                        # one journey-run subdir per row (same shape as above)
    <run-id-2>/
    ...
  diff-<runA>-vs-<runB>/               # journey-diff output
    diff-result.json                   # schema webwitness/diff/v1
    diff.html                          # rendered diff page
  substrate-audit/
    YYYY-MM-DD/
      <viewport>.json                  # snapshot + network + console, one per viewport
  index.html                           # multi-run index — flat runs + suite matrices + diffs panel
```

Main-session stdout hard-caps at a small, predictable surface: a verdict line, an artefact-path line, and (for journey/diff modes) a reader-path line. No JSON, no tracebacks, no screenshots inline.

---

## What this skill does NOT do (v1)

- `--codex-explain` flag — scoped out of v1 entirely. Revisit when a redaction spec lands.
- Request interception / response mocking — CDP MCP's Network category is read-only.
- Video capture — denied.
- PDF save — not in allowlist.
- Multi-page / multi-tab flows — v1 is single-page, single-tab.
- Concurrent runs — v1 is one browser per invocation.
- Cross-browser — CDP MCP is Chrome-only. Firefox/Safari are v2+.

---

## Follow-up tasks

### v1 (flow mode) — shipped
1. ✅ Skeleton on disk
2. ✅ Parameter-gated `emulate` dispatcher + smuggling fixture
3. ✅ Flow-script loader with refuse-to-run gate + SSRF gate + entropy scanner
4. ✅ Three-line output ceiling + artefacts writer (chmod 0o600/0o700)
5. ✅ MCP Python SDK pinned + hash-verified install.sh
6. ✅ Async session wrapper + dispatch_step + run_flow + run_audit_mode
7. ✅ `--audit-mode` dumps against known URL; substrate shape locked
8. ✅ Anya line-level re-pass on async wrappers + SSRF/entropy fixtures

### v0.3+ (journey mode) — shipped
9. ✅ J1 `journey.json` primitive + schema (`webwitness/journey/v0.3`)
10. ✅ J2 persona seeding (alpha — LLM framing only; v0.4 unblocks real cookie/storage seeding per BRIEF-032)
11. ✅ J3 LLM-in-loop selector via `claude --print` shell-out
12. ✅ J4 patience budgets (`max_clicks` / `max_dead_ends` / `max_page_wait_ms` / `max_duration_ms`)
13. ✅ J5 journey-suite (site.yaml shape + sequential runner)
14. ✅ J6 `final-snapshot.json` + `findings.json` (synthetic `no-contact-reachable` rule)
15. ✅ P1 natural-language journey expander (`verify.py expand`)
16. ✅ P2 site health matrix on the index (journeys × personas)
17. ✅ P3 regression alerts (`verify.py journey-diff`)
18. ✅ P4 client-facing review-mode toggle + brand slot
19. ✅ P5 template library (four curated journey templates in `journeys/templates/`)
20. ✅ Reader narrative polish — `patience_exhausted` renders as a labelled terminal step

### Open
21. ⏳ P7 device/viewport matrix (wrap `run_journey` × `{desktop, tablet, mobile}`)
22. ⏳ P8 consent / cookie banner primitive
23. ⏳ BRIEF-032 unblock — real persona seeding (cookie/storage/referrer); unblocks P6 persona-vs-persona diff. Scheduled cloud routine `trig_014gVeVsq5oJpDmY6hNKNmk1` checks status 2026-05-08.
24. ◻ Publish-to-`claude-code-skills` decision (deferred from panel synthesis until v1 is usable internally — now usable; revisit)

---

*Pairs with `verify.py` + `install.sh`. Panel synthesis: `_shared/briefs/BRIEF-028-webapp-verify-PANEL-SYNTHESIS.md`.*
