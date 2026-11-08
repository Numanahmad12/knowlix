"""Domain models and schemas for the Knowlix Semantic Cache Engine."""

import os
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CacheEntry(BaseModel):
    """Document-aware cache entry containing complete context and audit metadata."""

    entry_id: str = Field(description="Unique identifier for this cache entry")
    normalized_query: str = Field(description="Preprocessed query text")
    query_hash: str = Field(description="Deterministic hash of the normalized query")
    query_embedding: Optional[List[float]] = Field(
        default=None, description="Dense vector embedding (384-d float list)"
    )

    # Document & Context Scope
    doc_id: str = Field(description="Identifier of the document (session_id or document ID)")
    doc_hash: str = Field(description="Content hash (e.g. SHA-256) of the document")
    doc_name: Optional[str] = Field(default=None, description="Human-readable document name")
    collection_id: Optional[str] = Field(
        default=None, description="Optional multi-document collection identifier"
    )
    user_id: Optional[str] = Field(
        default="anonymous", description="User identity or access scope"
    )
    tenant_id: Optional[str] = Field(
        default="default", description="Tenant isolation boundary"
    )

    # Answer Payload & Traceability
    response: str = Field(description="Cached generated answer text")
    page_references: List[int] = Field(
        default_factory=list, description="Source page references (e.g. [1, 3])"
    )
    chunk_ids: List[str] = Field(
        default_factory=list, description="Source chunk identifiers or hashes"
    )
    citation_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured verification payload (support ratio, citations, chunks preview)",
    )

    # Model & Retrieval Environment
    llm_provider: str = Field(default="groq", description="LLM provider (e.g. groq, gemini, extractive)")
    llm_model: str = Field(default="openai/gpt-oss-120b", description="Model identifier")
    system_prompt_hash: str = Field(
        default="", description="SHA-256 hash of system prompt governing answer"
    )
    retrieval_config_version: str = Field(
        default="v1.0", description="Version of chunking/retrieval configuration"
    )

    # Lifecycle & Telemetry
    created_at: float = Field(default_factory=time.time, description="Creation epoch timestamp")
    expires_at: float = Field(description="Expiration epoch timestamp")
    hit_count: int = Field(default=0, description="Total cache hit count for this entry")
    last_accessed_at: float = Field(
        default_factory=time.time, description="Last access epoch timestamp"
    )

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return now >= self.expires_at

    def register_hit(self) -> None:
        self.hit_count += 1
        self.last_accessed_at = time.time()


class CacheConfig(BaseModel):
    """Runtime configuration for the Knowlix Semantic Cache Engine."""

    enabled: bool = Field(default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() in ("true", "1", "yes"))
    similarity_threshold: float = Field(
        default_factory=lambda: float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.75")),
        ge=0.50,
        le=1.00,
        description="Minimum cosine similarity for semantic hit",
    )
    ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("CACHE_TTL_SECONDS", "86400")),
        ge=60,
        description="Cache Time-To-Live in seconds (default 24 hours)",
    )
    max_entries: int = Field(
        default_factory=lambda: int(os.getenv("CACHE_MAX_ENTRIES", "1000")),
        ge=1,
        description="Maximum total entries allowed in cache",
    )
    exact_cache_enabled: bool = True
    semantic_cache_enabled: bool = True
    top_k_candidates: int = Field(
        default=5, ge=1, le=20, description="Number of nearest semantic candidates to evaluate"
    )
    redis_url: Optional[str] = Field(default_factory=lambda: os.getenv("REDIS_URL") or None)


class CacheLookupResult(BaseModel):
    """Structured result returned by cache evaluation."""

    hit: bool
    cache_type: str = Field(
        description="'exact' | 'semantic' | 'miss' | 'disabled'"
    )
    entry: Optional[CacheEntry] = None
    similarity_score: float = 0.0
    cache_lookup_ms: float = 0.0
    embedding_ms: float = 0.0
    reason: Optional[str] = None


class CacheStats(BaseModel):
    """Aggregate performance and operational statistics."""

    total_queries: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    cache_misses: int = 0
    hit_rate: float = 0.0
    total_entries: int = 0
    estimated_tokens_saved: int = 0
    estimated_cost_saved_usd: float = 0.0
    avg_lookup_latency_ms: float = 0.0
    llm_calls_avoided: int = 0
