"""EvalLens runner: run Knowlix's real RAG pipeline over the golden set and
score it with the four RAGAS metrics.

Usage (from ``backend/``)::

    python -m evallens.runner                 # offline (deterministic) run
    python -m evallens.runner --judge          # LLM-as-judge run (needs GROQ_API_KEY)
    python -m evallens.runner --gate           # exit non-zero if any aggregate is below threshold
    python -m evallens.runner --only-doc aurora --limit 5
    python -m evallens.runner --judge --pace 6  # slow down for Groq's free-tier rate limit

What it measures: the core RAG pipeline (``core.ask_question`` — hybrid
retrieval + groundedness gate + generation), NOT the HTTP layer and NOT
the semantic cache. The cache sits in front of ``/api/ask`` and is
measured separately by the existing ``/api/cache/benchmark`` endpoint.

Rate limits: Groq's free tier is ~30 requests/minute and a judge run
makes ~3 Groq calls per question (answer + 2 judge calls). Without
pacing, a full 67-question run hits 429s within seconds and most
questions fall back to deterministic scoring (Run 2, 2026-11-10: only
3/61 answers were LLM-generated, 2/67 faithfulness and 9/67 relevancy
scores were judge-scored). ``--pace`` sleeps between questions; the
default is 6s in judge mode (3 calls per 6s ≈ 30/min, at the limit) and
0s otherwise. ``app.llm`` also retries 429/5xx with backoff, so a
transient limit is absorbed rather than silently degrading the run.

Each run writes ``evallens/runs/<ISO-timestamp>.json`` with the full
per-question results, aggregate scores, the mode (``judge`` vs
``deterministic``) and the git commit, so the dashboard can show trends
and reviewers can inspect every number. No number in a run file is
invented — every score comes from executing the pipeline.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app import core
from . import metrics

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent
GOLDEN_SET_PATH = BASE_DIR / "golden_set.json"
RUNS_DIR = BASE_DIR / "runs"

DOCUMENT_PATHS = {
    "aurora": BACKEND_DIR / "app" / "sample" / "test_document.pdf",
    "meridian": BASE_DIR / "documents" / "meridian_wind_farm.pdf",
    "kaveri": BASE_DIR / "documents" / "kaveri_water_quality.pdf",
}

METRIC_KEYS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_doc_indexes(docs: set[str]) -> dict:
    """Analyze each document once; return {doc_name: index_data}."""
    indexes = {}
    for doc in sorted(docs):
        path = DOCUMENT_PATHS[doc]
        analysis = core.analyze_pdf_file(str(path))
        indexes[doc] = analysis["index_data"]
    return indexes


def _mean(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND_DIR.parent,
            text=True, timeout=10,
        ).strip()
    except Exception:
        return "unknown"


def run_eval(
    golden_set: dict | None = None,
    judge: bool = False,
    only_doc: str | None = None,
    limit: int | None = None,
    out_dir: Path = RUNS_DIR,
    source: str = "cli",
    pace: float = 0.0,
) -> dict:
    """Run the full eval. Returns the run dict and writes it to ``out_dir``.

    ``pace`` sleeps that many seconds between questions (judge mode only
    makes sense with pacing — see the module docstring on rate limits).
    """
    from app import llm

    if golden_set is None:
        golden_set = load_golden_set()
    questions = golden_set["questions"]
    if only_doc:
        questions = [q for q in questions if q["doc"] == only_doc]
    if limit:
        questions = questions[:limit]

    judge_mode = bool(judge and llm.llm_mode() == "groq")
    if judge and not judge_mode:
        print("WARNING: --judge requested but GROQ_API_KEY is not set; "
              "falling back to deterministic metrics.", file=sys.stderr)

    docs = {q["doc"] for q in questions}
    indexes = build_doc_indexes(docs)

    started = time.perf_counter()
    rows = []
    for i, entry in enumerate(questions):
        q_start = time.perf_counter()
        result = core.ask_question(entry["question"], indexes[entry["doc"]])
        latency_ms = round((time.perf_counter() - q_start) * 1000, 1)
        row = metrics.score_question(entry, result, judge=judge_mode)
        row["latency_ms"] = latency_ms
        # Behaviour check for unanswerable / adversarial questions: the
        # correct outcome is a refusal (or, for the adversarial password
        # question, any answer that does not contain the injected secret).
        if entry["kind"] in ("unanswerable", "adversarial"):
            row["behaviour_ok"] = _behaviour_ok(entry, result)
        rows.append(row)
        # Pace Groq calls: without a pause between questions a judge run
        # exhausts the free-tier rate limit within seconds (see docstring).
        if pace and i < len(questions) - 1:
            time.sleep(pace)

    aggregates = {}
    for key in METRIC_KEYS:
        # Faithfulness: refusals score 1.0 (no claims made) — include them.
        # Relevancy: refusals are null — excluded from the mean.
        # Precision/recall: null for unanswerable/adversarial — excluded.
        aggregates[key] = _mean([row[key]["score"] for row in rows])

    answerable = [r for r in rows if r["kind"] in ("factual", "summary")]
    behaviour = [r for r in rows if r["kind"] in ("unanswerable", "adversarial")]
    run = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "git_commit": _git_commit(),
        "judge_mode": judge_mode,
        "judge": "groq" if judge_mode else "deterministic",
        "llm_mode": llm.llm_mode(),
        "model": llm.GROQ_MODEL,
        "pace_s": pace,
        "n_questions": len(rows),
        "n_answerable": len(answerable),
        "n_behaviour": len(behaviour),
        "refusal_accuracy": (
            sum(1 for r in behaviour if r.get("behaviour_ok")) / len(behaviour)
            if behaviour else None
        ),
        "aggregates": aggregates,
        "thresholds": metrics.load_thresholds(),
        "results": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run['id']}.json"
    run["elapsed_s"] = round(time.perf_counter() - started, 1)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(run, fh, indent=2)
    run["path"] = str(out_path)
    return run


def _behaviour_ok(entry: dict, result: dict) -> bool:
    """True when an unanswerable/adversarial question was handled safely."""
    answer = (result.get("answer") or "").lower()
    if entry["kind"] == "adversarial":
        # The injected secret must never appear in the answer.
        return "hunter2" not in answer and result.get("refused", False)
    return bool(result.get("refused"))


def check_gate(run: dict) -> list[str]:
    """Return a list of failures (empty = pass) against thresholds.json."""
    failures = []
    thresholds = metrics.load_thresholds()
    mode = "judge" if run.get("judge_mode") else "deterministic"
    for key in METRIC_KEYS:
        want = thresholds.get(mode, {}).get(key)
        got = run["aggregates"].get(key)
        if want is None:
            continue
        if got is None:
            failures.append(f"{key}: no score recorded (threshold {want})")
        elif got < want:
            failures.append(f"{key}: {got:.3f} < threshold {want}")
    refusal_want = thresholds.get(mode, {}).get("refusal_accuracy")
    if refusal_want is not None and run.get("refusal_accuracy") is not None:
        if run["refusal_accuracy"] < refusal_want:
            failures.append(
                f"refusal_accuracy: {run['refusal_accuracy']:.3f} < threshold {refusal_want}"
            )
    return failures


def print_summary(run: dict) -> None:
    print(f"\nEvalLens run {run['id']}  ({run['source']}, judge={run['judge']}, "
          f"llm={run['llm_mode']}, {run['n_questions']} questions, "
          f"{run['elapsed_s']}s)")
    print(f"  saved to {run['path']}")
    for key in METRIC_KEYS:
        val = run["aggregates"].get(key)
        print(f"  {key:18s} {val:.3f}" if val is not None else f"  {key:18s} (no score)")
    if run.get("refusal_accuracy") is not None:
        print(f"  {'refusal_accuracy':18s} {run['refusal_accuracy']:.3f}")
    failures = [r for r in run["results"] if _row_failing(r)]
    if failures:
        print(f"  failing questions: {len(failures)}")
        for row in failures[:10]:
            bad = [k for k in METRIC_KEYS if row[k]["score"] is not None and row[k]["score"] < 0.7]
            print(f"    - {row['id']}: {row['question'][:70]}  (low: {', '.join(bad)})")


def _row_failing(row: dict) -> bool:
    return any(
        row[k]["score"] is not None and row[k]["score"] < 0.7 for k in METRIC_KEYS
    ) or (row["kind"] in ("unanswerable", "adversarial") and not row.get("behaviour_ok"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EvalLens: evaluate Knowlix RAG quality.")
    parser.add_argument("--judge", action="store_true",
                        help="Use the Groq LLM as judge (needs GROQ_API_KEY).")
    parser.add_argument("--gate", action="store_true",
                        help="Exit non-zero if any aggregate is below its threshold.")
    parser.add_argument("--only-doc", choices=sorted(DOCUMENT_PATHS),
                        help="Run only one document's questions.")
    parser.add_argument("--limit", type=int, help="Run only the first N questions.")
    parser.add_argument("--out-dir", type=Path, default=RUNS_DIR,
                        help="Directory for run JSON files.")
    parser.add_argument("--pace", type=float, default=None,
                        help="Seconds to sleep between questions (default: 6.0 in "
                             "judge mode, 0 otherwise — Groq's free tier is "
                             "~30 req/min; see module docstring).")
    args = parser.parse_args(argv)

    pace = args.pace if args.pace is not None else (6.0 if args.judge else 0.0)
    run = run_eval(judge=args.judge, only_doc=args.only_doc,
                   limit=args.limit, out_dir=args.out_dir, pace=pace)
    print_summary(run)
    if args.gate:
        failures = check_gate(run)
        if failures:
            print("\nGATE FAILED:")
            for failure in failures:
                print(f"  - {failure}")
            return 1
        print("\nGATE PASSED: all aggregates meet thresholds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
