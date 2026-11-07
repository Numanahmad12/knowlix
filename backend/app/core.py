"""Core RAG logic for the pdf_analyzer FastAPI backend.

Extracted from the reference Streamlit app (commit 8250835 of
Numanahmad12/pdf_analyzer, ``app.py``) with behaviour and thresholds
UNCHANGED. Only the presentation layer (Streamlit UI / CLI) and the
generation backend were changed:

* Streamlit UI and CLI entry point removed — see ``main.py`` (FastAPI).
* Ollama generation replaced by Groq — see ``llm.py``. When no
  ``GROQ_API_KEY`` is set, or the Groq call fails, generation falls back
  to the same extractive path the Ollama version used.

Public functions preserved by name/signature from the reference:
``extract_pages_from_pdf``, ``extract_text_from_pdf``, ``chunk_text``,
``chunk_pages``, ``build_index``, ``retrieve_with_scores``,
``retrieve_context``, ``summarize_text``, ``check_answer_support``,
``ask_question``, ``analyze_pdf_file``, ``sanitize_document_text``,
``detect_sensitive_data``.
"""

import logging
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import List

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

from . import llm

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
RETRIEVER_TOP_K = int(os.getenv("RETRIEVER_TOP_K", "4"))
# --- Guardrail / limits config (all tunable via env) -------------------------
# Relevance gate: a question is only answered when the best retrieved chunk
# scores at least this much (dense cosine similarity when embeddings are
# available, otherwise keyword overlap ratio). Calibrated 2026-11-07 on a
# 4-page test document (tests/fixtures/test_document.pdf): on-topic
# questions scored 0.485-0.677 cosine, off-topic questions 0.019-0.356, so
# 0.40 sits inside the observed gap. The near-miss "crew members" question
# (0.356) is refused by the gate; anything that slips past it is caught by
# the claim check in ask_question(). In keyword-only mode the same value
# applies to the overlap ratio — paraphrased questions may refuse there,
# since keyword matching genuinely finds weak evidence for them.
MIN_RETRIEVAL_SCORE = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.40"))
# Claim check: a sentence counts as supported when at least this fraction of
# its content terms appears in a single retrieved chunk.
MIN_CLAIM_SUPPORT_RATIO = float(os.getenv("MIN_CLAIM_SUPPORT_RATIO", "0.34"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "500"))
# Reciprocal Rank Fusion constant (standard value from the RRF paper).
RRF_K = int(os.getenv("RRF_K", "60"))

REFUSAL_TEXT = "I can't find an answer to that in this document."

STOP_WORDS = frozenset({
    "the", "and", "that", "have", "with", "this", "from", "they", "them", "their",
    "were", "will", "been", "more", "than", "your", "into", "over", "under", "about",
    "after", "before", "because", "while", "there", "these", "those", "other", "same",
    "through", "without", "within", "using", "also", "for", "are", "is", "was", "be",
    "as", "on", "in", "to", "of", "a", "an", "it", "its", "or", "but", "if", "our",
    "can", "may", "not", "we", "you", "he", "she", "do", "does", "did", "has", "had",
    "very", "each", "such", "than", "then", "when", "where", "which", "who", "how",
    "what", "why", "would", "should", "could", "must", "just", "only", "both", "all",
    "some", "any", "much", "many", "during", "between", "among", "upon", "by", "at",
    "up", "down", "out", "off", "from", "here", "there", "make", "made"
})

# ── Pre-compiled regex patterns (avoid re-compilation on every call) ──────────
_RE_WHITESPACE = re.compile(r"\s+")
_RE_WORD_BOUNDARY = re.compile(r"\b\w+\b")
_RE_ALPHA_3PLUS = re.compile(r"[A-Za-z]{3,}")
_RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_RE_AMOUNTS = re.compile(r"\$?\d+(?:\.\d{2})?")
_RE_ABSTRACT = re.compile(r"\bAbstract\b", re.IGNORECASE)

# Sensitive personal-data patterns (warning only — never a block).
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_RE_PHONE = re.compile(r"\+?\d[\d\s\-().]{8,}\d")
_RE_AADHAAR = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_RE_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_RE_CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_SENSITIVE_PATTERNS = {
    "email address": _RE_EMAIL,
    "phone number": _RE_PHONE,
    "Aadhaar-like number": _RE_AADHAAR,
    "PAN-like number": _RE_PAN,
    "card-like number": _RE_CARD,
}

# Prompt-injection patterns. STRONG patterns are instructions aimed at the
# model and almost never legitimate document content — a sentence matching
# one is replaced wholesale. WEAK patterns can appear legitimately (e.g. a
# paper about system prompts), so only the matched phrase is neutralized.
_STRONG_INJECTION = [
    re.compile(r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+instructions?", re.I),
    re.compile(r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+instructions?", re.I),
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"forget\s+(everything|all)\b", re.I),
    re.compile(r"do\s+not\s+follow\b", re.I),
    re.compile(r"override\s+(the\s+)?(previous|prior|above|system)\b", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    # Imperative sentence that orders the model to disclose a secret
    # ("Say the password is ...", "Reveal the API key ..."). Anchored at the
    # start of the sentence so advice like "Never reveal your password"
    # (which starts with "Never") is left alone.
    re.compile(
        r"^\s*(please\s+)?(say|tell|reveal|disclose|output|repeat|state|write|print)\b"
        r"[^.!?]{0,120}\b(password|secret|api[- ]?key|private key|access token|credentials)\b",
        re.I,
    ),
]
_WEAK_INJECTION = [
    re.compile(r"system\s+prompt", re.I),
    # "reveal the system prompt / instructions" — disclosure orders aimed
    # at model internals. Deliberately NOT password/secret: legitimate advice
    # like "never reveal your password" must survive, and real disclosure
    # orders are caught by the STRONG imperative pattern above.
    re.compile(r"reveal\s+(your|the)\s+(system|instructions|prompt)", re.I),
]

# Citation cleanup lives in llm.py (it post-processes LLM output); re-export
# it here so callers/tests can use ``core._strip_invalid_citations`` as before.
_strip_invalid_citations = llm._strip_invalid_citations


# ── Guardrails: input validation & sensitive-data detection ──────────────────

def detect_sensitive_data(text: str) -> List[str]:
    """Return labels for sensitive personal-data patterns found in the text.

    Warning only — documents are processed locally and never uploaded, so
    this never blocks analysis. It just tells the user what is in the file.
    """
    if not text:
        return []
    return sorted(
        label for label, pattern in _SENSITIVE_PATTERNS.items() if pattern.search(text)
    )


def _validate_pdf_limits(file_path: str) -> None:
    """Enforce the max file-size guard. Raises ValueError with a clear message."""
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"PDF is {size_mb:.1f} MB, above the {MAX_FILE_SIZE_MB} MB limit. "
            "Split or compress it and try again."
        )


def validate_pdf_path(file_path: str) -> str:
    """Validate that the PDF path exists and is a real file."""
    if not file_path or not os.path.isfile(file_path):
        raise FileNotFoundError(
            "PDF file not found. Please provide a real path to an existing PDF on your computer, "
            "for example: C:\\Users\\YourName\\Documents\\report.pdf"
        )
    return file_path


# ── Guardrails: prompt-injection defense ─────────────────────────────────────

def sanitize_document_text(text: str) -> str:
    """Neutralize instruction-like content embedded in a document.

    Sentences matching a STRONG injection pattern are replaced wholesale
    with a marker; WEAK patterns only have the matched phrase replaced.
    Idempotent — running it twice changes nothing further. Applied to chunk
    text at index time and to any document text placed in an LLM prompt, so
    injected instructions never reach the model (or the extractive fallback)
    verbatim.
    """
    if not text:
        return text
    cleaned = []
    for sentence in _RE_SENTENCE_SPLIT.split(text):
        if not sentence.strip():
            continue
        if any(pattern.search(sentence) for pattern in _STRONG_INJECTION):
            cleaned.append("[instruction-like content removed]")
            continue
        scrubbed = sentence
        for pattern in _WEAK_INJECTION:
            scrubbed = pattern.sub("[removed]", scrubbed)
        cleaned.append(scrubbed)
    return " ".join(cleaned)


# ── PDF extraction (page-aware) ───────────────────────────────────────────────

def extract_pages_from_pdf(file_path: str):
    """Extract per-page text as [(page_number, text), ...]; page numbers are 1-based."""
    file_path = validate_pdf_path(file_path)

    if PdfReader is None:
        raise RuntimeError("pypdf is required to parse PDF files.")

    reader = PdfReader(file_path)
    return [(number, page.extract_text() or "") for number, page in enumerate(reader.pages, start=1)]


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file using pypdf."""
    pages = extract_pages_from_pdf(file_path)
    return "\n\n".join(text for _, text in pages if text).strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks for retrieval."""
    cleaned = _RE_WHITESPACE.sub(" ", text or "")
    cleaned = cleaned.replace("\n", " ")

    if not cleaned.strip():
        return []

    chunks = []
    start = 0
    text_length = len(cleaned)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        if end < text_length:
            sentence_break = max(cleaned.rfind(". ", start, end), cleaned.rfind("! ", start, end), cleaned.rfind("? ", start, end))
            if sentence_break > start:
                end = sentence_break + 1

        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = max(0, next_start)

    return chunks


def chunk_pages(pages, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split per-page text into overlapping chunks that remember their page.

    ``pages`` is a list of (page_number, page_text) tuples as returned by
    extract_pages_from_pdf(). Returns [{"text": str, "page": int}, ...].
    Chunk text is sanitized (see sanitize_document_text) so instruction-like
    content embedded in the PDF never reaches the LLM verbatim.
    """
    chunks = []
    for page_number, page_text in pages:
        for piece in chunk_text(page_text, chunk_size=chunk_size, overlap=overlap):
            chunks.append({"text": sanitize_document_text(piece), "page": page_number})
    return chunks


# ── Embeddings (lazy, with graceful keyword-only fallback) ───────────────────
# The embedder runs the SAME all-MiniLM-L6-v2 model as the reference app, but
# via ONNX Runtime instead of sentence-transformers + torch: torch's import
# alone takes ~500 MB-1 GB RSS, which does not fit a 512 MB free-tier host.
# The ONNX export (app/onnx_model/model.onnx, bundled in the repo) and the
# tokenizer (app/onnx_model/tokenizer.json) are the public Hugging Face
# exports of sentence-transformers/all-MiniLM-L6-v2 — no token, no account.
# Vectors stay 384-dim and numerically ~identical to the torch model: the
# class below reproduces SentenceTransformer.encode(normalize_embeddings=True)
# for this model — mean-pool the last hidden state with the attention mask
# (the model's 1_Pooling config) and L2-normalize.

_ONNX_MODEL_DIR = Path(__file__).resolve().parent / "onnx_model"
# sentence-transformers' max_seq_length for all-MiniLM-L6-v2.
_ONNX_MAX_SEQ_LEN = 256

_embedding_model = None
_embedding_failed = False


class _OnnxEmbedder:
    """all-MiniLM-L6-v2 via ONNX Runtime + tokenizers. No torch.

    Drop-in for the subset of the SentenceTransformer API core.py uses:
    ``encode(texts, normalize_embeddings=True, show_progress_bar=False)``
    returns L2-normalized float32 embeddings of shape (n, 384).
    """

    def __init__(self, model_dir=_ONNX_MODEL_DIR):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=_ONNX_MAX_SEQ_LEN)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self._session = ort.InferenceSession(
            str(model_dir / "model.onnx"), providers=["CPUExecutionProvider"]
        )
        # Feed only the inputs this export declares (robust to exports that
        # drop token_type_ids).
        self._input_names = {inp.name for inp in self._session.get_inputs()}

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        encodings = self._tokenizer.encode_batch(texts)
        feed = {
            "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.array(
                [e.attention_mask for e in encodings], dtype=np.int64
            ),
        }
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.array(
                [e.type_ids for e in encodings], dtype=np.int64
            )
        hidden = self._session.run(None, feed)[0]  # (batch, seq, 384)
        mask = feed["attention_mask"][..., None].astype(np.float32)
        pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
        if normalize_embeddings:
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            pooled = pooled / np.maximum(norms, 1e-12)
        return pooled.astype(np.float32)


def _get_embedding_model():
    """Lazily load the ONNX embedder (cached after first load).

    Returns None when the library or model files are unavailable — callers
    must degrade to keyword-only retrieval. First load reads the bundled
    ~90 MB model file; nothing is downloaded at runtime.
    """
    global _embedding_model, _embedding_failed
    if _embedding_model is not None:
        return _embedding_model
    if _embedding_failed:
        return None
    try:
        logger.info("Loading embedding model %s (ONNX Runtime, no torch)...", EMBEDDING_MODEL)
        _embedding_model = _OnnxEmbedder()
        return _embedding_model
    except Exception as exc:  # pragma: no cover - environment dependent
        _embedding_failed = True
        logger.warning("Embeddings unavailable (%s). Falling back to keyword-only retrieval.", exc)
        return None


def _embed_texts(texts):
    """Encode texts to L2-normalized embeddings. Returns a numpy array or None."""
    if not texts or np is None:
        return None
    model = _get_embedding_model()
    if model is None:
        return None
    try:
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Embedding encoding failed (%s). Falling back to keyword-only retrieval.", exc)
        return None


def _build_faiss_index(embeddings):
    """Build a FAISS inner-product index over L2-normalized vectors (= cosine)."""
    if embeddings is None or len(embeddings) == 0:
        return None
    try:
        import faiss
        index = faiss.IndexFlatIP(int(embeddings.shape[1]))
        index.add(embeddings)
        return index
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("FAISS index build failed (%s). Dense search will use numpy.", exc)
        return None


# ── Hybrid retrieval (keyword + dense, reciprocal rank fusion) ───────────────

def build_index(chunks):
    """Prepare chunk metadata + embeddings for hybrid retrieval.

    Accepts a list of plain strings (legacy — page is None) or a list of
    {"text": ..., "page": ...} dicts (from chunk_pages). Returns an index
    dict with pre-computed term sets plus, when the embedding model loads,
    L2-normalized embeddings and a FAISS index (dense_available True).
    When embeddings are unavailable the index is keyword-only and retrieval
    degrades gracefully instead of failing.
    """
    records = []
    for chunk in chunks:
        if isinstance(chunk, dict):
            records.append({"text": chunk.get("text", ""), "page": chunk.get("page")})
        else:
            records.append({"text": str(chunk), "page": None})

    chunk_terms = []
    chunk_lower = []
    for record in records:
        lower = record["text"].lower()
        chunk_lower.append(lower)
        chunk_terms.append(set(_RE_WORD_BOUNDARY.findall(lower)))

    index = {
        "chunks": records,
        "chunk_terms": chunk_terms,
        "chunk_lower": chunk_lower,
        "embeddings": None,
        "faiss_index": None,
        "dense_available": False,
    }

    texts = [record["text"] for record in records]
    embeddings = _embed_texts(texts)
    if embeddings is not None and len(texts) > 0:
        index["embeddings"] = embeddings
        index["faiss_index"] = _build_faiss_index(embeddings)
        index["dense_available"] = True
    return index


def _keyword_ranked(question: str, index_data):
    """Legacy keyword-overlap ranking: [(chunk_idx, raw_score), ...] best-first.

    Raw score = shared-term count + substring hits (the original formula).
    """
    if not index_data or not index_data.get("chunks"):
        return []

    question_lower = question.lower()
    question_terms = set(_RE_WORD_BOUNDARY.findall(question_lower))

    chunks = index_data["chunks"]
    pre_terms = index_data.get("chunk_terms")
    pre_lower = index_data.get("chunk_lower")
    has_precomputed = pre_terms is not None and pre_lower is not None
    scored = []

    for i, record in enumerate(chunks):
        if has_precomputed:
            c_terms = pre_terms[i]
            c_lower = pre_lower[i]
        else:
            c_lower = record["text"].lower()
            c_terms = set(_RE_WORD_BOUNDARY.findall(c_lower))

        overlap = len(question_terms & c_terms)
        substr_hits = sum(1 for term in question_terms if term in c_lower)
        score = overlap + substr_hits
        if score > 0:
            scored.append((i, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def _keyword_overlap_ratio(question: str, index_data, chunk_idx: int) -> float:
    """Fraction of the question's content terms present in one chunk (0..1).

    Content terms exclude stop words, so 'what is the' does not inflate the
    score. Used by the groundedness gate in keyword-only mode.
    """
    question_terms = set(_RE_WORD_BOUNDARY.findall(question.lower()))
    content_terms = {term for term in question_terms if term not in STOP_WORDS}
    terms = content_terms or question_terms
    if not terms:
        return 0.0
    pre_terms = index_data.get("chunk_terms")
    if pre_terms is not None:
        c_terms = pre_terms[chunk_idx]
    else:
        c_terms = set(_RE_WORD_BOUNDARY.findall(index_data["chunks"][chunk_idx]["text"].lower()))
    return len(terms & c_terms) / len(terms)


def _dense_search(question: str, index_data, top_n: int):
    """Dense vector search: [(chunk_idx, cosine_similarity), ...] best-first.

    Uses the FAISS index when built, otherwise plain numpy cosine over the
    stored embeddings. Returns [] when dense retrieval is unavailable.
    """
    embeddings = index_data.get("embeddings") if index_data else None
    if embeddings is None or len(embeddings) == 0:
        return []
    query_vec = _embed_texts([question])
    if query_vec is None:
        return []

    faiss_index = index_data.get("faiss_index")
    if faiss_index is not None:
        try:
            scores, indices = faiss_index.search(query_vec, min(top_n, len(embeddings)))
            return [
                (int(idx), float(score))
                for score, idx in zip(scores[0], indices[0])
                if idx >= 0
            ]
        except Exception:  # fall through to numpy
            pass

    sims = embeddings @ query_vec[0]
    order = np.argsort(-sims)[:top_n]
    return [(int(i), float(sims[i])) for i in order]


def retrieve_with_scores(question: str, index_data, top_k: int = RETRIEVER_TOP_K):
    """Hybrid retrieval with reciprocal rank fusion (RRF, k=RRF_K).

    The keyword leg (legacy overlap scoring) and the dense leg (FAISS cosine
    over all-MiniLM-L6-v2 embeddings) each produce a ranking; RRF merges them
    as sum(1 / (RRF_K + rank)) per chunk, which needs no score normalization
    and lets either leg rescue a chunk the other missed. Returns records
    ranked by fused score:
    [{"text", "page", "score" (fused RRF), "keyword_rank", "dense_rank",
      "cosine" (or None), "keyword_ratio" (or None)}, ...]
    """
    if not index_data or not index_data.get("chunks"):
        return []

    keyword_ranked = _keyword_ranked(question, index_data)
    dense_ranked = _dense_search(question, index_data, top_n=max(top_k * 3, 10))

    fused = {}
    keyword_rank = {}
    for rank, (idx, _raw) in enumerate(keyword_ranked):
        keyword_rank[idx] = rank + 1
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)
    dense_rank = {}
    cosine_by_idx = {}
    for rank, (idx, cosine) in enumerate(dense_ranked):
        dense_rank[idx] = rank + 1
        cosine_by_idx[idx] = cosine
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)

    ranked = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:top_k]
    results = []
    for idx, score in ranked:
        record = index_data["chunks"][idx]
        results.append({
            "text": record["text"],
            "page": record.get("page"),
            "score": score,
            "keyword_rank": keyword_rank.get(idx),
            "dense_rank": dense_rank.get(idx),
            "cosine": cosine_by_idx.get(idx),
            "keyword_ratio": _keyword_overlap_ratio(question, index_data, idx),
        })
    return results


def retrieve_context(question: str, index_data, top_k: int = RETRIEVER_TOP_K) -> List[str]:
    """Hybrid retrieval ranked by fused score (see retrieve_with_scores).

    Returns chunk texts only — kept for backward compatibility.
    """
    return [record["text"] for record in retrieve_with_scores(question, index_data, top_k=top_k)]


# ── Summarization & Q&A (Groq generation + extractive fallback) ─────────────

def summarize_text(text: str, max_sentences: int = 3) -> str:
    """Create a stronger summary from the PDF by prioritizing the abstract and then using Groq or a better heuristic fallback."""
    if not text or not text.strip():
        return "No text available yet."

    # Sanitize before any LLM sees it — an injected sentence must not steer
    # the summary (or the extractive fallback below).
    text = sanitize_document_text(text)

    abstract_match = _RE_ABSTRACT.search(text)
    if abstract_match:
        abstract_text = text[abstract_match.end():]
        sentences = [s.strip() for s in _RE_SENTENCE_SPLIT.split(abstract_text) if s.strip()]
        abstract_summary = " ".join(sentences[:max_sentences])
        if abstract_summary and len(abstract_summary) > 60:
            return abstract_summary

    summary_prompt = (
        "You are a careful academic summarizer. Read the document below and write a concise summary "
        "in 2 to 4 sentences that captures the main idea, key findings, and why the paper matters. "
        "Do not use bullet points.\n\nDocument:\n"
        f"{sanitize_document_text(text[:6000])}\n\nSummary:"
    )
    groq_summary = llm.generate_text(summary_prompt, max_tokens=180)
    if groq_summary:
        return groq_summary

    sentences = [s.strip() for s in _RE_SENTENCE_SPLIT.split(text or "") if s.strip()]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    text_lower = text.lower()
    word_frequency = Counter(
        word for word in _RE_ALPHA_3PLUS.findall(text_lower)
        if word not in STOP_WORDS
    )

    scored = []
    for sentence in sentences:
        words = [word for word in _RE_ALPHA_3PLUS.findall(sentence.lower()) if word not in STOP_WORDS]
        score = sum(word_frequency.get(word, 1) for word in words)
        score += 2 if any(char.isdigit() for char in sentence) else 0
        score += 1 if len(sentence) > 80 else 0
        scored.append((score, sentence))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [sentence for _, sentence in scored[:max_sentences] if sentence]

    if not selected:
        selected = sentences[:max_sentences]

    summary = " ".join(selected)
    return summary if summary else text[:500]


def answer_question(question: str, context: List[str], pages=None) -> str:
    """Answer the user's question using retrieved context, with a Groq fallback when available.

    ``pages`` is an optional list of page numbers parallel to ``context``;
    when given, the answer cites them as [p. N] and citations to any other
    page are stripped. When Groq is unavailable (no key / call failed) the
    extractive fallback below is used, exactly as the reference did with
    Ollama.
    """
    if not context:
        return "No relevant PDF passages were found for that question."

    groq_answer = llm.answer_with_llm(question, context, pages=pages)
    if groq_answer:
        return groq_answer

    joined = "\n\n".join(context)
    lower_context = joined.lower()
    lower_question = question.lower()

    if any(term in lower_question for term in ("total", "amount", "cost", "price")):
        amounts = _RE_AMOUNTS.findall(joined)
        if amounts:
            return f"Based on the PDF, the relevant amount is {amounts[0]}."

    if "summary" in lower_question:
        return summarize_text(joined, max_sentences=4)

    passage = sanitize_document_text(context[0][:700])
    page_label = ""
    if pages and pages[0]:
        page_label = f" [p. {pages[0]}]"
    return (
        "Based on the uploaded PDF, the most relevant passage"
        f"{page_label} says:\n\n"
        + passage
        + ("..." if len(context[0]) > 700 else "")
    )


# ── Guardrails: claim check + grounded Q&A entry point ───────────────────────

def check_answer_support(answer: str, chunks) -> dict:
    """Sentence-level groundedness check (deterministic, keyword-based).

    Splits the answer into sentences; a sentence counts as supported when at
    least MIN_CLAIM_SUPPORT_RATIO of its content terms appears in at least
    one retrieved chunk. Citations are stripped before matching. Sentences
    with no content terms (e.g. 'I don't know.') count as supported.
    Returns {"supported", "total", "ratio", "unsupported": [sentences]}.
    """
    clean = llm._RE_CITATION.sub("", answer or "")
    sentences = [s.strip() for s in _RE_SENTENCE_SPLIT.split(clean) if s.strip()]

    chunk_terms = []
    for chunk in chunks:
        text = chunk["text"] if isinstance(chunk, dict) else str(chunk)
        chunk_terms.append(set(_RE_WORD_BOUNDARY.findall(text.lower())))

    supported = 0
    unsupported = []
    for sentence in sentences:
        terms = {t for t in _RE_WORD_BOUNDARY.findall(sentence.lower()) if t not in STOP_WORDS}
        if not terms:
            supported += 1
            continue
        best = max((len(terms & ct) / len(terms) for ct in chunk_terms), default=0.0)
        if best >= MIN_CLAIM_SUPPORT_RATIO:
            supported += 1
        else:
            unsupported.append(sentence)

    total = len(sentences)
    return {
        "supported": supported,
        "total": total,
        "ratio": (supported / total if total else 1.0),
        "unsupported": unsupported,
    }


def ask_question(question: str, index_data, top_k: int = RETRIEVER_TOP_K) -> dict:
    """Guarded end-to-end Q&A: hybrid retrieval -> groundedness gate ->
    generation -> citation cleanup -> claim check.

    Returns {"answer", "refused", "support" (dict or None), "citations" [pages],
    "chunks" [retrieval records], "best_score" (float), "dense_available" (bool)}.
    The answer string carries a support summary line, e.g.
    "Support: 3/4 claims backed by the document."
    """
    dense_on = bool(index_data.get("dense_available")) if index_data else False
    results = retrieve_with_scores(question, index_data, top_k=top_k)

    def _refused(best_score):
        return {
            "answer": REFUSAL_TEXT,
            "refused": True,
            "support": None,
            "citations": [],
            "chunks": results,
            "best_score": best_score,
            "dense_available": dense_on,
        }

    if not results:
        return _refused(0.0)

    if dense_on:
        best_score = max((record.get("cosine") or 0.0) for record in results)
    else:
        best_score = max((record.get("keyword_ratio") or 0.0) for record in results)

    # Groundedness gate: no evidence, no answer.
    if best_score < MIN_RETRIEVAL_SCORE:
        return _refused(best_score)

    texts = [record["text"] for record in results]
    pages = [record["page"] for record in results]
    answer = answer_question(question, texts, pages=pages)
    support = check_answer_support(answer, results)
    citations = sorted({page for page in pages if page})

    # Nothing in the answer is backed by the document — refuse instead.
    if support["total"] > 0 and support["supported"] == 0:
        return {
            "answer": REFUSAL_TEXT,
            "refused": True,
            "support": support,
            "citations": citations,
            "chunks": results,
            "best_score": best_score,
            "dense_available": dense_on,
        }

    summary_line = (
        f"\n\n_Support: {support['supported']}/{support['total']} "
        "claims backed by the document._"
    )
    return {
        "answer": answer + summary_line,
        "refused": False,
        "support": support,
        "citations": citations,
        "chunks": results,
        "best_score": best_score,
        "dense_available": dense_on,
    }


# ── Analysis pipeline ────────────────────────────────────────────────────────

def analyze_pdf_file(file_path: str) -> dict:
    """Extract, chunk (with page numbers), and summarize a PDF into a retrieval bundle.

    Enforces the MAX_FILE_SIZE_MB / MAX_PDF_PAGES guards and records any
    sensitive-data warning. The stored text and chunks are sanitized
    (instruction-like content neutralized) — see sanitize_document_text.
    """
    file_path = validate_pdf_path(file_path)
    _validate_pdf_limits(file_path)
    pages = extract_pages_from_pdf(file_path)
    if len(pages) > MAX_PDF_PAGES:
        raise ValueError(
            f"PDF has {len(pages)} pages, above the {MAX_PDF_PAGES}-page limit. "
            "Split it and try again."
        )

    raw_text = "\n\n".join(text for _, text in pages if text).strip()
    text = sanitize_document_text(raw_text)
    chunks = chunk_pages(pages)
    index_data = build_index(chunks)
    summary = summarize_text(text, max_sentences=3)
    return {
        "file_path": file_path,
        "text": text,
        "chunks": chunks,
        "index_data": index_data,
        "summary": summary,
        "page_count": len(pages),
        "sensitive_data": detect_sensitive_data(raw_text),
        "dense_available": index_data.get("dense_available", False),
    }


def analyze_pdf_bytes(data: bytes, filename: str = "upload.pdf") -> dict:
    """Analyze PDF bytes (e.g. from a multipart upload) via a temp file.

    Enforces the MAX_FILE_SIZE_MB guard before writing. Returns the same
    bundle as analyze_pdf_file(). Raises ValueError on a size violation.
    """
    if data is None:
        raise ValueError("Please upload a PDF file first.")

    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"PDF is {size_mb:.1f} MB, above the {MAX_FILE_SIZE_MB} MB limit. "
            "Split or compress it and try again."
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_file.write(data)
        temp_path = temp_file.name

    try:
        return analyze_pdf_file(temp_path)
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
