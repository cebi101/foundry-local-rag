"""Measure the assistant against a fixed question set.

    python eval/evaluate.py                       # retrieval only (fast, no LLM)
    python eval/evaluate.py --generate            # also generate answers
    python eval/evaluate.py --backend hashing     # force the offline backend

Two things are scored separately, because they fail for different reasons:

**Retrieval** -- did the right document come back?
    * ``Recall@K``  : share of questions whose expected source is in the top K
    * ``MRR``       : 1/rank of the expected source, averaged. Rewards ranking
                      the right document *first*, not merely somewhere in K.

**Refusal** -- for questions with no answer in the corpus, did the system say
so instead of inventing something? A high answer-accuracy score means nothing
if the system also confidently answers questions it cannot know.

Results are appended to ``eval/results.jsonl`` so runs can be compared. Without
that history there is no way to tell whether a prompt tweak helped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from foundry_rag import RagPipeline, Settings  # noqa: E402
from foundry_rag.prompts import NO_CONTEXT_ANSWER  # noqa: E402

QUESTIONS_PATH = Path(__file__).parent / "questions.json"
RESULTS_PATH = Path(__file__).parent / "results.jsonl"

REFUSAL_MARKERS = (
    NO_CONTEXT_ANSWER.lower(),
    "belgelerde yok",
    "bilmiyorum",
    "bilgi bulunmuyor",
    "yeterli bilgi yok",
)


@dataclass
class QuestionResult:
    id: str
    question: str
    answerable: bool
    expected_source: str | None
    retrieved_sources: list[str] = field(default_factory=list)
    top_score: float = 0.0
    rank: int | None = None          # 1-based position of the expected source
    hit: bool = False                # expected source present in top-k
    refused: bool = False            # system declined to answer
    correct: bool = False            # overall verdict for this question
    keywords_found: list[str] = field(default_factory=list)
    answer: str = ""
    seconds: float = 0.0


def is_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def evaluate_one(pipeline: RagPipeline, item: dict, generate: bool) -> QuestionResult:
    expected = item.get("expected_source")
    result = QuestionResult(
        id=item["id"],
        question=item["question"],
        answerable=expected is not None,
        expected_source=expected,
    )

    started = time.perf_counter()
    if generate:
        answer = pipeline.answer(item["question"])
        hits, result.answer = answer.hits, answer.text
    else:
        hits, _ = pipeline.retrieve(item["question"])
    result.seconds = time.perf_counter() - started

    result.retrieved_sources = [h.record.source for h in hits]
    result.top_score = float(hits[0].score) if hits else 0.0

    if result.answerable:
        for position, source in enumerate(result.retrieved_sources, start=1):
            if source == expected:
                result.rank, result.hit = position, True
                break
        if generate:
            found = [
                kw
                for kw in item.get("expected_keywords", [])
                if kw.lower() in result.answer.lower()
            ]
            result.keywords_found = found
            result.refused = is_refusal(result.answer)
            # answerable question: right source retrieved AND not refused
            result.correct = result.hit and not result.refused
        else:
            result.correct = result.hit
    else:
        # unanswerable: correct means nothing retrieved, or an explicit refusal
        result.refused = (not hits) or (generate and is_refusal(result.answer))
        result.correct = result.refused

    return result


def summarize(results: list[QuestionResult], generate: bool) -> dict:
    answerable = [r for r in results if r.answerable]
    unanswerable = [r for r in results if not r.answerable]

    recall = sum(r.hit for r in answerable) / len(answerable) if answerable else 0.0
    mrr = (
        sum(1.0 / r.rank for r in answerable if r.rank) / len(answerable)
        if answerable
        else 0.0
    )
    refusal_accuracy = (
        sum(r.refused for r in unanswerable) / len(unanswerable) if unanswerable else 0.0
    )
    overall = sum(r.correct for r in results) / len(results) if results else 0.0
    avg_seconds = sum(r.seconds for r in results) / len(results) if results else 0.0

    summary = {
        "questions": len(results),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "recall_at_k": round(recall, 3),
        "mrr": round(mrr, 3),
        "refusal_accuracy": round(refusal_accuracy, 3),
        "overall_accuracy": round(overall, 3),
        "avg_seconds": round(avg_seconds, 3),
        "generated_answers": generate,
    }
    if generate:
        with_keywords = [r for r in answerable if r.keywords_found]
        summary["answers_with_expected_keywords"] = (
            round(len(with_keywords) / len(answerable), 3) if answerable else 0.0
        )
    return summary


def print_report(results: list[QuestionResult], summary: dict, settings: Settings) -> None:
    print("\n" + "=" * 78)
    print("  SORU BAZLI SONUCLAR")
    print("=" * 78)
    print(f"{'id':<6}{'durum':<8}{'beklenen':<34}{'sira':<6}{'skor':<8}sure")
    print("-" * 78)
    for r in results:
        mark = "OK " if r.correct else "HATA"
        expected = r.expected_source or "(cevaplanamaz)"
        rank = str(r.rank) if r.rank else "-"
        print(
            f"{r.id:<6}{mark:<8}{expected:<34}{rank:<6}"
            f"{r.top_score:<8.3f}{r.seconds:.2f}s"
        )

    failures = [r for r in results if not r.correct]
    if failures:
        print("\n" + "-" * 78)
        print("  BASARISIZ SORULAR")
        print("-" * 78)
        for r in failures:
            print(f"\n[{r.id}] {r.question}")
            print(f"  beklenen : {r.expected_source or '(cevap vermemeliydi)'}")
            print(f"  getirilen: {', '.join(r.retrieved_sources) or '(hicbir sey)'}")
            if r.answer:
                print(f"  cevap    : {r.answer[:160].replace(chr(10), ' ')}")

    print("\n" + "=" * 78)
    print("  OZET")
    print("=" * 78)
    print(f"  backend           : {settings.backend}")
    print(f"  top_k             : {settings.top_k}")
    print(f"  min_similarity    : {settings.min_similarity}")
    print(f"  chunk_size        : {settings.chunk_size} / overlap {settings.chunk_overlap}")
    print("-" * 78)
    print(f"  soru sayisi       : {summary['questions']} "
          f"({summary['answerable']} cevaplanabilir, "
          f"{summary['unanswerable']} cevaplanamaz)")
    print(f"  Recall@{settings.top_k}          : {summary['recall_at_k']:.1%}")
    print(f"  MRR               : {summary['mrr']:.3f}")
    print(f"  Reddetme dogrulugu: {summary['refusal_accuracy']:.1%}")
    print(f"  Genel dogruluk    : {summary['overall_accuracy']:.1%}")
    print(f"  Ortalama sure     : {summary['avg_seconds']:.2f} sn")
    if "answers_with_expected_keywords" in summary:
        print(f"  Anahtar kelime    : {summary['answers_with_expected_keywords']:.1%}")
    print("=" * 78)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG degerlendirme seti")
    parser.add_argument("--backend", choices=["auto", "foundry", "hashing"])
    parser.add_argument("--top-k", type=int, dest="top_k")
    parser.add_argument("--min-similarity", type=float, dest="min_similarity")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Cevaplari da uret (yavas). Varsayilan: sadece getirme olculur.",
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Sonuclari results.jsonl'e yazma"
    )
    args = parser.parse_args(argv)

    payload = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    items = payload["questions"]

    settings = Settings.from_env()
    for name in ("backend", "top_k", "min_similarity"):
        if getattr(args, name, None) is not None:
            setattr(settings, name, getattr(args, name))
    settings.validate()

    print(f"{len(items)} soru degerlendiriliyor (backend={settings.backend}, "
          f"uretim={'acik' if args.generate else 'kapali'})...")

    with RagPipeline(settings, verbose=True) as pipeline:
        print(f"Backend: {pipeline.backend.describe()}\n")
        results = []
        for i, item in enumerate(items, start=1):
            results.append(evaluate_one(pipeline, item, args.generate))
            print(f"\r  {i}/{len(items)}", end="", flush=True)
        print()

    summary = summarize(results, args.generate)
    print_report(results, summary, settings)

    if not args.no_save:
        record = {
            "summary": summary,
            "settings": {
                "backend": settings.backend,
                "top_k": settings.top_k,
                "min_similarity": settings.min_similarity,
                "chunk_size": settings.chunk_size,
                "chunk_overlap": settings.chunk_overlap,
                "chat_model": settings.chat_model,
                "embedding_model": settings.embedding_model,
            },
            "results": [asdict(r) for r in results],
        }
        with RESULTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"\nSonuclar eklendi: {RESULTS_PATH}")

    return 0 if summary["overall_accuracy"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
