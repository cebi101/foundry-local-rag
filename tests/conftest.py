"""Shared pytest fixtures.

Every test runs against :class:`HashingBackend`, never Foundry Local. Tests must
be fast, offline and deterministic -- downloading a multi-gigabyte model in CI
is none of those things.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from foundry_rag import Settings  # noqa: E402
from foundry_rag.backends.hashing import HashingBackend  # noqa: E402

SAMPLE_DOCS = {
    "kediler.md": """# Kediler

## Beslenme

Kediler zorunlu etçildir ve taurin adlı amino asidi kendi vücutlarında
yeterince üretemezler. Bu yüzden taurini hazır mamadan almaları gerekir.

## Uyku

Bir kedi günde ortalama on altı saat uyur. Yavru kediler daha da fazla uyur.
""",
    "kahve.md": """# Kahve

## Demleme

Filtre kahve için önerilen su sıcaklığı doksan iki ile doksan altı derece
arasındadır. Daha sıcak su acı bir tat bırakır.

## Saklama

Kavrulmuş çekirdekler hava almayan bir kapta, serin ve karanlık bir yerde
saklanmalıdır. Buzdolabı nem yüzünden uygun değildir.
""",
}


@pytest.fixture
def backend() -> HashingBackend:
    return HashingBackend()


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "docs"
    directory.mkdir()
    for name, text in SAMPLE_DOCS.items():
        (directory / name).write_text(text, encoding="utf-8")
    return directory


@pytest.fixture
def settings(tmp_path: Path, docs_dir: Path) -> Settings:
    return Settings(
        docs_dir=docs_dir,
        db_path=tmp_path / "test.db",
        chunk_size=300,
        chunk_overlap=50,
        top_k=3,
        min_similarity=0.0,
        backend="hashing",
    )
