"""Vector similarity search over the stored chunks.

Cosine similarity, computed brute-force with numpy. For the scale this project
targets (hundreds to a few thousand chunks) a full matrix multiply takes
single-digit milliseconds, which is nothing next to the LLM call that follows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .lexical import BM25Index, saturate
from .store import ChunkRecord, VectorStore

#: RRF smoothing constant. 60 is the value from Cormack et al. (2009).
RRF_K = 60


@dataclass(frozen=True)
class SearchHit:
    """One retrieved chunk together with its scores.

    ``score`` is the **confidence** used for the answer/refuse decision.
    In dense-only mode it is the cosine similarity; in hybrid mode it is the
    stronger of the two retrievers' evidence. The per-retriever scores are kept
    alongside so you can see *why* a chunk was retrieved.
    """

    record: ChunkRecord
    score: float
    dense_score: float = 0.0
    lexical_score: float = 0.0
    fused_score: float = 0.0

    @property
    def matched_by(self) -> str:
        """Which retriever found this chunk -- useful when debugging recall."""
        dense = self.dense_score > 0.01
        lexical = self.lexical_score > 0.0
        if dense and lexical:
            return "ikisi"
        if lexical:
            return "kelime"
        return "anlam"


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
    """Dense-only search over a store. Returns the ``top_k`` best chunks.

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
        SearchHit(record=records[i], score=float(scores[i]), dense_score=float(scores[i]))
        for i in top_idx
        if scores[i] >= min_similarity
    ]


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[int]], k: int = RRF_K
) -> dict[int, float]:
    """Combine several ranked lists into one, using rank rather than score.

    ``RRF(d) = Σ 1 / (k + rank_i(d))`` over the lists that contain ``d``.

    Fusing on *rank* is the point. Cosine similarity lives in [-1, 1] and BM25
    is unbounded and corpus-dependent, so any weighted sum of the raw scores
    needs per-corpus tuning and silently breaks when the corpus changes. Ranks
    are directly comparable across retrievers with no calibration at all.

    ``k`` (60 by default, from Cormack et al. 2009) flattens the curve near the
    top: it stops a single retriever's first place from dominating a document
    that both retrievers placed in their top five.
    """
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, start=1):
            fused[index] = fused.get(index, 0.0) + 1.0 / (k + rank)
    return fused


def hybrid_search(
    records: Sequence[ChunkRecord],
    matrix: np.ndarray,
    query_vector: Sequence[float],
    query_text: str = "",
    bm25: BM25Index | None = None,
    top_k: int = 4,
    # Kept in step with Settings.min_similarity, which eval/calibrate.py chose.
    min_similarity: float = 0.30,
    rrf_k: int = RRF_K,
    lexical_scale: float = 4.0,
    candidate_multiplier: int = 5,
) -> list[SearchHit]:
    """Retrieve with dense vectors and BM25 together, fused by RRF.

    Why bother, when the embedding model is the "smart" one? Because the two
    fail in different places:

    * Dense search misses rare literal tokens -- a model id, ``1536``, an error
      string -- because embeddings blur exactly the details that make them rare.
    * Keyword search misses paraphrases -- a question about "araba fiyatları"
      against a document saying "otomobil ücretleri".

    A document that either retriever ranks highly survives fusion, so recall is
    the union rather than the intersection.

    The gate uses ``max(dense, saturated_lexical)``: a chunk is admitted if
    *either* retriever is confident about it. This is what stops a short query
    with weak embedding signal from being refused when the keyword match is
    unambiguous.
    """
    if not records:
        return []

    dense_scores = cosine_similarity(query_vector, matrix)
    lexical_scores = (
        bm25.score_all(query_text)
        if bm25 is not None and query_text
        else np.zeros(len(records), dtype=np.float32)
    )

    pool = min(len(records), max(top_k * candidate_multiplier, top_k))

    def top_indices(scores: np.ndarray) -> list[int]:
        if not scores.size or not np.any(scores > 0):
            return []
        size = min(pool, scores.size)
        idx = np.argpartition(-scores, size - 1)[:size]
        idx = idx[np.argsort(-scores[idx])]
        return [int(i) for i in idx if scores[i] > 0]

    rankings = [top_indices(dense_scores)]
    if bm25 is not None:
        rankings.append(top_indices(lexical_scores))

    fused = reciprocal_rank_fusion(rankings, k=rrf_k)
    if not fused:
        return []

    hits: list[SearchHit] = []
    for index in sorted(fused, key=lambda i: fused[i], reverse=True):
        dense = float(dense_scores[index])
        lexical = float(lexical_scores[index])
        confidence = max(dense, saturate(lexical, lexical_scale))
        if confidence < min_similarity:
            continue
        hits.append(
            SearchHit(
                record=records[index],
                score=confidence,
                dense_score=dense,
                lexical_score=lexical,
                fused_score=fused[index],
            )
        )
        if len(hits) >= top_k:
            break
    return hits
