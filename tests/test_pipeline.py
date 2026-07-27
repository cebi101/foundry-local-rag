"""End-to-end tests: ingest a tiny corpus, then ask questions against it."""

from __future__ import annotations

import pytest

from foundry_rag import RagPipeline, Settings, ingest
from foundry_rag.backends.hashing import HashingBackend
from foundry_rag.pipeline import META_SIGNATURE
from foundry_rag.store import VectorStore


@pytest.fixture
def indexed(settings, backend):
    ingest(settings, backend=backend, verbose=False)
    with RagPipeline(settings, backend=backend) as pipeline:
        yield pipeline


# -- ingestion -----------------------------------------------------------


def test_ingest_indexes_every_document(settings, backend):
    report = ingest(settings, backend=backend, verbose=False)
    assert report.documents == 2
    assert report.chunks > 0
    assert report.inserted == report.chunks


def test_ingest_records_the_embedding_signature(settings, backend):
    ingest(settings, backend=backend, verbose=False)
    with VectorStore(settings.db_path) as store:
        assert store.get_meta(META_SIGNATURE) == backend.embedding_signature()
        assert store.get_meta("chunk_size") == str(settings.chunk_size)


def test_reingest_replaces_rather_than_duplicates(settings, backend):
    first = ingest(settings, backend=backend, verbose=False)
    second = ingest(settings, backend=backend, verbose=False)
    assert first.chunks == second.chunks
    with VectorStore(settings.db_path) as store:
        assert store.count() == second.chunks


def test_ingest_on_empty_folder_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    settings = Settings(docs_dir=empty, db_path=tmp_path / "x.db", backend="hashing")
    with pytest.raises(ValueError, match="islenebilir belge yok"):
        ingest(settings, backend=HashingBackend(), verbose=False)


def test_ingest_on_missing_folder_raises(tmp_path):
    settings = Settings(
        docs_dir=tmp_path / "yok", db_path=tmp_path / "x.db", backend="hashing"
    )
    with pytest.raises(FileNotFoundError):
        ingest(settings, backend=HashingBackend(), verbose=False)


# -- querying ------------------------------------------------------------


def test_pipeline_refuses_to_open_an_empty_index(settings, backend):
    with pytest.raises(RuntimeError, match="Veritabani bos"):
        RagPipeline(settings, backend=backend)


def test_answer_retrieves_the_right_document(indexed):
    answer = indexed.answer("Kediler neden taurine ihtiyaç duyar?")
    assert answer.hits
    assert "kediler.md" in answer.sources


def test_answer_cites_its_sources(indexed):
    answer = indexed.answer("Filtre kahve için su sıcaklığı kaç derece olmalı?")
    assert "kahve.md" in answer.sources
    assert answer.grounded


def test_unanswerable_question_is_refused(indexed):
    """Nothing clears the threshold, so we must not call the model at all."""
    indexed.settings.min_similarity = 0.99
    answer = indexed.answer("Jüpiter'in kaç uydusu vardır?")
    assert answer.hits == []
    assert answer.grounded is False
    assert "belgelerde yok" in answer.text


def test_empty_question_is_handled(indexed):
    answer = indexed.answer("")
    assert answer.hits == []
    assert answer.grounded is False


def test_whitespace_only_question_is_handled(indexed):
    assert indexed.answer("   \n\t ").grounded is False


def test_top_k_is_respected(indexed):
    indexed.settings.top_k = 2
    assert len(indexed.answer("kedi").hits) <= 2


def test_timings_are_recorded(indexed):
    answer = indexed.answer("Kediler günde kaç saat uyur?")
    assert answer.retrieval_seconds >= 0
    assert answer.total_seconds >= answer.retrieval_seconds


def test_sources_are_unique_and_ordered_by_relevance(indexed):
    sources = indexed.answer("kedi beslenmesi taurin").sources
    assert len(sources) == len(set(sources))


def test_stream_answer_matches_answer(indexed):
    question = "Kediler günde kaç saat uyur?"
    streamed = "".join(indexed.stream_answer(question))
    assert streamed.strip() == indexed.answer(question).text.strip()


def test_signature_mismatch_is_detected(settings, backend, monkeypatch):
    """An index built by another embedder must be rejected, not silently used."""
    ingest(settings, backend=backend, verbose=False)
    with VectorStore(settings.db_path) as store:
        store.set_meta(META_SIGNATURE, "baska-model:1024")
    with pytest.raises(RuntimeError, match="farkli bir embedding modeliyle"):
        RagPipeline(settings, backend=backend)
