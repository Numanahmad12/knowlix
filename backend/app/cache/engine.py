"""Core orchestrator for the Knowlix Document-Aware Semantic Caching Engine."""

import hashlib
import logging
import re
import string
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .exact import ExactCacheManager
from .metrics import CacheMetricsTracker
from .models import CacheConfig, CacheEntry, CacheLookupResult, CacheStats
from .safeguards import validate_semantic_compatibility
from .vector_store import SemanticVectorStore

logger = logging.getLogger(__name__)

_RE_PUNCTUATION = re.compile(f"[{re.escape(string.punctuation)}]")
_RE_SPACES = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    """Normalize query text: lowercase, strip punctuation and redundant whitespace."""
    if not query:
        return ""
    q = query.strip().lower()
    q = _RE_PUNCTUATION.sub(" ", q)
    return _RE_SPACES.sub(" ", q).strip()


def hash_text(text: str) -> str:
    """Deterministic SHA-256 hash of text."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count (~1.33 tokens per word)."""
    if not text:
        return 0
    words = len(text.split())
    return max(1, int(words * 1.33))


class SemanticCacheEngine:
    """Document-aware semantic caching engine combining exact and vector search."""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.exact_cache = ExactCacheManager(
            redis_url=self.config.redis_url, max_entries=self.config.max_entries
        )
        self.vector_store = SemanticVectorStore(
            dimension=384, max_entries=self.config.max_entries
        )
        self.metrics = CacheMetricsTracker()

    def _get_exact_key(
        self,
        doc_hash: str,
        tenant_id: str,
        user_id: str,
        prompt_hash: str,
        query_hash: str,
        collection_id: Optional[str] = None,
    ) -> str:
        coll = collection_id or "none"
        return f"knowlix:cache:{doc_hash}:{coll}:{tenant_id}:{user_id}:{prompt_hash}:{query_hash}"

    def _embed_query(self, query: str) -> Optional[np.ndarray]:
        """Generate embedding using core's ONNX embedder without torch."""
        try:
            from .. import core
            vecs = core._embed_texts([query])
            if vecs is not None and len(vecs) > 0:
                return vecs[0]
        except Exception as exc:
            logger.warning("Cache query embedding failed: %s", exc)
        return None

    def lookup(
        self,
        query: str,
        doc_id: str,
        doc_hash: str,
        doc_name: str = "",
        system_prompt: str = "",
        user_id: str = "anonymous",
        tenant_id: str = "default",
        collection_id: Optional[str] = None,
    ) -> CacheLookupResult:
        """Execute context-aware dual-tier cache lookup (Exact -> Semantic)."""
        start_time = time.perf_counter()

        if not self.config.enabled:
            return CacheLookupResult(
                hit=False,
                cache_type="disabled",
                reason="Cache engine disabled in configuration",
            )

        norm_query = normalize_query(query)
        if not norm_query:
            return CacheLookupResult(
                hit=False,
                cache_type="miss",
                reason="Empty query",
            )

        q_hash = hash_text(norm_query)
        prompt_hash = hash_text(system_prompt)

        # ── 1. Check Exact Match ──────────────────────────────────────────────
        if self.config.exact_cache_enabled:
            exact_key = self._get_exact_key(
                doc_hash, tenant_id, user_id, prompt_hash, q_hash, collection_id=collection_id
            )
            raw_entry = None
            try:
                raw_entry = self.exact_cache.get(exact_key)
            except Exception as exc:
                logger.warning("Exact cache get failed: %s", exc)

            if raw_entry:
                try:
                    entry = CacheEntry(**raw_entry)
                    if not entry.is_expired():
                        # Strict security and context validations
                        if (
                            entry.doc_hash == doc_hash
                            and entry.user_id == user_id
                            and entry.tenant_id == tenant_id
                            and entry.system_prompt_hash == prompt_hash
                            and entry.collection_id == collection_id
                        ):
                            entry.register_hit()
                            # Persist updated hit count in exact cache
                            self.exact_cache.set(
                                exact_key,
                                entry.model_dump(),
                                int(max(60, entry.expires_at - time.time())),
                            )

                            lookup_ms = (time.perf_counter() - start_time) * 1000.0
                            saved_tokens = estimate_tokens(entry.response) + estimate_tokens(query)
                            self.metrics.record_query(
                                cache_type="exact",
                                lookup_ms=lookup_ms,
                                tokens_saved=saved_tokens,
                                query=query,
                                doc_name=doc_name or entry.doc_name or "",
                                similarity_score=1.0,
                            )
                            return CacheLookupResult(
                                hit=True,
                                cache_type="exact",
                                entry=entry,
                                similarity_score=1.0,
                                cache_lookup_ms=round(lookup_ms, 2),
                                embedding_ms=0.0,
                            )
                except Exception as exc:
                    logger.warning("Failed to parse exact cache entry: %s", exc)

        # ── 2. Check Semantic Vector Match ────────────────────────────────────
        emb_start = time.perf_counter()
        query_vec = None
        embedding_ms = 0.0

        if self.config.semantic_cache_enabled:
            query_vec = self._embed_query(query)
            embedding_ms = (time.perf_counter() - emb_start) * 1000.0

            if query_vec is not None:
                candidates = []
                try:
                    candidates = self.vector_store.search(
                        query_vec, top_k=self.config.top_k_candidates
                    )
                except Exception as exc:
                    logger.warning("Vector store search failed: %s", exc)

                for candidate, similarity in candidates:
                    # Verify similarity threshold
                    if similarity < self.config.similarity_threshold:
                        continue

                    # Context & Tenant isolation validation
                    if candidate.doc_hash != doc_hash:
                        continue
                    if candidate.user_id != user_id or candidate.tenant_id != tenant_id:
                        continue
                    if candidate.system_prompt_hash != prompt_hash:
                        continue
                    if collection_id and candidate.collection_id != collection_id:
                        continue

                    # Intent safeguards validation (negation, numbers, entities, aspects)
                    compatible, refusal_reason = validate_semantic_compatibility(
                        query, candidate.normalized_query
                    )
                    if not compatible:
                        logger.info(
                            "Semantic candidate rejected despite score %.3f: %s (query: '%s' vs '%s')",
                            similarity,
                            refusal_reason,
                            query,
                            candidate.normalized_query,
                        )
                        continue

                    # Safe semantic hit confirmed!
                    candidate.register_hit()
                    lookup_ms = (time.perf_counter() - start_time) * 1000.0
                    saved_tokens = estimate_tokens(candidate.response) + estimate_tokens(query)

                    # Store in exact cache under this variant query for instant next lookup
                    exact_key = self._get_exact_key(
                        doc_hash, tenant_id, user_id, prompt_hash, q_hash, collection_id=collection_id
                    )
                    self.exact_cache.set(
                        exact_key,
                        candidate.model_dump(),
                        int(max(60, candidate.expires_at - time.time())),
                    )
                    if query_vec is not None:
                        try:
                            self.vector_store.add_entry(candidate, query_vec)
                        except Exception:
                            pass

                    self.metrics.record_query(
                        cache_type="semantic",
                        lookup_ms=lookup_ms,
                        tokens_saved=saved_tokens,
                        query=query,
                        doc_name=doc_name or candidate.doc_name or "",
                        similarity_score=similarity,
                    )

                    return CacheLookupResult(
                        hit=True,
                        cache_type="semantic",
                        entry=candidate,
                        similarity_score=round(float(similarity), 4),
                        cache_lookup_ms=round(lookup_ms, 2),
                        embedding_ms=round(embedding_ms, 2),
                    )

        # ── 3. Cache Miss ─────────────────────────────────────────────────────
        lookup_ms = (time.perf_counter() - start_time) * 1000.0
        self.metrics.record_query(
            cache_type="miss",
            lookup_ms=lookup_ms,
            tokens_saved=0,
            query=query,
            doc_name=doc_name,
            similarity_score=0.0,
        )

        return CacheLookupResult(
            hit=False,
            cache_type="miss",
            similarity_score=0.0,
            cache_lookup_ms=round(lookup_ms, 2),
            embedding_ms=round(embedding_ms, 2),
            reason="No equivalent cached entry meeting similarity and context constraints",
        )

    def store(
        self,
        query: str,
        doc_id: str,
        doc_hash: str,
        response: str,
        citations: List[int],
        support: Optional[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
        best_score: float,
        dense_available: bool,
        retrieval_label: str,
        doc_name: str = "",
        system_prompt: str = "",
        user_id: str = "anonymous",
        tenant_id: str = "default",
        collection_id: Optional[str] = None,
        llm_provider: str = "groq",
        llm_model: str = "openai/gpt-oss-120b",
        refused: bool = False,
        query_embedding: Optional[np.ndarray] = None,
    ) -> Optional[CacheEntry]:
        """Store a verified answer and metadata in the cache."""
        if not self.config.enabled:
            return None

        # Guardrail checks: NEVER cache refused, ungrounded, or empty answers
        if refused:
            return None
        if not response or not response.strip():
            return None
        from .. import core
        if core.REFUSAL_TEXT in response:
            return None
        if support and support.get("total", 0) > 0 and support.get("supported", 0) == 0:
            return None

        norm_query = normalize_query(query)
        if not norm_query:
            return None

        q_hash = hash_text(norm_query)
        prompt_hash = hash_text(system_prompt)
        entry_id = str(uuid.uuid4())
        now = time.time()
        expires_at = now + self.config.ttl_seconds

        # Build citation metadata snapshot
        citation_meta = {
            "citations": citations or [],
            "support": support,
            "best_score": best_score,
            "dense_available": dense_available,
            "retrieval_label": retrieval_label,
            "chunks": chunks[:3] if chunks else [],
        }

        # Query embedding
        if query_embedding is None:
            query_embedding = self._embed_query(query)

        entry = CacheEntry(
            entry_id=entry_id,
            normalized_query=norm_query,
            query_hash=q_hash,
            query_embedding=query_embedding.tolist() if query_embedding is not None else None,
            doc_id=doc_id,
            doc_hash=doc_hash,
            doc_name=doc_name,
            collection_id=collection_id,
            user_id=user_id,
            tenant_id=tenant_id,
            response=response,
            page_references=citations or [],
            chunk_ids=[str(c.get("page", 0)) for c in (chunks or [])[:3]],
            citation_metadata=citation_meta,
            llm_provider=llm_provider,
            llm_model=llm_model,
            system_prompt_hash=prompt_hash,
            retrieval_config_version="v1.0",
            created_at=now,
            expires_at=expires_at,
            hit_count=0,
            last_accessed_at=now,
        )

        # Store in Exact Cache
        exact_key = self._get_exact_key(
            doc_hash, tenant_id, user_id, prompt_hash, q_hash, collection_id=collection_id
        )
        self.exact_cache.set(exact_key, entry.model_dump(), self.config.ttl_seconds)

        # Store in Vector Store
        if self.config.semantic_cache_enabled and query_embedding is not None:
            self.vector_store.add_entry(entry, query_embedding)

        return entry

    def invalidate_document(self, doc_id: str, doc_hash: Optional[str] = None) -> int:
        """Invalidate all cache entries associated with a document ID or content hash."""
        count = 0
        if doc_hash:
            exact_prefix = f"knowlix:cache:{doc_hash}:"
            count += self.exact_cache.delete_by_prefix(exact_prefix)
            count += self.vector_store.remove_by_doc_hash(doc_hash)
        else:
            count += self.vector_store.remove_by_doc_id(doc_id)
        return count

    def invalidate_entry(self, entry_id: str) -> bool:
        """Invalidate a specific cache entry by its entry_id."""
        entry = self.vector_store.get_by_id(entry_id)
        if entry:
            prompt_hash = entry.system_prompt_hash
            exact_key = self._get_exact_key(
                entry.doc_hash,
                entry.tenant_id or "default",
                entry.user_id or "anonymous",
                prompt_hash,
                entry.query_hash,
                collection_id=entry.collection_id,
            )
            self.exact_cache.delete(exact_key)
        return self.vector_store.remove_entry(entry_id)

    def clear_all(self) -> None:
        """Clear both exact and vector cache stores and reset telemetry."""
        self.exact_cache.clear()
        self.vector_store.clear()
        self.metrics.reset()

    def get_entry(self, entry_id: str) -> Optional[CacheEntry]:
        """Fetch a specific cache entry by entry_id."""
        return self.vector_store.get_by_id(entry_id)

    def list_entries(
        self, query_filter: Optional[str] = None, limit: int = 100
    ) -> List[CacheEntry]:
        """List active cache entries, optionally filtered by search text."""
        entries = self.vector_store.get_all_entries()
        if query_filter:
            q_clean = query_filter.lower().strip()
            entries = [
                e
                for e in entries
                if q_clean in e.normalized_query.lower()
                or (e.doc_name and q_clean in e.doc_name.lower())
            ]
        # Return newest first
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    def get_stats(self) -> CacheStats:
        """Return aggregate performance and financial savings metrics."""
        return self.metrics.get_stats(total_entries=self.vector_store.size())

    def get_settings(self) -> CacheConfig:
        return self.config

    def update_settings(self, updates: Dict[str, Any]) -> CacheConfig:
        """Update runtime caching settings dynamically."""
        current_dict = self.config.model_dump()
        for k, v in updates.items():
            if k in current_dict and v is not None:
                current_dict[k] = v
        self.config = CacheConfig(**current_dict)
        return self.config
