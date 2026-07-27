"""Model backends and the factory that picks one.

``Settings.backend`` controls selection:

``foundry``
    Require Foundry Local. Raise if it is unavailable -- use this once the
    environment is set up, so a broken install fails loudly instead of
    silently degrading.
``hashing``
    Always use the offline stand-in. Used by the test suite.
``auto`` (default)
    Try Foundry Local, fall back to hashing with a visible warning. Lets a
    student run the project on day one, before any model download finishes.
"""

from __future__ import annotations

import sys

from .base import Backend, BackendError, BackendUnavailable
from .hashing import HashingBackend

__all__ = [
    "Backend",
    "BackendError",
    "BackendUnavailable",
    "HashingBackend",
    "create_backend",
]


def create_backend(settings, verbose: bool = True) -> Backend:
    """Build the backend named by ``settings.backend``."""
    choice = settings.backend

    if choice == "hashing":
        return HashingBackend()

    from .foundry import FoundryBackend  # imported lazily: heavy native deps

    def _build_foundry() -> Backend:
        backend = FoundryBackend(
            chat_model=settings.chat_model,
            embedding_model=settings.embedding_model,
            device=getattr(settings, "device", "auto"),
            verbose=verbose,
        )
        # Force real initialisation now so "auto" can fall back before the
        # caller has started a long ingestion run.
        backend.embedding_dim
        return backend

    if choice == "foundry":
        return _build_foundry()

    if choice == "auto":
        try:
            return _build_foundry()
        except (BackendUnavailable, BackendError) as exc:
            # Always announce the downgrade, even when quiet. Silently answering
            # with a different (much weaker) model than the user asked for is
            # exactly the kind of thing that must never be invisible.
            print(
                "\n[!] Foundry Local kullanilamiyor, cevrimdisi yedek backend'e "
                f"gecildi.\n    Sebep: {exc}\n"
                "    Ayrinti icin: python scripts/doctor.py\n",
                file=sys.stderr,
            )
            return HashingBackend()

    raise ValueError(f"Unknown backend: {choice!r}")
