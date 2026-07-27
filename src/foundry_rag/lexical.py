"""BM25 lexical retrieval -- the keyword half of hybrid search.

Embeddings are good at meaning and bad at rare literal tokens: a model name, an
error code, a number like ``1536``. Keyword search is the opposite. Running
both and fusing the rankings recovers what either one alone would miss.

BM25 is the standard scoring function for the keyword side::

    score(D, Q) = Σ  idf(q) · ( f(q,D) · (k1 + 1) )
                  q     ───────────────────────────────────────
                        f(q,D) + k1 · (1 − b + b · |D| / avgdl)

Read it as three ideas:

* **f(q,D)** -- a term appearing more often in a document is better, but with
  **saturation**: ``k1`` caps how much the 10th occurrence adds over the 2nd.
  Plain term-frequency has no such cap, which is why raw TF over-rewards
  repetitive documents.
* **idf(q)** -- a term appearing in *few* documents is more informative. "ve"
  is in everything and tells you nothing; "1536" is in one chunk and tells you
  a lot.
* **|D| / avgdl** -- longer documents match more terms by accident, so ``b``
  discounts them by length.

Tokens come from :func:`foundry_rag.turkish.expand_tokens`, so each word is
indexed under both its surface form and its stem. That is what makes
``belgelerden`` in a query match ``belge`` in a document.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .turkish import expand_tokens

#: term-frequency saturation. Higher = later occurrences keep counting.
DEFAULT_K1 = 1.5
#: length normalisation strength. 0 = ignore length, 1 = full normalisation.
DEFAULT_B = 0.75


@dataclass
class BM25Index:
    """In-memory BM25 index over a list of documents.

    Built once when the pipeline opens and reused for every query. At this
    project's scale (tens to thousands of chunks) building costs milliseconds
    and searching is a single pass over the query's postings lists.
    """

    documents: Sequence[str]
    k1: float = DEFAULT_K1
    b: float = DEFAULT_B

    #: term -> {document index: term frequency}
    postings: dict[str, dict[int, int]] = field(default_factory=dict, init=False)
    doc_lengths: np.ndarray = field(default=None, init=False, repr=False)
    idf: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    average_length: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        count = len(self.documents)
        lengths = np.zeros(count, dtype=np.float32)

        for index, text in enumerate(self.documents):
            tokens = expand_tokens(text)
            lengths[index] = len(tokens)
            for term, frequency in Counter(tokens).items():
                self.postings.setdefault(term, {})[index] = frequency

        self.doc_lengths = lengths
        self.average_length = float(lengths.mean()) if count else 0.0

        # Robertson-Sparck Jones idf with the +1 that keeps it non-negative.
        # Without the +1, a term present in more than half the corpus gets a
        # negative weight and actively pushes matching documents down.
        for term, docs in self.postings.items():
            document_frequency = len(docs)
            self.idf[term] = math.log(
                1.0 + (count - document_frequency + 0.5) / (document_frequency + 0.5)
            )

    def __len__(self) -> int:
        return len(self.documents)

    @property
    def vocabulary_size(self) -> int:
        return len(self.postings)

    def score_all(self, query: str) -> np.ndarray:
        """BM25 score of every document against ``query``."""
        scores = np.zeros(len(self.documents), dtype=np.float32)
        if not len(self.documents) or self.average_length == 0:
            return scores

        for term in expand_tokens(query):
            docs = self.postings.get(term)
            if not docs:
                continue
            weight = self.idf[term]
            for index, frequency in docs.items():
                normalised_length = self.doc_lengths[index] / self.average_length
                denominator = frequency + self.k1 * (1.0 - self.b + self.b * normalised_length)
                scores[index] += weight * (frequency * (self.k1 + 1.0)) / denominator

        return scores

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Return ``(document index, score)`` for the best ``top_k`` matches."""
        scores = self.score_all(query)
        if not scores.size:
            return []
        k = min(top_k, scores.size)
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(i), float(scores[i])) for i in top if scores[i] > 0]


def saturate(score: float, scale: float = 4.0) -> float:
    """Map an unbounded BM25 score into ``[0, 1)`` for threshold comparison.

    BM25 scores have no upper bound and their range shifts with corpus size, so
    they cannot be compared against a cosine threshold directly. ``x / (x + s)``
    is monotone, maps 0 to 0, and reaches 0.5 at ``x = s`` -- giving one
    interpretable knob instead of a magic constant per corpus.
    """
    if score <= 0:
        return 0.0
    return float(score / (score + scale))
