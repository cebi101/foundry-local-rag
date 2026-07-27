"""The contract every model backend must satisfy.

Keeping model access behind this interface is what lets the same pipeline run
against Foundry Local on a student's laptop and against a deterministic stub in
CI -- without the pipeline knowing or caring which one it got.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence


class BackendError(RuntimeError):
    """Raised when a backend cannot serve a request."""


class BackendUnavailable(BackendError):
    """Raised when a backend cannot be initialised at all (not installed, service down)."""


class Backend(ABC):
    """Two operations are all a RAG pipeline needs from a model provider."""

    #: short identifier used in logs, meta rows and the UI
    name: str = "base"

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in the same order."""

    @abstractmethod
    def chat(
        self,
        messages: Sequence[dict],
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> str:
        """Return the assistant's reply for a list of chat messages."""

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Dimensionality of the vectors returned by :meth:`embed`."""

    def describe(self) -> str:
        """One-line description shown to the user at startup."""
        return f"{self.name} (dim={self.embedding_dim})"

    def embedding_signature(self) -> str:
        """Identity of the vector space, stored alongside the index.

        Two indexes are only comparable if their signatures match.
        """
        return f"{self.name}:{self.embedding_dim}"
