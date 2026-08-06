"""Environment check. Run this FIRST when something does not work.

    python scripts/doctor.py

It verifies, in order, the things that actually go wrong:

1. CPU architecture -- Foundry Local ships native wheels per OS/architecture
2. Python version -- the SDK needs >= 3.11 and macOS ships 3.9
3. which SDK generation is installed -- 0.x and 1.x share a package name
4. numpy / streamlit
5. whether the Foundry Local catalog resolves the configured model aliases

Advice is platform-aware. A checker that tells a Windows user to run ``brew``
has not helped them; it has cost them the afternoon.
"""

from __future__ import annotations

import platform
import sqlite3
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from foundry_rag.backends.foundry import venv_setup_command
except ImportError:  # broken checkout -- check_foundry_catalog reports it properly

    def venv_setup_command() -> str:
        return "pip install -r requirements.txt"


OK = "  [ok]  "
WARN = "  [!!]  "
BAD = "  [XX]  "

problems: list[str] = []

# Foundry Local publishes native wheels per OS *and* architecture. macOS is the
# strict one -- arm64 only, no Intel build exists at all -- so the old bare
# "is it arm64?" test flagged every healthy Windows and Linux machine and told
# it to escape Rosetta, which is not a thing outside macOS.
SUPPORTED_ARCH = {
    "Darwin": {"arm64"},
    "Windows": {"amd64", "arm64"},
    "Linux": {"x86_64", "amd64", "aarch64", "arm64"},
}

ARCH_HINT = {
    "Darwin": (
        "Foundry Local yalnizca macOS arm64 (Apple Silicon) icin wheel yayinliyor. "
        "Rosetta altinda calisan bir Python kullaniyorsan arm64 bir yorumlayiciya gec."
    ),
    "Windows": (
        "Foundry Local x64 ve ARM64 Windows icin wheel yayinliyor. 32-bit bir Python "
        "kullaniyorsan 64-bit surumune gec."
    ),
    "Linux": "Foundry Local bu mimari icin wheel yayinlamiyor olabilir.",
}


def architecture_status(system: str, machine: str) -> tuple[str, str]:
    """Grade this OS/architecture pair. Returns ``(status, hint)``.

    Split out from :func:`check_platform` so the per-OS rules can be tested
    without pretending to be another operating system.
    """
    supported = SUPPORTED_ARCH.get(system)
    if supported is None:
        return WARN, (
            f"'{system}' bu proje icin test edilmedi. Cevrimdisi yedek backend "
            "her platformda calisir: python -m app.cli --backend hashing ingest"
        )
    if machine.lower() in supported:
        return OK, ""
    return WARN, ARCH_HINT[system]


def report(status: str, message: str, fix: str = "") -> None:
    print(f"{status}{message}")
    if fix:
        print(f"         -> {fix}")
    if status == BAD:
        problems.append(message)


def check_platform() -> None:
    print("\n--- Platform ---")
    machine = platform.machine()
    status, hint = architecture_status(platform.system(), machine)
    report(status, f"islemci mimarisi: {machine}", hint)
    report(OK, f"isletim sistemi: {platform.platform()}")


def check_python() -> None:
    print("\n--- Python ---")
    version = sys.version_info
    label = f"{version.major}.{version.minor}.{version.micro} ({sys.executable})"
    if version >= (3, 11):
        report(OK, f"python: {label}")
    else:
        report(
            BAD,
            f"python: {label} -- Foundry Local SDK 1.x >= 3.11 istiyor",
            venv_setup_command(),
        )

    conn = sqlite3.connect(":memory:")
    can_load = hasattr(conn, "enable_load_extension")
    conn.close()
    report(
        OK if can_load else WARN,
        f"sqlite {sqlite3.sqlite_version} / uzanti yukleme: {can_load}",
        ""
        if can_load
        else "sqlite-vec bu yorumlayicida kullanilamaz. Bu proje icin sorun degil: "
        "arama numpy ile kaba kuvvet yapiliyor.",
    )


def check_packages() -> None:
    print("\n--- Paketler ---")
    try:
        import numpy

        report(OK, f"numpy {numpy.__version__}")
    except ImportError:
        report(BAD, "numpy kurulu degil", "pip install numpy")

    try:
        import streamlit

        report(OK, f"streamlit {streamlit.__version__}")
    except ImportError:
        report(WARN, "streamlit kurulu degil (sadece web arayuzu icin gerekli)",
               "pip install streamlit")

    # The package-name trap: 0.x installs `foundry_local`, 1.x `foundry_local_sdk`.
    try:
        import importlib.metadata as md

        version = md.version("foundry-local-sdk")
    except Exception:  # noqa: BLE001
        version = None

    if version is None:
        report(
            WARN,
            "foundry-local-sdk kurulu degil (cevrimdisi yedek backend calisir)",
            "pip install 'foundry-local-sdk>=1.2' openai",
        )
        return

    if version.startswith("0."):
        report(
            BAD,
            f"foundry-local-sdk {version} -- bu ESKI 0.x API'si, proje 1.x istiyor",
            "Python 3.11+ ortaminda: pip install --upgrade 'foundry-local-sdk>=1.2'",
        )
        return

    try:
        import foundry_local_sdk  # noqa: F401

        report(OK, f"foundry-local-sdk {version} (modul: foundry_local_sdk)")
    except ImportError as exc:
        report(BAD, f"foundry-local-sdk {version} import edilemedi: {exc}",
               "pip install --force-reinstall 'foundry-local-sdk>=1.2'")


def check_foundry_catalog() -> None:
    print("\n--- Foundry Local katalogu ---")
    try:
        from foundry_rag.backends.foundry import FoundryBackend
        from foundry_rag.config import Settings
    except ImportError as exc:
        report(BAD, f"proje modulleri import edilemedi: {exc}")
        return

    settings = Settings.from_env()
    backend = FoundryBackend(
        chat_model=settings.chat_model,
        embedding_model=settings.embedding_model,
        verbose=False,
    )
    try:
        aliases = backend.list_aliases()
    except Exception as exc:  # noqa: BLE001
        report(
            WARN,
            f"Foundry Local baslatilamadi: {exc}",
            "Cevrimdisi yedek backend ile calisabilirsin: "
            "python -m app.cli --backend hashing ingest",
        )
        return

    if not aliases:
        report(WARN, "katalog bos dondu (ilk calistirmada internet gerekir)")
        return

    report(OK, f"katalogda {len(aliases)} model var")
    for label, wanted in (
        ("sohbet", settings.chat_model),
        ("embedding", settings.embedding_model),
    ):
        found = wanted in aliases
        report(
            OK if found else BAD,
            f"{label} modeli '{wanted}': {'bulundu' if found else 'BULUNAMADI'}",
            ""
            if found
            else f"Bu donanimda mevcut ilk 15 alias: {', '.join(sorted(aliases)[:15])}",
        )


def main() -> int:
    print("=" * 62)
    print("  Yerel RAG Asistani -- ortam kontrolu")
    print("=" * 62)

    check_platform()
    check_python()
    check_packages()
    check_foundry_catalog()

    print("\n" + "=" * 62)
    if problems:
        print(f"  {len(problems)} sorun bulundu. Yukaridaki '->' satirlarini uygula.")
        return 1
    print("  Her sey yolunda gorunuyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
