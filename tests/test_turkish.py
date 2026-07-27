"""Turkish normalisation: the piece most likely to be silently wrong."""

from __future__ import annotations

import pytest

from foundry_rag.turkish import (
    expand_tokens,
    fold_case,
    last_vowel,
    shares_root,
    stem_word,
    tokenize,
)


# -- case folding --------------------------------------------------------


def test_dotless_i_folds_correctly():
    """Python's str.lower() maps I->i, which is wrong for Turkish."""
    assert fold_case("ISPARTA") == "ısparta"
    assert fold_case("İSTANBUL") == "istanbul"


def test_case_folding_is_idempotent():
    assert fold_case(fold_case("İÇGÜDÜ")) == fold_case("İÇGÜDÜ")


def test_turkish_specific_letters_fold():
    assert fold_case("ÇÖĞÜŞ") == "çöğüş"


# -- vowel harmony -------------------------------------------------------


def test_last_vowel_detection():
    assert last_vowel("belge") == "e"
    assert last_vowel("kitap") == "a"
    assert last_vowel("brt") is None


# -- stemming ------------------------------------------------------------


@pytest.mark.parametrize(
    "word,expected",
    [
        ("vektörler", "vektör"),
        ("vektörlerin", "vektör"),
        ("modeller", "model"),
        ("modelin", "model"),
        ("kediler", "kedi"),
        ("embeddingler", "embedding"),
    ],
)
def test_known_stems(word, expected):
    assert stem_word(word) == expected


def test_apostrophe_marks_the_root_boundary():
    assert stem_word("RAG'in") == "rag"
    assert stem_word("RAG'den") == "rag"


def test_apostrophe_root_is_not_stripped_further():
    """'SQLite'ta' must not become 'sqli' by eating the root's own -te."""
    assert stem_word("SQLite'ta") == "sqlite"
    assert stem_word("SQLite'ın") == "sqlite"


def test_short_words_are_left_alone():
    assert stem_word("ve") == "ve"
    assert stem_word("bir") == "bir"


def test_consonant_softening_is_reversed():
    """benzerliği -> benzerliğ -> benzerlik -> benzer, meeting the base form."""
    assert stem_word("benzerlik") == stem_word("benzerliği")


def test_single_char_suffix_only_stripped_once():
    """Without this guard 'parçalar' runs away to 'parç'."""
    assert stem_word("parçalar") == "parça"


def test_stemmer_never_returns_empty():
    for word in ["a", "ve", "belgelerinden", "çalışmalarımızdan"]:
        assert stem_word(word)


# -- expansion (what the index actually uses) ----------------------------


def test_expansion_contains_surface_and_stem():
    tokens = expand_tokens("belgeler")
    assert "belgeler" in tokens
    assert "belge" in tokens


@pytest.mark.parametrize(
    "family",
    [
        ["embedding", "embeddingler", "embedding'lerin"],
        ["vektör", "vektörler", "vektörlerin", "vektörlere"],
        ["belge", "belgeler", "belgelerden", "belgeleri"],
        ["parça", "parçalar", "parçalama", "parçalardan"],
        ["sorgu", "sorgular", "sorgudan", "sorgunun"],
        ["model", "modeller", "modelin", "modellerden"],
        ["benzerlik", "benzerliği", "benzerlikler"],
        ["kedi", "kediler", "kedilerin"],
        ["SQLite", "SQLite'ta", "SQLite'ın"],
        ["RAG", "RAG'in", "RAG'den"],
        ["bilgi", "bilgiler", "bilgiden"],
        ["çalışma", "çalışmalar", "çalışmadan"],
    ],
)
def test_word_families_share_a_root(family):
    """Every inflected form must be matchable against the base form."""
    base = family[0]
    for variant in family[1:]:
        assert shares_root(base, variant), f"{base} !~ {variant}"


@pytest.mark.parametrize(
    "a,b",
    [
        ("kedi", "kahve"),
        ("vektör", "veri"),
        ("model", "modern"),
        ("bilgi", "bilek"),
        ("sorgu", "sormak"),
    ],
)
def test_unrelated_words_do_not_match(a, b):
    """Over-stemming would collapse distinct words -- guard against it."""
    assert not shares_root(a, b)


# -- tokenisation --------------------------------------------------------


def test_tokenize_drops_punctuation():
    assert tokenize("Merhaba, dünya!", stem=False) == ["merhaba", "dünya"]


def test_tokenize_keeps_numbers():
    assert "1536" in tokenize("1536 bayt tutar", stem=False)


def test_empty_text_yields_no_tokens():
    assert tokenize("") == []
    assert expand_tokens("   ") == []
