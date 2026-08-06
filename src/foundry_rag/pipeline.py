"""The two flows that make up the application: ingestion and question answering.

**Ingestion** is slow and runs rarely -- read documents, chunk them, embed every
chunk, write to SQLite. **Querying** is fast and runs constantly -- embed one
question, search, build a prompt, call the model.

Keeping them apart is what stops the app from re-embedding the whole corpus on
every startup.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from . import extractive, groundedness
from .backends import Backend, create_backend
from .chunking import Chunk, chunk_document
from .config import Settings
from .groundedness import GroundednessReport
from .lexical import BM25Index
from .prompts import NO_CONTEXT_ANSWER, build_messages
from .retrieval import SearchHit, hybrid_search
from .store import VectorStore

#: how many chunks to embed per model call
EMBED_BATCH_SIZE = 16

#: file types treated as plain text documents
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}

META_SIGNATURE = "embedding_signature"
META_CHUNK_SIZE = "chunk_size"
META_CHUNK_OVERLAP = "chunk_overlap"
META_BACKEND = "backend"
META_DOC_COUNT = "document_count"


class IndexUnusable(RuntimeError):
    """The index cannot answer questions as it stands. Re-ingesting fixes it.

    Typed rather than a bare ``RuntimeError`` so a caller can tell "rebuild the
    index and you are done" apart from a genuine failure. The Streamlit app uses
    that distinction to offer a one-click rebuild instead of a dead end; the CLI
    still catches ``RuntimeError`` and prints the message, which is why this
    subclasses it.
    """


class EmptyIndex(IndexUnusable):
    """Nothing has been ingested yet."""


class IndexMismatch(IndexUnusable):
    """The index was built by a different embedding model.

    Carries both signatures because the interesting part -- which model wrote
    the index versus which one is asking -- should not have to be recovered by
    parsing the message text.
    """

    def __init__(self, stored: str, current: str) -> None:
        self.stored = stored
        self.current = current
        super().__init__(
            "Indeks farkli bir embedding modeliyle olusturulmus.\n"
            f"  indekste: {stored}\n"
            f"  simdiki : {current}\n"
            "Vektor uzaylari uyumsuz. Yeniden indeksle:\n"
            "  python -m app.cli ingest"
        )


@dataclass
class IngestReport:
    """What an ingestion run actually did."""

    documents: int = 0
    chunks: int = 0
    inserted: int = 0
    seconds: float = 0.0
    skipped: list[str] = field(default_factory=list)

    def summary(self) -> str:
        line = (
            f"{self.documents} belge -> {self.chunks} parca "
            f"({self.inserted} yeni kayit) / {self.seconds:.1f} sn"
        )
        if self.skipped:
            line += f"\nAtlanan dosyalar: {', '.join(self.skipped)}"
        return line


@dataclass
class Answer:
    """A generated answer plus everything needed to audit it."""

    question: str
    text: str
    hits: list[SearchHit]
    retrieval_seconds: float = 0.0
    generation_seconds: float = 0.0
    grounded: bool = True
    #: per-sentence support audit, when groundedness checking is enabled
    groundedness: GroundednessReport | None = None
    #: how this answer was produced: "generative", "extractive" or
    #: "extractive-fallback" (generated, then rejected by the groundedness check)
    mode: str = "generative"

    @property
    def sources(self) -> list[str]:
        """Unique source files behind this answer, best match first."""
        seen: list[str] = []
        for hit in self.hits:
            if hit.record.source not in seen:
                seen.append(hit.record.source)
        return seen

    @property
    def total_seconds(self) -> float:
        return self.retrieval_seconds + self.generation_seconds


def iter_documents(docs_dir: Path) -> Iterator[tuple[str, str]]:
    """Yield ``(filename, text)`` for every readable text document in a folder."""
    if not docs_dir.exists():
        raise FileNotFoundError(
            f"Belge klasoru bulunamadi: {docs_dir}\n"
            "FRAG_DOCS_DIR ile baska bir klasor gosterebilirsin."
        )
    for path in sorted(docs_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path.name, path.read_text(encoding="utf-8")


def _batched(items: Sequence[Chunk], size: int) -> Iterator[list[Chunk]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def ingest(
    settings: Settings,
    backend: Backend | None = None,
    reset: bool = True,
    verbose: bool = True,
) -> IngestReport:
    """Build (or rebuild) the vector index from ``settings.docs_dir``.

    ``reset=True`` wipes the index first. That is the default because it is the
    only strategy that cannot leave stale chunks behind when a document is
    edited or deleted, and at this corpus size rebuilding is cheap.
    """
    settings.validate()
    backend = backend or create_backend(settings, verbose=verbose)
    started = time.perf_counter()
    report = IngestReport()

    all_chunks: list[Chunk] = []
    for name, text in iter_documents(settings.docs_dir):
        if not text.strip():
            report.skipped.append(f"{name} (bos)")
            continue
        chunks = chunk_document(
            text, source=name, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        if not chunks:
            report.skipped.append(f"{name} (parca uretilemedi)")
            continue
        report.documents += 1
        all_chunks.extend(chunks)

    report.chunks = len(all_chunks)
    if not all_chunks:
        raise ValueError(
            f"{settings.docs_dir} icinde islenebilir belge yok "
            f"(desteklenen uzantilar: {', '.join(sorted(TEXT_SUFFIXES))})"
        )

    with VectorStore(settings.db_path) as store:
        if reset:
            store.reset()

        done = 0
        for batch in _batched(all_chunks, EMBED_BATCH_SIZE):
            vectors = backend.embed([c.with_heading_prefix() for c in batch])
            if len(vectors) != len(batch):
                raise RuntimeError(
                    f"Backend {len(batch)} metin icin {len(vectors)} vektor dondurdu"
                )
            report.inserted += store.add_chunks(
                (c.source, c.index, c.heading, c.text, c.content_hash, v)
                for c, v in zip(batch, vectors)
            )
            done += len(batch)
            if verbose:
                print(f"\r  Embedding: {done}/{len(all_chunks)} parca", end="", flush=True)
        if verbose:
            print()

        store.set_meta(META_SIGNATURE, backend.embedding_signature())
        store.set_meta(META_CHUNK_SIZE, str(settings.chunk_size))
        store.set_meta(META_CHUNK_OVERLAP, str(settings.chunk_overlap))
        store.set_meta(META_BACKEND, backend.name)
        store.set_meta(META_DOC_COUNT, str(report.documents))

    report.seconds = time.perf_counter() - started
    return report


class RagPipeline:
    """Answers questions against an already-built index.

    Open it once and reuse it: the store connection and the loaded models are
    the expensive parts, and neither should be rebuilt per question.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        backend: Backend | None = None,
        verbose: bool = False,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.settings.validate()
        self.backend = backend or create_backend(self.settings, verbose=verbose)
        self.store = VectorStore(self.settings.db_path)
        self._check_index()

        # Load the index into memory once, here, rather than on every question.
        # At this scale the whole matrix is a few megabytes and re-reading it
        # per query was pure waste.
        self.matrix, self.records = self.store.load_matrix()
        self.bm25 = (
            BM25Index([f"{r.heading}\n{r.content}" for r in self.records])
            if self.settings.hybrid
            else None
        )

    def _check_index(self) -> None:
        """Refuse to answer against an index built by a different embedder."""
        if self.store.count() == 0:
            raise EmptyIndex(
                "Veritabani bos. Once belgeleri indeksle:\n"
                "  python -m app.cli ingest"
            )
        stored = self.store.get_meta(META_SIGNATURE)
        current = self.backend.embedding_signature()
        if stored and stored != current:
            raise IndexMismatch(stored, current)

    # -- retrieval -------------------------------------------------------

    def retrieve(self, question: str) -> tuple[list[SearchHit], float]:
        """Find the passages most relevant to ``question``.

        Runs dense and lexical retrieval together when ``settings.hybrid`` is
        on, which is the default. Turning it off gives plain cosine search and
        is the baseline the hybrid mode is measured against.
        """
        started = time.perf_counter()
        query_vector = self.backend.embed([question])[0]
        hits = hybrid_search(
            self.records,
            self.matrix,
            query_vector,
            query_text=question,
            bm25=self.bm25,
            top_k=self.settings.top_k,
            min_similarity=self.settings.min_similarity,
            lexical_scale=self.settings.lexical_scale,
        )
        return hits, time.perf_counter() - started

    # -- answering -------------------------------------------------------

    def answer(self, question: str) -> Answer:
        """Full RAG round trip: retrieve, augment, generate."""
        question = (question or "").strip()
        if not question:
            return Answer(question="", text="Lutfen bir soru yaz.", hits=[], grounded=False)

        hits, retrieval_seconds = self.retrieve(question)

        # No passage cleared the similarity threshold. Calling the model here
        # would invite it to invent an answer, so we stop instead.
        if not hits:
            return Answer(
                question=question,
                text=NO_CONTEXT_ANSWER,
                hits=[],
                retrieval_seconds=retrieval_seconds,
                grounded=False,
            )

        # Pure extractive mode never touches the chat model.
        if self.settings.answer_mode == "extractive":
            text = extractive.extract_answer(question, hits)
            return Answer(
                question=question,
                text=text,
                hits=hits,
                retrieval_seconds=retrieval_seconds,
                groundedness=groundedness.check(text, hits)
                if self.settings.check_groundedness
                else None,
                mode="extractive",
            )

        messages = build_messages(question, hits, language=self.settings.answer_language)
        started = time.perf_counter()
        text = self.backend.chat(
            messages,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
        generation_seconds = time.perf_counter() - started
        text = text.strip() or NO_CONTEXT_ANSWER

        # Retrieving the right passage does not guarantee the model stayed
        # inside it. Audit the answer against what was actually retrieved.
        report = (
            groundedness.check(text, hits) if self.settings.check_groundedness else None
        )

        # Circuit breaker. If the audit says the generated answer is not
        # supported by the very passages it was given, showing it anyway means
        # knowingly handing the user something measured to be untrustworthy.
        # Quoting the sources instead is worse prose and better information.
        if (
            self.settings.answer_mode == "auto"
            and report is not None
            and report.score < self.settings.min_groundedness
        ):
            return Answer(
                question=question,
                text=extractive.extract_answer(
                    question, hits, notice=extractive.FALLBACK_NOTICE
                ),
                hits=hits,
                retrieval_seconds=retrieval_seconds,
                generation_seconds=generation_seconds,
                groundedness=report,
                mode="extractive-fallback",
            )

        return Answer(
            question=question,
            text=text,
            hits=hits,
            retrieval_seconds=retrieval_seconds,
            generation_seconds=generation_seconds,
            groundedness=report,
            mode="generative",
        )

    def stream_answer(self, question: str) -> Iterable[str]:
        """Same as :meth:`answer` but yields the reply as it is produced."""
        question = (question or "").strip()
        if not question:
            yield "Lutfen bir soru yaz."
            return

        hits, _ = self.retrieve(question)
        if not hits:
            yield NO_CONTEXT_ANSWER
            return

        messages = build_messages(question, hits, language=self.settings.answer_language)
        streamer = getattr(self.backend, "stream_chat", None)
        if streamer is None:
            yield self.backend.chat(
                messages,
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_tokens,
            )
            return
        yield from streamer(
            messages,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )

    # -- lifecycle -------------------------------------------------------

    def close(self) -> None:
        self.store.close()
        closer = getattr(self.backend, "close", None)
        if closer:
            closer()

    def __enter__(self) -> "RagPipeline":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
