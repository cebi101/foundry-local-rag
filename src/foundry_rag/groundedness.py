"""Verify that a generated answer is actually supported by the retrieved context.

The gap this closes
-------------------
Retrieval quality and answer quality are different things. A RAG system can
retrieve the right passage and *still* produce a sentence that is not in it --
the model fills a gap, smooths a transition, or blends in something it
remembers from pre-training. The user cannot tell the difference: a fabricated
sentence reads exactly like a grounded one, and the citation next to it makes
it look more trustworthy, not less.

So we check afterwards. Every sentence of the answer is scored against the
passages that were actually retrieved, and sentences with no support are
flagged. The output is a percentage plus a per-sentence verdict, which turns
"trust the model" into "here is the evidence, judge for yourself".

How support is measured
-----------------------
Content-word overlap, weighted by inverse document frequency, with Turkish
morphology folded in via :mod:`foundry_rag.turkish`:

* Rare words carry the weight. If a sentence says "1536 bayt" and the context
  says "1536 bayt", that is strong evidence. Sharing "ve" and "bir" is not.
* Function words are ignored entirely -- they appear everywhere and would let
  any fluent sentence look supported.
* Matching is on expanded tokens, so "belgelerden" in the answer counts as
  support from "belge" in the context.

Deliberately *not* natural language inference. A real NLI model would catch
contradictions and paraphrase that share no words, which this cannot. But it
would also mean a second model download, a second inference pass per sentence,
and a dependency the offline fallback cannot satisfy. Lexical entailment is the
honest 80% here: it reliably catches the failure that actually matters --
**the model asserting something the context never mentioned**.

The score is a *signal*, not a verdict. A low score means "look at this",
not "this is false".
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

from .retrieval import SearchHit
from .turkish import expand_tokens

#: Turkish function words. Frequent, contentless, and present in every sentence.
STOPWORDS = frozenset(
    """
    ve veya ile ama fakat ancak lakin çünkü zira eğer ise ki de da ne
    bir bu şu o bunlar şunlar onlar için gibi kadar sonra önce daha
    en çok az hem her hiç bazı tüm bütün olarak olan olur oldu olduğu
    var yok değil mi mı mu mü ya yani ayrıca ise iken üzere göre
    şey kez defa yine yeni artık henüz zaten sadece yalnız
    """.split()
)

#: below this, a sentence is reported as unsupported
SUPPORT_THRESHOLD = 0.45

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")
#: markdown noise and bracketed citations are not claims
_CITATION = re.compile(r"\[[^\]]*\]")
_MARKDOWN = re.compile(r"[*_`#>]+")


@dataclass(frozen=True)
class SentenceVerdict:
    """Support assessment for one sentence of the answer."""

    text: str
    score: float
    supported: bool
    best_source: str = ""

    @property
    def label(self) -> str:
        return "dayanakli" if self.supported else "DAYANAKSIZ"


@dataclass
class GroundednessReport:
    """Whole-answer verdict."""

    score: float
    sentences: list[SentenceVerdict] = field(default_factory=list)

    @property
    def unsupported(self) -> list[SentenceVerdict]:
        return [s for s in self.sentences if not s.supported]

    @property
    def is_clean(self) -> bool:
        return not self.unsupported

    def summary(self) -> str:
        if not self.sentences:
            return "Denetlenecek cumle yok."
        total = len(self.sentences)
        good = total - len(self.unsupported)
        line = f"Kaynaklilik: %{self.score * 100:.0f} ({good}/{total} cumle dayanakli)"
        if self.unsupported:
            line += f" -- {len(self.unsupported)} cumle bağlamda doğrulanamadı"
        return line


def split_sentences(text: str) -> list[str]:
    """Split an answer into checkable sentences, dropping markup and citations."""
    cleaned = _MARKDOWN.sub("", _CITATION.sub("", text))
    parts = [p.strip(" -•\t") for p in _SENTENCE_SPLIT.split(cleaned)]
    # very short fragments carry no checkable claim ("Evet.", "Ozet:")
    return [p for p in parts if len(p) >= 25]


def _content_terms(text: str) -> Counter:
    """Content-bearing tokens only, stopwords and bare numbers-as-noise removed."""
    return Counter(
        token
        for token in expand_tokens(text)
        if token not in STOPWORDS and len(token) > 1
    )


def _build_idf(passages: Sequence[str]) -> dict[str, float]:
    """IDF over the retrieved passages, so common-in-context words weigh less."""
    count = len(passages) or 1
    document_frequency: Counter = Counter()
    for passage in passages:
        document_frequency.update(set(_content_terms(passage)))
    return {
        term: math.log(1.0 + count / (frequency + 0.5))
        for term, frequency in document_frequency.items()
    }


def support_score(sentence: str, passage: str, idf: dict[str, float]) -> float:
    """Fraction of the sentence's information weight that the passage covers.

    Weighted recall of the *sentence's* terms, not symmetric overlap: we are
    asking "is everything this sentence claims present in the passage?", so a
    long passage containing extra material must not be penalised.
    """
    sentence_terms = _content_terms(sentence)
    if not sentence_terms:
        return 0.0
    passage_terms = _content_terms(passage)

    # unseen terms get the maximum weight -- a word absent from every retrieved
    # passage is exactly the kind of thing a fabrication introduces
    default_weight = max(idf.values(), default=1.0)

    total = 0.0
    covered = 0.0
    for term, frequency in sentence_terms.items():
        weight = idf.get(term, default_weight) * min(frequency, 2)
        total += weight
        if term in passage_terms:
            covered += weight
    return covered / total if total else 0.0


def check(
    answer: str,
    hits: Sequence[SearchHit],
    threshold: float = SUPPORT_THRESHOLD,
) -> GroundednessReport:
    """Score how well ``answer`` is supported by the passages in ``hits``."""
    sentences = split_sentences(answer)
    if not sentences:
        return GroundednessReport(score=1.0, sentences=[])

    if not hits:
        # An answer with no retrieved context cannot be grounded in anything.
        return GroundednessReport(
            score=0.0,
            sentences=[SentenceVerdict(s, 0.0, False) for s in sentences],
        )

    passages = [f"{h.record.heading}\n{h.record.content}" for h in hits]
    idf = _build_idf(passages)

    verdicts: list[SentenceVerdict] = []
    for sentence in sentences:
        best_score = 0.0
        best_source = ""
        for hit, passage in zip(hits, passages):
            score = support_score(sentence, passage, idf)
            if score > best_score:
                best_score, best_source = score, hit.record.source
        verdicts.append(
            SentenceVerdict(
                text=sentence,
                score=best_score,
                supported=best_score >= threshold,
                best_source=best_source,
            )
        )

    supported = sum(1 for v in verdicts if v.supported)
    return GroundednessReport(score=supported / len(verdicts), sentences=verdicts)
