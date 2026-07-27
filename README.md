# Yerel RAG Asistanı — Microsoft Foundry Local

Belgelerinizden cevap üreten, **tamamen çevrimdışı** çalışan bir soru-cevap asistanı.
Hem çalışan bir uygulama hem de yeni başlayan bilgisayar bilimleri öğrencileri için
**4–6 haftalık bir yaz okulu müfredatı**.

Model çıkarımı Microsoft Foundry Local ile cihaz üzerinde yapılır. Belgeler,
sorular ve cevaplar hiçbir zaman internete çıkmaz.

```
Soru ──▶ embedding ──▶ SQLite'ta vektör arama ──▶ en ilgili K parça
                                                        │
                          cevap ◀── yerel LLM ◀── bağlam + soru
```

---

## Ne yapar?

- `data/docs/` altındaki belgeleri parçalara böler, her parçanın embedding'ini
  üretir ve SQLite'a yazar.
- Sorduğunuz soruyu aynı modelle vektörleştirir, kosinüs benzerliğiyle en ilgili
  parçaları bulur.
- Bu parçaları bağlam olarak yerel bir dil modeline verir ve **kaynak göstererek**
  cevap üretir.
- Cevap belgelerde yoksa uydurmaz, "Bu bilgi elimdeki belgelerde yok." der.

---

## Hızlı başlangıç

### 1. Foundry Local olmadan denemek (30 saniye)

Kurulum derdine girmeden sistemin çalıştığını görmek için:

```bash
git clone https://github.com/cebi101/foundry-local-rag.git
cd foundry-local-rag
pip install numpy
python -m app.cli --backend hashing ingest
python -m app.cli --backend hashing ask "Kosinüs benzerliği nasıl hesaplanır?"
```

Bu mod dil modeli kullanmaz; ilgili cümleleri belgelerden doğrudan alıntılar.
Getirme (retrieval) katmanının çalıştığını görmek için yeterlidir.

### 2. Gerçek kurulum (Foundry Local ile)

> **macOS'ta sistem Python'u ile çalışmaz.** Sebebi ve çözümü aşağıda.

```bash
# 1) Modern Python (macOS'un 3.9'u yetmez)
brew install python@3.12
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate

# 2) Bağımlılıklar
pip install -r requirements.txt

# 3) Ortam kontrolü — sorun varsa burada görürsünüz
python scripts/doctor.py

# 4) İndeksle (ilk çalıştırmada ~1.3 GB model indirilir)
python -m app.cli ingest

# 5) Sor
python -m app.cli chat
```

### 3. Web arayüzü

```bash
streamlit run app/streamlit_app.py
```

---

## En sık karşılaşılan tuzak: Python 3.9

macOS 14.6, `python3` olarak **3.9.6** getirir. Foundry Local SDK 1.x ise
**Python 3.11+** ister. Kritik nokta şu: pip bu durumda hata vermez, sessizce
bir yıllık **0.5.1** sürümünü kurar.

```bash
$ python3 -V
Python 3.9.6
$ pip3 index versions foundry-local-sdk
foundry-local-sdk (0.5.1)          # ← yanıltıcı: requires_python'a göre filtrelenmiş
```

PyPI'daki gerçek sürüm 1.2.3'tür. İki sürümün modül adı bile farklıdır
(`foundry_local` ve `foundry_local_sdk`) ve API'leri hiç uyuşmaz. Microsoft'un
kendi dokümanlarındaki her örnek 1.x içindir; 3.9'da kopyala-yapıştır yaparsanız
anlaşılmaz `ImportError`'lar alırsınız.

`python scripts/doctor.py` bu durumu ilk satırlarda söyler.

---

## Kullanım

```bash
python -m app.cli ingest                      # belgeleri indeksle
python -m app.cli ask "RAG nedir?"            # tek soru
python -m app.cli chat                        # etkileşimli
python -m app.cli info                        # indekste ne var?

python -m app.cli --backend hashing ingest    # Foundry Local olmadan
python -m app.cli --top-k 6 ask "..."         # daha fazla bağlam getir
```

Kendi belgelerinizi kullanmak için `data/docs/` içine `.md` / `.txt` dosyalarını
koyup yeniden indeksleyin — ya da başka bir klasörü gösterin:

```bash
FRAG_DOCS_DIR=~/notlarim python -m app.cli ingest
```

Tüm ayarlar `FRAG_*` ortam değişkenleriyle geçersiz kılınabilir; bkz.
[.env.example](.env.example) ve [src/foundry_rag/config.py](src/foundry_rag/config.py).

---

## Test ve değerlendirme

```bash
python -m pytest tests/ -q            # 67 test, çevrimdışı, ~0.2 sn
python eval/evaluate.py               # sadece getirme kalitesi (hızlı)
python eval/evaluate.py --generate    # cevapları da üret (yavaş)
```

Değerlendirme seti 33 sorudan oluşur: **25 cevaplanabilir + 8 cevaplanamaz**.
Cevaplanamaz sorular kasıtlıdır — bir RAG sisteminin en tehlikeli hatası,
bilmediği bir konuda kendinden emin şekilde uydurmasıdır. Ölçülen metrikler:

| Metrik | Neyi ölçer |
|---|---|
| `Recall@K` | Doğru kaynak ilk K parça içinde geldi mi? |
| `MRR` | Doğru kaynak kaçıncı sırada geldi? (1. sıra > 5. sıra) |
| Reddetme doğruluğu | Cevaplanamaz sorularda "bilmiyorum" dedi mi? |

**Taban çizgisi** (çevrimdışı `hashing` backend, `top_k=4`, `min_similarity=0.15`):

| Recall@4 | MRR | Reddetme | Genel |
|---|---|---|---|
| %72.0 | 0.650 | %87.5 | %75.8 |

Bu skorlar kasıtlı olarak vasattır — `hashing` backend anlamsal değil, kelime
örtüşmesine dayalı çalışır. Gerçek embedding modeliyle karşılaştırma yapmak
Hafta 4'ün alıştırmalarından biridir.

---

## Proje yapısı

```
src/foundry_rag/
  config.py          Ayarlar (Settings), FRAG_* ortam değişkenleri
  chunking.py        Belge parçalama — başlık duyarlı, örtüşmeli
  store.py           SQLite katmanı, float32 BLOB vektör saklama
  retrieval.py       Kosinüs benzerliği, top-K arama
  prompts.py         Sistem istemi (5 kural) ve bağlam kurulumu
  pipeline.py        ingest() ve RagPipeline.answer()
  backends/
    base.py          Backend sözleşmesi: embed() + chat()
    foundry.py       Foundry Local SDK 1.x (in-process)
    hashing.py       Çevrimdışı yedek — bağımlılıksız, deterministik
app/
  cli.py             Komut satırı arayüzü
  streamlit_app.py   Web arayüzü
scripts/doctor.py    Ortam kontrolü
eval/                33 soruluk değerlendirme seti + ölçüm aracı
tests/               67 test (hepsi çevrimdışı)
data/docs/           Örnek bilgi tabanı — 8 Türkçe ders notu
docs/                Kurulum, mimari, sorun giderme + 6 haftalık müfredat
```

### Backend soyutlaması

Model çağrıları `Backend` arayüzünün arkasındadır. İki gerçekleme vardır:

| Backend | Ne zaman | Gereksinim |
|---|---|---|
| `foundry` | Gerçek kullanım | Python 3.11+, ~1.3 GB model indirmesi |
| `hashing` | Test, CI, ilk gün | Yalnızca numpy |

`--backend auto` (varsayılan) Foundry Local'i dener, bulamazsa uyarı basıp
`hashing`'e düşer. Bu sayede depo klonlandığı anda çalışır ve test paketi
model indirmeye ihtiyaç duymaz.

---

## Yaz okulu müfredatı

| Hafta | Konu | Faz |
|---|---|---|
| [1](docs/hafta-1-rag-kavramlari.md) | RAG kavramları, Foundry Local, ortam kurulumu | Temel |
| [2](docs/hafta-2-embedding-sqlite.md) | Embedding, kosinüs benzerliği, SQLite | Temel |
| [3](docs/hafta-3-ingestion-retrieval.md) | Parçalama, veri alımı, getirme boru hattı | Geliştirme |
| [4](docs/hafta-4-llm-entegrasyonu.md) | Yerel LLM entegrasyonu, istem tasarımı, arayüz | Geliştirme |
| [5](docs/hafta-5-test-degerlendirme.md) | Test, değerlendirme metrikleri, performans | Kapanış |
| [6](docs/hafta-6-dokumantasyon-sunum.md) | Dokümantasyon, kod temizliği, final sunumu | Kapanış |

Ayrıca: [Kurulum](docs/SETUP_MACOS.md) · [Mimari](docs/ARCHITECTURE.md) ·
[Sorun giderme](docs/TROUBLESHOOTING.md)

---

## Gereksinimler ve sınırlar

| | |
|---|---|
| İşletim sistemi | macOS 14.0+ **Apple Silicon (arm64)**, Windows, Linux |
| Python | **3.11+** (Foundry Local için) / 3.9+ (yalnızca `hashing` backend) |
| RAM | 8 GB önerilir (iki model aynı anda yüklenir) |
| Disk | ~150 MB çalışma zamanı + ~1.3 GB model |
| İnternet | Yalnızca ilk çalıştırmada (model indirmesi) |

**Bilinmesi gerekenler:**

- macOS'ta **Intel desteği yoktur**. Yalnızca Apple Silicon wheel'leri yayınlanır.
- Apple Silicon'da hızlandırma **ONNX Runtime WebGPU (Dawn → Metal)** üzerindendir;
  CoreML veya Neural Engine **kullanılmaz**. Aksini söyleyen kaynaklar yanlıştır.
- `brew install foundrylocal` **önerilmez**: tap yaklaşık 6 ay eskidir ve embedding
  desteği gelmeden önceki sürümü kurar. Bu proje CLI'ye ihtiyaç duymaz — SDK 1.x
  çalışma zamanını kendi içinde taşır.
- `brew install foundry` tamamen **başka bir yazılım** kurar (Ethereum aracı).
- Varsayılan sohbet modeli `qwen2.5-0.5b` küçüktür ve Türkçede zayıftır. Daha iyi
  sonuç için `FRAG_CHAT_MODEL=qwen3-1.7b` deneyin.
- Arama kaba kuvvettir; yaklaşık 100 bin parçaya kadar uygundur. Ötesinde
  yaklaşık en yakın komşu (ANN) indeksleri gerekir.
- Tek kullanıcılıdır. Foundry Local eşzamanlı istek kuyruğu sunmaz.

---

## Bilinen üst-akış hataları

Bu proje, Foundry Local'da açık olan şu hatalara karşı korumalıdır:

- **[#905](https://github.com/microsoft/Foundry-Local/issues/905)** — Streaming
  döngüsü son boş chunk'ta `IndexError` ile çöker. Microsoft'un kendi RAG
  tutorial'ı bu hatayı içerir. Bizde `if not chunk.choices: continue` ile korumalı.
- **[#858](https://github.com/microsoft/Foundry-Local/issues/858) /
  [#895](https://github.com/microsoft/Foundry-Local/issues/895)** — GPU execution
  provider doğru kaydolsa bile bazen yalnızca CPU varyantı yüklenir. Bu proje
  `load()` sonrası seçilen varyantı ve execution provider'ı ekrana yazar.

---

## Kaynaklar

- [Foundry Local nedir?](https://learn.microsoft.com/en-us/azure/foundry-local/what-is-foundry-local)
- [Microsoft Learn — RAG uygulaması oluşturma](https://learn.microsoft.com/en-us/azure/foundry-local/tutorials/tutorial-build-rag-app)
- [Tech Community — Building Your First Local RAG Application](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/building-your-first-local-rag-application-with-foundry-local/4501968)
- [İstem mühendisliği teknikleri](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/prompt-engineering)
- [SQLite](https://sqlite.org/index.html)

## Lisans

MIT
