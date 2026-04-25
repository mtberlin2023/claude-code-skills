"""HTML/CSS/JS template for a single-run report and the multi-run index.

Templates are Python string constants with `__TOKEN__` placeholders (not
`{key}` — that would collide with CSS/JS brace syntax). Substitution is
literal string replace, so no escaping surprises.
"""

from __future__ import annotations

import html
import json


def render_report(payload: dict) -> str:
    data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        _REPORT_HTML
        .replace("__TITLE__", html.escape(f"webwitness report — {payload['run_id']}"))
        .replace("__STYLE__", _STYLE)
        .replace("__DATA_JSON__", data_js)
        .replace("__SCRIPT__", _REPORT_JS)
    )


def render_index(payload: dict) -> str:
    data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        _INDEX_HTML
        .replace("__TITLE__", "webwitness runs — index")
        .replace("__STYLE__", _STYLE + _INDEX_STYLE)
        .replace("__DATA_JSON__", data_js)
        .replace("__SCRIPT__", _INDEX_JS)
    )


_REPORT_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__STYLE__</style>
</head>
<body>
<div id="app"></div>
<script id="run-data" type="application/json">__DATA_JSON__</script>
<script>__SCRIPT__</script>
</body>
</html>
"""


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__STYLE__</style>
</head>
<body>
<div id="app"></div>
<script id="index-data" type="application/json">__DATA_JSON__</script>
<script>__SCRIPT__</script>
</body>
</html>
"""


_STYLE = r"""
:root {
  --bg: #0e1116;
  --panel: #171c23;
  --panel-2: #1f252e;
  --border: #2a303a;
  --fg: #e6edf3;
  --muted: #8b949e;
  --pass: #2ea043;
  --fail: #cf222e;
  --warn: #d29922;
  --info: #58a6ff;
  --add: #2ea043;
  --rem: #cf222e;
  --chg: #d29922;
  --accent: #58a6ff;
  --mono: ui-monospace, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, monospace;
  --add-bg: rgba(46, 160, 67, 0.12);
  --rem-bg: rgba(207, 34, 46, 0.12);
  --chg-bg: rgba(210, 153, 34, 0.12);
}
body.light {
  --bg: #f6f8fa;
  --panel: #ffffff;
  --panel-2: #f0f3f7;
  --border: #d0d7de;
  --fg: #1f2328;
  --muted: #5d6572;
  --pass: #1a7f37;
  --fail: #cf222e;
  --warn: #9a6700;
  --info: #0969da;
  --add: #1a7f37;
  --rem: #cf222e;
  --chg: #9a6700;
  --accent: #0969da;
  --add-bg: rgba(26, 127, 55, 0.10);
  --rem-bg: rgba(207, 34, 46, 0.10);
  --chg-bg: rgba(154, 103, 0, 0.12);
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--fg);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
}
#app {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 24px 80px;
}
a { color: var(--accent); }
a:hover { text-decoration: underline; }
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
  padding: 0 0 14px;
  flex-wrap: wrap;
}
.toolbar .brand {
  margin-right: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: var(--fg);
}
.toolbar .brand img { height: 26px; width: auto; border-radius: 4px; }
.toolbar .brand .tagline { color: var(--muted); font-size: 12px; font-weight: 400; }
.tbtn {
  background: var(--panel);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 12px;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.tbtn:hover { border-color: var(--accent); }
.tbtn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.verdict {
  border-radius: 10px;
  padding: 20px 28px;
  display: flex;
  align-items: center;
  gap: 24px;
  font-size: 18px;
  font-weight: 500;
  border: 1px solid var(--border);
  flex-wrap: wrap;
}
.verdict .badge {
  font-size: 28px;
  font-weight: 700;
  padding: 4px 14px;
  border-radius: 6px;
}
.verdict.pass { background: rgba(46, 160, 67, 0.12); border-color: rgba(46, 160, 67, 0.5); }
.verdict.fail { background: rgba(207, 34, 46, 0.12); border-color: rgba(207, 34, 46, 0.5); }
.verdict.pass .badge { background: var(--pass); color: #fff; }
.verdict.fail .badge { background: var(--fail); color: #fff; }
.verdict .meta { color: var(--muted); font-size: 14px; font-weight: 400; font-family: var(--mono); }
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px 24px;
  margin-top: 20px;
  scroll-margin-top: 16px;
}
.panel h2 {
  margin: 0 0 12px;
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
}
.goal .prose { font-size: 15px; line-height: 1.55; }
.goal .meta-row {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 12.5px;
  margin-top: 10px;
}
.goal .meta-row span { margin-right: 16px; }
.why-fail {
  background: var(--rem-bg);
  border: 1px solid var(--fail);
  border-radius: 8px;
  padding: 14px 18px;
  margin-top: 12px;
}
.why-fail strong { color: var(--fail); }
.why-fail code { font-family: var(--mono); background: var(--panel-2); padding: 1px 5px; border-radius: 3px; }
.split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; }
.screenshot-thumb img {
  max-width: 100%;
  border-radius: 6px;
  border: 1px solid var(--border);
  cursor: zoom-in;
  display: block;
}
.evidence ul { list-style: none; padding: 0; margin: 0; }
.evidence li { padding: 6px 0; display: flex; gap: 10px; align-items: baseline; }
.evidence li .sym { color: var(--pass); font-weight: 700; }
.evidence li.miss .sym { color: var(--fail); }
.narr-meta { display: grid; gap: 4px; padding: 12px; background: var(--panel-2); border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
.narr-meta strong { color: var(--muted); font-weight: 600; margin-right: 4px; }
.narr-usage { color: var(--muted); font-size: 12px; margin-top: 4px; font-family: var(--mono); }
.narr-list { list-style: none; padding: 0; margin: 0; counter-reset: narr; }
.narr-step { counter-increment: narr; padding: 10px 12px 10px 38px; border-left: 2px solid var(--border); position: relative; margin-bottom: 6px; }
.narr-step::before { content: counter(narr); position: absolute; left: 8px; top: 10px; color: var(--muted); font-family: var(--mono); font-size: 12px; width: 22px; text-align: right; }
.narr-step:hover { background: var(--panel-2); }
.narr-head { font-weight: 600; }
.narr-tag { display: inline-block; padding: 1px 6px; background: var(--panel-2); border-radius: 3px; color: var(--muted); font-family: var(--mono); font-size: 11px; text-transform: lowercase; margin-right: 6px; }
.narr-rat { color: var(--fg); margin-top: 4px; font-style: italic; }
.narr-obs { color: var(--muted); margin-top: 3px; font-family: var(--mono); font-size: 12px; }
.narr-foot { color: var(--muted); font-size: 11px; margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border); font-style: italic; }
.narr-step--patience {
  border-left-color: var(--fail);
  background: var(--rem-bg);
  margin-top: 10px;
}
.narr-step--patience::before { color: var(--fail); font-weight: 700; }
.narr-step--patience .narr-tag {
  background: transparent;
  color: var(--fail);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.narr-step--patience .narr-rat,
.narr-step--patience .narr-obs { color: var(--fg); }
.narr-stop-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  background: var(--fail);
  color: #fff;
  font-family: var(--mono);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-right: 8px;
}
.timeline { font-family: var(--mono); font-size: 13px; }
.timeline .row {
  display: grid;
  grid-template-columns: 40px 24px 1fr 70px;
  gap: 10px;
  padding: 8px 8px;
  border-radius: 6px;
  align-items: baseline;
}
.timeline .row:hover { background: var(--panel-2); }
.timeline .row .idx { color: var(--muted); text-align: right; }
.timeline .row .dot { font-size: 14px; text-align: center; }
.timeline .row .tool { color: var(--fg); font-weight: 600; }
.timeline .row .detail { color: var(--muted); }
.timeline .row .delta { display: block; color: var(--muted); margin-top: 3px; }
.timeline .row .delta .add { color: var(--add); }
.timeline .row .delta .rem { color: var(--rem); }
.timeline .row .delta .chg { color: var(--chg); }
.timeline .row .duration { color: var(--muted); text-align: right; font-size: 12px; }
.timeline .step-screenshot { max-width: 220px; margin-top: 6px; border: 1px solid var(--border); border-radius: 4px; cursor: zoom-in; }
.findings-list { padding: 0; list-style: none; margin: 0; }
.findings-list li {
  padding: 10px 14px;
  border-left: 3px solid var(--border);
  margin: 6px 0;
  background: var(--panel-2);
  border-radius: 0 6px 6px 0;
}
.findings-list li.error { border-left-color: var(--fail); }
.findings-list li.warn { border-left-color: var(--warn); }
.findings-list li.info { border-left-color: var(--info); }
.findings-list li .fid { font-family: var(--mono); font-size: 12px; color: var(--muted); margin-right: 10px; }
.findings-list li .node { font-family: var(--mono); font-size: 12px; color: var(--muted); display: block; margin-top: 4px; white-space: pre-wrap; word-break: break-all; }
.findings-list li .sev-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-right: 8px;
}
.findings-list li.error .sev-pill { background: var(--fail); color: #fff; }
.findings-list li.warn .sev-pill { background: var(--warn); color: #fff; }
.findings-list li.info .sev-pill { background: var(--info); color: #fff; }
.findings-empty { color: var(--muted); font-style: italic; }
.tab-bar {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--border);
  margin-top: 10px;
}
.tab-bar button {
  background: transparent;
  border: none;
  color: var(--muted);
  font: inherit;
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  font-size: 13px;
}
.tab-bar button.active { color: var(--fg); border-bottom-color: var(--accent); }
.tab-body { padding-top: 16px; }
.search-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.search-bar input {
  flex: 1;
  background: var(--panel-2);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font: inherit;
  font-size: 13px;
}
.search-bar .hint { color: var(--muted); font-size: 12px; font-family: var(--mono); }
.diff {
  font-family: var(--mono);
  font-size: 12.5px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
.diff .line-wrap {
  display: flex;
  align-items: flex-start;
}
.diff .line {
  flex: 1;
  padding: 1px 8px;
  border-radius: 3px;
  cursor: text;
}
.diff .line.add { background: var(--add-bg); color: var(--add); }
.diff .line.rem { background: var(--rem-bg); color: var(--rem); }
.diff .line.chg { background: var(--chg-bg); color: var(--chg); }
.diff .line.eq { color: var(--muted); }
.diff .line.hidden { display: none; }
.diff .copy-btn {
  opacity: 0;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 4px;
  padding: 0 6px;
  font-size: 10px;
  cursor: pointer;
  margin-left: 6px;
  margin-top: 2px;
  font-family: var(--mono);
  transition: opacity 0.1s;
}
.diff .line-wrap:hover .copy-btn { opacity: 1; }
.diff .copy-btn.copied { color: var(--pass); border-color: var(--pass); }
.diff .collapsed { color: var(--muted); font-style: italic; cursor: pointer; padding: 4px 8px; }
.diff-summary { color: var(--muted); font-family: var(--mono); font-size: 12px; margin-bottom: 10px; }
.diff-summary .add { color: var(--add); }
.diff-summary .rem { color: var(--rem); }
.diff-summary .chg { color: var(--chg); }
.raw-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.raw-card { padding: 12px 14px; background: var(--panel-2); border-radius: 8px; border: 1px solid var(--border); }
.raw-card .name { font-family: var(--mono); font-size: 13px; }
.raw-card .size { color: var(--muted); font-family: var(--mono); font-size: 11.5px; margin-top: 4px; }
.raw-card a { display: inline-block; margin-top: 8px; font-size: 12px; }

.modal {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 100;
  overflow: hidden;
  touch-action: none;
}
.modal.open { display: flex; }
.modal .zoom-wrap {
  position: relative;
  cursor: grab;
  user-select: none;
}
.modal.dragging .zoom-wrap { cursor: grabbing; }
.modal img {
  max-width: none;
  display: block;
  transform-origin: 0 0;
  pointer-events: none;
}
.modal .zoom-hud {
  position: fixed;
  top: 14px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.65);
  color: #fff;
  font-family: var(--mono);
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 6px;
}
.modal .zoom-close {
  position: fixed;
  top: 14px;
  right: 14px;
  background: rgba(0,0,0,0.65);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  font: inherit;
  cursor: pointer;
}
.snapshot-picker { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.snapshot-picker button {
  background: var(--panel-2);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 6px 10px;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  font-family: var(--mono);
}
.snapshot-picker button.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.kbd { font-family: var(--mono); background: var(--panel-2); padding: 1px 6px; border-radius: 4px; font-size: 12px; border: 1px solid var(--border); }
.side-nav {
  position: fixed;
  right: 18px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 40;
}
.side-nav a {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--panel);
  border: 1px solid var(--border);
  color: var(--muted);
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  font-family: var(--mono);
  font-size: 11px;
  transition: all 0.12s;
}
.side-nav a:hover, .side-nav a.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
  transform: scale(1.08);
}
.side-nav a .tip {
  position: absolute;
  right: 36px;
  background: var(--panel);
  border: 1px solid var(--border);
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--fg);
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.12s;
  font-family: inherit;
}
.side-nav a:hover .tip { opacity: 1; }
body.review .dev-only { display: none !important; }
body.review .tab-bar button[data-tab="raw"] { display: none; }
body.review .uid { display: none; }
footer {
  margin-top: 48px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
  font-family: var(--mono);
  text-align: center;
}
footer .brand-footer {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
}
@media (max-width: 900px) {
  .side-nav { display: none; }
}
@media (max-width: 780px) {
  .split { grid-template-columns: 1fr; }
}
"""


_INDEX_STYLE = r"""
.filters {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.filters .seg { display: flex; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.filters .seg button {
  background: transparent;
  color: var(--muted);
  border: none;
  padding: 6px 12px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  border-right: 1px solid var(--border);
}
.filters .seg button:last-child { border-right: none; }
.filters .seg button.active { background: var(--accent); color: #fff; }
.filters input, .filters select {
  background: var(--panel-2);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font: inherit;
  font-size: 13px;
}
.filters input { min-width: 220px; }
.runs-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.runs-table th, .runs-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
.runs-table th { color: var(--muted); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600; }
.runs-table tbody tr:hover { background: var(--panel-2); }
.runs-table .verdict-cell { font-weight: 600; font-family: var(--mono); }
.runs-table .verdict-cell.pass { color: var(--pass); }
.runs-table .verdict-cell.fail { color: var(--fail); }
.runs-table td.goal-cell { max-width: 520px; }
.runs-table td.goal-cell .truncate {
  display: block;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.45;
}
.counts { color: var(--muted); font-family: var(--mono); font-size: 12px; margin-bottom: 6px; }
.cluster {
  margin-top: 14px;
  padding: 14px 18px;
  background: var(--panel-2);
  border-radius: 8px;
  border: 1px solid var(--border);
}
.cluster .cluster-goal { font-weight: 600; font-size: 13px; margin-bottom: 6px; }
.cluster .cluster-meta { color: var(--muted); font-size: 12px; font-family: var(--mono); margin-bottom: 10px; }
.cluster .trend { display: flex; gap: 3px; flex-wrap: wrap; align-items: center; }
.cluster .trend .pill {
  width: 18px;
  height: 18px;
  border-radius: 3px;
  display: inline-block;
  font-size: 10px;
  font-family: var(--mono);
  text-align: center;
  line-height: 18px;
  color: #fff;
  text-decoration: none;
}
.cluster .trend .pill.pass { background: var(--pass); }
.cluster .trend .pill.fail { background: var(--fail); }
.cluster .trend .arrow { color: var(--muted); margin: 0 4px; font-size: 11px; }
.cluster .trend .pill:hover { outline: 2px solid var(--accent); outline-offset: 1px; }
.suite {
  margin-top: 14px;
  padding: 16px 20px;
  background: var(--panel-2);
  border-radius: 10px;
  border: 1px solid var(--border);
}
.suite-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.suite-head .label { font-weight: 600; font-size: 14px; }
.suite-head .target { color: var(--muted); font-family: var(--mono); font-size: 12px; }
.suite-head .summary { margin-left: auto; color: var(--muted); font-family: var(--mono); font-size: 12px; }
.suite-head .summary .pass { color: var(--pass); }
.suite-head .summary .fail { color: var(--fail); }
.suite-head .summary .unclear { color: var(--warn); }
.matrix { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.matrix th, .matrix td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.matrix th {
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 600;
}
.matrix th.persona-col { text-align: center; }
.matrix td.file-cell {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--fg);
  max-width: 360px;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-all;
  line-height: 1.45;
}
.matrix td.cell {
  text-align: center;
  font-family: var(--mono);
}
.matrix .verdict-link {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 4px;
  text-decoration: none;
  font-weight: 600;
  font-size: 11px;
  letter-spacing: 0.04em;
}
.matrix .verdict-link.pass { background: var(--pass); color: #fff; }
.matrix .verdict-link.fail { background: var(--fail); color: #fff; }
.matrix .verdict-link.unclear { background: var(--warn); color: #fff; }
.matrix .verdict-link:hover { outline: 2px solid var(--accent); outline-offset: 1px; text-decoration: none; }
.matrix .empty-cell { color: var(--muted); font-size: 14px; }
.alpha-badge {
  display: inline-block;
  font-size: 10.5px;
  font-family: var(--mono);
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--warn);
  color: #fff;
  font-weight: 600;
  cursor: help;
}
.viewport-axis-badge {
  display: inline-block;
  font-size: 10.5px;
  font-family: var(--mono);
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--info);
  color: #fff;
  font-weight: 600;
  cursor: help;
}
.viewport-pill {
  display: inline-block;
  font-size: 10.5px;
  font-family: var(--mono);
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--panel);
  color: var(--info);
  border: 1px solid var(--info);
  margin-left: 8px;
  font-weight: 600;
}
.suite-diff-badge {
  display: inline-block;
  font-size: 10.5px;
  font-family: var(--mono);
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--info);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
}
.suite-diff-badge:hover { filter: brightness(1.1); }
.suite-diff-badge--alert { background: var(--fail); }
.suite-diff-badge--stable { background: var(--pass); }
.diffs-panel {
  margin-top: 14px;
  padding: 16px 20px;
  background: var(--panel-2);
  border-radius: 10px;
  border: 1px solid var(--border);
}
.diffs-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.diffs-head .label { font-weight: 600; font-size: 14px; }
.diffs-head .tagline { color: var(--muted); font-size: 12px; }
.diffs-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.diffs-table th,
.diffs-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.diffs-table th {
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 600;
}
"""


_REPORT_JS = r"""
(function () {
  const DATA = JSON.parse(document.getElementById('run-data').textContent);
  const app = document.getElementById('app');
  const prefs = loadPrefs();

  applyTheme(prefs.theme);
  applyMode(prefs.mode);

  app.innerHTML = [
    renderToolbar(DATA),
    renderVerdict(DATA),
    renderGoal(DATA),
    renderNarrative(DATA),
    renderWhyFail(DATA),
    renderSplit(DATA),
    renderTimeline(DATA),
    renderFindings(DATA),
    renderTabs(DATA),
    renderBrandFooter(DATA),
    '<footer>Generated by webwitness reader · run_id ' + escape(DATA.run_id) + '</footer>',
    '<div class="modal" id="img-modal"><div class="zoom-hud" id="zoom-hud">1.00×</div><button class="zoom-close" id="zoom-close">Close</button><div class="zoom-wrap" id="zoom-wrap"><img id="modal-img"></div></div>',
    '<nav class="side-nav dev-only" id="side-nav"></nav>'
  ].join('');

  wireToolbar();
  wireImageZoom();
  wireTabs();
  wireSideNav();

  function renderToolbar(d) {
    const brand = d.brand || {};
    const label = brand.label || 'webwitness';
    const tagline = brand.tagline || 'website review · run report';
    const logoHtml = brand.logo_src
      ? '<img src="' + escape(brand.logo_src) + '" alt="">'
      : '<span style="font-size:18px">◉</span>';
    return '<div class="toolbar">'
      + '<div class="brand">' + logoHtml + '<span>' + escape(label)
      + ' <span class="tagline">' + escape(tagline) + '</span></span></div>'
      + '<button class="tbtn" id="theme-btn">☾</button>'
      + '<button class="tbtn" id="mode-btn">dev mode</button>'
      + '</div>';
  }

  function renderVerdict(d) {
    const cls = d.result.pass ? 'pass' : 'fail';
    const label = d.result.pass ? 'PASS' : 'FAIL';
    const mark = d.result.pass ? '✓' : '✗';
    const matcher = d.result.matcher || 'no matcher fired';
    const steps = (d.result.steps_completed || 0) + '/' + (d.result.steps_total || 0);
    const duration = d.result.duration_ms ? (d.result.duration_ms + 'ms') : (d.duration_ms ? d.duration_ms + 'ms' : '—');
    return '<div class="verdict ' + cls + '" id="sec-verdict">'
      + '<span class="badge">' + label + ' ' + mark + '</span>'
      + '<span>' + escape(matcher) + ' matcher</span>'
      + '<span class="meta">' + steps + ' steps · ' + duration + ' · <span class="dev-only uid">' + escape(d.run_id) + '</span></span>'
      + '</div>';
  }

  function renderGoal(d) {
    const goal = d.flow.goal || '(no goal stated)';
    const target = d.flow.steps && d.flow.steps[0] && d.flow.steps[0].url ? d.flow.steps[0].url : '—';
    const success = d.flow.success_state || {};
    let successText = '—';
    if (success.url_pattern) successText = 'URL contains ' + success.url_pattern;
    else if (success.landmark) successText = 'landmark present';
    return '<section class="panel goal" id="sec-goal"><h2>Goal</h2>'
      + '<div class="prose">' + escape(goal) + '</div>'
      + '<div class="meta-row"><span>Target: <a href="' + escape(target) + '" target="_blank" rel="noopener">' + escape(target) + '</a></span>'
      + '<span>Success: ' + escape(successText) + '</span></div>'
      + '</section>';
  }

  function renderNarrative(d) {
    if (!d.journey || !d.narrative || !d.narrative.length) return '';
    const persona = (d.journey._resolved && d.journey._resolved.persona) || {};
    const personaLabel = persona.label || d.journey.persona || 'persona';
    const personaDesc = persona.description || '';
    const intent = d.journey.intent || '';
    const target = d.journey.target || '';
    const items = d.narrative.map(step => {
      const tag = step.action || '?';
      const isPatience = tag === 'patience_exhausted';
      const targetName = step.target_name ? ' "' + escape(step.target_name) + '"' : '';
      const observed = step.observed ? '<div class="narr-obs">→ ' + escape(step.observed) + '</div>' : '';
      const rationale = step.rationale ? '<div class="narr-rat">' + escape(step.rationale) + '</div>' : '';
      if (isPatience) {
        return '<li class="narr-step narr-step--patience">'
          + '<div class="narr-head">'
          + '<span class="narr-stop-pill">STOPPED</span>'
          + '<span class="narr-tag">patience exhausted</span>'
          + '</div>'
          + rationale
          + observed
          + '</li>';
      }
      return '<li class="narr-step"><div class="narr-head"><span class="narr-tag">' + escape(tag) + '</span>' + targetName + '</div>' + rationale + observed + '</li>';
    }).join('');
    const verdict = d.result.verdict || (d.result.pass ? 'PASS' : 'FAIL');
    const matcher = d.result.matcher || '—';
    const budget = d.journey._resolved && d.journey._resolved.patience ? d.journey._resolved.patience : null;
    const usage = '<span>iters: ' + (d.result.iterations || 0) + '</span> · '
      + '<span>clicks: ' + (d.result.clicks_used || 0) + (budget ? '/' + budget.max_clicks : '') + '</span> · '
      + '<span>dead-ends: ' + (d.result.dead_ends || 0) + (budget ? '/' + budget.max_dead_ends : '') + '</span>';
    return '<section class="panel" id="sec-narrative"><h2>Narrative</h2>'
      + '<div class="narr-meta">'
      + '<div><strong>Persona:</strong> ' + escape(personaLabel) + (personaDesc ? ' — ' + escape(personaDesc) : '') + '</div>'
      + '<div><strong>Intent:</strong> ' + escape(intent) + '</div>'
      + '<div><strong>Target:</strong> <a href="' + escape(target) + '" target="_blank" rel="noopener">' + escape(target) + '</a></div>'
      + '<div><strong>Verdict:</strong> ' + escape(verdict) + ' · matcher: ' + escape(matcher) + '</div>'
      + '<div class="narr-usage">' + usage + '</div>'
      + '</div>'
      + '<ol class="narr-list">' + items + '</ol>'
      + '<div class="narr-foot">v0.3 alpha: persona influences LLM framing only — in-browser state is empty for every persona. See journeys/SCHEMA.md.</div>'
      + '</section>';
  }

  function renderWhyFail(d) {
    if (d.result.pass) return '';
    const r = d.why_fail;
    if (!r) return '';
    return '<section class="panel" id="sec-whyfail"><h2>Why did this fail?</h2>'
      + '<div class="why-fail">' + r + '</div></section>';
  }

  function renderSplit(d) {
    const img = d.final_screenshot ? (
      '<div class="screenshot-thumb"><img src="' + d.final_screenshot + '" alt="final screenshot" onclick="openModal(this.src)"></div>'
    ) : '<div class="screenshot-thumb" style="color:var(--muted)">No screenshot captured.</div>';
    const evidence = d.result.pass ? renderEvidence(d) : renderMiss(d);
    return '<section class="panel" id="sec-evidence"><h2>' + (d.result.pass ? 'Success evidence' : 'Expected evidence (not met)') + '</h2>'
      + '<div class="split">' + img + '<div class="evidence">' + evidence + '</div></div></section>';
  }

  function renderEvidence(d) {
    const items = (d.evidence || []).map(e => '<li><span class="sym">✓</span><span>' + escape(e) + '</span></li>').join('');
    return '<ul>' + (items || '<li class="miss"><span class="sym">—</span><span>No evidence items recorded.</span></li>') + '</ul>';
  }

  function renderMiss(d) {
    const items = (d.missed_evidence || []).map(e => '<li class="miss"><span class="sym">✗</span><span>' + escape(e) + '</span></li>').join('');
    return '<ul>' + (items || '<li class="miss"><span class="sym">✗</span><span>Matcher returned no match.</span></li>') + '</ul>';
  }

  function renderTimeline(d) {
    const rows = (d.timeline || []).map(row => {
      const dot = row.kind === 'action' ? '●' : row.kind === 'snapshot' ? '○' : '◐';
      const thumb = row.screenshot ? '<img class="step-screenshot" src="' + row.screenshot + '" onclick="openModal(this.src)">' : '';
      const delta = row.delta_html ? '<span class="delta">' + row.delta_html + '</span>' : '';
      const duration = row.duration_ms !== null && row.duration_ms !== undefined ? (row.duration_ms + 'ms') : '';
      return '<div class="row">'
        + '<span class="idx">' + row.index + '</span>'
        + '<span class="dot">' + dot + '</span>'
        + '<div><span class="tool">' + escape(row.tool) + '</span> <span class="detail">' + (row.detail_html || escape(row.detail || '')) + '</span>' + delta + thumb + '</div>'
        + '<span class="duration">' + duration + '</span>'
        + '</div>';
    }).join('');
    return '<section class="panel" id="sec-timeline"><h2>Timeline</h2><div class="timeline">' + rows + '</div></section>';
  }

  function renderFindings(d) {
    const list = (d.findings || []).slice().sort(severitySort);
    if (!list.length) {
      return '<section class="panel" id="sec-findings"><h2>Findings (auto)</h2><div class="findings-empty">None flagged.</div></section>';
    }
    const items = list.map(f => '<li class="' + f.severity + '">'
      + '<span class="sev-pill">' + escape(f.severity) + '</span>'
      + '<span class="fid dev-only">' + escape(f.rule_id) + '</span>'
      + escape(f.description)
      + (f.node_repr ? '<span class="node">' + escape(f.node_repr) + '</span>' : '')
      + '</li>').join('');
    return '<section class="panel" id="sec-findings"><h2>Findings (auto)</h2><ul class="findings-list">' + items + '</ul></section>';
  }

  function severitySort(a, b) {
    const order = { error: 0, warn: 1, info: 2 };
    return (order[a.severity] || 9) - (order[b.severity] || 9);
  }

  function renderTabs(d) {
    const defaultTab = prefs.tab || 'diffs';
    const mkBtn = (id, label, devOnly) => '<button data-tab="' + id + '"' + (devOnly ? ' data-dev-only="1"' : '') + (id === defaultTab ? ' class="active"' : '') + '>' + label + '</button>';
    return '<section class="panel" id="sec-detail"><h2>Detail</h2>'
      + '<div class="tab-bar">'
      + mkBtn('diffs', 'Diffs')
      + mkBtn('snapshots', 'Snapshots')
      + mkBtn('raw', 'Raw files', true)
      + '</div>'
      + '<div class="tab-body" id="tab-body"></div></section>';
  }

  function renderBrandFooter(d) {
    const brand = d.brand || {};
    if (!brand.footer) return '';
    return '<footer class="brand-footer">' + escape(brand.footer) + '</footer>';
  }

  function renderDiffsTab() {
    const body = document.getElementById('tab-body');
    const diffs = DATA.diffs || [];
    if (!diffs.length) {
      body.innerHTML = '<div class="findings-empty">No snapshot diffs (fewer than two snapshots captured).</div>';
      return;
    }
    const pickerBtns = diffs.map((d, i) => '<button data-diff="' + i + '"' + (i === 0 ? ' class="active"' : '') + '>#' + d.from_step + ' → #' + d.to_step + '</button>').join('');
    body.innerHTML = '<div class="snapshot-picker" id="diff-picker">' + pickerBtns + '</div>'
      + '<div class="search-bar"><input id="diff-search" placeholder="Filter diff (role, name, url…)"><span class="hint">Enter to apply · Esc clears</span></div>'
      + '<div id="diff-body"></div>';
    showDiff(0);
    body.querySelectorAll('#diff-picker button').forEach(btn => {
      btn.addEventListener('click', () => {
        body.querySelectorAll('#diff-picker button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        showDiff(parseInt(btn.dataset.diff, 10));
      });
    });
    const input = document.getElementById('diff-search');
    input.addEventListener('input', () => applyDiffFilter(input.value));
    input.addEventListener('keydown', e => { if (e.key === 'Escape') { input.value = ''; applyDiffFilter(''); } });
  }

  function applyDiffFilter(q) {
    q = (q || '').toLowerCase();
    document.querySelectorAll('#diff-body .line-wrap').forEach(wrap => {
      const text = wrap.textContent.toLowerCase();
      wrap.classList.toggle('hidden', !!q && !text.includes(q));
    });
    document.querySelectorAll('#diff-body .collapsed').forEach(el => {
      el.classList.toggle('hidden', !!q);
    });
  }

  function showDiff(idx) {
    const d = DATA.diffs[idx];
    const summary = '<div class="diff-summary">Δ '
      + '<span class="add">+' + d.summary['+'] + '</span> '
      + '<span class="rem">−' + d.summary['-'] + '</span> '
      + '<span class="chg">~' + d.summary['~'] + '</span> '
      + '(' + d.summary['='] + ' unchanged)</div>';
    const lines = collapseEquals(d.ops);
    document.getElementById('diff-body').innerHTML = summary + '<div class="diff">' + lines + '</div>';
    wireCollapsed();
    wireCopy();
  }

  function collapseEquals(ops) {
    const out = [];
    let runStart = -1;
    let runCount = 0;
    function flushRun() {
      if (runCount >= 5) {
        out.push('<div class="collapsed" data-run="' + runStart + '-' + runCount + '">⋯ ' + runCount + ' unchanged nodes ⋯</div>');
      } else if (runCount > 0) {
        for (let i = runStart; i < runStart + runCount; i++) {
          out.push(renderDiffLineWrap(ops[i]));
        }
      }
      runStart = -1;
      runCount = 0;
    }
    ops.forEach((op, i) => {
      if (op.kind === '=') {
        if (runStart === -1) runStart = i;
        runCount++;
      } else {
        flushRun();
        out.push(renderDiffLineWrap(op));
      }
    });
    flushRun();
    return out.join('');
  }

  function renderDiffLineWrap(op) {
    return '<div class="line-wrap">' + renderDiffLine(op) + '<button class="copy-btn" title="Copy line">copy</button></div>';
  }

  function renderDiffLine(op) {
    const cls = op.kind === '+' ? 'add' : op.kind === '-' ? 'rem' : op.kind === '~' ? 'chg' : 'eq';
    const sym = op.kind === '=' ? ' ' : op.kind;
    let text;
    if (op.kind === '~') {
      text = nodeRender(op.a) + '\n  → ' + nodeRender(op.b);
    } else {
      text = nodeRender(op.a || op.b);
    }
    return '<div class="line ' + cls + '">' + sym + ' ' + escape(text) + '</div>';
  }

  function nodeRender(n) {
    if (!n) return '';
    const parts = [n.role];
    if (n.name !== null && n.name !== undefined) parts.push('"' + n.name + '"');
    if (n.level) parts.push('level=' + n.level);
    Object.entries(n.attrs || {}).forEach(([k, v]) => parts.push(k + '="' + v + '"'));
    if (n.url) parts.push('url="' + n.url + '"');
    if (n.value !== null && n.value !== undefined) parts.push('value="' + n.value + '"');
    (n.flags || []).forEach(f => parts.push(f));
    return '  '.repeat(n.depth) + parts.join(' ');
  }

  function renderSnapshotsTab() {
    const body = document.getElementById('tab-body');
    const snaps = DATA.snapshots || [];
    if (!snaps.length) {
      body.innerHTML = '<div class="findings-empty">No snapshots captured.</div>';
      return;
    }
    const pickerBtns = snaps.map((s, i) => '<button data-snap="' + i + '"' + (i === 0 ? ' class="active"' : '') + '>#' + s.step_index + ' ' + escape(s.label) + '</button>').join('');
    body.innerHTML = '<div class="snapshot-picker" id="snap-picker">' + pickerBtns + '</div>'
      + '<div class="search-bar"><input id="snap-search" placeholder="Filter snapshot (role, name, url…)"><span class="hint">Esc clears</span></div>'
      + '<div id="snap-body" class="diff"></div>';
    showSnap(0);
    body.querySelectorAll('#snap-picker button').forEach(btn => {
      btn.addEventListener('click', () => {
        body.querySelectorAll('#snap-picker button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        showSnap(parseInt(btn.dataset.snap, 10));
      });
    });
    const input = document.getElementById('snap-search');
    input.addEventListener('input', () => applySnapFilter(input.value));
    input.addEventListener('keydown', e => { if (e.key === 'Escape') { input.value = ''; applySnapFilter(''); } });
  }

  function applySnapFilter(q) {
    q = (q || '').toLowerCase();
    document.querySelectorAll('#snap-body .line-wrap').forEach(wrap => {
      const text = wrap.textContent.toLowerCase();
      wrap.classList.toggle('hidden', !!q && !text.includes(q));
    });
  }

  function showSnap(idx) {
    const s = DATA.snapshots[idx];
    const lines = s.nodes.map(n => '<div class="line-wrap"><div class="line eq">' + escape(nodeRender(n)) + '</div><button class="copy-btn" title="Copy line">copy</button></div>').join('');
    document.getElementById('snap-body').innerHTML = lines;
    wireCopy();
  }

  function renderRawTab() {
    const body = document.getElementById('tab-body');
    const files = DATA.raw_files || [];
    const cards = files.map(f => '<div class="raw-card">'
      + '<div class="name">' + escape(f.name) + '</div>'
      + '<div class="size">' + f.size + ' bytes</div>'
      + '<a href="' + escape(f.href) + '" target="_blank">Open</a></div>').join('');
    body.innerHTML = '<div class="raw-grid">' + cards + '</div>';
  }

  function wireTabs() {
    const bar = document.querySelector('.tab-bar');
    if (!bar) return;
    bar.addEventListener('click', e => {
      const btn = e.target.closest('button[data-tab]');
      if (!btn) return;
      bar.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      prefs.tab = btn.dataset.tab;
      savePrefs();
      renderTab(prefs.tab);
    });
    renderTab(prefs.tab || 'diffs');
  }

  function renderTab(id) {
    if (id === 'raw' && document.body.classList.contains('review')) id = 'diffs';
    if (id === 'diffs') renderDiffsTab();
    else if (id === 'snapshots') renderSnapshotsTab();
    else if (id === 'raw') renderRawTab();
  }

  function wireCollapsed() {
    document.querySelectorAll('.diff .collapsed').forEach(el => {
      el.addEventListener('click', () => {
        const [start, count] = el.dataset.run.split('-').map(Number);
        const replacement = [];
        for (let i = start; i < start + count; i++) {
          const op = currentOps()[i];
          if (op) replacement.push(renderDiffLineWrap(op));
        }
        el.outerHTML = replacement.join('');
        wireCopy();
      });
    });
  }

  function wireCopy() {
    document.querySelectorAll('.copy-btn').forEach(btn => {
      if (btn.dataset.wired) return;
      btn.dataset.wired = '1';
      btn.addEventListener('click', async () => {
        const wrap = btn.closest('.line-wrap');
        const line = wrap && wrap.querySelector('.line');
        if (!line) return;
        try {
          await navigator.clipboard.writeText(line.textContent.trim());
          btn.textContent = 'copied';
          btn.classList.add('copied');
          setTimeout(() => { btn.textContent = 'copy'; btn.classList.remove('copied'); }, 1200);
        } catch (e) {
          btn.textContent = 'err';
        }
      });
    });
  }

  function currentOps() {
    const active = document.querySelector('#diff-picker button.active');
    if (!active) return [];
    return DATA.diffs[parseInt(active.dataset.diff, 10)].ops;
  }

  // Image zoom / pan modal.
  const zoom = { scale: 1, x: 0, y: 0, startX: 0, startY: 0, dragging: false, naturalW: 0, naturalH: 0 };

  function wireImageZoom() {
    const modal = document.getElementById('img-modal');
    const img = document.getElementById('modal-img');
    const wrap = document.getElementById('zoom-wrap');
    const hud = document.getElementById('zoom-hud');
    const close = document.getElementById('zoom-close');

    window.openModal = function (src) {
      img.src = src;
      img.onload = () => {
        zoom.naturalW = img.naturalWidth;
        zoom.naturalH = img.naturalHeight;
        const vw = window.innerWidth * 0.94;
        const vh = window.innerHeight * 0.88;
        zoom.scale = Math.min(vw / zoom.naturalW, vh / zoom.naturalH, 1);
        zoom.x = (window.innerWidth - zoom.naturalW * zoom.scale) / 2;
        zoom.y = (window.innerHeight - zoom.naturalH * zoom.scale) / 2;
        applyZoom();
      };
      modal.classList.add('open');
    };

    function closeModal() { modal.classList.remove('open'); img.src = ''; }
    close.addEventListener('click', closeModal);
    modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && modal.classList.contains('open')) closeModal(); });

    wrap.addEventListener('wheel', e => {
      if (!modal.classList.contains('open')) return;
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const newScale = Math.max(0.1, Math.min(8, zoom.scale * factor));
      const rect = wrap.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      zoom.x -= cx * (newScale / zoom.scale - 1);
      zoom.y -= cy * (newScale / zoom.scale - 1);
      zoom.scale = newScale;
      applyZoom();
    }, { passive: false });

    wrap.addEventListener('mousedown', e => {
      zoom.dragging = true;
      zoom.startX = e.clientX - zoom.x;
      zoom.startY = e.clientY - zoom.y;
      modal.classList.add('dragging');
    });
    window.addEventListener('mousemove', e => {
      if (!zoom.dragging) return;
      zoom.x = e.clientX - zoom.startX;
      zoom.y = e.clientY - zoom.startY;
      applyZoom();
    });
    window.addEventListener('mouseup', () => {
      zoom.dragging = false;
      modal.classList.remove('dragging');
    });

    function applyZoom() {
      wrap.style.transform = 'translate(' + zoom.x + 'px,' + zoom.y + 'px)';
      img.style.transform = 'scale(' + zoom.scale + ')';
      hud.textContent = zoom.scale.toFixed(2) + '×  ·  drag to pan · scroll to zoom';
    }
  }

  function wireToolbar() {
    const themeBtn = document.getElementById('theme-btn');
    const modeBtn = document.getElementById('mode-btn');
    themeBtn.textContent = document.body.classList.contains('light') ? '☀' : '☾';
    modeBtn.textContent = document.body.classList.contains('review') ? 'review mode' : 'dev mode';
    modeBtn.classList.toggle('active', document.body.classList.contains('review'));
    themeBtn.addEventListener('click', () => {
      const light = document.body.classList.toggle('light');
      prefs.theme = light ? 'light' : 'dark';
      themeBtn.textContent = light ? '☀' : '☾';
      savePrefs();
    });
    modeBtn.addEventListener('click', () => {
      const review = document.body.classList.toggle('review');
      prefs.mode = review ? 'review' : 'dev';
      modeBtn.textContent = review ? 'review mode' : 'dev mode';
      modeBtn.classList.toggle('active', review);
      savePrefs();
      renderTab(prefs.tab || 'diffs');
    });
  }

  function applyTheme(t) {
    if (t === 'light') document.body.classList.add('light');
    else if (t !== 'dark' && window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      document.body.classList.add('light');
    }
  }

  function applyMode(m) {
    if (m === 'review') document.body.classList.add('review');
  }

  function wireSideNav() {
    const nav = document.getElementById('side-nav');
    const sections = [
      ['sec-verdict', 'V', 'Verdict'],
      ['sec-goal', 'G', 'Goal'],
      ['sec-narrative', 'N', 'Narrative'],
      ['sec-whyfail', 'W', 'Why fail'],
      ['sec-evidence', 'E', 'Evidence'],
      ['sec-timeline', 'T', 'Timeline'],
      ['sec-findings', 'F', 'Findings'],
      ['sec-detail', 'D', 'Detail'],
    ];
    const html = sections.filter(([id]) => document.getElementById(id)).map(([id, letter, label]) =>
      '<a href="#' + id + '" data-target="' + id + '">' + letter + '<span class="tip">' + label + '</span></a>'
    ).join('');
    nav.innerHTML = html;
    nav.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', e => {
        e.preventDefault();
        const el = document.getElementById(a.dataset.target);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
    const io = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        const link = nav.querySelector('a[data-target="' + entry.target.id + '"]');
        if (!link) return;
        if (entry.isIntersecting) link.classList.add('active');
        else link.classList.remove('active');
      });
    }, { rootMargin: '-30% 0px -60% 0px' });
    sections.forEach(([id]) => {
      const el = document.getElementById(id);
      if (el) io.observe(el);
    });
  }

  function escape(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function loadPrefs() {
    try { return JSON.parse(localStorage.getItem('webwitness-report-prefs') || '{}'); }
    catch (e) { return {}; }
  }

  function savePrefs() {
    try { localStorage.setItem('webwitness-report-prefs', JSON.stringify(prefs)); } catch (e) {}
  }
})();
"""


_INDEX_JS = r"""
(function () {
  const DATA = JSON.parse(document.getElementById('index-data').textContent);
  const app = document.getElementById('app');
  const prefs = loadPrefs();

  applyTheme(prefs.theme);
  render();

  function render() {
    const allHosts = (DATA.runs || []).map(r => r.target_host).concat((DATA.suites || []).map(s => s.target_host));
    const hosts = Array.from(new Set(allHosts)).filter(h => h).sort();
    const hostOptions = ['<option value="">All hosts</option>'].concat(hosts.map(h => '<option' + (prefs.host === h ? ' selected' : '') + '>' + escape(h) + '</option>')).join('');
    const mkSeg = (id, label) => '<button data-verdict="' + id + '"' + ((prefs.verdict || 'all') === id ? ' class="active"' : '') + '>' + label + '</button>';
    app.innerHTML =
        '<div class="toolbar">'
      + '<div class="brand"><span style="font-size:18px">◉</span><span>webwitness runs <span class="tagline">website review index</span></span></div>'
      + '<button class="tbtn" id="theme-btn">☾</button>'
      + '</div>'
      + '<div class="counts" id="counts"></div>'
      + '<section class="panel">'
      + '<div class="filters">'
      + '<div class="seg">' + mkSeg('all', 'All') + mkSeg('pass', 'PASS') + mkSeg('fail', 'FAIL') + '</div>'
      + '<select id="host-filter">' + hostOptions + '</select>'
      + '<input id="goal-search" placeholder="Search goal / run id…" value="' + escape(prefs.query || '') + '">'
      + '<div class="seg" style="margin-left:auto"><button data-view="flat"' + ((prefs.view || 'flat') === 'flat' ? ' class="active"' : '') + '>Flat</button><button data-view="clustered"' + (prefs.view === 'clustered' ? ' class="active"' : '') + '>Clustered</button></div>'
      + '</div>'
      + '<div id="view-body"></div>'
      + '</section>';
    document.querySelectorAll('[data-verdict]').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('[data-verdict]').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      prefs.verdict = b.dataset.verdict;
      savePrefs();
      redraw();
    }));
    document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('[data-view]').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      prefs.view = b.dataset.view;
      savePrefs();
      redraw();
    }));
    document.getElementById('host-filter').addEventListener('change', e => {
      prefs.host = e.target.value;
      savePrefs();
      redraw();
    });
    document.getElementById('goal-search').addEventListener('input', e => {
      prefs.query = e.target.value;
      savePrefs();
      redraw();
    });
    document.getElementById('theme-btn').addEventListener('click', () => {
      const light = document.body.classList.toggle('light');
      prefs.theme = light ? 'light' : 'dark';
      document.getElementById('theme-btn').textContent = light ? '☀' : '☾';
      savePrefs();
    });
    document.getElementById('theme-btn').textContent = document.body.classList.contains('light') ? '☀' : '☾';
    redraw();
  }

  function redraw() {
    const runs = filtered();
    const suites = filteredSuites();
    const diffs = (DATA.diffs || []);
    const body = document.getElementById('view-body');
    const suiteHtml = (suites || []).map(renderSuite).join('');
    const diffHtml = diffs.length ? renderDiffsPanel(diffs) : '';
    let runsHtml;
    if (prefs.view === 'clustered') {
      runsHtml = renderClusters(runs);
    } else {
      runsHtml = renderTable(runs);
    }
    body.innerHTML = suiteHtml + diffHtml + runsHtml;
    const totalSuites = (DATA.suites || []).length;
    const totalRuns = (DATA.runs || []).length;
    const totalDiffs = diffs.length;
    let counts = runs.length + ' of ' + totalRuns + ' runs shown';
    if (totalSuites) {
      counts = (suites || []).length + ' of ' + totalSuites + ' suites · ' + counts;
    }
    if (totalDiffs) {
      counts = totalDiffs + ' diff' + (totalDiffs === 1 ? '' : 's') + ' · ' + counts;
    }
    document.getElementById('counts').textContent = counts;
  }

  function renderDiffsPanel(diffs) {
    const rows = diffs.map(d => {
      const kind = d.first_divergence_kind || 'none';
      const kindLabel = kind === 'none'
        ? 'identical'
        : (kind === 'matcher_only' ? 'verdict only' : (kind + (d.first_divergence_step ? ' @' + d.first_divergence_step : '')));
      const verdictDelta = d.verdict_changed
        ? escape(d.verdict_a) + ' → ' + escape(d.verdict_b)
        : escape(d.verdict_a);
      const findingsDelta = (d.added_findings || d.removed_findings)
        ? '+' + d.added_findings + ' / -' + d.removed_findings
        : '—';
      return '<tr>'
        + '<td><span style="font-family:var(--mono);font-size:12px">' + escape(d.date) + '</span></td>'
        + '<td style="font-family:var(--mono);font-size:12px">' + escape(d.run_a_id) + ' → ' + escape(d.run_b_id) + '</td>'
        + '<td>' + escape(kindLabel) + '</td>'
        + '<td>' + verdictDelta + '</td>'
        + '<td>' + findingsDelta + '</td>'
        + '<td><a href="' + escape(d.diff_href) + '">open →</a></td>'
        + '</tr>';
    }).join('');
    return '<div class="diffs-panel">'
      + '<div class="diffs-head"><span class="label">Diffs</span><span class="tagline">regression alerts</span></div>'
      + '<table class="diffs-table"><thead><tr>'
      + '<th>Generated</th><th>A → B</th><th>First divergence</th><th>Verdict</th><th>Findings ±</th><th>Open</th>'
      + '</tr></thead><tbody>' + rows + '</tbody></table>'
      + '</div>';
  }

  function renderSuite(s) {
    const sum = s.verdict_summary || {};
    const pass = sum.PASS || 0;
    const unclear = sum.UNCLEAR || 0;
    const fail = sum.FAIL || 0;
    const personas = s.personas || [];
    const files = s.files || [];
    const viewports = s.viewports || [];
    const hasViewports = !!s.has_viewports && viewports.length > 0;
    // P7: when the suite has a viewport axis, rows are (file, viewport)
    // pairs; otherwise rows are just files (legacy shape). Index cells
    // by `file|viewport|persona` so multi-viewport suites don't collide.
    const cells = {};
    (s.journeys || []).forEach(j => {
      const vp = j.viewport || '';
      cells[j.file + '|' + vp + '|' + j.persona] = j;
    });
    const headerCols = personas.map(p => '<th class="persona-col">' + escape(p) + '</th>').join('');
    const rowKeys = hasViewports
      ? files.flatMap(f => viewports.map(vp => ({file: f, viewport: vp})))
      : files.map(f => ({file: f, viewport: ''}));
    const rows = rowKeys.map(rk => {
      const cellHtml = personas.map(p => {
        const j = cells[rk.file + '|' + rk.viewport + '|' + p];
        if (!j) return '<td class="cell empty-cell">—</td>';
        const cls = j.verdict === 'PASS' ? 'pass' : j.verdict === 'UNCLEAR' ? 'unclear' : 'fail';
        const tip = (j.matcher || '') + ' · ' + (j.duration_ms || 0) + 'ms';
        return '<td class="cell"><a class="verdict-link ' + cls + '" href="' + escape(j.report_href) + '" title="' + escape(tip) + '">' + escape(j.verdict) + '</a></td>';
      }).join('');
      const fileLabel = hasViewports
        ? escape(rk.file) + ' <span class="viewport-pill">' + escape(rk.viewport) + '</span>'
        : escape(rk.file);
      return '<tr><td class="file-cell">' + fileLabel + '</td>' + cellHtml + '</tr>';
    }).join('');
    const viewportBadge = hasViewports
      ? '<span class="viewport-axis-badge" title="P7 device matrix: each journey runs once per viewport. Cells link to per-(journey × persona × viewport) report.">' + viewports.length + ' viewports</span>'
      : '';
    const sd = s.suite_diff;
    const suiteDiffBadge = sd
      ? (function () {
          const flipped = sd.verdict_changed || 0;
          const total = sd.compared_total || 0;
          const baseline = sd.baseline_viewport || 'baseline';
          const cls = flipped > 0 ? 'suite-diff-badge suite-diff-badge--alert'
            : 'suite-diff-badge suite-diff-badge--stable';
          const label = flipped > 0
            ? flipped + '/' + total + ' verdict-changed'
            : total + '/' + total + ' verdict-stable';
          const tip = 'suite-diff vs ' + baseline + ': ' + flipped
            + ' of ' + total + ' compared cells flipped verdict.'
            + (sd.matcher_changed ? ' ' + sd.matcher_changed + ' matcher-changed.' : '')
            + ' Click to open the first per-pair diff.';
          return sd.first_diff_href
            ? '<a class="' + cls + '" href="' + escape(sd.first_diff_href) + '" title="' + escape(tip) + '">' + escape(label) + '</a>'
            : '<span class="' + cls + '" title="' + escape(tip) + '">' + escape(label) + '</span>';
        })()
      : '';
    return '<div class="suite">'
      + '<div class="suite-head">'
      + '<span class="label">' + escape(s.label) + '</span>'
      + '<span class="target">' + escape(s.target) + '</span>'
      + '<span class="alpha-badge" title="v0.3 alpha personas: LLM-framing only. Real cookie/storage seeding deferred to v0.4 per BRIEF-032. Persona variants of the same journey may not produce distinct traces.">v0.3α framing-only personas</span>'
      + viewportBadge
      + suiteDiffBadge
      + '<span class="summary">'
      + '<span class="pass">PASS ' + pass + '</span> · '
      + '<span class="unclear">UNCLEAR ' + unclear + '</span> · '
      + '<span class="fail">FAIL ' + fail + '</span> · '
      + escape(s.date)
      + '</span></div>'
      + '<table class="matrix"><thead><tr><th>Journey</th>' + headerCols + '</tr></thead>'
      + '<tbody>' + rows + '</tbody></table>'
      + '</div>';
  }

  function filteredSuites() {
    const h = prefs.host || '';
    const q = (prefs.query || '').toLowerCase();
    return (DATA.suites || []).filter(s => {
      if (h && s.target_host !== h) return false;
      if (q) {
        const hay = (s.label + ' ' + s.target + ' ' + (s.files || []).join(' ')).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function renderTable(runs) {
    return '<table class="runs-table"><thead><tr>'
      + '<th>Run</th><th>Goal</th><th>Host</th><th>Verdict</th><th>Steps</th><th>Findings</th><th>Open</th>'
      + '</tr></thead><tbody>'
      + runs.map(r => '<tr>'
        + '<td><span style="font-family:var(--mono);font-size:12px">' + escape(r.date) + '</span></td>'
        + '<td class="goal-cell"><span class="truncate">' + escape(r.goal) + '</span></td>'
        + '<td style="font-family:var(--mono);font-size:12px">' + escape(r.target_host) + '</td>'
        + '<td class="verdict-cell ' + (r.pass ? 'pass' : 'fail') + '">' + (r.pass ? '✓ PASS' : '✗ FAIL') + '</td>'
        + '<td>' + r.steps + '</td>'
        + '<td>' + r.findings + '</td>'
        + '<td><a href="' + escape(r.report_href) + '">open →</a></td>'
        + '</tr>').join('')
      + '</tbody></table>';
  }

  function renderClusters(runs) {
    const clusters = {};
    runs.forEach(r => {
      const key = clusterKey(r.goal);
      if (!clusters[key]) clusters[key] = { goal: r.goal, host: r.target_host, runs: [] };
      clusters[key].runs.push(r);
    });
    const keys = Object.keys(clusters).sort((a, b) => clusters[b].runs.length - clusters[a].runs.length);
    if (!keys.length) return '<div class="findings-empty">No runs match filters.</div>';
    return keys.map(k => {
      const c = clusters[k];
      c.runs.sort((a, b) => a.date.localeCompare(b.date));
      const passes = c.runs.filter(r => r.pass).length;
      const fails = c.runs.length - passes;
      const pills = c.runs.map(r => '<a class="pill ' + (r.pass ? 'pass' : 'fail') + '" href="' + escape(r.report_href) + '" title="' + escape(r.date + ' — ' + (r.pass ? 'PASS' : 'FAIL')) + '">' + (r.pass ? '✓' : '✗') + '</a>').join('<span class="arrow">›</span>');
      return '<div class="cluster">'
        + '<div class="cluster-goal">' + escape(c.goal) + '</div>'
        + '<div class="cluster-meta">' + escape(c.host) + ' · ' + c.runs.length + ' runs · ' + passes + ' PASS · ' + fails + ' FAIL</div>'
        + '<div class="trend">' + pills + '</div>'
        + '</div>';
    }).join('');
  }

  function clusterKey(goal) {
    return (goal || '').toLowerCase().replace(/\s+/g, ' ').trim().slice(0, 60);
  }

  function filtered() {
    const v = prefs.verdict || 'all';
    const h = prefs.host || '';
    const q = (prefs.query || '').toLowerCase();
    return (DATA.runs || []).filter(r => {
      if (v === 'pass' && !r.pass) return false;
      if (v === 'fail' && r.pass) return false;
      if (h && r.target_host !== h) return false;
      if (q && !(r.goal.toLowerCase().includes(q) || r.run_id.toLowerCase().includes(q))) return false;
      return true;
    });
  }

  function applyTheme(t) {
    if (t === 'light') document.body.classList.add('light');
    else if (t !== 'dark' && window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      document.body.classList.add('light');
    }
  }

  function escape(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function loadPrefs() { try { return JSON.parse(localStorage.getItem('webwitness-index-prefs') || '{}'); } catch (e) { return {}; } }
  function savePrefs() { try { localStorage.setItem('webwitness-index-prefs', JSON.stringify(prefs)); } catch (e) {} }
})();
"""
