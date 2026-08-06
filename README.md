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
- Sorduğunuz soruyu **hem anlamsal hem kelime tabanlı** arar, iki sonucu birleştirir.
- Bulunan parçaları bağlam olarak yerel bir dil modeline verir ve **kaynak
  göstererek** cevap üretir.
- Cevap belgelerde yoksa uydurmaz, "Bu bilgi elimdeki belgelerde yok." der.
- **Ürettiği cevabı sonradan denetler** ve bağlamda dayanağı olmayan cümleleri
  işaretler.

---

## Bu projeyi standart bir RAG tutorial'ından ayıran beş şey

Hepsi ölçülmüş bir problemi çözüyor ve etkisi `eval/` ile kanıtlanıyor.

### 1. Türkçe morfoloji duyarlı arama

Türkçe eklemeli bir dildir: `belge · belgeler · belgelerden · belgelerin` aynı
kavramın dört yüzüdür ama kelime eşleştiren bir arama için dört farklı kelimedir.
[`turkish.py`](src/foundry_rag/turkish.py) üç şeyi çözer:

- **Noktalı/noktasız I.** Python'un `.lower()` metodu `I → i` yapar; Türkçede
  doğrusu `I → ı`, `İ → i`. Bu hata, içinde I geçen her kelimede eşleşmeyi sessizce bozar.
- **Kesme işaretli ekler.** `RAG'in`, `SQLite'ta` → kök bedavaya çıkar.
- **Ünlü uyumlu ek ayıklama** + ünsüz yumuşaması geri alma (`benzerliği → benzerlik → benzer`).

Kural tabanlı bir stemmer `belge`(kök) ile `belgeler`(çekimli) arasındaki son
ünlünün ek mi kök mü olduğunu bilemez. Bu yüzden indeks **hem yüzey biçimini hem
gövdeyi** tutar; ikisinden biri tutar. 12 kelime ailesinde 12/12 eşleşme,
kontrol çiftlerinde (`kedi`~`kahve`, `model`~`modern`) sıfır yanlış pozitif.

### 2. Hibrit getirme: BM25 + vektör, RRF ile birleştirme

İki arama farklı yerlerde başarısız olur. Vektör araması nadir literal
ifadeleri kaçırır (`1536`, bir model adı, bir hata kodu) — çünkü embedding tam
da onları nadir yapan detayı bulanıklaştırır. Kelime araması ise eş anlamlıyı
kaçırır (`araba fiyatları` ↔ `otomobil ücretleri`).

İkisi de çalıştırılır ve **Reciprocal Rank Fusion** ile birleştirilir. Füzyon
skora değil **sıraya** bakar: kosinüs [-1,1] aralığında, BM25 ise sınırsız ve
korpusa bağlıdır — ham skorları toplamak her korpusta yeniden ayar ister,
sıralar ise kalibrasyonsuz karşılaştırılabilir.

### 3. Kaynaklılık denetleyici (halüsinasyon dedektörü)

Doğru parçayı getirmek, modelin o parçanın içinde kaldığı anlamına gelmez. Model
boşluk doldurur, geçiş cümlesi uydurur, ezberinden bir şey karıştırır — ve
uydurulmuş bir cümle, yanındaki kaynak etiketiyle birlikte, doğru olandan
**ayırt edilemez** görünür.

[`groundedness.py`](src/foundry_rag/groundedness.py) cevabın her cümlesini
getirilen parçalara karşı puanlar ve dayanaksızları işaretler. Ölçüm, Türkçe
morfoloji üzerinden IDF ağırlıklı içerik kelimesi örtüşmesi: nadir kelimeler
ağır basar, işlev kelimeleri hiç sayılmaz.

```
DOGRU   -> Kaynaklilik: %100 (2/2 cümle dayanaklı)
UYDURMA -> Kaynaklilik: %0  (0/2)  [!] (0.21) Kosinüs benzerliği 1950'de Isaac Newton...
```

Bu bir NLI modeli değil — çelişkiyi ve ortak kelimesiz eş anlamlıyı yakalayamaz.
Ama ikinci bir model indirmesi de gerektirmez ve asıl önemli hatayı güvenilir
biçimde yakalar: **modelin bağlamda hiç geçmeyen bir şeyi iddia etmesi.**

> **Ölçülmüş sınır: dejenerasyon dayanaklı görünüyor.** Denetim kelime örtüşmesine
> dayandığı için, model tekrar döngüsüne girip bağlamdaki kelimeleri döndürdüğünde
> skor **yükselir** — tekrarlanan kelimeler gerçekten bağlamda geçtiği için. Gerçek
> bir çalıştırmada `qwen2.5-0.5b` anlamsız ve kendini tekrar eden bir metin üretti,
> denetim **%42** verdi ve bu `min_groundedness=0.34` eşiğinin üstünde kaldığı için
> devre kesici tetiklenmedi; çöp metin kullanıcıya gösterildi.
>
> Yani denetleyici **uydurmayı** yakalıyor, **bozuk üretimi** yakalamıyor. Bunlar
> farklı iki hata ve ayrı sinyal gerektiriyor: dejenerasyon, kelime örtüşmesinden
> bağımsız olarak tekrar oranıyla ölçülmeli. Henüz yapılmadı.

### 4. Eşik kalibrasyonu ve CI kalite kapısı

`min_similarity` ne zaman cevap verileceğine karar verir. Düşük olursa sistem
bilmediğini uydurur, yüksek olursa bildiğini reddeder. Soyut bir doğru değeri
yoktur — korpusa, modele ve retriever'a bağlıdır.

Tahmin etmenin bedeli bu projede ölçüldü: `0.15` dense-only kosinüs için
ayarlanmıştı; BM25 eklenince skor dağılımı altından kaydı ve reddetme doğruluğu
%87.5'ten %12.5'e çöktü. [`calibrate.py`](eval/calibrate.py) 66 noktalık ızgarayı
tarayıp takas eğrisini çıkarır ve noktayı veriyle seçer.

CI'da [`--gate`](eval/evaluate.py) metrikler eşiğin altına düşerse build'i kırar.
Testler bozuk kodu yakalar; sessizce on puan recall kaybettiren bir prompt
değişikliğini yakalayamaz.

### 5. Kaynaklılık denetimi devre kesici olarak

Gerçek donanımda yapılan kontrollü bir deney, tasarımı değiştirdi:

| İstem | `qwen2.5-0.5b` çıktısı |
|---|---|
| İngilizce sistem + İngilizce soru | Tutarlı ve doğru |
| İngilizce sistem + Türkçe soru | Bozuk Türkçe, tek çarpık cümle |
| Türkçe sistem + Türkçe soru | **Anlamsız kelime salatası** |

Model çalışıyor; sorun Türkçe. 0.5B'lik bir model tutarlı Türkçe üretemiyor
(`qwen3-1.7b` daha da kötüydü). Aynı korpusta **getirme %97 doğrulukta.** Yani
zayıf halka arama değil, üretim.

Bu yüzden [`extractive.py`](src/foundry_rag/extractive.py) var:
`answer_mode="auto"` (varsayılan) önce üretir, sonra kaynaklılığı ölçer, ve
cevap kendi bağlamı tarafından desteklenmiyorsa **belgelerden doğrudan alıntıya
düşer.** Ölçüm zaten güvenilmez olduğunu söylediği bir metni kullanıcıya
göstermek yerine kaynağı gösterir.

```
Kaynaklilik: %0 (0/15 cumle dayanakli)  [mod: extractive-fallback]
```

Daha kötü bir okuma deneyimi, çok daha iyi bir bilgi. `FRAG_ANSWER_MODE` ile
`generative` veya `extractive` olarak sabitlenebilir.

### Ölçülen etki

33 soruluk set, `top_k=4`. Her iki eksende birden iyileşme — recall, reddetmeden
çalınarak elde edilmiş değil.

**Çevrimdışı `hashing` backend** (CI'da çalışan, bağımlılıksız yedek):

| | Dense-only, tahmini eşik | Hibrit + kalibre | |
|---|---|---|---|
| Recall@4 | %72.0 | **%88.0** | +16 puan |
| MRR | 0.650 | **0.793** | +0.14 |
| Reddetme doğruluğu | %87.5 | **%100.0** | +12.5 puan |
| **Genel doğruluk** | **%75.8** | **%90.9** | **+15.1 puan** |

**Gerçek `foundry` backend** (`qwen3-embedding-0.6b`, 1024 boyut, macOS M-series):

| | Değer |
|---|---|
| Recall@4 | **%96.0** |
| MRR | **0.960** |
| Reddetme doğruluğu | **%100.0** |
| **Genel doğruluk** | **%97.0** |
| Ortalama getirme süresi | 0.33 sn |

> **Eşik modele bağlıdır.** Optimum `min_similarity` hashing için `0.30`,
> Foundry embedding modeli için `0.40` çıktı. Kodda varsayılan `0.30` (testler ve
> CI çevrimdışı backend kullanıyor). Foundry Local kullanıyorsan:
> ```bash
> export FRAG_MIN_SIMILARITY=0.40
> ```
> Bilgi tabanını veya modeli değiştirdiğinde `python eval/calibrate.py` ile
> yeniden kalibre et. Bu, projenin en çok tekrarlanan dersidir.

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

**macOS** — sistem Python'u (3.9) ile çalışmaz, sebebi aşağıda:

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

**Windows (PowerShell)** — `python` komutu Microsoft Store'a gidebilir, `py -3.12` kullanın:

```powershell
# 1) Modern Python
winget install Python.Python.3.12
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned   # Activate.ps1 aksi halde engellenir
.venv\Scripts\Activate.ps1

# 2-5) Gerisi aynı
pip install -r requirements.txt
python scripts\doctor.py
python -m app.cli ingest
python -m app.cli chat
```

Ayrıntılı rehberler: [macOS](docs/SETUP_MACOS.md) · [Windows](docs/SETUP_WINDOWS.md)

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
python -m pytest tests/ -q             # 163 test, çevrimdışı, ~0.3 sn
python eval/evaluate.py                # sadece getirme kalitesi (hızlı)
python eval/evaluate.py --generate     # cevapları da üret (yavaş)
python eval/evaluate.py --gate         # CI kalite kapısı: regresyonda exit 1
python eval/calibrate.py               # eşikleri veriden seç
FRAG_HYBRID=0 python eval/evaluate.py  # hibrit kapalı — karşılaştırma tabanı
```

Değerlendirme seti 33 sorudan oluşur: **25 cevaplanabilir + 8 cevaplanamaz**.
Cevaplanamaz sorular kasıtlıdır — bir RAG sisteminin en tehlikeli hatası,
bilmediği bir konuda kendinden emin şekilde uydurmasıdır. Ölçülen metrikler:

| Metrik | Neyi ölçer |
|---|---|
| `Recall@K` | Doğru kaynak ilk K parça içinde geldi mi? |
| `MRR` | Doğru kaynak kaçıncı sırada geldi? (1. sıra > 5. sıra) |
| Reddetme doğruluğu | Cevaplanamaz sorularda "bilmiyorum" dedi mi? |
| `balanced` | Recall ile reddetmenin harmonik ortalaması |

Son metrik kasıtlı olarak harmonik ortalamadır: aritmetik ortalama alınsaydı,
her soruyu cevaplayıp hiçbirini reddetmeyen bir sistem %50 alırdı. Harmonik
ortalama, iki taraftan biri feda edilirse sıfıra gider.

Skorlar `hashing` backend içindir; bu backend anlamsal değil kelime örtüşmesine
dayalı çalışır, dolayısıyla gerçek embedding modelinin **alt sınırıdır**.
İkisini karşılaştırmak Hafta 4'ün alıştırmalarından biridir.

---

## Proje yapısı

```
src/foundry_rag/
  config.py          Ayarlar (Settings), FRAG_* ortam değişkenleri
  chunking.py        Belge parçalama — başlık duyarlı, örtüşmeli
  store.py           SQLite katmanı, float32 BLOB vektör saklama
  turkish.py         Türkçe normalizasyon, ek ayıklama, gövde genişletme
  lexical.py         BM25 indeksi ve doyum fonksiyonu
  retrieval.py       Kosinüs benzerliği, RRF füzyonu, hibrit arama
  groundedness.py    Cevap denetimi — dayanaksız cümle tespiti
  extractive.py      Alıntıya dayalı cevap ve devre kesici geri çekilmesi
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
eval/
  questions.json     33 soru (25 cevaplanabilir + 8 cevaplanamaz)
  evaluate.py        Recall@K, MRR, reddetme doğruluğu + CI kalite kapısı
  calibrate.py       Eşik taraması — takas eğrisi ve optimum nokta
tests/               163 test (hepsi çevrimdışı, ~0.3 sn)
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

Ayrıca: Kurulum ([macOS](docs/SETUP_MACOS.md) · [Windows](docs/SETUP_WINDOWS.md)) ·
[Mimari](docs/ARCHITECTURE.md) · [Sorun giderme](docs/TROUBLESHOOTING.md)

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
  Windows'ta hem x64 hem ARM64 desteklenir.
- Apple Silicon'da hızlandırma **ONNX Runtime WebGPU (Dawn → Metal)** üzerindendir;
  CoreML veya Neural Engine **kullanılmaz**. Aksini söyleyen kaynaklar yanlıştır.
  Windows'ta seçim donanıma göre yapılır (CUDA / NPU / CPU).
- **Ölçülmüş sayılar macOS arm64'te üretildi.** Getirme, füzyon ve denetim katmanları
  saf Python + numpy olduğu için platformdan bağımsızdır (CI Ubuntu'da koşuyor), ama
  hangi model varyantının seçileceği donanıma bağlıdır. Başka bir platformdaysanız
  `python eval/calibrate.py` ile eşiği kendi makinenizde ölçün.
- `brew install foundrylocal` **önerilmez**: tap yaklaşık 6 ay eskidir ve embedding
  desteği gelmeden önceki sürümü kurar. Bu proje CLI'ye ihtiyaç duymaz — SDK 1.x
  çalışma zamanını kendi içinde taşır. Windows'ta da
  `winget install Microsoft.FoundryLocal` gerekmez.
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
