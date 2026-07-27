# Mimari

Bu belge, projenin kodunun neden bu şekilde bölündüğünü anlatır. Anlatılan her
fonksiyon adı, tablo şeması ve varsayılan değer `src/` ve `app/` altındaki
gerçek dosyalardan alınmıştır.

Belgeyi okurken iki dosyayı yanında açık tut:

- `src/foundry_rag/pipeline.py` — iki ana akışın tamamı burada
- `src/foundry_rag/store.py` — veritabanı şeması ve vektör serileştirme burada

Kütüphane katmanı on beş modülden oluşur (`src/foundry_rag/` altında on bir,
`backends/` altında dört). En büyüğü `backends/foundry.py` (407 satır, yorumlar
dahil); geri kalanların hiçbiri 370 satırı geçmez. Güncel büyüklükleri görmek
için:

```bash
wc -l src/foundry_rag/*.py src/foundry_rag/backends/*.py | sort -rn
```

En büyük üçü sırasıyla `backends/foundry.py` (407), `pipeline.py` (368) ve
`turkish.py` (240); en küçükleri `backends/base.py` (55) ile
`foundry_rag/__init__.py` (57).

---

## 1. Dört katman

```
+------------------------------------------------------------------+
|  ARAYUZ KATMANI                                                   |
|  app/cli.py            ingest / ask / chat / info                 |
|  app/streamlit_app.py  tarayici arayuzu                           |
|  scripts/doctor.py     ortam kontrolu                             |
|  eval/evaluate.py      olcum (+ --gate ile CI kalite kapisi)      |
|  eval/calibrate.py     esik kalibrasyonu (izgara taramasi)        |
|  Sorumluluk: girdi almak, ciktiyi bicimlendirmek. Baska hicbir sey.|
+---------------------------|--------------------------------------+
                            | Settings, ingest(), RagPipeline
                            v
+------------------------------------------------------------------+
|  PIPELINE KATMANI                                                 |
|  pipeline.py      ingest(), RagPipeline.answer()/stream_answer()  |
|  chunking.py      chunk_text(), chunk_document()                  |
|  retrieval.py     cosine_similarity(), hybrid_search(), search()  |
|  lexical.py       BM25Index, saturate()                           |
|  turkish.py       expand_tokens()  (Turkce govdeleme)             |
|  groundedness.py  check()  (cumle bazli kaynaklilik denetimi)     |
|  extractive.py    extract_answer()  (model yerine alinti yapan    |
|                   cevap yolu; kaynaklilik dusukse devreye girer)  |
|  prompts.py       build_messages()                                |
|  config.py        Settings  (her katman buradan okur)             |
|  Sorumluluk: "RAG nedir" sorusunun cevabi. Is mantigi.            |
+--------------|---------------------------------|-----------------+
               |                                 |
               v                                 v
+----------------------------+   +-------------------------------------+
|  VERI KATMANI              |   |  MODEL KATMANI                      |
|  store.py                  |   |  backends/base.py     Backend (ABC)  |
|  VectorStore               |   |  backends/hashing.py  HashingBackend |
|  encode_vector()           |   |  backends/foundry.py  FoundryBackend |
|  decode_vector()           |   |  backends/__init__.py create_backend |
|  data/rag.db (SQLite)      |   |  Sorumluluk: embed() ve chat()      |
+----------------------------+   +-------------------------------------+
```

Katmanların sorumlulukları ve kuralları:

| Katman | Dosyalar | Sorumluluğu | Yasak olan |
|---|---|---|---|
| Arayüz | `app/cli.py`, `app/streamlit_app.py` | Kullanıcıdan soru almak, cevabı ve kaynakları yazdırmak | Chunk'lama, benzerlik hesabı, prompt kurma |
| Pipeline | `pipeline.py`, `chunking.py`, `retrieval.py`, `lexical.py`, `turkish.py`, `groundedness.py`, `extractive.py`, `prompts.py` | İndeksleme ve sorgulama akışları | `sqlite3` cümlesi yazmak, SDK çağırmak |
| Veri | `store.py` | SQLite'a yazmak/okumak, vektör serileştirme | Model çağırmak, prompt bilmek |
| Model | `backends/` | Metni vektöre çevirmek, mesajlardan cevap üretmek | Veritabanını bilmek, chunk bilmek |

Bunu somut olarak test edebilirsin: `src/foundry_rag/store.py` içinde `backend`
kelimesi geçmez, `src/foundry_rag/backends/` altında `sqlite3` geçmez.
`app/streamlit_app.py` dosyasının başındaki yorum da bunu söyler: cevabın nasıl
üretildiğini değiştirmek istiyorsan `foundry_rag.pipeline` dosyasını değiştir,
arayüz dosyasını değil.

---

## 2. İki akış

Proje iki farklı hızda çalışan iki akıştan ibarettir. Bunları ayırmak, uygulamanın
her açılışta tüm belgeleri yeniden embed etmesini engeller.

| | İndeksleme (ingest) | Sorgulama (query) |
|---|---|---|
| Ne zaman çalışır | Belgeler değişince | Her soruda |
| Giriş noktası | `ingest()` (fonksiyon) | `RagPipeline` (sınıf) |
| Model kullanımı | Sadece embedding | Embedding + chat |
| Sonucu | `IngestReport` | `Answer` |
| Yan etkisi | `data/rag.db` yazılır | Yok (salt okuma) |

### 2.1 İndeksleme akışı

Komut: `python -m app.cli ingest`

```
python -m app.cli ingest
      |
      v
cmd_ingest(args)                                     [app/cli.py]
      |  Settings.from_env() + CLI bayraklari (--chunk-size, --backend, ...)
      |  settings.validate()      <- burada patlarsa hicbir sey yazilmaz
      v
create_backend(settings, verbose=True)     [backends/__init__.py]
      |  "hashing" -> HashingBackend()
      |  "foundry" -> FoundryBackend(...)  (basarisizsa hata)
      |  "auto"    -> FoundryBackend, olmazsa uyari + HashingBackend
      v
ingest(settings, backend=backend, reset=not args.append)   [pipeline.py]
      |
      +--(1)-- iter_documents(settings.docs_dir)
      |          data/docs/*.md, *.markdown, *.txt, *.rst  (TEXT_SUFFIXES)
      |          -> ("01-rag-nedir.md", "# RAG Nedir...")
      |          bos dosyalar report.skipped listesine yazilir
      |
      +--(2)-- chunk_document(text, source=name,
      |                       chunk_size=900, chunk_overlap=150)
      |          -> [Chunk(source, index, heading, text), ...]
      |
      +--(3)-- VectorStore(settings.db_path)
      |          reset=True ise store.reset()  (DELETE FROM chunks + index_meta)
      |
      +--(4)-- _batched(all_chunks, EMBED_BATCH_SIZE=16)
      |          her parti icin:
      |             backend.embed([c.with_heading_prefix() for c in batch])
      |                -> list[list[float]]     (uzunluk kontrol edilir)
      |             store.add_chunks((source, index, heading, text,
      |                               content_hash, vector) ...)
      |                -> INSERT OR IGNORE ... (content_hash UNIQUE)
      |             ekrana: "Embedding: 48/132 parca"
      |
      +--(5)-- store.set_meta(...)   5 satir yazilir:
      |          embedding_signature, chunk_size, chunk_overlap,
      |          backend, document_count
      v
IngestReport(documents=8, chunks=..., inserted=..., seconds=..., skipped=[])
report.summary()  ->  "8 belge -> N parca (N yeni kayit) / X.X sn"
```

Dikkat edilecek üç nokta:

1. **Embed edilen metin, saklanan metinden farklıdır.** `backend.embed()` çağrısına
   `c.with_heading_prefix()` gider — yani `"Bölüm başlığı\n\ntext"`. Veritabanına
   `content` sütununa ise sadece `c.text` yazılır. Başlık, parçanın hangi bölüme
   ait olduğunu vektöre taşımak için embed'e eklenir.
2. **Vektör uzunluğu doğrulanır.** Backend `len(batch)` kadar metin için farklı
   sayıda vektör dönerse `ingest()` `RuntimeError` fırlatır. Sessiz kayma olmaz.
3. **`reset=True` varsayılandır.** `--append` bayrağı verilmedikçe indeks
   sıfırdan kurulur.

### 2.2 Sorgulama akışı

Komut: `python -m app.cli ask "RAG nedir?"`

```
python -m app.cli ask "RAG nedir?"
      |
      v
cmd_ask(args)                                        [app/cli.py]
      v
RagPipeline(settings, verbose=args.verbose).__init__  [pipeline.py]
      |  create_backend(settings)      -> modeller yuklenir
      |  VectorStore(settings.db_path) -> baglanti acilir
      |  _check_index():
      |      store.count() == 0             -> RuntimeError "Veritabani bos"
      |      stored_signature != current     -> RuntimeError "farkli embedding"
      |
      |  INDEKS ACILISTA BIR KEZ BELLEGE ALINIR (her soruda degil):
      |      self.matrix, self.records = self.store.load_matrix()
      |      self.bm25 = BM25Index([f"{r.heading}\n{r.content}"
      |                             for r in self.records])
      |                  settings.hybrid False ise self.bm25 = None
      v
RagPipeline.answer("RAG nedir?")
      |
      +--(1) RETRIEVE ------------------------------------------------
      |     retrieve(question)
      |        backend.embed([question])[0]        -> query_vector
      |        hybrid_search(self.records, self.matrix, query_vector,
      |                      query_text=question, bm25=self.bm25,
      |                      top_k=4, min_similarity=0.30,
      |                      lexical_scale=16.0)         [retrieval.py]
      |           anlam yolu : cosine_similarity(query_vector, matrix)
      |           kelime yolu: bm25.score_all(question)
      |           birlestirme: reciprocal_rank_fusion(...)  (SIRA uzerinden)
      |           guven kapisi: max(anlam, saturate(kelime, lexical_scale))
      |                         >= min_similarity
      |        -> (list[SearchHit], gecen sure)
      |        (adim adim semasi bolum 3'te, retrieval.py basligi altinda)
      |
      |     Disk okumasi YOK: matris ve BM25 indeksi __init__ icinde
      |     yuklendi. Bu adimda maliyet yalnizca soru embed'i + bir
      |     matris carpimi.
      |
      |     (settings.hybrid = False iken self.bm25 = None; ayni fonksiyon
      |      yalnizca vektor siralamasiyla calisir. Salt vektor arayan
      |      bagimsiz `search(store, ...)` fonksiyonu da durur ve
      |      testlerde/kiyaslamalarda kullanilir.)
      |
      +--(2) ESIK KAPISI ---------------------------------------------
      |     if not hits:
      |         return Answer(text=NO_CONTEXT_ANSWER, hits=[],
      |                       grounded=False)
      |         # MODEL HIC CAGRILMAZ. Bos baglamla cagrilirsa
      |         # kucuk model cevabi uydurur.
      |
      +--(3) MOD KAPISI ----------------------------------------------
      |     if settings.answer_mode == "extractive":
      |         text = extractive.extract_answer(question, hits)
      |         return Answer(..., mode="extractive")
      |         # Chat modeli HIC CAGRILMAZ; cevap parcalardan alintidir.
      |
      +--(4) AUGMENT -------------------------------------------------
      |     build_messages(question, hits, language="Türkçe")  [prompts.py]
      |        [0] system: 5 kural + dil
      |        [1] user:   "BAĞLAM:\n[1] Kaynak: dosya | Bölüm: baslik\n..."
      |                    "\n---\n\nSORU: RAG nedir?\n..."
      |
      +--(5) GENERATE ------------------------------------------------
      |     backend.chat(messages, temperature=0.1, max_tokens=600)
      |        FoundryBackend -> stream_chat() ciktilarini birlestirir
      |        HashingBackend -> baglamdan cumle alintilar
      |
      +--(6) DENETLE (settings.check_groundedness ise) ----------------
      |     groundedness.check(text, hits, threshold=0.45)  [groundedness.py]
      |        split_sentences(text)     -> denetlenecek cumleler
      |                                     (markdown ve [kaynak] atilir,
      |                                      25 karakterden kisa parca atilir)
      |        her cumle x her parca -> support_score()
      |        en iyi skor >= 0.45   -> "dayanakli", degilse "DAYANAKSIZ"
      |        -> GroundednessReport(score, sentences)
      |        Model burada TEKRAR CAGRILMAZ; bu adim saf metin islemi.
      |
      +--(7) SIGORTA (devre kesici) ----------------------------------
      |     if settings.answer_mode == "auto"
      |        and report is not None
      |        and report.score < settings.min_groundedness (0.34):
      |            text = extractive.extract_answer(
      |                       question, hits, notice=FALLBACK_NOTICE)
      |            return Answer(..., mode="extractive-fallback")
      |     # Uretilen cevap KENDI baglamindan dogrulanamadiysa onu
      |     # yine de gostermek, olculmus guvenilmezligi bilerek sunmaktir.
      v
Answer(question, text, hits, retrieval_seconds, generation_seconds,
       grounded=True, groundedness=GroundednessReport(...),
       mode="generative")
      |
      v
cmd_ask: cevabi yazdir + _print_sources() + _print_groundedness()
      "Kaynaklar:
         [1] 01-rag-nedir.md > Tanım
             guven 0.612 | anlam 0.612 | kelime 8.44 | bulan: ikisi
         getirme: 14 ms | uretim: 3.21 sn

       Kaynaklilik: %100 (3/3 cumle dayanakli)  [mod: generative]"
```

Adım (3) ile (7) aynı fonksiyonu (`extractive.extract_answer()`) iki farklı
sebeple çağırır: (3) kullanıcı dil modelini hiç istemediği için, (7) modelin
ürettiği cevap ölçüldüğü için. `Answer.mode` hangisinin çalıştığını söyler:
`"generative"`, `"extractive"` veya `"extractive-fallback"`.

**Akan (streaming) varyant.** `python -m app.cli chat` içinde
`RagPipeline.stream_answer()` kullanılır. Adım (1) ve (2) aynıdır; adım (4)
şöyle değişir:

```python
streamer = getattr(self.backend, "stream_chat", None)
if streamer is None:
    yield self.backend.chat(messages, ...)   # akis desteklemeyen backend
    return
yield from streamer(messages, ...)
```

`stream_chat`, `Backend` sözleşmesinde zorunlu değildir. `HashingBackend` bu
metodu tanımlamaz, bu yüzden cevabı tek parça alır. `FoundryBackend` tanımlar.
`getattr` kontrolü sayesinde pipeline hangi durumda olduğunu bilmek zorunda değil.

---

## 3. Modül modül

### `src/foundry_rag/config.py`

Tek bir `Settings` dataclass'ı, tüm ayarlanabilir değerler. Ortam değişkenleri
`FRAG_` önekiyle okunur.

| Alan | Varsayılan | Ortam değişkeni |
|---|---|---|
| `docs_dir` | `<repo>/data/docs` | `FRAG_DOCS_DIR` |
| `db_path` | `<repo>/data/rag.db` | `FRAG_DB_PATH` |
| `chunk_size` | `900` | `FRAG_CHUNK_SIZE` |
| `chunk_overlap` | `150` | `FRAG_CHUNK_OVERLAP` |
| `top_k` | `4` | `FRAG_TOP_K` |
| `min_similarity` | `0.30` | `FRAG_MIN_SIMILARITY` |
| `hybrid` | `True` | `FRAG_HYBRID` |
| `lexical_scale` | `16.0` | `FRAG_LEXICAL_SCALE` |
| `backend` | `auto` | `FRAG_BACKEND` |
| `chat_model` | `qwen2.5-0.5b` | `FRAG_CHAT_MODEL` |
| `embedding_model` | `qwen3-embedding-0.6b` | `FRAG_EMBEDDING_MODEL` |
| `device` | `auto` | `FRAG_DEVICE` |
| `temperature` | `0.1` | `FRAG_TEMPERATURE` |
| `max_tokens` | `600` | `FRAG_MAX_TOKENS` |
| `check_groundedness` | `True` | `FRAG_CHECK_GROUNDEDNESS` |
| `answer_mode` | `auto` | `FRAG_ANSWER_MODE` |
| `min_groundedness` | `0.34` | `FRAG_MIN_GROUNDEDNESS` |
| `answer_language` | `Türkçe` | `FRAG_ANSWER_LANGUAGE` |

`min_similarity` ve `lexical_scale` tahmin edilmiş değerler değildir.
`python eval/calibrate.py` 33 soruluk değerlendirme seti üzerinde
`min_similarity` x `lexical_scale` ızgarasını tarar (11 x 6 = 66 nokta) ve
`--objective balanced` (varsayılan) ile **dengeli** skoru en yüksek noktayı
seçer. Dengeli skor, recall ile reddetme doğruluğunun **harmonik** ortalamasıdır;
aritmetik olsaydı her soruyu cevaplayıp hiçbirini reddetmeyen bir sistem %50
alırdı. Sorular ızgara boyunca bir kez embed edilip yeniden kullanılır, bu
yüzden tüm tarama saniyeler sürer.

`min_similarity` eskiden `0.15` idi ve o değer **tahmindi** — üstelik yalnız
vektör skorları için ayarlanmıştı. BM25 eklenince skor dağılımı altından kaydı:
recall %72'den %96'ya çıkarken reddetme doğruluğu %87.5'ten %12.5'e düştü. Aynı
sayı artık başka bir şey ifade ediyordu. Şimdiki `0.30` bir argmax'tır.

**Optimum eşik modele bağlıdır.** Ölçüldü:

| Backend | Kalibre `min_similarity` |
|---|---|
| `hashing` (çevrimdışı yedek, CI'da koşan) | `0.30` |
| `foundry` (`qwen3-embedding-0.6b`, 1024 boyut) | `0.40` |

Kodda varsayılan `0.30`'dur, çünkü testler ve CI çevrimdışı backend'i kullanır.
Foundry Local ile çalışıyorsan `FRAG_MIN_SIMILARITY=0.40` kullan (ölçümler
bölüm 4'te). Korpus veya embedding modeli değişirse yeniden kalibre et.

Dışa açtığı iki metod:

```python
Settings.from_env() -> Settings     # ortamdan oku, yoksa varsayilani kullan
settings.validate() -> None         # bozuk ayarda hemen ValueError
```

`validate()` sekiz şeyi kontrol eder: `chunk_size > 0`, `chunk_overlap >= 0`,
`chunk_overlap < chunk_size`, `top_k > 0`, `-1 <= min_similarity <= 1`,
`backend in {auto, foundry, hashing}`, `device in {auto, cpu, gpu}`,
`answer_mode in {auto, generative, extractive}`. Bunlardan en kritik olanı
üçüncüsü: `chunk_overlap >= chunk_size` olursa parçalama ilerlemez, sonsuz
döngüye girer.

**Neden ayrı duruyor:** Deney yapmak tek satır değişiklik olsun diye. `top_k`
değerini denemek için kodun içinde arama yapmak zorunda kalmazsın:
`FRAG_TOP_K=8 python -m app.cli ask "..."`.

### `src/foundry_rag/chunking.py`

Saf fonksiyonlar; hiç I/O yok, hiç model yok. Bu yüzden test yazmaya buradan
başlanır.

```python
chunk_text(text: str, chunk_size: int = 900,
           chunk_overlap: int = 150) -> list[str]

chunk_document(text: str, source: str, chunk_size: int = 900,
               chunk_overlap: int = 150) -> list[Chunk]
```

`Chunk` donmuş (frozen) bir dataclass: `source`, `index`, `heading`, `text`.
İki üyesi önemlidir:

- `content_hash` (property): `sha256(source \x00 heading \x00 text)`. Veritabanında
  `UNIQUE` sütun; tekrar indeksleme bu sayede idempotent olur.
- `with_heading_prefix()`: `"heading\n\ntext"` döner. Embed edilen metin budur.

Parçalama stratejisi dört aşamalıdır ve sırayla düşer:

1. `_iter_sections()` Markdown başlıklarını (`^#{1,6}\s+`) izler, her parçanın
   hangi bölümden geldiğini bilir.
2. Paragraflar (`\n\s*\n` ile bölünmüş) `chunk_size`'ı aşana kadar birleştirilir.
3. Tek başına `chunk_size`'dan uzun bir paragraf cümlelere bölünür
   (`_SENTENCE_END` regex'i: `. ! ? …` sonrası boşluk).
4. Tek başına uzun bir cümle `_hard_split()` ile karakter sayısına göre kesilir.

Ardışık parçalar `_tail_overlap()` ile `chunk_overlap` karakter paylaşır ve bu
örtüşme kelime ortasından başlamaz.

**Neden ayrı duruyor:** Parçalama, RAG kalitesini en çok etkileyen ve en kolay
test edilen parçadır. Model olmadan çalıştığı için `tests/test_chunking.py`
saniyeler içinde koşar.

### `src/foundry_rag/store.py`

SQLite katmanı. Detaylı şema bölüm 6'da.

```python
encode_vector(vector: Sequence[float]) -> bytes
decode_vector(blob: bytes) -> np.ndarray

class VectorStore:
    __init__(db_path: Path | str)
    reset() -> None
    add_chunks(rows: Iterable[tuple[str, int, str, str, str, Sequence[float]]]) -> int
    set_meta(key: str, value: str) -> None
    get_meta(key: str, default: str | None = None) -> str | None
    count() -> int
    sources() -> list[str]
    load_matrix() -> tuple[np.ndarray, list[ChunkRecord]]
    close() -> None
```

`VectorStore` bir context manager'dır (`__enter__` / `__exit__`), yani
`with VectorStore(path) as store:` kullanımı bağlantıyı kapatmayı garanti eder.

`ChunkRecord.citation` property'si `"01-rag-nedir.md > Tanım"` biçiminde kısa
kaynak metni üretir; CLI ve Streamlit ikisi de bunu kullanır.

**Neden ayrı duruyor:** `VectorStore` hiçbir modelden haberdar değildir. Yarın
SQLite yerine başka bir depo kullanmak istersen sadece bu dosya değişir;
`pipeline.py` aynı kalır.

### `src/foundry_rag/turkish.py`

Türkçe morfoloji duyarlı normalizasyon. Kelime tabanlı aramanın (BM25) ve
kaynaklılık denetiminin ikisi de bu modülden token alır.

```python
MIN_STEM_LENGTH = 4

fold_case(text: str) -> str
deaccent(text: str) -> str
last_vowel(word: str) -> str | None
strip_suffixes(word: str, min_stem: int = MIN_STEM_LENGTH) -> str
stem_word(word: str) -> str
tokenize(text: str, stem: bool = True) -> list[str]
expand_tokens(text: str) -> list[str]
shares_root(a: str, b: str) -> bool
normalize(text: str) -> str
```

Modülün çözdüğü dört somut sorun:

| Sorun | Örnek | Çözen fonksiyon |
|---|---|---|
| Python'un `.lower()`'ı Türkçe'de yanlış | `.lower()` `I` -> `i` yapar; doğrusu `I` -> `ı`, `İ` -> `i` | `fold_case()` |
| Kesme işaretli ekler | `RAG'in` -> `rag`, `SQLite'ta` -> `sqlite` | `stem_word()` |
| Ünlü uyumlu ek yığını | `belgelerden` -> `belge` | `strip_suffixes()` |
| Ünsüz yumuşaması | `benzerliği` -> `benzerliğ` -> `benzerlik` -> `benzer` | `strip_suffixes()` |

Kesme işareti özel muameledir: apostrof **zaten kök sınırını işaretlediği için**
`stem_word()` orada keser ve sonrasında ek ayıklamaz. Ayıklasaydı `SQLite'ta`
kelimesinin kendi `-te` hecesi ek sanılır ve `sqli` çıkardı.

İki koruma stemmer'ın kaçmasını engeller:

1. **Tek harfli ekler sadece ilk geçişte ayıklanır.** Yoksa `parçalar` önce
   `-lar` eki düşüp `parça`, sonra son `-a` da düşüp `parç` olur ve
   `parçalama` ile hiç buluşmaz.
2. **`MIN_STEM_LENGTH = 4`.** `veri` -> `ver` -> `ve` zincirini kesen sınır.

En önemli fonksiyon `expand_tokens()`'dır ve **indeksin gerçekten kullandığı
biçim odur**. Her kelime hem yüzey biçimi hem gövdesi olarak indekslenir:

```
belge      -> {belge, belg}
belgeler   -> {belgeler, belge}     ortak: belge
benzerlik  -> {benzerlik, benzer}
benzerliği -> {benzerliği, benzer}  ortak: benzer
```

Sebep: kural tabanlı bir stemmer son ünlünün ek mi kök harfi mi olduğunu
bilemez. `belge` kökü `belg`'e iner, `belgeler` ise `belge`'ye — tek biçim
indekslense bu ikisi asla buluşmaz. İkisini birden indekslemek sorunu ortadan
kaldırır. **Gövde bir recall arttırıcıdır, doğruluk kaynağı değil.**
`expand_tokens()` tekrar eden tokenleri ayıklamaz, çünkü BM25'in terim frekansı
anlamlı kalmalıdır.

Ölçüm: 12 kelime ailesinin 12'sinde eşleşme sağlandı; kontrol çiftlerinde
(`kedi~kahve`, `vektör~veri`, `model~modern`, `bilgi~bilek`, `sorgu~sormak`)
0 yanlış pozitif. Doğrulama: `python -m pytest tests/test_turkish.py -q`.

**Neden ayrı duruyor:** Dil bilgisi ile arama matematiği farklı şeylerdir.
Yarın gerçek bir morfolojik çözümleyici (örneğin Zemberek) takılacaksa değişecek
tek dosya budur; `lexical.py` ve `groundedness.py` sadece `expand_tokens()`
çağırdıklarını bilir.

### `src/foundry_rag/lexical.py`

Hibrit aramanın kelime yarısı: BM25.

```python
DEFAULT_K1 = 1.5
DEFAULT_B  = 0.75

class BM25Index:
    __init__(documents: Sequence[str], k1: float = 1.5, b: float = 0.75)
    postings: dict[str, dict[int, int]]     # terim -> {belge indeksi: frekans}
    doc_lengths: np.ndarray
    idf: dict[str, float]
    average_length: float
    vocabulary_size (property)
    score_all(query: str) -> np.ndarray
    search(query: str, top_k: int = 10) -> list[tuple[int, float]]

saturate(score: float, scale: float = 4.0) -> float
```

BM25 skorunun üç fikri: terim frekansı **doyumlu** sayılır (`k1` onuncu
tekrarın ikinciye göre katkısını sınırlar), nadir terim ağır basar (`idf`),
uzun belge uzunluğuna göre cezalanır (`b`).

İki ayrıntı, sessiz hataları engellediği için önemlidir:

- **`idf`'deki `+1`** (Robertson-Sparck Jones biçimi:
  `log(1 + (N - df + 0.5) / (df + 0.5))`). Olmasaydı korpusun yarısından
  fazlasında geçen bir terim **negatif** ağırlık alır ve o terimi içeren
  belgeleri sıralamada aşağı iterdi.
- **`saturate(score, scale) = score / (score + scale)`.** Sınırsız BM25 skorunu
  `[0, 1)` aralığına eşler ve `score == scale` noktasında tam `0.5` verir.
  Gerekçe: kosinüs `[-1, 1]` aralığındadır, BM25 ise sınırsız ve korpusa
  bağlıdır; aynı eşikle karşılaştırılamazlar. `lexical_scale` işte bu tek
  yorumlanabilir düğmedir (varsayılan `16.0`, kalibre edilmiş değer).

Tokenler `turkish.expand_tokens()`'dan gelir. Sorgudaki `belgelerden`
kelimesinin belgedeki `belge` ile eşleşmesini sağlayan şey budur.

**Neden ayrı duruyor:** BM25 saf bir sayma işidir — model yok, veritabanı yok.
`tests/test_lexical_and_fusion.py` birkaç uydurma cümleyle koşar.

### `src/foundry_rag/retrieval.py`

```python
RRF_K = 60

@dataclass(frozen=True)
class SearchHit:
    record: ChunkRecord
    score: float           # guven: cevapla/reddet kararini bu verir
    dense_score: float = 0.0
    lexical_score: float = 0.0
    fused_score: float = 0.0
    matched_by (property) -> str

normalize(matrix: np.ndarray) -> np.ndarray
cosine_similarity(query: Sequence[float], matrix: np.ndarray) -> np.ndarray
reciprocal_rank_fusion(rankings: Sequence[Sequence[int]],
                       k: int = RRF_K) -> dict[int, float]
search(store: VectorStore, query_vector: Sequence[float],
       top_k: int = 4, min_similarity: float = 0.0) -> list[SearchHit]
hybrid_search(records, matrix, query_vector, query_text="", bm25=None,
              top_k=4, min_similarity=0.15, rrf_k=RRF_K,
              lexical_scale=4.0, candidate_multiplier=5) -> list[SearchHit]
```

`search()` salt vektör aramasıdır ve testler ile kıyaslamalar için durur.
Uygulamanın gerçek yolu `hybrid_search()`'tür: `RagPipeline.retrieve()` bunu
çağırır. Fonksiyon imzasındaki varsayılanlar kütüphane varsayılanlarıdır;
uygulamada geçen değerler her zaman `Settings`'ten gelir
(`min_similarity=0.30`, `lexical_scale=16.0`).

#### Hibrit getirmenin şeması

```
                        soru: "SQLite'ta vektor nasil saklaniyor?"
                                        |
                +-----------------------+-----------------------+
                |                                               |
                v                                               v
   ANLAM YOLU (dense)                              KELIME YOLU (lexical)
   backend.embed([soru])[0]                        bm25.score_all(soru)
   cosine_similarity(q, self.matrix)               tokenler: expand_tokens()
   -> her parca icin [-1, 1] skor                  -> her parca icin >= 0 skor
                |                                               |
                v                                               v
   aday havuzu: en iyi                             aday havuzu: en iyi
   top_k * candidate_multiplier                    top_k * candidate_multiplier
   (4 * 5 = 20) parca, SIRALI                      (4 * 5 = 20) parca, SIRALI
                |                                               |
                +----------------------+------------------------+
                                       |
                                       v
                    reciprocal_rank_fusion(rankings, k=60)
                    RRF(d) = toplam  1 / (60 + rank_i(d))
                    Skora DEGIL siraya bakar.
                                       |
                                       v  fused_score'a gore azalan siralama
                    +------------------------------------------+
                    |  GUVEN KAPISI (her aday icin)            |
                    |                                          |
                    |  dense   = dense_scores[i]               |
                    |  lexical = lexical_scores[i]             |
                    |  guven   = max(dense,                    |
                    |                saturate(lexical, 16.0))  |
                    |                                          |
                    |  guven < min_similarity (0.30) -> ATLA   |
                    |  aksi halde SearchHit olarak ekle        |
                    |  top_k (4) dolunca dur                   |
                    +------------------------------------------+
                                       |
                                       v
                       list[SearchHit]  (bos olabilir -> reddet)
```

Üç karar bu şemanın içinde saklıdır:

1. **Neden iki retriever.** İkisi farklı yerlerde başarısız olur. Vektör araması
   nadir literalleri kaçırır (`1536`, bir model adı, bir hata metni) — çünkü
   embedding tam da onları ayırt eden ayrıntıyı bulanıklaştırır. Kelime araması
   ise eş anlamlıyı kaçırır ("araba fiyatları" ile "otomobil ücretleri").
   Füzyondan sonra recall **birleşim** olur, kesişim değil.
2. **Neden füzyon sıra üzerinden.** Kosinüs `[-1, 1]`, BM25 sınırsız ve korpusa
   bağlı. Ham skorları toplamak her korpusta yeniden ayar ister ve korpus
   değişince sessizce bozulur. Sıralar hiçbir kalibrasyon olmadan
   karşılaştırılabilir. `k = 60` sabiti Cormack ve ark. (2009)'dan gelir ve
   tepeyi düzleştirir: tek bir retriever'ın birinciliği, iki retriever'ın da
   ilk beşine koyduğu bir belgeyi ezemesin diye.
3. **Neden kapı `max()`, `min()` ya da ortalama değil.** Bir parça **iki
   aramadan biri** ondan eminse kabul edilir. Kısa bir sorguda embedding sinyali
   zayıf olabilir ama kelime eşleşmesi tartışmasızdır; ortalama alsaydık böyle
   bir parçayı reddederdik.

#### `SearchHit`'in alanları

Tek bir skor yerine dört sayı taşınır, çünkü "bu parça neden geldi" sorusu
hata ayıklamanın yarısıdır.

| Alan | Aralık | Nereden gelir | Ne işe yarar |
|---|---|---|---|
| `score` | `[-1, 1]` | `max(dense_score, saturate(lexical_score, lexical_scale))` | **Güven.** `min_similarity` ile karşılaştırılan tek sayı; cevapla/reddet kararını bu verir |
| `dense_score` | `[-1, 1]` | `cosine_similarity()` | Anlam yolunun ham skoru |
| `lexical_score` | `[0, ∞)` | `bm25.score_all()` | Kelime yolunun ham BM25 skoru (doyurulmamış hâli) |
| `fused_score` | küçük pozitif | `reciprocal_rank_fusion()` | Sonuçların hangi sıraya göre dizildiği. `1/(60+1) + 1/(60+1) ≈ 0.0328` gibi değerler alır; mutlak büyüklüğü anlamsız, karşılaştırması anlamlıdır |

`matched_by` bir property'dir ve üç değer döner:

```python
dense   = self.dense_score > 0.01
lexical = self.lexical_score > 0.0
"ikisi"  -> her iki retriever da buldu
"kelime" -> yalnizca BM25 buldu
"anlam"  -> yalnizca vektor aramasi buldu
```

CLI bunu her kaynak satırında yazdırır, bu yüzden hibritin gerçekten iş yapıp
yapmadığı çıplak gözle görülür:

```
[1] 01-rag-nedir.md > Tanım
    guven 0.612 | anlam 0.612 | kelime 8.44 | bulan: ikisi
```

Bir soruda tüm satırlar `bulan: anlam` diyorsa BM25 o soruya hiç katkı
vermemiş demektir; hepsi `bulan: kelime` diyorsa embedding zayıf kalmıştır.

#### Diğer ayrıntılar

`cosine_similarity` her iki tarafı L2-normalize eder, böylece kosinüs benzerliği
bir nokta çarpımına indirgenir: `(normalize(matrix) @ q.T).ravel()`. Boyut
uyuşmazlığında açık bir `ValueError` fırlatır ve çözümü söyler ("yeniden
indeksle").

`normalize()` sıfır satırları sıfır bırakır (`norms[norms == 0] = 1.0`) — aksi
halde boş bir vektör NaN üretir ve sıralama sessizce bozulur.

`min_similarity` filtresi projedeki en önemli tek satırlık karardır. Eşik
olmasaydı, cevabı belgelerde bulunmayan bir soru için bile "en az kötü" 4 parça
dönerdi ve model onlardan bir cevap uydururdu.

**Neden ayrı duruyor:** Arama matematiği, depolamadan ve prompt'tan bağımsız
olarak test edilebilir. `tests/test_retrieval.py` uydurma vektörlerle,
`tests/test_lexical_and_fusion.py` uydurma metinlerle çalışır.

### `src/foundry_rag/prompts.py`

```python
SYSTEM_PROMPT               # 5 kurallik sablon, {language} yer tutuculu
NO_CONTEXT_ANSWER = "Bu bilgi elimdeki belgelerde yok."

build_system_prompt(language: str = "Türkçe") -> str
format_context(hits: Sequence[SearchHit]) -> str
build_user_prompt(question: str, hits: Sequence[SearchHit]) -> str
build_messages(question, hits, language="Türkçe") -> list[dict[str, str]]
```

Sistem prompt'undaki beş kural: (1) sadece bağlamı kullan, (2) yoksa
`"Bu bilgi elimdeki belgelerde yok."` de, (3) her iddianın sonunda kaynağı köşeli
parantezle belirt, (4) kısa yaz, (5) belirtilen dilde cevapla.

`format_context()` her parçayı şöyle etiketler:

```
[1] Kaynak: 01-rag-nedir.md | Bölüm: Tanım
<parca metni>

---

[2] Kaynak: 03-embedding-ve-vektor-arama.md | Bölüm: Kosinüs benzerliği
<parca metni>
```

Kullanıcı mesajında bağlam **önce**, soru **sonra** gelir. Model önce malzemeyi
okur, sonra ne yapması istendiğini öğrenir.

**Neden ayrı duruyor:** Prompt, RAG projesinde en sık değiştirilen dosyadır.
Ayrı durduğu için `pipeline.py`'a dokunmadan denenebilir ve
`tests/test_prompts_and_backend.py` içinde bağımsız doğrulanır.

### `src/foundry_rag/groundedness.py`

Cevap üretildikten **sonra** çalışan denetleyici. Getirmenin doğru parçayı
bulması, modelin o parçanın içinde kaldığını göstermez: model boşluğu doldurur,
geçişi yumuşatır ya da ön eğitiminden hatırladığı bir şeyi araya karıştırır.
Uydurulmuş bir cümle, yanındaki `[kaynak]` etiketiyle birlikte doğrusundan
ayırt edilemez görünür — hatta daha güvenilir görünür.

```python
STOPWORDS: frozenset          # Turkce islev kelimeleri
SUPPORT_THRESHOLD = 0.45

split_sentences(text: str) -> list[str]
support_score(sentence: str, passage: str, idf: dict[str, float]) -> float
check(answer: str, hits: Sequence[SearchHit],
      threshold: float = SUPPORT_THRESHOLD) -> GroundednessReport

@dataclass(frozen=True)
class SentenceVerdict:
    text: str
    score: float
    supported: bool
    best_source: str = ""
    label (property) -> "dayanakli" | "DAYANAKSIZ"

@dataclass
class GroundednessReport:
    score: float
    sentences: list[SentenceVerdict]
    unsupported (property) -> list[SentenceVerdict]
    is_clean (property) -> bool
    summary() -> str
```

Akış: `check()` cevabı cümlelere böler, her cümleyi getirilen **her** parçaya
karşı puanlar, en iyi skoru alır, `threshold` (varsayılan `0.45`) ile
karşılaştırır. Rapor skoru desteklenen cümlelerin oranıdır.

`split_sentences()` denetlenecek metni temizler: markdown işaretlerini
(`[*_`#>]+`) ve `[...]` biçimindeki kaynak etiketlerini atar, 25 karakterden
kısa parçaları eler. Sebep: "Evet." ya da "Özet:" bir iddia taşımaz; onları
puanlamak skoru anlamsızca aşağı çeker.

`support_score()` **ağırlıklı recall**tir, simetrik örtüşme değil:

```
sorulan soru: "bu cumlenin iddia ettigi her sey pasajda var mi?"
degil        : "cumle ile pasaj ne kadar benziyor?"
```

Bu ayrım önemlidir; simetrik bir ölçü uzun pasajı sırf uzun olduğu için
cezalandırırdı. Üç detay:

- `STOPWORDS` listesindeki işlev kelimeleri tamamen atılır. Atılmasaydı akıcı
  yazılmış her cümle desteklenmiş görünürdü.
- Nadir kelimeler IDF ile ağır basar. Cümle "1536 bayt" diyor ve pasaj da
  "1536 bayt" diyorsa bu güçlü kanıttır; "ve" ile "bir" paylaşmak değildir.
- **Hiç görülmemiş terim maksimum ağırlık alır** (`default_weight`). Getirilen
  hiçbir pasajda geçmeyen bir kelime, uydurmanın tam da ürettiği şeydir.

Karşılaştırma `turkish.expand_tokens()` üstünden yapılır, yani cevaptaki
`belgelerden` bağlamdaki `belge`'den destek alır.

**Bu bir NLI (doğal dil çıkarımı) modeli değildir.** Çelişkiyi ve ortak
kelimesi olmayan eş anlamlıyı yakalayamaz. Karşılığında ikinci bir model
indirmesi, cümle başına ikinci bir çıkarım geçişi ve çevrimdışı yedeğin
karşılayamayacağı bir bağımlılık gerektirmez — ve asıl önemli hatayı yakalar:
**modelin bağlamda hiç geçmeyen bir şeyi iddia etmesi.** Skor bir sinyaldir,
hüküm değil: düşük skor "buraya bak" demektir, "bu yanlış" değil.

Ölçüldü: doğru cevapta %100, kasten uydurulmuş cevapta %0
(`tests/test_groundedness.py`).

Bağlantı noktaları: `RagPipeline.answer()` sonucu `Answer.groundedness` alanına
yazar, `Settings.check_groundedness` (`FRAG_CHECK_GROUNDEDNESS=0`) ile kapatılır,
CLI `_print_groundedness()` ile yazdırır.

**Neden ayrı duruyor:** Getirme kalitesi ile cevap kalitesi farklı şeylerdir ve
ayrı ölçülmelidir. Ayrıca bu modül `pipeline.py`'ı hiç tanımaz — girdisi bir
metin ve bir `SearchHit` listesidir, o kadar.

### `src/foundry_rag/extractive.py`

Dil modeli kullanmayan cevap yolu: soruya en iyi cevap veren cümleleri getirilen
parçalardan **birebir alıntılar**.

```python
MIN_SENTENCE_LENGTH = 30
MIN_RELEVANCE = 0.08
FALLBACK_NOTICE            # "(Not: Uretilen cevap ... dogrudan alinti yapildi.)"
NO_ANSWER = "Bu bilgi elimdeki belgelerde yok."

split_sentences(text: str) -> list[str]
score_sentence(question_terms: set[str], sentence: str) -> float
extract_answer(question: str, hits: Sequence[SearchHit],
               max_sentences: int = 3, notice: str = "") -> str
```

Skorlama iki çarpandan oluşur: cümlenin soru terimlerini ne kadar kapsadığı
(`score_sentence`, `turkish.expand_tokens()` üzerinden) ve cümlenin geldiği
parçanın getirme sırası (`chunk_weight = 1 / (1 + rank)`, katkısı
`0.5 + 0.5 * chunk_weight` ile yumuşatılır). İkinci çarpan olmasaydı zayıf bir
parçadaki gevşek ilgili bir cümle, 1. sıradaki gerçek cevabı geçebilirdi.

İki yerde kullanılır:

| Kullanım | Tetikleyen |
|---|---|
| Cevabın tamamı | `settings.answer_mode == "extractive"` — chat modeli hiç çağrılmaz |
| Devre kesici | `answer_mode == "auto"` iken `groundedness` skoru `min_groundedness` (`0.34`) altına düşerse; `notice=FALLBACK_NOTICE` ile |

**Neden ayrı duruyor:** Modülün başındaki ölçüm tablosu sebebi anlatır — bu
korpusta getirme %97 genel doğrulukla çalışırken `qwen2.5-0.5b` Türkçe'de
tutarsız metin üretiyor. Zayıf halka üretim, arama değil; o yüzden üretimi
atlayabilen bir yol gerekiyor. `NO_ANSWER` metni `prompts.NO_CONTEXT_ANSWER` ile
aynı cümledir, böylece kullanıcı iki farklı reddetme biçimi görmez.

### `src/foundry_rag/pipeline.py`

İki akışın birleştiği yer.

```python
EMBED_BATCH_SIZE = 16
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}

iter_documents(docs_dir: Path) -> Iterator[tuple[str, str]]
ingest(settings: Settings, backend: Backend | None = None,
       reset: bool = True, verbose: bool = True) -> IngestReport

class RagPipeline:
    __init__(settings=None, backend=None, verbose=False)
    # __init__ sonunda hazir olan alanlar:
    #   self.backend, self.store
    #   self.matrix   : np.ndarray  (n, dim)
    #   self.records  : list[ChunkRecord]
    #   self.bm25     : BM25Index | None
    retrieve(question: str) -> tuple[list[SearchHit], float]
    answer(question: str) -> Answer
    stream_answer(question: str) -> Iterable[str]
    close() -> None
```

`ingest()` bir fonksiyon, `RagPipeline` bir sınıftır. Bu ayrım bilinçlidir:
indeksleme çalışır ve biter (durum tutmaz), sorgulama ise açık bir veritabanı
bağlantısı ve yüklü modeller üzerinde tekrar tekrar çalışır (durum tutar).

#### İndeks açılışta bir kez belleğe alınır

`__init__`, `_check_index()` geçtikten sonra şunu yapar:

```python
self.matrix, self.records = self.store.load_matrix()
self.bm25 = (
    BM25Index([f"{r.heading}\n{r.content}" for r in self.records])
    if self.settings.hybrid
    else None
)
```

Eskiden her soruda tüm veritabanı yeniden okunuyordu: `search(store, ...)` içi
`store.load_matrix()` çağırır, yani her soru bir tam tablo taraması + bir
`np.vstack` demekti. Şimdi bu maliyet açılışta bir kez ödenir.

Sonuçları:

| | Açılışta (bir kez) | Her soruda |
|---|---|---|
| SQLite okuması | `load_matrix()` — tüm satırlar | yok |
| BM25 kurulumu | `BM25Index(...)` — tüm parçalar tokenize edilir | yok |
| Model çağrısı | modelleri yükle | soruyu embed et + üret |
| Matris işlemi | yok | tek `matrix @ q.T` |

`BM25Index` metni `heading + "\n" + content` olarak alır — yani başlık kelime
aramasına da girer, tıpkı `with_heading_prefix()` ile embed'e girdiği gibi.

Bunun bir bedeli vardır ve bilinçlidir: pipeline açıkken `python -m app.cli
ingest` çalıştırılırsa açık pipeline eski indeksi görmeye devam eder. Tek
kullanıcılı, tek süreçli bir araç için doğru takas budur (bkz. "Bilinçli
sınırlar").

`Answer` dataclass'ı cevabı denetlenebilir kılar:

| Alan | Ne işe yarar |
|---|---|
| `text` | Modelin ürettiği cevap |
| `hits` | Cevabın dayandığı parçalar + skorları |
| `retrieval_seconds` | Arama süresi |
| `generation_seconds` | Üretim süresi |
| `grounded` | `False` ise cevap bağlamdan değil, eşik kapısından geldi |
| `groundedness` | `GroundednessReport` — cümle bazlı destek denetimi (kapalıysa `None`) |
| `mode` | Cevabın nasıl üretildiği: `"generative"`, `"extractive"` veya `"extractive-fallback"` |
| `sources` (property) | Tekrarsız kaynak dosya listesi, en iyi eşleşme önce |
| `total_seconds` (property) | `retrieval_seconds + generation_seconds` |

**Neden ayrı duruyor:** Bu dosya diğer tüm modülleri çağırır ama hiçbiri bunu
çağırmaz. Bağımlılık yönü tek yönlüdür.

### `app/cli.py` ve `app/streamlit_app.py`

İkisi de aynı `RagPipeline`'ı kullanır; sadece render eder.

CLI alt komutları ve yaptıkları:

| Komut | Çağırdığı |
|---|---|
| `python -m app.cli ingest` | `create_backend()` + `ingest()` |
| `python -m app.cli ask "soru"` | `RagPipeline.answer()` |
| `python -m app.cli chat` | `RagPipeline.stream_answer()` döngüde |
| `python -m app.cli info` | `VectorStore.count()`, `.sources()`, `.get_meta()` |

Global bayraklar: `--backend {auto,foundry,hashing}`, `--top-k`,
`--min-similarity`, `-v/--verbose`. `ingest` ayrıca `--chunk-size`,
`--chunk-overlap`, `--append` alır.

`main()` çıkış kodlarını ayırır: backend hatası `2`, diğer hatalar `1`,
Ctrl-C `130`. Bu, `eval/evaluate.py` gibi betiklerin sorunu ayırt etmesini sağlar.

Streamlit tarafında kritik satır şudur:

```python
@st.cache_resource(show_spinner=False)
def load_pipeline(backend: str, top_k: int, min_similarity: float) -> RagPipeline:
```

Streamlit her etkileşimde tüm script'i yeniden çalıştırır. `cache_resource`
olmasaydı her tıklamada yeni bir `RagPipeline` kurulur, bu da
`FoundryLocalManager.initialize()`'ın ikinci kez çağrılmasına ve çökmeye yol
açardı (bkz. bölüm 8, `FoundryLocalManager.instance` satırı).

`app/_bootstrap.py` küçük ama gereklidir: `pip install -e .` yapılmamış bir
klonda `src/` klasörünü `sys.path`'e ekler, böylece `python -m app.cli` doğrudan
çalışır.

---

## 4. Backend soyutlaması

### Sözleşme

`src/foundry_rag/backends/base.py`:

```python
class Backend(ABC):
    name: str = "base"

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    @abstractmethod
    def chat(self, messages: Sequence[dict], temperature: float = 0.1,
             max_tokens: int = 600) -> str: ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int: ...

    def describe(self) -> str:
        return f"{self.name} (dim={self.embedding_dim})"

    def embedding_signature(self) -> str:
        return f"{self.name}:{self.embedding_dim}"
```

Bir RAG pipeline'ının bir model sağlayıcısından ihtiyaç duyduğu her şey bu üç
üyedir. Fazlası değil.

İki istisna sınıfı vardır ve ayrımları anlamlıdır:

- `BackendUnavailable` — backend hiç kurulamadı (paket yok, Python sürümü yanlış,
  servis kapalı). `auto` modu bunu yakalayıp yedeğe geçer.
- `BackendError` — backend var ama istek başarısız oldu.

### Seçim: `create_backend()`

`src/foundry_rag/backends/__init__.py`:

| `settings.backend` | Davranış | Ne zaman kullanılır |
|---|---|---|
| `hashing` | Her zaman `HashingBackend` | Testler, Foundry Local yokken demo |
| `foundry` | `FoundryBackend` zorunlu, olmazsa hata | Ortam kurulduktan sonra; bozuk kurulum sessizce gizlenmesin |
| `auto` (varsayılan) | Önce Foundry, olmazsa uyarı basıp `HashingBackend` | İlk gün; model indirmesi bitmeden proje çalışsın |

`FoundryBackend` **lazy import** edilir (`create_backend` fonksiyonunun içinde
`from .foundry import FoundryBackend`). Sebebi: `hashing` yolunu seçen bir
kullanıcı SDK'nın ağır native bağımlılıklarını hiç yüklemek zorunda kalmasın.

`auto` ve `foundry` yollarında `backend.embedding_dim` bilerek erkenden okunur:

```python
def _build_foundry() -> Backend:
    backend = FoundryBackend(...)
    backend.embedding_dim   # gercek baslatmayi simdi tetikle
    return backend
```

Bu satır olmasaydı, model yükleme hatası uzun bir indeksleme çalışmasının
ortasında ortaya çıkardı.

### İki uygulama arasındaki fark

| | `HashingBackend` | `FoundryBackend` |
|---|---|---|
| `name` | `hashing-offline` | `foundry-local` |
| Vektör boyutu | `512` (sabit, `DIM`) | Çalışma anında ölçülür; `qwen3-embedding-0.6b` için `1024` |
| `embedding_signature()` | `hashing-offline:512` | `foundry-local:qwen3-embedding-0.6b:1024` |
| Embedding yöntemi | Hash'lenmiş kelime + bigram + karakter 4-gram torbası | Gerçek sinir ağı, anlam uzayı |
| Eş anlamlı / paraphrase eşleşmesi | Yok. Ortak kelime yoksa skor düşer | Var |
| Chat | Dil modeli yok; bağlamdaki en yakın 3 cümleyi **alıntılar** | Gerçek üretim, `complete_streaming_chat` |
| `stream_chat` | Yok | Var |
| Bağımlılık | stdlib + numpy | `foundry-local-sdk >= 1.2`, Python >= 3.11, arm64 macOS |
| İlk çalıştırma maliyeti | 0 | ~1.3 GB model indirmesi |
| Determinizm | Tam. Aynı girdi hep aynı vektör | Hayır |

`HashingBackend` determinizmi bir tesadüf değil, bilinçli bir seçimdir.
`_bucket()` fonksiyonu Python'un yerleşik `hash()`'ini değil `blake2b`'yi kullanır:

```python
def _bucket(feature: str) -> int:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") % DIM
```

Python 3'te `hash()` süreç başına rastgeleleştirilir; onunla üretilen vektörler
iki farklı çalıştırmada farklı olurdu ve indeks bir sonraki çalıştırmada
kullanılamaz hale gelirdi.

`HashingBackend.chat()` bir dil modeli değildir. Kendisine verilen prompt'u
tersine ayrıştırır (`_split_prompt()` ile `SORU:` ve `BAĞLAM:` bloklarını
çıkarır), her bağlam cümlesini soruyla skorlar, en iyi 3'ünü kaynak etiketiyle
döndürür ve cevabın sonuna bunun bir dil modeli tarafından yazılmadığını
belirten bir not ekler. Öğrenci böylece hangi yarının çalıştığını karıştırmaz.

### Neden testler `HashingBackend` kullanıyor

`tests/conftest.py` dosyasının başındaki yorum sebebi açıkça söyler: testler
hızlı, çevrimdışı ve deterministik olmalıdır. CI ortamında gigabaytlarca model
indirmek bunların hiçbiri değildir.

Somut olarak, test paketinin tamamı `HashingBackend` ile koşar. `conftest.py` şu
üç fixture'ı verir:

```python
@pytest.fixture
def backend() -> HashingBackend: ...

@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:      # kediler.md + kahve.md
    ...

@pytest.fixture
def settings(tmp_path, docs_dir) -> Settings:
    return Settings(docs_dir=docs_dir, db_path=tmp_path / "test.db",
                    chunk_size=300, chunk_overlap=50, top_k=3,
                    min_similarity=0.0, backend="hashing")
```

Her test kendi `tmp_path` veritabanını kullanır; testler birbirini kirletmez.

Aynı backend `eval/evaluate.py` için de bir taban çizgisi görevi görür. Ölçülen
değerler (`top_k=4`, 33 soruluk set):

| Metrik | Yalnız vektör, `min_similarity=0.15` | Hibrit + kalibre, `min_similarity=0.30` (varsayılan) |
|---|---|---|
| Recall@4 | %72.0 | %88.0 |
| MRR | 0.650 | 0.793 |
| Reddetme doğruluğu | %87.5 | %100.0 |
| Genel doğruluk | %75.8 | %90.9 |

Soldaki sütun `FRAG_HYBRID=0 FRAG_MIN_SIMILARITY=0.15` ile yeniden üretilebilir;
sağdaki sütun deponun varsayılan yapılandırmasıdır. İki sütun arasındaki fark,
BM25 eklemenin ve eşiği veriden seçmenin birlikte kazandırdığıdır.

Bu sonuç bilerek vasattır. `python eval/evaluate.py --backend hashing` ile bu
taban çizgisini, `python eval/evaluate.py` ile gerçek embedding modelinin
sonucunu alıp farkı görürsün. Soyutlamanın öğretim değeri budur: aynı pipeline,
değişen tek şey model.

Gerçek embedding modeliyle (`foundry` backend, `qwen3-embedding-0.6b`, 1024
boyut, aynı 33 soru, `top_k=4`) ölçülen:

| Metrik | `min_similarity=0.30` | `min_similarity=0.40` (bu backend için kalibre) |
|---|---|---|
| Recall@4 | %100 | %96 |
| MRR | 0.973 | 0.960 |
| Reddetme doğruluğu | %62.5 | %100.0 |
| Genel doğruluk | %90.9 | %97.0 |

Ortalama getirme süresi 0.33 sn (embed çağrısı dahil).

Buradaki ders, tek bir metriğe bakmanın neden yetmediğidir: `0.30` ile recall
mükemmeldir ama sistem cevaplayamayacağı soruların %37.5'ine yine de cevap
üretir. Eşiği `0.40`'a çekmek 1 recall puanı karşılığında reddetme doğruluğunu
%62.5'ten %100'e çıkarır. **Doğru eşik modele bağlıdır** ve modeli değiştirince
yeniden kalibre edilmesi gerekir:

```bash
FRAG_MIN_SIMILARITY=0.40 python eval/evaluate.py --backend foundry
python eval/calibrate.py --backend foundry
```

---

## 5. Platforma özgü davranışlar (macOS arm64)

Bu bölümdeki dört madde tahmin ya da genel tavsiye değildir; bu makinede
(macOS 14.6 / Apple Silicon, `foundry-local-sdk` 1.2.3, 2026-07-27) canlı
üretildi. Her biri `backends/foundry.py` içinde bir savunmaya karşılık gelir.
Kodun neden "gereksiz yere karmaşık" göründüğünü açıklayan bölüm burasıdır.

### A. GPU embedding varyantı bozuk vektör üretiyor

**Belirti.** `qwen3-embedding-0.6b`'nin `-generic-gpu:1` varyantı
(`WebGpuExecutionProvider`) vektör içinde `Inf`/`NaN` üretiyor. Hata modelin
kendisinde değil, SDK'nın vektörü serileştirdiği yerde patlıyor:

```
System.ArgumentException: .NET number values such as positive and negative
infinity cannot be written as valid JSON.
```

**Neden bu kadar kafa karıştırıcı.** Mesaj JSON'dan bahsediyor, model ya da GPU
sürücüsünden değil. Hatanın metnine bakan biri kendi kodunda bir serileştirme
sorunu arar. Gerçek sebep, sayının kendisinin geçersiz olmasıdır.

**Doğrulanan davranış.** Aynı modelin `-generic-cpu:1` varyantı sorunsuz
çalışıyor ve temiz, 1024 boyutlu vektör döndürüyor. Foundry Local varsayılan
olarak **bozuk olanı** seçiyor.

**Koddaki karşılığı** (`src/foundry_rag/backends/foundry.py`):

| Fonksiyon | Ne yapıyor |
|---|---|
| `_embedding_device_default()` | `platform.system() == "Darwin" and platform.machine() == "arm64"` ise `"cpu"` döner. Embedding modeli doğrudan CPU varyantıyla açılır, bozuk varyantın ~540 MB'ı hiç indirilmez |
| `_is_non_finite_failure(error)` | Hata metninde `"infinity"` veya `"cannot be written as valid json"` arar — yani sebebi belirtinin imzasından tanır |
| `FoundryBackend.embed()` | O imzayı görürse tek seferlik CPU'ya geçer ve isteği yeniden dener; tüm indeksleme çalışması bir batch yüzünden çöpe gitmez |
| `_switch_embedding_to_cpu()` | Modeli `unload()` eder, CPU varyantını seçer, gerekirse indirir, `load()` eder, embedding client'ını yeniden kurar, `self.device = "cpu"` yapar |

Bu, GPU'yu kalıcı olarak dışlamaz: `FRAG_DEVICE=gpu` seçimi geçersiz kılar.
Microsoft varyantı düzelttiğinde koddan bir şey silmeye gerek kalmaz.

Dikkat: `_embedding_device_default()` yalnızca **embedding** modeline uygulanır.
Chat modeli `self.device` ile açılmaya devam eder (`_ensure_chat_client()` ->
`_prepare_model(self.chat_model_alias, "chat")`), çünkü sorun embedding
varyantında gözlendi.

### B. Execution provider adının yazımı tutarsız

Uzak katalog API'si sağlayıcıyı `WebGPUExecutionProvider` diye yazıyor; SDK'nın
okuduğu yerel önbellek aynı şeyi `WebGpuExecutionProvider` diye yazıyor.

Sonucu: tam eşleşmeli bir string karşılaştırması GPU varyantını **asla**
bulamaz. Hiçbir hata da vermez — `select_device_variant()` sessizce `False`
döner ve kullanıcı istediğini aldığını sanır.

Çözüm `_variant_provider()` içindedir ve tek satırdır:

```python
return str(getattr(runtime, "execution_provider", "") or "").lower()
```

Karşılaştırmalar da küçük harfli **alt dizge** üzerinden yapılır
(`if wanted in _variant_provider(variant)`), tam eşitlik üzerinden değil.

Genel ders: dış bir servisin döndürdüğü tanımlayıcıları normalize etmeden
karşılaştırma. Yazım hatası sessizdir; sessiz hata en pahalı hatadır.

### C. `qwen2.5-0.5b` Türkçe'de kullanılamaz

Varsayılan sohbet modeli olan `qwen2.5-0.5b`, Türkçe soruda dejenere tekrar
döngüsüne giriyor ("kendinden ve kendinden ve kendinden...") ve tek bir soru
346 saniye sürüyor.

`src/foundry_rag/extractive.py`'ın başındaki ölçüm tablosu sorunun modelde değil
**dilde** olduğunu gösteriyor:

| Prompt | `qwen2.5-0.5b` çıktısı |
|---|---|
| İngilizce sistem + İngilizce soru | tutarlı ve doğru |
| İngilizce sistem + Türkçe soru | bozuk Türkçe, tek bir anlaşılmaz cümle |
| Türkçe sistem + Türkçe soru | tutarsız kelime yığını |

Bu ölçümün öğretici tarafı, **getirmenin kusursuz** olmasıydı: güven 0.741,
doğru parça 1. sırada. Yani boru hattının getirme yarısı doğru çalışırken üretim
yarısı tamamen çöptü. Bir RAG sisteminde bu iki yarının ayrı ayrı ölçülmesi
gerektiğinin somut kanıtı budur (`eval/evaluate.py` tam olarak bunu yapar).

Hatayı otomatik yakalayan şey kaynaklılık denetleyicisi oldu: **15 cümlenin
0'ı dayanaklı**. Kimse çıktıyı okumadan da bir şeyin bozuk olduğu görülüyordu.

**Daha büyük model denendi ve çözmedi.** Aynı tablonun notu `qwen3-1.7b`'nin daha
da kötü sonuç verdiğini kaydeder. Bu yüzden depoya giren çözüm model değiştirmek
değil, `answer_mode="auto"` devre kesicisi oldu: cevap yine üretilir, ama
kaynaklılık skoru `min_groundedness` (`0.34`) altına düşerse kullanıcıya
gösterilen şey `extractive.extract_answer()`'ın belgelerden yaptığı doğrudan
alıntı olur (`Answer.mode == "extractive-fallback"`). Başka bir sohbet modeli
denemek yine tek satırdır (`FRAG_CHAT_MODEL`); boru hattının geri kalanı
değişmez.

### D. Model önbelleği `app_name`'e göre ayrışır

`FoundryBackend.__init__` varsayılan olarak `app_name="foundry_local_rag"`
kullanır. Foundry Local her uygulama adı için ayrı bir önbellek dizini tutar:
`~/.foundry_local_rag/`, `~/.foundry/` vb.

Sonuç: `app_name` değiştirmek tüm modellerin **yeniden inmesine** yol açar. Bu
bir ayar değeri gibi görünür ama gigabaytlık bir karardır. Değiştirmek
gerekiyorsa `model_cache_dir` parametresiyle önbelleği açıkça sabitle.

---

## 6. Veri modeli

Tüm veri tek bir SQLite dosyasında durur: varsayılan olarak `data/rag.db`.

### `chunks` tablosu

`src/foundry_rag/store.py` içindeki `SCHEMA` sabitinden birebir:

```sql
CREATE TABLE IF NOT EXISTS chunks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT    NOT NULL,
    chunk_index   INTEGER NOT NULL,
    heading       TEXT    NOT NULL DEFAULT '',
    content       TEXT    NOT NULL,
    content_hash  TEXT    NOT NULL UNIQUE,
    embedding     BLOB    NOT NULL,
    dim           INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);
```

| Sütun | Neden var |
|---|---|
| `id` | `load_matrix()` satırları `ORDER BY id` çeker; matris satırı ile kayıt listesi indeksi böylece hizalı kalır |
| `source` | Kaynak gösterimi (`[01-rag-nedir.md]`) ve `sources()` sorgusu |
| `chunk_index` | Parçanın belge içindeki sırası; hata ayıklarken "kaçıncı parça" sorusunu cevaplar |
| `heading` | `ChunkRecord.citation` ve prompt'taki `Bölüm:` etiketi |
| `content` | Prompt'a giren metin. Başlık öneki içermez (o sadece embed'e girer) |
| `content_hash` | `UNIQUE`. `INSERT OR IGNORE` ile birlikte tekrar indekslemeyi idempotent yapar |
| `embedding` | `float32` ham baytlar (bölüm 7) |
| `dim` | Yazılırken `len(vec)` olarak kaydedilir; okurken bütünlük kontrolü için kullanılır |

`idx_chunks_source` indeksi `sources()` ve kaynağa göre filtreleme içindir.
`embedding` sütununda indeks **yoktur** ve olamaz — kosinüs benzerliği B-tree ile
aranamaz, bu yüzden arama kaba kuvvettir.

`dim` sütunu tek başına bir sayıdan fazlasıdır. `load_matrix()` şunu yapar:

```python
dims = {int(r["dim"]) for r in rows}
if len(dims) != 1:
    raise ValueError(
        f"Corrupt index: mixed embedding dimensions {sorted(dims)}. "
        "Re-run ingestion to rebuild the database."
    )
```

Karışık boyutlu satırlar `np.vstack` sırasında anlaşılmaz bir numpy hatası
verirdi. Bu kontrol, hatayı kullanıcının anlayacağı bir cümleye çevirir.

### `index_meta` tablosu

```sql
CREATE TABLE IF NOT EXISTS index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Basit anahtar-değer tablosu. `ingest()` sonunda beş satır yazılır
(`pipeline.py` içindeki sabitler):

| Anahtar | Sabit | Örnek değer |
|---|---|---|
| `embedding_signature` | `META_SIGNATURE` | `foundry-local:qwen3-embedding-0.6b:1024` |
| `chunk_size` | `META_CHUNK_SIZE` | `900` |
| `chunk_overlap` | `META_CHUNK_OVERLAP` | `150` |
| `backend` | `META_BACKEND` | `foundry-local` |
| `document_count` | `META_DOC_COUNT` | `8` |

Hepsini görmek için: `python -m app.cli info`.

`set_meta()` `INSERT ... ON CONFLICT(key) DO UPDATE` kullanır, yani yeniden
indeksleme değerleri günceller, çoğaltmaz.

### `embedding_signature` neden saklanıyor

Bu, projedeki en sinsi hatayı engelleyen mekanizmadır.

Senaryo: Öğrenci `--backend hashing` ile indeksliyor (512 boyutlu vektörler).
Ertesi gün Foundry Local'i kuruyor ve `python -m app.cli ask "..."` çalıştırıyor.
Artık sorgu vektörü 1024 boyutlu, indekstekiler 512 boyutlu.

Bu koruma olmasaydı iki kötü sonuçtan biri olurdu:

1. Boyutlar farklıysa numpy anlaşılmaz bir shape hatası verir.
2. Boyutlar tesadüfen aynı olsaydı (iki farklı 1024 boyutlu model) hiçbir hata
   olmaz, sadece **benzerlik skorları anlamsız** olurdu. Sistem çalışıyor gibi
   görünüp yanlış parçalar getirirdi. Bu, sessiz bozulmadır ve en kötü hata
   türüdür.

Not: bu koruma yalnızca **anlam** yolunu kapsar. BM25 indeksi metinden kurulur,
vektörden değil; embedding modeli değişse bile kelime araması aynı sonucu verir.
Bir başka deyişle hibritin kelime yarısı, vektör uzayı uyumsuzluğuna karşı
bağışıktır — ama eşik dağılımı kaydığı için sistem yine de yeniden kalibre
edilmelidir.

`RagPipeline._check_index()` bunu açılışta yakalar:

```python
stored = self.store.get_meta(META_SIGNATURE)
current = self.backend.embedding_signature()
if stored and stored != current:
    raise RuntimeError(
        "Indeks farkli bir embedding modeliyle olusturulmus.\n"
        f"  indekste: {stored}\n"
        f"  simdiki : {current}\n"
        "Vektor uzaylari uyumsuz. Yeniden indeksle:\n"
        "  python -m app.cli ingest"
    )
```

İki savunma katmanı daha vardır: `cosine_similarity()` boyut uyuşmazlığında
`ValueError` fırlatır, `load_matrix()` karışık `dim` değerlerinde `ValueError`
fırlatır. Üçü birlikte "yanlış vektör uzayı" hatasının sessizce geçmesini
imkânsız kılar.

---

## 7. Vektörlerin `float32` BLOB olarak saklanması

### Karar

```python
VECTOR_DTYPE = np.float32

def encode_vector(vector: Sequence[float]) -> bytes:
    return np.asarray(vector, dtype=VECTOR_DTYPE).tobytes()

def decode_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=VECTOR_DTYPE)
```

Vektör, SQLite'a `BLOB` sütununda ham `float32` baytları olarak yazılır.
Alternatif, listeyi `json.dumps()` ile `TEXT` sütununa yazmaktı.

### Boyut karşılaştırması

Bu projedeki iki gerçek boyut için ölçüldü:

| Vektör boyutu | `float32` BLOB | JSON metin | Oran |
|---|---|---|---|
| 512 (`HashingBackend`) | 2.048 bayt | 10.629 bayt | 5,2x |
| 1024 (`qwen3-embedding-0.6b`) | 4.096 bayt | 21.275 bayt | 5,2x |

BLOB boyutu tam olarak hesaplanabilir: `boyut x 4 bayt`. 1024 x 4 = 4096.

Kendin doğrulamak istersen:

```python
import array, json, random
v = [random.uniform(-1, 1) for _ in range(1024)]
len(array.array('f', v).tobytes())   # 4096
len(json.dumps(v))                   # ~21000
```

### Hız karşılaştırması

JSON yolu her satır için şunu gerektirir: metin çöz (`json.loads`) -> Python
`float` listesi kur -> `np.asarray` ile numpy'a çevir. Üç adım, hepsi Python
seviyesinde, satır başına.

BLOB yolu tek adımdır: `np.frombuffer(blob, dtype=np.float32)`. Bu fonksiyon
veriyi kopyalamaz bile, mevcut bayt tamponunun üstüne bir numpy görünümü açar.
`load_matrix()` sonra tek `np.vstack` ile hepsini `(n, dim)` matrise yığar ve
arama tek bir matris çarpımına indirgenir.

### Tek tehlike: dtype tutarlılığı

`store.py`'ın en başındaki uyarı bunu söyler: yazarken ve okurken **aynı** dtype
kullanılmalıdır. `float32` yazıp `float64` okursan hata almazsın — `frombuffer`
baytları sessizce yanlış yorumlar ve tamamen çöp sayılar döner. Bu yüzden dtype
tek bir yerde, `VECTOR_DTYPE` sabitinde tanımlıdır ve iki fonksiyon da onu
kullanır.

`float32` seçilme sebebi: embedding modellerinin ürettiği hassasiyet zaten
`float32` düzeyindedir. `float64`'e yükseltmek dosyayı iki katına çıkarır,
kosinüs benzerliği sonucunu ise ölçülebilir biçimde değiştirmez.

---

## 8. Tasarım kararları ve gerekçeleri

| Karar | Alternatif | Neden bu seçildi |
|---|---|---|
| SQLite + numpy kaba kuvvet arama | `sqlite-vec`, FAISS, Chroma, Qdrant | macOS sistem Python'unda `enable_load_extension` yok, `sqlite-vec` kurulamıyor. Ayrıca bu ölçekte (yüzler-binler) tek matris çarpımı milisaniyeler sürüyor ve sıfır ek bağımlılık gerektiriyor |
| Vektörler `float32` BLOB | JSON `TEXT` sütunu | 5,2x daha küçük; okuma tek `np.frombuffer` çağrısı, kopyalama yok |
| `Backend` ABC + iki uygulama | `FoundryBackend`'i doğrudan `pipeline.py`'dan çağırmak | Testler çevrimdışı, hızlı ve deterministik koşuyor; öğrenci ilk gün model indirmeden projeyi uçtan uca çalıştırabiliyor |
| `create_backend()`'de lazy import | Modül başında `from .foundry import ...` | `hashing` yolunu kullanan kimse ağır native SDK bağımlılığını yüklemek zorunda kalmıyor |
| `auto` varsayılan backend | Sadece `foundry` | İlk çalıştırmada Foundry Local hazır değilse proje çökmek yerine görünür bir uyarıyla yedeğe geçiyor |
| `foundry` modu sert başarısız oluyor | Her zaman sessizce yedeğe geçmek | Ortam kurulduktan sonra bozuk bir kurulumun sessizce yavaş/yanlış çalışması, hata vermesinden daha kötü |
| `ingest(reset=True)` varsayılan | Artımlı güncelleme | Silinen veya düzenlenen bir belgenin bayat parçalarını geride bırakmayan tek strateji bu; bu korpus boyutunda yeniden kurmak zaten ucuz |
| `content_hash` `UNIQUE` + `INSERT OR IGNORE` | Her seferinde koşulsuz `INSERT` | `--append` ile tekrar indeksleme kopya satır üretmiyor |
| `min_similarity = 0.30` eşiği | Her zaman `top_k` parça döndürmek | Eşik olmadan cevabı belgelerde olmayan soru için "en az kötü" parçalar döner ve model onlardan cevap uydurur |
| Eşiğin `eval/calibrate.py` ile veriden seçilmesi | Makul görünen bir sayı yazmak | Tahminin bedeli ölçüldü: `0.15` yalnız-vektör skorları için ayarlanmıştı, BM25 eklenince skor dağılımı kaydı ve reddetme doğruluğu %87.5'ten %12.5'e düştü. Doğru eşik korpusa ve retriever'a bağlıdır |
| Hibrit getirme (BM25 + vektör), RRF ile füzyon | Yalnızca kosinüs benzerliği | İki arama farklı yerlerde başarısız olur: vektör nadir literalleri (`1536`, model adı), kelime araması eş anlamlıları kaçırır. Recall birleşim olur, kesişim değil |
| Füzyonun **sıra** üzerinden yapılması | Ham skorların ağırlıklı toplamı | Kosinüs `[-1, 1]`, BM25 sınırsız ve korpusa bağlı; ham toplam her korpusta yeniden ayar ister, sıralar kalibrasyonsuz karşılaştırılabilir. `k = 60` Cormack ve ark. (2009) |
| Her kelimenin **hem yüzey biçimi hem gövdesi** indeksleniyor (`expand_tokens()`) | Yalnızca gövdeyi indekslemek | Kural tabanlı bir stemmer son ünlünün ek mi kök harfi mi olduğunu bilemez: `belge` -> `belg` ama `belgeler` -> `belge`, yani tek biçimle bu ikisi asla buluşmaz. İkisini birden indekslemek sorunu kural eklemeden kaldırır — gövde bir recall arttırıcıdır, doğruluk kaynağı değil |
| Üretimden sonra cümle bazlı kaynaklılık denetimi (`groundedness.py`) | Cevabı olduğu gibi sunmak | Doğru parçayı getirmek modelin o parçanın içinde kaldığını göstermez; uydurulmuş bir cümle, yanındaki kaynak etiketiyle doğrusundan ayırt edilemez görünür. Denetim model çağrısı gerektirmez |
| Kaynaklılığın **leksik örtüşme** ile ölçülmesi | NLI (doğal dil çıkarımı) modeli | NLI çelişkiyi ve ortak kelimesiz eş anlamlıyı yakalardı; karşılığında ikinci bir model indirmesi, cümle başına ikinci bir çıkarım geçişi ve çevrimdışı yedeğin karşılayamayacağı bir bağımlılık isterdi. Leksik ölçü asıl önemli hatayı zaten yakalıyor: modelin bağlamda hiç geçmeyen bir şeyi iddia etmesi (ölçüldü: doğru cevapta %100, uydurmada %0) |
| Kaynaklılık düşükse alıntıya düşen devre kesici (`answer_mode="auto"`) | Üretilen cevabı her hâlükârda göstermek | Kendi bağlamından doğrulanamayan bir cevabı yine de sunmak, ölçülmüş güvenilmezliği bilerek sunmaktır. Alıntı daha kötü bir metin, daha iyi bir bilgidir |
| İndeksin `RagPipeline.__init__` içinde bir kez belleğe alınması | Her soruda `store.load_matrix()` çağırmak | Eskiden her soru bir tam tablo taraması + bir `np.vstack` + BM25 kurulumu demekti; bu maliyet soru sayısından bağımsızdır ve açılışta bir kez ödenmelidir |
| `hits` boşken model **hiç** çağrılmıyor | Boş bağlamla modeli çağırıp "bilmiyorum" demesini ummak | `qwen2.5-0.5b` gibi küçük bir model boş bağlamda kuralı unutup uyduruyor. Ayrıca gereksiz saniyeler harcanmıyor |
| `embedding_signature` meta satırı | Hiçbir şey saklamamak | Vektör uzayı değiştiğinde sistem sessizce yanlış sonuç üretmek yerine açık hata veriyor (bölüm 6) |
| Embed'e başlık öneki (`with_heading_prefix()`) | Ham parça metnini embed etmek | Belgeden koparılmış parça hangi bölüme ait olduğunu kaybediyor; başlık öneki yapılandırılmış belgelerde eşleşmeyi iyileştiriyor |
| `embedding_dim` çalışma anında ölçülüyor | Kodda `1024` sabiti | Boyut modelin özelliği, her alias için belgelenmiş değil ve model değişince sabit sessizce yanlışa dönüşür |
| Streaming döngüsünde `if not chunk.choices: continue` | Microsoft'un tutorial kodundaki korumasız indeksleme | Son chunk boş `choices` ile gelebiliyor ve tutorial kodu cevabı yazdırdıktan hemen sonra `IndexError` ile çöküyor (Foundry-Local issue #905, açık) |
| `if FoundryLocalManager.instance is None` kontrolü | Doğrudan `initialize()` çağırmak | Manager bir singleton; ikinci `initialize()` hata veriyor. Streamlit her etkileşimde script'i yeniden çalıştırdığı, `uvicorn --reload` ve notebook hücreleri de tekrar çalıştırdığı için bu kontrol olmadan çöküyor |
| `download_and_register_eps()` hatası ölümcül değil | Hata fırlatmak | macOS'ta hızlandırma WebGPU (Dawn -> Metal) üzerinden gidiyor ve bu çağrı no-op olabiliyor; başarısızlığı çalışmayı engellememeli |
| `load()` sonrası model id + execution provider yazdırılıyor (`describe_variant()`) | Sessizce devam etmek | GPU EP doğru kaydolsa bile bazen sadece CPU varyantı seçilebiliyor (issue #858 / #895); yavaş build'de çalıştığını fark etmenin tek yolu bunu yazdırmak |
| `stream_chat` isteğe bağlı, `getattr` ile yoklanıyor | ABC'ye zorunlu metod eklemek | `HashingBackend`'in akıtacak bir şeyi yok; sözleşmeyi minimum tutmak yeni backend yazmayı kolaylaştırıyor |
| Tüm ayarlar tek `Settings` dataclass'ında + `FRAG_*` ortam değişkenleri | Sabitleri modüllere dağıtmak | Deney tek satır: `FRAG_TOP_K=8 python -m app.cli ask "..."` |
| `settings.validate()` her akışın başında | Değerleri kullanıldıkları yerde kontrol etmek | `chunk_overlap >= chunk_size` gibi bir hata parçalamanın ortasında değil, hiçbir şey yazılmadan önce yakalanıyor |
| `temperature = 0.1` | Model varsayılanı (daha yüksek) | Bağlama dayalı cevapta yaratıcılık istenmiyor; düşük sıcaklık kuralları takip etmeyi ve alıntı formatını korumayı artırıyor |
| Streamlit'te `@st.cache_resource` | Her yeniden çalıştırmada yeni pipeline | Model yükleme maliyetinden bağımsız olarak, singleton manager ikinci kez kurulamaz |
| `_bootstrap.py` ile `sys.path`'e `src/` ekleme | `pip install -e .` zorunlu tutmak | Depoyu yeni klonlayan öğrenci `python -m app.cli` komutunu hemen çalıştırabiliyor |

---

## 9. Bilinçli sınırlar

Aşağıdakiler eksiklik değil, kapsam dışı bırakılmış şeylerdir. Her biri neyin
ne zaman değişmesi gerektiğini söyler.

### Kaba kuvvet arama ~100 bin parçaya kadar

`store.load_matrix()` her sorguda **tüm** vektörleri belleğe yükler. Docstring
bunu açıkça sınırlar: "Loading everything into memory is deliberate ... Revisit
only past ~100k chunks."

Somut hesap: 1024 boyutlu `float32` vektör = 4.096 bayt. 100.000 parça =
yaklaşık 410 MB matris. Bunun üstünde:

- Bellek kullanımı rahatsız edici olur.
- Her sorguda tüm matrisi diskten okumak, arama süresini LLM çağrısına kıyasla
  önemsiz olmaktan çıkarır.

Bu sınıra yaklaşırsan yapılacak şey `retrieval.py`'ı bir ANN indeksiyle
(FAISS, hnswlib) değiştirmektir. `search()` imzası aynı kalabilir, çünkü arayüz
zaten `store` ve `query_vector` alıp `list[SearchHit]` döndürüyor.

### Tek kullanıcı, tek süreç

`VectorStore.__init__` tek bir `sqlite3.connect()` bağlantısı açar ve bu bağlantı
`RagPipeline` ömrü boyunca yaşar. Proje şunları varsaymaz ve desteklemez:

- Aynı veritabanına eşzamanlı yazan birden fazla süreç
- Kullanıcı hesapları, oturum yönetimi, yetkilendirme
- Ağ üzerinden paylaşılan indeks

Streamlit arayüzü tarayıcıda çalışsa da tek bir yerel süreçtir. Birden fazla
kişi aynı anda kullanırsa `st.cache_resource` ile paylaşılan tek bir pipeline'ı
paylaşırlar; bu proje bunun için tasarlanmadı.

### Çok turlu sohbet geçmişi yok

`build_messages()` tam olarak iki mesaj döndürür:

```python
[
    {"role": "system", "content": build_system_prompt(language)},
    {"role": "user",   "content": build_user_prompt(question, hits)},
]
```

Önceki soru ve cevaplar modele hiç gönderilmez. Sonucu:

- "Peki onun avantajı ne?" gibi bir takip sorusu çalışmaz. "Onun" neye
  gönderdiğini model bilmez.
- Her soru bağımsız olarak embed edilir ve bağımsız olarak aranır.

`app/cli.py chat` komutundaki döngü ve Streamlit'teki `st.session_state.history`
sadece **ekranda** geçmiş gösterir; modele gitmez.

Bunu eklemek isteyen için doğru yer `prompts.py`'daki `build_messages()`'tır ve
dikkat edilecek nokta şudur: geçmiş mesajlar bağlam penceresini yer, `top_k`
parça için kalan yeri azaltır. Küçük modellerde bu takas hızla zarara döner.

### Diğer bilinçli kapsam dışılıklar

| Yok olan | Sonucu | Nerede eklenirdi |
|---|---|---|
| Yeniden sıralama (reranker) | `top_k` parça füzyon sırasına göre seçilir; ikinci bir model onları yeniden puanlamaz | `retrieval.py`, `hybrid_search()` sonrası |
| Sorgu genişletme için LLM kullanımı | Sorgu, kullanıcının yazdığı hâliyle aranır | `pipeline.py`, `retrieve()` |
| Doğal dil çıkarımı (NLI) ile kaynaklılık | `groundedness.py` kelime örtüşmesine bakar; çelişkiyi ve ortak kelimesiz eş anlamlıyı yakalayamaz | `groundedness.py`, `support_score()` |
| Artımlı indeksleme | Bir belge değişince tüm indeks yeniden kurulur | `pipeline.py`, `ingest()` |
| PDF / DOCX / HTML okuma | Sadece `.md`, `.markdown`, `.txt`, `.rst` (`TEXT_SUFFIXES`) | `pipeline.py`, `iter_documents()` |
| Sorgu genişletme / yeniden yazma | Kötü ifade edilmiş soru kötü sonuç verir | `pipeline.py`, `retrieve()` |
| Cevap önbelleği | Aynı soru iki kez sorulursa iki kez üretilir | `pipeline.py`, `answer()` |
| İndeks bütünlük doğrulaması | Bozuk model önbelleği tespit edilmez (Foundry-Local issue #909 / #906, açık) | `scripts/doctor.py` |

### "Çevrimdışı" ne zaman geçerli

Proje çevrimdışı çalışır, ama **ilk çalıştırmadan sonra**. İlk `ingest`
sırasında model kataloğu ve model dosyaları ağdan çekilir. `HashingBackend` ise
ilk andan itibaren ağ kullanmaz — bu yüzden testler ve `--backend hashing` yolu
tamamen çevrimdışıdır.

---

## Kontrol listesi: mimariyi anladın mı

Aşağıdakileri kodun içinde bulabiliyorsan bu belgeyi işlevsel olarak okumuşsundur.

- [ ] `ingest()` ile `RagPipeline`'ın biri fonksiyon biri sınıf — sebebini
      söyleyebiliyor musun?
- [ ] `backend.embed()`'e giden metinle `chunks.content` sütununa yazılan metnin
      neden farklı olduğunu gösterebiliyor musun?
- [ ] `hits` boşken hangi satırın modeli çağırmayı engellediğini
      `pipeline.py`'da bulabiliyor musun?
- [ ] `embedding_signature` uyuşmazlığını üreten senaryoyu iki komutla
      canlandırabiliyor musun? (`--backend hashing` ile indeksle, `--backend
      foundry` ile sor)
- [ ] `python -m app.cli info` çıktısındaki beş meta satırının hangi kod
      satırında yazıldığını gösterebiliyor musun?
- [ ] `store.py` içinde neden hiç `backend` kelimesi, `backends/` içinde neden
      hiç `sqlite3` geçmediğini açıklayabiliyor musun?
- [ ] `np.frombuffer(blob, dtype=np.float64)` yazarsan ne olacağını
      söyleyebiliyor musun?
- [ ] Bir kaynak satırında `bulan: kelime` yazıyorsa o parçayı hangi
      retriever'ın bulduğunu ve `score` alanının hangi iki sayıdan `max()` ile
      seçildiğini gösterebiliyor musun?
- [ ] `self.matrix`, `self.records` ve `self.bm25` alanlarının `pipeline.py`
      içinde hangi satırda kurulduğunu ve neden `retrieve()` içinde
      kurulmadığını söyleyebiliyor musun?
- [ ] `expand_tokens("belgeler")` ile `expand_tokens("belge")` çıktılarının
      hangi tokende buluştuğunu yazabiliyor musun?

Doğrulamak için:

```bash
python -m app.cli --backend hashing ingest
python -m app.cli info
python -m app.cli --backend hashing ask "Kosinüs benzerliği nedir?"
python -m pytest tests/ -q
python eval/evaluate.py --backend hashing
python eval/calibrate.py --backend hashing
```
