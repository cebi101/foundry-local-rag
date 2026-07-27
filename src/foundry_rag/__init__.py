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
from .pipeline import Answer, IngestReport, RagPipeline, ingest
from .retrieval import SearchHit, cosine_similarity, search
from .store import ChunkRecord, VectorStore

__version__ = "1.0.0"

__all__ = [
    "Answer",
    "Backend",
    "BackendError",
    "BackendUnavailable",
    "Chunk",
    "ChunkRecord",
    "IngestReport",
    "PROJECT_ROOT",
    "RagPipeline",
    "SearchHit",
    "Settings",
    "VectorStore",
    "chunk_document",
    "chunk_text",
    "cosine_similarity",
    "create_backend",
    "ingest",
    "search",
]
