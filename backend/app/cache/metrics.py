"""Telemetry, performance metrics, and cost estimation for the Knowlix Semantic Cache."""

import threading
import time
from typing import Dict, List, Optional
from .models import CacheStats

# Cost estimation constants (Groq / standard LLM pricing reference)
# Approx $0.59 per 1M prompt tokens, $0.79 per 1M completion tokens -> ~$0.70/1M blended
ESTIMATED_COST_PER_TOKEN = 0.0000007


class CacheMetricsTracker:
    """Thread-safe real-time telemetry tracker."""

    def __init__(self):
        self._lock = threading.RLock()
        self._total_queries = 0
        self._exact_hits = 0
        self._semantic_hits = 0
        self._cache_misses = 0
        self._tokens_saved = 0
        self._lookup_latencies_ms: List[float] = []
        self._recent_events: List[Dict] = []
        self._max_recent_events = 200

    def record_query(
        self,
        cache_type: str,
        lookup_ms: float,
        tokens_saved: int = 0,
        query: str = "",
        doc_name: str = "",
        similarity_score: float = 0.0,
    ) -> None:
        with self._lock:
            self._total_queries += 1
            if cache_type == "exact":
                self._exact_hits += 1
                self._tokens_saved += tokens_saved
            elif cache_type == "semantic":
                self._semantic_hits += 1
                self._tokens_saved += tokens_saved
            else:
                self._cache_misses += 1

            self._lookup_latencies_ms.append(lookup_ms)
            if len(self._lookup_latencies_ms) > 1000:
                self._lookup_latencies_ms = self._lookup_latencies_ms[-1000:]

            event = {
                "timestamp": time.time(),
                "query": query,
                "doc_name": doc_name,
                "cache_type": cache_type,
                "lookup_ms": round(lookup_ms, 2),
                "similarity_score": round(similarity_score, 4),
                "tokens_saved": tokens_saved,
            }
            self._recent_events.append(event)
            if len(self._recent_events) > self._max_recent_events:
                self._recent_events.pop(0)

    def get_stats(self, total_entries: int = 0) -> CacheStats:
        with self._lock:
            total = self._total_queries
            hits = self._exact_hits + self._semantic_hits
            hit_rate = round(hits / total, 4) if total > 0 else 0.0
            avg_latency = (
                round(sum(self._lookup_latencies_ms) / len(self._lookup_latencies_ms), 2)
                if self._lookup_latencies_ms
                else 0.0
            )
            cost_saved = round(self._tokens_saved * ESTIMATED_COST_PER_TOKEN, 5)

            return CacheStats(
                total_queries=total,
                exact_hits=self._exact_hits,
                semantic_hits=self._semantic_hits,
                cache_misses=self._cache_misses,
                hit_rate=hit_rate,
                total_entries=total_entries,
                estimated_tokens_saved=self._tokens_saved,
                estimated_cost_saved_usd=cost_saved,
                avg_lookup_latency_ms=avg_latency,
                llm_calls_avoided=hits,
            )

    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            return list(reversed(self._recent_events[-limit:]))

    def reset(self) -> None:
        with self._lock:
            self._total_queries = 0
            self._exact_hits = 0
            self._semantic_hits = 0
            self._cache_misses = 0
            self._tokens_saved = 0
            self._lookup_latencies_ms.clear()
            self._recent_events.clear()
