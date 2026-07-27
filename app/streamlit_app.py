"""Streamlit web interface for the local RAG assistant.

    streamlit run app/streamlit_app.py

Same pipeline as the CLI -- this file only renders. If you change how answers
are produced, change ``foundry_rag.pipeline``, not this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit executes this file as a script, so the package-relative bootstrap
# used by the CLI is not available. Put ``src/`` on the path directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import streamlit as st  # noqa: E402

from foundry_rag import RagPipeline, Settings, VectorStore, ingest  # noqa: E402
from foundry_rag.backends import BackendError, BackendUnavailable  # noqa: E402

st.set_page_config(page_title="Yerel RAG Asistanı", page_icon="📚", layout="wide")


@st.cache_resource(show_spinner=False)
def load_pipeline(backend: str, top_k: int, min_similarity: float) -> RagPipeline:
    """Build the pipeline once and reuse it across reruns.

    ``cache_resource`` matters here beyond speed: Foundry Local's manager is a
    singleton that raises if initialised twice, and Streamlit re-executes this
    script on every interaction.
    """
    settings = Settings.from_env()
    settings.backend = backend
    settings.top_k = top_k
    settings.min_similarity = min_similarity
    settings.validate()
    return RagPipeline(settings, verbose=False)


def index_status(db_path: Path) -> tuple[int, int, str]:
    if not db_path.exists():
        return 0, 0, "-"
    with VectorStore(db_path) as store:
        return store.count(), len(store.sources()), store.get_meta("backend", "-") or "-"


# -- sidebar -------------------------------------------------------------

with st.sidebar:
    st.title("⚙️ Ayarlar")

    backend_choice = st.selectbox(
        "Backend",
        ["auto", "foundry", "hashing"],
        index=0,
        help=(
            "auto: Foundry Local varsa onu kullan, yoksa çevrimdışı yedeğe geç. "
            "foundry: Foundry Local zorunlu. "
            "hashing: her zaman çevrimdışı yedek (dil modeli yok)."
        ),
    )
    top_k = st.slider("Getirilecek parça (top-k)", 1, 10, 4)
    min_similarity = st.slider("Benzerlik eşiği", 0.0, 0.9, 0.15, 0.05)

    st.divider()

    base_settings = Settings.from_env()
    chunks, docs, meta_backend = index_status(base_settings.db_path)
    st.metric("İndekslenmiş parça", chunks)
    st.metric("Belge", docs)
    st.caption(f"İndeks backend'i: `{meta_backend}`")

    if st.button("🔄 Belgeleri yeniden indeksle", use_container_width=True):
        settings = Settings.from_env()
        settings.backend = backend_choice
        with st.spinner("İndeksleniyor... (ilk çalıştırmada model indirilebilir)"):
            try:
                report = ingest(settings, verbose=False)
                st.cache_resource.clear()
                st.success(report.summary())
            except (BackendUnavailable, BackendError, ValueError, FileNotFoundError) as exc:
                st.error(str(exc))

    st.divider()
    st.caption(f"Belge klasörü: `{base_settings.docs_dir}`")
    st.caption("Kurulum kontrolü: `python scripts/doctor.py`")


# -- main ----------------------------------------------------------------

st.title("📚 Yerel RAG Asistanı")
st.caption(
    "Belgelerinden cevap üretir. Foundry Local ile tamamen çevrimdışı çalışır — "
    "sorular ve belgeler cihazdan çıkmaz."
)

if chunks == 0:
    st.warning(
        "İndeks boş. Soldaki **Belgeleri yeniden indeksle** düğmesine bas ya da "
        "terminalde `python -m app.cli ingest` çalıştır."
    )
    st.stop()

try:
    rag = load_pipeline(backend_choice, top_k, min_similarity)
except (BackendUnavailable, BackendError, RuntimeError) as exc:
    st.error(str(exc))
    st.stop()

st.info(f"Aktif backend: **{rag.backend.describe()}**", icon="🧠")

if "history" not in st.session_state:
    st.session_state.history = []

for entry in st.session_state.history:
    with st.chat_message("user"):
        st.write(entry["question"])
    with st.chat_message("assistant"):
        st.write(entry["answer"])
        if entry["hits"]:
            with st.expander(f"Kaynaklar ({len(entry['hits'])} parça)"):
                for i, hit in enumerate(entry["hits"], start=1):
                    st.markdown(f"**[{i}] {hit['citation']}** — benzerlik `{hit['score']:.3f}`")
                    st.text(hit["content"])
            st.caption(entry["timing"])

question = st.chat_input("Belgelerine bir soru sor...")

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Aranıyor ve cevap üretiliyor..."):
                answer = rag.answer(question)
            st.write(answer.text)

            hits = [
                {
                    "citation": hit.record.citation,
                    "score": hit.score,
                    "content": hit.record.content,
                }
                for hit in answer.hits
            ]
            if hits:
                with st.expander(f"Kaynaklar ({len(hits)} parça)"):
                    for i, hit in enumerate(hits, start=1):
                        st.markdown(f"**[{i}] {hit['citation']}** — benzerlik `{hit['score']:.3f}`")
                        st.text(hit["content"])
            else:
                st.caption("Eşik üstünde ilgili parça bulunamadı.")

            timing = (
                f"getirme {answer.retrieval_seconds * 1000:.0f} ms · "
                f"üretim {answer.generation_seconds:.2f} sn"
            )
            st.caption(timing)

            st.session_state.history.append(
                {"question": question, "answer": answer.text, "hits": hits, "timing": timing}
            )
        except BackendError as exc:
            st.error(str(exc))
