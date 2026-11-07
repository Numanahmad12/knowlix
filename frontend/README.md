# Nexora — Frontend

Next.js (App Router) frontend for the Vercel version of Nexora, the
RAG PDF Q&A app. Upload a PDF, get a summary, and ask questions — every
answer is grounded in the document, with page citations, a support count,
and a retrieval note. Questions the document can't answer are refused
instead of guessed.

This is the frontend only. The FastAPI backend lives in `../backend/`
(a sibling agent builds it against the contract below). The frontend calls
it at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Backend contract

| Call | Shape |
| --- | --- |
| `GET /api/health` | `{"status":"ok","version":"1.0.0","llm_mode":"groq"\|"extractive"}` |
| `POST /api/upload` | multipart, field `file` (PDF, max 20 MB / 500 pages). Returns `{"session_id","filename","page_count","word_count","chunk_count","dense_available","retrieval_mode":"hybrid"\|"keyword","summary","sensitive_data"}`. Upload auto-analyzes; each upload is a fresh session. |
| `POST /api/sample` | no body; analyzes the bundled Aurora sample document, same shape as `/api/upload`. |
| `POST /api/ask` | JSON `{"session_id","question"}` → `{"answer","citations":[page ints],"support":{"supported":int,"total":int},"refused":bool,"best_score":float,"dense_available":bool,"retrieval_label":str,"chunks":[{"page":int,"text":str}]}` (top 3 chunks). |
| `DELETE /api/session/{session_id}` | `{"status":"ok"}` |

Notes carried over from the Phase 3 Streamlit UI
(`../../pdf-analyzer-upgrade/pdf_analyzer/app.py`, `run_streamlit_app()`):

- A newly picked file is auto-analyzed, tracked by file name + size so the
  same file is never re-analyzed; "Analyze this PDF" re-uploads it manually.
- The relevance gate is **0.40**: a refused answer says so, with the returned
  `best_score` in the message.
- Every answer always shows three metadata lines: `Support: n/m claims
  backed by the document.`, `Sources: p. N, p. M`, and
  `Retrieval: {retrieval_label} (best score 0.67)`.
- The backend returns a summary but **no full extracted text**, so there is
  no "Preview extracted text" section here (the Streamlit preview showed the
  first ~6000 chars of text the backend used to return locally). No endpoint
  was invented for it.

## Run locally

```bash
cd frontend
cp .env.example .env.local   # optional; default API URL is http://localhost:8000
npm install
npm run dev                  # http://localhost:3000
```

Then start the backend (see `../backend/README.md`) so upload / sample /
ask work. If the backend isn't running, the page still loads and shows
"Backend unreachable" in the header, and upload / ask attempts report that
clearly instead of failing silently.

Production build:

```bash
npm run build
npm start
```

For a Vercel deploy, set `NEXT_PUBLIC_API_URL` to the deployed backend URL
in the project environment variables. No deploy has been done from here.

## Tech

- Next.js 14 App Router, React 18 — `next`, `react`, `react-dom` only, no
  extra UI libraries.
- Plain CSS in `app/globals.css` (no Tailwind): dark gradient theme
  (deep navy `#07223b` → `#0f172a` → `#111827`), rounded pill buttons,
  card layout, single-column stacking on mobile.
- Single main page: `app/page.js` (+ `app/layout.js`, `lib/api.js` for the
  backend calls).

## Files

```
frontend/
  app/
    layout.js       # page title / metadata, loads globals.css
    page.js         # the whole app: upload, status strip, summary, ask, conversation
    globals.css     # dark theme, cards, metrics, chat, responsive layout
  lib/
    api.js          # backend contract: health / upload / sample / ask / deleteSession
  .env.example      # NEXT_PUBLIC_API_URL=http://localhost:8000
  next.config.js
  package.json
  README.md
```
