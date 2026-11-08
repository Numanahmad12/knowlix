"""Knowlix Document-Aware Semantic Caching Engine.

Provides exact-match and semantic caching with strict document isolation,
guardrail verification, intent safeguards, and detailed performance telemetry.
"""

from .models import CacheConfig, CacheEntry, CacheLookupResult, CacheStats
from .engine import SemanticCacheEngine

__all__ = [
    "CacheConfig",
    "CacheEntry",
    "CacheLookupResult",
    "CacheStats",
    "SemanticCacheEngine",
]
