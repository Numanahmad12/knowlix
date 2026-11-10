"""EvalLens metric implementations — the four RAGAS metrics.

RAGAS defines faithfulness, answer relevancy, context precision and
context recall. This module implements those same four definitions, in two
modes:

* **Judge mode** (``GROQ_API_KEY`` set): an LLM-as-judge via Knowlix's own
  Groq client (``app.llm.generate_text``). This is the RAGAS-style path:
  claims are extracted from the answer and verified against the retrieved
  context, and relevance questions are generated from the answer.
* **Deterministic mode** (no key): transparent, reproducible measurements
  built on Knowlix's own machinery — ``core.check_answer_support`` for
  faithfulness, page-level ground truth from the golden set for context
  precision, key-fact coverage for context recall, and the local ONNX
  embedder (all-MiniLM-L6-v2) for answer relevancy. Every run JSON records
  which mode produced each number (``judge`` / ``method`` fields), so a
  deterministic score is never mistaken for a judge score.

Why not the RAGAS library itself? It was tried (2026-11-10): ``ragas``
0.4.3 installs but ``import ragas`` fails out of the box
(``langchain_community.chat_models.vertexai`` missing), and pinning
``langchain-community`` to a compatible version breaks ``langchain-core``
for the rest of the tree. RAGAS also needs a LangChain LLM + embeddings
wiring and makes ~10 LLM calls per question, which is slow and
rate-limit-prone on the Groq free tier. The implementations below follow
the published RAGAS definitions; see README.md for the per-metric mapping.

Metric definitions (all in [0, 1], higher is better):

* **faithfulness** — fraction of the answer's claims supported by the
  retrieved context. Judge mode: the judge lists the answer's claims and
  marks each SUPPORTED / NOT SUPPORTED against the context. Deterministic
  mode: ``core.check_answer_support`` sentence ratio. A refused answer
  scores 1.0 (it made no claims).
* **answer_relevancy** — how well the answer addresses the question.
  Judge mode (RAGAS-style): the judge writes 3 questions the answer
  addresses; relevancy is the mean cosine similarity between those
  questions' embeddings and the original question's embedding (local ONNX
  embedder). Deterministic mode: cosine similarity between the question
  and answer embeddings directly, labelled ``embedding_cosine_proxy``.
  Refused answers are excluded from the aggregate (recorded as null).
* **context_precision** — RAGAS formula over the ranked retrieved chunks:
  ``sum(precision@k * v_k) / sum(v_k)`` where ``v_k`` is 1 when chunk k is
  relevant. Relevance here is page-level ground truth from the golden set
  (a chunk is relevant iff its page is in ``relevant_pages``) — chunks are
  built per page by ``core.chunk_pages``, so this is exact, not a guess.
  Computed identically in both modes; the judge is not needed for it.
* **context_recall** — fraction of the ground-truth key facts covered by
  the retrieved chunks. A fact counts as covered when its content terms
  overlap a retrieved chunk at or above ``core.MIN_CLAIM_SUPPORT_RATIO``.
  Also computed identically in both modes.
"""

import json
import logging
import re

from app import core, llm

logger = logging.getLogger(__name__)

# Sentence splitting / citation stripping reuse core's patterns.
_SENTENCE_SPLIT = core._RE_SENTENCE_SPLIT
_CITATION = llm._RE_CITATION
_BOILERPLATE = core._RE_BOILERPLATE

# Citations Groq actually emits: ASCII "[p. 1]" (stripped by _CITATION),
# full-width "【p. 1】" and "[Page 3]". The full-width form contains "p. "
# — a period followed by a space — so the sentence splitter would cut it
# into fragments ("...【p." / "1】.") that the judge then marks NOT
# SUPPORTED, deflating faithfulness by construction (Run 3, 2026-11-10:
# 16 questions below 1.0, most of them 0.5 from exactly this). Strip all
# three forms before splitting.
_RE_CITATION_FULLWIDTH = re.compile(r"【p\.?\s*\d+】")
_RE_CITATION_PAGE = re.compile(r"\[Page\s*\d+\]", re.IGNORECASE)

# Judge prompts use at most this many generated questions for relevancy.
RELEVANCY_NUM_QUESTIONS = 3

# A chunk counts as supporting a key fact when the fact's content terms
# overlap the chunk at this ratio (same bar as core's claim check).
FACT_SUPPORT_RATIO = core.MIN_CLAIM_SUPPORT_RATIO


# ── Small helpers ────────────────────────────────────────────────────────────

def _clean_answer(answer: str) -> str:
    """Strip citations, the support-summary line and boilerplate from an answer."""
    if not answer:
        return ""
    clean = _CITATION.sub("", answer)
    clean = _RE_CITATION_FULLWIDTH.sub("", clean)
    clean = _RE_CITATION_PAGE.sub("", clean)
    clean = _BOILERPLATE.sub("", clean)
    clean = re.sub(r"_Support:.*?_", "", clean, flags=re.DOTALL)
    return clean.strip()


def _split_claims(answer: str) -> list[str]:
    """Split a cleaned answer into claim sentences (non-empty, has content terms)."""
    clean = _clean_answer(answer)
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(clean) if s.strip()]
    return [
        s for s in sentences
        if {t for t in core._RE_WORD_BOUNDARY.findall(s.lower()) if t not in core.STOP_WORDS}
    ]


def _content_terms(text: str) -> set[str]:
    return {t for t in core._RE_WORD_BOUNDARY.findall((text or "").lower()) if t not in core.STOP_WORDS}


def _cosine(a, b) -> float:
    """Cosine similarity between two 1-D numpy vectors (already L2-normalised)."""
    import numpy as np

    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# ── Faithfulness ─────────────────────────────────────────────────────────────

def _judge_claims_supported(claims: list[str], contexts: list[str]) -> list[bool] | None:
    """Ask Groq to verify each claim against the contexts. None on failure."""
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
    ctx = "\n\n".join(f"--- Passage {i + 1} ---\n{c}" for i, c in enumerate(contexts))
    prompt = (
        "You are a strict fact checker. Below are numbered statements and the "
        "document passages they must be checked against. For EACH statement, "
        "reply with exactly one line in the format 'N: SUPPORTED' or "
        "'N: NOT SUPPORTED', where N is the statement number. A statement is "
        "SUPPORTED only if the passages directly state it or it follows from "
        "them without adding new facts. Do not add any other text.\n\n"
        f"Statements:\n{numbered}\n\nPassages:\n{ctx}\n\nVerdicts:"
    )
    raw = llm.generate_text(prompt, max_tokens=400)
    if not raw:
        return None
    verdicts: dict[int, bool] = {}
    for line in raw.strip().splitlines():
        m = re.match(r"\s*(\d+)\s*:\s*(SUPPORTED|NOT SUPPORTED)", line.strip(), re.IGNORECASE)
        if m:
            verdicts[int(m.group(1))] = m.group(2).upper().startswith("SUPPORTED")
    if len(verdicts) != len(claims):
        logger.warning(
            "Judge returned %d verdicts for %d claims; falling back to deterministic faithfulness.",
            len(verdicts), len(claims),
        )
        return None
    return [verdicts[i + 1] for i in range(len(claims))]


def faithfulness(answer: str, chunks: list[dict], refused: bool, judge: bool) -> dict:
    """Faithfulness = supported claims / total claims. See module docstring."""
    if refused:
        return {"score": 1.0, "method": "refused_no_claims", "supported": 0, "total": 0}
    claims = _split_claims(answer)
    if not claims:
        return {"score": 1.0, "method": "no_claims", "supported": 0, "total": 0}
    contexts = [c.get("text", "") for c in chunks]
    if judge and llm.llm_mode() == "groq":
        verdicts = _judge_claims_supported(claims, contexts)
        if verdicts is not None:
            supported = sum(1 for v in verdicts if v)
            return {
                "score": supported / len(claims),
                "method": "groq_judge",
                "supported": supported,
                "total": len(claims),
            }
    # Deterministic fallback: Knowlix's own claim check, run on the cleaned
    # answer — the raw answer carries a "_Support: n/m claims backed by the
    # document._" trailer that would otherwise count as an extra, unsupported
    # claim and deflate the score by construction.
    support = core.check_answer_support(_clean_answer(answer), chunks)
    return {
        "score": support["ratio"],
        "method": "deterministic_claim_check",
        "supported": support["supported"],
        "total": support["total"],
    }


# ── Answer relevancy ─────────────────────────────────────────────────────────

def _embed_one(text: str):
    """Embed one string with the local ONNX embedder. None if unavailable."""
    vecs = core._embed_texts([text])
    if vecs is None or len(vecs) == 0:
        return None
    return vecs[0]


def _judge_generated_questions(answer: str) -> list[str] | None:
    """Ask Groq to write questions the answer addresses. None on failure."""
    prompt = (
        "Read the answer below and write exactly 3 different questions that "
        "this answer addresses. One question per line, no numbering, no extra "
        "text.\n\nAnswer:\n"
        f"{_clean_answer(answer)}\n\nQuestions:"
    )
    raw = llm.generate_text(prompt, max_tokens=200)
    if not raw:
        return None
    questions = [line.strip() for line in raw.strip().splitlines() if line.strip().endswith("?")]
    return questions[:RELEVANCY_NUM_QUESTIONS] if questions else None


def answer_relevancy(question: str, answer: str, refused: bool, judge: bool) -> dict:
    """Answer relevancy. See module docstring.

    Refused answers return score None (excluded from aggregates) — a
    refusal is correct behaviour for unanswerable questions, not an
    irrelevant answer.
    """
    if refused:
        return {"score": None, "method": "refused_excluded", "generated_questions": []}
    if judge and llm.llm_mode() == "groq":
        generated = _judge_generated_questions(answer)
        q_vec = _embed_one(question)
        if generated and q_vec is not None:
            sims = []
            for gen_q in generated:
                g_vec = _embed_one(gen_q)
                if g_vec is not None:
                    sims.append(_cosine(g_vec, q_vec))
            if sims:
                return {
                    "score": sum(sims) / len(sims),
                    "method": "ragas_style_llm_judge",
                    "generated_questions": generated,
                }
    # Deterministic fallback: embedding cosine between question and answer.
    q_vec = _embed_one(question)
    a_vec = _embed_one(_clean_answer(answer))
    if q_vec is None or a_vec is None:
        return {"score": None, "method": "embeddings_unavailable", "generated_questions": []}
    return {
        "score": max(0.0, min(1.0, _cosine(q_vec, a_vec))),
        "method": "embedding_cosine_proxy",
        "generated_questions": [],
    }


# ── Context precision (RAGAS formula, page-level ground truth) ───────────────

def context_precision(retrieved_pages: list[int | None], relevant_pages: list[int]) -> dict:
    """Context precision over the ranked retrieved chunks.

    A chunk is relevant iff its page is in ``relevant_pages`` (golden-set
    ground truth; chunks are built per page). RAGAS formula:
    sum(precision@k * v_k) / sum(v_k), v_k = 1 when chunk k is relevant.
    """
    relevant = set(relevant_pages or [])
    if not retrieved_pages:
        return {"score": 0.0, "method": "page_ground_truth", "relevant_retrieved": 0}
    flags = [1 if (page in relevant) else 0 for page in retrieved_pages]
    total_relevant = sum(flags)
    if total_relevant == 0:
        return {"score": 0.0, "method": "page_ground_truth", "relevant_retrieved": 0}
    weighted = 0.0
    running = 0
    for k, flag in enumerate(flags, start=1):
        running += flag
        if flag:
            weighted += (running / k) * flag
    return {
        "score": weighted / total_relevant,
        "method": "page_ground_truth",
        "relevant_retrieved": total_relevant,
    }


# ── Context recall (key-fact coverage) ───────────────────────────────────────

def context_recall(key_facts: list[str], chunks: list[dict]) -> dict:
    """Context recall = fraction of ground-truth key facts covered by retrieval.

    A fact counts as covered when its content terms overlap some retrieved
    chunk at or above FACT_SUPPORT_RATIO (same bar as core's claim check).
    """
    if not key_facts:
        return {"score": None, "method": "no_key_facts", "covered": 0, "total": 0}
    chunk_term_sets = [
        set(core._RE_WORD_BOUNDARY.findall((c.get("text", "")).lower())) for c in chunks
    ]
    covered = 0
    uncovered = []
    for fact in key_facts:
        terms = _content_terms(fact)
        if not terms:
            covered += 1
            continue
        best = max(
            (len(terms & ct) / len(terms) for ct in chunk_term_sets),
            default=0.0,
        )
        if best >= FACT_SUPPORT_RATIO:
            covered += 1
        else:
            uncovered.append(fact)
    return {
        "score": covered / len(key_facts),
        "method": "key_fact_coverage",
        "covered": covered,
        "total": len(key_facts),
        "uncovered_facts": uncovered,
    }


# ── One question, all four metrics ───────────────────────────────────────────

def score_question(entry: dict, result: dict, judge: bool) -> dict:
    """Score one golden-set entry against a core.ask_question() result.

    Returns per-metric dicts plus the retrieval facts the dashboard needs.
    """
    chunks = result.get("chunks") or []
    refused = bool(result.get("refused"))
    answer = result.get("answer") or ""
    retrieved_pages = [c.get("page") for c in chunks]
    kind = entry.get("kind", "factual")

    f = faithfulness(answer, chunks, refused, judge)
    r = answer_relevancy(entry["question"], answer, refused, judge)
    p = context_precision(retrieved_pages, entry.get("relevant_pages") or [])
    c = context_recall(entry.get("key_facts") or [], chunks)

    # Unanswerable / adversarial questions have no ground-truth context to
    # retrieve: precision and recall are not meaningful for them. Record
    # them as null and judge them on behaviour instead (see runner).
    if kind in ("unanswerable", "adversarial"):
        p = {"score": None, "method": "not_applicable_no_ground_truth", "relevant_retrieved": 0}
        c = {"score": None, "method": "not_applicable_no_ground_truth", "covered": 0, "total": 0}

    return {
        "id": entry["id"],
        "doc": entry["doc"],
        "kind": kind,
        "question": entry["question"],
        "expected_answer": entry.get("expected_answer", ""),
        "answer": answer,
        "refused": refused,
        "citations": result.get("citations") or [],
        "retrieved_pages": retrieved_pages,
        "best_score": result.get("best_score"),
        "dense_available": bool(result.get("dense_available")),
        "faithfulness": f,
        "answer_relevancy": r,
        "context_precision": p,
        "context_recall": c,
    }


def load_thresholds(path=None) -> dict:
    """Load metric thresholds from thresholds.json (next to this file)."""
    import os

    if path is None:
        path = os.path.join(os.path.dirname(__file__), "thresholds.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
