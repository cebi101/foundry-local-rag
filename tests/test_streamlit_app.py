"""The web UI's recovery paths.

An index fault is recoverable by construction -- re-ingesting fixes it -- so the
app must offer that fix rather than printing the error and stopping. It used to
stop: opening the default (hashing-built) index while Foundry Local was
installed produced a dead error screen, which is the first thing a student hits
on demo day.

Streamlit is optional for the core library and CI installs only numpy+pytest,
so these skip when it is absent.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from foundry_rag import ingest  # noqa: E402
from foundry_rag.backends.hashing import HashingBackend  # noqa: E402
from foundry_rag.pipeline import META_SIGNATURE  # noqa: E402
from foundry_rag.store import VectorStore  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


def _text(app_test) -> str:
    """All rendered markdown, tags stripped."""
    return re.sub(r"<[^>]+>", " ", " ".join(m.value for m in app_test.markdown))


def _run(monkeypatch, tmp_path, docs_dir, db_name="ui.db"):
    monkeypatch.setenv("FRAG_DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("FRAG_DOCS_DIR", str(docs_dir))
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()
    return app


def test_empty_index_offers_to_build_it(monkeypatch, tmp_path, docs_dir):
    """No index yet: say so and give a button, do not just stop."""
    app = _run(monkeypatch, tmp_path, docs_dir)

    assert not app.exception
    assert "İndeks boş" in _text(app)
    assert any("indeksle" in b.label.lower() for b in app.button)


def test_signature_mismatch_shows_both_signatures_and_a_fix(
    monkeypatch, tmp_path, docs_dir, settings
):
    """The regression this module exists for: recovery panel, not a dead end."""
    settings.db_path = tmp_path / "ui.db"
    settings.docs_dir = docs_dir
    ingest(settings, backend=HashingBackend(), verbose=False)
    with VectorStore(settings.db_path) as store:
        store.set_meta(META_SIGNATURE, "baska-model:1024")

    # Keep the UI offline: "auto" would otherwise reach for Foundry Local.
    monkeypatch.setattr(
        "foundry_rag.pipeline.create_backend", lambda *a, **k: HashingBackend()
    )
    app = _run(monkeypatch, tmp_path, docs_dir)

    assert not app.exception
    rendered = _text(app)
    assert "baska-model:1024" in rendered, "indeksi kuran model gorunmeli"
    assert "hashing-offline:512" in rendered, "simdiki model gorunmeli"
    assert any("yeniden indeksle" in b.label.lower() for b in app.button)


def _hue_saturation(value: str) -> tuple[float, float]:
    """HSV hue (degrees) and saturation for a ``#rrggbb`` string.

    Channel dominance is the wrong test for this: violet is blue-dominant in
    RGB while reading as purple. Hue is what the eye actually names.
    """
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (1, 3, 5))
    high, low = max(r, g, b), min(r, g, b)
    delta = high - low
    if delta == 0:
        return 0.0, 0.0
    if high == r:
        hue = 60 * (((g - b) / delta) % 6)
    elif high == g:
        hue = 60 * ((b - r) / delta + 2)
    else:
        hue = 60 * ((r - g) / delta + 4)
    return hue, delta / high


def test_palette_avoids_the_traffic_light_convention():
    """The status ramp is warm on purpose -- no green, no blue.

    Guards a deliberate design choice, so that a later "let's make success
    green again" edit has to be a conscious one.
    """
    source = Path(APP).read_text(encoding="utf-8")
    hexes = re.findall(r'"(#[0-9A-Fa-f]{6})"', source)
    assert hexes, "palet bulunamadi"

    for value in hexes:
        hue, saturation = _hue_saturation(value)
        if saturation < 0.35:
            continue  # near-neutral surface colours carry no hue message
        assert not 75 <= hue <= 165, f"{value} yesil ton (hue {hue:.0f})"
        assert not 185 <= hue <= 265, f"{value} mavi ton (hue {hue:.0f})"
