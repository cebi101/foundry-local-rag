"""The hallucination detector. Its job is to separate two kinds of sentence:
one the retrieved passages support, and one the model made up.
"""

from __future__ import annotations

import pytest

from foundry_rag.groundedness import check, split_sentences, support_score
from foundry_rag.retrieval import SearchHit
from foundry_rag.store import ChunkRecord

CONTEXT = (
    "Kosinüs benzerliği iki vektör arasındaki açının kosinüsünü hesaplar. "
    "Nokta çarpımı, vektör normlarının çarpımına bölünür. Sonuç eksi bir ile "
    "bir arasında değişir. Normalize edilmiş vektörlerde kosinüs benzerliği "
    "basit nokta çarpımına eşittir."
)


def _hit(content: str = CONTEXT, source: str = "03-embedding.md") -> SearchHit:
    return SearchHit(
        record=ChunkRecord(
            id=1, source=source, chunk_index=0, heading="Kosinüs Benzerliği", content=content
        ),
        score=0.9,
        dense_score=0.9,
    )


# -- sentence splitting --------------------------------------------------


def test_splits_on_sentence_boundaries():
    text = "Birinci cümle burada bitiyor. İkinci cümle de burada bitiyor."
    assert len(split_sentences(text)) == 2


def test_citations_are_stripped_before_checking():
    """'[03-embedding.md]' is metadata, not a claim."""
    sentences = split_sentences("Kosinüs açının kosinüsünü hesaplar [03-embedding.md].")
    assert "[" not in sentences[0]


def test_markdown_is_stripped():
    assert "*" not in split_sentences("**Kosinüs benzerliği** açıyı ölçen bir yöntemdir.")[0]


def test_short_fragments_are_ignored():
    """'Evet.' carries no checkable claim."""
    assert split_sentences("Evet. Tamam.") == []


def test_empty_answer_splits_to_nothing():
    assert split_sentences("") == []


# -- support scoring -----------------------------------------------------


def test_verbatim_sentence_scores_high():
    score = support_score(
        "Kosinüs benzerliği iki vektör arasındaki açının kosinüsünü hesaplar.",
        CONTEXT,
        {},
    )
    assert score > 0.9


def test_unrelated_sentence_scores_low():
    score = support_score(
        "Osmanlı Devleti bin üç yüz bir yılında Söğüt kasabasında kurulmuştur.",
        CONTEXT,
        {},
    )
    assert score < 0.3


def test_stopwords_do_not_create_support():
    """A fluent sentence made only of function words must not look grounded."""
    assert support_score("Ve bu bir şey için de daha çok olarak.", CONTEXT, {}) < 0.45


def test_empty_sentence_scores_zero():
    assert support_score("", CONTEXT, {}) == 0.0


# -- whole-answer check --------------------------------------------------


def test_grounded_answer_passes():
    answer = (
        "Kosinüs benzerliği iki vektör arasındaki açının kosinüsünü hesaplar. "
        "Nokta çarpımı vektör normlarının çarpımına bölünür."
    )
    report = check(answer, [_hit()])
    assert report.score == 1.0
    assert report.is_clean
    assert report.unsupported == []


def test_fabricated_answer_is_flagged():
    answer = (
        "Kosinüs benzerliği bin dokuz yüz elli yılında Isaac Newton tarafından "
        "İskoçya'da icat edilmiştir. Hesaplanması için kuantum bilgisayar gerekir."
    )
    report = check(answer, [_hit()])
    assert report.score == 0.0
    assert len(report.unsupported) == 2


def test_mixed_answer_flags_only_the_invented_sentence():
    """The realistic failure: a true sentence followed by an embellishment."""
    answer = (
        "Kosinüs benzerliği iki vektör arasındaki açının kosinüsünü hesaplar. "
        "Bu yöntem Google tarafından iki bin yirmi altıda patentlenmiş bir tekniktir."
    )
    report = check(answer, [_hit()])
    assert 0.0 < report.score < 1.0
    assert len(report.unsupported) == 1
    assert "patent" in report.unsupported[0].text.lower()


def test_answer_without_context_is_not_grounded():
    report = check("Herhangi bir iddia içeren yeterince uzun bir cümle.", [])
    assert report.score == 0.0
    assert not report.is_clean


def test_empty_answer_is_vacuously_clean():
    report = check("", [_hit()])
    assert report.score == 1.0
    assert report.sentences == []


def test_verdict_records_the_supporting_source():
    report = check(
        "Kosinüs benzerliği iki vektör arasındaki açının kosinüsünü hesaplar.", [_hit()]
    )
    assert report.sentences[0].best_source == "03-embedding.md"


def test_best_source_picked_across_multiple_passages():
    other = _hit("Kediler zorunlu etçildir ve taurin ihtiyacı duyar.", "kedi.md")
    report = check(
        "Kediler zorunlu etçildir ve taurin ihtiyacı duyar.", [_hit(), other]
    )
    assert report.sentences[0].best_source == "kedi.md"


def test_threshold_is_adjustable():
    answer = "Kosinüs benzerliği iki vektör arasındaki açının kosinüsünü hesaplar."
    assert check(answer, [_hit()], threshold=0.99).score <= 1.0
    assert check(answer, [_hit()], threshold=0.0).score == 1.0


def test_summary_is_human_readable():
    report = check("Kosinüs iki vektör arasındaki açının kosinüsünü hesaplar.", [_hit()])
    assert "Kaynaklilik" in report.summary()
