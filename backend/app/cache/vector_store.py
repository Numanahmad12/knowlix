"""Dedicated FAISS semantic vector store for Knowlix cache entries.

Uses an isolated FAISS IndexFlatIP (wrapped in IndexIDMap2) to index 384-dimensional
normalized embeddings of previously answered questions, completely decoupled
from document chunk retrieval vectors.
"""

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .models import CacheEntry

logger = logging.getLogger(__name__)

try:
    import faiss
except ImportError:  # pragma: no cover
    faiss = None

DIMENSION = 384


class SemanticVectorStore:
    """Isolated, bounded vector index for cached query embeddings."""

    def __init__(self, dimension: int = DIMENSION, max_entries: int = 1000):
        self._dim = dimension
        self._max_entries = max(10, max_entries)
        self._lock = threading.RLock()

        self._next_id: int = 1
        # Map internal int_id -> CacheEntry
        self._id_to_entry: Dict[int, CacheEntry] = {}
        # Map string entry_id -> internal int_id
        self._entry_id_to_int_id: Dict[str, int] = {}
        # Track LRU access order of string entry_ids
        self._lru_order: OrderedDict[str, float] = OrderedDict()

        # Numpy fallback matrix when FAISS is unavailable or fails
        self._vectors_map: Dict[int, np.ndarray] = {}

        self._faiss_index = None
        self._init_faiss_index()

    def _init_faiss_index(self) -> None:
        if faiss is not None:
            try:
                base_index = faiss.IndexFlatIP(self._dim)
                self._faiss_index = faiss.IndexIDMap2(base_index)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to initialize FAISS semantic cache index (%s). Using numpy fallback.", exc)
                self._faiss_index = None

    def size(self) -> int:
        with self._lock:
            return len(self._id_to_entry)

    def get_by_id(self, entry_id: str) -> Optional[CacheEntry]:
        with self._lock:
            int_id = self._entry_id_to_int_id.get(entry_id)
            if int_id is None:
                return None
            entry = self._id_to_entry.get(int_id)
            if entry and not entry.is_expired():
                self._lru_order.move_to_end(entry_id)
                return entry
            elif entry and entry.is_expired():
                self.remove_entry(entry_id)
                return None
            return None

    def get_all_entries(self) -> List[CacheEntry]:
        with self._lock:
            self.evict_expired()
            return list(self._id_to_entry.values())

    def add_entry(self, entry: CacheEntry, vector: np.ndarray) -> bool:
        """Add or replace a cache entry with its 384-d normalized vector."""
        with self._lock:
            # Normalize vector shape
            vec = np.asarray(vector, dtype=np.float32).reshape(1, -1)
            if vec.shape[1] != self._dim:
                logger.error("Vector dimension mismatch: expected %d, got %d", self._dim, vec.shape[1])
                return False

            # Normalize L2 norm
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            # If entry_id already exists, remove it first
            if entry.entry_id in self._entry_id_to_int_id:
                self.remove_entry(entry.entry_id)

            # Evict if full
            self.evict_expired()
            while len(self._id_to_entry) >= self._max_entries:
                oldest_entry_id = next(iter(self._lru_order))
                self.remove_entry(oldest_entry_id)

            int_id = self._next_id
            self._next_id += 1

            self._id_to_entry[int_id] = entry
            self._entry_id_to_int_id[entry.entry_id] = int_id
            self._lru_order[entry.entry_id] = time.time()
            self._vectors_map[int_id] = vec[0]

            if self._faiss_index is not None:
                try:
                    ids_arr = np.array([int_id], dtype=np.int64)
                    self._faiss_index.add_with_ids(vec, ids_arr)
                except Exception as exc:
                    logger.warning("FAISS add_with_ids failed (%s). Falling back to numpy for search.", exc)

            return True

    def remove_entry(self, entry_id: str) -> bool:
        """Remove a single entry by entry_id."""
        with self._lock:
            int_id = self._entry_id_to_int_id.pop(entry_id, None)
            if int_id is None:
                return False

            self._id_to_entry.pop(int_id, None)
            self._lru_order.pop(entry_id, None)
            self._vectors_map.pop(int_id, None)

            if self._faiss_index is not None:
                try:
                    ids_arr = np.array([int_id], dtype=np.int64)
                    self._faiss_index.remove_ids(ids_arr)
                except Exception as exc:
                    logger.warning("FAISS remove_ids failed (%s). Rebuilding index.", exc)
                    self._rebuild_faiss_index()

            return True

    def remove_by_doc_id(self, doc_id: str) -> int:
        """Remove all entries matching a document ID (e.g. on session deletion)."""
        with self._lock:
            to_remove = [
                entry.entry_id
                for entry in self._id_to_entry.values()
                if entry.doc_id == doc_id
            ]
            for eid in to_remove:
                self.remove_entry(eid)
            return len(to_remove)

    def remove_by_doc_hash(self, doc_hash: str) -> int:
        """Remove all entries matching a document content hash (e.g. on PDF replace)."""
        with self._lock:
            to_remove = [
                entry.entry_id
                for entry in self._id_to_entry.values()
                if entry.doc_hash == doc_hash
            ]
            for eid in to_remove:
                self.remove_entry(eid)
            return len(to_remove)

    def clear(self) -> None:
        """Clear all entries and vectors from the index."""
        with self._lock:
            self._id_to_entry.clear()
            self._entry_id_to_int_id.clear()
            self._lru_order.clear()
            self._vectors_map.clear()
            self._init_faiss_index()

    def evict_expired(self, current_time: Optional[float] = None) -> int:
        """Evict all entries that have exceeded their TTL."""
        with self._lock:
            now = current_time if current_time is not None else time.time()
            expired_ids = [
                entry.entry_id
                for entry in self._id_to_entry.values()
                if entry.is_expired(now)
            ]
            for eid in expired_ids:
                self.remove_entry(eid)
            return len(expired_ids)

    def search(
        self, query_vector: np.ndarray, top_k: int = 5
    ) -> List[Tuple[CacheEntry, float]]:
        """Search nearest candidates by inner product (= cosine similarity)."""
        with self._lock:
            self.evict_expired()
            n_entries = len(self._id_to_entry)
            if n_entries == 0:
                return []

            q_vec = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)
            norm = np.linalg.norm(q_vec)
            if norm > 0:
                q_vec = q_vec / norm

            k = min(top_k, n_entries)

            # Try FAISS index first
            if self._faiss_index is not None and self._faiss_index.ntotal > 0:
                try:
                    scores, indices = self._faiss_index.search(q_vec, k)
                    results = []
                    for score, idx in zip(scores[0], indices[0]):
                        if idx >= 0 and int(idx) in self._id_to_entry:
                            results.append((self._id_to_entry[int(idx)], float(score)))
                    return results
                except Exception as exc:
                    logger.warning("FAISS search failed (%s). Falling back to numpy search.", exc)

            # Pure NumPy fallback
            candidates = []
            for int_id, vec in self._vectors_map.items():
                sim = float(np.dot(q_vec[0], vec))
                candidates.append((self._id_to_entry[int_id], sim))

            candidates.sort(key=lambda item: item[1], reverse=True)
            return candidates[:k]

    def _rebuild_faiss_index(self) -> None:
        """Rebuild the FAISS index from the in-memory vectors map."""
        self._init_faiss_index()
        if self._faiss_index is not None and self._vectors_map:
            int_ids = np.array(list(self._vectors_map.keys()), dtype=np.int64)
            matrix = np.array(list(self._vectors_map.values()), dtype=np.float32)
            self._faiss_index.add_with_ids(matrix, int_ids)
