"""Dependency-free offline backend: hashed bag-of-ngrams + extractive answers.

Why this exists
---------------
Foundry Local needs an install, a model download and a running service. None of
that is available in CI, and it may not be available on a given student's
machine on day one. This backend implements the same :class:`Backend` contract
using nothing but the standard library and numpy, so:

* ``pytest`` runs offline, fast and deterministically
* the app is demonstrable end-to-end before Foundry Local is set up
* students can see the retrieval half working in isolation from the LLM half

What it is *not*: a semantic embedder. It matches on shared words and character
n-grams, so paraphrases match far worse than with a real embedding model. The
generation side is extractive -- it quotes the best-matching sentences rather
than writing prose. Good enough to prove the pipeline, not a substitute for the
real thing.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter
from typing import Sequence

import numpy as np

from .base import Backend

DIM = 512
_TOKEN = re.compile(r"\w+", re.UNICODE)


def _fold_case(text: str) -> str:
    """Lowercase in a way that survives Turkish dotted/dotless I."""
    return text.replace("I", "ı").replace("İ", "i").lower()


def _strip_accents(text: str) -> str:
    """Fold diacritics so 'çalışma' and 'calisma' hash together."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    """Normalised word tokens."""
    return _TOKEN.findall(_strip_accents(_fold_case(text)))


def _features(text: str) -> Counter:
    """Words, word bigrams and intra-word character 4-grams.

    Character n-grams give partial credit for Turkish's agglutinative endings:
    'embedding' and 'embedding'lerin' share most of their character grams.
    """
    tokens = tokenize(text)
    feats: Counter = Counter()

    for token in tokens:
        feats[f"w:{token}"] += 1
        if len(token) > 5:
            for i in range(len(token) - 3):
                feats[f"c:{token[i:i + 4]}"] += 1

    for a, b in zip(tokens, tokens[1:]):
        feats[f"b:{a}_{b}"] += 1

    return feats


def _bucket(feature: str) -> int:
    """Map a feature string to a vector index via a stable hash.

    ``hash()`` is randomised per process in Python 3, which would make vectors
    non-reproducible across runs -- blake2b is not.
    """
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") % DIM


def _sign(feature: str) -> float:
    """Signed hashing: halves the collision bias of plain hashing."""
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=5).digest()
    return 1.0 if digest[-1] & 1 else -1.0


def embed_one(text: str) -> list[float]:
    """Deterministic vector for one text. Same input always gives same output."""
    vector = np.zeros(DIM, dtype=np.float32)
    for feature, count in _features(text).items():
        # sublinear tf: the 10th occurrence of a word should not count 10x
        vector[_bucket(feature)] += _sign(feature) * (1.0 + math.log(count))

    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector /= norm
    return vector.tolist()


def _split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text)]
    return [s for s in parts if len(s) > 20]


class HashingBackend(Backend):
    """Offline stand-in for a real embedding + chat model."""

    name = "hashing-offline"

    @property
    def embedding_dim(self) -> int:
        return DIM

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [embed_one(t) for t in texts]

    def chat(
        self,
        messages: Sequence[dict],
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> str:
        """Extractive 'generation': quote the sentences closest to the question.

        There is no language model here. We pull the question and the context
        back out of the prompt, score every context sentence against the
        question, and return the best ones verbatim.
        """
        user_turn = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        question, context = self._split_prompt(user_turn)
        if not context.strip():
            return "Bu bilgi elimdeki belgelerde yok."

        q_vec = np.asarray(embed_one(question), dtype=np.float32)
        scored = []
        for block in context.split("\n\n---\n\n"):
            source = self._source_of(block)
            for sentence in _split_sentences(self._strip_header(block)):
                score = float(np.dot(q_vec, np.asarray(embed_one(sentence), dtype=np.float32)))
                scored.append((score, sentence, source))

        scored.sort(key=lambda item: item[0], reverse=True)
        picked = [s for s in scored[:3] if s[0] > 0.05]
        if not picked:
            return "Bu bilgi elimdeki belgelerde yok."

        lines = [f"{sentence} [{source}]" for _, sentence, source in picked]
        return (
            "\n".join(lines)
            + "\n\n(Not: Foundry Local kurulu olmadığı için bu cevap bir dil modeli "
            "tarafından yazılmadı; belgelerden doğrudan alıntılandı.)"
        )

    @staticmethod
    def _split_prompt(user_turn: str) -> tuple[str, str]:
        """Recover ``(question, context)`` from the assembled user prompt."""
        question = ""
        match = re.search(r"^SORU:\s*(.+)$", user_turn, re.MULTILINE)
        if match:
            question = match.group(1).strip()

        context = user_turn
        if "BAĞLAM:" in context:
            context = context.split("BAĞLAM:", 1)[1]
        context = re.split(r"\n\s*---\s*\n\s*SORU:", context)[0]
        return question, context

    @staticmethod
    def _strip_header(block: str) -> str:
        """Drop the ``[n] Kaynak: file | Bölüm: heading`` line.

        Without this the header itself scores as a candidate sentence and gets
        quoted back to the user as if it were content.
        """
        lines = block.strip().splitlines()
        if lines and re.match(r"^\s*\[\d+\]\s*Kaynak:", lines[0]):
            lines = lines[1:]
        return "\n".join(lines)

    @staticmethod
    def _source_of(block: str) -> str:
        match = re.search(r"Kaynak:\s*([^\s|]+)", block)
        return match.group(1) if match else "bilinmeyen kaynak"
