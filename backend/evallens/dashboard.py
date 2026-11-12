"""Interactive dashboard for EvalLens (v3).

``render_dashboard(runs, latest)`` returns a single self-contained HTML
page. Server-rendered first paint (KPI cards, trend chart, question
explorer for the latest full run), then vanilla JavaScript takes over —
no framework, no extra dependencies:

- Run switcher: pick any recorded run; other runs load on demand from
  ``/api/eval/runs/{id}`` and the whole page re-renders from that run.
- Clickable KPI cards: click a metric to sort the explorer by it, worst
  first; click again to clear.
- Question explorer: all 67 questions with filters (document, kind,
  pass/fail, text search), sortable columns, and expandable rows showing
  the question, expected vs actual answer, citations, retrieved pages,
  per-metric scores with their method, and latency.
- Per-document panels: Aurora / Meridian / Kaveri means, computed from
  the run's own rows (None scores ignored, same as the runner).
- Interactive trend chart: hover a point for the full run summary,
  click it to load that run.

All numbers come from real run JSON files — nothing is invented here.
"""

import html
import json
from pathlib import Path

_THRESHOLDS_PATH = Path(__file__).resolve().parent / "thresholds.json"


def _load_thresholds(embedded: dict | None) -> dict:
    """Live thresholds from thresholds.json (the gate's source of truth).

    Run JSONs embed a snapshot of the thresholds at run time, which goes
    stale when the gate is tightened — so prefer the config file and fall
    back to the embedded snapshot only if the file is missing.
    """
    try:
        with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "judge" in data:
            return data
    except Exception:
        pass
    return embedded or {}


METRIC_KEYS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
METRIC_LABELS = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer relevancy",
    "context_precision": "Context precision",
    "context_recall": "Context recall",
}
METRIC_SHORT = {
    "faithfulness": "Faith.",
    "answer_relevancy": "Relev.",
    "context_precision": "Prec.",
    "context_recall": "Recall",
}
DOC_ORDER = ("aurora", "meridian", "kaveri")
DOC_LABELS = {"aurora": "Aurora", "meridian": "Meridian", "kaveri": "Kaveri"}


# Score colours: green >= 0.90, amber 0.70–0.90, red < 0.70.
def _score_color(value) -> str:
    if value is None:
        return "#9ca3af"
    if value >= 0.90:
        return "#16a34a"
    if value >= 0.70:
        return "#d97706"
    return "#dc2626"


def _fmt(value) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "—"


def _metric_score(row: dict, key: str):
    entry = row.get(key) or {}
    value = entry.get("score") if isinstance(entry, dict) else None
    return value if isinstance(value, (int, float)) else None


def _is_failing(row: dict) -> tuple[bool, list[str], bool]:
    """(failing, low_metric_keys, behaviour_bad) — same rule as the gate notes."""
    bad = [key for key in METRIC_KEYS if (_metric_score(row, key) or 1.0) < 0.7]
    behaviour_bad = row.get("kind") in ("unanswerable", "adversarial") and not row.get("refused")
    return (bool(bad) or behaviour_bad, bad, behaviour_bad)


def _gate_status(latest: dict, thresholds: dict) -> tuple[bool, list[str]]:
    """(passed, failures) for the latest run against its mode's thresholds."""
    mode = "judge" if latest.get("judge_mode") else "deterministic"
    want = thresholds.get(mode, {}) if isinstance(thresholds, dict) else {}
    agg = latest.get("aggregates") or {}
    failures = []
    for key in METRIC_KEYS:
        threshold = want.get(key)
        value = agg.get(key)
        if threshold is not None and value is not None and value < threshold:
            failures.append(f"{METRIC_LABELS[key]} {value:.3f} < {threshold}")
    refusal_want = want.get("refusal_accuracy")
    refusal = latest.get("refusal_accuracy")
    if refusal_want is not None and refusal is not None and refusal < refusal_want:
        failures.append(f"Refusal accuracy {refusal:.3f} < {refusal_want}")
    return (not failures, failures)


def _doc_stats(results: list[dict]) -> dict:
    """Per-document means (None scores ignored) + refusal accuracy + fail counts."""
    stats = {}
    for doc in DOC_ORDER:
        rows = [r for r in results if r.get("doc") == doc]
        if not rows:
            continue
        means = {}
        for key in METRIC_KEYS:
            vals = [_metric_score(r, key) for r in rows]
            vals = [v for v in vals if v is not None]
            means[key] = sum(vals) / len(vals) if vals else None
        refuse_qs = [r for r in rows if r.get("kind") in ("unanswerable", "adversarial")]
        refusal = (
            sum(1 for r in refuse_qs if r.get("refused")) / len(refuse_qs)
            if refuse_qs else None
        )
        n_fail = sum(1 for r in rows if _is_failing(r)[0])
        stats[doc] = {
            "n": len(rows), "means": means, "refusal": refusal,
            "n_fail": n_fail, "n_refuse_qs": len(refuse_qs),
        }
    return stats


def _score_card(label: str, value, threshold, metric_key: str) -> str:
    """A clickable KPI card: label, big number, 0–1 bar with the gate tick.

    ``data-metric`` lets the explorer sort by this metric when clicked.
    """
    color = _score_color(value)
    pct = max(0.0, min(1.0, value)) * 100 if isinstance(value, (int, float)) else 0.0
    threshold_mark = ""
    if isinstance(threshold, (int, float)):
        t_pct = max(0.0, min(1.0, threshold)) * 100
        threshold_mark = (
            f"<div title='Gate threshold {threshold}' style='position:absolute;left:{t_pct}%;"
            "top:-3px;bottom:-3px;width:2px;background:#111827'></div>"
            f"<div style='position:absolute;left:{t_pct}%;top:12px;transform:translateX(-50%);"
            f"font-size:10px;color:#6b7280;white-space:nowrap'>gate {threshold}</div>"
        )
    return (
        f"<button type='button' class='card' data-metric='{metric_key}' "
        "title='Click to sort questions by this metric (worst first)'>"
        f"<div class='card-label'>{html.escape(label)}</div>"
        f"<div class='card-value' style='color:{color}' data-value='{value if isinstance(value, (int, float)) else ''}'>{_fmt(value)}</div>"
        "<div class='card-bar'>"
        f"<div class='card-fill' style='width:{pct:.1f}%;background:{color}'></div>"
        f"{threshold_mark}</div>"
        "<div class='card-hint'>click to drill in ↓</div>"
        "</button>"
    )


def _trend_chart(runs_asc: list[dict]) -> str:
    """Inline SVG line chart: faithfulness + answer relevancy across runs.

    Dots carry data attributes so JS can show a tooltip and load the run
    on click. Partial runs (fewer questions than the max) are marked.
    """
    series = [
        ("faithfulness", "Faithfulness", "#2563eb"),
        ("answer_relevancy", "Answer relevancy", "#16a34a"),
    ]
    width, height = 920, 260
    pad_l, pad_r, pad_t, pad_b = 44, 16, 18, 30
    y_min, y_max = 0.5, 1.0
    n = len(runs_asc)
    if n == 0:
        return "<p style='color:#6b7280'>No runs yet.</p>"

    def x(i: int) -> float:
        if n == 1:
            return pad_l + (width - pad_l - pad_r) / 2
        return pad_l + (width - pad_l - pad_r) * i / (n - 1)

    def y(v) -> float:
        v = max(y_min, min(y_max, v)) if isinstance(v, (int, float)) else y_min
        return pad_t + (height - pad_t - pad_b) * (1 - (v - y_min) / (y_max - y_min))

    parts = [f"<svg id='trend-svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
             "style='max-width:100%;height:auto;display:block'>"]
    for gv in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        gy = y(gv)
        parts.append(f"<line x1='{pad_l}' y1='{gy:.1f}' x2='{width - pad_r}' y2='{gy:.1f}' stroke='#e5e7eb'/>")
        parts.append(f"<text x='{pad_l - 8}' y='{gy + 4:.1f}' font-size='11' fill='#6b7280' text-anchor='end'>{gv:.1f}</text>")
    for key, label, color in series:
        pts = []
        for i, run in enumerate(runs_asc):
            value = (run.get("aggregates") or {}).get(key)
            if isinstance(value, (int, float)):
                pts.append((i, x(i), y(value), value))
        if not pts:
            continue
        if len(pts) > 1:
            path = "M " + " L ".join(f"{px:.1f},{py:.1f}" for _, px, py, _ in pts)
            parts.append(f"<path d='{path}' fill='none' stroke='{color}' stroke-width='2.5'/>")
        for i, px, py, value in pts:
            run = runs_asc[i]
            agg = run.get("aggregates") or {}
            attrs = (
                f"data-run-id='{html.escape(str(run.get('id', '')))}' "
                f"data-ts='{html.escape(str(run.get('timestamp', ''))[:19])}' "
                + " ".join(
                    f"data-{k}='{agg.get(k) if isinstance(agg.get(k), (int, float)) else ''}'"
                    for k in (*METRIC_KEYS, "refusal_accuracy")
                    if k != "refusal_accuracy" or True
                )
                + f" data-refusal='{run.get('refusal_accuracy') if isinstance(run.get('refusal_accuracy'), (int, float)) else ''}'"
                f" data-n='{run.get('n_questions', '')}'"
            )
            parts.append(
                f"<circle class='trend-dot' cx='{px:.1f}' cy='{py:.1f}' r='5' fill='{color}' "
                f"stroke='#fff' stroke-width='1.5' {attrs} style='cursor:pointer'>"
                f"<title>{html.escape(str(run.get('id', '')))} — {label} {value:.3f}</title></circle>"
            )
    for i, run in enumerate(runs_asc):
        ts = str(run.get("timestamp", ""))
        label = ts[11:16] if len(ts) >= 16 else str(run.get("id", ""))[:8]
        # Partial runs get an asterisk; the footnote below the chart explains it.
        if run.get("_partial"):
            label += " *"
        anchor = "middle"
        if i == 0:
            anchor = "start"
        elif i == n - 1:
            anchor = "end"
        parts.append(f"<text x='{x(i):.1f}' y='{height - 8}' font-size='11' fill='#6b7280' text-anchor='{anchor}'>{html.escape(label)}</text>")
    parts.append("</svg>")
    legend = "".join(
        f"<span style='display:inline-flex;align-items:center;gap:6px;margin-right:18px;font-size:13px;color:#374151'>"
        f"<span style='width:14px;height:3px;background:{color};border-radius:2px;display:inline-block'></span>{label}</span>"
        for _, label, color in series
    )
    footnote = "<p class='note' style='margin:8px 0 0'>* partial probe run (fewer questions than the full golden set).</p>" if any(r.get("_partial") for r in runs_asc) else ""
    return f"<div>{legend}</div>" + "".join(parts) + footnote + "<div id='trend-tip' class='tooltip' hidden></div>"


def _question_rows(results: list[dict]) -> str:
    """Explorer rows: one summary <tr> + one hidden detail <tr> per question."""
    out = []
    for row in results:
        failing, bad, behaviour_bad = _is_failing(row)
        if row.get("refused") and row.get("kind") in ("unanswerable", "adversarial"):
            status = "<span class='pill pill-blue'>Refused ✓</span>"
        elif failing:
            status = "<span class='pill pill-red'>Failing</span>"
        else:
            status = "<span class='pill pill-green'>Pass</span>"
        cells = "".join(
            f"<td class='num' data-sort='{(_metric_score(row, k) if _metric_score(row, k) is not None else -1):.3f}' "
            f"style='color:{_score_color(_metric_score(row, k))}'>{_fmt(_metric_score(row, k))}</td>"
            for k in METRIC_KEYS
        )
        latency = row.get("latency_ms")
        lat_txt = f"{latency:.0f} ms" if isinstance(latency, (int, float)) else "—"
        out.append(
            f"<tr class='qrow' data-id='{html.escape(str(row.get('id', '')))}' "
            f"data-doc='{html.escape(str(row.get('doc', '')))}' "
            f"data-kind='{html.escape(str(row.get('kind', '')))}' "
            f"data-status='{'fail' if failing else 'pass'}' "
            f"data-latency='{(latency if isinstance(latency, (int, float)) else -1)}' tabindex='0'>"
            f"<td><strong>{html.escape(str(row.get('id', '')))}</strong></td>"
            f"<td class='qtext'>{html.escape(str(row.get('question', '')))}</td>"
            f"<td>{html.escape(DOC_LABELS.get(str(row.get('doc', '')), str(row.get('doc', ''))))}</td>"
            f"<td>{html.escape(str(row.get('kind', '')))}</td>"
            f"<td>{status}</td>"
            f"{cells}"
            f"<td class='num'>{lat_txt}</td>"
            "<td class='expander'>▸</td></tr>"
        )
        # Detail row (hidden until the summary row is clicked).
        metric_lines = []
        for k in METRIC_KEYS:
            entry = row.get(k) or {}
            score = _metric_score(row, k)
            method = entry.get("method", "") if isinstance(entry, dict) else ""
            metric_lines.append(
                f"<div class='kv'><span>{METRIC_LABELS[k]}</span><b style='color:{_score_color(score)}'>{_fmt(score)}</b>"
                f"<code>{html.escape(str(method))}</code></div>"
            )
        if bad:
            metric_lines.append(
                f"<div class='kv'><span>Low metrics</span><b style='color:#dc2626'>{', '.join(bad)}</b></div>"
            )
        if behaviour_bad:
            metric_lines.append(
                "<div class='kv'><span>Behaviour</span><b style='color:#92400e'>not refused</b></div>"
            )
        cites = row.get("citations") or []
        pages = row.get("retrieved_pages") or []
        best = row.get("best_score")
        out.append(
            "<tr class='qdetail' hidden><td colspan='11'>"
            "<div class='detail-grid'>"
            f"<div><div class='d-label'>Question</div><div>{html.escape(str(row.get('question', '')))}</div></div>"
            f"<div><div class='d-label'>Expected answer</div><div>{html.escape(str(row.get('expected_answer', '')))}</div></div>"
            f"<div><div class='d-label'>Actual answer</div><div class='answer'>{html.escape(str(row.get('answer', '')))}</div></div>"
            "<div class='d-metrics'>" + "".join(metric_lines) + "</div>"
            f"<div class='d-meta'><span>Citations: <b>{html.escape(str(cites))}</b></span>"
            f"<span>Retrieved pages: <b>{html.escape(str(pages))}</b></span>"
            f"<span>Best retrieval score: <b>{best:.3f}</b></span>" if isinstance(best, (int, float)) else "<span>Best retrieval score: <b>—</b></span>"
            f"<span>Latency: <b>{lat_txt}</b></span>"
            f"<span>Refused: <b>{'yes' if row.get('refused') else 'no'}</b></span></div>"
            "</div></td></tr>"
        )
    return "".join(out)


def _doc_panels(stats: dict, thresholds: dict, mode: str) -> str:
    """Per-document mini panels with mean bars for each metric + refusal."""
    want = thresholds.get(mode, {}) if isinstance(thresholds, dict) else {}
    panels = []
    for doc in DOC_ORDER:
        s = stats.get(doc)
        if not s:
            continue
        bars = []
        for key in METRIC_KEYS:
            value = s["means"].get(key)
            color = _score_color(value)
            pct = max(0.0, min(1.0, value)) * 100 if isinstance(value, (int, float)) else 0.0
            gate = want.get(key)
            gate_txt = f" · gate {gate}" if isinstance(gate, (int, float)) else ""
            bars.append(
                f"<div class='doc-bar-row'><span>{METRIC_SHORT[key]}</span>"
                "<div class='doc-bar'><div style='width:"
                f"{pct:.1f}%;background:{color}'></div></div>"
                f"<b style='color:{color}'>{_fmt(value)}</b>"
                f"<span class='gate-txt'>{gate_txt}</span></div>"
            )
        refusal = s["refusal"]
        refusal_txt = (
            f"{refusal:.2f} ({s['n_refuse_qs']} refusal Qs)"
            if refusal is not None else "— (no refusal Qs)"
        )
        panels.append(
            f"<div class='panel doc-panel'><div class='doc-head'>"
            f"<strong>{DOC_LABELS[doc]}</strong>"
            f"<span class='note'>{s['n']} questions · {s['n_fail']} failing</span></div>"
            + "".join(bars) +
            f"<div class='doc-bar-row'><span>Refusal</span><b>{refusal_txt}</b></div>"
            "</div>"
        )
    return "".join(panels)


_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
       background: #f6f7f9; color: #111827; margin: 0; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 0 20px 48px; }
.header { background: #0f2040; color: #fff; padding: 28px 0 24px; margin-bottom: 24px; position: sticky; top: 0; z-index: 20;
          box-shadow: 0 2px 12px rgba(15,32,64,0.35); }
.header h1 { font-size: 26px; margin: 0 0 4px; display: inline-block; }
.header p { margin: 0; color: #cbd5e1; font-size: 14px; }
.header .gate { float: right; margin-top: 4px; }
.meta { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.meta span { background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.18);
             border-radius: 99px; padding: 4px 12px; font-size: 12px; }
h2 { font-size: 17px; margin: 28px 0 12px; }
h2 .hint { font-weight: 400; font-size: 13px; color: #6b7280; }
.cards { display: flex; gap: 14px; flex-wrap: wrap; }
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px 20px 12px;
        flex: 1; min-width: 160px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); cursor: pointer;
        text-align: left; font: inherit; transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease; }
.card:hover { transform: translateY(-2px); box-shadow: 0 4px 14px rgba(0,0,0,0.08); }
.card.selected { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37,99,235,0.35); }
.card-label { font-size: 12px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: #6b7280; }
.card-value { font-size: 34px; font-weight: 800; line-height: 1.15; margin-top: 4px; }
.card-bar { position: relative; height: 8px; background: #f3f4f6; border-radius: 99px; margin-top: 12px; }
.card-fill { height: 8px; border-radius: 99px; transition: width .5s ease; }
.card-hint { font-size: 11px; color: #9ca3af; margin-top: 14px; text-align: right; }
.badge { display: inline-block; border-radius: 99px; padding: 5px 14px; font-size: 13px; font-weight: 700; }
.badge-pass { background: #dcfce7; color: #166534; }
.badge-fail { background: #fee2e2; color: #991b1b; }
.run-switch { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 4px; }
.run-pill { border: 1px solid #d1d5db; background: #fff; border-radius: 99px; padding: 6px 14px;
            font-size: 13px; cursor: pointer; color: #374151; transition: all .12s ease; }
.run-pill:hover { border-color: #2563eb; color: #1d4ed8; }
.run-pill.active { background: #0f2040; border-color: #0f2040; color: #fff; font-weight: 600; }
.run-pill .partial { color: #d97706; font-size: 11px; }
.run-pill.active .partial { color: #fcd34d; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 12px 0; }
.filters select, .filters input { border: 1px solid #d1d5db; border-radius: 8px; padding: 7px 10px;
    font-size: 13px; background: #fff; color: #111827; }
.filters input { min-width: 220px; flex: 1; }
.seg { display: inline-flex; border: 1px solid #d1d5db; border-radius: 8px; overflow: hidden; }
.seg button { border: none; background: #fff; padding: 7px 12px; font-size: 13px; cursor: pointer; color: #374151; }
.seg button.active { background: #0f2040; color: #fff; font-weight: 600; }
.table-scroll { overflow-x: auto; border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; }
table { width: 100%; border-collapse: collapse; background: #fff; font-size: 14px; }
th { text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
     color: #6b7280; background: #f9fafb; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; white-space: nowrap; }
th.sortable { cursor: pointer; user-select: none; }
th.sortable:hover { color: #111827; }
td { padding: 10px 12px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
tr:last-child td { border-bottom: none; }
tr.qrow { cursor: pointer; }
tr.qrow:hover td { background: #f8fafc; }
tr.qrow.open td { background: #eff6ff; }
td.qtext { max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
td.num { font-variant-numeric: tabular-nums; text-align: right; font-weight: 600; white-space: nowrap; }
th.num { text-align: right; }
td.expander { color: #9ca3af; }
tr.qrow.open td.expander { transform: rotate(90deg); display: inline-block; }
tr.qdetail td { background: #f8fafc; padding: 16px 18px; }
.detail-grid { display: grid; gap: 12px; font-size: 13px; line-height: 1.55; }
.d-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; margin-bottom: 2px; }
.answer { white-space: pre-wrap; }
.d-metrics { display: flex; gap: 18px; flex-wrap: wrap; }
.kv { display: flex; gap: 6px; align-items: baseline; }
.kv span { color: #6b7280; }
.kv code { background: #eef2f7; border-radius: 4px; padding: 1px 6px; font-size: 11px; color: #475569; }
.d-meta { display: flex; gap: 18px; flex-wrap: wrap; color: #6b7280; font-size: 12px; }
.d-meta b { color: #111827; }
.pill { display: inline-block; border-radius: 99px; padding: 2px 9px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.pill-red { background: #fee2e2; color: #991b1b; }
.pill-amber { background: #fef3c7; color: #92400e; }
.pill-green { background: #dcfce7; color: #166534; }
.pill-blue { background: #dbeafe; color: #1e40af; }
.note { color: #6b7280; font-size: 13px; line-height: 1.5; }
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px 20px;
         box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.doc-panels { display: flex; gap: 14px; flex-wrap: wrap; }
.doc-panel { flex: 1; min-width: 260px; }
.doc-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.doc-bar-row { display: flex; align-items: center; gap: 8px; font-size: 13px; margin: 6px 0; }
.doc-bar-row span:first-child { width: 44px; color: #6b7280; }
.doc-bar { flex: 1; height: 7px; background: #f3f4f6; border-radius: 99px; overflow: hidden; }
.doc-bar div { height: 7px; border-radius: 99px; }
.gate-txt { color: #9ca3af; font-size: 11px; }
.tooltip { position: absolute; background: #111827; color: #fff; border-radius: 8px; padding: 10px 12px;
           font-size: 12px; line-height: 1.5; pointer-events: none; z-index: 30; box-shadow: 0 4px 16px rgba(0,0,0,0.25); }
.tooltip b { color: #fff; }
.count-line { font-size: 13px; color: #6b7280; margin: 8px 0 0; }
.empty { padding: 28px; text-align: center; color: #6b7280; }
.spin { display: inline-block; width: 14px; height: 14px; border: 2px solid #d1d5db; border-top-color: #2563eb;
        border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: -2px; }
@keyframes spin { to { transform: rotate(360deg); } }
"""


def render_dashboard(runs: list[dict], latest: dict | None) -> str:
    if latest is None:
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>EvalLens — Knowlix RAG evaluation</title>
<style>{_CSS}</style></head><body>
<div class="header"><div class="wrap" style="padding-bottom:0">
<h1>EvalLens</h1><p>Knowlix RAG evaluation</p></div></div>
<div class="wrap"><div class="panel"><p>No eval runs yet. Run one with:</p>
<pre>cd backend &amp;&amp; python -m evallens.runner</pre></div></div>
</body></html>"""

    thresholds = _load_thresholds(latest.get("thresholds"))
    mode = "judge" if latest.get("judge_mode") else "deterministic"
    want = thresholds.get(mode, {}) if isinstance(thresholds, dict) else {}
    agg = latest.get("aggregates") or {}
    results = latest.get("results") or []

    # Partial runs (fewer questions than the biggest run) are probe runs —
    # listed, never the default view.
    max_n = max((r.get("n_questions") or 0) for r in runs) if runs else (latest.get("n_questions") or 0)
    for r in runs:
        r["_partial"] = (r.get("n_questions") or 0) < max_n
    newest = runs[0] if runs else None
    partial_note = ""
    if newest and newest.get("_partial") and str(newest.get("id")) != str(latest.get("id")):
        partial_note = (
            f"<p class='note'>Newest recording is a partial probe run "
            f"({html.escape(str(newest.get('id', '')))} — {newest.get('n_questions')} questions), "
            "so this page shows the latest full run instead. The probe is in the switcher below.</p>"
        )

    passed, failures = _gate_status(latest, thresholds)
    gate_badge = (
        '<span class="badge badge-pass">✓ Gate passed</span>' if passed
        else '<span class="badge badge-fail">✗ Gate failed</span>'
    )
    fail_note = ""
    if not passed:
        fail_note = ("<p class='note' style='color:#991b1b'>Failing: " +
                     html.escape("; ".join(failures)) + "</p>")

    cards = "".join(
        _score_card(METRIC_LABELS[key], agg.get(key), want.get(key), key) for key in METRIC_KEYS
    )
    cards += _score_card("Refusal accuracy", latest.get("refusal_accuracy"),
                         want.get("refusal_accuracy"), "refusal")

    # Run switcher pills, newest first.
    pills = []
    for r in runs:
        ts = str(r.get("timestamp", ""))[:16].replace("T", " ")
        label = ts[5:] if len(ts) >= 16 else str(r.get("id", ""))[:10]
        judge = "judge" if r.get("judge") else "deterministic"
        active = " active" if str(r.get("id")) == str(latest.get("id")) else ""
        partial = " <span class='partial'>partial</span>" if r.get("_partial") else ""
        pills.append(
            f"<button type='button' class='run-pill{active}' data-run-id='{html.escape(str(r.get('id', '')))}'>"
            f"{html.escape(label)} · {judge} · {r.get('n_questions', '')} qs{partial}</button>"
        )
    switcher = "".join(pills)

    doc_panels = _doc_panels(_doc_stats(results), thresholds, mode)

    runs_asc = sorted(runs, key=lambda r: str(r.get("timestamp", "")))
    trend_rows = ""
    for run in runs:
        a = run.get("aggregates") or {}
        partial_tag = " <span class='pill pill-amber'>partial</span>" if run.get("_partial") else ""
        trend_rows += (
            f"<tr class='runrow' data-run-id='{html.escape(str(run.get('id', '')))}' style='cursor:pointer'>"
            f"<td>{html.escape(str(run.get('timestamp', ''))[:19].replace('T', ' '))}{partial_tag}</td>"
            f"<td>{html.escape(str(run.get('judge', '')))}</td>"
            f"<td>{run.get('n_questions', '')}</td>"
            + "".join(f"<td>{_fmt(a.get(key))}</td>" for key in METRIC_KEYS)
            + f"<td>{_fmt(run.get('refusal_accuracy'))}</td></tr>"
        )

    n_fail = sum(1 for r in results if _is_failing(r)[0])
    meta = (
        f"<span>Run <strong>{html.escape(str(latest.get('id', '')))}</strong></span>"
        f"<span>Judge: {html.escape(str(latest.get('judge', '')))}</span>"
        f"<span>LLM: {html.escape(str(latest.get('llm_mode', '')))}</span>"
        f"<span>{latest.get('n_questions', '')} questions</span>"
        f"<span>Commit {html.escape(str(latest.get('git_commit', '')))}</span>"
    )

    payload = {
        "runs": [
            {k: r.get(k) for k in ("id", "timestamp", "judge", "llm_mode", "n_questions", "aggregates", "refusal_accuracy", "_partial")}
            for r in runs
        ],
        "current": latest,
        "thresholds": thresholds,
    }
    embedded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>EvalLens — Knowlix RAG evaluation</title><style>{_CSS}</style></head>
<body>
<div class="header"><div class="wrap" style="padding-bottom:0">
<h1>EvalLens</h1><span class="gate" id="gate-badge">{gate_badge}</span>
<p>Knowlix RAG evaluation — measured quality, not vibes.</p>
<div class="meta" id="run-meta">{meta}</div></div></div>
<div class="wrap">
<h2>Run <span class="hint">— click a run to load it, or a point on the chart</span></h2>
<div class="run-switch" id="run-switch">{switcher}</div>
{partial_note}
<p class="note" id="loading-note" hidden><span class="spin"></span> Loading run…</p>
<h2>Latest scores &nbsp;<span class="hint">click a card to sort questions by that metric</span></h2>
<div id="fail-note">{fail_note}</div>
<div class="cards" id="cards">{cards}</div>
<p class="note">Scores are means over the golden set's answerable questions
(faithfulness includes refusals at 1.0; answer relevancy excludes refusals;
context precision/recall exclude unanswerable and adversarial questions).
The black tick on each bar is the quality-gate threshold. Click a card to
drill into the questions behind that number. See
<code>evallens/README.md</code> for the metric definitions.</p>
<h2>By document <span class="hint">— which document drags the scores down</span></h2>
<div class="doc-panels" id="doc-panels">{doc_panels}</div>
<h2>Trend — faithfulness &amp; relevancy <span class="hint">— hover a point, click to load that run</span></h2>
<div class="panel" style="position:relative">{_trend_chart(runs_asc)}</div>
<h2>Question explorer <span class="hint">— filter, sort, click a row for the full answer</span></h2>
<div class="filters">
  <select id="f-doc" aria-label="Document">
    <option value="all">All documents</option>
    <option value="aurora">Aurora</option>
    <option value="meridian">Meridian</option>
    <option value="kaveri">Kaveri</option>
  </select>
  <select id="f-kind" aria-label="Question kind">
    <option value="all">All kinds</option>
    <option value="factual">Factual</option>
    <option value="summary">Summary</option>
    <option value="unanswerable">Unanswerable</option>
    <option value="adversarial">Adversarial</option>
    <option value="refusal">Refusal questions</option>
  </select>
  <span class="seg" id="f-status">
    <button type="button" data-status="all" class="active">All</button>
    <button type="button" data-status="pass">Passing</button>
    <button type="button" data-status="fail">Failing</button>
  </span>
  <input id="f-q" type="search" placeholder="Search questions, answers, IDs…" aria-label="Search questions">
</div>
<p class="count-line" id="count-line">Showing {len(results)} of {len(results)} questions · {n_fail} failing</p>
<div class="table-scroll"><table>
<thead><tr>
<th>ID</th><th class="sortable" data-sort="question">Question</th>
<th class="sortable" data-sort="doc">Doc</th><th class="sortable" data-sort="kind">Kind</th>
<th>Status</th>
<th class="sortable num" data-sort="faithfulness">Faith.</th>
<th class="sortable num" data-sort="answer_relevancy">Relev.</th>
<th class="sortable num" data-sort="context_precision">Prec.</th>
<th class="sortable num" data-sort="context_recall">Recall</th>
<th class="sortable num" data-sort="latency">Latency</th><th></th>
</tr></thead>
<tbody id="qbody">{_question_rows(results)}</tbody>
</table></div>
<p class="note" id="empty-note" hidden>No questions match these filters.</p>
<h2>Run history <span class="hint">— click a row to load that run</span></h2>
<div class="table-scroll"><table><tr><th>Run</th><th>Judge</th><th>Qs</th><th>Faithfulness</th><th>Relevancy</th><th>Precision</th><th>Recall</th><th>Refusal</th></tr>
{trend_rows}</table></div>
<p class="note" style="margin-top:28px">EvalLens runs Knowlix's real RAG pipeline over a
67-question golden set and scores it with the four RAGAS metrics. Every number
on this page comes from a recorded run file — nothing is invented.</p>
</div>
<script type="application/json" id="eval-data">{embedded}</script>
<script>{_JS}</script>
</body></html>"""


_JS = """
(function () {
  var DATA = JSON.parse(document.getElementById('eval-data').textContent);
  var METRICS = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall'];
  var LABELS = { faithfulness: 'Faithfulness', answer_relevancy: 'Answer relevancy',
    context_precision: 'Context precision', context_recall: 'Context recall' };
  var SHORT = { faithfulness: 'Faith.', answer_relevancy: 'Relev.',
    context_precision: 'Prec.', context_recall: 'Recall' };
  var DOCS = ['aurora', 'meridian', 'kaveri'];
  var DOC_LABELS = { aurora: 'Aurora', meridian: 'Meridian', kaveri: 'Kaveri' };

  var state = {
    run: DATA.current,
    doc: 'all', kind: 'all', status: 'all', q: '',
    sortKey: null, sortDir: 1, selectedMetric: null
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmt(v) { return (typeof v === 'number') ? v.toFixed(3) : '—'; }
  function color(v) {
    if (typeof v !== 'number') return '#9ca3af';
    if (v >= 0.90) return '#16a34a';
    if (v >= 0.70) return '#d97706';
    return '#dc2626';
  }
  function mscore(row, key) {
    var e = row[key];
    if (!e || typeof e.score !== 'number') return null;
    return e.score;
  }
  function failing(row) {
    var bad = METRICS.filter(function (k) { var s = mscore(row, k); return s !== null && s < 0.7; });
    var behaviour = (row.kind === 'unanswerable' || row.kind === 'adversarial') && !row.refused;
    return { fail: bad.length > 0 || behaviour, bad: bad, behaviour: behaviour };
  }
  function gateStatus(run) {
    var mode = run.judge_mode ? 'judge' : 'deterministic';
    var want = (DATA.thresholds && DATA.thresholds[mode]) || {};
    var agg = run.aggregates || {};
    var fails = [];
    METRICS.forEach(function (k) {
      var t = want[k], v = agg[k];
      if (typeof t === 'number' && typeof v === 'number' && v < t) fails.push(LABELS[k] + ' ' + v.toFixed(3) + ' < ' + t);
    });
    if (typeof want.refusal_accuracy === 'number' && typeof run.refusal_accuracy === 'number'
        && run.refusal_accuracy < want.refusal_accuracy)
      fails.push('Refusal accuracy ' + run.refusal_accuracy.toFixed(3) + ' < ' + want.refusal_accuracy);
    return { passed: fails.length === 0, fails: fails };
  }
  function docStats(results) {
    var out = {};
    DOCS.forEach(function (doc) {
      var rows = results.filter(function (r) { return r.doc === doc; });
      if (!rows.length) return;
      var means = {};
      METRICS.forEach(function (k) {
        var vals = rows.map(function (r) { return mscore(r, k); }).filter(function (v) { return v !== null; });
        means[k] = vals.length ? vals.reduce(function (a, b) { return a + b; }, 0) / vals.length : null;
      });
      var rq = rows.filter(function (r) { return r.kind === 'unanswerable' || r.kind === 'adversarial'; });
      out[doc] = { n: rows.length, means: means,
        refusal: rq.length ? rq.filter(function (r) { return r.refused; }).length / rq.length : null,
        nFail: rows.filter(function (r) { return failing(r).fail; }).length, nRefuse: rq.length };
    });
    return out;
  }

  /* ---------- renderers ---------- */
  function renderCards() {
    var run = state.run;
    var mode = run.judge_mode ? 'judge' : 'deterministic';
    var want = (DATA.thresholds && DATA.thresholds[mode]) || {};
    var agg = run.aggregates || {};
    var wrap = document.getElementById('cards');
    var html = '';
    METRICS.concat(['refusal']).forEach(function (key) {
      var label = key === 'refusal' ? 'Refusal accuracy' : LABELS[key];
      var value = key === 'refusal' ? run.refusal_accuracy : agg[key];
      var t = key === 'refusal' ? want.refusal_accuracy : want[key];
      var c = color(value);
      var pct = (typeof value === 'number') ? Math.max(0, Math.min(1, value)) * 100 : 0;
      var tick = '';
      if (typeof t === 'number') {
        var tp = Math.max(0, Math.min(1, t)) * 100;
        tick = "<div title='Gate threshold " + t + "' style='position:absolute;left:" + tp + "%;top:-3px;bottom:-3px;width:2px;background:#111827'></div>"
          + "<div style='position:absolute;left:" + tp + "%;top:12px;transform:translateX(-50%);font-size:10px;color:#6b7280;white-space:nowrap'>gate " + t + "</div>";
      }
      html += "<button type='button' class='card" + (state.selectedMetric === key ? ' selected' : '') + "' data-metric='" + key + "'"
        + " title='Click to sort questions by this metric (worst first)'>"
        + "<div class='card-label'>" + esc(label) + "</div>"
        + "<div class='card-value' style='color:" + c + "'>" + fmt(value) + "</div>"
        + "<div class='card-bar'><div class='card-fill' style='width:" + pct.toFixed(1) + "%;background:" + c + "'></div>" + tick + "</div>"
        + "<div class='card-hint'>click to drill in ↓</div></button>";
    });
    wrap.innerHTML = html;
    var g = gateStatus(run);
    document.getElementById('gate-badge').innerHTML = g.passed
      ? '<span class="badge badge-pass">✓ Gate passed</span>'
      : '<span class="badge badge-fail">✗ Gate failed</span>';
    document.getElementById('fail-note').innerHTML = g.passed ? ''
      : "<p class='note' style='color:#991b1b'>Failing: " + esc(g.fails.join('; ')) + "</p>";
    document.getElementById('run-meta').innerHTML =
      '<span>Run <strong>' + esc(run.id) + '</strong></span>'
      + '<span>Judge: ' + esc(run.judge || '') + '</span>'
      + '<span>LLM: ' + esc(run.llm_mode || '') + '</span>'
      + '<span>' + (run.n_questions || '') + ' questions</span>'
      + '<span>Commit ' + esc(run.git_commit || '') + '</span>';
  }
  function renderDocs() {
    var run = state.run;
    var mode = run.judge_mode ? 'judge' : 'deterministic';
    var want = (DATA.thresholds && DATA.thresholds[mode]) || {};
    var stats = docStats(run.results || []);
    var html = '';
    DOCS.forEach(function (doc) {
      var s = stats[doc];
      if (!s) return;
      var bars = METRICS.map(function (k) {
        var v = s.means[k], c = color(v);
        var pct = (typeof v === 'number') ? Math.max(0, Math.min(1, v)) * 100 : 0;
        var gate = (typeof want[k] === 'number') ? ' · gate ' + want[k] : '';
        return "<div class='doc-bar-row'><span>" + SHORT[k] + "</span>"
          + "<div class='doc-bar'><div style='width:" + pct.toFixed(1) + "%;background:" + c + "'></div></div>"
          + "<b style='color:" + c + "'>" + fmt(v) + "</b><span class='gate-txt'>" + gate + "</span></div>";
      }).join('');
      var ref = s.refusal !== null ? s.refusal.toFixed(2) + ' (' + s.nRefuse + ' refusal Qs)' : '— (no refusal Qs)';
      html += "<div class='panel doc-panel'><div class='doc-head'><strong>" + DOC_LABELS[doc] + "</strong>"
        + "<span class='note'>" + s.n + " questions · " + s.nFail + " failing</span></div>"
        + bars + "<div class='doc-bar-row'><span>Refusal</span><b>" + ref + "</b></div></div>";
    });
    document.getElementById('doc-panels').innerHTML = html;
  }
  function rowHtml(row) {
    var f = failing(row);
    var status = (row.refused && (row.kind === 'unanswerable' || row.kind === 'adversarial'))
      ? "<span class='pill pill-blue'>Refused ✓</span>"
      : f.fail ? "<span class='pill pill-red'>Failing</span>" : "<span class='pill pill-green'>Pass</span>";
    var cells = METRICS.map(function (k) {
      var s = mscore(row, k);
      return "<td class='num' style='color:" + color(s) + "'>" + fmt(s) + "</td>";
    }).join('');
    var lat = (typeof row.latency_ms === 'number') ? row.latency_ms.toFixed(0) + ' ms' : '—';
    var metrics = METRICS.map(function (k) {
      var e = row[k] || {}, s = mscore(row, k);
      return "<div class='kv'><span>" + LABELS[k] + "</span><b style='color:" + color(s) + "'>" + fmt(s) + "</b>"
        + "<code>" + esc(e.method || '') + "</code></div>";
    }).join('');
    if (f.bad.length) metrics += "<div class='kv'><span>Low metrics</span><b style='color:#dc2626'>" + f.bad.join(', ') + "</b></div>";
    if (f.behaviour) metrics += "<div class='kv'><span>Behaviour</span><b style='color:#92400e'>not refused</b></div>";
    var best = (typeof row.best_score === 'number') ? row.best_score.toFixed(3) : '—';
    return "<tr class='qrow' data-id='" + esc(row.id) + "' tabindex='0'>"
      + "<td><strong>" + esc(row.id) + "</strong></td>"
      + "<td class='qtext'>" + esc(row.question) + "</td>"
      + "<td>" + esc(DOC_LABELS[row.doc] || row.doc || '') + "</td>"
      + "<td>" + esc(row.kind) + "</td><td>" + status + "</td>" + cells
      + "<td class='num'>" + lat + "</td><td class='expander'>▸</td></tr>"
      + "<tr class='qdetail' hidden><td colspan='11'><div class='detail-grid'>"
      + "<div><div class='d-label'>Question</div><div>" + esc(row.question) + "</div></div>"
      + "<div><div class='d-label'>Expected answer</div><div>" + esc(row.expected_answer) + "</div></div>"
      + "<div><div class='d-label'>Actual answer</div><div class='answer'>" + esc(row.answer) + "</div></div>"
      + "<div class='d-metrics'>" + metrics + "</div>"
      + "<div class='d-meta'><span>Citations: <b>" + esc(JSON.stringify(row.citations || [])) + "</b></span>"
      + "<span>Retrieved pages: <b>" + esc(JSON.stringify(row.retrieved_pages || [])) + "</b></span>"
      + "<span>Best retrieval score: <b>" + best + "</b></span>"
      + "<span>Latency: <b>" + lat + "</b></span>"
      + "<span>Refused: <b>" + (row.refused ? 'yes' : 'no') + "</b></span></div>"
      + "</div></td></tr>";
  }
  function visibleRows() {
    var rows = (state.run.results || []).slice();
    var q = state.q.trim().toLowerCase();
    rows = rows.filter(function (r) {
      if (state.doc !== 'all' && r.doc !== state.doc) return false;
      if (state.kind === 'refusal') { if (!(r.kind === 'unanswerable' || r.kind === 'adversarial')) return false; }
      else if (state.kind !== 'all' && r.kind !== state.kind) return false;
      var f = failing(r).fail;
      if (state.status === 'pass' && f) return false;
      if (state.status === 'fail' && !f) return false;
      if (q) {
        var hay = ((r.id || '') + ' ' + (r.question || '') + ' ' + (r.expected_answer || '') + ' ' + (r.answer || '')).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    if (state.sortKey) {
      var key = state.sortKey, dir = state.sortDir;
      rows.sort(function (a, b) {
        var va, vb;
        if (key === 'question') { va = a.question || ''; vb = b.question || ''; return va.localeCompare(vb) * dir; }
        if (key === 'doc' || key === 'kind') { va = a[key] || ''; vb = b[key] || ''; return va.localeCompare(vb) * dir; }
        if (key === 'latency') { va = a.latency_ms; vb = b.latency_ms; }
        else { va = mscore(a, key); vb = mscore(b, key); }
        if (va === null || va === undefined) return 1;
        if (vb === null || vb === undefined) return -1;
        return (va - vb) * dir;
      });
    }
    return rows;
  }
  function renderTable() {
    var rows = visibleRows();
    var total = (state.run.results || []).length;
    var nFail = (state.run.results || []).filter(function (r) { return failing(r).fail; }).length;
    document.getElementById('qbody').innerHTML = rows.map(rowHtml).join('');
    document.getElementById('empty-note').hidden = rows.length > 0;
    document.getElementById('count-line').textContent =
      'Showing ' + rows.length + ' of ' + total + ' questions · ' + nFail + ' failing';
  }
  function renderAll() {
    renderCards();
    renderDocs();
    renderTable();
    markActiveDot();
  }
  function markActiveDot() {
    document.querySelectorAll('.trend-dot').forEach(function (d) {
      var active = d.getAttribute('data-run-id') === String(state.run.id);
      d.setAttribute('r', active ? '7' : '5');
      d.setAttribute('stroke', active ? '#0f2040' : '#fff');
      d.setAttribute('stroke-width', active ? '2.5' : '1.5');
    });
  }

  /* ---------- run switching ---------- */
  function setActivePill(id) {
    document.querySelectorAll('.run-pill').forEach(function (p) {
      p.classList.toggle('active', p.getAttribute('data-run-id') === String(id));
    });
  }
  function loadRun(id) {
    if (String(state.run.id) === String(id)) { setActivePill(id); return; }
    var note = document.getElementById('loading-note');
    note.hidden = false;
    fetch('/api/eval/runs/' + encodeURIComponent(id))
      .then(function (resp) { if (!resp.ok) throw new Error('HTTP ' + resp.status); return resp.json(); })
      .then(function (run) {
        state.run = run;
        state.sortKey = null; state.selectedMetric = null;
        setActivePill(id);
        renderAll();
        note.hidden = true;
        document.getElementById('cards').scrollIntoView({ behavior: 'smooth', block: 'start' });
      })
      .catch(function () {
        note.hidden = true;
        note.innerHTML = "<span style='color:#991b1b'>Couldn't load that run — still showing the previous one.</span>";
        note.hidden = false;
        setTimeout(function () { note.hidden = true; note.innerHTML = '<span class="spin"></span> Loading run…'; }, 4000);
      });
  }

  /* ---------- events ---------- */
  document.getElementById('run-switch').addEventListener('click', function (e) {
    var b = e.target.closest('.run-pill');
    if (b) loadRun(b.getAttribute('data-run-id'));
  });
  document.querySelectorAll('.runrow').forEach(function (tr) {
    tr.addEventListener('click', function () { loadRun(tr.getAttribute('data-run-id')); });
  });
  document.getElementById('cards').addEventListener('click', function (e) {
    var card = e.target.closest('.card');
    if (!card) return;
    var metric = card.getAttribute('data-metric');
    if (state.selectedMetric === metric) {
      state.selectedMetric = null; state.sortKey = null;
      document.getElementById('f-kind').value = 'all'; state.kind = 'all';
    } else if (metric === 'refusal') {
      state.selectedMetric = 'refusal'; state.sortKey = null;
      document.getElementById('f-kind').value = 'refusal'; state.kind = 'refusal';
    } else {
      state.selectedMetric = metric; state.sortKey = metric; state.sortDir = 1;
    }
    renderCards(); renderTable();
  });
  document.getElementById('f-doc').addEventListener('change', function (e) { state.doc = e.target.value; renderTable(); });
  document.getElementById('f-kind').addEventListener('change', function (e) {
    state.kind = e.target.value;
    if (state.kind !== 'refusal' && state.selectedMetric === 'refusal') state.selectedMetric = null;
    renderCards(); renderTable();
  });
  document.getElementById('f-status').addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b) return;
    state.status = b.getAttribute('data-status');
    document.querySelectorAll('#f-status button').forEach(function (x) { x.classList.toggle('active', x === b); });
    renderTable();
  });
  document.getElementById('f-q').addEventListener('input', function (e) { state.q = e.target.value; renderTable(); });
  document.querySelectorAll('th.sortable').forEach(function (th) {
    th.addEventListener('click', function () {
      var key = th.getAttribute('data-sort');
      if (state.sortKey === key) state.sortDir = -state.sortDir;
      else { state.sortKey = key; state.sortDir = 1; }
      state.selectedMetric = METRICS.indexOf(key) !== -1 ? key : null;
      renderCards(); renderTable();
    });
  });
  document.getElementById('qbody').addEventListener('click', function (e) {
    var tr = e.target.closest('tr.qrow');
    if (!tr) return;
    var detail = tr.nextElementSibling;
    var open = tr.classList.toggle('open');
    if (detail && detail.classList.contains('qdetail')) detail.hidden = !open;
  });
  document.getElementById('qbody').addEventListener('keydown', function (e) {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('qrow')) {
      e.preventDefault(); e.target.click();
    }
  });

  /* trend chart: hover tooltip + click to load */
  var tip = document.getElementById('trend-tip');
  var panel = tip ? tip.parentElement : null;
  document.querySelectorAll('.trend-dot').forEach(function (dot) {
    dot.addEventListener('mouseenter', function (e) {
      var d = dot.dataset;
      tip.innerHTML = '<b>' + esc(d.runId || '') + '</b> · ' + esc((d.ts || '').replace('T', ' ')) + '<br>'
        + 'Faithfulness ' + (d.faithfulness || '—') + ' · Relevancy ' + (d.answer_relevancy || '—') + '<br>'
        + 'Precision ' + (d.context_precision || '—') + ' · Recall ' + (d.context_recall || '—') + '<br>'
        + 'Refusal ' + (d.refusal || '—') + ' · ' + (d.n || '') + ' questions<br>'
        + '<span style="color:#93c5fd">Click to load this run</span>';
      tip.hidden = false;
    });
    dot.addEventListener('mousemove', function (e) {
      if (!panel) return;
      var r = panel.getBoundingClientRect();
      var x = e.clientX - r.left + 14, y = e.clientY - r.top + 14;
      x = Math.min(x, r.width - 240); y = Math.min(y, r.height - 110);
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    });
    dot.addEventListener('mouseleave', function () { tip.hidden = true; });
    dot.addEventListener('click', function () { tip.hidden = true; loadRun(dot.getAttribute('data-run-id')); });
  });

  markActiveDot();
})();
"""
