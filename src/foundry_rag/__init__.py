"""foundry_rag -- offline RAG question answering on Microsoft Foundry Local.

Typical use::

    from foundry_rag import Settings, RagPipeline, ingest

    settings = Settings.from_env()
    ingest(settings)                       # build the index (slow, run once)

    with RagPipeline(settings) as rag:      # answer questions (fast)
        print(rag.answer("RAG nedir?").text)
"""

from __future__ import annotations

from .backends import Backend, BackendError, BackendUnavailable, create_backend
from .chunking import Chunk, chunk_document, chunk_text
from .config import PROJECT_ROOT, Settings
from .extractive import extract_answer
from .groundedness import GroundednessReport, SentenceVerdict
from .lexical import BM25Index
from .pipeline import Answer, IngestReport, RagPipeline, ingest
from .retrieval import (
    SearchHit,
    cosine_similarity,
    hybrid_search,
    reciprocal_rank_fusion,
    search,
)
from .store import ChunkRecord, VectorStore

__version__ = "1.0.0"

__all__ = [
    "Answer",
    "BM25Index",
    "Backend",
    "BackendError",
    "BackendUnavailable",
    "Chunk",
    "ChunkRecord",
    "GroundednessReport",
    "IngestReport",
    "PROJECT_ROOT",
    "RagPipeline",
    "SearchHit",
    "SentenceVerdict",
    "Settings",
    "VectorStore",
    "chunk_document",
    "chunk_text",
    "cosine_similarity",
    "create_backend",
    "extract_answer",
    "hybrid_search",
    "ingest",
    "reciprocal_rank_fusion",
    "search",
]
