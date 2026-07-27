# Hafta 2 -- Embedding, Vektör Arama ve SQLite

**Faz 1: Temel Öğrenme**

Bu hafta RAG boru hattının "getirme" (retrieval) yarısını sökeceğiz. Dil modeline
hiç dokunmuyoruz. Haftanın sonunda şu beş sorunun cevabını kodun içinden
gösterebiliyor olman gerekiyor:

1. Bir metin nasıl sayı dizisine dönüşüyor?
2. İki sayı dizisinin "benzer" olduğuna nasıl karar veriliyor?
3. Bu diziler diske nasıl yazılıyor ve neden JSON değil de BLOB?
4. Vektör araması neyi kaçırır ve BM25 bunu neden yakalar?
5. İki farklı arama sonucu tek listede nasıl birleştirilir?

---

## Bu haftada dokunacağın dosyalar

| Dosya | Ne var içinde |
|---|---|
| `src/foundry_rag/retrieval.py` | `normalize()`, `cosine_similarity()`, `search()`, `reciprocal_rank_fusion()`, `hybrid_search()`, `SearchHit` |
| `src/foundry_rag/lexical.py` | `BM25Index`, `saturate()`, `DEFAULT_K1 = 1.5`, `DEFAULT_B = 0.75` |
| `src/foundry_rag/turkish.py` | `fold_case()`, `stem_word()`, `expand_tokens()`, `shares_root()` |
| `src/foundry_rag/store.py` | `SCHEMA`, `encode_vector()`, `decode_vector()`, `VectorStore` |
| `src/foundry_rag/backends/base.py` | `Backend` sözleşmesi: `embed()`, `embedding_dim`, `embedding_signature()` |
| `src/foundry_rag/backends/hashing.py` | `DIM = 512`, `tokenize()` -- çevrimdışı yedek embedder |
| `src/foundry_rag/config.py` | `Settings.top_k = 4`, `min_similarity = 0.30`, `hybrid = True`, `lexical_scale = 16.0` |
| `tests/test_retrieval.py` | 14 test |
| `tests/test_store.py` | 10 test |
| `tests/test_lexical_and_fusion.py` | 23 test (BM25, `saturate`, RRF, `hybrid_search`) |
| `data/docs/03-embedding-ve-vektor-arama.md` | Aynı konunun Türkçe ders notu (bilgi tabanında da var) |
| `data/docs/04-sqlite-ile-yerel-depolama.md` | SQLite ders notu |

Depoda toplam 163 test var (`python -m pytest tests/ -q`). Bu haftanın doğrudan
konusu olan üç dosya bunun 47'sini tutuyor.

## Ön koşullar

Alıştırmalara başlamadan önce bu üç komut hatasız çalışmalı:

```bash
cd ~/Desktop/foundry-local-rag
python --version          # 3.11 veya üstü olmalı (venv icinde)
python -m pytest tests/ -q
python -m app.cli info
```

`python --version` 3.9.6 diyorsa venv'i aktive etmemişsin demektir. Sistem
Python'u ile devam edersen bu haftanın alıştırmaları yine de çalışır (numpy ve
sqlite3 yeterli), ama Hafta 3'te Foundry Local SDK'sı kurulmayacak.

> **Tek satırlık `python -c` komutları için not:** paket `src/` altında ve
> `pip install -e .` yapmadıysan import başarısız olur. Bu dokümandaki tüm
> `python -c` komutları `PYTHONPATH=src` ön ekiyle yazıldı; repo kökünden
> çalıştır. `pytest` ve `python -m app.cli` bu ön eke ihtiyaç duymaz --
> ilki `pyproject.toml` içindeki `pythonpath = ["src"]` ayarını, ikincisi
> `app/_bootstrap.py`'yi kullanır.

---

## 1. Embedding nedir

Embedding, bir metni sabit uzunlukta bir gerçel sayı vektörüne çeviren
fonksiyondur. "Sabit uzunluk" kısmı önemli: 5 kelimelik bir cümle de, 800
karakterlik bir paragraf da aynı boyutta vektör üretir. Bu sayede hepsini tek bir
matriste toplayabiliyoruz.

Projedeki sözleşme `src/foundry_rag/backends/base.py` içinde:

```python
@abstractmethod
def embed(self, texts: Sequence[str]) -> list[list[float]]:
    """Return one embedding vector per input text, in the same order."""
```

İki farklı uygulaması var:

| Backend | `name` | Boyut | Nasıl çalışıyor |
|---|---|---|---|
| `HashingBackend` | `hashing-offline` | 512 (`hashing.py` içinde `DIM = 512`) | Kelime + kelime ikilisi + karakter 4-gram'larını blake2b ile 512 kovaya dağıtır |
| `FoundryBackend` | `foundry-local` | 1024 | `qwen3-embedding-0.6b` modelini yerelde çalıştırır |

`HashingBackend` **anlamsal değildir**. Ortak kelime ve karakter dizisi arar.
"otomobil" ile "araba" arasında hiçbir benzerlik göremez. Bu kasıtlı: testler
çevrimdışı, hızlı ve deterministik çalışsın diye var. Hafta 3'te gerçek modeli
takınca ölçtüğün skorların ne kadar arttığını göreceksin.

### Boyut asla sabit yazılmaz

`FoundryBackend.embedding_dim` (bkz. `backends/foundry.py`) boyutu tahmin etmiyor,
ölçüyor:

```python
@property
def embedding_dim(self) -> int:
    if self._dim is None:
        self._dim = len(self.embed(["boyut olcumu"])[0])
    return self._dim
```

Sebep: boyut modelin bir özelliği, senin kodunun değil. Modeli değiştirdiğinde
sabit yazılmış bir `1024` sessizce yanlış hale gelir.

### Neye embedding uygulanıyor

Ham parça metnine değil. `chunking.py` içindeki `Chunk.with_heading_prefix()`
başlığı metnin önüne ekliyor:

```python
def with_heading_prefix(self) -> str:
    if self.heading:
        return f"{self.heading}\n\n{self.text}"
    return self.text
```

`pipeline.ingest()` de embedding'i tam olarak bunun üzerinden alıyor
(`backend.embed([c.with_heading_prefix() for c in batch])`). Bir paragrafı
belgesinden koparınca hangi bölümden geldiği bilgisi kaybolur; başlığı eklemek
onu geri kazandırır.

---

## 2. Kosinüs benzerliği

İki vektörün benzerliğini ölçmenin en yaygın yolu aralarındaki açının kosinüsü:

```
                a · b            Σ aᵢbᵢ
cos(a, b) = ───────────── = ────────────────────
             ‖a‖ · ‖b‖      √(Σ aᵢ²) · √(Σ bᵢ²)
```

Sonuç `[-1, +1]` aralığındadır:

| Değer | Anlamı |
|---|---|
| `+1` | Aynı yön (aynı ya da ölçeklenmiş vektör) |
| `0` | Dik -- ortak hiçbir şey yok |
| `-1` | Tam zıt yön |

### Neden uzunluk değil de yön?

Vektörün uzunluğu (normu) metnin **ne kadar** olduğunu taşır: tekrar eden
kelimeler, uzun paragraflar normu büyütür. Yönü ise **ne hakkında** olduğunu
taşır. Uzun bir belge kısa bir soruyla sırf uzun olduğu için daha yüksek skor
almamalı. Kosinüs, normu bölerek uzunluk etkisini tamamen atar.

`tests/test_retrieval.py` bunu doğrudan test ediyor:

```python
def test_magnitude_does_not_change_cosine():
    matrix = np.array([[1.0, 1.0], [100.0, 100.0]], dtype=np.float32)
    scores = cosine_similarity([1.0, 1.0], matrix)
    assert scores[0] == pytest.approx(scores[1], abs=1e-6)
```

`[1, 1]` ile `[100, 100]` aynı yönü gösterir; ikisi de skor `1.0` alır.

### Normalize edince kosinüs, nokta çarpımına iner

Eğer `‖a‖ = ‖b‖ = 1` ise payda `1` olur ve formül `cos(a, b) = a · b` haline
gelir. `retrieval.py` tam olarak bunu yapıyor:

```python
def normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalise rows. Zero rows stay zero instead of becoming NaN."""
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms
```

```python
return (normalize(matrix) @ q.T).ravel()
```

Kazanç şu: `n` parça için `n` tane ayrı bölme yapmak yerine tek bir matris
çarpımı kalıyor. Bu, numpy'nin BLAS'a devrettiği tek bir çağrı.

`norms[norms == 0] = 1.0` satırına dikkat et. Sıfır vektörün normu sıfırdır;
sıfıra bölme `nan` üretir ve `nan` her karşılaştırmada `False` döner, yani
sıralama sessizce bozulur. Burada sıfır satır sıfır kalıyor, skoru da `0.0`
oluyor. Testi: `test_zero_vector_does_not_produce_nan`.

### Boyut uyuşmazlığı sessizce geçmez

```python
if q.shape[1] != matrix.shape[1]:
    raise ValueError(
        f"Dimension mismatch: query has {q.shape[1]} dims but the index has "
        f"{matrix.shape[1]}. ..."
    )
```

512 boyutlu bir soru vektörünü 1024 boyutlu bir indekste aramak anlamsızdır. Bu
kontrol olmasaydı numpy zaten hata verirdi, ama mesajı öğrenciye hiçbir şey
anlatmazdı.

---

## 3. Top-K seçimi ve benzerlik eşiği

`search()` iki parametre alıyor (`retrieval.py`):

```python
def search(store, query_vector, top_k: int = 4, min_similarity: float = 0.0) -> list[SearchHit]:
```

Uygulamada kullanılan gerçek değerler `config.py` içindeki `Settings`'ten gelir:

| Ayar | Varsayılan | Ortam değişkeni |
|---|---|---|
| `top_k` | `4` | `FRAG_TOP_K` |
| `min_similarity` | `0.30` | `FRAG_MIN_SIMILARITY` |
| `hybrid` | `True` | `FRAG_HYBRID` |
| `lexical_scale` | `16.0` | `FRAG_LEXICAL_SCALE` |

`min_similarity` tahmin edilmiş bir sayı değildir: `python eval/calibrate.py`
33 soruluk değerlendirme setinde `min_similarity` × `lexical_scale` ızgarasını
(11 × 6 = 66 nokta) tarar ve dengeli skoru en yüksek noktayı seçer. `0.30`
o taramanın argmax'ıdır. Önceki değer `0.15`'ti ve tahmindi.

> **Eşik modele bağlıdır.** Aynı kalibrasyon `foundry` backend'iyle (yani
> `qwen3-embedding-0.6b` ile) çalıştırıldığında `0.40` çıkıyor. Koddaki
> varsayılan `0.30`, çünkü testler ve CI çevrimdışı `hashing` backend'ini
> kullanır. Hafta 3'te Foundry Local'a geçince `FRAG_MIN_SIMILARITY=0.40`
> yapman gerekecek.

Bölüm 1-3 yalnız vektör tarafını anlatıyor (`search()`). Uygulamanın varsayılan
yolu bölüm 4-5'te göreceğin `hybrid_search()`'tür; eşik o yol için kalibre
edilmiştir.

### Top-K

```python
k = min(top_k, len(records))
top_idx = np.argsort(scores)[-k:][::-1]
```

`np.argsort` artan sıralar; son `k` elemanı almak en yüksek `k` skoru verir,
`[::-1]` de azalan sıraya çevirir. `min(top_k, len(records))` sayesinde `top_k`
korpustan büyük olduğunda hata çıkmaz -- `test_top_k_larger_than_corpus` bunu
kontrol ediyor.

`top_k` neden 4? Fazla parça = daha uzun prompt = daha yavaş üretim ve modelin
dikkatinin dağılması. Az parça = doğru cevap bağlamda hiç olmayabilir. 4, bu
projede ölçülmüş bir uzlaşma noktası.

### Eşik: "bilmiyorum" diyebilmenin tek mekanizması

```python
return [
    SearchHit(record=records[i], score=float(scores[i]))
    for i in top_idx
    if scores[i] >= min_similarity
]
```

Eşik olmasaydı, cevabı korpusta olmayan bir soru bile "en az kötü" 4 parçayı geri
getirirdi ve model bunlardan uydurma bir cevap üretirdi. `pipeline.py` bu durumu
şöyle yakalıyor:

```python
hits, retrieval_seconds = self.retrieve(question)
if not hits:
    return Answer(..., text=NO_CONTEXT_ANSWER, hits=[], grounded=False)
```

Hiç parça eşiği geçemediyse dil modeli **hiç çağrılmıyor**.

### Ölçülmüş taban çizgisi

Önce yalnız vektör tarafının taban çizgisini al. BM25'i kapatıyoruz ve eski
tahmini eşiği kullanıyoruz:

```bash
FRAG_HYBRID=0 FRAG_MIN_SIMILARITY=0.15 python eval/evaluate.py --backend hashing
```

| Metrik | Yalnız vektör (`FRAG_HYBRID=0`, eşik `0.15`) | Deponun varsayılanı (hibrit, eşik `0.30`) |
|---|---|---|
| Recall@4 | %72.0 | %88.0 |
| MRR | 0.650 | 0.793 |
| Reddetme doğruluğu | %87.5 | %100.0 |
| Genel doğruluk | %75.8 | %90.9 |

Sağdaki sütunu üreten komut (varsayılanlar zaten hibrit + `0.30`):

```bash
python eval/evaluate.py --backend hashing
```

Soldaki sütun kasıtlı olarak vasat. Bölüm 4 ve 5, o sütunu sağdakine çeviren
iki mekanizmayı anlatıyor. Her iki çıktıyı da not al; Hafta 3'te gerçek
embedding modeliyle üçüncü bir sütun ekleyeceksin.

---

## 4. Kelime tabanlı arama: BM25

### Vektör aramasının kör noktası

Embedding modeli anlamı iyi yakalar, **nadir ve birebir** simgeleri kötü:
bir model adı, bir hata kodu, `1536` gibi bir sayı. Sebep basit -- embedding
tam da bu ayrıntıları bulanıklaştırarak "anlam" üretiyor. Kelime araması ise
tersi: `1536` ile `1536`'yı eşleştirmekte kusursuz, "araba fiyatları" ile
"otomobil ücretleri"ni eşleştirmekte çaresiz.

`src/foundry_rag/lexical.py` bu ikinci yarıyı ekliyor. Sınıf `BM25Index`.

### BM25 formülü, üç fikir

```
score(D, Q) = Σ  idf(q) · ( f(q,D) · (k1 + 1) )
              q  ───────────────────────────────────────
                 f(q,D) + k1 · (1 − b + b · |D| / avgdl)
```

Formülü ezberleme, üç fikri anla:

**1. `f(q,D)` -- terim frekansı, ama doyumlu.** Bir kelime belgede ne kadar
çok geçerse belge o kadar iyi eşleşir. Ama 10. geçiş 2. geçiş kadar bilgi
katmaz. `k1` bu doyumu ayarlar: payda `f(q,D)`'yi de içerdiği için oran
büyüdükçe artış yavaşlar. Düz terim frekansında böyle bir tavan yoktur ve
tekrar eden belgeler haksız yere kazanır.

```python
DEFAULT_K1 = 1.5    # lexical.py
```

**2. `idf(q)` -- az belgede geçen terim daha bilgilendiricidir.** "ve" her
belgede vardır ve hiçbir şey söylemez; "1536" tek belgededir ve her şeyi
söyler. Kodda:

```python
self.idf[term] = math.log(
    1.0 + (count - document_frequency + 0.5) / (document_frequency + 0.5)
)
```

Baştaki `1.0 +` süs değil. O olmasaydı korpusun yarısından fazlasında geçen
bir terim **negatif** ağırlık alırdı, yani o terimi içeren belgeleri aşağı
iterdi. Testi: `test_scores_are_non_negative`.

**3. `|D| / avgdl` -- uzunluk normalizasyonu.** Uzun belgeler kazayla daha çok
terim eşleştirir. `b` bunu cezalandırır:

```python
DEFAULT_B = 0.75    # 0 = uzunlugu yoksay, 1 = tam normalizasyon
```

Testi: `test_longer_document_is_length_normalised` -- aynı eşleşmeye sahip bir
belgeye dolgu metni eklenince skoru **düşüyor**.

### Türkçe: `expand_tokens()`

BM25'in tokenleri `foundry_rag.turkish.expand_tokens()`'dan gelir, `str.split()`
veya `.lower()` değil. İki sebep:

```python
fold_case("IST")   # 'ıst'   -- Turkce'de dogrusu
"IST".lower()      # 'ist'   -- Python'un varsayilani, yanlis
```

Python'un `.lower()`'i `I` -> `i` yapar. Türkçede `I` -> `ı`, `İ` -> `i`'dir.
Bu hata, içinde I geçen her kelimede eşleşmeyi sessizce bozar.

İkincisi, Türkçe eklemeli bir dil: `vektör`, `vektörler`, `vektörlerin`,
`vektörlere`. Ham token karşılaştıran bir eşleştirici bunları dört ayrı kelime
sayar. `expand_tokens()` her kelimeyi **hem yüzey biçimi hem gövde** olarak
indeksler:

```python
expand_tokens("vektörlerin")   # ['vektörlerin', 'vektör']
expand_tokens("vektör")        # ['vektör']
expand_tokens("belgeler")      # ['belgeler', 'belge']
expand_tokens("belge")         # ['belge', 'belg']
```

Son iki satır neden ikisini birden indekslediğimizi gösteriyor: kural tabanlı
bir gövdeleyici son ünlünün ek mi kök mü olduğunu bilemez. `belge` gövdelenince
`belg` olur, `belgeler` gövdelenince `belge`. Tek başına gövde kullansaydık bu
ikisi asla buluşmazdı. İkisini birden indeksleyince ortak eleman `belge` çıkıyor.
Gövde bir **recall arttırıcı**, doğruluk kaynağı değil.

### `saturate()` -- iki farklı ölçeği aynı eşikle karşılaştırmak

Burada somut bir problem var. Kosinüs benzerliği `[-1, +1]` aralığındadır. BM25
skorunun **üst sınırı yoktur** ve aralığı korpusla birlikte kayar. `0.30` eşiği
kosinüs için anlamlıdır, BM25 için hiçbir şey ifade etmez.

Çözüm `lexical.py` içinde:

```python
def saturate(score: float, scale: float = 4.0) -> float:
    if score <= 0:
        return 0.0
    return float(score / (score + scale))
```

`x / (x + s)` fonksiyonunun üç özelliği:

| Özellik | Sonuç |
|---|---|
| Monoton artan | Sıralamayı bozmaz |
| `saturate(0) = 0` | Eşleşme yoksa güven yok |
| `saturate(s, s) = 0.5` | `scale` = "yarı güven" noktası |

Yani `lexical_scale = 16.0` şu demek: ham BM25 skoru 16 olan bir parça 0.5
güven alır. Tek ve yorumlanabilir bir düğme; korpus başına sihirli sabit değil.
Testi: `test_saturate_reaches_half_at_the_scale`.

### `BM25Index` arayüzü

```python
BM25Index(documents, k1=1.5, b=0.75)

index.postings          # terim -> {belge indeksi: frekans}
index.idf               # terim -> agirlik
index.doc_lengths       # np.ndarray
index.average_length    # float
index.vocabulary_size   # int

index.score_all(query)          -> np.ndarray  (her belge icin skor)
index.search(query, top_k=10)   -> [(indeks, skor), ...]
```

`RagPipeline` bunu açılışta **bir kez** kuruyor (`pipeline.py`):

```python
self.matrix, self.records = self.store.load_matrix()
self.bm25 = (
    BM25Index([f"{r.heading}\n{r.content}" for r in self.records])
    if self.settings.hybrid
    else None
)
```

Dikkat: BM25 indeksi de embedding gibi başlık + içerik üzerinden kuruluyor.

---

## 5. İki aramayı birleştirmek: RRF

Elimizde iki sıralama var: vektör aramasının sıralaması ve BM25'in sıralaması.
Bunları tek listeye indirmek gerekiyor.

### Neden skorları toplamayalım?

Akla ilk gelen `0.6 * kosinüs + 0.4 * bm25` gibi bir ağırlıklı toplam. Çalışmaz:

- Kosinüs `[-1, 1]`'de, BM25 sınırsız. Toplamda BM25 her zaman ezer.
- BM25'in aralığı korpus büyüklüğüne ve terim dağılımına bağlı. Bilgi tabanına
  üç belge eklediğinde ağırlıkların yeniden ayarlanması gerekir.
- Bu ayar sessizce bozulur -- kod çalışmaya devam eder, sadece sonuçlar kötüleşir.

**Sıralar kalibrasyona ihtiyaç duymaz.** "Bu retriever'ın 1. sırası" ifadesi
her retriever'da ve her korpusta aynı şeyi ifade eder. Reciprocal Rank Fusion
(RRF) tam olarak bunu kullanır.

### Formül

```
RRF(d) = Σ  1 / (k + rank_i(d))
         i
```

`i` = sıralamalar, `rank_i(d)` = `d` belgesinin `i`'inci sıralamadaki
1-tabanlı yeri. Belge bir sıralamada hiç yoksa o terim toplama girmez.

```python
# retrieval.py
RRF_K = 60   # Cormack ve ark. (2009)

def reciprocal_rank_fusion(rankings, k=RRF_K) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, start=1):
            fused[index] = fused.get(index, 0.0) + 1.0 / (k + rank)
    return fused
```

`k` ne işe yarar? Tepedeki farkları **düzleştirir**. `k = 0` olsaydı 1. sıra
`1.0`, 2. sıra `0.5` alırdı -- tek bir retriever'ın birinciliği her şeyi
belirlerdi. `k = 60` ile 1. sıra `1/61 = 0.01639`, 2. sıra `1/62 = 0.01613`;
aradaki fark %1.6. Böylece **iki retriever'ın da ilk beşine giren** bir belge,
**tek bir retriever'ın birincisini** geçebilir. Testi:
`test_smoothing_constant_flattens_top_ranks`.

### `hybrid_search()` ve kapı

```python
hybrid_search(
    records, matrix, query_vector,
    query_text="", bm25=None, top_k=4,
    min_similarity=0.15, rrf_k=RRF_K,
    lexical_scale=4.0, candidate_multiplier=5,
) -> list[SearchHit]
```

`RagPipeline.retrieve()` bunu `settings.top_k`, `settings.min_similarity` ve
`settings.lexical_scale` ile çağırır, yani pratikte `4`, `0.30`, `16.0`.

RRF sıralamayı belirler ama **kabul kararını** vermez. Onu şu satır verir:

```python
confidence = max(dense, saturate(lexical, lexical_scale))
if confidence < min_similarity:
    continue
```

Okunuşu: *iki retriever'dan biri emin ise parça kabul edilir.* Kesişim değil
birleşim. Kısa bir sorguda embedding sinyali zayıf olsa bile kelime eşleşmesi
tartışmasızsa parça kurtulur.

### `SearchHit` artık dört skor taşıyor

```python
@dataclass(frozen=True)
class SearchHit:
    record: ChunkRecord
    score: float            # guven = max(dense, saturate(lexical))
    dense_score: float = 0.0
    lexical_score: float = 0.0
    fused_score: float = 0.0
```

Ve `matched_by` property'si hangi retriever'ın bulduğunu söyler: `"ikisi"`,
`"kelime"` ya da `"anlam"`.

### Aynı soru, iki mod

CLI bunları doğrudan yazdırıyor. Önce hibrit (varsayılan):

```bash
python -m app.cli --backend hashing ask "Kosinüs benzerliği nedir?"
```

```
Kaynaklar:
  [1] 03-embedding-ve-vektor-arama.md > Kosinüs Benzerliği
      guven 0.446 | anlam 0.344 | kelime 12.89 | bulan: ikisi
  [2] 08-test-ve-degerlendirme.md > Birim Testleri
      guven 0.301 | anlam 0.073 | kelime 6.87 | bulan: ikisi
```

Şimdi BM25'i kapat:

```bash
FRAG_HYBRID=0 python -m app.cli --backend hashing ask "Kosinüs benzerliği nedir?"
```

```
Kaynaklar:
  [1] 03-embedding-ve-vektor-arama.md > Kosinüs Benzerliği
      guven 0.344 | anlam 0.344 | kelime 0.00 | bulan: anlam
```

İkinci parçayı incele. Vektör skoru `0.073` -- `0.30` eşiğinin çok altında,
yalnız vektör modunda hiçbir koşulda gelemezdi. Ama BM25 skoru `6.87` ve
`saturate(6.87, 16.0) = 6.87 / (6.87 + 16.0) = 0.3004`, eşiği kıl payı geçiyor.
Kelime kanıtı bir parçayı kurtardı. Deponun `%72 -> %88` recall sıçraması işte
bu mekanizmadan geliyor.

---

## 6. Neden SQLite

`store.py` dosyasının başındaki tasarım notları bu kararı zaten anlatıyor. Özet:

- **Tek dosya, sıfır kurulum.** `data/rag.db` kopyalanabilir, silinebilir,
  `.gitignore`'a eklenebilir. Ayrı bir sunucu süreci yok. Projenin "çevrimdışı
  çalışır" iddiası bir vektör veritabanı sunucusu gerektirseydi çökerdi.
- **Standart kütüphanede var.** `import sqlite3` -- ek bağımlılık yok.
- **İşlem (transaction) desteği.** `add_chunks()` tüm parçaları tek
  `executemany` + tek `commit` ile yazıyor; yarım kalmış bir indeksleme diske
  yarım veri bırakmıyor.

### sqlite-vec neden yok

sqlite-vec gibi vektör eklentileri `conn.enable_load_extension(True)` gerektirir.
macOS'un sistem Python'unda (3.9.6) bu metot **derlenmiş değildir**, çağırırsan
`AttributeError` alırsın. Kendin doğrula:

```bash
/usr/bin/python3 -c "import sqlite3; print(hasattr(sqlite3.connect(':memory:'), 'enable_load_extension'))"
```

Sorun değil, çünkü arama zaten numpy ile kaba kuvvet yapılıyor. `load_matrix()`
tüm vektörleri belleğe alıyor:

```python
def load_matrix(self) -> tuple[np.ndarray, list[ChunkRecord]]:
    """Loading everything into memory is deliberate: for a few thousand chunks
    this costs a few megabytes and turns retrieval into a single matrix
    multiply. Revisit only past ~100k chunks."""
```

Şu anki indeks 54 parça (`python -m app.cli info` ile gör). 1024 boyutta 54
vektör = 54 × 1024 × 4 bayt ≈ 221 KB. Bunun için ANN indeksi kurmak, LLM
çağrısının yanında ölçülemeyecek bir kazanç için karmaşıklık eklemek olurdu.

### Şema

`store.py` içindeki `SCHEMA` sabiti:

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

CREATE TABLE IF NOT EXISTS index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Üç tasarım kararı:

1. **`content_hash TEXT NOT NULL UNIQUE`** + `INSERT OR IGNORE` = yeniden
   indeksleme idempotent. Aynı parça iki kez eklenirse ikincisi sessizce
   düşer. Test: `test_duplicate_hash_is_ignored`.
2. **`dim INTEGER NOT NULL`** her satırda tekrar tutuluyor. Gereksiz görünüyor
   ama `load_matrix()` bunları kümeye atıp tek boyut olup olmadığını kontrol
   ediyor; karışıksa `ValueError: Corrupt index: mixed embedding dimensions`.
   Test: `test_mixed_dimensions_raise`.
3. **`index_meta`** basit bir anahtar-değer tablosu. Hangi model, hangi parça
   boyutu ile indekslendiğini tutar. A2.5'te ayrıntısına gireceğiz.

---

## 7. float32 BLOB, JSON değil

`store.py`:

```python
VECTOR_DTYPE = np.float32

def encode_vector(vector: Sequence[float]) -> bytes:
    return np.asarray(vector, dtype=VECTOR_DTYPE).tobytes()

def decode_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=VECTOR_DTYPE)
```

| | float32 BLOB | JSON metin |
|---|---|---|
| 1024 boyut için yer | 4096 bayt (boyut başına tam 4) | Sayı başına ~20 karakter, ~21 KB |
| Okuma | `np.frombuffer` -- kopya bile yok | `json.loads` + `np.asarray` |
| Hassasiyet | ~7 anlamlı ondalık basamak | Tam, ama işe yaramaz kadar fazla |
| Hata riski | Yazma/okuma dtype'ı aynı olmalı | Yok |

En büyük tuzak son satırda: `float32` yazıp `float64` okursan `numpy` hata
vermez, sana yarısı kadar uzunlukta ve tamamen anlamsız bir dizi verir. `store.py`
bunu tek bir `VECTOR_DTYPE` sabiti ile çözüyor -- iki fonksiyon da aynı sabiti
kullanıyor, ayrışamazlar.

`test_blob_size_is_four_bytes_per_dimension` bu sözleşmeyi kilitliyor:

```python
def test_blob_size_is_four_bytes_per_dimension():
    assert len(encode_vector([0.0] * 384)) == 384 * 4
```

---

# Alıştırmalar

Sıra önemli. A2.1 → A2.5 birbirinin üstüne biniyor; A2.6 → A2.8 bölüm 4 ve 5'i
elle doğrular ve birbirinden bağımsızdır.

## A2.1 -- Kosinüs benzerliğini elle hesapla

**Amaç:** Formülü kâğıtta uygulamadan koda güvenme.

`tests/conftest.py` içindeki örnek belgelerden üç cümle alıyoruz. Bunları iki
boyuta indirdiğimizi varsay: `x` ekseni "kedi/uyku", `y` ekseni "kahve/demleme".

| No | Cümle | Vektör |
|---|---|---|
| c1 | "Bir kedi günde ortalama on altı saat uyur." | `(3, 1)` |
| c2 | "Yavru kediler daha da fazla uyur." | `(4, 0)` |
| c3 | "Filtre kahve için önerilen su sıcaklığı doksan iki derecedir." | `(0, 2)` |

**Adım 1 -- kâğıtta.** Üç normu hesapla, sonra üç kosinüsü. Ara sonuçları yaz,
sadece nihai sayıyı değil.

```
‖c1‖ = √(3² + 1²) = √10 ≈ 3.16228
‖c2‖ = √(4² + 0²) = 4
‖c3‖ = √(0² + 2²) = 2

cos(c1, c2) = (3·4 + 1·0) / (√10 · 4)  = 12 / 12.64911 = ?
cos(c1, c3) = (3·0 + 1·2) / (√10 · 2)  = 2  /  6.32456 = ?
cos(c2, c3) = (4·0 + 0·2) / (4 · 2)    = 0  /  8       = ?
```

**Adım 2 -- kodla doğrula.** Repo kökünden:

```bash
PYTHONPATH=src python -c "
import numpy as np
from foundry_rag.retrieval import cosine_similarity
matrix = np.array([[3.0, 1.0], [4.0, 0.0], [0.0, 2.0]], dtype=np.float32)
print(np.round(cosine_similarity([3.0, 1.0], matrix), 5))
"
```

Beklenen çıktı:

```
[1.      0.94868 0.31623]
```

Sırasıyla `cos(c1,c1)`, `cos(c1,c2)`, `cos(c1,c3)`. Üçüncü sayı `1/√10`;
kâğıttaki sonucunla aynı olmalı.

**Adım 3 -- yorumla.** Şu soruları cevapla (yazılı, birer cümle):

- c2 vektörünü `(400, 0)` yaparsan `cos(c1, c2)` değişir mi? Neden?
- `cos(c2, c3) = 0` çıktı. Bu iki cümlenin "hiç ilgisi yok" demek mi, yoksa
  "seçtiğimiz 2 boyutta ortak bileşenleri yok" demek mi?
- `min_similarity = 0.30` eşiği bu üç skordan hangilerini elerdi?

**Kontrol:** Kâğıttaki üç sayı ile koddan çıkan üç sayı 5 ondalık basamağa kadar
tutuyor mu?

---

## A2.2 -- Testleri oku, çalıştır, iki test ekle

**Amaç:** Var olan testin ne iddia ettiğini okuyabilmek ve kendi kenar durumunu
yazabilmek.

**Adım 1 -- oku.** `tests/test_retrieval.py` dosyasını aç. 14 test var, iki gruba
ayrılmışlar: ilk 8'i saf matematik (`cosine_similarity`, `normalize`), son 6'sı
`search()` davranışı (`tmp_path` fixture'ı ile geçici bir `VectorStore` kurup).

**Adım 2 -- çalıştır.**

```bash
python -m pytest tests/test_retrieval.py -q
python -m pytest tests/test_retrieval.py -v      # her testin adini gor
```

**Adım 3 -- bozarak öğren.** `retrieval.py` içindeki `normalize()` fonksiyonunda
`norms[norms == 0] = 1.0` satırını yorum satırı yap ve testi tekrar çalıştır.
Hangi test kırıldı? Hata mesajını not al, sonra satırı geri koy.

**Adım 4 -- iki yeni test yaz.** `tests/test_retrieval.py` dosyasının sonuna
ekle.

*Test 1: çok küçük vektörler.* float32'nin en küçük normal sayısı yaklaşık
`1.18e-38`. Bileşenler `1e-25` civarındayken bileşenlerin kendisi temsil
edilebilir, ama **kareleri** (`1e-50`) taşma altına düşüp sıfıra yuvarlanır.
Sonuç: `np.linalg.norm` sıfır döner, `normalize()` içindeki koruma devreye girer,
ve vektör kendisiyle karşılaştırıldığında `1.0` yerine `0.0` skor alır. Bu bir
çökme değil, sessiz bir davranış -- testin işi onu belgelemek.

```python
def test_underflowing_vectors_score_zero_instead_of_nan():
    """Bilesenlerin karesi float32'de sifira dusunce norm 0 olur.

    normalize() sifir normu 1.0 ile degistirdigi icin nan cikmaz, ama
    benzerlik 1.0 yerine 0.0 olur. Cokme degil, sessiz davranis.
    """
    tiny = np.array([[1e-25, 1e-25]], dtype=np.float32)
    score = cosine_similarity([1e-25, 1e-25], tiny)[0]
    assert not np.isnan(score)
    assert score == pytest.approx(0.0, abs=1e-6)
```

Şunu da dene ve farkı gör: aynı testi `1e-20` ile yaz. Bu sefer skor `1.0`
civarında çıkar ama tam `1.0` değil -- normal altı (subnormal) sayılarda
hassasiyet eridiği için sonuç `1.0`'ın biraz altına da üstüne de düşebilir.
Eşik nerede? `1e-21`, `1e-22`, `1e-23` ile dene ve hangisinde davranışın
tamamen değiştiğini bul.

*Test 2: negatif skor.* Zıt yönlü bir vektör `-1.0` skor alır, ve
`min_similarity`'nin varsayılanı `0.0` olduğu için `search()` onu eler.

```python
def test_negative_scores_are_filtered_by_default_threshold(tmp_path):
    with VectorStore(tmp_path / "t.db") as store:
        store.add_chunks(
            [
                ("zit.md", 0, "", "tam zit yon", "h1", [-1.0, 0.0]),
                ("dik.md", 0, "", "dik yon", "h2", [0.0, 1.0]),
            ]
        )
        # varsayilan min_similarity=0.0 -> -1.0 skorlu parca elenir
        default_hits = search(store, [1.0, 0.0], top_k=2)
        assert [h.record.source for h in default_hits] == ["dik.md"]

        # esik -1.0'a cekilirse negatif skor da geri gelir
        all_hits = search(store, [1.0, 0.0], top_k=2, min_similarity=-1.0)
        assert [h.record.source for h in all_hits] == ["dik.md", "zit.md"]
        assert all_hits[1].score == pytest.approx(-1.0, abs=1e-6)
```

**Adım 5 -- çalıştır.**

```bash
python -m pytest tests/test_retrieval.py -q
```

**Kontrol:**

- [ ] `tests/test_retrieval.py` artık 16 test topluyor (`--collect-only` ile say)
- [ ] Adım 3'te hangi testin kırıldığını yazılı olarak not aldın
- [ ] `1e-20` ile `1e-25` arasındaki eşiği deneyerek buldun

---

## A2.3 -- SQLite kum havuzu

**Amaç:** Gerçek şemayı okumadan önce SQLite'ın temel işlemlerini kendi ellerinle
yapmak.

**Adım 1 -- sıfırdan bir tablo.** Bu komut geçici bir dosyaya yazıyor, projenin
`data/rag.db` dosyasına dokunmuyor:

```bash
python - <<'PY'
import sqlite3, tempfile, pathlib

db = pathlib.Path(tempfile.mkdtemp()) / "kum.db"
conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row

conn.executescript("""
CREATE TABLE IF NOT EXISTS notlar (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ders   TEXT NOT NULL,
    puan   INTEGER NOT NULL
);
""")

conn.executemany(
    "INSERT INTO notlar (ders, puan) VALUES (?, ?)",
    [("matematik", 85), ("fizik", 70), ("kimya", 92)],
)
conn.commit()

for row in conn.execute("SELECT id, ders, puan FROM notlar ORDER BY puan DESC"):
    print(row["id"], row["ders"], row["puan"])

print("toplam satir:", conn.execute("SELECT COUNT(*) AS n FROM notlar").fetchone()["n"])
print("dosya:", db)
conn.close()
PY
```

Dikkat edilecekler:

- `?` yer tutucuları. String birleştirme ile SQL yazma; SQL enjeksiyonu buradan
  başlar.
- `conn.commit()` olmadan hiçbir şey diske yazılmaz.
- `conn.row_factory = sqlite3.Row` satırı sonuçlara `row["ders"]` ile isimle
  erişmeyi açar. `VectorStore.__init__` de aynı satırı kullanıyor.

**Adım 2 -- gerçek şemayı gör.** Projenin veritabanını salt okunur incele:

```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("data/rag.db")
conn.row_factory = sqlite3.Row
for row in conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name"):
    print(f"--- {row['type']}: {row['name']}")
    print(row["sql"])
for row in conn.execute("SELECT id, source, chunk_index, heading, dim, LENGTH(embedding) AS blob_bytes FROM chunks LIMIT 5"):
    print(dict(row))
conn.close()
PY
```

**Adım 3 -- karşılaştır.** `src/foundry_rag/store.py` içindeki `SCHEMA` sabitini
aç ve kendi kum havuzu tablonla yan yana koy. Şu soruları yazılı cevapla:

| Soru | İpucu |
|---|---|
| `content_hash` neden `UNIQUE`? | `add_chunks()` içindeki `INSERT OR IGNORE`'a bak |
| `dim` sütunu neden her satırda tekrar ediyor? | `load_matrix()` içindeki `dims = {...}` kümesine bak |
| `idx_chunks_source` indeksi hangi sorguyu hızlandırır? | `sources()` metoduna bak |
| `index_meta` neden ayrı tablo, `chunks`'a sütun olarak eklenmemiş? | Kaç satır olurdu? |
| `LENGTH(embedding)` kaç çıktı? `dim` ile ilişkisi ne? | A2.4'ün konusu |

**Kontrol:**

- [ ] Kum havuzu betiği üç satır yazdırdı ve `SELECT` sıralaması `kimya, matematik, fizik` oldu
- [ ] `sqlite_master` çıktısında `chunks`, `index_meta` ve `idx_chunks_source` üçünü de gördün
- [ ] Tablodaki beş soruyu yazılı cevapladın

---

## A2.4 -- float32 gidiş-dönüş: hassasiyet nerede kırılıyor

**Amaç:** "float32 yeterli" iddiasını kendi ölçtüğün sayıyla desteklemek.

**Adım 1 -- ölç.**

```bash
PYTHONPATH=src python - <<'PY'
import numpy as np
from foundry_rag.store import encode_vector, decode_vector

rng = np.random.default_rng(0)
orijinal = rng.normal(size=1024).tolist()      # 1024 boyut, qwen3-embedding ile ayni
geri = decode_vector(encode_vector(orijinal))

print("blob boyutu :", len(encode_vector(orijinal)), "bayt")
print("dizi uzunlugu:", len(geri), "dtype:", geri.dtype)
print("en buyuk mutlak hata:", float(np.max(np.abs(np.array(orijinal) - geri))))

for atol in (1e-4, 1e-5, 1e-6, 1e-7, 1e-8):
    print(f"allclose(atol={atol:g}) ->", np.allclose(geri, orijinal, atol=atol, rtol=0))
PY
```

Bu makinede alınan çıktı:

```
blob boyutu : 4096 bayt
dizi uzunlugu: 1024 dtype: float32
en buyuk mutlak hata: 1.1836993829561493e-07
allclose(atol=0.0001) -> True
allclose(atol=1e-05) -> True
allclose(atol=1e-06) -> True
allclose(atol=1e-07) -> False
allclose(atol=1e-08) -> False
```

**Kırılma noktası `1e-6` ile `1e-7` arasında.** Bu tesadüf değil: float32'nin
mantisi 24 bit, dolayısıyla makine epsilonu `2⁻²³ ≈ 1.19e-7`. `-1..+1`
aralığındaki sayılarda beklenen en büyük hata tam olarak bu mertebede.

`test_store.py` içindeki testin neden `atol=1e-6` seçtiği de buradan anlaşılıyor:

```python
# float32 storage: exact equality is not guaranteed, 1e-6 is plenty
assert np.allclose(restored, original, atol=1e-6)
```

**Adım 2 -- hata mutlak değil, göreli.** Aynı vektörü büyüterek tekrarla:

```bash
PYTHONPATH=src python - <<'PY'
import numpy as np
from foundry_rag.store import encode_vector, decode_vector

rng = np.random.default_rng(0)
for olcek in (1, 1000, 1e6):
    o = rng.normal(size=1024) * olcek
    g = decode_vector(encode_vector(o.tolist()))
    print(f"olcek={olcek:>10} en buyuk mutlak hata = {float(np.max(np.abs(o - g))):.6e}")
PY
```

Bu makinede alınan çıktı:

```
olcek=         1 en buyuk mutlak hata = 1.183699e-07
olcek=      1000 en buyuk mutlak hata = 1.220204e-04
olcek=   1000000 en buyuk mutlak hata = 1.212174e-01
```

Ölçek 1000 katına çıkınca hata da 1000 katına çıkıyor. float32'nin garantisi
**mutlak** değil **göreli** hassasiyettir: yaklaşık 7 anlamlı ondalık basamak.

**Adım 3 -- neden bu bizi ilgilendirmiyor.** Embedding vektörleri normalize
edildikten sonra her bileşen `[-1, +1]` içinde. Kosinüs skorunda gördüğün
oynama `1e-7` mertebesinde, `min_similarity = 0.30` eşiği ise iki ondalık
basamakla çalışıyor. Aradaki mesafe beş büyüklük mertebesi.

**Adım 4 -- yanlış dtype tuzağını gör.** Bu, projedeki en sinsi hata sınıfı:

```bash
PYTHONPATH=src python - <<'PY'
import numpy as np
from foundry_rag.store import encode_vector

blob = encode_vector([1.0, 2.0, 3.0, 4.0])
print("dogru  (float32):", np.frombuffer(blob, dtype=np.float32))
print("yanlis (float64):", np.frombuffer(blob, dtype=np.float64))
PY
```

Hata yok, uyarı yok. Sadece yanlış uzunlukta ve anlamsız değerlerde bir dizi.
Projenin savunması `store.py` tepesindeki tek `VECTOR_DTYPE = np.float32`
sabiti -- `encode_vector` ve `decode_vector` ikisi de onu kullanıyor.

**Kontrol:**

- [ ] `1024 × 4 = 4096` bayt eşitliğini kendi çıktında gördün
- [ ] `allclose`'un `1e-6` ile `1e-7` arasında kırıldığını doğruladın
- [ ] Ölçek büyüdükçe mutlak hatanın orantılı büyüdüğünü gördün
- [ ] Yanlış dtype ile okumanın hata vermediğini gördün

---

## A2.5 -- `info` komutu ve `embedding_signature`

**Amaç:** İndeksin hangi vektör uzayına ait olduğunun neden kayıt altına
alındığını anlamak.

**Adım 1 -- çalıştır.**

```bash
python -m app.cli --backend hashing ingest
python -m app.cli info
```

`info` çıktısı (`app/cli.py` içindeki `cmd_info`):

```
Veritabani : /Users/.../foundry-local-rag/data/rag.db
Parca      : 54
Belge      : 8

Meta:
  embedding_signature    hashing-offline:512
  backend                hashing-offline
  chunk_size             900
  chunk_overlap          150
  document_count         8

Belgeler:
  - 01-rag-nedir.md
  ...
```

**Adım 2 -- imza nereden geliyor.** `backends/base.py`:

```python
def embedding_signature(self) -> str:
    """Identity of the vector space, stored alongside the index."""
    return f"{self.name}:{self.embedding_dim}"
```

`FoundryBackend` bunu ezip model adını da katıyor (`backends/foundry.py`):

```python
def embedding_signature(self) -> str:
    return f"{self.name}:{self.embedding_model_alias}:{self.embedding_dim}"
```

| Backend | İmza |
|---|---|
| `HashingBackend` | `hashing-offline:512` |
| `FoundryBackend` (`qwen3-embedding-0.6b`) | `foundry-local:qwen3-embedding-0.6b:1024` |

İndeksleme sırasında `pipeline.ingest()` bunu yazıyor:

```python
store.set_meta(META_SIGNATURE, backend.embedding_signature())
```

**Adım 3 -- ne işe yarıyor.** `RagPipeline._check_index()` her açılışta
karşılaştırıyor:

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

Bu kontrol olmasaydı iki senaryo vardı:

1. **Boyutlar farklı (512 vs 1024).** `cosine_similarity()` içindeki
   `Dimension mismatch` hatası yakalardı -- yani çökerdik ama en azından sesli.
2. **Boyutlar aynı, model farklı.** Hiçbir şey hata vermezdi. Skorlar hesaplanır,
   sıralama yapılır, cevap üretilir -- ve tamamı çöp olur. Sessiz yanlışlık,
   gürültülü çökmeden çok daha kötüdür. `embedding_signature` işte bu ikinci
   senaryoyu yakalamak için var.

**Adım 4 -- bozup gör.** İmzayı elle bozup davranışı kendin tetikle:

```bash
PYTHONPATH=src python -c "
from foundry_rag.store import VectorStore
with VectorStore('data/rag.db') as s:
    print('eski:', s.get_meta('embedding_signature'))
    s.set_meta('embedding_signature', 'sahte-model:9999')
"

python -m app.cli --backend hashing ask "RAG nedir?"
```

Beklenen: `[hata] Indeks farkli bir embedding modeliyle olusturulmus.` mesajı ve
çıkış kodu `1` (`main()` içindeki `except (RuntimeError, ValueError, ...)` dalı).

Düzelt:

```bash
python -m app.cli --backend hashing ingest
python -m app.cli --backend hashing ask "RAG nedir?"
```

**Adım 5 -- yaz.** Kendi cümlelerinle, en fazla beş cümlede:
`embedding_signature` ne saklıyor, kim yazıyor, kim okuyor, okuduğunda uyuşmazsa
ne oluyor, ve neden bu kontrol `dim` sütunu kontrolünden farklı bir işe yarıyor.

**Kontrol:**

- [ ] `info` çıktısında `embedding_signature` değerini `hashing-offline:512` olarak gördün
- [ ] İmzayı bozunca hata mesajını aldın
- [ ] Yeniden indeksleyip düzelttin
- [ ] Beş cümlelik açıklamayı yazdın

---

# Hafta sonu kontrol listesi

## Anlama

- [ ] Kosinüs benzerliği formülünü kâğıda bakmadan yazabiliyorum
- [ ] "Neden uzunluk değil yön?" sorusunu bir örnekle açıklayabiliyorum
- [ ] Normalize edilmiş vektörlerde kosinüsün neden nokta çarpımına indiğini gösterebiliyorum
- [ ] `top_k` ve `min_similarity`'nin farklı işler yaptığını, birinin diğerinin yerini tutmadığını anlatabiliyorum
- [ ] Eşik olmadan sistemin neden "bilmiyorum" diyemeyeceğini açıklayabiliyorum
- [ ] float32'nin göreli hassasiyetinin neden bu proje için yeterli olduğunu savunabiliyorum
- [ ] `embedding_signature` kontrolünün hangi sessiz hatayı yakaladığını anlatabiliyorum

## Yapma

- [ ] A2.1: Üç kosinüsü kâğıtta hesapladım, `cosine_similarity` ile 5 ondalık basamağa kadar tuttu
- [ ] A2.2: `tests/test_retrieval.py`'ı okudum, çalıştırdım, iki test ekledim, 16 test geçiyor
- [ ] A2.3: Kum havuzu tablosunu kurdum, `data/rag.db`'nin gerçek şemasını gördüm, beş soruyu cevapladım
- [ ] A2.4: `1e-6`/`1e-7` kırılma noktasını ölçtüm, ölçek etkisini gördüm, dtype tuzağını denedim
- [ ] A2.5: İmzayı bozdum, hatayı aldım, yeniden indeksledim

## Doğrulama komutları

```bash
python -m pytest tests/ -q                       # tumu gecmeli
python -m pytest tests/test_retrieval.py -q      # 16 test (2 tanesi senin)
python -m app.cli info                           # embedding_signature dolu olmali
python eval/evaluate.py --backend hashing        # taban cizgisini not al
```

## Teslim

Tek bir markdown dosyası (`hafta-2-teslim.md`):

1. A2.1'in kâğıt hesabı (ara adımlarla) ve kod çıktısı
2. A2.2'de yazdığın iki testin kodu + `1e-20`..`1e-25` arasında bulduğun kırılma eşiği
3. A2.3'teki beş sorunun cevabı
4. A2.4'ün iki çıktısı ve kırılma noktası yorumu
5. A2.5 Adım 5'teki beş cümle
6. `python eval/evaluate.py --backend hashing` çıktısı (Hafta 3'te karşılaştıracağız)

## Haftaya ne var

Hafta 3'te `HashingBackend`'i bırakıp Foundry Local SDK 1.x'i kuruyoruz:
Python 3.12 venv, `qwen3-embedding-0.6b` (1024 boyut) ve `qwen2.5-0.5b`
indirmesi, `scripts/doctor.py` ile ortam doğrulama. Bu haftaki yalnız-vektör
taban çizgisini (Recall@4 %72.0 / MRR 0.650) elinin altında tut -- ilk işimiz
onu yeniden ölçmek olacak.
