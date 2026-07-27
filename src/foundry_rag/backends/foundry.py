"""Microsoft Foundry Local backend (SDK 1.x, in-process inference).

IMPORTANT -- two incompatible SDK generations share the name ``foundry-local-sdk``:

============  ===========================  ==============  ========================
version       import                       Python          how it runs
============  ===========================  ==============  ========================
0.x (legacy)  ``from foundry_local ...``   any             HTTP client, needs the
                                                           ``foundry`` CLI on PATH
1.x (current) ``from foundry_local_sdk``   **>= 3.11**     in-process native core,
                                                           no CLI, no server
============  ===========================  ==============  ========================

This module targets **1.x**. The trap: on macOS's system Python 3.9,
``pip install foundry-local-sdk`` silently resolves to 0.5.1 because pip filters
by ``requires_python``. You then get a completely different API and confusing
``ImportError``s. :func:`_import_sdk` detects that case and says so explicitly.

Run ``python scripts/doctor.py`` to check all of this before debugging by hand.
"""

from __future__ import annotations

import platform
import sys
from typing import Callable, Iterator, Sequence

from .base import Backend, BackendError, BackendUnavailable

DEFAULT_CHAT_MODEL = "qwen2.5-0.5b"
DEFAULT_EMBEDDING_MODEL = "qwen3-embedding-0.6b"


def _embedding_device_default() -> str:
    """Preferred embedding variant when the user said "auto".

    On macOS Apple Silicon this returns ``"cpu"``, deliberately overriding
    Foundry Local's own choice. Its auto-selected ``-generic-gpu`` embedding
    variant emits Inf/NaN on this platform (verified macOS 14.6 / M-series,
    SDK 1.2.3, 2026-07-27), so leaving it on "auto" costs every user a ~500 MB
    download of a variant that cannot work, followed by a crash whose message
    points at JSON serialisation rather than at the model.

    :meth:`FoundryBackend.embed` still recovers if this guess is wrong in the
    other direction, and ``FRAG_DEVICE=gpu`` overrides it outright -- so when
    Microsoft fixes the variant, nothing here blocks using it.
    """
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "cpu"
    return "auto"


def _import_sdk():
    """Import the 1.x SDK, or raise :class:`BackendUnavailable` with a real fix."""
    if sys.version_info < (3, 11):
        raise BackendUnavailable(
            f"Foundry Local SDK 1.x requires Python >= 3.11, but this interpreter is "
            f"{sys.version_info.major}.{sys.version_info.minor}.\n"
            "macOS ships 3.9 as /usr/bin/python3 and pip will silently install the "
            "incompatible 0.5.1 SDK instead of erroring.\n"
            "Fix:  brew install python@3.12 && "
            "/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate"
        )
    try:
        from foundry_local_sdk import Configuration, FoundryLocalManager  # noqa: PLC0415
    except ImportError as exc:
        # 0.x installs a `foundry_local` package instead -- detect and name it
        try:
            import foundry_local  # noqa: F401,PLC0415

            raise BackendUnavailable(
                "Found the LEGACY foundry-local-sdk 0.x (module 'foundry_local'). "
                "This project targets 1.x (module 'foundry_local_sdk').\n"
                "Fix:  pip install --upgrade 'foundry-local-sdk>=1.2'"
            ) from exc
        except ImportError:
            pass
        raise BackendUnavailable(
            "foundry-local-sdk is not installed.\n"
            "Fix:  pip install 'foundry-local-sdk>=1.2' openai"
        ) from exc
    return Configuration, FoundryLocalManager


def _progress_printer(label: str) -> Callable[[float], None]:
    def _cb(percent: float) -> None:
        print(f"\r  {label}: {percent:5.1f}%", end="", flush=True)

    return _cb


def _variant_provider(variant) -> str:
    """Execution provider string of a model variant, lowercased.

    Case matters and cannot be trusted: the remote catalog spells it
    ``WebGPUExecutionProvider`` while the local cache the SDK reads back spells
    it ``WebGpuExecutionProvider``. An exact-match comparison silently never
    matches, so everything here compares lowercased substrings.
    """
    runtime = getattr(getattr(variant, "info", None), "runtime", None)
    return str(getattr(runtime, "execution_provider", "") or "").lower()


def select_device_variant(model, device: str, verbose: bool = False) -> bool:
    """Force the CPU or GPU variant of a model. Returns True if it switched."""
    if device not in {"cpu", "gpu"}:
        return False
    wanted = "cpu" if device == "cpu" else "gpu"
    for variant in getattr(model, "variants", []) or []:
        if wanted in _variant_provider(variant):
            if getattr(variant, "id", None) == getattr(model, "id", None):
                return False
            model.select_variant(variant)
            if verbose:
                print(f"  varyant secildi: {variant.id}")
            return True
    return False


def _is_non_finite_failure(error: Exception) -> bool:
    """Detect the WebGPU variant emitting Inf/NaN inside the embedding vector.

    On Apple Silicon the auto-selected ``*-generic-gpu`` variant of
    ``qwen3-embedding-0.6b`` returns non-finite floats. The failure surfaces far
    from the cause -- as a .NET ``JsonSerializer`` exception while the SDK tries
    to write the vector out:

        System.ArgumentException: .NET number values such as positive and
        negative infinity cannot be written as valid JSON.

    Verified on macOS 14.6 / M-series, SDK 1.2.3, 2026-07-27. The CPU variant of
    the same model works and returns clean 1024-dim vectors.
    """
    text = str(error).lower()
    return "infinity" in text or "cannot be written as valid json" in text


def describe_variant(model) -> str:
    """Report which hardware variant actually got selected.

    Worth surfacing: Foundry Local has open issues (microsoft/Foundry-Local
    #858, #895) where only CPU variants are exposed even though the WebGPU
    execution provider registered fine. You then silently run the slower build.
    Printing the resolved id and EP is the only way to notice.
    """
    model_id = getattr(model, "id", "?")
    runtime = getattr(getattr(model, "info", None), "runtime", None)
    provider = getattr(runtime, "execution_provider", None) if runtime else None
    device = getattr(runtime, "device_type", None) if runtime else None
    details = " / ".join(str(x) for x in (device, provider) if x)
    return f"{model_id} [{details}]" if details else str(model_id)


class FoundryBackend(Backend):
    """Runs a chat model and an embedding model locally, in-process."""

    name = "foundry-local"

    def __init__(
        self,
        chat_model: str = DEFAULT_CHAT_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        app_name: str = "foundry_local_rag",
        model_cache_dir: str | None = None,
        device: str = "auto",
        verbose: bool = True,
    ) -> None:
        self.chat_model_alias = chat_model
        self.embedding_model_alias = embedding_model
        self.app_name = app_name
        self.model_cache_dir = model_cache_dir
        self.device = device
        self.verbose = verbose

        self._manager = None
        self._chat_model = None
        self._chat_client = None
        self._embedding_model = None
        self._embedding_client = None
        self._dim: int | None = None

    # -- lifecycle -------------------------------------------------------

    def _ensure_manager(self):
        """Initialise the SDK singleton exactly once.

        ``FoundryLocalManager`` is a hard singleton: a second ``initialize()``
        raises. That bites with auto-reloading dev servers (streamlit, uvicorn
        ``--reload``) and re-run notebook cells, so we always check ``instance``
        before initialising.
        """
        if self._manager is not None:
            return self._manager

        Configuration, FoundryLocalManager = _import_sdk()

        if getattr(FoundryLocalManager, "instance", None) is None:
            kwargs = {"app_name": self.app_name}
            if self.model_cache_dir:
                kwargs["model_cache_dir"] = self.model_cache_dir
            try:
                FoundryLocalManager.initialize(Configuration(**kwargs))
            except Exception as exc:  # noqa: BLE001 - surface the real cause
                raise BackendUnavailable(
                    f"Foundry Local could not start: {exc}\n"
                    "Check that the native core installed correctly:  "
                    "pip install --force-reinstall 'foundry-local-sdk>=1.2'"
                ) from exc

        self._manager = FoundryLocalManager.instance

        # Fetch/register execution providers for this hardware. On macOS this
        # may be a no-op (acceleration goes through Metal-via-WebGPU), so a
        # failure here must not be fatal.
        try:
            self._manager.download_and_register_eps()
        except Exception as exc:  # noqa: BLE001
            if self.verbose:
                print(f"  (execution provider setup skipped: {exc})")

        return self._manager

    def _prepare_model(self, alias: str, label: str, device: str | None = None):
        """Resolve an alias, download it if needed, and load it into memory."""
        manager = self._ensure_manager()
        try:
            model = manager.catalog.get_model(alias)
        except Exception as exc:  # noqa: BLE001
            available = ", ".join(sorted(self.list_aliases())[:20]) or "<none>"
            raise BackendError(
                f"Model alias {alias!r} is not in the catalog on this machine.\n"
                f"Aliases are hardware-dependent. Available here: {available}"
            ) from exc

        select_device_variant(model, device or self.device, self.verbose)

        if not getattr(model, "is_cached", False):
            if self.verbose:
                print(f"  Downloading {label} model ({alias})...")
            model.download(_progress_printer(label) if self.verbose else None)
            if self.verbose:
                print()

        model.load()
        if self.verbose:
            print(f"  {label}: {describe_variant(model)}")
        return model

    def _switch_embedding_to_cpu(self) -> bool:
        """Rebuild the embedding client on the CPU variant. True if it changed."""
        if self._embedding_model is None:
            return False
        try:
            self._embedding_model.unload()
        except Exception:  # noqa: BLE001, S110
            pass
        if not select_device_variant(self._embedding_model, "cpu", self.verbose):
            return False
        if not getattr(self._embedding_model, "is_cached", False):
            if self.verbose:
                print("  CPU varyanti indiriliyor...")
            self._embedding_model.download(
                _progress_printer("embedding-cpu") if self.verbose else None
            )
            if self.verbose:
                print()
        self._embedding_model.load()
        self._embedding_client = self._embedding_model.get_embedding_client()
        self.device = "cpu"
        return True

    # -- introspection ---------------------------------------------------

    def list_aliases(self) -> list[str]:
        """Every model alias the catalog offers on this hardware."""
        manager = self._ensure_manager()
        try:
            return [m.alias for m in manager.catalog.list_models()]
        except Exception:  # noqa: BLE001
            return []

    def describe(self) -> str:
        return (
            f"{self.name} (chat={self.chat_model_alias}, "
            f"embed={self.embedding_model_alias}, dim={self.embedding_dim})"
        )

    def embedding_signature(self) -> str:
        return f"{self.name}:{self.embedding_model_alias}:{self.embedding_dim}"

    # -- embeddings ------------------------------------------------------

    def _ensure_embedding_client(self):
        if self._embedding_client is None:
            # The embedding model gets its own device policy: the platform
            # default steers around a variant that is known to be broken here.
            device = self.device if self.device != "auto" else _embedding_device_default()
            self._embedding_model = self._prepare_model(
                self.embedding_model_alias, "embedding", device=device
            )
            self._embedding_client = self._embedding_model.get_embedding_client()
        return self._embedding_client

    @property
    def embedding_dim(self) -> int:
        """Vector width, discovered by embedding one short string.

        Never hardcode this. The dimension is a property of the model, it is not
        documented for every alias, and it changes if you swap models.
        """
        if self._dim is None:
            self._dim = len(self.embed(["boyut olcumu"])[0])
        return self._dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        client = self._ensure_embedding_client()
        items = list(texts)
        if not items:
            return []

        try:
            response = client.generate_embeddings(items)
        except Exception as exc:  # noqa: BLE001
            # The GPU variant can emit Inf/NaN, which blows up inside the SDK's
            # serializer rather than at the model. Recover onto CPU once instead
            # of failing the whole ingestion run -- see _is_non_finite_failure.
            if self.device != "cpu" and _is_non_finite_failure(exc):
                if self.verbose:
                    print(
                        "\n  [!] GPU varyanti gecersiz sayi (Inf/NaN) uretti. "
                        "CPU varyantina geciliyor.\n"
                        "      (Foundry Local'in WebGPU embedding varyantinda "
                        "bilinen sorun; kalici olarak FRAG_DEVICE=cpu kullan.)"
                    )
                if self._switch_embedding_to_cpu():
                    self._dim = None
                    response = self._embedding_client.generate_embeddings(items)
                    return [list(item.embedding) for item in response.data]
            raise BackendError(f"Embedding generation failed: {exc}") from exc

        return [list(item.embedding) for item in response.data]

    # -- chat ------------------------------------------------------------

    def _ensure_chat_client(self):
        if self._chat_client is None:
            self._chat_model = self._prepare_model(self.chat_model_alias, "chat")
            self._chat_client = self._chat_model.get_chat_client()
        return self._chat_client

    def stream_chat(
        self,
        messages: Sequence[dict],
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> Iterator[str]:
        """Yield answer fragments as the model produces them.

        ``complete_streaming_chat`` is the call used by Microsoft's own RAG
        tutorial, so it is the verified path. Whether it accepts sampling
        kwargs is NOT documented -- we try with them and retry without on
        ``TypeError`` rather than assuming either way.
        """
        client = self._ensure_chat_client()
        payload = [dict(m) for m in messages]

        try:
            stream = client.complete_streaming_chat(
                payload, temperature=temperature, max_tokens=max_tokens
            )
        except TypeError:
            stream = client.complete_streaming_chat(payload)
        except Exception as exc:  # noqa: BLE001
            raise BackendError(f"Chat completion failed: {exc}") from exc

        for chunk in stream:
            # The final chunk can arrive with an empty `choices` list. Microsoft's
            # own tutorial indexes into it unguarded and crashes with IndexError
            # right after printing the answer (Foundry-Local issue #905, open,
            # reproduced on macOS arm64 + WebGPU + SDK 1.2.3). Skip such chunks.
            if not getattr(chunk, "choices", None):
                continue
            delta = getattr(chunk.choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta else None
            if content:
                yield content

    def chat(
        self,
        messages: Sequence[dict],
        temperature: float = 0.1,
        max_tokens: int = 600,
    ) -> str:
        return "".join(self.stream_chat(messages, temperature, max_tokens)).strip()

    # -- teardown --------------------------------------------------------

    def close(self) -> None:
        """Free model memory. Safe to call more than once."""
        for model in (self._embedding_model, self._chat_model):
            if model is not None:
                try:
                    model.unload()
                except Exception:  # noqa: BLE001, S110 - teardown must not raise
                    pass
        self._embedding_model = self._embedding_client = None
        self._chat_model = self._chat_client = None
