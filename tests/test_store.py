"""Storage tests. The one that matters most: vectors must survive a round trip."""

from __future__ import annotations

import numpy as np
import pytest

from foundry_rag.store import VectorStore, decode_vector, encode_vector


def test_vector_round_trip_preserves_values():
    original = [0.1, -0.25, 3.5, 0.0, -1.75]
    restored = decode_vector(encode_vector(original))
    assert len(restored) == len(original)
    # float32 storage: exact equality is not guaranteed, 1e-6 is plenty
    assert np.allclose(restored, original, atol=1e-6)


def test_blob_size_is_four_bytes_per_dimension():
    assert len(encode_vector([0.0] * 384)) == 384 * 4


def test_add_and_count(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        assert store.count() == 0
        store.add_chunks([("a.md", 0, "Bolum", "metin", "hash-1", [0.1, 0.2, 0.3])])
        assert store.count() == 1


def test_duplicate_hash_is_ignored(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        row = ("a.md", 0, "B", "metin", "ayni-hash", [0.1, 0.2])
        store.add_chunks([row])
        store.add_chunks([row])
        assert store.count() == 1


def test_load_matrix_shape_and_order(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        store.add_chunks(
            [
                ("a.md", 0, "", "birinci", "h1", [1.0, 0.0, 0.0]),
                ("a.md", 1, "", "ikinci", "h2", [0.0, 1.0, 0.0]),
                ("b.md", 0, "", "ucuncu", "h3", [0.0, 0.0, 1.0]),
            ]
        )
        matrix, records = store.load_matrix()
        assert matrix.shape == (3, 3)
        assert [r.content for r in records] == ["birinci", "ikinci", "ucuncu"]
        assert [r.source for r in records] == ["a.md", "a.md", "b.md"]


def test_empty_store_returns_empty_matrix(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        matrix, records = store.load_matrix()
        assert records == []
        assert matrix.size == 0


def test_mixed_dimensions_raise(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        store.add_chunks([("a.md", 0, "", "x", "h1", [1.0, 0.0])])
        store.add_chunks([("a.md", 1, "", "y", "h2", [1.0, 0.0, 0.0])])
        with pytest.raises(ValueError, match="mixed embedding dimensions"):
            store.load_matrix()


def test_reset_clears_everything(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        store.add_chunks([("a.md", 0, "", "x", "h1", [1.0, 0.0])])
        store.set_meta("backend", "hashing")
        store.reset()
        assert store.count() == 0
        assert store.get_meta("backend") is None


def test_meta_upsert(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        store.set_meta("k", "birinci")
        store.set_meta("k", "ikinci")
        assert store.get_meta("k") == "ikinci"
        assert store.get_meta("yok", "varsayilan") == "varsayilan"


def test_citation_formatting(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        store.add_chunks(
            [
                ("a.md", 0, "Beslenme", "x", "h1", [1.0, 0.0]),
                ("b.md", 0, "", "y", "h2", [0.0, 1.0]),
            ]
        )
        _, records = store.load_matrix()
        assert records[0].citation == "a.md > Beslenme"
        assert records[1].citation == "b.md"
