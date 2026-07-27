"""Prompt assembly and the offline backend's contract."""

from __future__ import annotations

import numpy as np

from foundry_rag.backends.hashing import HashingBackend, embed_one, tokenize
from foundry_rag.prompts import build_messages, build_system_prompt, format_context
from foundry_rag.retrieval import SearchHit
from foundry_rag.store import ChunkRecord


def _hit(source: str, heading: str, content: str, score: float = 0.9) -> SearchHit:
    return SearchHit(
        record=ChunkRecord(id=1, source=source, chunk_index=0, heading=heading, content=content),
        score=score,
    )


# -- prompts -------------------------------------------------------------


def test_system_prompt_contains_the_five_rules():
    prompt = build_system_prompt("Türkçe")
    assert "Sadece" in prompt
    assert "Bu bilgi elimdeki belgelerde yok." in prompt
    assert "kaynağı" in prompt or "Kaynak" in prompt
    assert "Türkçe" in prompt


def test_language_is_injected():
    assert "English" in build_system_prompt("English")


def test_context_labels_every_passage_with_its_source():
    context = format_context([_hit("a.md", "Beslenme", "Kediler etcildir.")])
    assert "Kaynak: a.md" in context
    assert "Bölüm: Beslenme" in context
    assert "Kediler etcildir." in context


def test_multiple_passages_are_separated():
    context = format_context([_hit("a.md", "", "birinci"), _hit("b.md", "", "ikinci")])
    assert "---" in context
    assert "[1]" in context and "[2]" in context


def test_messages_put_context_before_the_question():
    messages = build_messages("Kediler ne yer?", [_hit("a.md", "", "Kediler etcildir.")])
    assert [m["role"] for m in messages] == ["system", "user"]
    user = messages[1]["content"]
    assert user.index("BAĞLAM:") < user.index("SORU:")
    assert "Kediler ne yer?" in user


# -- hashing backend -----------------------------------------------------


def test_embeddings_are_deterministic():
    assert embed_one("aynı metin") == embed_one("aynı metin")


def test_embeddings_are_unit_length():
    vector = np.asarray(embed_one("herhangi bir metin"), dtype=np.float32)
    assert float(np.linalg.norm(vector)) == 1.0 or np.isclose(np.linalg.norm(vector), 1.0)


def test_similar_text_scores_higher_than_unrelated():
    query = np.asarray(embed_one("kediler ne yer"), dtype=np.float32)
    close = np.asarray(embed_one("kediler et yer ve taurin gerekir"), dtype=np.float32)
    far = np.asarray(embed_one("filtre kahve suyu doksan derece"), dtype=np.float32)
    assert float(np.dot(query, close)) > float(np.dot(query, far))


def test_turkish_dotted_i_folds_consistently():
    assert tokenize("İSTANBUL") == tokenize("istanbul")


def test_empty_text_yields_zero_vector_without_crashing():
    assert len(embed_one("")) == HashingBackend().embedding_dim


def test_batch_embed_preserves_order_and_count():
    backend = HashingBackend()
    vectors = backend.embed(["bir", "iki", "uc"])
    assert len(vectors) == 3
    assert vectors[0] == backend.embed(["bir"])[0]


def test_embed_of_empty_batch():
    assert HashingBackend().embed([]) == []


def test_chat_without_context_refuses():
    backend = HashingBackend()
    messages = [{"role": "system", "content": "x"}, {"role": "user", "content": "SORU: nedir?"}]
    assert "belgelerde yok" in backend.chat(messages)


def test_chat_quotes_the_relevant_sentence():
    backend = HashingBackend()
    hits = [
        _hit("kediler.md", "Beslenme", "Kediler zorunlu etcildir ve taurin ihtiyaci duyarlar."),
        _hit("kahve.md", "Demleme", "Filtre kahve icin su sicakligi doksan iki derecedir."),
    ]
    answer = backend.chat(build_messages("Kediler neye ihtiyac duyar?", hits))
    assert "taurin" in answer
    assert "kediler.md" in answer


def test_chat_does_not_quote_the_source_header():
    """The '[1] Kaynak: ...' line is metadata, not an answer."""
    backend = HashingBackend()
    hits = [_hit("kediler.md", "Beslenme", "Kediler zorunlu etcildir ve taurin ihtiyaci duyarlar.")]
    answer = backend.chat(build_messages("Kediler neye ihtiyac duyar?", hits))
    assert "Kaynak:" not in answer
    assert "Bölüm:" not in answer


def test_signature_identifies_the_vector_space():
    assert HashingBackend().embedding_signature() == "hashing-offline:512"
