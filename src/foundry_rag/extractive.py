"""Answer by quoting the retrieved passages instead of generating prose.

Why a RAG project ships a no-LLM answer path
--------------------------------------------
Measured on this project's own corpus (macOS M-series, Foundry Local 1.2.3):

===========================  ==========================================
prompt                       ``qwen2.5-0.5b`` output
===========================  ==========================================
English system + English Q   coherent and correct
English system + Turkish Q   broken Turkish, one garbled sentence
Turkish system + Turkish Q   incoherent word salad
===========================  ==========================================

The model is fine; Turkish is the problem. A 0.5B model cannot generate
coherent Turkish, and ``qwen3-1.7b`` was worse still. Meanwhile **retrieval on
the same corpus scores 97% overall accuracy**. So the weak link is generation,
not search -- and quoting a passage the system found with 96% recall beats
paraphrasing it with a model that produces word salad.

This module picks the sentences that actually answer the question and returns
them verbatim with their sources. Nothing is invented, because nothing is
written: every sentence is copied from a real document. That is a worse reading
experience than good prose and a much better one than fluent nonsense.

Used two ways:

* as the whole answer for :class:`~foundry_rag.backends.hashing.HashingBackend`,
  which has no language model at all
* as the **circuit breaker** for generated answers -- when
  :mod:`foundry_rag.groundedness` reports that a generated answer is not
  supported by its own context, the pipeline falls back here rather than
  showing the user something it has already measured to be untrustworthy
"""

from __future__ import annotations

import re
from typing import Sequence

import numpy as np

from .groundedness import STOPWORDS
from .retrieval import SearchHit
from .turkish import expand_tokens

#: sentences shorter than this carry no answer
MIN_SENTENCE_LENGTH = 30
#: below this overlap a sentence is not about the question at all
MIN_RELEVANCE = 0.08

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n{2,}")

FALLBACK_NOTICE = (
    "\n\n(Not: Üretilen cevap getirilen belgelerde doğrulanamadığı için "
    "belgelerden doğrudan alıntı yapıldı.)"
)

NO_ANSWER = "Bu bilgi elimdeki belgelerde yok."


def _content_terms(text: str) -> set[str]:
    return {
        token
        for token in expand_tokens(text)
        if token not in STOPWORDS and len(token) > 1
    }


def split_sentences(text: str) -> list[str]:
    parts = [p.strip(" -•\t*") for p in _SENTENCE_SPLIT.split(text)]
    return [p for p in parts if len(p) >= MIN_SENTENCE_LENGTH]


def score_sentence(question_terms: set[str], sentence: str) -> float:
    """Share of the question's content words the sentence covers."""
    if not question_terms:
        return 0.0
    return len(question_terms & _content_terms(sentence)) / len(question_terms)


def extract_answer(
    question: str,
    hits: Sequence[SearchHit],
    max_sentences: int = 3,
    notice: str = "",
) -> str:
    """Quote the sentences from ``hits`` that best answer ``question``."""
    if not hits:
        return NO_ANSWER

    question_terms = _content_terms(question)
    scored: list[tuple[float, str, str]] = []

    for rank, hit in enumerate(hits):
        # A sentence inherits its chunk's standing. Retrieval already decided
        # which passage answers the question; word overlap alone would let a
        # loosely-related sentence from a weak chunk outrank the real answer.
        chunk_weight = 1.0 / (1.0 + rank)
        for sentence in split_sentences(hit.record.content):
            relevance = score_sentence(question_terms, sentence)
            if relevance >= MIN_RELEVANCE:
                scored.append(
                    (relevance * (0.5 + 0.5 * chunk_weight), sentence, hit.record.source)
                )

    if not scored:
        return NO_ANSWER

    scored.sort(key=lambda item: item[0], reverse=True)

    picked: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, sentence, source in scored:
        if len(picked) >= max_sentences:
            break
        if sentence in seen:  # the same sentence can appear in overlapping chunks
            continue
        seen.add(sentence)
        picked.append((sentence, source))

    lines = [f"{sentence} [{source}]" for sentence, source in picked]
    return "\n".join(lines) + notice
