# Knowlix backend (FastAPI)

RAG PDF Q&A backend for the Vercel build of Numan Ahmad's Knowlix.
Extracted from the reference Streamlit app (commit 8250835 of
`Numanahmad12/pdf_analyzer`) with behaviour and thresholds unchanged; the
only functional change is Groq (`openai/gpt-oss-120b`) replacing local
Ollama for generation, with the same extractive fallback when no key is set
or the call fails.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | `{"status":"ok","version":"1.0.0","llm_mode":"groq"\|"extractive"}` |
| POST | `/api/upload` | Multipart `file` (PDF). Auto-analyzes, returns a `session_id` + summary. |
| POST | `/api/sample` | Analyzes the bundled Aurora fixture (`app/sample/test_document.pdf`). |
| POST | `/api/ask` | JSON `{"session_id","question"}` → grounded answer + citations + support. |
| DELETE | `/api/session/{session_id}` | Drops a session. |

Sessions are in-memory only (uuid4 keys). Upload limits: 20 MB, 500 pages
(400 on violation). Unknown `session_id` → 404.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: enable Groq answers (without it, answers use the extractive fallback)
cp .env.example .env   # then set GROQ_API_KEY in .env
# or: export GROQ_API_KEY=...

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Check it: `curl http://localhost:8000/api/health`

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
pytest -q
```

The suite ports all 21 reference tests (retrieval, guardrails, citations,
prompt-injection, input caps) plus FastAPI endpoint smoke tests using
`TestClient`. Dense-retrieval tests skip automatically when the embedding
model cannot load (no network / no model cache) — the keyword-only fallback
is tested explicitly instead.

## Layout

```
backend/
  app/
    core.py     pure RAG logic (extraction, chunking, hybrid retrieval, guardrails)
    llm.py      Groq client (key from GROQ_API_KEY env only) + citation cleanup
    main.py     FastAPI app + session store
    sample/     bundled Aurora fixture PDF for /api/sample
  tests/        ported reference tests + endpoint smoke tests
  requirements.txt
  Dockerfile
  .env.example
```

## Notes

- The embedding model (`all-MiniLM-L6-v2`, ~90 MB ONNX) is bundled in
  `app/onnx_model/` and runs via ONNX Runtime — no torch, no download at
  runtime. Without it the backend degrades to keyword-only retrieval.
- CORS is open (`allow_origins=["*"]`) for local dev. Restrict it to the
  Vercel domain before deploying — see `../DEPLOY.md`.
- Never commit a real `.env` or API key.
