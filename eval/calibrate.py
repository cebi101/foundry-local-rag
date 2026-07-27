"""Choose the retrieval thresholds from data instead of guessing them.

    python eval/calibrate.py                    # sweep and recommend
    python eval/calibrate.py --backend hashing  # force the offline backend

The problem this solves
-----------------------
``min_similarity`` decides when the assistant answers and when it says "I don't
know". Set it too low and it answers questions it cannot know (hallucination).
Set it too high and it refuses questions it *can* answer. There is no correct
value in the abstract -- it depends on the corpus, the embedding model and the
retriever.

Guessing produces exactly the failure this project hit: ``0.15`` was tuned for
dense-only cosine scores, and adding BM25 changed the score distribution
underneath it. Recall jumped from 72% to 96% while refusal accuracy collapsed
from 87.5% to 12.5% -- the same threshold now meant something different.

So: sweep the thresholds over the evaluation set, look at the whole trade-off
curve, and pick a point deliberately. Retrieval costs no LLM call, so the full
grid runs in seconds.

Reported metrics
----------------
``recall``     share of answerable questions whose correct source is retrieved
``refusal``    share of unanswerable questions correctly declined
``overall``    share of all questions handled correctly
``balanced``   harmonic mean of recall and refusal -- the honest single number,
               because it collapses if either side is sacrificed
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from foundry_rag import RagPipeline, Settings  # noqa: E402
from foundry_rag.retrieval import hybrid_search  # noqa: E402

QUESTIONS_PATH = Path(__file__).parent / "questions.json"

DEFAULT_SIMILARITY_GRID = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]
DEFAULT_LEXICAL_GRID = [2.0, 4.0, 8.0, 16.0, 32.0, 64.0]


@dataclass
class Point:
    """One grid position and the quality it produced."""

    min_similarity: float
    lexical_scale: float
    recall: float
    refusal: float
    overall: float

    @property
    def balanced(self) -> float:
        """Harmonic mean of recall and refusal accuracy.

        Chosen over the plain average on purpose: an arithmetic mean lets a
        system score 50% by answering everything and refusing nothing. The
        harmonic mean goes to zero if either side does.
        """
        if self.recall + self.refusal == 0:
            return 0.0
        return 2 * self.recall * self.refusal / (self.recall + self.refusal)


def evaluate_grid_point(
    pipeline: RagPipeline,
    items: list[dict],
    query_vectors: dict[str, list[float]],
    min_similarity: float,
    lexical_scale: float,
) -> Point:
    """Score one (threshold, scale) pair. Embeddings are reused, not recomputed."""
    answerable = hits = refused_ok = correct = 0
    unanswerable = 0

    for item in items:
        expected = item.get("expected_source")
        found = hybrid_search(
            pipeline.records,
            pipeline.matrix,
            query_vectors[item["id"]],
            query_text=item["question"],
            bm25=pipeline.bm25,
            top_k=pipeline.settings.top_k,
            min_similarity=min_similarity,
            lexical_scale=lexical_scale,
        )
        sources = [h.record.source for h in found]

        if expected is not None:
            answerable += 1
            if expected in sources:
                hits += 1
                correct += 1
        else:
            unanswerable += 1
            if not found:
                refused_ok += 1
                correct += 1

    total = answerable + unanswerable
    return Point(
        min_similarity=min_similarity,
        lexical_scale=lexical_scale,
        recall=hits / answerable if answerable else 0.0,
        refusal=refused_ok / unanswerable if unanswerable else 0.0,
        overall=correct / total if total else 0.0,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Getirme esiklerini veriden kalibre et")
    parser.add_argument("--backend", choices=["auto", "foundry", "hashing"])
    parser.add_argument("--top-k", type=int, dest="top_k")
    parser.add_argument(
        "--objective",
        choices=["balanced", "overall", "recall"],
        default="balanced",
        help="Hangi metrige gore en iyi nokta secilsin (varsayilan: balanced)",
    )
    parser.add_argument(
        "--no-lexical-sweep",
        action="store_true",
        help="lexical_scale'i sabit tut, sadece min_similarity tara",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    for name in ("backend", "top_k"):
        if getattr(args, name, None) is not None:
            setattr(settings, name, getattr(args, name))
    settings.hybrid = True
    settings.validate()

    items = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
    lexical_grid = [settings.lexical_scale] if args.no_lexical_sweep else DEFAULT_LEXICAL_GRID

    print(f"{len(items)} soru, {len(DEFAULT_SIMILARITY_GRID)}x{len(lexical_grid)} nokta taraniyor...\n")

    with RagPipeline(settings, verbose=True) as pipeline:
        print(f"Backend: {pipeline.backend.describe()}")
        print(f"Indeks : {len(pipeline.records)} parca\n")

        # Embed every question ONCE. This is the only expensive part, and it
        # does not depend on the thresholds being swept.
        query_vectors = {
            item["id"]: pipeline.backend.embed([item["question"]])[0] for item in items
        }

        points = [
            evaluate_grid_point(pipeline, items, query_vectors, similarity, scale)
            for scale in lexical_grid
            for similarity in DEFAULT_SIMILARITY_GRID
        ]

    print("=" * 78)
    print(f"{'lex_scale':>10}{'min_sim':>10}{'recall':>10}{'reddetme':>11}{'genel':>9}{'dengeli':>10}")
    print("-" * 78)
    best = max(points, key=lambda p: getattr(p, args.objective))
    for point in points:
        marker = "  <== EN IYI" if point is best else ""
        print(
            f"{point.lexical_scale:>10.1f}{point.min_similarity:>10.2f}"
            f"{point.recall:>10.1%}{point.refusal:>11.1%}"
            f"{point.overall:>9.1%}{point.balanced:>10.1%}{marker}"
        )

    print("=" * 78)
    print(f"\nEn iyi nokta ({args.objective} metrigine gore):")
    print(f"  FRAG_MIN_SIMILARITY={best.min_similarity}")
    print(f"  FRAG_LEXICAL_SCALE={best.lexical_scale}")
    print(
        f"\n  recall {best.recall:.1%} | reddetme {best.refusal:.1%} | "
        f"genel {best.overall:.1%} | dengeli {best.balanced:.1%}"
    )
    print(
        "\nBu degerleri src/foundry_rag/config.py'daki varsayilanlara yaz ya da\n"
        ".env dosyasina koy. Bilgi tabani degistiginde yeniden kalibre et."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
