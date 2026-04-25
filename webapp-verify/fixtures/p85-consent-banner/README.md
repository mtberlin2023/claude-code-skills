# P8.5 — synthetic consent-banner fixture

Built 2026-04-25 to validate the `dismiss_consent` LLM-trigger leg in a controlled environment after 6 wild targets failed to surface a blocking modal in chrome-devtools-mcp's accessibility-tree snapshot (see `_pocs/technical/webwitness-vs-playwright/results/READER-ROADMAP.md` § P8.5).

## What's in here

- `index.html` — a minimal article page with a fixed-bottom consent banner (`<div role="dialog" aria-modal="true">` + Accept all / Reject all / Manage buttons in standard ARIA roles). Article body containing the success phrase `quokka safari handbook` is hidden behind a CSS class that flips when any banner button is clicked. No shadow DOM, no top-layer rendering, no CMP fingerprinting.
- `journey.json` — a webwitness journey targeting `http://127.0.0.1:9876/` with `required_content: ["quokka safari handbook"]`. Only path to PASS is for the LLM to pick `dismiss_consent`.

## Why it isn't usable from loopback

The SSRF static gate in `verify.py` (`_validate_step_url`, Anya #5, 2026-04-22, honesty-critical) refuses any IP literal in `is_private | is_loopback | is_link_local | is_multicast | is_reserved` ranges. `127.0.0.1`, `localhost`, and well-known loopback DNS names (`localhost.localdomain`, `ip6-loopback`, etc.) are all hard-blocked. There is no override flag.

This is correct substrate behaviour — the gate exists precisely to stop verify.py from being weaponised against internal services. The fixture cannot be smoked from loopback without weakening the gate, which is not the right trade.

## How to actually run this

To validate the LLM-trigger leg, deploy the fixture to a public-facing host and re-target `journey.json` at the public URL. Three reasonable paths:

1. **GitHub Pages from this repo** — push `fixtures/p85-consent-banner/` and enable Pages on the branch; the fixture will be served at `https://<owner>.github.io/<repo>/fixtures/p85-consent-banner/`.
2. **`surge.sh` one-shot deploy** — `cd fixtures/p85-consent-banner && surge .` gives a `https://<random>.surge.sh` URL.
3. **Cloudflare Pages / Vercel / Netlify** — drop the dir into any static-site host.

Once the fixture has a public URL, edit `journey.json`'s `target` field and run `verify.py journey fixtures/p85-consent-banner/journey.json`. Expected positive result: `consents_dismissed >= 1`, `clicks_used == 0` (consent dismissals are explicitly NOT charged to clicks_used per the P8 substrate), `verdict: PASS`, `matcher: required_content`.

## Wild-target context

Six wild targets attempted 2026-04-25 (undavos.com, termly.io/resources/articles/gdpr-consent-examples/, theguardian.com/europe, zeit.de, bbc.com/news, cookiebot.com) all returned `consents_dismissed: 0`. Snapshot inspection confirmed the issue is **not** the LLM failing to pick `dismiss_consent` — the snapshots simply don't contain modal/dialog DOM elements. Page body content captures fine; CMP-injected overlays do not. This is consistent with chrome-devtools-mcp's accessibility-tree snapshot not traversing top-layer / shadow-DOM modals, possibly compounded by CMP scripts that detect automation and skip injection.

The synthetic fixture eliminates both confounds (visible div, no shadow DOM, no top-layer, no automation-detection) and is the cleanest known way to prove the LLM-trigger leg works as designed once it can be served from a non-loopback host.
