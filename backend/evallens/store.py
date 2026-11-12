"""Run-history storage for EvalLens.

Run JSON files live in ``evallens/runs/`` (one file per run, named
``<UTC-timestamp>.json``). They are committed to the repo so the dashboard
can show trends and reviewers can inspect every measured number.
"""

import json
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent / "runs"


def list_runs(runs_dir: Path = RUNS_DIR) -> list[dict]:
    """All runs, newest first, with only the summary fields loaded."""
    runs = []
    if not runs_dir.exists():
        return runs
    for path in sorted(runs_dir.glob("*.json"), reverse=True):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            runs.append({
                "id": data.get("id"),
                "timestamp": data.get("timestamp"),
                "source": data.get("source"),
                "judge": data.get("judge"),
                "llm_mode": data.get("llm_mode"),
                "n_questions": data.get("n_questions"),
                "aggregates": data.get("aggregates") or {},
                "refusal_accuracy": data.get("refusal_accuracy"),
                "path": str(path),
            })
        except Exception:
            continue
    return runs


def latest_run(runs_dir: Path = RUNS_DIR) -> dict | None:
    """The newest full run dict, or None when no runs exist yet.

    Partial runs (a probe with 2 questions, a run killed mid-way) never
    become "latest" — the dashboard and /api/eval/latest show the newest
    run with the full question count instead. Partials stay listed in
    history and loadable by id.
    """
    if not runs_dir.exists():
        return None
    paths = sorted(runs_dir.glob("*.json"), reverse=True)
    if not paths:
        return None
    loaded = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                loaded.append(json.load(fh))
        except Exception:
            continue
    if not loaded:
        return None
    max_n = max((d.get("n_questions") or 0) for d in loaded)
    for data in loaded:
        if (data.get("n_questions") or 0) == max_n:
            return data
    return loaded[0]


def load_run(run_id: str, runs_dir: Path = RUNS_DIR) -> dict | None:
    path = runs_dir / f"{run_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
