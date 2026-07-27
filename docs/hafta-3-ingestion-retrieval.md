# Hafta 3 -- Veri Alımı ve Getirme Boru Hattı

**Faz 2: Proje Geliştirme** | Yaz okulu, tam zamanlı

Bu hafta modelle değil, **veriyle** uğraşıyoruz. Bir RAG sisteminin cevap kalitesinin
büyük kısmı, model daha devreye girmeden önce belirlenir: belgeyi nasıl parçaladığın,
her parçaya hangi bilgiyi iliştirdiğin ve arama sırasında hangi eşiği koyduğun.

Bu haftanın sonunda elinde şunlar olacak:

- `data/rag.db` içinde **dolu bir SQLite veritabanı**
- Sorulara ilgili parçalar döndüren **çalışan bir getirme (retrieval) katmanı**
- Kendi ölçümlerinle doldurduğun bir **eval tablosu**

---

## 1. Ön koşullar

Hafta 1-2'de kurduğun ortam ayakta olmalı.

```bash
cd ~/Desktop/foundry-local-rag
source .venv/bin/activate
python --version          # 3.11 veya üstü olmalı
python scripts/doctor.py
python -m pytest tests/ -q   # 163 test, hepsi geçmeli
```

`python --version` çıktısı `3.9.6` diyorsa venv aktif değil ya da venv sistem
Python'uyla kurulmuş demektir. Foundry Local SDK 1.x **Python >= 3.11** ister;
Python 3.9'da `pip install foundry-local-sdk` hata vermeden eski **0.5.1** sürümünü
kurar ve modül adı `foundry_local_sdk` yerine `foundry_local` olur. Bu projedeki
1 numaralı tuzak budur. Çözüm: `brew install python@3.12`, sonra yeni bir venv.

> **Bu haftanın alıştırmaları için Foundry Local şart değil.**
> Bütün ölçümleri `--backend hashing` ile yapabilirsin. `HashingBackend` çevrimdışı,
> deterministik ve hızlıdır; aynı metin her çalıştırmada aynı vektörü üretir
> (`src/foundry_rag/backends/hashing.py`, `blake2b` tabanlı işaretli hashing).
> Ölçümlerin tekrarlanabilir olması için bu haftaki tüm eval koşularını **aynı
> backend ile** yap.

---

## 2. Boru hattının haritası

İki akış var ve bilerek ayrılmışlardır:

| Akış | Ne zaman çalışır | Maliyet | Giriş noktası |
| --- | --- | --- | --- |
| **Ingestion** (veri alımı) | Belgeler değiştiğinde, nadiren | Yavaş: her parça için embedding | `ingest()` -- `src/foundry_rag/pipeline.py` |
| **Query** (sorgu) | Her soruda | Hızlı: 1 embedding + 1 matris çarpımı | `RagPipeline.retrieve()` / `.answer()` |

Bu ayrım olmasaydı uygulama her açılışta tüm külliyatı yeniden embed ederdi.

Ingestion adımları, `pipeline.py` içindeki `ingest()` fonksiyonunun gerçek sırası:

```
data/docs/*.md
   -> iter_documents()          dosyaları oku (.md .markdown .txt .rst)
   -> chunk_document()          bölüm -> paragraf -> cümle sırasıyla parçala
   -> Chunk.with_heading_prefix()   embed edilecek metni hazırla
   -> backend.embed(batch)      16'lık gruplar hâlinde (EMBED_BATCH_SIZE = 16)
   -> VectorStore.add_chunks()  float32 BLOB olarak SQLite'a yaz
   -> store.set_meta(...)       imza, chunk_size, overlap, backend, belge sayısı
```

Sorgu adımları, `RagPipeline.retrieve()`:

```
soru -> backend.embed([soru])[0]
     -> hybrid_search(records, matrix, vektör, query_text=soru, bm25=...,
                      top_k, min_similarity, lexical_scale)
        (kosinüs + BM25, RRF ile birleştirilir)
     -> list[SearchHit]  (her biri: ChunkRecord + guven/anlam/kelime skorlari)
```

`settings.hybrid = False` iken BM25 kurulmaz ve aynı fonksiyon yalnızca vektör
sıralamasıyla çalışır. Salt vektör arayan bağımsız `search(store, ...)`
fonksiyonu da durur; testlerde ve kıyaslamalarda kullanılır.

Bu hafta dokunacağın dosyalar:

| Dosya | Sorumluluk |
| --- | --- |
| `src/foundry_rag/chunking.py` | `Chunk`, `chunk_text()`, `chunk_document()`, `with_heading_prefix()` |
| `src/foundry_rag/store.py` | `VectorStore`, `encode_vector()`, `decode_vector()`, şema |
| `src/foundry_rag/retrieval.py` | `cosine_similarity()`, `search()`, `hybrid_search()`, `SearchHit` |
| `src/foundry_rag/pipeline.py` | `ingest()`, `RagPipeline`, `IngestReport` |
| `src/foundry_rag/config.py` | `Settings` ve `FRAG_*` ortam değişkenleri |
| `eval/evaluate.py` | Recall@K, MRR, reddetme doğruluğu |

---

## 3. Teori

### 3.1 Neden parçalıyoruz?

Üç ayrı sebep var ve karıştırılmamaları gerekir:

1. **Bağlam penceresi.** Tüm külliyatı prompt'a sığdıramazsın.
2. **Getirme çözünürlüğü.** Bir belgenin tamamı tek vektöre indirgenirse, o vektör
   belgedeki her konunun ortalaması olur ve hiçbir soruya net eşleşmez. Küçük
   parçalar daha keskin sinyal verir.
3. **Alıntılanabilirlik.** Kullanıcıya "şu dosyanın şu bölümü" diyebilmek için
   parçanın nereden geldiğini bilmek gerekir (`ChunkRecord.citation`).

### 3.2 Üç parçalama stratejisi

| Strateji | Nasıl çalışır | Artı | Eksi |
| --- | --- | --- | --- |
| **Sabit boyut** (fixed-size) | Metni her N karakterde bir kes | Uygulaması en basit, boyut garantisi verir | Cümleyi, tabloyu, kod bloğunu ortadan böler |
| **Ayraca göre** (delimiter / recursive) | Önce paragraf (`\n\n`), sığmazsa cümle, o da sığmazsa karakter | Anlam birimlerini korur, boyut hâlâ kontrollü | Ayraç yoksa (tek dev paragraf) sabit boyuta düşer |
| **Yapıya göre** (structure-aware) | Belgenin kendi yapısını kullanır: Markdown başlıkları, HTML bölümleri | Parça = mantıksal bölüm; başlık meta veri olarak kazanılır | Yapısız düz metinde işe yaramaz; bölüm boyutları çok değişken olur |

**Bu repo üçünü kademeli olarak birleştirir.** `chunking.py` sırasıyla:

1. `_iter_sections()` -- `^#{1,6}\s+` düzenli ifadesiyle Markdown başlıklarını bulur,
   belgeyi `(heading, body)` çiftlerine ayırır. **Bir parça asla iki bölüme yayılmaz.**
2. `chunk_text()` -- her bölüm gövdesini `\n\s*\n` ile paragraflara böler,
   `_pack_units()` ile `chunk_size`'ı aşmayacak şekilde açgözlü paketler.
3. Tek başına `chunk_size`'dan uzun bir paragraf varsa `_split_sentences()` devreye
   girer (`.`, `!`, `?`, `…` sonrası boşluk).
4. Tek bir cümle bile sığmıyorsa `_hard_split()` ile ham karakter kesimi yapılır.

Bu kademelerin doğrudan ölçülebilir bir sonucu var ve A3.1'de karşına çıkacak:
**`chunk_size` bir üst sınırdır, hedef değil.** Belgedeki en büyük bölüm
`chunk_size`'dan küçükse, `chunk_size`'ı büyütmek hiçbir şeyi değiştirmez.

Bir ayrıntı daha: üretilen parça `chunk_size`'ı biraz aşabilir, çünkü örtüşme öneki
paketlenmiş metnin başına eklenir. `tests/test_chunking.py::test_chunks_respect_size_limit`
bu toleransı açıkça `chunk_size + chunk_overlap` olarak kabul eder. Kodu okurken
"neden 220 karakterlik parça çıktı" diye şaşırma.

### 3.3 Örtüşme (overlap)

Sınırda duran bir bilgi, örtüşme yoksa iki parçanın da yarısında kalır ve hiçbiri
soruyla eşleşmez. Klasik örnek: "Foundry Local macOS'ta yalnızca arm64 destekler."
cümlesi bir parçanın son satırında, gerekçesi sonraki parçanın ilk satırında olsun.
Getirme birini bulur, cevap yarım kalır.

`_tail_overlap(text, overlap)` bunu şöyle çözer:

- Önceki parçanın **son `chunk_overlap` karakterini** alır.
- İlk boşluğu bulup ondan sonrasını keser, yani **kelime ortasından başlamaz**.
- Sonucu bir sonraki parçanın önüne ekler.

Varsayılanlar (`config.py`): `chunk_size = 900`, `chunk_overlap = 150` -- yaklaşık
%17 örtüşme. Pratik aralık %10-20'dir.

`chunk_overlap >= chunk_size` olursa `chunk_text()` `ValueError` fırlatır ve
`Settings.validate()` da aynı kontrolü yapar. Sebebi mekanik: örtüşme parçadan büyük
olsaydı paketleme hiç ilerlemez, sonsuz döngüye girerdi.

Örtüşmenin bedeli depolamadır: aynı metin iki parçada durur, veritabanı ve embedding
maliyeti artar. Bedava değil.

### 3.4 Başlık öneki neden getirme kalitesini artırır?

`Chunk.with_heading_prefix()`:

```python
def with_heading_prefix(self) -> str:
    if self.heading:
        return f"{self.heading}\n\n{self.text}"
    return self.text
```

`pipeline.py` içinde embedding tam olarak bu metin üzerinden alınır:

```python
vectors = backend.embed([c.with_heading_prefix() for c in batch])
```

ama veritabanına **başlıksız** hâli (`c.text`) yazılır. Yani başlık *vektörü* etkiler,
*prompt'a giren metni* şişirmez.

Mekanizma şu: bir parça belgeden koparıldığı anda bağlamını kaybeder. Şu cümleyi
tek başına düşün:

> "Varsayılan 900 karakterdir ve örtüşme 150'dir."

Bu cümlenin vektörü "neyin varsayılanı" bilgisini taşımaz. Kullanıcı
"parça boyutu varsayılanı nedir?" diye sorduğunda sorunun vektöründe "parça",
"boyut" kavramları vardır ama parçanın vektöründe yoktur; benzerlik düşük çıkar.
Başına `Parçalama parametreleri` başlığını koyduğunda o kavramlar parçanın
vektörüne girer ve eşleşme yükselir.

Bunun iki yan etkisi vardır ve ikisini de A3.3'te gözlemleyeceksin:

- **Artı:** kısa, zamir yüklü, "bu", "yukarıdaki" diyen parçalar aranabilir hâle gelir.
- **Eksi:** aynı belgedeki tüm parçalar aynı başlığı paylaştığı için birbirlerine
  benzemeye başlar; bölüm içi ayırt edicilik bir miktar düşer.

Bu yüzden bunu "her zaman doğru" diye ezberleme, **ölç**.

### 3.5 Meta veri

İki katman var.

**Parça düzeyi** -- `chunks` tablosu (`store.py` içindeki `SCHEMA`):

| Sütun | Nereden gelir | Ne işe yarar |
| --- | --- | --- |
| `source` | dosya adı | Alıntı, eval'de `expected_source` karşılaştırması |
| `chunk_index` | belge içindeki sıra | Parçanın belgedeki yerini bulmak |
| `heading` | `_iter_sections()` | `citation` üretimi, prompt'ta `Bölüm:` satırı |
| `content` | başlıksız parça metni | Prompt'a giren gerçek metin |
| `content_hash` | `sha256(source + heading + text)` | `UNIQUE` -- tekrarlı ekleme engeli |
| `embedding` | `encode_vector()` | float32 ham baytlar (BLOB) |
| `dim` | `len(vec)` | Boyut uyuşmazlığını yakalamak |

Vektörler JSON değil **BLOB** olarak tutulur. `float32` yazıp `float64` okursan
hata almazsın, sessizce çöp okursun. `VECTOR_DTYPE` tek noktada tanımlı olduğu için
yazma ve okuma aynı dtype'ı kullanır.

**İndeks düzeyi** -- `index_meta` tablosu, `ingest()` sonunda yazılır:

`embedding_signature`, `chunk_size`, `chunk_overlap`, `backend`, `document_count`.

`embedding_signature` en kritik olanıdır. `HashingBackend` için `hashing-offline:512`,
Foundry backend için `foundry-local:<alias>:<dim>` biçimindedir (`qwen3-embedding-0.6b`
**1024 boyutlu** vektör üretir). `RagPipeline._check_index()` açılışta imzayı
karşılaştırır ve uyuşmazsa çalışmayı reddeder:

```
Indeks farkli bir embedding modeliyle olusturulmus.
```

Bu kontrol olmasaydı 512 boyutlu bir indekste 1024 boyutlu sorgu vektörüyle arama
yapmaya çalışırdın; `cosine_similarity()` boyut uyuşmazlığını yakalayıp `ValueError`
verir, ama aynı boyutlu **farklı** iki model kullansaydın hiç hata almadan anlamsız
skorlar üretirdin. Sessiz yanlış, gürültülü hatadan çok daha tehlikelidir.

İndeksin şu anki durumunu görmek için:

```bash
python -m app.cli info
```

### 3.6 Yeniden indeksleme stratejisi

`ingest()` imzası: `ingest(settings, backend=None, reset=True, verbose=True)`.

**Varsayılan `reset=True`, yani tam yeniden inşa.** `VectorStore.reset()` hem
`chunks` hem `index_meta` tablosunu boşaltır. Sebebi: bir belge silindiğinde veya
düzenlendiğinde eski parçaları indekste bırakmayan **tek** basit strateji budur.
Bu külliyat boyutunda tam yeniden inşa saniyeler sürer.

`--append` bayrağı `reset=False` yapar. Bu durumda `INSERT OR IGNORE` +
`content_hash UNIQUE` sayesinde ekleme **idempotent** olur: değişmemiş parçalar
yeniden eklenmez, `IngestReport.inserted` sadece gerçekten yazılan satırları sayar.
Ama silinen belgelerin parçaları indekste kalır. `--append`'i yalnızca külliyata
yeni dosya eklerken kullan.

Yeniden indekslemek **zorunlu** olduğu durumlar:

- [ ] `chunk_size` veya `chunk_overlap` değişti
- [ ] `with_heading_prefix()` mantığı değişti (A3.3'te yapacağın şey)
- [ ] Embedding modeli / backend değişti (`hashing` <-> `foundry`)
- [ ] `data/docs/` içinde bir dosya düzenlendi veya silindi

Yeniden indekslemek **gereksiz** olduğu durumlar:

- [ ] `top_k` değişti
- [ ] `min_similarity` değişti (A3.4'te yapacağın şey)
- [ ] Sistem prompt'u veya sohbet modeli değişti

Bu ayrımı A3.3 ile A3.4'ün ne kadar sürdüğünden fiziksel olarak hissedeceksin.

---

## 4. Alıştırmalar

Her alıştırmanın çıktısını `docs/hafta-3-sonuclarim.md` adlı kendi dosyanda topla.
Teslim edeceğin şey o dosya.

### A3.1 -- `chunk_size` etkisini ölç

**Amaç:** `chunk_size`'ın parça sayısına ve parça uzunluk dağılımına etkisini görmek.

1. `src/foundry_rag/chunking.py`'yi baştan sona oku. Şu dört fonksiyonun ne yaptığını
   kendi cümlelerinle bir satırda yaz: `_iter_sections`, `_pack_units`,
   `_tail_overlap`, `_split_sentences`.
2. Deney betiğini oluştur:

```bash
mkdir -p experiments
```

`experiments/a31_chunk_sizes.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from foundry_rag.chunking import chunk_document

DOC = Path(__file__).resolve().parents[1] / "data" / "docs" / "06-belge-parcalama.md"
text = DOC.read_text(encoding="utf-8")
print(f"kaynak karakter: {len(text)}")

for chunk_size in (200, 900, 2000):
    overlap = min(150, chunk_size // 4)   # overlap < chunk_size olmak zorunda
    chunks = chunk_document(text, DOC.name, chunk_size=chunk_size, chunk_overlap=overlap)
    lengths = [len(c.text) for c in chunks]
    print(
        f"chunk_size={chunk_size:5d} overlap={overlap:4d} "
        f"parca={len(chunks):3d} min={min(lengths):4d} "
        f"max={max(lengths):4d} ort={sum(lengths) // len(lengths):4d}"
    )
```

```bash
python experiments/a31_chunk_sizes.py
```

**Referans çıktı** (`06-belge-parcalama.md`, 3004 karakter):

```
kaynak karakter: 3004
chunk_size=  200 overlap=  50 parca= 22 min=  67 max= 220 ort= 160
chunk_size=  900 overlap= 150 parca=  6 min= 236 max= 692 ort= 470
chunk_size= 2000 overlap= 150 parca=  6 min= 236 max= 692 ort= 470
```

3. Şu üç soruyu yazılı cevapla:
   - `chunk_size=900` ile `chunk_size=2000` neden **birebir aynı** sonucu verdi?
     (İpucu: `chunk_document()` önce neye göre bölüyor?)
   - `chunk_size=200` iken `max=220` çıktı. 200'ü aşan 20 karakter nereden geldi?
   - `chunk_size=200` çıktısında en kısa parçayı ekrana bastır. Tek başına
     okunduğunda anlamlı mı? Bir soruya cevap olabilir mi?
4. Aynı betiği `data/docs/` altındaki en uzun dosyayla tekrar çalıştır ve sonucun
   değişip değişmediğine bak.

**Teslim:** üç `chunk_size` için tablo + üç sorunun cevabı.

### A3.2 -- Kendi bilgi tabanını kur

**Amaç:** Boru hattını kendi verinle uçtan uca çalıştırmak.

1. 5-10 kendi belgeni hazırla. Ders notu, staj raporu, bir kütüphanenin dokümanı,
   kendi projenin README'leri -- fark etmez. **Markdown başlıkları (`#`, `##`) kullan**,
   yoksa yapıya göre parçalama devre dışı kalır ve `heading` boş gelir.
   Desteklenen uzantılar (`pipeline.py`, `TEXT_SUFFIXES`): `.md`, `.markdown`,
   `.txt`, `.rst`. Boş dosyalar atlanır ve `IngestReport.skipped` içinde listelenir.
2. Referans indeksini bozmamak için ayrı klasör ve ayrı veritabanı kullan:

```bash
mkdir -p data/mydocs
# belgeleri data/mydocs/ altına kopyala

FRAG_DOCS_DIR=data/mydocs FRAG_DB_PATH=data/mydocs.db \
  python -m app.cli --backend hashing ingest
```

3. İndeksi doğrula ve sor:

```bash
FRAG_DOCS_DIR=data/mydocs FRAG_DB_PATH=data/mydocs.db python -m app.cli info

FRAG_DB_PATH=data/mydocs.db \
  python -m app.cli --backend hashing ask "kendi belgene dair bir soru"
```

4. En az 5 soru sor. Bunlardan **2 tanesi belgelerinde cevabı olmayan** soru olsun.
   Sistem "Bu bilgi elimdeki belgelerde yok." diyor mu?
5. `--append` davranışını gör: bir belge daha ekle, `--append` ile indeksle,
   `python -m app.cli info` çıktısındaki parça sayısının nasıl değiştiğini not et.
   Sonra bir belgeyi sil, tekrar `--append` ile indeksle. Silinen belgenin parçaları
   hâlâ orada mı?

> **CLI tuzağı:** `--backend`, `--top-k`, `--min-similarity` ve `-v` **genel**
> bayraklardır, alt komuttan **önce** yazılır. `--chunk-size`, `--chunk-overlap`
> ve `--append` ise `ingest` alt komutuna aittir, **sonra** yazılır:
> `python -m app.cli --backend hashing ingest --chunk-size 400 --chunk-overlap 60`

**Teslim:** `info` çıktısı + 5 soru ve cevapları + `--append` gözlemin.

### A3.3 -- Başlık önekinin etkisini ölç

**Amaç:** `with_heading_prefix()`'in Recall@4'e katkısını sayıyla göstermek.

Bu deneyde kodu **geçici olarak** değiştireceksin. Değişikliği geri almayı unutma.

1. Taban çizgisini al (başlık öneki **açık**, mevcut kod):

```bash
python -m app.cli --backend hashing ingest
python eval/evaluate.py --backend hashing
```

Beklenen (deponun varsayılanı: hibrit getirme, `top_k=4`,
`min_similarity=0.30`):

| Metrik | Değer |
| --- | --- |
| Recall@4 | %88.0 |
| MRR | 0.793 |
| Reddetme doğruluğu | %100.0 |
| Genel doğruluk | %90.9 |

Karşılaştırma için yalnız-vektör hâli (`FRAG_HYBRID=0 FRAG_MIN_SIMILARITY=0.15
python eval/evaluate.py --backend hashing`): Recall@4 %72.0 / MRR 0.650 /
reddetme %87.5 / genel %75.8.

2. `src/foundry_rag/pipeline.py` içinde şu satırı bul:

```python
vectors = backend.embed([c.with_heading_prefix() for c in batch])
```

Geçici olarak şuna çevir:

```python
vectors = backend.embed([c.text for c in batch])   # A3.3 -- GECICI
```

3. **Yeniden indeksle** (embedding üretimi değişti, indeks geçersiz) ve tekrar ölç:

```bash
python -m app.cli --backend hashing ingest
python eval/evaluate.py --backend hashing
```

4. Değişikliği geri al ve testlerin hâlâ geçtiğini doğrula:

```bash
python -m pytest tests/ -q
python -m app.cli --backend hashing ingest
```

`tests/test_chunking.py::test_heading_prefix_included_for_embedding` bu davranışı
zaten test ediyor; geri almayı unutursan test kırmızı yanar.

5. Sonucu tabloya yaz:

| Yapılandırma | Recall@4 | MRR | Reddetme doğruluğu | Genel doğruluk |
| --- | --- | --- | --- | --- |
| Başlık öneki AÇIK (`with_heading_prefix()`) | %88.0 | 0.793 | %100.0 | %90.9 |
| Başlık öneki KAPALI (`c.text`) | ? | ? | ? | ? |

6. `eval/evaluate.py` çıktısındaki **BAŞARISIZ SORULAR** bölümünü iki koşu için
   karşılaştır. Hangi soru bir koşuda düzelip diğerinde bozuldu? En az bir soruyu
   seçip, o sorunun beklenen kaynağındaki bölüm başlığına bakarak neden böyle
   olduğunu açıkla.

> Not: Her `evaluate.py` koşusu sonucu `eval/results.jsonl` dosyasına ekler.
> İki koşunun `summary` alanlarını oradan da okuyabilirsin.

**Teslim:** doldurulmuş tablo + en az bir sorunun soru-bazlı açıklaması.

### A3.4 -- `min_similarity` eşiği ve reddetme takası

**Amaç:** "Recall" ile "bilmediğini söyleyebilme" arasındaki takası ölçmek.

Değerlendirme setinde 33 soru var: **25 cevaplanabilir** + **8 cevaplanamaz**
(`eval/questions.json` içinde `expected_source` alanı `null` olanlar: `u01`-`u08`).
`evaluate.py` bu iki grubu ayrı puanlar:

- `recall_at_k` yalnızca cevaplanabilir sorulardan hesaplanır
- `refusal_accuracy` yalnızca cevaplanamaz sorulardan hesaplanır
  (`--generate` olmadan: "hiç parça dönmediyse doğru reddetme" sayılır)

`min_similarity` yalnızca sorgu zamanını etkiler, dolayısıyla **yeniden indekslemene
gerek yok**. Bir kez indeksle, üç kez ölç:

```bash
python -m app.cli --backend hashing ingest        # bir kez

python eval/evaluate.py --backend hashing --min-similarity 0.0
python eval/evaluate.py --backend hashing --min-similarity 0.30
python eval/evaluate.py --backend hashing --min-similarity 0.5
```

Tabloyu doldur:

| `min_similarity` | Recall@4 | MRR | Reddetme doğruluğu | Genel doğruluk |
| --- | --- | --- | --- | --- |
| 0.0 | ? | ? | ? | ? |
| 0.30 (varsayılan) | %88.0 | 0.793 | %100.0 | %90.9 |
| 0.5 | ? | ? | ? | ? |

> Eşiği kendin taramak yerine `python eval/calibrate.py` de aynı ızgarayı
> otomatik gezer. Varsayılan `0.30` oradan çıkmıştır; bu alıştırma o sonucu
> elle yeniden üretmen içindir.

Sonra iki eğriyi tek grafikte çiz. Eksen: x = `min_similarity`, y = yüzde;
iki seri: Recall@4 ve reddetme doğruluğu. Matplotlib kurulu değilse tabloyu
ASCII bar olarak çizmen de yeterli.

Cevaplaman gereken sorular:

- Eşik 0.0 iken reddetme doğruluğu neden düşüyor? `retrieval.py` içindeki
  `hybrid_search()` fonksiyonunda hangi satır bunu belirliyor?
  (İpucu: `confidence = max(dense, saturate(lexical, lexical_scale))`)
- Eşik 0.5 iken Recall neden düşüyor? Kaybedilen sorular hangileri?
- `pipeline.py`'de `hits` boş dönerse ne oluyor? (`RagPipeline.answer()` içinde
  `NO_CONTEXT_ANSWER` dönen dalı bul.) Modelin hiç çağrılmaması neden önemli?
- Bu üç eşikten hangisini **bir hastane bilgi asistanı** için seçerdin? Hangisini
  **bir kod arama aracı** için? Gerekçelendir.

**Teslim:** doldurulmuş tablo + grafik (veya ASCII tablo) + dört sorunun cevabı.

### A3.5 -- Getirmeyi elle denetle

**Amaç:** Metriklere körü körüne güvenmemek. Recall@4 "doğru dosya top-4'te mi"
diye sorar; getirilen **parçanın** gerçekten soruyla ilgili olup olmadığını sormaz.

1. `ask` alt komutu kaynakları **varsayılan olarak gösterir** (`show_sources=True`).
   Bu alıştırmada `--no-sources` bayrağını **kullanma**.

```bash
python -m app.cli --backend hashing ask "RAG kısaltması hangi üç adımdan gelir?"
```

Çıktının sonundaki blok şuna benzer (`app/cli.py`, `_print_sources()`):

```
Kaynaklar:
  [1] 01-rag-nedir.md > <bölüm başlığı>
      guven 0.499 | anlam 0.159 | kelime 15.93 | bulan: ikisi
  ...
  getirme: 12 ms | uretim: 0.03 sn
```

`guven` cevap/reddetme kararında kullanılan skordur -- `anlam` (kosinüs) ile
doyurulmuş `kelime` (BM25) skorunun büyüğü. `bulan` sütunu parçayı hangi
aramanın getirdiğini söyler: `anlam`, `kelime` ya da `ikisi`.

2. `eval/questions.json` içinden **5 soru** seç. En az biri `u01`-`u08` arasından,
   yani cevaplanamaz bir soru olsun.
3. Her soru için dönen 4 parçanın **her birini** elle işaretle. Parçanın tam metnini
   görmek için `top_k=1` ile tek tek bakabilir ya da `python -m app.cli info` ile
   dosyayı bulup açabilirsin.

| Soru id | Sıra | Kaynak (`citation`) | `guven` | İlgili mi? (E/H) | Not |
| --- | --- | --- | --- | --- | --- |
| q01 | 1 | | | | |
| q01 | 2 | | | | |
| q01 | 3 | | | | |
| q01 | 4 | | | | |
| ... | | | | | |

4. Tablodan **Precision@4** hesapla: `ilgili işaretlenen parça sayısı / 20`.
5. Şu iki durumu ayrı ayrı ara ve birer örnek bul:
   - **Doğru dosya, yanlış parça:** `expected_source` top-4'te (yani Recall için
     "başarılı") ama getirilen parça soruyu cevaplamıyor.
   - **Yüksek skor, alakasız içerik:** `guven` 0.30'un üstünde ama içerik ilgisiz.
6. Bulduğun her örnek için tek cümlelik hipotez yaz: bu neden oldu? Parça çok mu
   kısa, başlık mı yanıltıcı, `HashingBackend` kelime örtüşmesine mi takıldı?

> `HashingBackend` semantik bir embedder **değildir**; kelime ve karakter n-gram
> örtüşmesine bakar. Bu yüzden eş anlamlıları ve yeniden ifade edilmiş soruları
> kaçırır. Hibrit getirme bu açığın bir kısmını BM25 ile kapatıyor (yalnız
> vektörde %72.0, hibritte %88.0), ama tavan hâlâ düşük -- taban çizgisinin
> burada kalması bilerek böyledir; `qwen3-embedding-0.6b` ile karşılaştırma
> yapabilmek için bir zemin lazım.

**Teslim:** 20 satırlık işaretleme tablosu + Precision@4 + iki örnek ve hipotezleri.

---

## 5. Haftanın çıktı kriteri

Aşağıdakilerin hepsi sağlanmalı:

- [ ] `data/rag.db` dolu. `python -m app.cli info` parça sayısı > 0, belge sayısı 8
      ve `embedding_signature` satırı boş değil.
- [ ] Kendi bilgi tabanın (`data/mydocs.db`) ayrıca indekslenmiş ve sorulara cevap veriyor.
- [ ] `python -m app.cli ask "..."` ilgili kaynakları benzerlik skorlarıyla listeliyor.
- [ ] `python -m pytest tests/ -q` -- 163 test geçiyor.
- [ ] `docs/hafta-3-sonuclarim.md` içinde A3.3 ve A3.4 tabloları dolu.
- [ ] `eval/results.jsonl` içinde bu haftadan en az **4 koşu** kaydı var
      (taban çizgisi + başlık öneki kapalı + üç eşik koşusundan kalanlar).
- [ ] `pipeline.py` üzerindeki geçici A3.3 değişikliği **geri alınmış**.

---

## 6. Sık yapılan hatalar

| Belirti | Sebep | Çözüm |
| --- | --- | --- |
| `Veritabani bos. Once belgeleri indeksle` | `ingest` hiç çalıştırılmadı ya da `FRAG_DB_PATH` başka dosyayı gösteriyor | `python -m app.cli ingest` |
| `Indeks farkli bir embedding modeliyle olusturulmus` | İndeks `hashing` ile kuruldu, sorgu `foundry` ile yapılıyor (veya tersi) | Aynı `--backend` ile yeniden indeksle |
| `Dimension mismatch: query has 512 dims but the index has 1024` | Aynı sebep, `cosine_similarity()` tarafından yakalandı | Yeniden indeksle |
| `Corrupt index: mixed embedding dimensions` | `--append` ile farklı backend'lerden parça karıştı | `python -m app.cli ingest` (reset ile) |
| `chunk_overlap (900) must be smaller than chunk_size (900)` | `--chunk-size` küçültülürken `--chunk-overlap` unutuldu | İkisini birlikte ver |
| A3.3 sonrası eval değişmedi | Kod değişti ama yeniden indekslenmedi | Embedding'i etkileyen her değişiklikten sonra `ingest` |
| `--chunk-size` bilinmeyen argüman hatası | Alt komuttan önce yazıldı | `ingest --chunk-size 400` sırasına dikkat |
| Foundry backend'de yavaşlık, `execution_provider` CPU görünüyor | Bilinen açık hata: microsoft/Foundry-Local **#858 / #895** -- GPU EP doğru kaydolsa bile bazen yalnızca CPU varyantları görünür | `load()` sonrası basılan model kimliğini ve EP'yi not et; bu hafta `--backend hashing` ile devam et |

---

## 7. Hafta 4'e hazırlık

Bu haftanın tabloları gelecek haftanın karşılaştırma zemini. Hafta 4'te aynı eval'i
gerçek embedding modeliyle (`qwen3-embedding-0.6b`, 1024 boyut, indirme ~520-541 MB)
çalıştırıp bu satırların yanına ikinci bir sütun ekleyeceğiz. O yüzden
`eval/results.jsonl` dosyasını silme.

Hafta 4'e gelmeden önce ilk model indirmesini başlat: ilk çalıştırmada sohbet ve
embedding modelleri birlikte yaklaşık 1.3 GB indirir. "Çevrimdışı" ifadesi
**ilk çalıştırmadan sonrası** için geçerlidir; katalog ve model dosyaları ilk
kullanımda ağdan çekilir.
