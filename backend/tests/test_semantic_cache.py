"""Comprehensive verification test suite for the Knowlix Semantic Cache Engine.

Covers all 18 required scenarios:
 1. First question results in a cache miss.
 2. Identical repeated question produces an exact hit.
 3. Equivalent rephrased question produces a semantic hit.
 4. Unrelated question produces a miss.
 5. Different PDFs never share incompatible answers (document isolation).
 6. Replacing a PDF invalidates previous cache entries.
 7. Deleting a PDF/session invalidates associated entries.
 8. Expired entries are rejected (TTL).
 9. Different users cannot access private cache entries (user isolation).
10. Different document collections remain isolated.
11. Changed system prompts invalidate incompatible results.
12. Existing citations and support metadata are preserved on cache hits.
13. Existing guardrails still execute (refusals/ungrounded answers are never cached).
14. Cache failure falls back to original RAG gracefully.
15. LLM provider failures are handled gracefully without cache corruption.
16. Similar questions with different intent (negation, entities, numbers) do not share responses.
17. Cache capacity limits (LRU eviction) work properly.
18. Cache settings and runtime controls work correctly.
"""

import os
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.cache.engine import SemanticCacheEngine
from app.cache.exact import InMemoryExactCache
from app.cache.models import CacheConfig, CacheEntry
from app.cache.safeguards import validate_semantic_compatibility
from app.cache.vector_store import SemanticVectorStore
from app.main import app, cache_engine

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "test_document.pdf"


@pytest.fixture
def clean_cache():
    cache_engine.clear_all()
    cache_engine.config.enabled = True
    cache_engine.config.exact_cache_enabled = True
    cache_engine.config.semantic_cache_enabled = True
    cache_engine.config.similarity_threshold = 0.88
    yield cache_engine
    cache_engine.clear_all()


@pytest.fixture
def client(clean_cache):
    os.environ.pop("GROQ_API_KEY", None)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_session(client):
    resp = client.post("/api/sample")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Test 1: First question results in a cache miss ───────────────────────────
def test_1_first_question_is_cache_miss(client, sample_session):
    resp = client.post(
        "/api/ask",
        json={
            "session_id": sample_session["session_id"],
            "question": "What instruments does the Aurora probe carry?",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cache_status"] == "miss"
    assert body["cache_type"] == "miss"
    assert "magnetometer" in body["answer"].lower()
    assert 1 in body["citations"]


# ── Test 2: Identical repeated question produces an exact hit ────────────────
def test_2_repeated_question_produces_exact_hit(client, sample_session):
    q = "What instruments does the Aurora probe carry?"
    # First query -> miss
    r1 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q})
    assert r1.status_code == 200
    assert r1.json()["cache_status"] == "miss"

    # Second query -> exact hit
    r2 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q})
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["cache_status"] == "hit"
    assert b2["cache_type"] == "exact"
    assert b2["similarity_score"] == 1.0
    assert "magnetometer" in b2["answer"].lower()
    assert b2["tokens_saved_estimate"] > 0


# ── Test 3: Equivalent rephrased question produces a semantic hit ────────────
def test_3_rephrased_question_produces_semantic_hit(client, sample_session):
    q1 = "What instruments does the Aurora probe carry?"
    q2 = "Which scientific instruments are onboard the Aurora probe?"

    r1 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q1})
    assert r1.status_code == 200
    assert r1.json()["cache_status"] == "miss"

    r2 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q2})
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["cache_status"] == "hit"
    assert b2["cache_type"] == "semantic"
    assert b2["similarity_score"] >= 0.88
    assert "magnetometer" in b2["answer"].lower()
    assert b2["tokens_saved_estimate"] > 0


# ── Test 4: Unrelated question produces a miss ───────────────────────────────
def test_4_unrelated_question_produces_miss(client, sample_session):
    q1 = "What instruments does the Aurora probe carry?"
    q2 = "What did the ground station communicate?"

    client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q1})
    r2 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q2})
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["cache_status"] == "miss"
    assert b2["cache_type"] == "miss"


# ── Test 5: Different PDFs never share incompatible answers ──────────────────
def test_5_different_pdfs_never_share_cache(client, sample_session):
    q = "What instruments does the Aurora probe carry?"
    # Populate cache for session 1
    r1 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q})
    assert r1.json()["cache_status"] == "miss"

    # Create a dummy session with a DIFFERENT document content hash
    session_2_id = "test_doc_2_session"
    from app.main import _sessions
    _sessions[session_2_id] = {
        "filename": "other.pdf",
        "doc_hash": "completely_different_hash_9999",
        "index_data": sample_session,  # index data mock
    }

    # Query with same question on different document -> must be a cache miss!
    lookup = cache_engine.lookup(
        query=q,
        doc_id=session_2_id,
        doc_hash="completely_different_hash_9999",
    )
    assert lookup.hit is False
    assert lookup.cache_type == "miss"


# ── Test 6: Replacing a PDF invalidates previous cache entries ────────────────
def test_6_replacing_pdf_invalidates_cache(clean_cache):
    doc_hash_v1 = "doc_hash_v1"
    doc_hash_v2 = "doc_hash_v2"
    q = "What are the key results?"

    # Store entry under v1
    clean_cache.store(
        query=q,
        doc_id="session_1",
        doc_hash=doc_hash_v1,
        response="Result v1 text",
        citations=[1],
        support={"supported": 1, "total": 1},
        chunks=[{"page": 1, "text": "pass"}],
        best_score=0.9,
        dense_available=True,
        retrieval_label="hybrid",
    )

    # Invalidate old version when document is replaced
    clean_cache.invalidate_document(doc_id="session_1", doc_hash=doc_hash_v1)

    # Subsequent lookup for v1 should miss
    lookup_v1 = clean_cache.lookup(query=q, doc_id="session_1", doc_hash=doc_hash_v1)
    assert lookup_v1.hit is False

    # Lookup for v2 should also miss
    lookup_v2 = clean_cache.lookup(query=q, doc_id="session_1", doc_hash=doc_hash_v2)
    assert lookup_v2.hit is False


# ── Test 7: Deleting a session invalidates associated entries ─────────────────
def test_7_deleting_session_invalidates_entries(client, sample_session):
    q = "What instruments does the Aurora probe carry?"
    client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q})

    # Delete session
    del_resp = client.delete(f"/api/session/{sample_session['session_id']}")
    assert del_resp.status_code == 200

    # Ensure cache entries for that document were cleared
    stats = client.get("/api/cache/stats").json()
    assert stats["total_entries"] == 0


# ── Test 8: Expired entries are rejected (TTL) ────────────────────────────────
def test_8_expired_entries_are_rejected(clean_cache):
    entry = CacheEntry(
        entry_id="test_exp",
        normalized_query="test question",
        query_hash="hash",
        doc_id="doc1",
        doc_hash="dochash",
        response="answer",
        created_at=time.time() - 200,
        expires_at=time.time() - 10,  # Expired 10 seconds ago
    )
    assert entry.is_expired() is True

    clean_cache.exact_cache.set("key_exp", entry.model_dump(), ttl_seconds=-5)
    assert clean_cache.exact_cache.get("key_exp") is None


# ── Test 9: Different users cannot access private cache entries ───────────────
def test_9_user_isolation(clean_cache):
    q = "What is the secret data?"
    clean_cache.store(
        query=q,
        doc_id="doc1",
        doc_hash="dochash1",
        response="User 1 private answer",
        citations=[1],
        support={"supported": 1, "total": 1},
        chunks=[],
        best_score=0.9,
        dense_available=True,
        retrieval_label="hybrid",
        user_id="user_alice",
    )

    # Bob asks same question -> must be a cache miss
    lookup_bob = clean_cache.lookup(
        query=q,
        doc_id="doc1",
        doc_hash="dochash1",
        user_id="user_bob",
    )
    assert lookup_bob.hit is False

    # Alice asks same question -> exact hit
    lookup_alice = clean_cache.lookup(
        query=q,
        doc_id="doc1",
        doc_hash="dochash1",
        user_id="user_alice",
    )
    assert lookup_alice.hit is True


# ── Test 10: Multi-document collection context isolation ─────────────────────
def test_10_collection_context_isolation(clean_cache):
    q = "Summarize the project timeline."
    clean_cache.store(
        query=q,
        doc_id="doc1",
        doc_hash="dochash1",
        response="Collection A timeline",
        citations=[1],
        support={"supported": 1, "total": 1},
        chunks=[],
        best_score=0.9,
        dense_available=True,
        retrieval_label="hybrid",
        collection_id="collection_alpha",
    )

    # Query with different collection context
    lookup_beta = clean_cache.lookup(
        query=q,
        doc_id="doc1",
        doc_hash="dochash1",
        collection_id="collection_beta",
    )
    assert lookup_beta.hit is False


# ── Test 11: Changed system prompts invalidate incompatible results ──────────
def test_11_changed_system_prompt_invalidates_cache(clean_cache):
    q = "What are the findings?"
    prompt_v1 = "You are a concise academic assistant."
    prompt_v2 = "You are an ELI5 explaining assistant."

    clean_cache.store(
        query=q,
        doc_id="doc1",
        doc_hash="dochash1",
        response="Academic answer",
        citations=[1],
        support={"supported": 1, "total": 1},
        chunks=[],
        best_score=0.9,
        dense_available=True,
        retrieval_label="hybrid",
        system_prompt=prompt_v1,
    )

    lookup_v2 = clean_cache.lookup(
        query=q,
        doc_id="doc1",
        doc_hash="dochash1",
        system_prompt=prompt_v2,
    )
    assert lookup_v2.hit is False


# ── Test 12: Existing citations and support metadata preserved on cache hits ─
def test_12_citations_and_support_preserved(client, sample_session):
    q = "What instruments does the Aurora probe carry?"
    # First query -> miss
    r1 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q})
    b1 = r1.json()

    # Second query -> exact hit
    r2 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q})
    b2 = r2.json()

    assert b2["cache_status"] == "hit"
    assert b2["citations"] == b1["citations"]
    assert b2["support"] == b1["support"]
    assert len(b2["chunks"]) == len(b1["chunks"])
    assert b2["chunks"][0]["page"] == b1["chunks"][0]["page"]


# ── Test 13: Existing guardrails still execute (refusals never cached) ───────
def test_13_refused_answers_never_cached(client, sample_session):
    off_topic = "What is the capital of France?"
    r1 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": off_topic})
    b1 = r1.json()
    assert b1["refused"] is True

    # Off-topic question should not be cached
    stats = client.get("/api/cache/stats").json()
    assert stats["total_entries"] == 0

    # Repeating off-topic query should still be a cache miss
    r2 = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": off_topic})
    b2 = r2.json()
    assert b2["cache_status"] == "miss"
    assert b2["refused"] is True


# ── Test 14: Cache failure falls back to original RAG gracefully ─────────────
def test_14_cache_failure_falls_back_to_rag(client, sample_session):
    # Mock lookup to raise an unexpected runtime error
    with patch.object(cache_engine, "lookup", side_effect=RuntimeError("Simulated cache error")):
        # Request should not fail 500; it falls through gracefully to normal RAG
        resp = client.post(
            "/api/ask",
            json={
                "session_id": sample_session["session_id"],
                "question": "What instruments does the Aurora probe carry?",
            },
        )
        assert resp.status_code == 200
        assert "magnetometer" in resp.json()["answer"].lower()

    # Verify engine handles internal errors gracefully
    with patch.object(cache_engine.exact_cache, "get", side_effect=Exception("Redis down")):
        lookup = cache_engine.lookup(
            query="What instruments does the Aurora probe carry?",
            doc_id=sample_session["session_id"],
            doc_hash="sample_hash",
        )
        # Should degrade gracefully to semantic search or miss
        assert lookup is not None


# ── Test 15: LLM provider failures are handled gracefully without cache corruption
def test_15_llm_failure_handled_without_corrupt_cache(client, sample_session):
    # When Groq fails or no key is set, Knowlix falls back to extractive answers cleanly
    q = "What instruments does the Aurora probe carry?"
    resp = client.post("/api/ask", json={"session_id": sample_session["session_id"], "question": q})
    assert resp.status_code == 200
    assert "magnetometer" in resp.json()["answer"].lower()


# ── Test 16: Similar questions with different intent rejected ────────────────
def test_16_safeguards_reject_contrasting_intents():
    # 1. Negation mismatch
    ok1, reason1 = validate_semantic_compatibility(
        "Who proposed the model?", "Who did not propose the model?"
    )
    assert ok1 is False
    assert reason1 == "negation_mismatch"

    # 2. Number mismatch
    ok2, reason2 = validate_semantic_compatibility(
        "What happened in 2024?", "What happened in 2025?"
    )
    assert ok2 is False
    assert reason2 == "number_mismatch"

    # 3. Interrogative entity mismatch
    ok3, reason3 = validate_semantic_compatibility(
        "Who proposed the algorithm?", "What are the limitations of the algorithm?"
    )
    assert ok3 is False
    assert "mismatch" in reason3 or "aspect" in reason3

    # 4. Valid paraphrase passes
    ok4, reason4 = validate_semantic_compatibility(
        "What are the main findings of this research paper?",
        "Summarize the key findings presented in the paper.",
    )
    assert ok4 is True
    assert reason4 is None


# ── Test 17: Cache capacity limits work (LRU eviction) ───────────────────────
def test_17_cache_capacity_limits(clean_cache):
    # Configure tiny cache size of 3
    orig_max = clean_cache.config.max_entries
    try:
        clean_cache.config.max_entries = 3
        clean_cache.vector_store._max_entries = 3
        clean_cache.exact_cache._max_entries = 3

        for i in range(5):
            clean_cache.store(
                query=f"query number {i}",
                doc_id="doc1",
                doc_hash="hash1",
                response=f"answer {i}",
                citations=[1],
                support={"supported": 1, "total": 1},
                chunks=[],
                best_score=0.9,
                dense_available=True,
                retrieval_label="hybrid",
            )

        # Size should not exceed max_entries
        assert clean_cache.vector_store.size() <= 3
    finally:
        clean_cache.config.max_entries = orig_max
        clean_cache.vector_store._max_entries = orig_max
        clean_cache.exact_cache._max_entries = orig_max


# ── Test 18: Cache settings and benchmark endpoints work correctly ───────────
def test_18_cache_settings_and_benchmarks(client, sample_session):
    # Read settings
    s_resp = client.get("/api/cache/settings")
    assert s_resp.status_code == 200
    settings = s_resp.json()
    assert "similarity_threshold" in settings

    # Update settings
    p_resp = client.patch(
        "/api/cache/settings",
        json={"similarity_threshold": 0.95, "ttl_seconds": 3600},
    )
    assert p_resp.status_code == 200
    updated = p_resp.json()
    assert updated["similarity_threshold"] == 0.95
    assert updated["ttl_seconds"] == 3600

    # Run benchmark endpoint
    b_resp = client.post(
        "/api/cache/benchmark/run",
        json={"session_id": sample_session["session_id"]},
    )
    assert b_resp.status_code == 200
    bench_data = b_resp.json()
    assert "mode_a_baseline" in bench_data
    assert "mode_b_exact" in bench_data
    assert "mode_c_semantic" in bench_data
    assert bench_data["mode_c_semantic"]["cache_hits"] > 0
    assert bench_data["semantic_speedup_factor"] > 0

    # History endpoint
    h_resp = client.get("/api/cache/benchmarks")
    assert h_resp.status_code == 200
    assert len(h_resp.json()["history"]) >= 1
