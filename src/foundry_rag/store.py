"""SQLite-backed storage for document chunks and their embedding vectors.

Design notes
------------
* Vectors are stored as **BLOB** (``float32`` raw bytes), not JSON. A 384-dim
  vector is exactly 1536 bytes and round-trips with a single ``numpy`` call.
  Writing and reading must use the *same* dtype -- writing float32 and reading
  float64 yields silent garbage.
* An ``index_meta`` table records which embedding model built the index. Query
  time compares against it, so mixing vector spaces fails loudly instead of
  returning nonsense similarity scores.
* Everything is stdlib ``sqlite3``. Apple's system Python ships without
  ``enable_load_extension``, so extensions like ``sqlite-vec`` are not an option
  here -- brute-force search in numpy is both simpler and fast enough at this
  scale.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

VECTOR_DTYPE = np.float32

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT    NOT NULL,
    chunk_index   INTEGER NOT NULL,
    heading       TEXT    NOT NULL DEFAULT '',
    content       TEXT    NOT NULL,
    content_hash  TEXT    NOT NULL UNIQUE,
    embedding     BLOB    NOT NULL,
    dim           INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);

CREATE TABLE IF NOT EXISTS index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class ChunkRecord:
    """A chunk as stored in the database."""

    id: int
    source: str
    chunk_index: int
    heading: str
    content: str

    @property
    def citation(self) -> str:
        """Short human-readable reference, e.g. ``01-rag-nedir.md > Tanım``."""
        return f"{self.source} > {self.heading}" if self.heading else self.source


def encode_vector(vector: Sequence[float]) -> bytes:
    """Serialise a float vector to compact bytes for BLOB storage."""
    return np.asarray(vector, dtype=VECTOR_DTYPE).tobytes()


def decode_vector(blob: bytes) -> np.ndarray:
    """Deserialise a BLOB back into a 1-D float32 array."""
    return np.frombuffer(blob, dtype=VECTOR_DTYPE)


class VectorStore:
    """Thin persistence layer over a single SQLite file."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- lifecycle -------------------------------------------------------

    def __enter__(self) -> "VectorStore":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def reset(self) -> None:
        """Drop all indexed data. Used when re-ingesting from scratch."""
        self.conn.execute("DELETE FROM chunks")
        self.conn.execute("DELETE FROM index_meta")
        self.conn.commit()

    # -- writes ----------------------------------------------------------

    def add_chunks(
        self,
        rows: Iterable[tuple[str, int, str, str, str, Sequence[float]]],
    ) -> int:
        """Insert chunks in one transaction.

        Each row is ``(source, chunk_index, heading, content, content_hash,
        embedding)``. Rows whose ``content_hash`` already exists are ignored,
        which makes re-ingestion idempotent.
        """
        payload = [
            (source, idx, heading, content, chash, encode_vector(vec), len(vec))
            for source, idx, heading, content, chash, vec in rows
        ]
        if not payload:
            return 0
        cur = self.conn.executemany(
            """
            INSERT OR IGNORE INTO chunks
                (source, chunk_index, heading, content, content_hash, embedding, dim)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        self.conn.commit()
        return cur.rowcount

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO index_meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    # -- reads -----------------------------------------------------------

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM index_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"])

    def sources(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT source FROM chunks ORDER BY source"
        ).fetchall()
        return [r["source"] for r in rows]

    def load_matrix(self) -> tuple[np.ndarray, list[ChunkRecord]]:
        """Load every vector as one ``(n, dim)`` matrix plus its chunk records.

        Loading everything into memory is deliberate: for a few thousand chunks
        this costs a few megabytes and turns retrieval into a single matrix
        multiply. Revisit only past ~100k chunks.
        """
        rows = self.conn.execute(
            """
            SELECT id, source, chunk_index, heading, content, embedding, dim
            FROM chunks
            ORDER BY id
            """
        ).fetchall()

        if not rows:
            return np.zeros((0, 0), dtype=VECTOR_DTYPE), []

        dims = {int(r["dim"]) for r in rows}
        if len(dims) != 1:
            raise ValueError(
                f"Corrupt index: mixed embedding dimensions {sorted(dims)}. "
                "Re-run ingestion to rebuild the database."
            )

        matrix = np.vstack([decode_vector(r["embedding"]) for r in rows])
        records = [
            ChunkRecord(
                id=int(r["id"]),
                source=r["source"],
                chunk_index=int(r["chunk_index"]),
                heading=r["heading"] or "",
                content=r["content"],
            )
            for r in rows
        ]
        return matrix, records
