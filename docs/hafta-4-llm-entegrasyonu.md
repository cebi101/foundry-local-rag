# Hafta 4 -- Yerel LLM Entegrasyonu ve Uygulama Bütünleştirme

**Faz 2: Proje Geliştirme** | Yaz okulu, tam zamanlı

Hafta 3'te sistem, soruya en yakın parçaları bulabiliyordu ama cevabı bir dil modeli
yazmıyordu: `HashingBackend` bağlamdaki cümleleri skorlayıp doğrudan alıntılıyordu.
Bu hafta o boşluğu dolduruyoruz. Sonunda cevabı **cihazında çalışan gerçek bir model**
yazacak ve bunun getirme kalitesine, reddetme davranışına ve gecikmeye etkisini
sayıyla göstereceksin.

Bu haftanın sonunda elinde şunlar olacak:

- Foundry Local ile uçtan uca çalışan bir asistan (`--backend foundry`)
- `hashing` ile `foundry` backend'lerini yan yana koyan bir **karşılaştırma tablosu**
- Sistem isteminin ve sıcaklığın davranışa etkisine dair kendi ölçümlerin
- Sunulabilir bir Streamlit demosu

Bu haftanın en önemli dersi tek cümlede: **getirmenin doğru olması üretimin
doğru olduğu anlamına gelmez.** Bu iki yarı ayrı ayrı ölçülür, ayrı ayrı bozulur
ve bu hafta ikisini de kendi makinende ölçeceksin.

---

## 1. Ön koşullar

```bash
cd ~/Desktop/foundry-local-rag
source .venv/bin/activate
python --version                 # 3.11 veya üstü olmalı
python scripts/doctor.py
python -m pytest tests/ -q       # 163 test, hepsi geçmeli
python -m app.cli info           # Hafta 3'ten kalan indeks
```

Hafta 3'ün tabloları (`hashing`, `top_k=4`, deponun varsayılan hibrit getirmesi,
`min_similarity=0.30`) bu haftanın karşılaştırma zeminidir:

| Metrik | Değer |
| --- | --- |
| Recall@4 | %88.0 |
| MRR | 0.793 |
| Reddetme doğruluğu | %100.0 |
| Genel doğruluk | %90.9 |

`eval/results.jsonl` dosyasını silme; bu hafta yanına yeni koşular ekleyeceksin.

> **Bu hafta Foundry Local şart.** Hafta 3'te `--backend hashing` ile her şeyi
> yapabiliyordun, bu hafta yapamazsın. Ortam kurulumu tıkanırsa A4.1'i bitirmeden
> diğer alıştırmalara geçme; A4.3 ve A4.4 iki backend'in karşılaştırılmasıdır.

> **Eşiği daha ilk komuttan doğru kur.** `config.py`'daki varsayılan
> `min_similarity=0.30`, **hashing** backend'i üzerinde kalibre edilmiş bir
> değerdir (testler ve CI çevrimdışı backend kullandığı için). Foundry Local ile
> ölçülen argmax **0.40**'tır. Bu haftaki foundry koşularında:
>
> ```bash
> export FRAG_MIN_SIMILARITY=0.40
> ```
>
> Neden farklı olduğunu A4.3'te ölçeceksin. `.env.example` bu iki değeri ve
> gerekçesini zaten yazıyor.

---

## 2. Bu haftanın haritası

| Dosya | Bu hafta ne yapıyor |
| --- | --- |
| `src/foundry_rag/backends/base.py` | `Backend` soyut sınıfı: `embed()`, `chat()`, `embedding_dim` |
| `src/foundry_rag/backends/foundry.py` | `FoundryBackend` -- SDK 1.x, model indirme/yükleme, streaming |
| `src/foundry_rag/backends/__init__.py` | `create_backend()` -- `auto` / `foundry` / `hashing` seçimi |
| `src/foundry_rag/prompts.py` | `SYSTEM_PROMPT` (5 kural), `build_messages()` |
| `src/foundry_rag/pipeline.py` | `RagPipeline.answer()` ve `.stream_answer()` |
| `src/foundry_rag/groundedness.py` | `check()` -- cevabın her cümlesini getirilen pasajlarla doğrular |
| `src/foundry_rag/extractive.py` | `extract_answer()` -- üretim çöp çıkarsa devreye giren alıntı yolu |
| `src/foundry_rag/config.py` | `temperature`, `max_tokens`, `chat_model`, `embedding_model`, `answer_mode` |
| `app/cli.py` | `chat` alt komutu -- akışlı çıktı; `_print_groundedness()` |
| `app/streamlit_app.py` | Web arayüzü, `st.cache_resource` ile tekil pipeline |

Sorgu akışının tamamı (`RagPipeline.answer()`, `pipeline.py`):

```
soru
  -> backend.embed([soru])[0]                 embedding modeli
  -> hybrid_search(records, matrix, vektor, query_text=soru, bm25=...,
                   top_k, min_similarity, lexical_scale)   kosinus + BM25, RRF
  -> hits bos mu?  EVET -> NO_CONTEXT_ANSWER dondur, MODELI HIC CAGIRMA
                   HAYIR
  -> answer_mode == "extractive" ?  EVET -> extractive.extract_answer(...)
                                    HAYIR
  -> build_messages(soru, hits, language)     system + user mesaji
  -> backend.chat(messages, temperature, max_tokens)   sohbet modeli
  -> check_groundedness ise: groundedness.check(text, hits)   MODEL CAGIRMAZ
  -> answer_mode == "auto" ve rapor.score < min_groundedness (0.34) ?
       EVET -> uretilen cevabi AT, extract_answer(..., FALLBACK_NOTICE) koy
               mode = "extractive-fallback"
       HAYIR -> uretilen cevabi dondur, mode = "generative"
  -> Answer(text, hits, retrieval_seconds, generation_seconds,
            groundedness, mode)
```

Hafta 3 bu şemanın ilk üç satırıyla ilgiliydi. Bu haftanın tamamı geri kalanı:
model çağrısı, denetim ve devre kesici.

---

## 3. Teori

### 3.1 Tek paket adı, iki uyumsuz SDK nesli

`foundry-local-sdk` adı altında birbirine hiç benzemeyen iki API yayınlanıyor
(`src/foundry_rag/backends/foundry.py` dosya başlığındaki tabloyla aynı):

| Sürüm | Import | Python | Nasıl çalışır |
| --- | --- | --- | --- |
| 0.x (eski) | `from foundry_local import ...` | herhangi | HTTP istemcisi, PATH'te `foundry` CLI ister |
| 1.x (güncel) | `from foundry_local_sdk import ...` | **>= 3.11** | süreç içi (in-process) yerel çekirdek, CLI yok, sunucu yok |

Bu proje 1.x hedefler. Tuzak şu: macOS 14.6'nın sistem Python'u 3.9.6'dır ve orada
`pip install foundry-local-sdk` **hata vermez**, pip `requires_python` alanına bakıp
sessizce eski **0.5.1** sürümünü kurar. Sonra `foundry_local_sdk` import'u
`ImportError` verir ve saatler kaybedilir.

`_import_sdk()` bu iki durumu ayrı ayrı yakalar ve çözümü metin olarak yazdırır:

- Python < 3.11 ise: `BackendUnavailable`, çözüm `brew install python@3.12` + venv
- `foundry_local` modülü varsa: "LEGACY 0.x kurulu" mesajı, çözüm `pip install --upgrade 'foundry-local-sdk>=1.2'`

Kurulum üç kuralla özetlenir:

- [ ] Python **3.11+** (öneri: `brew install python@3.12`; numpy 2.5 artık 3.11'i desteklemiyor, 3.12 tatlı nokta)
- [ ] macOS **arm64** (Apple Silicon). Intel Mac için hiçbir build yok. Minimum macOS 14.0.
- [ ] `foundry` CLI kurma. SDK 1.x çalışma zamanını kendi içinde taşır.

Kurmaman gereken iki şey:

| Komut | Ne olur |
| --- | --- |
| `brew tap microsoft/foundrylocal` + `brew install foundrylocal` | Tap yaklaşık 6 ay eski; `v0.8.119` kurar. Bu sürüm embedding desteğinden (minFLVersion 1.1.0) **önceki** sürümdür, yani `qwen3-embedding-0.6b`'yi katalogda göremez. CLI gerçekten gerekiyorsa GitHub releases'ten `.pkg` al. |
| `brew install foundry` | Tamamen başka bir yazılım kurar (Ethereum aracı). |

### 3.2 SDK 1.x yaşam döngüsü

Doğrulanmış çağrı sırası:

```python
from foundry_local_sdk import Configuration, FoundryLocalManager

FoundryLocalManager.initialize(Configuration(app_name="foundry_local_rag"))  # SINGLETON
manager = FoundryLocalManager.instance
manager.download_and_register_eps()

model = manager.catalog.get_model("qwen3-embedding-0.6b")   # alias ile
model.download(cb)          # cb: yuzdeyi alan callback
model.load()

emb = model.get_embedding_client()
emb.generate_embedding(text).data[0].embedding          # tek metin
[d.embedding for d in emb.generate_embeddings(texts).data]   # toplu

chat = chat_model.get_chat_client()
for chunk in chat.complete_streaming_chat(messages):
    chunk.choices[0].delta.content
```

`FoundryBackend` bu sırayı üç metoda böler:

| Metot | Sorumluluk |
| --- | --- |
| `_ensure_manager()` | Tekil (singleton) yöneticiyi bir kez kurar, EP'leri kaydeder |
| `_prepare_model(alias, label)` | Alias'ı çözer, gerekiyorsa indirir, `load()` eder, varyantı yazdırır |
| `_ensure_embedding_client()` / `_ensure_chat_client()` | İlgili istemciyi tembel (lazy) oluşturur |

**Tembellik önemli:** `create_backend()` yalnızca `backend.embedding_dim` özelliğini
okur, o da yalnızca embedding modelini yükler. Sohbet modeli ilk `chat()` /
`stream_chat()` çağrısına kadar indirilmez bile. Bunu A4.2'de doğrudan göreceksin:
`ingest` sırasında yalnızca embedding modeli iner, sohbet modeli ilk `ask`'te.

`download_and_register_eps()` çağrısı `try/except` içindedir ve hata verirse
**ölümcül değildir**. macOS'ta hızlandırma ONNX Runtime'ın **WebGPU** sağlayıcısı
üzerinden (Dawn -> Metal) gider; bu çağrı burada büyük ölçüde işlevsizdir.
Aksini söyleyen bloglar var: macOS'ta **CoreML kullanılmıyor**, **Apple Neural Engine
kullanılmıyor**.

### 3.3 Singleton problemi

`FoundryLocalManager` sert bir tekildir: ikinci `initialize()` çağrısı **hata verir**.
Bu, normal bir betikte hiç görünmez; şu üç durumda anında patlar:

- Streamlit -- her etkileşimde betiği baştan çalıştırır
- `uvicorn --reload` -- dosya değişince modülü yeniden yükler
- Jupyter -- aynı hücreyi ikinci kez çalıştırdığında

`foundry.py` içindeki korumanın tamamı şu:

```python
if getattr(FoundryLocalManager, "instance", None) is None:
    FoundryLocalManager.initialize(Configuration(**kwargs))
self._manager = FoundryLocalManager.instance
```

Yani "önce var mı diye bak, yoksa kur". Streamlit tarafında ikinci bir kat koruma
daha var (`app/streamlit_app.py`):

```python
@st.cache_resource(show_spinner=False)
def load_pipeline(backend: str, top_k: int, min_similarity: float) -> RagPipeline:
    ...
```

`cache_resource` burada sadece hız için değil: pipeline her yeniden çalıştırmada
sıfırdan kurulsaydı model her seferinde yeniden yüklenir ve tekil yönetici sorunu
kaçınılmaz olurdu.

### 3.4 Alias, donanım varyantı ve #858

`manager.catalog.get_model("qwen3-embedding-0.6b")` çağrısındaki metin bir **alias**'tır,
dosya adı değil. Aynı alias arkasında birden fazla derleme (varyant) bulunur:
`generic-cpu`, `generic-gpu` gibi. Hangisinin geleceği donanıma ve kayıtlı execution
provider'a bağlıdır ve **alias listesi donanıma göre değişir**.

Bunun iki pratik sonucu var:

1. Bir alias'ın senin makinende var olduğunu **varsayamazsın**. `Phi-4-mini-instruct-generic-cpu`
   arm64'te Microsoft'un kendi blocklist'i yüzünden desteklenmiyor; `deepseek-r1-1.5b`'nin
   Mac varyantı hiç yok. `list_aliases()` ve `python scripts/doctor.py` tek doğru kaynaktır.
2. GPU execution provider doğru kaydolsa bile bazen yalnızca CPU varyantları görünür
   (microsoft/Foundry-Local **#858 / #895**, ikisi de açık). Hiçbir uyarı almazsın,
   sadece yavaş çalışırsın.

`describe_variant()` bunun için var:

```python
model_id = getattr(model, "id", "?")
runtime = getattr(getattr(model, "info", None), "runtime", None)
provider = getattr(runtime, "execution_provider", None) if runtime else None
device = getattr(runtime, "device_type", None) if runtime else None
```

`_prepare_model()` sonucu `load()` sonrasında `  embedding: <model.id> [<device> / <provider>]`
biçiminde yazdırır. Bu satır bu haftanın en önemli çıktısıdır: yüklenen derlemenin
CPU mu GPU mu olduğunu öğrenmenin başka yolu yok.

Model boyutları (canlı katalogdan doğrulandı):

| Alias | Rol | İndirme |
| --- | --- | --- |
| `qwen3-embedding-0.6b` | embedding, **1024 boyut**, 32K bağlam, 100+ dil | ~520-541 MB |
| `qwen2.5-0.5b` | sohbet (varsayılan) -- **Türkçede kullanılamaz**, bkz. `docs/TROUBLESHOOTING.md` 16. bölüm | ~735 MB (gpu) / ~862 MB (cpu) |
| `qwen3-1.7b` | sohbet, daha büyük | ~1490 MB |
| `qwen3-4b` | sohbet, en büyük | ~3083 MB |

İlk çalıştırmada iki varsayılan model + yerel kütüphaneler toplamda yaklaşık
**1.3 GB indirme + ~146 MB yerel kütüphane** demektir. Hiçbir modelde EULA/lisans
onay kapısı yok; hepsi MIT veya Apache-2.0. "Çevrimdışı" ifadesi **ilk çalıştırmadan
sonrası** için geçerlidir: katalog ve model dosyaları ilk kullanımda ağdan çekilir.

### 3.5 Streaming ve açık hata #905

Akışlı üretim iki şey kazandırır: kullanıcı ilk kelimeyi 20 saniye beklemez, ve
model yanlış yola saptığında iptal edebilirsin.

CLI'daki tüketici (`app/cli.py`, `cmd_chat`):

```python
for fragment in rag.stream_answer(question):
    print(fragment, end="", flush=True)
```

Üretici (`FoundryBackend.stream_chat`) iki savunma içerir.

**Birincisi -- örnekleme parametreleri.** `complete_streaming_chat`'in `temperature`
ve `max_tokens` kabul edip etmediği belgelenmemiş. Kod varsayım yapmaz, dener:

```python
try:
    stream = client.complete_streaming_chat(payload, temperature=temperature, max_tokens=max_tokens)
except TypeError:
    stream = client.complete_streaming_chat(payload)
```

`TypeError` düşerse parametreler **sessizce düşer**. A4.5'te ilk yapacağın şey bunu
kontrol etmek olacak.

**İkincisi -- boş chunk.** Akışın son parçası bazen boş bir `choices` listesiyle gelir.
Microsoft'un kendi RAG tutorial'ındaki döngü buna indeksliyor ve cevabı ekrana
bastıktan **hemen sonra** `IndexError` ile çöküyor (microsoft/Foundry-Local **#905**,
açık, 2026-07-25). Bu repodaki koruma:

```python
for chunk in stream:
    if not getattr(chunk, "choices", None):
        continue
    delta = getattr(chunk.choices[0], "delta", None)
    content = getattr(delta, "content", None) if delta else None
    if content:
        yield content
```

`RagPipeline.stream_answer()` ayrıca `stream_chat` metodu olmayan backend'ler için
`chat()`'e düşer (`getattr(self.backend, "stream_chat", None)`); `HashingBackend`
akış desteklemez, bu yüzden CLI onunla da çalışır.

### 3.6 Sıcaklık (temperature) ve `max_tokens`

Sıcaklık, bir sonraki token seçilirken olasılık dağılımının ne kadar düzleştirileceğini
belirler. Düşük sıcaklık dağılımı sivrileştirir: en olası token neredeyse her zaman
seçilir, çıktı tekrarlanabilir olur. Yüksek sıcaklık düşük olasılıklı tokenlara da
şans verir: çeşitlilik artar, uydurma riski de artar.

Varsayılanlar (`config.py`):

| Ayar | Varsayılan | Ortam değişkeni |
| --- | --- | --- |
| `temperature` | `0.1` | `FRAG_TEMPERATURE` |
| `max_tokens` | `600` | `FRAG_MAX_TOKENS` |
| `chat_model` | `qwen2.5-0.5b` | `FRAG_CHAT_MODEL` |
| `embedding_model` | `qwen3-embedding-0.6b` | `FRAG_EMBEDDING_MODEL` |
| `device` | `auto` | `FRAG_DEVICE` (`auto` / `cpu` / `gpu`) |
| `check_groundedness` | `True` | `FRAG_CHECK_GROUNDEDNESS` |
| `answer_mode` | `auto` | `FRAG_ANSWER_MODE` (`auto` / `generative` / `extractive`) |
| `min_groundedness` | `0.34` | `FRAG_MIN_GROUNDEDNESS` |
| `answer_language` | `Türkçe` | `FRAG_ANSWER_LANGUAGE` |

RAG'de sıcaklık **düşük** olmalıdır, ve `0.1` bu yüzden seçilmiştir. Görev "verilen
metinden cevabı çıkar ve kaynağını yaz"dır; yaratıcılık istenmiyor. Sıcaklığı
yükseltmek burada yalnızca aynı soruya farklı cevaplar üretme ihtimalini artırır --
kullanıcı açısından bu "iyileşme" değil, **güvenilmezlik**tir.

### 3.7 Sistem istemi tasarımı

`prompts.py` bu projedeki en yüksek kaldıraçlı dosyadır. Beş kural işi taşır:

| # | Kural | Neyi engeller |
| --- | --- | --- |
| 1 | Sadece "BAĞLAM" bölümündeki metni kullan, genel bilgini kullanma | Modelin eğitim verisinden cevap uydurmasını |
| 2 | Cevap bağlamda yoksa tam olarak "Bu bilgi elimdeki belgelerde yok." de | Alakasız bağlamdan zorlama cevap üretmeyi |
| 3 | Her iddianın sonunda kaynağı köşeli parantezle belirt | Denetlenemez cevapları |
| 4 | Kısa ve net yaz, giriş cümlesi kurma | Bağlam penceresini ve kullanıcının zamanını israf etmeyi |
| 5 | Cevabını `{language}` dilinde ver | Türkçe soruya İngilizce cevap dönmesini |

Üç tasarım kararı kodda görünür:

**Kural 2'nin metni tesadüf değil.** `NO_CONTEXT_ANSWER` sabiti ile birebir aynı
cümledir ve `eval/evaluate.py` içindeki `REFUSAL_MARKERS` bu cümleyi arar. İsteme
"bilmiyorum de" yazıp değerlendirmede başka bir kalıp aramak, ölçülemeyen bir kural
demektir.

**Bağlam sorudan önce gelir.** `build_user_prompt()` sırayla `BAĞLAM:` bloğunu,
`---` ayracını, sonra `SORU:` satırını yazar. Model önce malzemeyi okur, sonra
ne yapması istendiğini öğrenir.

**Her pasaj kaynağıyla etiketlenir.** `format_context()` her parçanın başına
`[n] Kaynak: dosya.md | Bölüm: başlık` satırını koyar. Kural 3'ün uygulanabilir
olması için modelin alıntılayacak bir şeyi olmalı.

Listeyi uzatma isteğine direnç göster. Küçük yerel modellerde uzun kural listesi
bağlam penceresini yer ve dikkati dağıtır; A4.4'te kural **çıkarmanın** etkisini
ölçeceksin, ama tersinin de bedeli var.

### 3.8 Backend seçimi ve indeks imzası

`create_backend()` üç seçeneği yönetir:

| `--backend` | Davranış | Ne zaman |
| --- | --- | --- |
| `foundry` | Foundry Local zorunlu, yoksa gürültülü hata | Ortam kurulduktan sonra, ölçüm yaparken |
| `hashing` | Her zaman çevrimdışı yedek | Testler, karşılaştırma zemini |
| `auto` (varsayılan) | Foundry Local'i dene, olmazsa `hashing`'e düş | İlk gün, kurulum bitmeden |

`auto` düşerken **her zaman** stderr'e uyarı basar. Kullanıcının istediğinden çok
daha zayıf bir modelle sessizce cevap vermek, bu projede kabul edilmeyen tek şeydir.

Backend değiştirdiğinde **yeniden indekslemek zorundasın**. `embedding_signature`
`hashing-offline:512` iken `foundry-local:qwen3-embedding-0.6b:1024` olur ve
`RagPipeline._check_index()` çalışmayı reddeder:

```
Indeks farkli bir embedding modeliyle olusturulmus.
```

Bu hafta boyunca kural: **her backend değişikliğinden sonra `ingest`.**

---

## 4. Alıştırmalar

Her alıştırmanın çıktısını `docs/hafta-4-sonuclarim.md` adlı kendi dosyanda topla.
Teslim edeceğin şey o dosya.

### A4.1 -- Foundry Local'i kur ve katalogu doğrula

**Amaç:** Model indirmeye başlamadan önce ortamın gerçekten hazır olduğunu kanıtlamak.

1. `docs/SETUP_MACOS.md` dosyasını baştan sona uygula. Özet kontrol listesi:

- [ ] `uname -m` çıktısı `arm64`
- [ ] `sw_vers -productVersion` çıktısı 14.0 veya üstü
- [ ] `python --version` çıktısı 3.11+ ve venv aktif
- [ ] `pip install -r requirements.txt` hatasız bitti
- [ ] `foundry` CLI **kurmadın** (gerekmiyor)

2. Ortam kontrolünü çalıştır:

```bash
python scripts/doctor.py
```

3. Çıktının dört bölümünü de kaydet. `--- Foundry Local katalogu ---` bölümünde
   şu üç satırı arıyorsun:

```
  [ok]  katalogda <N> model var
  [ok]  sohbet modeli 'qwen2.5-0.5b': bulundu
  [ok]  embedding modeli 'qwen3-embedding-0.6b': bulundu
```

`BULUNAMADI` görürsen `doctor.py` o donanımdaki ilk 15 alias'ı listeler; listeyi
sonuç dosyana yapıştır. `foundry-local-sdk 0.x` uyarısı görürsen `_import_sdk()`'nın
tarif ettiği yükseltmeyi yap ve `doctor.py`'yi tekrar çalıştır.

4. Şu soruları yazılı cevapla:
   - `doctor.py` katalogu okurken **model indiriyor mu**? (`check_foundry_catalog()`
     hangi metodu çağırıyor, o metot ne yapıyor?)
   - `sqlite ... / uzanti yukleme: False` uyarısı aldın mı? Bu proje için neden
     sorun değil?

**Teslim:** tam `doctor.py` çıktısı + iki sorunun cevabı.

### A4.2 -- İlk indirme ve varyant tespiti

**Amaç:** Modelleri indirmek, süreyi ölçmek ve hangi donanım varyantının yüklendiğini
çıktıdan okumak.

1. Foundry backend ile indeksle. `time` ile süreyi ölç:

```bash
time python -m app.cli --backend foundry ingest
```

`_prepare_model()` indirme sırasında yüzde basar, `load()` sonrasında da şu biçimde
bir satır yazar:

```
  embedding: <model.id> [<device_type> / <execution_provider>]
```

2. **Beklentiyi doğru kur.** `ingest` yalnızca embedding modelini indirir
   (~520-541 MB), çünkü `create_backend()` sadece `backend.embedding_dim`'i okur ve
   bu da yalnızca `_ensure_embedding_client()`'ı tetikler. Sohbet modeli ilk soruda
   iner:

```bash
time python -m app.cli --backend foundry ask "RAG kısaltması hangi üç adımdan gelir?"
```

Bu adımda `  chat: ...` satırını göreceksin (~735 MB gpu / ~862 MB cpu). İki adımın
toplamı yaklaşık **1.3 GB indirme + ~146 MB yerel kütüphane** eder.

3. Tabloyu doldur:

| Adım | Süre | İnen boyut | Yazdırılan `model.id` | `device_type` / `execution_provider` |
| --- | --- | --- | --- | --- |
| `ingest` (embedding) | | | | |
| İlk `ask` (sohbet) | | | | |
| İkinci `ask` (önbellekten) | | 0 | | |

4. `execution_provider` satırında CPU görüyorsan bu **muhtemelen açık hata
   #858 / #895**'tir: GPU EP doğru kaydolsa bile bazen yalnızca CPU varyantları
   görünür ve sistem sessizce yavaş çalışır. Gördüğünü olduğu gibi not et, uydurma.
5. İkinci `ask` çağrısının süresini birinciyle karşılaştır. Aradaki farkın ne kadarı
   indirme, ne kadarı model yükleme? (`_prepare_model()` içinde `is_cached` kontrolüne
   bak.)
6. `python -m app.cli info` çıktısındaki `embedding_signature` satırını kaydet.
   Beklenen biçim: `foundry-local:qwen3-embedding-0.6b:1024`.

> **İndirme sırasında bilgisayarı uyutma.** Açık hatalar **#909 / #906**: uyku modu
> bozuk model önbelleği bırakabiliyor ve önbellek bütünlük doğrulaması yok. İndirme
> yarıda kalıp tuhaf hatalar alırsan ilk şüphelenilecek şey budur.

**Teslim:** doldurulmuş tablo + `info` çıktısı + varyant gözlemin.

### A4.3 -- İki backend'i aynı eval ile karşılaştır

**Amaç:** Gerçek embedding modelinin getirme kalitesine katkısını 33 soruluk sabit
sette ölçmek.

Değerlendirme seti: **25 cevaplanabilir** (`q..`) + **8 cevaplanamaz** (`u01`-`u08`,
`expected_source` alanı `null`). `recall_at_k` yalnızca birinci gruptan,
`refusal_accuracy` yalnızca ikinci gruptan hesaplanır.

1. `hashing` zeminini tazele (Hafta 3'te ölçtüysen sayılar aynı çıkmalı):

```bash
python -m app.cli --backend hashing ingest
python eval/evaluate.py --backend hashing
```

2. Foundry ile **yeniden indeksle** ve aynı eval'i koştur:

```bash
python -m app.cli --backend foundry ingest
python eval/evaluate.py --backend foundry
```

Yeniden indeksleme atlanamaz: vektör uzayı 512 boyuttan 1024 boyuta geçiyor.

3. Karşılaştırma tablosunu doldur (`top_k=4`, `min_similarity=0.30`, üretim kapalı):

| Metrik | `hashing-offline` | `foundry-local` | Fark |
| --- | --- | --- | --- |
| Recall@4 | %88.0 | | |
| MRR | 0.793 | | |
| Reddetme doğruluğu | %100.0 | | |
| Genel doğruluk | %90.9 | | |
| Ortalama süre / soru | | | |

4. Aynı iki koşuyu `--generate` ile tekrarla ve **ayrı bir tabloya** yaz. Neden ayrı:
   `--generate` olmadan `refusal_accuracy` yalnızca "hiç parça dönmedi mi" sorusunu
   ölçer (`evaluate_one()` içindeki `result.refused = (not hits) or ...` satırı);
   `--generate` ile cevabın metnine de bakılır. İki modun sayılarını aynı tabloda
   karıştırma.

```bash
python eval/evaluate.py --backend foundry --generate
```

> Foundry + `--generate` 33 soruda 33 model çağrısı demektir ve dakikalar sürer.
> `avg_seconds` satırını not et; A4.6'daki demoda kullanıcıya ne kadar bekleteceğini
> bu belirliyor.

5. **"Fark neden bu kadar büyük?"** sorusunu somut kanıtla cevapla:
   - `hashing` koşusunda başarısız olup `foundry` koşusunda düzelen soruları listele.
     Bu soruların ortak özelliği ne? Sorudaki kelimeler beklenen belgede birebir
     geçiyor mu, yoksa eş anlamlı/yeniden ifade edilmiş mi?
   - `HashingBackend` semantik bir embedder **değildir**: `blake2b` ile kelime ve
     karakter n-gram'larını 512 boyutlu bir vektöre işaretli olarak hash'ler. Kelime
     örtüşmesi yoksa benzerlik yoktur. `qwen3-embedding-0.6b` ise 1024 boyutlu,
     100+ dilde eğitilmiş bir modeldir.
   - Ters yönü de ara: `foundry` koşusunda **bozulan** soru var mı? Varsa neden?
     (İpucu: `min_similarity=0.30` eşiği iki modelde aynı anlama gelmez; skor
     dağılımları farklıdır. Eşik `hashing` skorları üzerinde kalibre edildi --
     gerçek embedding modeline geçince `python eval/calibrate.py` ile yeniden
     kalibre edilmesi gerekir.)
   - Reddetme doğruluğu beklediğin gibi mi değişti? Daha iyi bir embedder,
     cevaplanamaz sorulara **daha yüksek** skor da verebilir; bu eşiği aşarsa
     reddetme düşer.

**Teslim:** iki tablo (üretim kapalı / açık) + düzelen ve bozulan soruların listesi
+ dört maddenin yazılı cevabı.

### A4.4 -- Sistem isteminden bir kural çıkar

**Amaç:** Tek bir istem satırının reddetme davranışına etkisini ölçmek.

Bu deneyde kodu **geçici olarak** bozacaksın. Geri almayı unutma.

1. Önce **ne kadar etki mümkün** olduğunu hesapla. `RagPipeline.answer()`, `hits`
   boşsa modeli **hiç çağırmaz** ve doğrudan `NO_CONTEXT_ANSWER` döner. Yani sistem
   isteminin reddetme üzerindeki etkisi, yalnızca eşiği geçen parça bulan
   cevaplanamaz sorularda görünür. Kaç tane olduğunu bul:

```bash
python eval/evaluate.py --backend foundry
```

Çıktıda `u01`-`u08` satırlarına bak: `skor` sütunu `0.000` olanlar hiç parça
döndürmemiş demektir. Kalanların sayısını yaz: **N = ?**

2. Taban çizgisini üretimle al:

```bash
python eval/evaluate.py --backend foundry --generate
```

3. `src/foundry_rag/prompts.py` içinde `SYSTEM_PROMPT`'un 2. kuralını **geçici olarak**
   sil:

```
2. Cevap bağlamda yoksa, tam olarak şunu söyle: "Bu bilgi elimdeki belgelerde yok."
   Tahmin yürütme, uydurma.
```

Kalan kuralları 1-2-3-4 diye yeniden numaralandır (numaralar bozuk kalırsa modelin
kafası karışır, ölçtüğün şey değişir).

4. Tekrar ölç. **Yeniden indekslemene gerek yok** -- istem yalnızca sorgu zamanını
   etkiler, embedding'lere dokunmaz:

```bash
python eval/evaluate.py --backend foundry --generate
```

5. Etkiyi büyütmek için eşiği düşürüp tekrarla. `min_similarity=0.0` ile her
   cevaplanamaz soru için de model çağrılır, yani kuralın etkisi 8 sorunun
   tamamında görünür:

```bash
python eval/evaluate.py --backend foundry --generate --min-similarity 0.0
```

6. Tabloyu doldur:

| İstem | `min_similarity` | Reddetme doğruluğu | Genel doğruluk | Anahtar kelime |
| --- | --- | --- | --- | --- |
| 5 kural (özgün) | 0.30 | | | |
| Kural 2 çıkarılmış | 0.30 | | | |
| 5 kural (özgün) | 0.0 | | | |
| Kural 2 çıkarılmış | 0.0 | | | |

7. Kural 2 yokken modelin cevaplanamaz sorulara ne yazdığına **gözünle bak**.
   `evaluate.py` çıktısındaki `BASARISIZ SORULAR` bölümünden iki örneği aynen
   sonuç dosyana kopyala. Model uydurdu mu, başka bir kalıpla mı reddetti?

8. **Kuralı geri koy** ve testleri çalıştır:

```bash
python -m pytest tests/ -q
```

`tests/test_prompts_and_backend.py::test_system_prompt_contains_the_five_rules`
istemde `"Bu bilgi elimdeki belgelerde yok."` cümlesini arar; geri koymayı
unutursan test kırmızı yanar.

9. Son soru: `evaluate.py` içindeki `REFUSAL_MARKERS` listesi
   (`"belgelerde yok"`, `"bilmiyorum"`, `"bilgi bulunmuyor"`, `"yeterli bilgi yok"`)
   ile sistem istemindeki tek cümle arasındaki bağı açıkla. Model "bu konuda bir şey
   diyemem" derse ölçüm ne gösterir? Bu, metriğin hangi zayıflığıdır?

**Teslim:** N sayısı + doldurulmuş tablo + iki örnek cevap + son sorunun cevabı.

### A4.5 -- Sıcaklığın tutarlılığa etkisi

**Amaç:** Aynı soruya verilen cevapların sıcaklıkla nasıl değiştiğini ölçmek.

1. **Önce parametrenin gerçekten geçtiğini doğrula.** `stream_chat()` içindeki
   `except TypeError` dalı, `complete_streaming_chat` örnekleme parametrelerini kabul
   etmiyorsa onları sessizce düşürür. `experiments/a45_signature.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import inspect

from foundry_rag.backends.foundry import FoundryBackend

backend = FoundryBackend(verbose=True)
client = backend._ensure_chat_client()
print(inspect.signature(client.complete_streaming_chat))
```

```bash
mkdir -p experiments
python experiments/a45_signature.py
```

İmzada `temperature` yoksa bu alıştırmanın sonucu "parametre bu SDK sürümünde
uygulanmıyor" olur. Bu da geçerli bir bulgudur; uydurma bir sonuç yazma.

2. Aynı soruyu iki sıcaklıkta üçer kez sor. Sıcaklık `FRAG_TEMPERATURE` ile geçer
   (`Settings.from_env()`), CLI'da ayrı bir bayrak yok:

```bash
for i in 1 2 3; do
  FRAG_TEMPERATURE=0.1 python -m app.cli --backend foundry ask \
    "Foundry Local macOS'ta hangi işlemci mimarisini destekler?" --no-sources
done

for i in 1 2 3; do
  FRAG_TEMPERATURE=0.9 python -m app.cli --backend foundry ask \
    "Foundry Local macOS'ta hangi işlemci mimarisini destekler?" --no-sources
done
```

3. Altı cevabı da sonuç dosyana **tam olarak** yapıştır ve şu tabloyu doldur:

| Sıcaklık | Koşu | Cevap uzunluğu (karakter) | Kaynak alıntısı var mı? | Önceki koşuyla aynı mı? | Bağlam dışı iddia var mı? |
| --- | --- | --- | --- | --- | --- |
| 0.1 | 1 | | | -- | |
| 0.1 | 2 | | | | |
| 0.1 | 3 | | | | |
| 0.9 | 1 | | | -- | |
| 0.9 | 2 | | | | |
| 0.9 | 3 | | | | |

4. Yorumla:
   - 0.1'de üç cevap birebir aynı mı? Değilse, sıcaklık 0 olmadığı için mi, yoksa
     başka bir kaynaktan mı belirsizlik geliyor?
   - 0.9'da 3. kural (kaynak belirtme) hâlâ tutuyor mu? Küçük modellerde ilk bozulan
     genellikle biçim kurallarıdır.
   - Bir kullanıcı destek asistanı için hangi sıcaklığı seçerdin? Bir "belgelerden
     yeni sınav sorusu üret" aracı için? Gerekçelendir.

5. İsteğe bağlı: `qwen2.5-0.5b` grounded (bağlama sadık) cevaplama için zayıftır.
   Elinde yer varsa `FRAG_CHAT_MODEL=qwen3-1.7b` (~1490 MB) ile 0.9 koşusunu
   tekrarla ve kural ihlallerinin azalıp azalmadığını not et. Sohbet modeli
   değiştiğinde **yeniden indekslemeye gerek yoktur** -- embedding modeli aynı kalır.

**Teslim:** imza çıktısı + altı cevap + doldurulmuş tablo + üç sorunun cevabı.

### A4.6 -- Streamlit demosu

**Amaç:** Uygulamayı sunulabilir hâle getirmek ve arayüzün pipeline'la ilişkisini
görmek.

1. Arayüzü çalıştır:

```bash
streamlit run app/streamlit_app.py
```

2. Kenar çubuğundaki üç kontrolü tanı (`app/streamlit_app.py`):
   - **Backend** seçimi: `auto` / `foundry` / `hashing`
   - **Getirilecek parça (top-k)**: 1-10, varsayılan 4
   - **Benzerlik eşiği**: 0.0-0.9, adım 0.05, varsayılan `Settings.min_similarity` (0.30)
   - Metrikler: indekslenmiş parça, belge sayısı, indeksin backend'i
   - **Belgeleri yeniden indeksle** düğmesi -- `ingest()` çağırır, sonra
     `st.cache_resource.clear()` ile pipeline önbelleğini boşaltır

3. Bilerek bir hata üret: indeks `foundry` ile kurulmuşken kenar çubuğundan
   `hashing`'i seç. Ekranda çıkan mesajı ekran görüntüsüyle kaydet ve hangi kod
   yolundan geldiğini yaz (`load_pipeline()` -> `RagPipeline._check_index()` ->
   `st.error(...)` + `st.stop()`).

4. Bir gözlem yap ve sonuç dosyana yaz: CLI'daki `chat` alt komutu cevabı **akışlı**
   basar (`stream_answer()`), Streamlit arayüzü ise `rag.answer()` çağırıp cevabı
   **tek parça** gösterir, bu sırada bir spinner döner. Kullanıcı deneyimi açısından
   fark neydi? A4.3'te ölçtüğün `avg_seconds` değeriyle birlikte değerlendir.

5. **Beş adımlık demo senaryosu hazırla** ve sonuç dosyana yaz. Zorunlu içerik:

| Adım | Ne gösteriliyor | Kullanılacak soru / eylem | Beklenen ekran |
| --- | --- | --- | --- |
| 1 | Sistem çevrimdışı çalışıyor | Kenar çubuğundaki backend ve indeks metrikleri | `foundry-local (chat=..., embed=..., dim=1024)` |
| 2 | Doğru cevap + kaynak | Cevabı `data/docs/` içinde net geçen bir soru | Cevap + "Kaynaklar" açılır bloğu, benzerlik skorları |
| 3 | Reddetme | `eval/questions.json` içinden bir `u..` sorusu | "Bu bilgi elimdeki belgelerde yok." |
| 4 | Bir ayarın etkisi | Eşiği 0.30'dan 0.6'ya çek, aynı soruyu tekrar sor | Daha az parça veya reddetme |
| 5 | Denetlenebilirlik | "Kaynaklar" bloğunu aç, alıntılanan parçanın tam metnini göster | Parça metni + `citation` |

6. Demoyu bir arkadaşına 5 dakikada anlat. Takıldığı ilk yeri not et; bu, Hafta 6'daki
   sunum için en değerli geri bildirimdir.

**Teslim:** hata mesajının ekran görüntüsü + 4. maddedeki gözlem + doldurulmuş
5 adımlık senaryo tablosu.

---

## 5. Haftanın çıktı kriteri

Aşağıdakilerin hepsi sağlanmalı:

- [ ] `python scripts/doctor.py` çıktısında `qwen3-embedding-0.6b` ve `qwen2.5-0.5b`
      **bulundu** yazıyor.
- [ ] `python -m app.cli info` çıktısında `embedding_signature` satırı
      `foundry-local:qwen3-embedding-0.6b:1024` biçiminde.
- [ ] `python -m app.cli --backend foundry ask "..."` gerçek bir dil modelinden gelen,
      kaynak belirten bir cevap üretiyor.
- [ ] `python -m app.cli --backend foundry chat` akışlı çalışıyor ve `IndexError`
      vermeden bitiyor.
- [ ] `docs/hafta-4-sonuclarim.md` içinde A4.3'ün **karşılaştırma tablosu** dolu
      (hashing vs foundry, 4 metrik).
- [ ] A4.4 ve A4.5 tabloları dolu.
- [ ] `eval/results.jsonl` içinde bu haftadan en az **6 koşu** kaydı var.
- [ ] `prompts.py` üzerindeki geçici A4.4 değişikliği **geri alınmış** ve
      `python -m pytest tests/ -q` 163 testle yeşil.
- [ ] Streamlit demosu 5 adımıyla hazır.

---

## 6. Sık yapılan hatalar

| Belirti | Sebep | Çözüm |
| --- | --- | --- |
| `Foundry Local SDK 1.x requires Python >= 3.11` | venv sistem Python'uyla (3.9.6) kurulmuş | `brew install python@3.12`, yeni venv, `pip install -r requirements.txt` |
| `Found the LEGACY foundry-local-sdk 0.x (module 'foundry_local')` | pip 3.9 altında 0.5.1'i kurmuş | 3.11+ ortamında `pip install --upgrade 'foundry-local-sdk>=1.2'` |
| `Model alias 'qwen3-embedding-0.6b' is not in the catalog on this machine` | brew tap'ten gelen eski CLI/çekirdek (v0.8.119) embedding desteği öncesi | Brew paketini kaldır; SDK 1.x CLI'sız çalışır, `pip install --force-reinstall 'foundry-local-sdk>=1.2'` |
| `[backend hatasi] Foundry Local could not start: ...` | Yerel çekirdek eksik veya bozuk kurulmuş | `pip install --force-reinstall 'foundry-local-sdk>=1.2'`, sonra `python scripts/doctor.py` |
| İkinci `initialize()` hatası (Streamlit / notebook) | `FoundryLocalManager` tekildir | `if FoundryLocalManager.instance is None` koruması + `st.cache_resource` |
| Cevap yazıldıktan **sonra** `IndexError` | Açık hata **#905**: son chunk boş `choices` ile geliyor | `if not chunk.choices: continue` -- bu repoda zaten var; kendi kodunda tekrarla |
| Her şey çalışıyor ama çok yavaş, `execution_provider` CPU | Açık hata **#858 / #895**: GPU EP kayıtlı olsa da yalnızca CPU varyantı görünüyor | `load()` sonrası basılan satırı not et; sürüm notlarını izle |
| İndirme sonrası tuhaf, tekrarlanmayan hatalar | Açık hata **#909 / #906**: uyku modu bozuk önbellek bırakabiliyor, bütünlük doğrulaması yok | Model önbelleğini temizleyip yeniden indir; indirme sırasında uyutma |
| `Indeks farkli bir embedding modeliyle olusturulmus` | Backend değişti, indeks eski vektör uzayında | `python -m app.cli --backend foundry ingest` |
| `Dimension mismatch: query has 1024 dims but the index has 512` | Aynı sebep, `cosine_similarity()` tarafından yakalandı | Yeniden indeksle |
| Sıcaklık değiştirdim, cevap hiç değişmedi | `complete_streaming_chat` parametreleri kabul etmiyor olabilir; `except TypeError` dalı onları sessizce düşürür | A4.5 adım 1: imzayı yazdır |
| `--generate` koşusu bitmek bilmiyor | 33 soru = 33 model çağrısı | Önce üretimsiz koş; `--generate`'i yalnızca gerektiğinde kullan |
| `auto` seçtim ama cevaplar alıntı gibi geliyor | `hashing`'e düşülmüş; stderr'de uyarı var | Uyarıyı oku, `python scripts/doctor.py` çalıştır, sonra `--backend foundry` ile zorla |

---

## 7. Hafta 5'e hazırlık

Elinde artık iki backend'in aynı 33 soruda ölçülmüş sonuçları var. Hafta 5 bu
ölçümü derinleştirir: metriklerin ne söyleyip ne söylemediği, gecikme profili
(`retrieval_seconds` ile `generation_seconds` ayrı ayrı kaydediliyor) ve test kapsamı.

Bu haftadan taşıman gerekenler:

- `eval/results.jsonl` -- silme, Hafta 5'te bu dosyayı okuyacağız
- A4.2'de kaydettiğin varyant satırı (`device_type` / `execution_provider`)
- A4.3'ün karşılaştırma tablosu
- A4.5'te sıcaklık parametresinin gerçekten uygulanıp uygulanmadığına dair bulgun

`qwen2.5-0.5b`'nin bağlama sadık cevaplamada zayıf olduğunu A4.4 ve A4.5'te büyük
olasılıkla göreceksin. Hafta 5'e gelmeden diskinde yer varsa `qwen3-1.7b`
(~1490 MB) veya `qwen3-4b` (~3083 MB) indirmesini başlat; model boyutunun cevap
kalitesine etkisi Hafta 5'in ölçüm konularından biri.
