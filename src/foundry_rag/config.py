"""Central configuration for the local RAG assistant.

Every tunable lives here so that experiments (chunk size, top-k, model choice)
are a one-line change instead of a hunt through the codebase.

Settings can be overridden with environment variables prefixed with ``FRAG_``,
e.g. ``FRAG_TOP_K=5``. See ``.env.example``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# repo root: src/foundry_rag/config.py -> src/foundry_rag -> src -> repo
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DOCS_DIR = PROJECT_ROOT / "data" / "docs"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "rag.db"


def _env_str(name: str, default: str) -> str:
    return os.environ.get(f"FRAG_{name}", default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(f"FRAG_{name}")
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"FRAG_{name} must be an integer, got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(f"FRAG_{name}")
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"FRAG_{name} must be a number, got {raw!r}") from exc


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(f"FRAG_{name}")
    return Path(raw).expanduser() if raw else default


@dataclass
class Settings:
    """Runtime settings for ingestion and querying."""

    # --- data ---
    docs_dir: Path = DEFAULT_DOCS_DIR
    db_path: Path = DEFAULT_DB_PATH

    # --- chunking ---
    chunk_size: int = 900
    chunk_overlap: int = 150

    # --- retrieval ---
    top_k: int = 4
    min_similarity: float = 0.15

    # --- models ---
    # "auto"    -> use Foundry Local if reachable, otherwise the offline fallback
    # "foundry" -> require Foundry Local, fail loudly if unavailable
    # "hashing" -> always use the dependency-free offline backend
    backend: str = "auto"
    # Aliases used by Microsoft's own RAG tutorial. Aliases are hardware
    # dependent -- run `python scripts/doctor.py` to list what resolves here.
    chat_model: str = "qwen2.5-0.5b"
    embedding_model: str = "qwen3-embedding-0.6b"

    # --- generation ---
    temperature: float = 0.1
    max_tokens: int = 600

    # --- misc ---
    answer_language: str = "Türkçe"

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables, falling back to defaults."""
        return cls(
            docs_dir=_env_path("DOCS_DIR", DEFAULT_DOCS_DIR),
            db_path=_env_path("DB_PATH", DEFAULT_DB_PATH),
            chunk_size=_env_int("CHUNK_SIZE", 900),
            chunk_overlap=_env_int("CHUNK_OVERLAP", 150),
            top_k=_env_int("TOP_K", 4),
            min_similarity=_env_float("MIN_SIMILARITY", 0.15),
            backend=_env_str("BACKEND", "auto").lower().strip(),
            chat_model=_env_str("CHAT_MODEL", "qwen2.5-0.5b"),
            embedding_model=_env_str("EMBEDDING_MODEL", "qwen3-embedding-0.6b"),
            temperature=_env_float("TEMPERATURE", 0.1),
            max_tokens=_env_int("MAX_TOKENS", 600),
            answer_language=_env_str("ANSWER_LANGUAGE", "Türkçe"),
        )

    def validate(self) -> None:
        """Fail fast on settings that would silently produce nonsense."""
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be smaller than "
                f"chunk_size ({self.chunk_size}), otherwise chunking never advances"
            )
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if not -1.0 <= self.min_similarity <= 1.0:
            raise ValueError("min_similarity must be between -1 and 1")
        if self.backend not in {"auto", "foundry", "hashing"}:
            raise ValueError(
                f"backend must be one of auto/foundry/hashing, got {self.backend!r}"
            )
