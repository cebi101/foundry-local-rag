"""BM25 scoring, reciprocal rank fusion, and hybrid retrieval behaviour."""

from __future__ import annotations

import numpy as np
import pytest

from foundry_rag.lexical import BM25Index, saturate
from foundry_rag.retrieval import hybrid_search, reciprocal_rank_fusion
from foundry_rag.store import ChunkRecord

DOCS = [
    "Kosinüs benzerliği iki vektör arasındaki açının kosinüsünü hesaplar.",
    "SQLite sunucusuz bir veritabanı motorudur ve tek dosyada saklanır.",
    "Bir float32 vektör 384 boyutta tam olarak 1536 bayt tutar.",
    "Kediler zorunlu etçildir ve taurin ihtiyacı duyar.",
]


@pytest.fixture
def index() -> BM25Index:
    return BM25Index(DOCS)


# -- BM25 ----------------------------------------------------------------


def test_index_covers_every_document(index):
    assert len(index) == len(DOCS)
    assert index.vocabulary_size > 0


def test_exact_term_ranks_its_document_first(index):
    results = index.search("kosinüs benzerliği", top_k=2)
    assert results[0][0] == 0


def test_rare_literal_token_is_found(index):
    """The case dense retrieval is worst at: an exact number."""
    results = index.search("1536 bayt", top_k=1)
    assert results[0][0] == 2


def test_inflected_query_matches_base_form(index):
    """'vektörlerin' in the query must reach 'vektör' in the document."""
    results = index.search("vektörlerin boyutu", top_k=1)
    assert results
    assert results[0][0] in {0, 2}


def test_unrelated_query_scores_zero(index):
    assert index.search("fotosentez kloroplast", top_k=3) == []


def test_scores_are_non_negative(index):
    """The +1 in the idf formula exists to prevent negative weights."""
    assert (index.score_all("bir ve veritabanı") >= 0).all()


def test_empty_index_is_safe():
    empty = BM25Index([])
    assert empty.search("herhangi bir sorgu") == []
    assert empty.score_all("sorgu").size == 0


def test_empty_query_returns_nothing(index):
    assert index.search("", top_k=3) == []


def test_longer_document_is_length_normalised():
    """Padding a document must not inflate its score for the same match."""
    short = BM25Index(["kosinüs benzerliği", "alakasız metin"])
    padded = BM25Index(["kosinüs benzerliği " + "dolgu " * 60, "alakasız metin"])
    assert padded.score_all("kosinüs")[0] < short.score_all("kosinüs")[0]


# -- saturation ----------------------------------------------------------


def test_saturate_maps_into_unit_interval():
    for value in [0.0, 0.5, 4.0, 100.0, 1e6]:
        assert 0.0 <= saturate(value) < 1.0


def test_saturate_is_monotone():
    values = [saturate(x) for x in [0.5, 1.0, 4.0, 16.0]]
    assert values == sorted(values)


def test_saturate_reaches_half_at_the_scale():
    assert saturate(4.0, scale=4.0) == pytest.approx(0.5)


def test_saturate_of_zero_is_zero():
    assert saturate(0.0) == 0.0
    assert saturate(-3.0) == 0.0


# -- reciprocal rank fusion ----------------------------------------------


def test_document_ranked_by_both_beats_one_ranked_by_one():
    fused = reciprocal_rank_fusion([[7, 1, 2], [7, 3, 4]])
    assert max(fused, key=fused.get) == 7


def test_rank_one_scores_highest_within_a_list():
    fused = reciprocal_rank_fusion([[10, 20, 30]])
    assert fused[10] > fused[20] > fused[30]


def test_fusion_of_nothing_is_empty():
    assert reciprocal_rank_fusion([]) == {}
    assert reciprocal_rank_fusion([[], []]) == {}


def test_smoothing_constant_flattens_top_ranks():
    """A large k reduces how much first place dominates second."""
    tight = reciprocal_rank_fusion([[1, 2]], k=1)
    flat = reciprocal_rank_fusion([[1, 2]], k=1000)
    assert (tight[1] - tight[2]) > (flat[1] - flat[2])


# -- hybrid search -------------------------------------------------------


def _records() -> list[ChunkRecord]:
    return [
        ChunkRecord(id=i, source=f"{i}.md", chunk_index=0, heading="", content=text)
        for i, text in enumerate(DOCS)
    ]


def _matrix() -> np.ndarray:
    # one-hot vectors: document i is the only match for query vector i
    return np.eye(len(DOCS), dtype=np.float32)


def test_lexical_rescues_what_dense_misses():
    """The core claim of hybrid search, tested directly.

    The dense vector points at document 3, but the query text is unmistakably
    about document 2. Keyword evidence must pull document 2 in.
    """
    records, matrix = _records(), _matrix()
    bm25 = BM25Index(DOCS)
    query_vector = [0.0, 0.0, 0.0, 1.0]

    dense_only = hybrid_search(
        records, matrix, query_vector, query_text="1536 bayt", bm25=None,
        top_k=2, min_similarity=0.3,
    )
    hybrid = hybrid_search(
        records, matrix, query_vector, query_text="1536 bayt", bm25=bm25,
        top_k=2, min_similarity=0.3, lexical_scale=4.0,
    )

    assert "2.md" not in [h.record.source for h in dense_only]
    assert "2.md" in [h.record.source for h in hybrid]


def test_hit_reports_which_retriever_found_it():
    records, matrix = _records(), _matrix()
    bm25 = BM25Index(DOCS)
    hits = hybrid_search(
        records, matrix, [0.0, 0.0, 1.0, 0.0], query_text="1536 bayt",
        bm25=bm25, top_k=1, min_similarity=0.1,
    )
    assert hits[0].matched_by in {"ikisi", "kelime", "anlam"}


def test_threshold_still_refuses_unrelated_queries():
    records, matrix = _records(), _matrix()
    bm25 = BM25Index(DOCS)
    hits = hybrid_search(
        records, matrix, [0.0, 0.0, 0.0, 0.0],
        query_text="fotosentez kloroplast klorofil", bm25=bm25,
        top_k=4, min_similarity=0.3, lexical_scale=16.0,
    )
    assert hits == []


def test_top_k_is_respected():
    records, matrix = _records(), _matrix()
    hits = hybrid_search(
        records, matrix, [1.0, 0.0, 0.0, 0.0], query_text="kosinüs",
        bm25=BM25Index(DOCS), top_k=2, min_similarity=0.0,
    )
    assert len(hits) <= 2


def test_empty_corpus_returns_nothing():
    assert hybrid_search([], np.zeros((0, 0)), [1.0], query_text="x") == []


def test_scores_are_recorded_separately():
    records, matrix = _records(), _matrix()
    hits = hybrid_search(
        records, matrix, [1.0, 0.0, 0.0, 0.0], query_text="kosinüs benzerliği",
        bm25=BM25Index(DOCS), top_k=1, min_similarity=0.0,
    )
    hit = hits[0]
    assert hit.dense_score > 0
    assert hit.lexical_score > 0
    assert hit.score == pytest.approx(max(hit.dense_score, saturate(hit.lexical_score, 16.0)))
