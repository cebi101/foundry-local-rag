"""Similarity maths and top-k selection."""

from __future__ import annotations

import numpy as np
import pytest

from foundry_rag.retrieval import cosine_similarity, normalize, search
from foundry_rag.store import VectorStore


def test_identical_vectors_score_one():
    matrix = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    assert cosine_similarity([1.0, 2.0, 3.0], matrix)[0] == pytest.approx(1.0, abs=1e-6)


def test_orthogonal_vectors_score_zero():
    matrix = np.array([[0.0, 1.0]], dtype=np.float32)
    assert cosine_similarity([1.0, 0.0], matrix)[0] == pytest.approx(0.0, abs=1e-6)


def test_opposite_vectors_score_minus_one():
    matrix = np.array([[-1.0, 0.0]], dtype=np.float32)
    assert cosine_similarity([1.0, 0.0], matrix)[0] == pytest.approx(-1.0, abs=1e-6)


def test_magnitude_does_not_change_cosine():
    matrix = np.array([[1.0, 1.0], [100.0, 100.0]], dtype=np.float32)
    scores = cosine_similarity([1.0, 1.0], matrix)
    assert scores[0] == pytest.approx(scores[1], abs=1e-6)


def test_zero_vector_does_not_produce_nan():
    matrix = np.array([[0.0, 0.0]], dtype=np.float32)
    assert not np.isnan(cosine_similarity([1.0, 0.0], matrix)).any()


def test_normalize_gives_unit_length_rows():
    normalized = normalize(np.array([[3.0, 4.0], [1.0, 0.0]], dtype=np.float32))
    assert np.allclose(np.linalg.norm(normalized, axis=1), 1.0, atol=1e-6)


def test_dimension_mismatch_is_reported_clearly():
    matrix = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="Dimension mismatch"):
        cosine_similarity([1.0, 0.0], matrix)


def test_empty_matrix_returns_no_scores():
    assert cosine_similarity([1.0, 0.0], np.zeros((0, 0))).size == 0


def _seed(store: VectorStore) -> None:
    store.add_chunks(
        [
            ("a.md", 0, "", "tam eslesme", "h1", [1.0, 0.0, 0.0]),
            ("b.md", 0, "", "kismi eslesme", "h2", [0.7, 0.7, 0.0]),
            ("c.md", 0, "", "ilgisiz", "h3", [0.0, 0.0, 1.0]),
        ]
    )


def test_search_orders_by_descending_score(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        _seed(store)
        hits = search(store, [1.0, 0.0, 0.0], top_k=3)
        assert [h.record.source for h in hits] == ["a.md", "b.md", "c.md"]
        assert hits[0].score > hits[1].score > hits[2].score


def test_search_respects_top_k(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        _seed(store)
        assert len(search(store, [1.0, 0.0, 0.0], top_k=2)) == 2


def test_threshold_filters_weak_matches(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        _seed(store)
        hits = search(store, [1.0, 0.0, 0.0], top_k=3, min_similarity=0.9)
        assert [h.record.source for h in hits] == ["a.md"]


def test_high_threshold_can_return_nothing(tmp_path):
    """This is the mechanism that lets the assistant say 'I don't know'."""
    with VectorStore(tmp_path / "t.db") as store:
        _seed(store)
        assert search(store, [0.0, 1.0, 0.0], top_k=3, min_similarity=0.99) == []


def test_search_on_empty_store(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        assert search(store, [1.0, 0.0], top_k=3) == []


def test_top_k_larger_than_corpus(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        _seed(store)
        assert len(search(store, [1.0, 0.0, 0.0], top_k=99)) == 3
