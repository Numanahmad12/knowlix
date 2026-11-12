"""EvalLens unit tests — fast, deterministic, no network, no API key.

These tests cover the metric implementations (with hand-computed expected
values), the golden-set schema, and a small runner smoke test in offline
mode. The full eval gate lives in test_eval_gate.py.
"""

import json
from pathlib import Path

import pytest

from evallens import metrics, runner

GOLDEN_SET_PATH = Path(__file__).resolve().parent.parent / "evallens" / "golden_set.json"
DOCS = {
    "aurora": Path(__file__).resolve().parent.parent / "app" / "sample" / "test_document.pdf",
    "meridian": Path(__file__).resolve().parent.parent / "evallens" / "documents" / "meridian_wind_farm.pdf",
    "kaveri": Path(__file__).resolve().parent.parent / "evallens" / "documents" / "kaveri_water_quality.pdf",
}


# ── Golden set schema ────────────────────────────────────────────────────────

def test_golden_set_is_valid():
    data = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    questions = data["questions"]
    assert 50 <= len(questions) <= 100, f"golden set has {len(questions)} questions"
    ids = [q["id"] for q in questions]
    assert len(set(ids)) == len(ids), "duplicate question ids"
    kinds = {q["kind"] for q in questions}
    assert kinds <= {"factual", "summary", "unanswerable", "adversarial"}
    assert "unanswerable" in kinds and "adversarial" in kinds
    for q in questions:
        assert q["doc"] in DOCS, f"{q['id']}: unknown doc {q['doc']}"
        assert q["question"].strip(), f"{q['id']}: empty question"
        if q["kind"] != "summary":
            assert q["question"].strip().endswith("?"), f"{q['id']}: not a question"
        assert isinstance(q["relevant_pages"], list)
        assert isinstance(q["key_facts"], list)
        if q["kind"] in ("factual", "summary"):
            assert q["relevant_pages"], f"{q['id']}: answerable question needs relevant_pages"
            assert q["key_facts"], f"{q['id']}: answerable question needs key_facts"
            assert q["expected_answer"].strip()
        else:
            assert not q["relevant_pages"] and not q["key_facts"]


def test_golden_set_documents_exist():
    for name, path in DOCS.items():
        assert path.exists(), f"missing document for {name}: {path}"


# ── Context precision (RAGAS formula, hand-computed) ─────────────────────────

def test_context_precision_all_relevant_first():
    # Retrieved pages [1, 1, 2]: relevant pages {1, 2} → all relevant.
    out = metrics.context_precision([1, 1, 2], [1, 2])
    assert out["score"] == pytest.approx(1.0)
    assert out["relevant_retrieved"] == 3


def test_context_precision_ranks_matter():
    # Relevant chunk at rank 3 only: precision@3 = 1/3, one relevant chunk.
    out = metrics.context_precision([2, 3, 1], [1])
    assert out["score"] == pytest.approx(1 / 3)
    # Relevant chunks at ranks 1 and 3: (1/1 + 2/3) / 2 = 5/6.
    out = metrics.context_precision([1, 2, 1], [1])
    assert out["score"] == pytest.approx(5 / 6)


def test_context_precision_none_relevant():
    out = metrics.context_precision([2, 3], [1])
    assert out["score"] == 0.0
    assert metrics.context_precision([], [1])["score"] == 0.0


# ── Context recall (key-fact coverage) ───────────────────────────────────────

def test_context_recall_full_and_partial():
    chunks = [
        {"text": "The Aurora probe launched in March 2024 to study solar wind."},
        {"text": "Its magnetometer measures magnetic fields precisely."},
    ]
    out = metrics.context_recall(
        ["launched in March 2024", "magnetometer measures magnetic fields"], chunks
    )
    assert out["score"] == 1.0
    out = metrics.context_recall(
        ["launched in March 2024", "the probe cost nine billion dollars"], chunks
    )
    assert out["score"] == 0.5
    assert out["uncovered_facts"] == ["the probe cost nine billion dollars"]
    assert metrics.context_recall([], chunks)["score"] is None


# ── Faithfulness (deterministic path) ────────────────────────────────────────

def test_faithfulness_deterministic_supported():
    chunks = [{"text": "The Aurora probe launched in March 2024."}]
    out = metrics.faithfulness(
        "The Aurora probe launched in March 2024.", chunks, refused=False, judge=False
    )
    assert out["score"] == 1.0
    assert out["method"] == "deterministic_claim_check"


def test_faithfulness_deterministic_unsupported():
    chunks = [{"text": "The Aurora probe launched in March 2024."}]
    out = metrics.faithfulness(
        "The Aurora probe launched in March 2024. It was built on Mars by robots.",
        chunks, refused=False, judge=False,
    )
    assert out["score"] < 1.0
    assert out["supported"] < out["total"]


def test_faithfulness_refused_is_one():
    out = metrics.faithfulness("I can't find an answer.", [], refused=True, judge=False)
    assert out["score"] == 1.0


def test_faithfulness_ignores_support_trailer():
    # The "_Support: n/m claims backed by the document._" trailer must not
    # count as an extra unsupported claim.
    chunks = [{"text": "The Aurora probe launched in March 2024."}]
    answer = ("The Aurora probe launched in March 2024.\n\n"
              "_Support: 1/1 claims backed by the document._")
    out = metrics.faithfulness(answer, chunks, refused=False, judge=False)
    assert out["score"] == 1.0


def test_faithfulness_ignores_fullwidth_and_page_citations():
    # Groq emits citations as "【p. 1】" and "[Page 3]" as well as "[p. 1]".
    # The "p. " inside "【p. 1】" contains a period + space, so the sentence
    # splitter would cut it into fragments ("...【p." / "1】.") that a judge
    # marks NOT SUPPORTED. Stripping them first must leave exactly one claim.
    chunks = [{"text": "The Aurora probe launched in March 2024."}]
    for answer in (
        "The Aurora probe launched in March 2024【p. 1】.",
        "The Aurora probe launched in March 2024 [Page 1].",
        "The Aurora probe launched in March 2024 [p. 1].",
    ):
        out = metrics.faithfulness(answer, chunks, refused=False, judge=False)
        assert out["total"] == 1, answer
        assert out["score"] == 1.0, answer


# ── Judge parsing (mocked Groq) ──────────────────────────────────────────────

def test_judge_claims_parsing(monkeypatch):
    import app.llm as llm

    monkeypatch.setattr(
        llm, "generate_text",
        lambda prompt, max_tokens=200: "1: SUPPORTED\n2: NOT SUPPORTED\n",
    )
    verdicts = metrics._judge_claims_supported(
        ["Aurora launched in March 2024.", "Aurora was built on Mars."],
        ["The Aurora probe launched in March 2024."],
    )
    assert verdicts == [True, False]


def test_judge_claims_falls_back_on_bad_verdicts(monkeypatch):
    import app.llm as llm

    monkeypatch.setattr(llm, "generate_text", lambda prompt, max_tokens=200: "looks good!")
    assert metrics._judge_claims_supported(["One claim."], ["Context."]) is None


# ── Runner smoke test (offline, 2 questions) ────────────────────────────────

def test_runner_smoke_offline(tmp_path):
    run = runner.run_eval(
        judge=False, only_doc="aurora", limit=2, out_dir=tmp_path, source="pytest-smoke",
    )
    assert run["judge_mode"] is False
    assert run["n_questions"] == 2
    assert run["aggregates"]["context_precision"] is not None
    assert run["aggregates"]["context_recall"] is not None
    assert 0.0 <= run["aggregates"]["faithfulness"] <= 1.0
    assert (tmp_path / f"{run['id']}.json").exists()
    assert all("latency_ms" in row for row in run["results"])


def test_gate_check_passes_and_fails():
    # Values sit above the thresholds in thresholds.json (set from the
    # measured baseline); the "bad" variant drops faithfulness below 0.95.
    good = {
        "judge_mode": False,
        "aggregates": {
            "faithfulness": 0.99, "answer_relevancy": 0.9,
            "context_precision": 0.98, "context_recall": 0.99,
        },
        "refusal_accuracy": 1.0,
    }
    assert runner.check_gate(good) == []
    bad = dict(good, aggregates=dict(good["aggregates"], faithfulness=0.1))
    failures = runner.check_gate(bad)
    assert failures and "faithfulness" in failures[0]


# ── Dashboard (v3) ───────────────────────────────────────────────────────────

def test_latest_run_skips_partial_probe():
    """latest_run() must return the newest FULL run, never a probe file."""
    from evallens import store

    latest = store.latest_run()
    assert latest is not None
    assert latest["n_questions"] == 67, f"latest is a partial run: {latest['id']}"
    assert latest["id"] == "20261110T154611Z"


def test_dashboard_renders_latest_full_run():
    """render_dashboard() shows the latest full run with the v3 explorer."""
    from evallens import dashboard, store

    runs = store.list_runs()
    latest = store.latest_run()
    page = dashboard.render_dashboard(runs, latest)
    assert latest["id"] in page
    # 67 server-rendered rows + 1 identical row template inside the JS.
    assert page.count("<tr class='qrow'") == 68, "explorer must render all 67 questions"
    assert "Question explorer" in page
    assert "run-switch" in page and "trend-dot" in page
    assert "Gate failed" in page  # Run 4 fails its refusal gate (0.667 < 0.80)
    assert "partial probe run" in page  # the 2-question probe is disclosed, not hidden
    assert "eval-data" in page  # embedded JSON for the client-side interactivity
