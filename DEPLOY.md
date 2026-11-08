# Deploying Knowlix (Vercel build)

Split deployment: the Next.js frontend lives on Vercel, the FastAPI backend
on Render (both free tiers).

## Live deployment (7 Nov 2026)

- **Frontend:** https://pdf-analyzer-vercel-c3zqu6ndw-noumanahmad1916-2595s-projects.vercel.app
- **Backend:** https://pdf-analyzer-backend-16uw.onrender.com
  (`GET /api/health` → `{"status":"ok","version":"1.0.0","llm_mode":"groq"}`)
- `NEXT_PUBLIC_API_URL` on Vercel is set to the Render backend URL.

## Frontend → Vercel

1. Import the repo (or the `frontend/` directory) as a new Vercel project.
2. Set the environment variable:
   - `NEXT_PUBLIC_API_URL` — the public base URL of the deployed backend,
     e.g. `https://knowlix-backend.fly.dev` (no trailing slash).
3. Deploy. The frontend calls the backend at `${NEXT_PUBLIC_API_URL}/api/...`.

## Backend → Fly.io or Render (Dockerfile deploy)

The backend ships as a Docker image (`backend/Dockerfile`, Python 3.12-slim,
uvicorn on `$PORT`).

### Fly.io

```bash
cd backend
fly launch --no-deploy   # pick a region; do NOT add a Postgres/volume
fly secrets set GROQ_API_KEY=...
fly deploy
fly open   # note the https://<app>.fly.dev URL → use as NEXT_PUBLIC_API_URL
```

### Render

1. New → Web Service → deploy from the repo, root directory `backend`,
   runtime Docker.
2. Environment → add `GROQ_API_KEY`.
3. Render assigns `https://<service>.onrender.com` → use as
   `NEXT_PUBLIC_API_URL`.

Free-tier note: Render's free web service sleeps after inactivity, so the
first request after idle can take ~30–60 s to wake.

## Required environment variables

| Variable | Where | Notes |
| --- | --- | --- |
| `GROQ_API_KEY` | Backend | Groq console key. Without it the backend still runs but answers with the extractive fallback only (`llm_mode: "extractive"`). |
| `NEXT_PUBLIC_API_URL` | Frontend (Vercel) | Public backend base URL, no trailing slash. |

Optional backend tunables (defaults in `backend/.env.example`):
`GROQ_MODEL` (default `openai/gpt-oss-120b`), `MIN_RETRIEVAL_SCORE=0.40`,
`MIN_CLAIM_SUPPORT_RATIO=0.34`, `MAX_FILE_SIZE_MB=20`, `MAX_PDF_PAGES=500`,
`RRF_K=60`, `EMBEDDING_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`,
`RETRIEVER_TOP_K`, `REDIS_URL` (optional Redis connection string for exact cache),
`CACHE_ENABLED=true`, `CACHE_SIMILARITY_THRESHOLD=0.90`, `CACHE_TTL_SECONDS=86400`,
`CACHE_MAX_ENTRIES=1000`.

## Before going live

- **CORS:** `backend/app/main.py` currently allows all origins
  (`allow_origins=["*"]`) for local dev. Restrict it to the Vercel domain
  (e.g. `["https://knowlix.vercel.app"]`) before deploying.
- **Keys:** never commit `.env` or a real `GROQ_API_KEY`. Rotate any key
  that was ever shared in chat or pasted into a public place.
- **Health check:** after deploy, `curl <backend-url>/api/health` should
  return `{"status":"ok","version":"1.0.0","llm_mode":"groq","cache_enabled":true}`.
