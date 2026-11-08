# SEMANTIC CACHE INTEGRATION PLAN: KNOWLIX

## 1. Executive Summary & Architectural Goals
Knowlix is a high-precision, production-oriented PDF question-answering system combining page-aware chunking, ONNX Runtime embeddings (`all-MiniLM-L6-v2`), FAISS hybrid retrieval with Reciprocal Rank Fusion (RRF), deterministic groundedness verification, claim checking, and Groq LLM generation (`openai/gpt-oss-120b`) with extractive fallback.

The **Knowlix Semantic Cache Engine** augments the Q&A pipeline to intercept redundant LLM calls and retrieval overhead for semantically equivalent queries on identical document contexts, while strictly preserving:
1. **Document Isolation & Context Integrity**: Queries are tied to document content hash, session/collection context, and prompt configuration. Cross-document leakage is strictly prevented.
2. **Deterministic Guardrails & Safety**: Groundedness gating, sentence-level claim checking, citation validation, and injection sanitization are never bypassed. Refused, ungrounded, or sensitive answers are never cached.
3. **Semantic Semantic Drift Safeguards**: Strict semantic similarity (configurable threshold default 0.90) augmented with intent-level heuristic filters (negations, numbers/dates, distinct named entities, query structural polarity) to avoid false-positive semantic collisions.
4. **Zero-Torch Lightweight Footprint**: Reuses the bundled ONNX Runtime `all-MiniLM-L6-v2` embedder (384-dimensional normalized vectors) and a dedicated isolated FAISS `IndexFlatIP` index for semantic vectors, keeping the Render free-tier (512 MB) memory profile safe.
5. **Tiered Storage Architecture**: Fast exact lookup (Redis when configured, with thread-safe bounded memory fallback) paired with dedicated vector semantic lookup and structured metadata storage.

---

## 2. Technical Stack & Invariants
- **Backend**: Python 3.11/3.12, FastAPI, ONNX Runtime 1.31+, FAISS-CPU 1.9+, Pydantic v2.
- **Frontend**: Next.js 14, React 18, CSS modules/vanilla variables matching Knowlix dark-slate/cyan design system.
- **Embedder**: `all-MiniLM-L6-v2` via `_OnnxEmbedder` in `core.py` (384-dim, normalized).
- **Default LLM**: Groq API (`openai/gpt-oss-120b`) with robust fallback to extractive summarizer. Optional pluggable provider abstraction for Gemini or mock LLM.

---

## 3. Phased Implementation Roadmap

### Phase 1: Repository Inspection & Architectural Plan
- Inspect existing codebase (`main.py`, `core.py`, `llm.py`, `test_api.py`, `test_core.py`, Next.js app).
- Author `SEMANTIC_CACHE_INTEGRATION_PLAN.md` and `DEVELOPMENT_STATUS.md`.

### Phase 2: Cache Domain Interfaces, Configuration & Exact Cache
- Design `CacheEntry`, `CacheConfig`, `CacheStats`, `CacheLookupResult` data models in `app/cache/models.py`.
- Implement `ExactCache` with Redis client support and bounded LRU/TTL in-memory fallback in `app/cache/exact.py`.
- Unit tests for exact caching, TTL expiry, and capacity bounds.

### Phase 3: Dedicated FAISS Semantic Vector Index & ONNX Integration
- Implement `SemanticVectorStore` in `app/cache/vector_store.py`:
  - Separate FAISS `IndexFlatIP(384)` dedicated exclusively to cached queries.
  - Metadata indexing mapped to vector IDs.
  - Thread-safe add, search, remove, clear, and optional persistence.
- Re-use `_get_embedding_model` and `_embed_texts` without installing PyTorch or SentenceTransformers.

### Phase 4: Intent Safeguards & Semantic Cache Engine
- Implement `app/cache/engine.py` orchestrating:
  - Context-aware cache key computation (`doc_id`, `content_hash`, `prompt_hash`, `user_id`, `normalized_query`).
  - Dual-tier lookup: Exact -> Semantic.
  - Safeguard filters:
    - Negation detector (`not`, `never`, `no`, `without`, `except`, etc.).
    - Entity & number alignment checks (different years, figures, or key proper nouns reject semantic match even if cosine >= 0.90).
    - Top-k candidate evaluation with configurable cosine threshold (default 0.90).
  - Cache insertion policy: only successful, non-refused, grounded responses with valid citations are stored.

### Phase 5: Pipeline Integration & Document-Aware Invalidation
- Integrate into `app/main.py` (`/api/ask`, `/api/upload`, `/api/sample`, `/api/session/{id}`).
- Compute content hash of uploaded/sampled PDFs (`sha256(raw_bytes)`).
- Attach document hash and metadata to sessions.
- Invalidation triggers:
  - Deleting session invalidates associated session cache entries.
  - Re-uploading or updating document invalidates old version cache entries.
  - System prompt modification invalidates incompatible prompt hashes.
  - Explicit document or global clear triggers.

### Phase 6: Guardrail Verification & Resilience
- Verify that cache hits return authentic citations and support metrics.
- Ensure refused answers (`REFUSAL_TEXT`) and injection attempts are never cached.
- Fallback resilience: If semantic cache lookup throws an unexpected error, log and gracefully proceed to normal RAG pipeline without failing the user request.

### Phase 7: Analytics, Performance Metrics & Benchmarking Service
- Implement `CacheMetricsTracker` tracking:
  - Total queries, exact hits, semantic hits, misses, hit rate.
  - Latency metrics: cache lookup ms, embedding ms, retrieval ms, generation ms, total ms.
  - Token savings estimate (~1.3 tokens per word) and estimated API cost saved.
- Implement benchmarking engine (`app/cache/benchmark.py`) comparing:
  - Mode A: No caching (baseline)
  - Mode B: Exact-only caching
  - Mode C: Full semantic caching
- API Endpoints:
  - `GET /api/cache/stats`
  - `GET /api/cache/entries`
  - `GET /api/cache/entries/{id}`
  - `DELETE /api/cache/entries/{id}`
  - `POST /api/cache/clear`
  - `GET /api/cache/settings`
  - `PATCH /api/cache/settings`
  - `POST /api/cache/benchmark/run`
  - `GET /api/cache/benchmark/results`

### Phase 8: Frontend Integration (Knowlix Design System)
- Update `lib/api.js` with new cache endpoints and response fields.
- Chat UI enhancements:
  - Cache badges on answers (`EXACT CACHE HIT`, `SEMANTIC CACHE HIT`, `CACHE MISS`, `CACHE DISABLED`).
  - Expandable Performance & Cache Inspection panel per answer (latencies, similarity score, tokens saved, retrieved chunk verification).
- New "Semantic Cache" dashboard tab/view in `app/page.js`:
  - Metric summary cards: Total queries, Hit rate, Latency saved, Tokens saved, Cost saved.
  - Interactive visual charts: Hits vs Misses breakdown, Latency distribution, Request volume over time.
  - Searchable Cache Explorer table: Query, Document, Type, Similarity, Created, Expire, Hits, Actions (delete entry).
  - Cache Configuration panel: Enable/disable toggle, threshold slider (0.70-0.99), TTL input, Max entries, Invalidate Document, Clear All.

### Phase 9: Deployment Configuration & Production Hardening
- Update `backend/README.md`, `DEPLOY.md`, `requirements.txt`, `.env.example`.
- Verify Docker configuration and Render 512 MB memory constraints.
- Document Redis URL setup vs bounded in-memory fallback.

### Phase 10: Comprehensive Test Suite & Validation
- Run existing 34 tests to guarantee zero regressions.
- Add comprehensive test suite in `tests/test_semantic_cache.py` covering all 18 specified scenarios:
  1. First query -> cache miss.
  2. Repeated identical query -> exact hit.
  3. Rephrased semantic query -> semantic hit.
  4. Unrelated query -> miss.
  5. Different PDFs never share cache answers (document isolation).
  6. Replacing/updating PDF invalidates previous entries.
  7. Deleting session/PDF invalidates entries.
  8. TTL expiration rejects expired entries.
  9. User/tenant isolation.
  10. Multi-PDF/collection context isolation.
  11. System prompt alteration invalidates entries.
  12. Citations and support metadata preserved intact on hits.
  13. Guardrails (groundedness, claim check, injection) still active.
  14. Cache failure gracefully degrades to standard RAG pipeline.
  15. LLM failure handled gracefully.
  16. High semantic similarity with different intent (negation, numbers, entities) rejected.
  17. Cache capacity LRU eviction works.
  18. Runtime settings update works dynamically.
