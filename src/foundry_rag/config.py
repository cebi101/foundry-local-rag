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
    # These two are NOT guesses. They are the argmax of `python eval/calibrate.py`
    # over the 33-question evaluation set (balanced score 93.6%: recall 88.0%,
    # refusal accuracy 100.0%). Re-run calibration whenever the corpus or the
    # embedding model changes -- the right threshold moves with them.
    min_similarity: float = 0.30
    # Hybrid = dense vectors + BM25 keywords, fused by reciprocal rank fusion.
    # Set False to compare against dense-only retrieval (a Week 3 exercise).
    hybrid: bool = True
    # BM25 saturation point: the raw score at which lexical confidence hits 0.5.
    lexical_scale: float = 16.0

    # --- models ---
    # "auto"    -> use Foundry Local if reachable, otherwise the offline fallback
    # "foundry" -> require Foundry Local, fail loudly if unavailable
    # "hashing" -> always use the dependency-free offline backend
    backend: str = "auto"
    # Aliases used by Microsoft's own RAG tutorial. Aliases are hardware
    # dependent -- run `python scripts/doctor.py` to list what resolves here.
    chat_model: str = "qwen2.5-0.5b"
    embedding_model: str = "qwen3-embedding-0.6b"
    # Which hardware variant to ask Foundry Local for: "auto", "cpu" or "gpu".
    # "auto" lets Foundry Local choose and falls back to CPU if the chosen
    # variant produces unusable output -- see FoundryBackend for why that is
    # not hypothetical on Apple Silicon.
    device: str = "auto"

    # --- generation ---
    temperature: float = 0.1
    max_tokens: int = 600
    # After generating, check every sentence of the answer against the
    # retrieved passages and flag the ones with no support. Cheap (no model
    # call) and it is what catches the model filling gaps on its own.
    check_groundedness: bool = True

    # How the answer is produced:
    #   "generative" -> always use the chat model
    #   "extractive" -> never use it; quote the retrieved passages instead
    #   "auto"       -> generate, then fall back to quoting when the
    #                   groundedness check says the generated answer is not
    #                   supported by its own context
    # "auto" is the default because small local models produce word salad in
    # Turkish while retrieval on the same corpus scores 97% -- see
    # foundry_rag/extractive.py for the measurements.
    answer_mode: str = "auto"
    # Groundedness below this triggers the fallback. 0.34 means "at least a
    # third of the answer's sentences must be traceable to the context".
    min_groundedness: float = 0.34

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
            min_similarity=_env_float("MIN_SIMILARITY", 0.30),
            hybrid=_env_str("HYBRID", "1").strip().lower() not in {"0", "false", "no"},
            lexical_scale=_env_float("LEXICAL_SCALE", 16.0),
            backend=_env_str("BACKEND", "auto").lower().strip(),
            chat_model=_env_str("CHAT_MODEL", "qwen2.5-0.5b"),
            embedding_model=_env_str("EMBEDDING_MODEL", "qwen3-embedding-0.6b"),
            device=_env_str("DEVICE", "auto").lower().strip(),
            temperature=_env_float("TEMPERATURE", 0.1),
            max_tokens=_env_int("MAX_TOKENS", 600),
            check_groundedness=_env_str("CHECK_GROUNDEDNESS", "1").strip().lower()
            not in {"0", "false", "no"},
            answer_mode=_env_str("ANSWER_MODE", "auto").lower().strip(),
            min_groundedness=_env_float("MIN_GROUNDEDNESS", 0.34),
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
        if self.device not in {"auto", "cpu", "gpu"}:
            raise ValueError(f"device must be one of auto/cpu/gpu, got {self.device!r}")
        if self.answer_mode not in {"auto", "generative", "extractive"}:
            raise ValueError(
                "answer_mode must be one of auto/generative/extractive, "
                f"got {self.answer_mode!r}"
            )
