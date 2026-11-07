"""FastAPI backend for the Nexora Vercel build.

Endpoints:
    GET    /api/health                  liveness + LLM mode
    POST   /api/upload                  multipart PDF upload, auto-analyzes
    POST   /api/sample                  analyze the bundled Aurora fixture
    POST   /api/ask                     grounded Q&A against a session
    DELETE /api/session/{session_id}    drop a session

Sessions live in an in-memory dict keyed by uuid4. No persistence, no
accounts, no keys on disk — GROQ_API_KEY comes from the environment only.
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import core, llm

APP_VERSION = "1.0.0"

app = FastAPI(title="Nexora backend", version=APP_VERSION)

# Dev-open CORS. Production must restrict this to the Vercel domain —
# see ../DEPLOY.md.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store: session_id -> analysis bundle from core.
_sessions: dict = {}

SAMPLE_PDF = Path(__file__).resolve().parent / "sample" / "test_document.pdf"


class AskRequest(BaseModel):
    session_id: str
    question: str


def _retrieval_label(dense_available: bool) -> str:
    return (
        "hybrid dense + keyword (FAISS)"
        if dense_available
        else "keyword-only"
    )


def _store_analysis(analysis: dict) -> str:
    """Store an analysis bundle and return its new session id."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = analysis
    return session_id


def _analysis_response(session_id: str, filename: str, analysis: dict) -> dict:
    """Shape shared by /api/upload and /api/sample."""
    text = analysis.get("text") or ""
    chunks = analysis.get("chunks") or []
    dense_available = bool(analysis.get("dense_available"))
    return {
        "session_id": session_id,
        "filename": filename,
        "page_count": analysis.get("page_count", 0),
        "word_count": len(text.split()),
        "chunk_count": len(chunks),
        "dense_available": dense_available,
        "retrieval_mode": "hybrid" if dense_available else "keyword",
        "summary": analysis.get("summary") or "",
        "sensitive_data": analysis.get("sensitive_data") or [],
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": APP_VERSION, "llm_mode": llm.llm_mode()}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    data = await file.read()
    try:
        analysis = core.analyze_pdf_bytes(data, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    session_id = _store_analysis(analysis)
    return _analysis_response(session_id, file.filename, analysis)


@app.post("/api/sample")
def sample() -> dict:
    try:
        analysis = core.analyze_pdf_file(str(SAMPLE_PDF))
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    session_id = _store_analysis(analysis)
    return _analysis_response(session_id, SAMPLE_PDF.name, analysis)


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    analysis = _sessions.get(req.session_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Unknown session_id.")
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    result = core.ask_question(req.question, analysis["index_data"])
    dense_available = bool(result.get("dense_available"))
    top_chunks = [
        {"page": record.get("page"), "text": record.get("text", "")}
        for record in (result.get("chunks") or [])[:3]
    ]
    return {
        "answer": result["answer"],
        "citations": result.get("citations") or [],
        "support": result.get("support"),
        "refused": bool(result.get("refused")),
        "best_score": float(result.get("best_score") or 0.0),
        "dense_available": dense_available,
        "retrieval_label": _retrieval_label(dense_available),
        "chunks": top_chunks,
    }


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str) -> dict:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Unknown session_id.")
    del _sessions[session_id]
    return {"status": "ok"}
