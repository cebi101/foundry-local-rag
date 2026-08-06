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

Second failure: degeneration reads as grounded
----------------------------------------------
Support alone is not enough, and the reason is structural. Because support is
lexical overlap, a model stuck in a repetition loop *gains* score -- the words
it keeps echoing came from the context, so every repeated clause looks
supported. Observed with ``qwen2.5-0.5b``: an answer that had collapsed into
meaningless repeated Turkish scored **42%**, above the 0.34 fallback threshold,
so the circuit breaker let it through to the user.

Fabrication and degeneration are different failures and need different signals,
so :func:`is_degenerate` measures repetition *from the answer alone* -- distinct
bigram ratio plus verbatim sentence repeats. A report now carries both verdicts
and the pipeline falls back to quoting when either one fires.

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

#: Distinct-bigram floor. Below this an answer is treated as degenerate.
#:
#: Not a guess. Measured on real ``qwen2.5-0.5b`` output over the evaluation
#: questions: ten generated answers spanned 0.405-1.000, while the extractive
#: answers quoting the same retrieved passages never fell below 0.776, and the
#: degenerate sample that motivated this check scored 0.717. 0.75 is the gap
#: between the worst healthy value and the best degenerate one. Re-measure if
#: the chat model changes -- a fluent model's floor sits higher.
DEGENERACY_THRESHOLD = 0.75

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
    #: the answer collapsed into repetition -- see :func:`is_degenerate`
    degenerate: bool = False

    @property
    def unsupported(self) -> list[SentenceVerdict]:
        return [s for s in self.sentences if not s.supported]

    @property
    def is_clean(self) -> bool:
        return not self.unsupported and not self.degenerate

    @property
    def trustworthy(self) -> bool:
        """Cheap single question for callers: can this answer be shown as-is?

        Kept separate from :attr:`score` because the two failures are
        independent -- a degenerate answer can score *well* on support.
        """
        return not self.degenerate

    def summary(self) -> str:
        if not self.sentences:
            return "Denetlenecek cumle yok."
        total = len(self.sentences)
        good = total - len(self.unsupported)
        line = f"Kaynaklilik: %{self.score * 100:.0f} ({good}/{total} cumle dayanakli)"
        if self.unsupported:
            line += f" -- {len(self.unsupported)} cumle bağlamda doğrulanamadı"
        if self.degenerate:
            line += " -- [!] cevap kendini tekrar ediyor (dejenere)"
        return line


def split_sentences(text: str) -> list[str]:
    """Split an answer into checkable sentences, dropping markup and citations."""
    cleaned = _MARKDOWN.sub("", _CITATION.sub("", text))
    parts = [p.strip(" -•\t") for p in _SENTENCE_SPLIT.split(cleaned)]
    # very short fragments carry no checkable claim ("Evet.", "Ozet:")
    return [p for p in parts if len(p) >= 25]


def distinct_bigram_ratio(text: str) -> float:
    """Share of word bigrams that are unique. 1.0 = no phrase ever repeats.

    Deliberately independent of the retrieved context. That independence is the
    whole point: support is measured *against* the passages, so a model looping
    on words taken from those passages scores well on support while saying
    nothing. Repetition has to be judged from the answer alone.
    """
    words = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    if len(words) < 2:
        return 1.0
    bigrams = [(words[i], words[i + 1]) for i in range(len(words) - 1)]
    return len(set(bigrams)) / len(bigrams)


def repeated_sentence(text: str) -> str:
    """A sentence the answer states more than once verbatim, or ``""``.

    Exact repetition needs no threshold: a model that emits the same sentence
    twice in one short answer has stopped making progress. This catches the
    tight loops that a whole-text ratio can dilute when the answer is long.
    """
    seen: set[str] = set()
    for sentence in split_sentences(text):
        key = " ".join(sentence.lower().split())
        if key in seen:
            return sentence
        seen.add(key)
    return ""


def is_degenerate(text: str) -> bool:
    """Has the answer collapsed into repetition rather than said something?"""
    return (
        distinct_bigram_ratio(text) < DEGENERACY_THRESHOLD
        or bool(repeated_sentence(text))
    )


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

    degenerate = is_degenerate(answer)

    if not hits:
        # An answer with no retrieved context cannot be grounded in anything.
        return GroundednessReport(
            score=0.0,
            sentences=[SentenceVerdict(s, 0.0, False) for s in sentences],
            degenerate=degenerate,
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
    return GroundednessReport(
        score=supported / len(verdicts), sentences=verdicts, degenerate=degenerate
    )
