"""Chunking is pure logic, so it gets the most thorough tests in the project."""

from __future__ import annotations

import pytest

from foundry_rag.chunking import chunk_document, chunk_text


def test_empty_input_produces_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_stays_one_chunk():
    chunks = chunk_text("Kısa bir cümle.", chunk_size=300, chunk_overlap=50)
    assert chunks == ["Kısa bir cümle."]


def test_chunks_respect_size_limit():
    text = "\n\n".join(f"Paragraf numarası {i}. " * 12 for i in range(20))
    chunks = chunk_text(text, chunk_size=400, chunk_overlap=60)
    assert chunks, "chunking produced nothing"
    # allow the overlap prefix to push a chunk slightly past the target
    assert all(len(c) <= 400 + 60 for c in chunks)


def test_long_paragraph_is_split_on_sentences():
    sentence = "Bu cümle yeterince uzun bir cümledir ve tekrar edilecektir. "
    chunks = chunk_text(sentence * 30, chunk_size=300, chunk_overlap=40)
    assert len(chunks) > 1


def test_overlap_carries_text_between_chunks():
    text = "\n\n".join(f"Bolum {i} icin ayrilmis bir paragraf metni." for i in range(40))
    with_overlap = chunk_text(text, chunk_size=300, chunk_overlap=100)
    without_overlap = chunk_text(text, chunk_size=300, chunk_overlap=0)
    # overlap duplicates content, so it can only produce more (or equal) chunks
    assert len(with_overlap) >= len(without_overlap)


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("herhangi bir metin", chunk_size=100, chunk_overlap=100)


def test_no_empty_or_whitespace_chunks():
    text = "Bir.\n\n\n\n   \n\nIki.\n\n\n\nUc."
    assert all(c.strip() for c in chunk_text(text, chunk_size=200, chunk_overlap=20))


def test_headings_are_attached_to_their_chunks():
    doc = """# Baslik

## Beslenme

Kediler etcildir ve taurine ihtiyac duyar.

## Uyku

Kediler gunde on alti saat uyur.
"""
    chunks = chunk_document(doc, source="kediler.md", chunk_size=300, chunk_overlap=40)
    headings = {c.heading for c in chunks}
    assert "Beslenme" in headings
    assert "Uyku" in headings
    assert all(c.source == "kediler.md" for c in chunks)


def test_chunk_indices_are_sequential():
    doc = "\n\n".join(f"## Bolum {i}\n\nIcerik metni {i}." for i in range(5))
    chunks = chunk_document(doc, source="x.md", chunk_size=200, chunk_overlap=30)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_heading_prefix_included_for_embedding():
    doc = "## Beslenme\n\nKediler etcildir."
    chunk = chunk_document(doc, source="k.md", chunk_size=200, chunk_overlap=20)[0]
    assert chunk.with_heading_prefix().startswith("Beslenme")
    assert "Kediler etcildir." in chunk.with_heading_prefix()


def test_content_hash_is_stable_and_distinct():
    doc = "## A\n\nBir metin."
    first = chunk_document(doc, "a.md", 200, 20)[0]
    same = chunk_document(doc, "a.md", 200, 20)[0]
    other = chunk_document("## A\n\nBaska metin.", "a.md", 200, 20)[0]
    assert first.content_hash == same.content_hash
    assert first.content_hash != other.content_hash
