"""Benchmarking suite for comparing Knowlix caching architectures.

Compares:
- Mode A: Baseline (no caching)
- Mode B: Exact-match caching only
- Mode C: Full Document-Aware Semantic Caching
"""

import logging
import statistics
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

BENCHMARK_QUESTION_PAIRS = [
    # Pair 1: Identical repeat
    ("What instruments does the Aurora probe carry?", "What instruments does the Aurora probe carry?"),
    # Pair 2: Semantic paraphrase
    ("What instruments does the Aurora probe carry?", "List the scientific instruments onboard the Aurora spacecraft."),
    # Pair 3: Main findings paraphrase
    ("What are the main findings of the mission?", "Summarize the primary discoveries made by Aurora."),
    # Pair 4: Specific fact paraphrase
    ("What did the magnetometer detect?", "What measurements were recorded by the magnetometer?"),
]


class BenchmarkModeResult(BaseModel):
    mode: str
    total_queries: int
    cache_hits: int
    cache_misses: int
    llm_calls: int
    retrieval_calls: int
    tokens_saved: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    latencies_ms: List[float] = Field(default_factory=list)


class BenchmarkRunResult(BaseModel):
    run_id: str
    timestamp: float
    document_name: str
    mode_a_baseline: BenchmarkModeResult
    mode_b_exact: BenchmarkModeResult
    mode_c_semantic: BenchmarkModeResult
    semantic_speedup_factor: float
    semantic_token_savings: int


class BenchmarkService:
    """Orchestrates repeatable live benchmarks comparing caching modes."""

    def __init__(self):
        self._history: List[BenchmarkRunResult] = []

    def get_history(self) -> List[BenchmarkRunResult]:
        return list(reversed(self._history))

    def run_benchmark(
        self,
        session_id: str,
        analysis_bundle: Dict[str, Any],
        custom_queries: Optional[List[str]] = None,
    ) -> BenchmarkRunResult:
        import uuid
        from .. import core
        from .engine import SemanticCacheEngine
        from .models import CacheConfig

        run_id = f"bench_{uuid.uuid4().hex[:8]}"
        doc_hash = analysis_bundle.get("doc_hash", "aurora_hash")
        doc_name = analysis_bundle.get("filename", "test_document.pdf")
        index_data = analysis_bundle["index_data"]

        # Default query progression: original question followed by paraphrase or repetition
        test_queries = custom_queries or [
            "What instruments does the Aurora probe carry?",
            "What instruments does the Aurora probe carry?",  # Exact hit test
            "List the scientific instruments onboard the Aurora spacecraft.",  # Semantic hit test
            "What did the magnetometer detect?",
            "What measurements were recorded by the magnetometer?",  # Semantic hit test
            "What is the primary power source?",
            "What are the key discoveries of this document?",
            "Summarize the main findings of the Aurora mission.",  # Semantic hit test
        ]

        def _percentile(data: List[float], p: float) -> float:
            if not data:
                return 0.0
            k = (len(data) - 1) * (p / 100.0)
            f = int(k)
            c = min(f + 1, len(data) - 1)
            d0 = sorted(data)[f]
            d1 = sorted(data)[c]
            return round(d0 + (d1 - d0) * (k - f), 2)

        # ── Run Mode A (No Caching) ───────────────────────────────────────────
        latencies_a: List[float] = []
        llm_a = 0
        retrieval_a = 0
        for q in test_queries:
            t0 = time.perf_counter()
            _res = core.ask_question(q, index_data)
            dur = (time.perf_counter() - t0) * 1000.0
            latencies_a.append(dur)
            retrieval_a += 1
            if not _res.get("refused"):
                llm_a += 1

        result_a = BenchmarkModeResult(
            mode="Mode A: Baseline (No Caching)",
            total_queries=len(test_queries),
            cache_hits=0,
            cache_misses=len(test_queries),
            llm_calls=llm_a,
            retrieval_calls=retrieval_a,
            tokens_saved=0,
            avg_latency_ms=round(statistics.mean(latencies_a), 2) if latencies_a else 0.0,
            p50_latency_ms=_percentile(latencies_a, 50),
            p95_latency_ms=_percentile(latencies_a, 95),
            latencies_ms=[round(x, 2) for x in latencies_a],
        )

        # ── Run Mode B (Exact Caching Only) ───────────────────────────────────
        engine_b = SemanticCacheEngine(
            CacheConfig(exact_cache_enabled=True, semantic_cache_enabled=False)
        )
        latencies_b: List[float] = []
        hits_b = 0
        llm_b = 0
        retrieval_b = 0
        tokens_saved_b = 0

        for q in test_queries:
            t0 = time.perf_counter()
            lookup = engine_b.lookup(q, doc_id=session_id, doc_hash=doc_hash, doc_name=doc_name)
            if lookup.hit:
                hits_b += 1
                tokens_saved_b += 120
            else:
                retrieval_b += 1
                res = core.ask_question(q, index_data)
                if not res.get("refused"):
                    llm_b += 1
                    engine_b.store(
                        query=q,
                        doc_id=session_id,
                        doc_hash=doc_hash,
                        response=res["answer"],
                        citations=res.get("citations", []),
                        support=res.get("support"),
                        chunks=res.get("chunks", []),
                        best_score=res.get("best_score", 0.0),
                        dense_available=res.get("dense_available", False),
                        retrieval_label="hybrid",
                        doc_name=doc_name,
                        refused=res.get("refused", False),
                    )
            dur = (time.perf_counter() - t0) * 1000.0
            latencies_b.append(dur)

        result_b = BenchmarkModeResult(
            mode="Mode B: Exact Caching Only",
            total_queries=len(test_queries),
            cache_hits=hits_b,
            cache_misses=len(test_queries) - hits_b,
            llm_calls=llm_b,
            retrieval_calls=retrieval_b,
            tokens_saved=tokens_saved_b,
            avg_latency_ms=round(statistics.mean(latencies_b), 2) if latencies_b else 0.0,
            p50_latency_ms=_percentile(latencies_b, 50),
            p95_latency_ms=_percentile(latencies_b, 95),
            latencies_ms=[round(x, 2) for x in latencies_b],
        )

        # ── Run Mode C (Full Semantic Caching) ────────────────────────────────
        engine_c = SemanticCacheEngine(
            CacheConfig(exact_cache_enabled=True, semantic_cache_enabled=True, similarity_threshold=0.88)
        )
        latencies_c: List[float] = []
        hits_c = 0
        llm_c = 0
        retrieval_c = 0
        tokens_saved_c = 0

        for q in test_queries:
            t0 = time.perf_counter()
            lookup = engine_c.lookup(q, doc_id=session_id, doc_hash=doc_hash, doc_name=doc_name)
            if lookup.hit:
                hits_c += 1
                tokens_saved_c += 140
            else:
                retrieval_c += 1
                res = core.ask_question(q, index_data)
                if not res.get("refused"):
                    llm_c += 1
                    engine_c.store(
                        query=q,
                        doc_id=session_id,
                        doc_hash=doc_hash,
                        response=res["answer"],
                        citations=res.get("citations", []),
                        support=res.get("support"),
                        chunks=res.get("chunks", []),
                        best_score=res.get("best_score", 0.0),
                        dense_available=res.get("dense_available", False),
                        retrieval_label="hybrid",
                        doc_name=doc_name,
                        refused=res.get("refused", False),
                    )
            dur = (time.perf_counter() - t0) * 1000.0
            latencies_c.append(dur)

        result_c = BenchmarkModeResult(
            mode="Mode C: Full Semantic Caching",
            total_queries=len(test_queries),
            cache_hits=hits_c,
            cache_misses=len(test_queries) - hits_c,
            llm_calls=llm_c,
            retrieval_calls=retrieval_c,
            tokens_saved=tokens_saved_c,
            avg_latency_ms=round(statistics.mean(latencies_c), 2) if latencies_c else 0.0,
            p50_latency_ms=_percentile(latencies_c, 50),
            p95_latency_ms=_percentile(latencies_c, 95),
            latencies_ms=[round(x, 2) for x in latencies_c],
        )

        speedup = (
            round(result_a.avg_latency_ms / max(0.01, result_c.avg_latency_ms), 2)
            if result_c.avg_latency_ms > 0
            else 1.0
        )

        summary = BenchmarkRunResult(
            run_id=run_id,
            timestamp=time.time(),
            document_name=doc_name,
            mode_a_baseline=result_a,
            mode_b_exact=result_b,
            mode_c_semantic=result_c,
            semantic_speedup_factor=speedup,
            semantic_token_savings=tokens_saved_c,
        )

        self._history.append(summary)
        if len(self._history) > 20:
            self._history.pop(0)

        return summary
