"""Command-line interface for the local RAG assistant.

    python -m app.cli ingest              # build the index from data/docs
    python -m app.cli ask "RAG nedir?"    # single question
    python -m app.cli chat                # interactive loop
    python -m app.cli info                # what is in the index right now
"""

from __future__ import annotations

import argparse
import sys

from . import _bootstrap  # noqa: F401  (side effect: puts src/ on sys.path)

from foundry_rag import RagPipeline, Settings, VectorStore, ingest
from foundry_rag.backends import BackendError, BackendUnavailable, create_backend

BANNER = """
  Yerel RAG Asistani  --  Microsoft Foundry Local
  Belgelerinden cevap uretir, internete cikmaz.
"""


def _settings_from_args(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env()
    for name in ("backend", "top_k", "chunk_size", "chunk_overlap", "min_similarity"):
        value = getattr(args, name, None)
        if value is not None:
            setattr(settings, name, value)
    settings.validate()
    return settings


def _print_sources(answer) -> None:
    if not answer.hits:
        return
    print("\nKaynaklar:")
    for i, hit in enumerate(answer.hits, start=1):
        print(f"  [{i}] {hit.record.citation}  (benzerlik: {hit.score:.3f})")
    print(
        f"\n  getirme: {answer.retrieval_seconds * 1000:.0f} ms | "
        f"uretim: {answer.generation_seconds:.2f} sn"
    )


# -- commands ------------------------------------------------------------


def cmd_ingest(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    print(BANNER)
    print(f"Belge klasoru : {settings.docs_dir}")
    print(f"Veritabani    : {settings.db_path}")
    print(f"Parca boyutu  : {settings.chunk_size} (ortusme {settings.chunk_overlap})\n")

    backend = create_backend(settings, verbose=True)
    print(f"Backend: {backend.describe()}\n")

    report = ingest(settings, backend=backend, reset=not args.append, verbose=True)
    print("\n" + report.summary())
    print(f"\nHazir. Soru sormak icin: python -m app.cli chat")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    with RagPipeline(settings, verbose=args.verbose) as rag:
        answer = rag.answer(" ".join(args.question))
        print(f"\n{answer.text}")
        if args.show_sources:
            _print_sources(answer)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    print(BANNER)
    with RagPipeline(settings, verbose=True) as rag:
        print(f"Backend  : {rag.backend.describe()}")
        print(f"Indeks   : {rag.store.count()} parca / {len(rag.store.sources())} belge")
        print("Cikmak icin 'q' veya Ctrl-C.\n")

        while True:
            try:
                question = input("Soru> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not question:
                continue
            if question.lower() in {"q", "quit", "exit", "cik"}:
                break

            print("\nCevap: ", end="", flush=True)
            try:
                for fragment in rag.stream_answer(question):
                    print(fragment, end="", flush=True)
                print()
            except BackendError as exc:
                print(f"\n[hata] {exc}")
                continue

            if args.show_sources:
                hits, _ = rag.retrieve(question)
                if hits:
                    print("\nKaynaklar:")
                    for i, hit in enumerate(hits, start=1):
                        print(f"  [{i}] {hit.record.citation}  ({hit.score:.3f})")
            print()
    print("Gorusuruz.")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    if not settings.db_path.exists():
        print(f"Veritabani yok: {settings.db_path}")
        print("Once indeksle: python -m app.cli ingest")
        return 1

    with VectorStore(settings.db_path) as store:
        print(f"Veritabani : {settings.db_path}")
        print(f"Parca      : {store.count()}")
        print(f"Belge      : {len(store.sources())}")
        print("\nMeta:")
        for key in (
            "embedding_signature",
            "backend",
            "chunk_size",
            "chunk_overlap",
            "document_count",
        ):
            print(f"  {key:22s} {store.get_meta(key, '-')}")
        print("\nBelgeler:")
        for source in store.sources():
            print(f"  - {source}")
    return 0


# -- entrypoint ----------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.cli",
        description="Foundry Local ile calisan cevrimdisi RAG asistani",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "foundry", "hashing"],
        help="Model backend'i (varsayilan: auto)",
    )
    parser.add_argument("--top-k", type=int, dest="top_k", help="Getirilecek parca sayisi")
    parser.add_argument(
        "--min-similarity", type=float, dest="min_similarity", help="Benzerlik esigi"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Ayrintili cikti")

    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Belgeleri indeksle")
    p_ingest.add_argument("--chunk-size", type=int, dest="chunk_size")
    p_ingest.add_argument("--chunk-overlap", type=int, dest="chunk_overlap")
    p_ingest.add_argument(
        "--append", action="store_true", help="Mevcut indeksi silme, uzerine ekle"
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="Tek soru sor")
    p_ask.add_argument("question", nargs="+")
    p_ask.add_argument(
        "--no-sources", dest="show_sources", action="store_false", help="Kaynaklari gizle"
    )
    p_ask.set_defaults(func=cmd_ask, show_sources=True)

    p_chat = sub.add_parser("chat", help="Etkilesimli soru-cevap")
    p_chat.add_argument("--no-sources", dest="show_sources", action="store_false")
    p_chat.set_defaults(func=cmd_chat, show_sources=True)

    p_info = sub.add_parser("info", help="Indeks durumunu goster")
    p_info.set_defaults(func=cmd_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (BackendUnavailable, BackendError) as exc:
        print(f"\n[backend hatasi] {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"\n[hata] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
