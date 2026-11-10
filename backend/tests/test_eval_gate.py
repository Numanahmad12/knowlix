"""EvalLens quality gate — runs the FULL golden set against thresholds.json.

This is the test CI runs on every push/PR. It executes Knowlix's real RAG
pipeline over all 67 golden questions (offline deterministic mode unless a
GROQ_API_KEY is present, in which case judge mode is used) and fails if any
aggregate score drops below its threshold.

Runtime is ~1–2 minutes (one embedder load, then ~1s per question). It is
marked ``slow`` so the normal unit suite stays fast; run it with::

    pytest tests/test_eval_gate.py -v
    pytest -m "not slow"   # skip it
"""

import os

import pytest

from evallens import metrics, runner

pytestmark = pytest.mark.slow

GATE_MODE = "judge" if os.environ.get("GROQ_API_KEY") else "deterministic"


def test_full_eval_meets_thresholds(tmp_path):
    run = runner.run_eval(
        judge=(GATE_MODE == "judge"),
        out_dir=tmp_path,
        source="pytest-gate",
    )
    failures = runner.check_gate(run)
    # Print the real numbers in the failure message so CI logs show them.
    assert not failures, (
        f"EvalLens gate failed (mode={GATE_MODE}, run {run['id']}): "
        + "; ".join(failures)
        + f" | aggregates={run['aggregates']}"
    )


def test_thresholds_are_documented_and_bounded():
    thresholds = metrics.load_thresholds()
    for mode, values in thresholds.items():
        if mode.startswith("_"):
            continue
        for key, value in values.items():
            assert 0.0 <= value <= 1.0, f"{mode}.{key} = {value} out of range"
