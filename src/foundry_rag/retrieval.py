"""Vector similarity search over the stored chunks.

Cosine similarity, computed brute-force with numpy. For the scale this project
targets (hundreds to a few thousand chunks) a full matrix multiply takes
single-digit milliseconds, which is nothing next to the LLM call that follows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .store import ChunkRecord, VectorStore


@dataclass(frozen=True)
class SearchHit:
    """One retrieved chunk together with its similarity score."""

    record: ChunkRecord
    score: float


def normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalise rows. Zero rows stay zero instead of becoming NaN."""
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def cosine_similarity(query: Sequence[float], matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity between one query vector and every row of ``matrix``.

    Both sides are normalised first, so the similarity reduces to a dot product.
    """
    if matrix.size == 0:
        return np.zeros((0,), dtype=np.float32)

    q = normalize(np.asarray(query, dtype=np.float32))
    if q.shape[1] != matrix.shape[1]:
        raise ValueError(
            f"Dimension mismatch: query has {q.shape[1]} dims but the index has "
            f"{matrix.shape[1]}. The query and the index must use the same "
            "embedding model -- re-run ingestion."
        )
    return (normalize(matrix) @ q.T).ravel()


def search(
    store: VectorStore,
    query_vector: Sequence[float],
    top_k: int = 4,
    min_similarity: float = 0.0,
) -> list[SearchHit]:
    """Return the ``top_k`` most similar chunks above ``min_similarity``.

    The threshold matters: without it, a question with no answer in the corpus
    still returns the "least bad" chunks, and the model dutifully hallucinates
    an answer from them. Returning nothing lets the pipeline say "I don't know".
    """
    matrix, records = store.load_matrix()
    if not records:
        return []

    scores = cosine_similarity(query_vector, matrix)

    # argsort ascending -> take the tail, then reverse for descending order
    k = min(top_k, len(records))
    top_idx = np.argsort(scores)[-k:][::-1]

    return [
        SearchHit(record=records[i], score=float(scores[i]))
        for i in top_idx
        if scores[i] >= min_similarity
    ]
