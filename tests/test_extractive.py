"""Extractive answering and the groundedness circuit breaker.

The circuit breaker is the one behaviour here that is easy to get subtly wrong,
so it gets tested against a backend that is deliberately made to hallucinate.
"""

from __future__ import annotations

import pytest

from foundry_rag import RagPipeline, ingest
from foundry_rag.backends.base import Backend
from foundry_rag.backends.hashing import HashingBackend, embed_one
from foundry_rag.extractive import (
    FALLBACK_NOTICE,
    NO_ANSWER,
    extract_answer,
    score_sentence,
    split_sentences,
)
from foundry_rag.retrieval import SearchHit
from foundry_rag.store import ChunkRecord

CATS = (
    "Kediler zorunlu etçildir ve taurin adlı amino asidi kendi vücutlarında "
    "yeterince üretemezler. Bu yüzden taurini hazır mamadan almaları gerekir. "
    "Bir kedi günde ortalama on altı saat uyur."
)
COFFEE = (
    "Filtre kahve için önerilen su sıcaklığı doksan iki ile doksan altı derece "
    "arasındadır. Daha sıcak su acı bir tat bırakır."
)


def _hit(content: str, source: str) -> SearchHit:
    return SearchHit(
        record=ChunkRecord(id=1, source=source, chunk_index=0, heading="", content=content),
        score=0.9,
        dense_score=0.9,
    )


HITS = [_hit(CATS, "kediler.md"), _hit(COFFEE, "kahve.md")]


# -- sentence handling ---------------------------------------------------


def test_splits_into_sentences():
    assert len(split_sentences(CATS)) == 3


def test_short_fragments_dropped():
    assert split_sentences("Evet. Hayır. Tamam.") == []


def test_relevance_scoring_prefers_the_matching_sentence():
    terms = {"taurin", "kedi"}
    high = score_sentence(terms, "Kediler taurin ihtiyacı duyar.")
    low = score_sentence(terms, "Filtre kahve doksan iki derecede demlenir.")
    assert high > low


def test_empty_question_terms_score_zero():
    assert score_sentence(set(), "herhangi bir cümle") == 0.0


# -- extraction ----------------------------------------------------------


def test_quotes_the_sentence_that_answers_the_question():
    answer = extract_answer("Kediler neden taurine ihtiyaç duyar?", HITS)
    assert "taurin" in answer
    assert "[kediler.md]" in answer


def test_every_line_carries_its_source():
    answer = extract_answer("Kediler ne yer ve kahve kaç derecede demlenir?", HITS)
    for line in answer.splitlines():
        if line.strip():
            assert "[" in line and "]" in line


def test_respects_max_sentences():
    answer = extract_answer("kedi taurin uyku kahve derece", HITS, max_sentences=2)
    assert len([line for line in answer.splitlines() if line.strip()]) <= 2


def test_no_hits_means_no_answer():
    assert extract_answer("herhangi bir soru", []) == NO_ANSWER


def test_irrelevant_question_is_refused():
    assert extract_answer("Osmanlı Devleti hangi yılda kuruldu?", HITS) == NO_ANSWER


def test_higher_ranked_chunk_wins_ties():
    """Retrieval already decided which passage answers the question."""
    first = extract_answer("taurin", [_hit(CATS, "a.md"), _hit(CATS, "b.md")], max_sentences=1)
    assert "[a.md]" in first


def test_notice_is_appended_when_given():
    answer = extract_answer("Kediler neden taurine ihtiyaç duyar?", HITS, notice=FALLBACK_NOTICE)
    assert answer.endswith(FALLBACK_NOTICE)


def test_duplicate_sentences_are_not_repeated():
    """Overlapping chunks contain the same sentence twice."""
    answer = extract_answer("taurin", [_hit(CATS, "a.md"), _hit(CATS, "a.md")], max_sentences=3)
    lines = [line for line in answer.splitlines() if line.strip()]
    assert len(lines) == len(set(lines))


# -- circuit breaker -----------------------------------------------------


class HallucinatingBackend(Backend):
    """A backend that retrieves correctly and then invents its answer.

    Exactly the failure mode the circuit breaker exists for -- and the one
    observed for real with qwen2.5-0.5b on Turkish prompts.
    """

    name = "hallucinating-test"

    @property
    def embedding_dim(self) -> int:
        return 512

    def embed(self, texts):
        return [embed_one(t) for t in texts]

    def embedding_signature(self) -> str:
        # Embeddings come from HashingBackend's own function, so this really is
        # the same vector space -- report it as such or the index check (rightly)
        # refuses to open an index built by the other backend.
        return HashingBackend().embedding_signature()

    def chat(self, messages, temperature=0.1, max_tokens=600):
        return (
            "Kosinüs benzerliği bin dokuz yüz elli yılında İskoçya'da icat edilmiştir. "
            "Hesaplanması için kuantum bilgisayar gereklidir."
        )


@pytest.fixture
def indexed(settings):
    backend = HashingBackend()
    ingest(settings, backend=backend, verbose=False)
    return settings


def test_generative_mode_keeps_the_hallucination(indexed):
    """With the breaker off, the fabricated answer reaches the user."""
    indexed.answer_mode = "generative"
    with RagPipeline(indexed, backend=HallucinatingBackend()) as rag:
        answer = rag.answer("Kediler neden taurine ihtiyaç duyar?")
        assert answer.mode == "generative"
        assert "kuantum" in answer.text
        assert answer.groundedness.score < 0.34


def test_auto_mode_falls_back_when_ungrounded(indexed):
    indexed.answer_mode = "auto"
    with RagPipeline(indexed, backend=HallucinatingBackend()) as rag:
        answer = rag.answer("Kediler neden taurine ihtiyaç duyar?")
        assert answer.mode == "extractive-fallback"
        assert "kuantum" not in answer.text
        assert "taurin" in answer.text
        assert FALLBACK_NOTICE.strip() in answer.text


def test_auto_mode_keeps_a_grounded_answer(indexed):
    """The breaker must not fire on a good answer."""
    indexed.answer_mode = "auto"
    with RagPipeline(indexed, backend=HashingBackend()) as rag:
        answer = rag.answer("Kediler neden taurine ihtiyaç duyar?")
        assert answer.mode == "generative"


def test_extractive_mode_never_calls_the_model(indexed):
    indexed.answer_mode = "extractive"

    class ExplodingBackend(HallucinatingBackend):
        def chat(self, messages, temperature=0.1, max_tokens=600):
            raise AssertionError("extractive mode must not call chat()")

    with RagPipeline(indexed, backend=ExplodingBackend()) as rag:
        answer = rag.answer("Kediler neden taurine ihtiyaç duyar?")
        assert answer.mode == "extractive"
        assert "taurin" in answer.text


def test_unanswerable_question_still_refused_in_extractive_mode(indexed):
    indexed.answer_mode = "extractive"
    indexed.min_similarity = 0.99
    with RagPipeline(indexed, backend=HashingBackend()) as rag:
        answer = rag.answer("Jüpiter'in kaç uydusu vardır?")
        assert answer.hits == []
        assert answer.grounded is False


def test_invalid_answer_mode_is_rejected(settings):
    settings.answer_mode = "sacmalik"
    with pytest.raises(ValueError, match="answer_mode"):
        settings.validate()
