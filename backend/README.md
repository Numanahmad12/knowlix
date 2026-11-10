# Knowlix backend (FastAPI)

RAG PDF Q&A backend with Document-Aware Semantic Caching for the Vercel build of Numan Ahmad's Knowlix.
Extracted from the reference Streamlit app (commit 8250835 of `Numanahmad12/pdf_analyzer`) with behaviour and thresholds unchanged; the generation engine uses Groq (`openai/gpt-oss-120b`) with an extractive fallback, augmented with an isolated FAISS semantic caching layer.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | `{"status":"ok","version":"1.0.0","llm_mode":"groq"\|"extractive","cache_enabled":true}` |
| POST | `/api/upload` | Multipart `file` (PDF). Auto-analyzes, returns a `session_id`, `doc_hash`, summary. |
| POST | `/api/sample` | Analyzes the bundled Aurora fixture (`app/sample/test_document.pdf`). |
| POST | `/api/ask` | JSON `{"session_id","question"}` → grounded answer + citations + support + cache telemetry. |
| DELETE | `/api/session/{session_id}` | Drops a session and invalidates its associated cache entries. |
| GET | `/api/cache/stats` | Real-time cache telemetry: hit rate, calls avoided, tokens saved, cost savings. |
| GET | `/api/cache/entries` | Searchable list of active cache entries. |
| GET | `/api/cache/entries/{id}` | Retrieve details for a specific cache entry. |
| DELETE | `/api/cache/entries/{id}` | Invalidate a specific cache entry. |
| POST | `/api/cache/clear` | Clear all cache entries and reset telemetry. |
| GET | `/api/cache/settings` | Read current runtime cache engine configuration. |
| PATCH | `/api/cache/settings` | Update cache thresholds, TTL, or toggle modes dynamically. |
| POST | `/api/cache/benchmark/run` | Execute automated 3-mode architectural benchmark against active session. |
| GET | `/api/cache/benchmarks` | Retrieve historical benchmark execution results. |
| GET | `/api/eval/latest` | EvalLens: latest eval run (full scores). |
| GET | `/api/eval/runs` | EvalLens: eval run history (summaries). |
| GET | `/api/eval/runs/{run_id}` | EvalLens: one eval run (full scores). |
| GET | `/eval` | EvalLens dashboard (HTML): latest scores, trends, per-question failures. |

## Knowlix Semantic Cache Engine

- **Dedicated Vector Store**: An isolated FAISS `IndexFlatIP(384)` index (using `IndexIDMap2`) dedicated exclusively to semantic caching — never mixed with document retrieval vectors.
- **Dual-Tier Caching**: High-speed exact hash lookup (Redis or bounded thread-safe in-memory LRU) + cosine vector similarity matching.
- **Zero-Torch Embeddings**: Reuses the bundled ONNX Runtime `all-MiniLM-L6-v2` embedder (384 dimensions, normalized), fitting within 512 MB Render free-tier RAM.
- **Document & Context Isolation**: Cache entries are bound to document content hashes (`SHA-256`), user ID, tenant ID, and system prompt hashes. Unrelated documents never share cached answers.
- **Intent Safeguard Filters**: Semantic similarity threshold (default 0.90) augmented with heuristic filters detecting negation mismatches, numerical/temporal discrepancies, and entity contrasts.
- **Guardrail Preservation**: Refused questions (`REFUSAL_TEXT`), ungrounded answers, or injection attempts are strictly excluded from storage.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: enable Groq answers and configure Redis
cp .env.example .env   # then set GROQ_API_KEY / REDIS_URL in .env
# or: export GROQ_API_KEY=...

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs: http://localhost:8000/docs

## Run with Docker

```bash
cd backend
docker build -t knowlix-backend .
docker run --rm -p 8000:8000 -e GROQ_API_KEY=... knowlix-backend
```

## Tests

```bash
cd backend
pytest -v              # 52 tests (all core, API, and semantic cache tests)
pytest tests/test_evallens.py -q   # 14 EvalLens unit tests
pytest tests/test_eval_gate.py -q  # EvalLens full 67-question quality gate
```

## EvalLens — RAG evaluation harness

EvalLens (`evallens/`) measures RAG quality against a 67-question golden
set using the four RAGAS metrics (faithfulness, answer relevancy, context
precision, context recall), running the real pipeline — never a mock.
Full docs: [`evallens/README.md`](evallens/README.md).

```bash
cd backend
python -m evallens.runner            # offline run (deterministic, ~10s)
python -m evallens.runner --judge    # Groq LLM-as-judge (needs GROQ_API_KEY)
python -m evallens.runner --gate     # exit non-zero if below thresholds
```

Baseline (2026-11-10, deterministic, 67 questions): faithfulness 1.000,
answer relevancy 0.613, context precision 0.953, context recall 0.997,
refusal accuracy 0.167. Dashboard at `/eval` when the server is running.
CI gate: `.github/workflows/eval.yml`.

## Layout

```
backend/
  app/
    cache/
      __init__.py       package exports
      benchmark.py      3-mode benchmark suite (A: Baseline, B: Exact, C: Semantic)
      engine.py         orchestrator (dual-tier lookup, invalidation, lifecycle)
      exact.py          Redis exact cache with in-memory LRU fallback
      metrics.py        real-time telemetry & financial token savings tracker
      models.py         domain models (CacheEntry, CacheConfig, CacheStats)
      safeguards.py     intent mismatch & semantic drift filters
      vector_store.py   isolated FAISS IndexFlatIP(384) + IndexIDMap2
    core.py             pure RAG logic (extraction, chunking, hybrid retrieval, guardrails)
    llm.py              Groq client + citation cleanup
    main.py             FastAPI app + session store & cache routing
    sample/             bundled Aurora fixture PDF
  tests/
    test_api.py         endpoint smoke tests
    test_core.py        core retrieval, chunking, and guardrail tests
    test_semantic_cache.py  18-point verification suite for semantic caching
  requirements.txt
  Dockerfile
  .env.example
```
