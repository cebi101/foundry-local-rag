# Sorun Giderme

Bu dosya, projede gercekten karsilasilan hatalari **belirti -> sebep -> cozum**
sirasiyla anlatir. Her maddenin basinda gordugun ekran ciktisi vardir; once o
ciktiyi bu sayfada ara, sonra oku.

**Altin kural:** hata alinca ilk komut her zaman sudur.

```bash
python scripts/doctor.py
```

`doctor.py` sirasiyla islemci mimarisini, Python surumunu, hangi SDK kusaginin
kurulu oldugunu, numpy/streamlit'i ve Foundry Local katalogunun model
alias'larini kontrol eder. Cikti satirlari uc isaretten biriyle baslar:

| Isaret | Anlami |
| --- | --- |
| `[ok]` | Sorun yok |
| `[!!]` | Uyari; proje calisir ama sinirli calisir |
| `[XX]` | Hata; duzeltmeden Foundry Local calismaz |

`[XX]` satirlarinin altindaki `->` satiri, calistiracagin komutu verir.
`doctor.py` bir veya daha fazla `[XX]` bulursa cikis kodu `1` doner.

## Hizli tablo

| Gordugun mesaj | Bolum |
| --- | --- |
| `cannot import name 'Configuration' from 'foundry_local_sdk'` | [1](#1-cannot-import-name-configuration-from-foundry_local_sdk) |
| `Foundry Local SDK 1.x requires Python >= 3.11` | [2](#2-foundry-local-sdk-1x-requires-python--311) |
| `No matching distribution found for foundry-local-sdk` | [3](#3-no-matching-distribution-found-for-foundry-local-sdk) |
| `IndexError: list index out of range` (streaming sirasinda) | [4](#4-indexerror-list-index-out-of-range--streaming-dongusunde) |
| Baslangicta `...-generic-cpu` yaziyor, cevaplar yavas | [5](#5-generic-cpu-varyanti-yukleniyor-model-yavas-calisiyor) |
| `Veritabani bos. Once belgeleri indeksle` | [6](#6-veritabani-bos-once-belgeleri-indeksle) |
| `Indeks farkli bir embedding modeliyle olusturulmus` | [7](#7-indeks-farkli-bir-embedding-modeliyle-olusturulmus) |
| `Model alias '...' is not in the catalog on this machine` | [8](#8-model-alias--is-not-in-the-catalog-on-this-machine) |
| Ilk calistirma dakikalarca suruyor | [9](#9-ilk-calistirma-cok-uzun-suruyor--internet-gerekiyor-mu) |
| `Foundry Local could not start: ...` (Streamlit'te) | [10](#10-foundry-local-could-not-start--streamlit-yeniden-yuklendiginde) |
| `zsh: killed` / sistem donuyor | [11](#11-zsh-killed-bellek-yetersiz) |
| `foundry model list` embedding modelini gostermiyor | [12](#12-brew-install-foundrylocal-eski-surum-kuruyor) |
| Turkce cevaplar kotu, kaynak vermiyor | [13](#13-turkce-cevap-kalitesi-dusuk) |
| `ModuleNotFoundError: No module named 'foundry_rag'` (pytest) | [14](#14-testler-gecmiyor) |
| `.NET number values such as positive and negative infinity cannot be written as valid JSON` | [15](#15-net-number-values-such-as-positive-and-negative-infinity-cannot-be-written-as-valid-json) |
| Cevap ayni kelimeyi tekrar edip duruyor, dakikalarca suruyor | [16](#16-cevap-ayni-kelimeyi-tekrar-edip-duruyor--tek-soru-dakikalarca-suruyor) |
| `Kaynaklilik: %0 (0/N cumle dayanakli)` | [17](#17-kaynaklilik-0-cikiyor) |
| `(Not: Üretilen cevap ... belgelerden doğrudan alıntı yapıldı.)` | [17](#17-kaynaklilik-0-cikiyor) |
| Sistem her seye cevap veriyor, "bilmiyorum" demiyor | [18](#18-reddetme-dogrulugu-cok-dusuk--sistem-her-seye-cevap-veriyor) |
| CI'da `Kalite kapisi BASARISIZ` | [19](#19-cida-kalite-kapisi-basarisiz) |
| Modeller gigabaytlarca yeniden iniyor | [20](#20-modeller-yeniden-iniyor) |

---

## 1. `cannot import name 'Configuration' from 'foundry_local_sdk'`

### Belirti

Kendi yazdigin bir betikte ya da bir notebook hucresinde:

```
ImportError: cannot import name 'Configuration' from 'foundry_local_sdk'
```

veya daha sik gorulen hali:

```
ModuleNotFoundError: No module named 'foundry_local_sdk'
```

Bu projenin icinden calistirdiginda ayni durum su mesaja donusur (kaynak:
`src/foundry_rag/backends/foundry.py`, `_import_sdk()`):

```
Found the LEGACY foundry-local-sdk 0.x (module 'foundry_local').
This project targets 1.x (module 'foundry_local_sdk').
Fix:  pip install --upgrade 'foundry-local-sdk>=1.2'
```

### Sebep

`foundry-local-sdk` adini paylasan **iki uyumsuz SDK kusagi** var:

| Surum | Import edilen modul | Python | Nasil calisir |
| --- | --- | --- | --- |
| 0.x (eski) | `foundry_local` | herhangi | HTTP istemcisi, `foundry` CLI gerekir |
| 1.x (guncel) | `foundry_local_sdk` | **>= 3.11** | surec icinde calisir, CLI gerekmez |

Python 3.10 ve altinda `pip install foundry-local-sdk` **hata vermez**. pip,
paketin `requires_python` alanina bakip sessizce eski **0.5.1** surumunu kurar.
Sonra `foundry_local_sdk` diye bir modul bulamazsin, cunku 0.5.1 `foundry_local`
kurar. API'ler tamamen farklidir.

Bu, projedeki 1 numarali tuzaktir.

### Cozum

Once hangi surumun kurulu oldugunu ogren:

```bash
pip show foundry-local-sdk | grep -i version
python -c "import sys; print(sys.version)"
```

Surum `0.` ile basliyorsa Python surumu de eskidir. Sirayla:

```bash
pip uninstall -y foundry-local-sdk
brew install python@3.12
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/doctor.py
```

`doctor.py` ciktisinda su satiri gormelisin:

```
  [ok]  foundry-local-sdk 1.2.x (modul: foundry_local_sdk)
```

Hala `[XX]` goruyorsan [2. bolume](#2-foundry-local-sdk-1x-requires-python--311)
gec.

### Kontrol listesi

- [ ] `pip show foundry-local-sdk` 1.x gosteriyor
- [ ] `python -c "import foundry_local_sdk"` hatasiz calisiyor
- [ ] `python -c "import foundry_local"` **hata veriyor** (eski paket temizlenmis)

---

## 2. `Foundry Local SDK 1.x requires Python >= 3.11`

### Belirti

`python scripts/doctor.py` ciktisinda:

```
--- Python ---
  [XX]  python: 3.9.6 (/usr/bin/python3) -- Foundry Local SDK 1.x >= 3.11 istiyor
         -> brew install python@3.12 && /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

`--backend foundry` ile calistirirsan CLI ayni sorunu su sekilde bildirir
(`app/cli.py` icindeki `main()`, cikis kodu **2**):

```
[backend hatasi] Foundry Local SDK 1.x requires Python >= 3.11, but this interpreter is 3.9.
macOS ships 3.9 as /usr/bin/python3 and pip will silently install the
incompatible 0.5.1 SDK instead of erroring.
Fix:  brew install python@3.12 && /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate
```

Varsayilan `--backend auto` ile ise hata degil, **uyari** alirsin ve proje
calismaya devam eder:

```
[!] Foundry Local kullanilamiyor, cevrimdisi yedek backend'e gecildi.
    Sebep: Foundry Local SDK 1.x requires Python >= 3.11, ...
    Ayrinti icin: python scripts/doctor.py
```

Bu uyariyi kacirirsan proje calisir ama gercek bir dil modeli **hic devreye
girmez**. Bunu nasil anlayacagini [13. bolumde](#13-turkce-cevap-kalitesi-dusuk)
anlatiyoruz.

### Sebep

macOS 14.6, `/usr/bin/python3` olarak **3.9.6** gonderir. Foundry Local SDK 1.x
en az 3.11 ister. Kontrol `src/foundry_rag/backends/foundry.py` icinde import'tan
once yapilir:

```python
if sys.version_info < (3, 11):
    raise BackendUnavailable(...)
```

Bu kontrol bilerek erken calisir: yoksa 3.9'da pip'in sessizce kurdugu 0.5.1
yuzunden cok daha kafa karistirici bir `ImportError` alirdin.

### Cozum

```bash
brew install python@3.12
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -V                      # Python 3.12.x yazmali
pip install -r requirements.txt
python scripts/doctor.py
```

**Neden 3.12, neden 3.13 degil:** numpy 2.5 artik 3.11'i desteklemiyor; 3.12 su
an hem SDK'nin hem numpy'nin sorunsuz calistigi surum.

Her yeni terminal penceresinde `source .venv/bin/activate` yapmayi unutma.
Unuttugunda sistem Python'una duser ve bu hatayi tekrar alirsin. Hangi
yorumlayicinin aktif oldugunu su komutla dogrula:

```bash
which python     # .../foundry-local-rag/.venv/bin/python olmali
```

### Yan not: sqlite uzantilari

Ayni bolumde su uyariyi gorebilirsin:

```
  [!!]  sqlite 3.x.y / uzanti yukleme: False
         -> sqlite-vec bu yorumlayicida kullanilamaz. Bu proje icin sorun degil:
            arama numpy ile kaba kuvvet yapiliyor.
```

Sistem Python'unda `sqlite3` baglantisinin `enable_load_extension` metodu yoktur,
yani `sqlite-vec` gibi uzantilar yuklenemez. Bu proje icin **sorun degil**:
`src/foundry_rag/retrieval.py` icindeki `cosine_similarity()` aramayi numpy ile
kaba kuvvet yapar. Birkac bin parcada bu tek bir matris carpimidir.

---

## 3. `No matching distribution found for foundry-local-sdk`

### Belirti

```
ERROR: Could not find a version that satisfies the requirement foundry-local-sdk (from versions: none)
ERROR: No matching distribution found for foundry-local-sdk
```

`doctor.py` ciktisinda ise:

```
--- Platform ---
  [!!]  islemci mimarisi: x86_64
         -> Foundry Local yalnizca macOS arm64 (Apple Silicon) icin wheel yayinliyor.
            Rosetta altinda calisan bir Python kullaniyorsan arm64 bir yorumlayiciya gec.
```

### Sebep

Iki ayri durum ayni mesaji uretir:

1. **Python 3.11+ ama x86_64.** macOS'ta Foundry Local yalnizca **arm64 (Apple
   Silicon)** icin wheel yayinlar. Intel Mac icin hicbir build yoktur. Rosetta
   altinda acilmis bir terminalde kurulan Python da kendini x86_64 olarak
   tanitir, dolayisiyla pip uygun wheel bulamaz.
2. **Python 3.10 veya altinda.** Bu durumda genelde bu mesaji almazsin; pip
   sessizce 0.5.1'e duser. Bkz. [1. bolum](#1-cannot-import-name-configuration-from-foundry_local_sdk).

### Cozum

Once mimariyi olc:

```bash
python -c "import platform; print(platform.machine())"   # arm64 olmali
arch                                                     # arm64 olmali
brew --prefix                                            # /opt/homebrew olmali
```

`brew --prefix` `/usr/local` donuyorsa Intel (Rosetta) Homebrew kullaniyorsun.
`/opt/homebrew` altindaki arm64 Homebrew ile yeniden kur:

```bash
/opt/homebrew/bin/brew install python@3.12
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Terminal.app veya iTerm'de "Rosetta kullanarak ac" secenegi isaretliyse
kapatip terminali yeniden baslat.

**Gercek bir Intel Mac kullaniyorsan** Foundry Local'i calistiramazsin. Yapacak
bir sey yok; projeyi cevrimdisi yedek backend ile calistir:

```bash
python -m app.cli --backend hashing ingest
python -m app.cli --backend hashing ask "RAG nedir?"
```

Boru hattinin tamami (parcalama, vektor deposu, getirme, prompt kurma,
degerlendirme) calisir; yalnizca dil modeli yerine alintilayan bir yedek devreye
girer.

### Minimum surum notu

Foundry Local'in `libonnxruntime.dylib` dosyasi minimum **macOS 14.0** ister.
macOS 14.6 bu siniri ancak geciyor. Daha eski bir macOS'ta calistiramazsin.

---

## 4. `IndexError: list index out of range` — streaming dongusunde

### Belirti

Cevap ekrana **tamamen yazildiktan sonra** program cokuyor:

```
Traceback (most recent call last):
  File "benim_denemem.py", line 21, in <module>
    print(chunk.choices[0].delta.content, end="")
IndexError: list index out of range
```

### Sebep

`complete_streaming_chat()` akisinin **son parcasi bos bir `choices` listesiyle**
gelebiliyor. Microsoft'un kendi RAG tutorial'indaki dongu bu listeye kontrolsuz
indeksliyor ve tam da cevabi yazdirdiktan sonra `IndexError` ile cokuyor.

> Ust kaynak hata kaydi: **microsoft/Foundry-Local #905** — 2026-07-25 itibariyle
> **acik**. macOS arm64 + WebGPU + SDK 1.2.3 uzerinde uretilebiliyor.

### Bu depoda durum

Bu depodaki kod korumali. `src/foundry_rag/backends/foundry.py`,
`FoundryBackend.stream_chat()`:

```python
for chunk in stream:
    if not getattr(chunk, "choices", None):
        continue
    delta = getattr(chunk.choices[0], "delta", None)
    content = getattr(delta, "content", None) if delta else None
    if content:
        yield content
```

Yani `python -m app.cli chat` bu hatayi vermez. Hatayi **kendi betigini yazan
ogrenci** alir.

### Cozum

Kendi kodunda ayni deseni kullan. Uc ayri koruma var, ucu de gerekli:

1. `if not getattr(chunk, "choices", None): continue` — bos son parca
2. `delta` yoksa atla — bazi parcalarda `delta` gelmeyebilir
3. `content` bos string ise yayma — aksi halde ciktida bosluklar birikir

Tutorial'dan kopyaladigin dongude sadece `chunk.choices[0].delta.content`
varsa, once bu korumalari ekle.

---

## 5. `...-generic-cpu` varyanti yukleniyor, model yavas calisiyor

### Belirti

Baslangicta yazdirilan satirda `gpu` yerine `cpu` goruyorsun:

```
  Downloading embedding model (qwen3-embedding-0.6b)...
  embedding: qwen3-embedding-0.6b-generic-cpu [CPU]
  chat: qwen2.5-0.5b-generic-cpu [CPU]
```

Hicbir hata mesaji yoktur. Sadece cevap uretimi beklediginden cok daha yavastir.

### Once ayirt et: embedding mi, sohbet mi

Iki satir ayni gorunur ama sebepleri farklidir.

| Satir | `-generic-cpu` ne demek |
| --- | --- |
| `embedding: ...` | **Kasitli.** macOS arm64'te `device="auto"` iken proje embedding icin CPU varyantini bilerek secer (`backends/foundry.py`, `_embedding_device_default()`). Sebep: `qwen3-embedding-0.6b`'nin `-generic-gpu` varyanti bu platformda vektore Inf/NaN yaziyor. Ayrintisi ve hatanin tam metni [15. bolumde](#15-net-number-values-such-as-positive-and-negative-infinity-cannot-be-written-as-valid-json). Zorlamak icin `FRAG_DEVICE=gpu`. |
| `chat: ...` | Muhtemelen asagidaki ust kaynak hatasi. Sohbet modelinin varyantini Foundry Local kendi secer, proje karismaz. |

Yani embedding satirinda CPU gormek **bir ariza degildir**. Asagisi sohbet
modeli icindir.

### Sebep

Foundry Local'da acik bir hata var: **execution provider dogru kaydolsa bile**
katalog bazen yalnizca CPU varyantlarini gosteriyor. Sessizce yavas build'i
calistirmis olursun.

> Ust kaynak hata kayitlari: **microsoft/Foundry-Local #858** ve **#895** —
> ikisi de acik.

macOS'ta hizlandirma **ONNX Runtime WebGPU** (Dawn -> Metal) uzerinden yapilir.
CoreML **degil**, Apple Neural Engine **degil**. Aksini soyleyen bloglar
yaniltiyor; ANE gormemen bir hata belirtisi degildir.

### Bu depoda durum

Depo bu durumu gorunur kilmak icin her model yuklemesinden sonra cozulen id'yi
ve calisma zamani bilgisini yazdirir (`foundry.py`, `describe_variant()`):

```python
model_id = getattr(model, "id", "?")
runtime = getattr(getattr(model, "info", None), "runtime", None)
provider = getattr(runtime, "execution_provider", None) if runtime else None
device = getattr(runtime, "device_type", None) if runtime else None
```

Bu satir yalnizca `verbose=True` iken basilir. `ingest` ve `chat` komutlari
zaten verbose calisir; `ask` icin `-v` bayragini eklemen gerekir:

```bash
python -m app.cli -v ask "RAG nedir?"
```

### Cozum

1. Execution provider kaydini yeniden tetikle. Bu cagri
   `FoundryBackend._ensure_manager()` icinde yapilir ve **hata verirse fatal
   degildir**; sessizce atlanir:

   ```
     (execution provider setup skipped: <sebep>)
   ```

   Bu satiri goruyorsan sebebi okuyup not al.

2. Sureci tamamen kapatip yeniden baslat. Katalog bilgisi surec icinde
   onbelleklenir.

3. Yeniden denemeden once agin acik oldugundan emin ol; katalog ilk cagrida
   agdan cekilir.

4. Duzelmiyorsa **bu bir ust kaynak hatasidir**. Proje CPU varyantiyla dogru
   calisir, sadece yavastir. Odev teslim ediyorsan hangi varyantin yuklendigini
   ciktida gosterip not dus.

### Ne zaman panige gerek yok

`qwen2.5-0.5b` gibi kucuk bir model CPU'da da makul hizda calisir. Yavaslik
asil `qwen3-4b` gibi buyuk modellerde can yakar.

---

## 6. `Veritabani bos. Once belgeleri indeksle`

### Belirti

```
[hata] Veritabani bos. Once belgeleri indeksle:
  python -m app.cli ingest
```

Cikis kodu **1**. Streamlit'te ayni durum su uyariya donusur ve sayfa durur:

```
İndeks boş. Soldaki Belgeleri yeniden indeksle düğmesine bas ya da
terminalde `python -m app.cli ingest` çalıştır.
```

### Sebep

`RagPipeline._check_index()` (`src/foundry_rag/pipeline.py`) acilista
`store.count() == 0` ise soru sormayi reddeder. Uc olasilik:

1. `ingest` hic calistirilmadi.
2. `ingest` calisti ama **baska bir veritabani dosyasina** yazdi. `FRAG_DB_PATH`
   ortam degiskeni iki komut arasinda farkliysa bu olur.
3. `ingest` bir hatayla yarida kaldi (ornegin embedding modeli indirilemedi).

Varsayilan veritabani yolu `src/foundry_rag/config.py` icinde **mutlak** olarak
hesaplanir (`PROJECT_ROOT / "data" / "rag.db"`), dolayisiyla "yanlis klasorden
calistirdim" bu hatanin sebebi **degildir**.

### Cozum

Once ne oldugunu gor:

```bash
python -m app.cli info
```

Ciktisi soyle olmali:

```
Veritabani : /Users/.../foundry-local-rag/data/rag.db
Parca      : 54
Belge      : 8
```

`Veritabani yok: ...` diyorsa dosya hic olusmamis. Ortam degiskenlerini kontrol
et:

```bash
env | grep FRAG_
```

Sonra indeksle:

```bash
python -m app.cli ingest
```

Foundry Local henuz hazir degilse yedek backend ile de indeksleyebilirsin:

```bash
python -m app.cli --backend hashing ingest
```

Ama bu indeksle sonradan `--backend foundry` ile soru soramazsin; bkz.
[7. bolum](#7-indeks-farkli-bir-embedding-modeliyle-olusturulmus).

### Ilgili hata: hic belge yok

`data/docs/` bos veya desteklenmeyen uzantilar iceriyorsa `ingest` sunu der:

```
[hata] /Users/.../data/docs icinde islenebilir belge yok (desteklenen uzantilar: .markdown, .md, .rst, .txt)
```

Desteklenen uzantilar `pipeline.py` icindeki `TEXT_SUFFIXES` kumesidir:
`.md`, `.markdown`, `.txt`, `.rst`. PDF ve DOCX desteklenmez.

Klasorun kendisi yoksa:

```
[hata] Belge klasoru bulunamadi: /Users/.../data/docs
FRAG_DOCS_DIR ile baska bir klasor gosterebilirsin.
```

---

## 7. `Indeks farkli bir embedding modeliyle olusturulmus`

### Belirti

```
[hata] Indeks farkli bir embedding modeliyle olusturulmus.
  indekste: hashing-offline:512
  simdiki : foundry-local:qwen3-embedding-0.6b:1024
Vektor uzaylari uyumsuz. Yeniden indeksle:
  python -m app.cli ingest
```

### Sebep

Indeks kurulurken hangi embedding modelinin kullanildigi `index_meta`
tablosunda `embedding_signature` anahtariyla saklanir. `RagPipeline._check_index()`
her aciliste bunu su anki backend'in imzasiyla karsilastirir.

Imzalar soyle uretilir:

| Backend | Imza formati | Ornek |
| --- | --- | --- |
| `FoundryBackend` | `foundry-local:<alias>:<dim>` | `foundry-local:qwen3-embedding-0.6b:1024` |
| `HashingBackend` | `<name>:<dim>` | `hashing-offline:512` |

Bu kontrol bilerek serttir. Iki farkli model **ayni boyutta** vektor uretse bile
vektor uzaylari uyumsuzdur: benzerlik skorlari anlamsiz cikar ama hicbir yerde
hata vermez. Sessiz sacmalik yerine yuksek sesle hata tercih edilmistir.

En sik senaryo: Foundry Local hazir degilken `auto` backend sessizce
`HashingBackend`'e dustu, indeks 512 boyutlu kuruldu; ertesi gun Foundry Local
calisti ve 1024 boyutlu sorgu geldi.

### Cozum

```bash
python -m app.cli info          # indekste hangi imza var, gor
python -m app.cli ingest        # ayni backend ile bastan kur
```

`ingest` varsayilan olarak indeksi **sifirlar** (`reset=not args.append`), yani
eski vektorler kalmaz.

Backend'i sabitlemek istersen:

```bash
python -m app.cli --backend foundry ingest
python -m app.cli --backend foundry ask "RAG nedir?"
```

`--backend foundry` sessiz duse gecmez; Foundry Local yoksa `[backend hatasi]`
verip cikis kodu 2 ile biter. Deneylerde bu daha guvenlidir.

### Iki akraba hata

**Boyut uyusmazligi** (`src/foundry_rag/retrieval.py`, `cosine_similarity()`):

```
Dimension mismatch: query has 1024 dims but the index has 512. The query and the
index must use the same embedding model -- re-run ingestion.
```

**Karisik boyutlu indeks** (`src/foundry_rag/store.py`, `load_matrix()`):

```
Corrupt index: mixed embedding dimensions [512, 1024]. Re-run ingestion to rebuild the database.
```

Ikincisi neredeyse her zaman `--append` yuzunden olur:

```bash
python -m app.cli --backend hashing ingest            # 512 boyut
python -m app.cli --backend foundry ingest --append   # 1024 boyut, eskiler duruyor
```

`--append` sifirlamayi atlar. Backend degistirirken **asla** `--append`
kullanma.

---

## 8. `Model alias '...' is not in the catalog on this machine`

### Belirti

```
[backend hatasi] Model alias 'phi-4-mini-instruct' is not in the catalog on this machine.
Aliases are hardware-dependent. Available here: qwen2.5-0.5b, qwen3-1.7b, qwen3-4b, qwen3-embedding-0.6b, ...
```

`doctor.py` ayni sorunu su sekilde gosterir:

```
--- Foundry Local katalogu ---
  [ok]  katalogda 27 model var
  [XX]  embedding modeli 'qwen3-embedding-0.6b': BULUNAMADI
         -> Bu donanimda mevcut ilk 15 alias: ...
```

### Sebep

Model alias'lari **donanima baglidir**. Katalog, calistigin makinede
desteklenmeyen modelleri hic listelemez. macOS arm64'te bilinen durumlar:

| Alias | macOS arm64 durumu |
| --- | --- |
| `qwen3-embedding-0.6b` | Var. `generic-cpu` ve `generic-gpu` varyantlari mevcut |
| `qwen2.5-0.5b` | Var |
| `qwen3-1.7b` | Var |
| `qwen3-4b` | Var |
| `Phi-4-mini-instruct-generic-cpu` | **Desteklenmiyor.** Microsoft'un kendi blocklist'inde |
| `deepseek-r1-1.5b` | **Mac varyanti yok** |

Ayrica `foundry` CLI'nin eski bir surumunu kurduysan katalog embedding
modellerini hic gostermez; bkz. [12. bolum](#12-brew-install-foundrylocal-eski-surum-kuruyor).

### Cozum

Once bu makinede gercekte ne varsa listele:

```bash
python scripts/doctor.py
```

Sonra `.env` dosyasinda (veya `export` ile) mevcut bir alias'a gec:

```bash
export FRAG_CHAT_MODEL=qwen2.5-0.5b
export FRAG_EMBEDDING_MODEL=qwen3-embedding-0.6b
```

Varsayilanlar zaten bunlardir (`src/foundry_rag/config.py`). Yani bu hatayi
aliyorsan ya bir ortam degiskenini elle degistirmissindir ya da katalog
cekilememistir (ag yok / CLI surumu eski).

Bir blogdan kopyaladigin alias calismiyorsa ilk varsayimin "bu alias bu
donanimda yok" olsun, "kurulum bozuk" olmasin.

### Lisans notu

Bu modellerin hicbirinde EULA / lisans onay kapisi yok. Hepsi MIT veya
Apache-2.0. "Lisansi kabul et" adimi arayip zaman kaybetme.

---

## 9. Ilk calistirma cok uzun suruyor / internet gerekiyor mu

### Belirti

`python -m app.cli ingest` dakikalarca su satirda takiliyor gorunuyor:

```
  Downloading embedding model (qwen3-embedding-0.6b)...
  embedding:  37.2%
```

### Sebep

Bu bir hata degil. Modeller ilk kullanimda agdan indirilir.

| Ne | Boyut |
| --- | --- |
| `qwen3-embedding-0.6b` | ~520-541 MB |
| `qwen2.5-0.5b` (gpu varyanti) | ~735 MB |
| `qwen2.5-0.5b` (cpu varyanti) | ~862 MB |
| Yerel calisma zamani kutuphaneleri | ~146 MB |
| **Ilk calistirma toplami** | **~1.3 GB + ~146 MB** |

"Tamamen cevrimdisi calisir" ifadesi **ilk calistirmadan sonra** gecerlidir.
Model katalogu ve model dosyalari ilk kullanimda agdan cekilir. Sinifta
demo yapacaksan indirmeyi onceden yap.

### Ne zaman ne iniyor

Modeller **tembel** yuklenir, bu yuzden indirmeler tek seferde olmaz:

| Komut | Inen model |
| --- | --- |
| `python -m app.cli ingest` | Yalnizca **embedding** modeli |
| `python -m app.cli ask` / `chat` (ilk soru) | Ek olarak **sohbet** modeli |
| `python -m app.cli info` | **Hicbiri** — sadece SQLite okur |

Sebep: `create_backend()` icinde `backend.embedding_dim` ozelligine bilerek
dokunulur, bu da embedding modelini hemen yukler; sohbet modeli ise ilk
`chat()` cagrisinda `_ensure_chat_client()` ile yuklenir. `ingest` hicbir zaman
`chat()` cagirmaz.

Yani ilk `ingest` bittikten sonra ilk soruda **ikinci bir indirme** basladiginda
sasirma.

### Cozum

1. Sabirla bekle ve yuzde gostergesini izle. Yuzde ilerliyorsa sorun yok.

2. **Mac'i uyutma.** Indirme sirasindaki uyku, dogrulanmamis/bozuk bir model
   onbellegi birakabiliyor ve onbellek butunluk dogrulamasi yapilmiyor.

   > Ust kaynak hata kayitlari: **microsoft/Foundry-Local #909** ve **#906** —
   > ikisi de acik.

   Uzun indirmeyi soyle koru:

   ```bash
   caffeinate -i python -m app.cli ingest
   ```

3. Onbellek bozulduysa is kotulesir: kod `if not getattr(model, "is_cached", False)`
   kontrolu yapar, yani **bozuk ama "mevcut" gorunen** bir onbellek yeniden
   indirilmez. Bu durumda temiz bir onbellek dizini ver:

   ```python
   from foundry_rag.backends.foundry import FoundryBackend
   backend = FoundryBackend(model_cache_dir="/Users/<sen>/foundry-cache-2")
   ```

   `FoundryBackend.__init__` bu parametreyi alir ve `Configuration`'a aktarir.

4. Once agin acik oldugunu dogrula. Ag yoksa `doctor.py` sunu der:

   ```
     [!!]  katalog bos dondu (ilk calistirmada internet gerekir)
   ```

---

## 10. `Foundry Local could not start: ...` (Streamlit yeniden yuklendiginde)

### Belirti

`streamlit run app/streamlit_app.py` ilk aciliste calisiyor; sayfayla
etkilesime girdiginde veya "Belgeleri yeniden indeksle" dugmesine bastiktan
sonra kirmizi kutuda:

```
Foundry Local could not start: <FoundryLocalException ...>
Check that the native core installed correctly:  pip install --force-reinstall 'foundry-local-sdk>=1.2'
```

Kendi kodunda ise dogrudan bir `FoundryLocalException` gorursun.

### Sebep

`FoundryLocalManager` **kati bir singleton**: ikinci `initialize()` cagrisi hata
verir. Streamlit ise her etkilesimde betigi bastan calistirir. Ayni tuzak
`uvicorn --reload` ve tekrar calistirilan notebook hucrelerinde de vardir.

### Bu depoda durum

Iki ayri koruma var.

**1. Streamlit tarafinda** (`app/streamlit_app.py`) boru hatti onbelleklenir:

```python
@st.cache_resource(show_spinner=False)
def load_pipeline(backend: str, top_k: int, min_similarity: float) -> RagPipeline:
    ...
```

**2. Backend tarafinda** (`foundry.py`, `_ensure_manager()`) initialize etmeden
once singleton kontrol edilir:

```python
if getattr(FoundryLocalManager, "instance", None) is None:
    FoundryLocalManager.initialize(Configuration(**kwargs))
self._manager = FoundryLocalManager.instance
```

Kendi kodunu yazarken **ikinci desen** hayat kurtarir. `initialize()`'i sarmadan
cagirma.

### Cozum

- Streamlit surecini tamamen kapat (`Ctrl-C`) ve yeniden baslat. Sicak yeniden
  yukleme, karisan surec durumunu duzeltmez.
- `@st.cache_resource` dekoratorunu kaldirma. Kaldirirsan her tiklamada yeni bir
  boru hatti kurulur.
- Notebook'ta `initialize()` iceren hucreyi ikinci kez calistirma; onun yerine
  cekirdegi yeniden baslat.
- Kendi FastAPI/uvicorn denemende `--reload` ile calisiyorsan yukaridaki
  `instance is None` kontrolunu ekle.

### Ilgili: yeniden indeksleme dugmesi

Kenar cubugundaki "Belgeleri yeniden indeksle" dugmesi `ingest(settings, verbose=False)`
cagirir. `ingest()` kendi backend'ini kurar (`pipeline.py`,
`backend or create_backend(settings, ...)`), yani ekranda zaten yuklu olan boru
hattina **ek olarak ikinci bir `FoundryBackend` nesnesi** olusur. Manager
singleton'i paylasilir, ama bellek baskisi hissediyorsan yeniden indeksleme
sonrasi Streamlit'i yeniden baslat.

---

## 11. `zsh: killed` (bellek yetersiz)

### Belirti

```
zsh: killed     python -m app.cli chat
```

veya macOS'un "Uygulama belleginiz tukendi" uyarisi, ya da uzun bir donmanin
ardindan surecin sessizce olmesi.

### Sebep

RAG boru hatti **iki modeli ayni anda** ayakta tutar: embedding modeli (her
soruda sorgu vektoru icin lazim) ve sohbet modeli. Diskteki buyuklukleri:

| Model | Boyut |
| --- | --- |
| `qwen3-embedding-0.6b` | ~520-541 MB |
| `qwen2.5-0.5b` | ~735 MB (gpu) / ~862 MB (cpu) |
| `qwen3-1.7b` | ~1490 MB |
| `qwen3-4b` | ~3083 MB |

Bu rakamlar disk boyutudur; yuklendiklerinde bellekte de yer kaplarlar. Kesin
RAM tuketimi calisan varyanta ve donanima gore degisir, ama buyuk modele
gecerken bu tabloyu goz onunde tut: `qwen3-4b` + embedding modeli, 8 GB'lik bir
makinede Streamlit ve tarayici da acikken rahat calismaz.

### Cozum

1. **Ayni anda tek bir sey calistir.** Streamlit acikken terminalde `chat`
   calistirma; ikisi ayri sureclerdir ve ikisi de modelleri yukler.

2. **Islerini ayir.** `ingest` yalnizca embedding modelini yukler:

   ```bash
   python -m app.cli ingest        # sadece embedding modeli
   python -m app.cli chat          # embedding + sohbet modeli
   ```

3. **Boru hattini kapat.** CLI zaten `with RagPipeline(...)` kullanir; cikista
   `close()` cagrilir ve o da her model icin `model.unload()` calistirir. Kendi
   betigini yazarken ayni deseni kullan:

   ```python
   with RagPipeline(settings) as rag:
       print(rag.answer("RAG nedir?").text)
   ```

4. **Model yuklemeyen komutlari tercih et.** `python -m app.cli info` yalnizca
   `VectorStore` acar, hicbir model yuklemez.

5. **Getirme tarafiyla ugrasiyorsan** dil modeline hic ihtiyacin yok:

   ```bash
   python eval/evaluate.py --backend hashing
   ```

6. **Buyuk modele gecmeden once** Aktivite Monitoru'nde bos bellegi kontrol et.
   `qwen3-4b` denemek istiyorsan once `qwen3-1.7b` ile dene.

---

## 12. `brew install foundrylocal` eski surum kuruyor

### Belirti

```bash
foundry model list
```

ciktisinda `qwen3-embedding-0.6b` **yok**. Surum kontrolu eski bir surum
gosteriyor:

```
0.8.119
```

### Sebep

`brew tap microsoft/foundrylocal` ile eklenen tap yaklasik **6 ay eski**. Kurdugu
surum **v0.8.119**, embedding destegi (`minFLVersion 1.1.0`) **oncesine** aittir.
Yani brew ile kurulan CLI `qwen3-embedding-0.6b`yi goremez.

Ayri bir tuzak: `brew install foundry` (sonunda `local` olmadan) **tamamen baska
bir yazilim** kurar — bir Ethereum gelistirme araci. Foundry Local ile ilgisi
yoktur.

### Cozum

**Bu proje icin CLI kurmana gerek yok.** SDK 1.x calisma zamanini kendi icinde
tasir; surec icinde calisir, ayri bir servis veya `foundry` komutu gerektirmez.
`requirements.txt` icindeki iki satir yeterlidir:

```
foundry-local-sdk>=1.2 ; python_version >= "3.11"
openai>=1.40 ; python_version >= "3.11"
```

Yanlislikla kurduysan kaldirabilirsin:

```bash
brew uninstall foundrylocal
brew untap microsoft/foundrylocal
```

CLI'ye baska bir ders/deneme icin gercekten ihtiyacin varsa Homebrew yerine
GitHub releases sayfasindan guncel `.pkg` dosyasini indir.

### Nasil dogrularsin

CLI olmadan calistigini gormek icin:

```bash
python scripts/doctor.py
```

`--- Foundry Local katalogu ---` bolumu `foundry` komutu PATH'te olmadan da
model listesini doldurabiliyorsa her sey yolundadir.

---

## 13. Turkce cevap kalitesi dusuk

### Belirti

Bir veya birkacini goruyorsun:

- Cevap belgelerdeki bilgiyi degil, modelin genel bilgisini kullaniyor
- Kaynak koseli parantezle belirtilmiyor (`[01-rag-nedir.md]` gibi)
- Cevap Ingilizce'ye kayiyor
- Dogru parca getirilmis olmasina ragmen model "Bu bilgi elimdeki belgelerde
  yok." diyor
- Cevap cumle ortasinda kesiliyor

### Once teshis: getirme mi, uretim mi

Bu ayrimi yapmadan model degistirme. `ask` komutu kaynaklari ve benzerlik
skorlarini yazdirir:

```bash
python -m app.cli ask "embedding nedir"
```

```
Kaynaklar:
  [1] 03-embedding-ve-vektor-arama.md > Tanım
      guven 0.612 | anlam 0.612 | kelime 8.44 | bulan: ikisi
  [2] 01-rag-nedir.md > Nasıl çalışır
      guven 0.401 | anlam 0.401 | kelime 0.00 | bulan: anlam

  getirme: 48 ms | uretim: 2.31 sn

Kaynaklilik: %100 (3/3 cumle dayanakli)  [mod: generative]
```

`guven` cevap/reddetme kararinda kullanilan skordur; `anlam` kosinus
benzerligi, `kelime` BM25 skoru, `bulan` ise parcayi hangi aramanin getirdigi.
Son satir `groundedness.py`'nin cumle bazli denetimidir.

Sondaki `[mod: ...]` cevabin **nasil uretildigini** soyler
(`pipeline.py`, `Answer.mode`). Uc deger alir:

| `mod` | Anlami |
| --- | --- |
| `generative` | Cevabi sohbet modeli yazdi, kaynaklilik denetimini gecti |
| `extractive` | `FRAG_ANSWER_MODE=extractive` acik; sohbet modeli hic cagrilmadi, cumleler belgelerden alintilandi |
| `extractive-fallback` | Sohbet modeli yazdi ama kaynaklilik `min_groundedness` esiginin altinda kaldi, cevap atildi ve yerine alinti kondu. Bkz. [17. bolum](#17-kaynaklilik-0-cikiyor) |

- **Dogru parca listede yok** -> getirme sorunu. `--top-k` degerini yukselt,
  `--min-similarity` degerini dusur, parca boyutunu degistir. Esigi elle
  tahmin etme, [18. bolume](#18-reddetme-dogrulugu-cok-dusuk--sistem-her-seye-cevap-veriyor)
  bak.
- **Dogru parca listede var ama cevap kotu** -> uretim sorunu. Sohbet modeli
  zayif. Cevap kendini tekrar ediyorsa
  [16. bolum](#16-cevap-ayni-kelimeyi-tekrar-edip-duruyor--tek-soru-dakikalarca-suruyor).
- **Cevap geldi ama `Kaynaklilik` dusuk** -> model getirilen parcalarin disina
  cikmis. `[!]` isaretli cumleleri oku; uydurma tam orada olur. Nasil
  yorumlanacagi [17. bolumde](#17-kaynaklilik-0-cikiyor).

### Sebep 1: aslinda dil modeli hic calismiyor

Cevabin sonunda su not varsa Foundry Local devrede degildir:

```
(Not: Foundry Local kurulu olmadığı için bu cevap bir dil modeli
tarafından yazılmadı; belgelerden doğrudan alıntılandı.)
```

Bu, `HashingBackend`'in cikti imzasidir. Cevaplar dogrudan alintidir, cunku
ortada dil modeli yoktur. Cozum icin [2. bolume](#2-foundry-local-sdk-1x-requires-python--311)
don.

Ayni durumu `info` ile de gorursun:

```bash
python -m app.cli info
```

```
  backend                hashing-offline
```

### Sebep 2: `qwen2.5-0.5b` bu is icin zayif

Varsayilan sohbet modeli `qwen2.5-0.5b`, kaynaga sadik (grounded) cevaplama icin
zayiftir. 0.5 milyar parametreli bir model, `src/foundry_rag/prompts.py`
icindeki bes kurala her zaman uymaz.

### Cozum

Daha buyuk bir sohbet modeline gec:

```bash
export FRAG_CHAT_MODEL=qwen3-1.7b        # ~1490 MB
# veya
export FRAG_CHAT_MODEL=qwen3-4b          # ~3083 MB
```

**Onemli:** sohbet modelini degistirince **yeniden indekslemeye gerek yok**.
Indeks imzasi yalnizca embedding modelini icerir
(`f"{self.name}:{self.embedding_model_alias}:{self.embedding_dim}"`), sohbet
modelini icermez. Model ilk soruda indirilir; [11. bolumdeki](#11-zsh-killed-bellek-yetersiz)
bellek uyarisini oku.

Diger ayarlar (`.env.example` icinde hepsi listeli):

| Degisken | Varsayilan | Ne zaman degistirilir |
| --- | --- | --- |
| `FRAG_TOP_K` | `4` | Dogru parca listeye girmiyorsa 6-8 dene |
| `FRAG_MIN_SIMILARITY` | `0.30` | Cok sik "belgelerde yok" diyorsa dusur; uydurma yapiyorsa yukselt. Tahmin etme: `python eval/calibrate.py` ile veriden sec. Foundry Local kullaniyorsan `0.40` |
| `FRAG_HYBRID` | `1` | `0` yaparsan BM25 kapanir, yalnizca vektor aramasi kalir |
| `FRAG_LEXICAL_SCALE` | `16.0` | BM25 skorunun 0.5 guvene karsilik geldigi nokta; `calibrate.py` bunu da tarar |
| `FRAG_CHECK_GROUNDEDNESS` | `1` | `0` yaparsan cumle bazli kaynaklilik denetimi kapanir |
| `FRAG_ANSWER_MODE` | `auto` | `generative` (her zaman model), `extractive` (modeli hic cagirma, alintila) veya `auto` (uret, dayanaksizsa alintiya dus) |
| `FRAG_MIN_GROUNDEDNESS` | `0.34` | `auto` modda alintiya dusme esigi. Uretilen cevabin kaynakliligi bunun altindaysa cevap atilir |
| `FRAG_MAX_TOKENS` | `600` | Cevap ortadan kesiliyorsa yukselt; model tekrar donguse giriyorsa dusur |
| `FRAG_TEMPERATURE` | `0.1` | Dusuk tutulmali; RAG'de yaratici cevap istemiyoruz |
| `FRAG_DEVICE` | `auto` | `cpu` veya `gpu`. macOS arm64'te embedding zaten CPU'ya sabitlenir; bkz. [15. bolum](#15-net-number-values-such-as-positive-and-negative-infinity-cannot-be-written-as-valid-json) |
| `FRAG_CHUNK_SIZE` | `900` | Parcalar konu butunlugunu bozuyorsa |
| `FRAG_CHUNK_OVERLAP` | `150` | Sinira denk gelen bilgi kaybediliyorsa |

`FRAG_CHUNK_SIZE` veya `FRAG_CHUNK_OVERLAP` degistirdiginde **yeniden indeksle**.

### Karsilastirma icin taban cizgisi

Degisiklikleri olcmek icin degerlendirme setini calistir:

```bash
python eval/evaluate.py --backend hashing
```

`eval/questions.json` icinde 33 soru vardir: 25 cevaplanabilir, 8 cevaplanamaz.
Cevaplanamayan sorular, sistemin "bilmiyorum" diyebilme yetenegini olcer.

`HashingBackend` ile olculmus taban cizgisi (`top_k=4`):

| Metrik | Yalniz vektor, eski tahmini esik `0.15` | Hibrit + kalibre `0.30` (bugunku varsayilan) |
| --- | --- | --- |
| Recall@4 | %72.0 | %88.0 |
| MRR | 0.650 | 0.793 |
| Reddetme dogrulugu | %87.5 | %100.0 |
| Genel dogruluk | %75.8 | %90.9 |

Soldaki sutun **tarihseldir**: `0.15` bir zamanlar varsayilandi ve tahmin
edilmisti. `FRAG_HYBRID=0 FRAG_MIN_SIMILARITY=0.15` ile tekrar uretebilirsin.
Sagdaki sutun deponun bugunku varsayilan yapilandirmasidir ve `0.30` degeri
`eval/calibrate.py`'nin argmax'idir.

Bu sayilar **kasitli olarak vasattir**. Gercek embedding modeliyle ne kadar
iyilestigini gormek icin referanstir. Ayni komutu Foundry Local ile calistirip
karsilastir:

```bash
python eval/evaluate.py --backend foundry
python eval/evaluate.py --backend foundry --generate    # cevaplari da uretir, yavas
```

`--generate` olmadan yalnizca getirme olculur (hizli).

Foundry Local (`qwen3-embedding-0.6b`, 1024 boyut) ile ayni set su sonuclari
verdi:

| Metrik | `min_similarity=0.30` | `min_similarity=0.40` (kalibre) |
| --- | --- | --- |
| Recall@4 | %100 | %96 |
| MRR | 0.973 | 0.960 |
| Reddetme dogrulugu | %62.5 | %100.0 |
| Genel dogruluk | %90.9 | %97.0 |

Ortalama getirme suresi 0.33 sn. Dikkat: **ayni esik iki backend'de ayni seyi
ifade etmiyor.** Sebebi ve cozumu
[18. bolumde](#18-reddetme-dogrulugu-cok-dusuk--sistem-her-seye-cevap-veriyor).

---

## 14. Testler gecmiyor

### Belirti 1

```
ModuleNotFoundError: No module named 'foundry_rag'
```

**Sebep:** pytest'i depo kokunden calistirmadin. `pyproject.toml` icindeki
ayarlar (`testpaths = ["tests"]`, `pythonpath = ["src"]`) yalnizca `pyproject.toml`
bulunabildiginde uygulanir.

**Cozum:**

```bash
cd /Users/<sen>/Desktop/foundry-local-rag
python -m pytest tests/ -q
```

### Belirti 2

```
ModuleNotFoundError: No module named 'numpy'
```

veya

```
zsh: command not found: pytest
```

**Sebep:** venv aktif degil, sistem Python'undasin.

**Cozum:**

```bash
source .venv/bin/activate
which python                    # .venv/bin/python olmali
pip install -r requirements.txt
python -m pytest tests/ -q
```

`pytest` yerine `python -m pytest` yazmayi aliskanlik haline getir; boylece
komutun hangi yorumlayiciyi kullandigi belirsiz kalmaz.

### Belirti 3: testler model indirmeye calisiyor

Testler asla model indirmemeli. Ag trafigi veya `Downloading ... model` satiri
goruyorsan bir sey yanlis.

**Sebep:** `tests/conftest.py` icindeki `settings` fixture'i `backend="hashing"`
ile kurulur. Testler **her zaman** `HashingBackend` kullanir: hizli, cevrimdisi
ve deterministik. Kendi ekledigin bir test `Settings.from_env()` cagiriyorsa
`FRAG_BACKEND` ortam degiskeni devreye girer.

**Cozum:** testlerde `Settings.from_env()` kullanma; `conftest.py` icindeki
`settings` fixture'ini iste.

### Beklenen cikti

Test paketinin tamami cevrimdisi calisir ve saniyeler icinde biter:

```bash
python -m pytest tests/ -q
```

```
... passed in 0.9s
```

Hangi dosyada kac test oldugunu gormek icin (sayilar depo buyudukce degisir,
o yuzden burada sabit yazilmiyor):

```bash
python -m pytest tests/ --collect-only -q
```

Belirli bir dosyayi calistirmak icin:

```bash
python -m pytest tests/test_chunking.py -q
python -m pytest tests/test_pipeline.py::test_signature_mismatch_is_detected -q
```

---

## 15. `.NET number values such as positive and negative infinity cannot be written as valid JSON`

### Belirti

`python -m app.cli ingest` sirasinda, embedding modeli yuklendikten hemen sonra:

```
System.ArgumentException: .NET number values such as positive and negative
infinity cannot be written as valid JSON.
```

Proje bu hatayi yakalarsa once su satiri gorursun:

```
  [!] GPU varyanti gecersiz sayi (Inf/NaN) uretti. CPU varyantina geciliyor.
      (Foundry Local'in WebGPU embedding varyantinda bilinen sorun;
       kalici olarak FRAG_DEVICE=cpu kullan.)
```

Yakalayamazsa CLI su bicimde bitirir (cikis kodu **2**):

```
[backend hatasi] Embedding generation failed: System.ArgumentException: .NET number
values such as positive and negative infinity cannot be written as valid JSON.
```

### Sebep

Hata mesaji **yanlis yeri gosteriyor**. Ortada bir JSON sorunu yok. Olan sudur:

1. Foundry Local `qwen3-embedding-0.6b` icin varsayilan olarak
   `qwen3-embedding-0.6b-generic-gpu:1` varyantini secer
   (`WebGpuExecutionProvider`).
2. Bu varyant macOS arm64'te vektorun icine `Inf` / `NaN` yaziyor.
3. SDK vektoru surec sinirindan gecirirken JSON'a yazmaya calisiyor. .NET'in
   `JsonSerializer`'i sonsuzlugu yazamaz ve `System.ArgumentException` firlatir.

Yani patlayan yer serilestirici, bozuk olan model varyanti. Ayni modelin
`-generic-cpu:1` varyanti sorunsuz calisir ve temiz 1024 boyutlu vektor doner.

Bu makinede canli dogrulandi (macOS 14.6 / Apple Silicon, SDK 1.2.3).

### Bu depoda durum

Uc ayri koruma var, hepsi `src/foundry_rag/backends/foundry.py` icinde.

| Fonksiyon | Ne yapar |
| --- | --- |
| `_embedding_device_default()` | macOS + arm64 ise `"cpu"` doner. `device="auto"` iken embedding modeli **dogrudan** CPU varyantiyla acilir; calismayacak bir varyant icin ~540 MB bosuna inmez |
| `_is_non_finite_failure(error)` | Hata metninde `infinity` ya da `cannot be written as valid json` geciyor mu diye bakar |
| `FoundryBackend.embed()` | Hata bu imzaya uyuyorsa `_switch_embedding_to_cpu()` ile **tek seferlik** CPU'ya gecip yeniden dener; olcum bosa gitmez |

Kod iyilesme olasiligini kapatmiyor: `FRAG_DEVICE=gpu` platform varsayilanini
gecersiz kilar. Microsoft varyanti duzelttiginde tek satir ayarla GPU'ya
donebilirsin.

### Cozum

Kalici cozum ortam degiskenidir:

```bash
export FRAG_DEVICE=cpu
python -m app.cli ingest
```

Dogru calistigini su satirdan anlarsin (`ingest` ve `chat` zaten verbose,
`ask` icin `-v` gerekir):

```
  embedding: qwen3-embedding-0.6b-generic-cpu [CPU / CPUExecutionProvider]
```

Hala `-generic-gpu` goruyorsan `FRAG_DEVICE` degeri okunmamis demektir;
`env | grep FRAG_DEVICE` ile dogrula.

**Onemli:** CPU'ya gecmek vektor uzayini degistirmez. Imza
(`foundry-local:qwen3-embedding-0.6b:1024`) ayni kaldigi icin yeniden
indekslemene gerek yoktur.

### Ilgili tuzak: saglayici adinin yazimi tutarsiz

Ayni model varyantini kod icinden secmeye kalkarsan ikinci bir tuzak var:

| Nerede | Nasil yaziyor |
| --- | --- |
| Uzak katalog API'si | `WebGPUExecutionProvider` |
| SDK'nin okudugu yerel onbellek | `WebGpuExecutionProvider` |

Tam eslesmeli bir string karsilastirmasi (`provider == "WebGPUExecutionProvider"`)
GPU varyantini **asla** bulamaz ve sessizce hicbir sey yapmaz. Depodaki
`_variant_provider()` bu yuzden kucuk harfe cevirip alt dize arar:

```python
runtime = getattr(getattr(variant, "info", None), "runtime", None)
return str(getattr(runtime, "execution_provider", "") or "").lower()
```

Kendi kodunda varyant secerken ayni yaklasimi kullan.

### Kontrol listesi

- [ ] `export FRAG_DEVICE=cpu` yapildi
- [ ] `python -m app.cli -v ask "RAG nedir?"` ciktisinda embedding satiri `-generic-cpu`
- [ ] `python -m app.cli info` icinde `embedding_signature` hala `...:1024`

---

## 16. Cevap ayni kelimeyi tekrar edip duruyor / tek soru dakikalarca suruyor

### Belirti

Cevap uretilmeye basliyor ama bitmiyor. Ekrana su tarzda bir sey akiyor:

```
Cevap: ... kendinden ve kendinden ve kendinden ve kendinden ve kendinden ...
```

Kaynak satirindaki sure sacma buyuklukte:

```
  getirme: 41 ms | uretim: 346.02 sn
```

Kaynaklilik denetleyicisi ayni anda alarm veriyor:

```
Kaynaklilik: %0 (0/15 cumle dayanakli) -- 15 cumle bağlamda doğrulanamadı
```

### Sebep

`qwen2.5-0.5b` **Turkce'de dejenere tekrar dongusune giriyor.** 0.5 milyar
parametreli bir modelin Turkce uretim kapasitesi yetersiz; ayni ifadeyi durma
kosulu olusana kadar tekrarliyor ve `max_tokens` sinirina kadar token uretiyor.

Bu makinede olculen degerler:

| Olcum | Deger |
| --- | --- |
| Tek sorunun uretim suresi | 346 sn |
| Dayanakli cumle orani | 0/15 |
| Getirme guveni (ayni soru) | 0.741, dogru parca 1. sirada |

**Kritik ayrim:** getirme mukemmeldi. Dogru parca birinci siradaydi ve guven
skoru yuksekti. Bozuk olan yalnizca uretim. Bu yuzden `--top-k`,
`--min-similarity` ya da parca boyutuyla oynamak bu sorunu **cozmez**.

Bu, [13. bolumdeki](#13-turkce-cevap-kalitesi-dusuk) "getirme mi, uretim mi"
ayriminin en net ornegidir.

### Cozum

Daha buyuk bir sohbet modeline gec:

```bash
export FRAG_CHAT_MODEL=qwen3-1.7b      # ~1490 MB
python -m app.cli ask "RAG nedir?"
```

Model ilk soruda indirilir. Yeniden indekslemeye **gerek yok**: indeks imzasi
(`f"{self.name}:{self.embedding_model_alias}:{self.embedding_dim}"`) yalnizca
embedding modelini icerir, sohbet modelini icermez.

Ikinci onlem, tekrar dongusunun maliyetini kesmektir:

```bash
export FRAG_MAX_TOKENS=250
```

`max_tokens` dongunun kendisini engellemez ama uretimi erken keser: 346 saniye
yerine saniyeler icinde bozuk ciktiyi gorup teshis koyarsin. Cevaplar duzeldikten
sonra varsayilan `600` degerine geri don, yoksa uzun cevaplar ortadan kesilir.

Bellek durumun elveriyorsa `qwen3-4b` (~3083 MB) daha da iyidir; once
[11. bolumdeki](#11-zsh-killed-bellek-yetersiz) bellek tablosunu oku.

### Neden bu hatayi yakalayabildik

Bunu fark ettiren sey kaynaklilik denetleyicisidir. `qwen2.5-0.5b` akici
cumleler uretiyordu; ekrana bakarak "kotu ama calisiyor" demek mumkundu.
`groundedness.check()` 15 cumlenin 15'ini **DAYANAKSIZ** isaretledi ve model
degistirme karari tahmine degil olcume dayandi.

```bash
export FRAG_CHECK_GROUNDEDNESS=1     # zaten varsayilan
```

---

## 17. `Kaynaklilik: %0` cikiyor

### Belirti

`python -m app.cli ask "..."` ciktisinin sonunda:

```
Kaynaklilik: %0 (0/6 cumle dayanakli) -- 6 cumle bağlamda doğrulanamadı
  [!] (0.12) RAG sistemleri 2019 yılında Facebook AI tarafından tanıtılmıştır ve...
  [!] (0.08) Bu yöntem genellikle 1536 boyutlu vektörlerle çalışır ve...
      ^ Bu cumleler getirilen belgelerde dogrulanamadi. Modelin kendi
        ezberinden eklemis olabilecegi kisimlar bunlar.
```

Streamlit'te ayni bilgi kirmizi bir kutu ve "Doğrulanamayan cümleler" acilir
panelidir.

### Bu sayi ne olcuyor

`src/foundry_rag/groundedness.py`, cevabin **her cumlesini** getirilen
parcalarla karsilastirir. Bir cumlenin skoru, o cumlenin icerik kelimelerinin
**agirlikli recall**'udur: "bu cumlenin iddia ettigi her sey pasajda var mi?"

Uc tasarim karari sonucu dogrudan etkiler:

| Karar | Sonucu |
| --- | --- |
| Simetrik ortusme degil, recall | Uzun pasaj cezalandirilmaz; onemli olan cumlenin fazla sey soyleyip soylemedigi |
| Nadir kelimeler IDF ile agir basar | "ve", "bir" paylasmak destek sayilmaz; `STOPWORDS` listesi bunlari tamamen atar |
| Hic gorulmemis terim **maksimum** agirlik alir | Uydurma tam da baglamda gecmeyen kelime getirir; en cok o cezalandirilir |

`split_sentences()` markdown isaretlerini ve `[kaynak]` etiketlerini atar, 25
karakterden kisa parcalari hic denetlemez (iddia tasimazlar). Esik
`SUPPORT_THRESHOLD = 0.45`: bunun altindaki cumle `DAYANAKSIZ` sayilir.

Olculen davranis: dogru cevapta **%100**, kasitli uydurma cevapta **%0**.

### Ne zaman ciddiye alinmali

| Durum | Yorum |
| --- | --- |
| Cevapta kaynakta hic gecmeyen **sayi, tarih, isim** var | **Gercek uydurma.** Cumleyi ve `Kaynaklar` bloguna bak, dogrula |
| Cevap kendini tekrar ediyor, %0 cikiyor | Model dejenere olmus. [16. bolum](#16-cevap-ayni-kelimeyi-tekrar-edip-duruyor--tek-soru-dakikalarca-suruyor) |
| Cevap dogru ama tamamen **kendi kelimeleriyle** yazilmis | Buyuk olasilikla **yanlis alarm.** Bu denetleyici kelime ortusmesine bakar, anlama bakmaz |
| Tek bir kisa cumle dusuk skorlu, gerisi yuksek | Genelde gecis cumlesi ("Ozetle bunlar onemlidir.") -- gormezden gelinebilir |

Denetleyici **NLI degildir.** Celiskiyi yakalayamaz ("X dogrudur" ile "X
yanlistir" ayni kelimeleri paylasir, ikisi de dayanakli gorunur) ve ortak
kelimesi olmayan es anlamli anlatimi kacirir. Karsiliginda ikinci bir model
indirmesi gerektirmez ve asil onemli hatayi yakalar: **modelin baglamda hic
gecmeyen bir seyi iddia etmesi.**

Skor bir **sinyaldir, hukum degil.** Dusuk skor "buna bak" demektir, "bu
yanlis" demez.

### Esigi nasil ayarlarsin

Esik icin ortam degiskeni **yoktur**. Iki yol var.

**1. Sabiti degistir.** `src/foundry_rag/groundedness.py`:

```python
#: below this, a sentence is reported as unsupported
SUPPORT_THRESHOLD = 0.45
```

- Yukselt (ornegin `0.60`): daha kati, daha cok yanlis alarm.
- Dusur (ornegin `0.30`): daha musamahali, gercek uydurmalari kacirabilir.

**2. Kendi kodunda parametre gecir.** Fonksiyon esigi argüman olarak alir:

```python
from foundry_rag import groundedness

report = groundedness.check(answer.text, answer.hits, threshold=0.60)
print(report.summary())
for verdict in report.unsupported:
    print(verdict.label, round(verdict.score, 2), verdict.text)
```

Denetimi tamamen kapatmak icin:

```bash
export FRAG_CHECK_GROUNDEDNESS=0
```

Kapatmak yalnizca olcum yaparken mantiklidir (uretim suresini bir miktar
kisaltir). Gunluk kullanimda acik birak: uydurma bir cumle, dayanakli bir
cumleyle **birebir ayni gorunur**, yanindaki kaynak etiketi onu daha da
guvenilir gosterir.

### Ilgili: hic cumle denetlenmiyor

```
Denetlenecek cumle yok.
```

Cevabin tamami 25 karakterden kisa parcalardan olusuyorsa bu cikar. Bir hata
degil; denetlenecek iddia yok demektir.

---

## 18. Reddetme dogrulugu cok dusuk / sistem her seye cevap veriyor

### Belirti

Bilgi tabaninda karsiligi olmayan bir soru soruyorsun, sistem yine de cevap
uretiyor:

```bash
python -m app.cli ask "Kuantum bilgisayarlar RAG'i nasil hizlandirir?"
```

```
Kaynaklar:
  [1] 03-embedding-ve-vektor-arama.md > Tanım
      guven 0.312 | anlam 0.312 | kelime 0.00 | bulan: anlam
```

Degerlendirme setinde ayni sorun sayiya donusur:

```
  Reddetme dogrulugu: 62.5%
```

Ters yonu de aynidir: sistem cevabini bildigi sorulara "Bu bilgi elimdeki
belgelerde yok." diyorsa esik bu sefer fazla yuksektir.

### Sebep

`min_similarity` esigi **modele bagli**, ve varsayilan deger senin backend'in
icin dogru olmayabilir.

Neden: `hybrid_search()` bir parcayi kabul ederken
`max(dense_score, saturate(lexical_score, lexical_scale))` degerini esikle
karsilastirir. Kosinus benzerliginin dagilimi her embedding modelinde farklidir.
Bu bilgi tabaninda olculen degerler:

| Backend | Kalibre esik | Recall@4 | Reddetme | Genel |
| --- | --- | --- | --- | --- |
| `hashing` (cevrimdisi yedek) | **0.30** | %88.0 | %100.0 | %90.9 |
| `foundry` (`qwen3-embedding-0.6b`) | **0.40** | %96 | %100.0 | %97.0 |

Ayni bilgi tabani, ayni sorular, **farkli optimum esik**. `foundry` backend'i
`0.30` ile calistirirsan recall %100'e cikar ama reddetme %62.5'e duser --
tam da bu bolumun belirtisi.

Koddaki varsayilan `0.30`'dur (`src/foundry_rag/config.py`), cunku testler ve CI
cevrimdisi backend kullanir. **Foundry Local kullaniyorsan degistirmen gerekir.**

### Cozum

Tahmin etme, olc:

```bash
python eval/calibrate.py --backend foundry
```

`calibrate.py` `min_similarity` x `lexical_scale` izgarasini tarar
(11 x 6 = 66 nokta) ve her nokta icin recall / reddetme / genel / dengeli
hesaplar. Sorular **bir kez** embed edilir ve izgara boyunca yeniden kullanilir,
bu yuzden tarama saniyeler surer.

Cikti soyle biter:

```
En iyi nokta (balanced metrigine gore):
  FRAG_MIN_SIMILARITY=0.4
  FRAG_LEXICAL_SCALE=16.0

  recall 96.0% | reddetme 100.0% | genel 97.0% | dengeli 98.0%
```

Onerilen degeri `.env` dosyasina yaz ya da export et:

```bash
export FRAG_MIN_SIMILARITY=0.40
export FRAG_LEXICAL_SCALE=16.0
python eval/evaluate.py --backend foundry     # dogrula
```

### Secim olcutu neden "dengeli"

Varsayilan hedef `balanced`, yani recall ile reddetmenin **harmonik**
ortalamasi. Aritmetik ortalama olsaydi, her soruyu cevaplayip hicbirini
reddetmeyen bir sistem %50 alirdi -- yani hicbir sey yapmayan bir sistem gecer
not alirdi. Harmonik ortalama, iki taraftan biri cokerse sifira gider.

Baska bir hedef istersen:

```bash
python eval/calibrate.py --objective overall     # genel dogruluk
python eval/calibrate.py --objective recall      # sadece recall (reddetmeyi umursama)
python eval/calibrate.py --no-lexical-sweep      # lexical_scale sabit, sadece esigi tara
```

`--objective recall` bilerek tek tarafli bir secimdir; reddetme yetenegini
onemsemedigin bir deney yapiyorsan kullan.

### Ne zaman yeniden kalibre etmelisin

- Embedding modelini degistirdiginde
- Backend degistirdiginde (`hashing` <-> `foundry`)
- `data/docs/` icerigini kayda deger olcude degistirdiginde
- `chunk_size` / `chunk_overlap` degistirdiginde

Bunlarin hepsi skor dagilimini kaydirir. Esik ayni kalirsa **ayni sayi artik
baska bir sey ifade eder.**

---

## 19. CI'da `Kalite kapisi BASARISIZ`

### Belirti

GitHub Actions'ta "Retrieval quality gate" adimi kirmiziya donuyor:

```
  KALITE KAPISI
==============================================================================
  [GECTI] Recall@K              88.0%  (esik: 84.0%)
  [KALDI] Reddetme dogrulugu    75.0%  (esik: 95.0%)
  [KALDI] Genel dogruluk        81.8%  (esik: 87.0%)
==============================================================================

Kalite kapisi BASARISIZ:
  - Reddetme dogrulugu: 75.0% < 95.0%
  - Genel dogruluk: 81.8% < 87.0%

Getirme kalitesi dustu. Ya degisikligi geri al, ya da
  python eval/calibrate.py
calistirip esikleri yeniden kalibre et ve dususun kasitli oldugunu dogrula.
```

Adim cikis kodu **1** dondurur ve build kirilir.

### Sebep

Bu bir kurulum hatasi **degil**. Getirme kalitesi gercekten dustu.

Testler bozuk kodu yakalar. Bir prompt duzenlemesinin, bir `chunk_size`
degisikliginin ya da bir esik oynamasinin sessizce on puan recall goturmesini
yakalayamaz -- bunu ancak bir degerlendirme seti gorur. `.github/workflows/ci.yml`
icindeki adim tam olarak sunu calistirir:

```bash
python eval/evaluate.py --backend hashing --no-save --gate
```

Esikler (`eval/evaluate.py`, `run_quality_gate()`) olculen degerlerin **biraz
altina** konmustur, boylece gurultu build'i kirmaz ama gercek dusus kirar:

| Kontrol | Bayrak | Esik | Depodaki olculen deger |
| --- | --- | --- | --- |
| Recall@K | `--min-recall` | 0.84 | %88.0 |
| Reddetme dogrulugu | `--min-refusal` | 0.95 | %100.0 |
| Genel dogruluk | `--min-overall` | 0.87 | %90.9 |

### Cozum

Once ayni komutu **yerelde** calistir; CI ile ayni cevrimdisi backend'i kullanir,
model indirmez ve saniyeler surer:

```bash
python eval/evaluate.py --backend hashing --no-save --gate
echo $?        # 0 = gecti, 1 = kaldi
```

Sonra iki yoldan birini sec.

**Yol 1 -- dusus istenmiyordu: degisikligi geri al.**

`BASARISIZ SORULAR` blogu hangi sorularin bozuldugunu ve ne getirildigini
gosterir. Son degisikligini geri alip komutu tekrar calistir:

```bash
git diff                       # ne degistirdin
git stash                      # gecici olarak kaldir
python eval/evaluate.py --backend hashing --no-save --gate
```

Kapi `git stash` sonrasi geciyorsa sucluyu buldun.

**Yol 2 -- dusus kasitliydi: yeniden kalibre et.**

Ornegin `chunk_size` degistirdiysen skor dagilimi da degismistir. Once
indeksi yeniden kur, sonra esikleri veriden sec:

```bash
python -m app.cli --backend hashing ingest
python eval/calibrate.py --backend hashing
```

Onerilen degerleri `src/foundry_rag/config.py` icindeki varsayilanlara yaz,
sonra kapiyi tekrar calistir. Yeni degerler kapiyi geciyorsa is bitti.

**Esikleri dusurmek** son caredir ve ayri bir karardir:

```bash
python eval/evaluate.py --backend hashing --no-save --gate --min-refusal 0.90
```

Bunu yapiyorsan commit mesajinda **neden** dusurdugunu yaz. Aksi halde kapi
zamanla anlamsizlasir: her kirildiginda esik biraz daha indirilirse kapi hicbir
seyi korumaz.

### Yapmaman gereken

- Adimi `|| true` ile susturma. Ayni dosyada `Environment doctor` adimi
  bilerek `|| true` ile calisir cunku o bilgi amaclidir; kalite kapisi degildir.
- Testleri gecti diye kapiyi gormezden gelme. Ikisi farkli seyleri olcer.
- Kapiyi `--backend foundry` ile calistirmaya calisma. CI cevrimdisidir ve
  `foundry-local-sdk` **bilerek** kurulmaz; gigabaytlarca model agirligi
  indirmemek icin.

---

## 20. Modeller yeniden iniyor

### Belirti

Daha once indirdigin modeller bastan iniyor:

```
  Downloading embedding model (qwen3-embedding-0.6b)...
  embedding:   4.1%
```

Disk doluyor; ev dizininde birden fazla model onbellegi goruyorsun:

```
~/.foundry_local_rag/
~/.foundry/
```

### Sebep

Foundry Local model onbellegini **`app_name`'e gore ayirir.** Her `app_name`
kendi onbellek dizinini kullanir. `app_name` degistirdiginde SDK eski dizini
bilmez ve tum modelleri sifirdan indirir.

Bu depodaki deger `src/foundry_rag/backends/foundry.py` icinde sabittir:

```python
app_name: str = "foundry_local_rag",
```

`create_backend()` bu parametreyi hic gecmez, yani proje icinden calistigin
surece deger **degismez** ve onbellek paylasilir. Modelleri yeniden indiriyorsan
sebebi neredeyse her zaman sudur: kendi betiginde `FoundryBackend`'i farkli bir
`app_name` ya da `model_cache_dir` ile kurdun, ya da bir blog ornegini
kopyalayip `app_name="foundry"` yazdin.

Ikinci olasilik: onbellek gercekten eksik. Kod
`if not getattr(model, "is_cached", False)` kontrolu yapar; onbellek dizini
silinmis ya da baska bir kullaniciya aitse model "yok" gorunur.

### Cozum

1. **`app_name`'i degistirme.** Kendi betiginde de varsayilani birak:

   ```python
   from foundry_rag.backends.foundry import FoundryBackend

   backend = FoundryBackend()          # app_name="foundry_local_rag"
   ```

2. Onbellegi bilerek baska yere almak istiyorsan `app_name` yerine
   `model_cache_dir` kullan; bu deger dogrudan `Configuration`'a gecer:

   ```python
   backend = FoundryBackend(model_cache_dir="/Volumes/Disk2/foundry-cache")
   ```

   Bu yolu **her calistirmada ayni** ver. Yolu degistirmek de yeniden indirme
   demektir.

3. Diskteki onbellekleri gorup gereksizleri sil:

   ```bash
   du -sh ~/.foundry_local_rag ~/.foundry 2>/dev/null
   ```

   Silmeden once hangisinin aktif oldugundan emin ol; yanlisini silersen
   ~1.3 GB'i tekrar indirirsin.

4. Indirme sirasinda **Mac'i uyutma.** Yarim kalan indirme dogrulanmamis bir
   onbellek birakabiliyor ve butunluk dogrulamasi yapilmiyor. Ayrintisi ve
   `caffeinate` kullanimi [9. bolumde](#9-ilk-calistirma-cok-uzun-suruyor--internet-gerekiyor-mu).

### Kontrol listesi

- [ ] Kendi kodumda `app_name` parametresini gecmiyorum
- [ ] `model_cache_dir` veriyorsam her calistirmada ayni yolu veriyorum
- [ ] Ev dizininde tek bir model onbellegi var

---

## Hangi komutu once calistirmaliyim

Bir sey calismadiginda bu sirayi izle. Her adim bir sonrakinin on kosuludur.

```mermaid
flowchart TD
    A[Bir sey calismiyor] --> B["python scripts/doctor.py"]
    B --> C{"[XX] satiri var mi?"}
    C -- Evet --> D["'->' satirindaki komutu uygula<br/>Bolum 1, 2, 3 veya 8"]
    D --> B
    C -- Hayir --> E["python -m app.cli info"]
    E --> F{"Veritabani ve parca sayisi var mi?"}
    F -- Hayir --> G["python -m app.cli ingest<br/>Bolum 6"]
    G --> G3{"'infinity ... valid JSON'<br/>hatasi cikti mi?"}
    G3 -- Evet --> G4["export FRAG_DEVICE=cpu<br/>Bolum 15"]
    G4 --> G
    G3 -- Hayir --> E
    F -- Evet --> H{"embedding_signature<br/>su anki backend ile ayni mi?"}
    H -- Hayir --> G2["python -m app.cli ingest<br/>Bolum 7"]
    G2 --> E
    H -- Evet --> I["python -m pytest tests/ -q"]
    I --> J{"Testler geciyor mu?"}
    J -- Hayir --> K["Bolum 14"]
    J -- Evet --> L["python -m app.cli -v ask 'RAG nedir?'"]
    L --> M{"Dogru parca<br/>Kaynaklar listesinde mi?"}
    M -- Hayir --> N["Getirme sorunu:<br/>python eval/calibrate.py<br/>Bolum 18"]
    N --> L
    M -- Evet --> P{"Kaynaklilik yuzdesi<br/>kac cikti?"}
    P -- "Dusuk / %0" --> Q{"Cevap ayni ifadeyi<br/>tekrarliyor mu?"}
    Q -- Evet --> R["export FRAG_CHAT_MODEL=qwen3-1.7b<br/>Bolum 16"]
    R --> L
    Q -- Hayir --> S["DAYANAKSIZ cumleleri oku,<br/>uydurma mi yanlis alarm mi<br/>Bolum 17"]
    S --> L
    P -- "Yuksek" --> T{"Cevaplanamaz sorulara<br/>da cevap veriyor mu?"}
    T -- Evet --> U["python eval/calibrate.py<br/>Bolum 18"]
    U --> L
    T -- Hayir --> V["python eval/evaluate.py --gate<br/>ile sayiyla dogrula<br/>Bolum 19"]
    V --> W["Sorun cozuldu"]
```

Diyagrami goremiyorsan ayni sira duz liste olarak:

1. `python scripts/doctor.py` — ortam saglam mi? `[XX]` varsa once onu coz.
2. `python -m app.cli info` — indeks var mi, hangi backend ile kurulmus?
3. `python -m app.cli ingest` — indeks yoksa veya imza uyusmuyorsa.
   `infinity ... valid JSON` hatasi cikarsa `export FRAG_DEVICE=cpu`
   ([15. bolum](#15-net-number-values-such-as-positive-and-negative-infinity-cannot-be-written-as-valid-json)).
4. `python -m pytest tests/ -q` — kod tarafi saglam mi? Hepsi gecmeli.
5. `python -m app.cli -v ask "RAG nedir?"` — uctan uca dene. Uc seye bak:
   `Kaynaklar` listesi, `guven` skorlari ve son satirdaki `Kaynaklilik`.
6. **Dogru parca gelmiyorsa** getirme sorunudur:
   `python eval/calibrate.py` ([18. bolum](#18-reddetme-dogrulugu-cok-dusuk--sistem-her-seye-cevap-veriyor)).
7. **Dogru parca geliyor ama kaynaklilik dusukse** uretim sorunudur:
   cevap kendini tekrarliyorsa [16. bolum](#16-cevap-ayni-kelimeyi-tekrar-edip-duruyor--tek-soru-dakikalarca-suruyor),
   degilse [17. bolum](#17-kaynaklilik-0-cikiyor).
8. **Sistem bilmedigi sorulara da cevap veriyorsa** esik kalibre edilmemistir:
   [18. bolum](#18-reddetme-dogrulugu-cok-dusuk--sistem-her-seye-cevap-veriyor).
9. Duzelttigini sandiginda sayiyla dogrula:
   `python eval/evaluate.py --backend hashing --no-save --gate`
   ([19. bolum](#19-cida-kalite-kapisi-basarisiz)).

### Her sey tikandiginda: bilinen calisan yol

Foundry Local'i bugun calistiramiyorsan, projeyi tamamen cevrimdisi yedek
backend ile ayaga kaldir ve derse oyle devam et:

```bash
python -m app.cli --backend hashing ingest
python -m app.cli --backend hashing ask "RAG nedir?"
python -m pytest tests/ -q
python eval/evaluate.py --backend hashing
```

Bu yol internet, model indirmesi ve Python 3.11 gerektirmez. Boru hattinin
tamami calisir; yalnizca dil modeli yerine alintilayan bir yedek devreye girer.
Foundry Local'i sonra kurdugunda `python -m app.cli ingest` ile yeniden
indeksleyip ayni sorulari tekrar sorarak farki olcebilirsin.
