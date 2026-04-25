"""HTML render for a journey-diff result (P3 regression alerts).

Pairs with ``reader.report`` (per-run report) and ``reader.diff`` (parsed-
snapshot LCS used inside a single run). This module renders the
journey-vs-journey diff produced by ``journeys.diff.diff_runs``.

Generates ``diff.html`` next to ``diff-result.json`` in a diff dir. The
page header shows both runs side-by-side; the step table walks the merged
sequence with the divergent step highlighted in red; the findings section
shows new findings highlighted in yellow and removed findings struck
through.

Reuses the ``_STYLE`` block from ``reader.template`` so the diff page
picks up the same dark/light tokens, pills and panels as the per-run
report.
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path

from .template import _STYLE


def generate(diff_dir: Path) -> Path:
    """Render diff.html from diff-result.json in ``diff_dir``. Returns the path."""
    diff_dir = Path(diff_dir)
    payload_path = diff_dir / "diff-result.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    out = _render(payload)
    out_path = diff_dir / "diff.html"
    out_path.write_text(out, encoding="utf-8")
    return out_path


def _render(payload: dict) -> str:
    title = f"webwitness diff — {_html.escape(payload['diff_id'])}"
    return (
        _DIFF_HTML
        .replace("__TITLE__", title)
        .replace("__STYLE__", _STYLE + _DIFF_STYLE)
        .replace("__BODY__", _body_html(payload))
        .replace("__DATA_JSON__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    )


# ---------------------------------------------------------------------------
# Body fragments
# ---------------------------------------------------------------------------

def _body_html(payload: dict) -> str:
    parts: list[str] = []
    parts.append(_header_html(payload))
    parts.append(_summary_panel(payload))
    if payload.get("journey_changed"):
        parts.append(_journey_warning())
    parts.append(_steps_panel(payload))
    parts.append(_findings_panel(payload))
    return "\n".join(parts)


def _verdict_class(v: str | None) -> str:
    if v == "PASS":
        return "pass"
    if v == "FAIL":
        return "fail"
    return "unclear"


def _run_card(side: str, run: dict) -> str:
    e = _html.escape
    rid = e(str(run.get("run_id") or "?"))
    persona = e(str(run.get("persona") or "—"))
    matcher = e(str(run.get("matcher") or "—"))
    target = e(str(run.get("target") or "—"))
    verdict = run.get("verdict") or "FAIL"
    vclass = _verdict_class(verdict)
    href = e(run.get("report_href") or "#")
    iters = e(str(run.get("iterations") or "—"))
    clicks = e(str(run.get("clicks_used") or "—"))
    duration = e(str(run.get("duration_ms") or "—"))
    return (
        f'<div class="diff-run side-{e(side)}">'
        f'  <div class="diff-run-head">'
        f'    <span class="diff-run-side">{e(side.upper())}</span>'
        f'    <span class="run-pill">{rid}</span>'
        f'    <span class="verdict-pill v-{vclass}">{e(verdict)}</span>'
        f'  </div>'
        f'  <div class="diff-run-meta">'
        f'    <div><span class="lbl">persona</span> {persona}</div>'
        f'    <div><span class="lbl">matcher</span> <code>{matcher}</code></div>'
        f'    <div><span class="lbl">target</span> <code>{target}</code></div>'
        f'    <div><span class="lbl">iters</span> {iters} '
        f'<span class="lbl">clicks</span> {clicks} '
        f'<span class="lbl">duration_ms</span> {duration}</div>'
        f'  </div>'
        f'  <div class="diff-run-link"><a href="{href}">open report →</a></div>'
        f'</div>'
    )


def _header_html(payload: dict) -> str:
    diff_id = _html.escape(payload["diff_id"])
    when = _html.escape(payload.get("generated_at", ""))
    return (
        '<div class="toolbar">'
        '  <div class="brand">'
        '    <span>webwitness diff</span>'
        f'    <span class="tagline">{diff_id}</span>'
        '  </div>'
        '  <button class="tbtn" id="theme-toggle" type="button">theme</button>'
        '</div>'
        f'<div class="diff-generated">generated {when}</div>'
        '<div class="diff-runs">'
        f'  {_run_card("a", payload["run_a"])}'
        f'  {_run_card("b", payload["run_b"])}'
        '</div>'
    )


def _summary_panel(payload: dict) -> str:
    fd = payload.get("first_divergence") or {}
    kind = fd.get("kind") or "none"
    idx = fd.get("step_index")
    e = _html.escape

    if kind == "none":
        msg = "Sequences are identical at every step. Verdicts and matchers also match."
        css = "summary-match"
    elif kind == "matcher_only":
        msg = (
            "Step sequences are identical, but the verdict or matcher changed. "
            "The same path through the site produced a different judgement."
        )
        css = "summary-matcher"
    elif kind == "length":
        msg = f"First divergence: step {idx} — one run had no step at this index (sequence-length mismatch)."
        css = "summary-length"
    else:
        msg = f"First divergence: step {idx} ({kind})."
        css = "summary-divergent"

    badges: list[str] = []
    if payload.get("verdict_changed"):
        badges.append('<span class="badge-pill chg">verdict changed</span>')
    if payload.get("matcher_changed"):
        badges.append('<span class="badge-pill chg">matcher changed</span>')
    fdiff = payload.get("findings_diff") or {}
    n_added = len(fdiff.get("added") or [])
    n_removed = len(fdiff.get("removed") or [])
    if n_added:
        badges.append(f'<span class="badge-pill add">+{n_added} new finding{"s" if n_added != 1 else ""}</span>')
    if n_removed:
        badges.append(f'<span class="badge-pill rem">-{n_removed} removed finding{"s" if n_removed != 1 else ""}</span>')
    if not badges:
        badges.append('<span class="badge-pill eq">no differences</span>')

    return (
        '<div class="panel diff-summary-panel">'
        '  <h2>Summary</h2>'
        f'  <div class="diff-summary-headline {e(css)}">{e(msg)}</div>'
        f'  <div class="diff-summary-badges">{"".join(badges)}</div>'
        '</div>'
    )


def _journey_warning() -> str:
    return (
        '<div class="panel diff-warn">'
        '  <h2>Heads-up</h2>'
        '  <div>The two runs use different journey definitions '
        '(intent / target / persona / success differ). The step diff still works, '
        'but step-by-step alignment may be misleading.</div>'
        '</div>'
    )


def _steps_panel(payload: dict) -> str:
    rows = payload.get("step_table") or []
    fd = payload.get("first_divergence") or {}
    first_idx = fd.get("step_index")
    parts: list[str] = ['<div class="panel">', '<h2>Step-by-step</h2>',
                        '<table class="diff-steps"><thead><tr>',
                        '<th class="idx">#</th>',
                        '<th class="side-a">A</th>',
                        '<th class="side-b">B</th>',
                        '<th class="verdict">·</th>',
                        '</tr></thead><tbody>']
    for r in rows:
        is_first = (r["idx"] == first_idx)
        klass = "row-divergent" if r["divergent"] else "row-match"
        if is_first:
            klass += " row-first-divergence"
        parts.append(f'<tr class="{klass}">')
        parts.append(f'<td class="idx">{r["idx"]}</td>')
        parts.append(f'<td class="side-a">{_step_cell(r.get("a"))}</td>')
        parts.append(f'<td class="side-b">{_step_cell(r.get("b"))}</td>')
        parts.append(f'<td class="verdict">{_kind_pill(r["kind"], is_first)}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')
    return "".join(parts)


def _step_cell(step: dict | None) -> str:
    if not step:
        return '<span class="diff-step-empty">—</span>'
    e = _html.escape
    action = e(str(step.get("action") or "?"))
    target_role = step.get("target_role")
    target_name = step.get("target_name")
    url = step.get("url") or ""
    head = f'<span class="diff-step-action">{action}</span>'
    if target_name:
        role_str = f' [{e(str(target_role))}]' if target_role else ""
        head += f' <span class="diff-step-target">→ {e(str(target_name))}{role_str}</span>'
    rationale = step.get("rationale") or ""
    rationale_short = rationale.strip().replace("\n", " ")
    if len(rationale_short) > 220:
        rationale_short = rationale_short[:217] + "…"
    return (
        f'<div class="diff-step">'
        f'  <div class="diff-step-head">{head}</div>'
        f'  <div class="diff-step-url"><code>{e(url)}</code></div>'
        f'  <div class="diff-step-rat">{e(rationale_short)}</div>'
        f'</div>'
    )


def _kind_pill(kind: str, is_first: bool) -> str:
    e = _html.escape
    if kind == "match":
        return '<span class="kind-pill kind-match">=</span>'
    if kind in ("missing_a", "missing_b"):
        return f'<span class="kind-pill kind-length">{e(kind)}</span>'
    klass = f"kind-{kind}"
    extra = " kind-first" if is_first else ""
    return f'<span class="kind-pill {klass}{extra}">{e(kind)}</span>'


def _findings_panel(payload: dict) -> str:
    fd = payload.get("findings_diff") or {}
    added = fd.get("added") or []
    removed = fd.get("removed") or []
    shared = fd.get("shared") or []
    if not (added or removed or shared):
        return (
            '<div class="panel">'
            '<h2>Findings</h2>'
            '<div class="findings-empty">No findings recorded in either run.</div>'
            '</div>'
        )
    parts: list[str] = ['<div class="panel">', '<h2>Findings</h2>',
                        '<ul class="findings-list diff-findings">']
    for f in added:
        parts.append(_finding_li(f, status="added"))
    for f in removed:
        parts.append(_finding_li(f, status="removed"))
    for f in shared:
        parts.append(_finding_li(f, status="shared"))
    parts.append('</ul></div>')
    return "".join(parts)


def _finding_li(f: dict, status: str) -> str:
    e = _html.escape
    sev = (f.get("severity") or "info").lower()
    rule_id = e(str(f.get("rule_id") or "?"))
    desc = e(str(f.get("description") or ""))
    node = e(str(f.get("node_repr") or ""))
    pill_label = {"added": "new", "removed": "gone", "shared": "shared"}.get(status, status)
    return (
        f'<li class="{sev} status-{status}">'
        f'  <span class="status-pill status-{status}">{e(pill_label)}</span>'
        f'  <span class="sev-pill">{e(sev)}</span>'
        f'  <span class="fid">{rule_id}</span>'
        f'  <span class="desc">{desc}</span>'
        f'  <span class="node">{node}</span>'
        f'</li>'
    )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_DIFF_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__STYLE__</style>
</head>
<body>
<div id="app">__BODY__</div>
<script id="diff-data" type="application/json">__DATA_JSON__</script>
<script>
(function () {
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;
  var saved = localStorage.getItem('ww-theme');
  if (saved === 'light') document.body.classList.add('light');
  btn.addEventListener('click', function () {
    document.body.classList.toggle('light');
    localStorage.setItem('ww-theme', document.body.classList.contains('light') ? 'light' : 'dark');
  });
})();
</script>
</body>
</html>
"""


_DIFF_STYLE = r"""
.diff-generated {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 12px;
  margin: -8px 0 14px;
}
.diff-runs {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}
.diff-run {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
}
.diff-run.side-a { border-left: 3px solid var(--info); }
.diff-run.side-b { border-left: 3px solid var(--accent); }
.diff-run-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.diff-run-side {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--muted);
  text-transform: uppercase;
}
.run-pill {
  background: var(--panel-2);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 2px 8px;
  font-family: var(--mono);
  font-size: 12px;
}
.verdict-pill {
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #fff;
}
.verdict-pill.v-pass { background: var(--pass); }
.verdict-pill.v-fail { background: var(--fail); }
.verdict-pill.v-unclear { background: var(--warn); }
.diff-run-meta {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--fg);
  display: grid;
  gap: 4px;
}
.diff-run-meta .lbl { color: var(--muted); font-weight: 600; margin-right: 4px; }
.diff-run-meta code { background: var(--panel-2); padding: 1px 5px; border-radius: 3px; word-break: break-all; }
.diff-run-link { margin-top: 8px; font-size: 12px; }
.diff-summary-panel .diff-summary-headline {
  font-size: 15px;
  padding: 10px 12px;
  border-radius: 6px;
  margin-bottom: 10px;
}
.diff-summary-headline.summary-match { background: var(--add-bg); color: var(--add); }
.diff-summary-headline.summary-matcher { background: var(--chg-bg); color: var(--chg); }
.diff-summary-headline.summary-length { background: var(--rem-bg); color: var(--rem); }
.diff-summary-headline.summary-divergent { background: var(--rem-bg); color: var(--rem); }
.diff-summary-badges { display: flex; flex-wrap: wrap; gap: 6px; }
.badge-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-family: var(--mono);
}
.badge-pill.eq { background: var(--panel-2); color: var(--muted); border: 1px solid var(--border); }
.badge-pill.add { background: var(--add-bg); color: var(--add); border: 1px solid var(--add); }
.badge-pill.rem { background: var(--rem-bg); color: var(--rem); border: 1px solid var(--rem); }
.badge-pill.chg { background: var(--chg-bg); color: var(--chg); border: 1px solid var(--chg); }
.diff-warn {
  border-color: var(--warn);
  background: var(--chg-bg);
}
table.diff-steps {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
table.diff-steps th,
table.diff-steps td {
  text-align: left;
  vertical-align: top;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  overflow-wrap: anywhere;
}
table.diff-steps th {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  font-weight: 600;
}
table.diff-steps td.idx,
table.diff-steps th.idx { width: 36px; text-align: right; color: var(--muted); font-family: var(--mono); }
table.diff-steps td.verdict,
table.diff-steps th.verdict { width: 80px; text-align: center; }
table.diff-steps td.side-a,
table.diff-steps td.side-b { width: 42%; }
table.diff-steps tr.row-match td { background: transparent; }
table.diff-steps tr.row-divergent { background: var(--rem-bg); }
table.diff-steps tr.row-first-divergence {
  background: var(--rem-bg);
  outline: 2px solid var(--fail);
  outline-offset: -2px;
}
.diff-step .diff-step-head {
  font-family: var(--mono);
  font-size: 12.5px;
}
.diff-step .diff-step-action { font-weight: 700; color: var(--fg); }
.diff-step .diff-step-target { color: var(--muted); }
.diff-step .diff-step-url {
  font-family: var(--mono);
  font-size: 11.5px;
  color: var(--muted);
  margin-top: 3px;
}
.diff-step .diff-step-url code { background: var(--panel-2); padding: 1px 4px; border-radius: 3px; word-break: break-all; }
.diff-step .diff-step-rat {
  font-style: italic;
  font-size: 12px;
  color: var(--fg);
  margin-top: 4px;
  line-height: 1.4;
}
.diff-step-empty {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 12px;
  font-style: italic;
}
.kind-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
}
.kind-pill.kind-match { background: var(--panel-2); color: var(--muted); }
.kind-pill.kind-action,
.kind-pill.kind-target_name,
.kind-pill.kind-url { background: var(--rem-bg); color: var(--rem); border: 1px solid var(--rem); }
.kind-pill.kind-length,
.kind-pill.kind-missing_a,
.kind-pill.kind-missing_b { background: var(--chg-bg); color: var(--chg); border: 1px solid var(--chg); }
.kind-pill.kind-first { box-shadow: 0 0 0 2px var(--fail); }
.diff-findings li {
  display: grid;
  grid-template-columns: auto auto auto 1fr;
  gap: 6px 10px;
  align-items: baseline;
}
.diff-findings li .desc { grid-column: 1 / -1; }
.diff-findings li .node { grid-column: 1 / -1; }
.diff-findings li.status-removed .desc,
.diff-findings li.status-removed .fid { text-decoration: line-through; opacity: 0.7; }
.diff-findings li.status-added { background: var(--chg-bg); }
.status-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-right: 4px;
}
.status-pill.status-added { background: var(--warn); color: #fff; }
.status-pill.status-removed { background: var(--rem); color: #fff; }
.status-pill.status-shared { background: var(--panel-2); color: var(--muted); border: 1px solid var(--border); }
@media (max-width: 760px) {
  .diff-runs { grid-template-columns: 1fr; }
  table.diff-steps td.side-a,
  table.diff-steps td.side-b { width: auto; }
  table.diff-steps,
  table.diff-steps thead,
  table.diff-steps tbody,
  table.diff-steps tr,
  table.diff-steps th,
  table.diff-steps td { display: block; }
  table.diff-steps thead { display: none; }
  table.diff-steps tr { border-bottom: 1px solid var(--border); padding: 6px 0; }
}
"""


__all__ = ["generate"]
