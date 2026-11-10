"""Server-rendered dashboard for EvalLens (no JavaScript framework).

``render_dashboard(runs, latest)`` returns a single self-contained HTML
page: aggregate score cards for the latest run, a trend table over run
history, and a per-question failure table (which questions failed, on
which metric, with the actual vs expected answer). All numbers come from
real run JSON files — nothing is invented here.
"""

import html

METRIC_KEYS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
METRIC_LABELS = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer relevancy",
    "context_precision": "Context precision",
    "context_recall": "Context recall",
}


def _fmt(value) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "—"


def _failing_rows(run: dict) -> list[dict]:
    rows = []
    for row in run.get("results", []):
        bad = [
            key for key in METRIC_KEYS
            if row.get(key, {}).get("score") is not None and row[key]["score"] < 0.7
        ]
        behaviour_bad = row.get("kind") in ("unanswerable", "adversarial") and not row.get("behaviour_ok")
        if bad or behaviour_bad:
            rows.append((row, bad, behaviour_bad))
    return rows


def render_dashboard(runs: list[dict], latest: dict | None) -> str:
    if latest is None:
        return """<!doctype html><html><head><meta charset="utf-8"><title>EvalLens — Knowlix RAG evaluation</title></head>
<body style="font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 16px">
<h1>EvalLens — Knowlix RAG evaluation</h1>
<p>No eval runs yet. Run one with:</p>
<pre>cd backend && python -m evallens.runner</pre>
</body></html>"""

    agg = latest.get("aggregates") or {}
    cards = "".join(
        f"<div style='border:1px solid #ddd;border-radius:8px;padding:16px;min-width:140px'>"
        f"<div style='font-size:12px;color:#666'>{METRIC_LABELS[key]}</div>"
        f"<div style='font-size:28px;font-weight:700'>{_fmt(agg.get(key))}</div></div>"
        for key in METRIC_KEYS
    )
    refusal = latest.get("refusal_accuracy")
    cards += (
        "<div style='border:1px solid #ddd;border-radius:8px;padding:16px;min-width:140px'>"
        "<div style='font-size:12px;color:#666'>Refusal accuracy</div>"
        f"<div style='font-size:28px;font-weight:700'>{_fmt(refusal)}</div></div>"
    )

    trend_rows = ""
    for run in runs:
        a = run.get("aggregates") or {}
        trend_rows += (
            "<tr>"
            f"<td>{html.escape(str(run.get('timestamp', '')))}</td>"
            f"<td>{html.escape(str(run.get('judge', '')))}</td>"
            f"<td>{run.get('n_questions', '')}</td>"
            + "".join(f"<td>{_fmt(a.get(key))}</td>" for key in METRIC_KEYS)
            + f"<td>{_fmt(run.get('refusal_accuracy'))}</td></tr>"
        )

    fail_rows = ""
    for row, bad, behaviour_bad in _failing_rows(latest):
        metrics = ", ".join(
            f"{key}={_fmt(row[key]['score'])}" for key in bad
        ) or ("behaviour: not refused" if behaviour_bad else "")
        fail_rows += (
            "<tr>"
            f"<td>{html.escape(row['id'])}</td>"
            f"<td>{html.escape(row['question'])}</td>"
            f"<td>{html.escape(row.get('expected_answer', ''))}</td>"
            f"<td>{html.escape((row.get('answer') or '')[:300])}</td>"
            f"<td>{html.escape(metrics)}</td></tr>"
        )
    if not fail_rows:
        fail_rows = "<tr><td colspan='5'>No failing questions in the latest run.</td></tr>"

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>EvalLens — Knowlix RAG evaluation</title></head>
<body style="font-family:system-ui,sans-serif;max-width:1000px;margin:40px auto;padding:0 16px">
<h1>EvalLens — Knowlix RAG evaluation</h1>
<p>Latest run <strong>{html.escape(str(latest.get('id', '')))}</strong> ·
judge: {html.escape(str(latest.get('judge', '')))} · LLM mode: {html.escape(str(latest.get('llm_mode', '')))} ·
{latest.get('n_questions', '')} questions · commit {html.escape(str(latest.get('git_commit', '')))}</p>
<h2>Latest scores</h2>
<div style="display:flex;gap:12px;flex-wrap:wrap">{cards}</div>
<p style="color:#666;font-size:13px">Scores are means over the golden set's answerable questions
(faithfulness includes refusals at 1.0; answer relevancy excludes refusals;
context precision/recall exclude unanswerable and adversarial questions).
See <code>evallens/README.md</code> for the metric definitions.</p>
<h2>Trend</h2>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
<tr><th>Run</th><th>Judge</th><th>Qs</th><th>Faithfulness</th><th>Relevancy</th><th>Precision</th><th>Recall</th><th>Refusal</th></tr>
{trend_rows}
</table>
<h2>Failing questions (latest run)</h2>
<p style="color:#666;font-size:13px">A question is listed when any metric is below 0.7, or when an
unanswerable / adversarial question was not refused.</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
<tr><th>ID</th><th>Question</th><th>Expected</th><th>Actual answer</th><th>Low metrics</th></tr>
{fail_rows}
</table>
</body></html>"""
