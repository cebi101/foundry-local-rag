# macOS Kurulum Rehberi (Apple Silicon)

Bu rehber, projeyi sıfırdan bir Mac'te çalışır hale getirir. Komutlar kopyala-yapıştır
çalışacak şekilde yazıldı; her adımda **ne göreceğin** de yazıyor.

Rehberi sırayla uygula. Adımları atlarsan, en sık karşılaşılan tuzağa (bölüm 2) düşersin
ve saatlerce hata mesajı okursun.

> Windows kullanıyorsan bu rehber sana göre değil: [SETUP_WINDOWS.md](SETUP_WINDOWS.md).
> Tuzaklar farklıdır — orada sorun Python'un sürümü değil, `python` komutunun
> Microsoft Store'a gitmesi ve PowerShell'in script çalıştırmayı yasaklamasıdır.

**Bittiğinde elinde ne olacak:**

- `python3.12` tabanlı bir sanal ortam (`.venv`)
- Foundry Local SDK 1.x, doğru sürüm
- `data/docs/` içindeki 8 Türkçe ders notundan üretilmiş bir vektör indeksi
- Terminalden ve tarayıcıdan soru sorabildiğin, internete çıkmayan bir RAG asistanı

**Tahmini süre:** komutlar 10-15 dakika, model indirmeleri internet hızına bağlı.

---

## Hızlı kontrol listesi

Aceleci isen sıra bu. Her satırın ayrıntısı ilgili bölümde.

- [ ] `uname -m` çıktısı `arm64` mi? (bölüm 1)
- [ ] `sw_vers` çıktısında `ProductVersion` 14.0 veya üstü mü? (bölüm 1)
- [ ] Sistem Python'unu **kullanma**, sebebini oku (bölüm 2)
- [ ] `brew install python@3.12` (bölüm 3)
- [ ] `/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate` (bölüm 3)
- [ ] `pip install -r requirements.txt` (bölüm 4)
- [ ] `pip show foundry-local-sdk` → `Version: 1.x` (bölüm 4)
- [ ] `python scripts/doctor.py` → "Her sey yolunda gorunuyor." (bölüm 5)
- [ ] `python -m app.cli ingest` (bölüm 6)
- [ ] `python -m app.cli ask "Belge parcalama neden gerekli?"` (bölüm 6)
- [ ] `foundry` CLI kurma, gerekmiyor (bölüm 7)

---

## 1. Ön koşullar

| Gereksinim | Zorunlu değer | Nasıl kontrol edilir | Karşılanmazsa |
|---|---|---|---|
| İşlemci | Apple Silicon (`arm64`) | `uname -m` | Foundry Local çalışmaz. Intel Mac için **hiçbir build yok**. Bkz. aşağıdaki not. |
| İşletim sistemi | macOS 14.0 veya üstü | `sw_vers` | Yükselt. `libonnxruntime.dylib` minimum 14.0 istiyor. |
| RAM | ~8 GB | `sysctl hw.memsize` | 8 GB altında iki modeli aynı anda tutmak zorlaşır. |
| Boş disk | ~3 GB | `df -h ~` | Modeller + çalışma zamanı kütüphanesi sığmaz. |
| İnternet | Sadece ilk çalıştırmada | — | Katalog ve model dosyaları ilk kullanımda ağdan çekilir. |
| Homebrew | Kurulu | `brew --version` | https://brew.sh adresindeki komutu çalıştır. |

Kontrol komutları ve bu makinedeki gerçek çıktı:

```bash
uname -m
# arm64

sw_vers
# ProductName:		macOS
# ProductVersion:		14.6
# BuildVersion:		23G80
```

`uname -m` çıktısı `x86_64` ise iki ihtimal var:

1. Gerçekten Intel Mac kullanıyorsun. Foundry Local kurulamaz. Proje yine de çalışır:
   bölüm 6'daki `--backend hashing` yolunu izle, çevrimdışı yedek backend'i kullan.
2. Apple Silicon'dasın ama terminal Rosetta altında açılmış. Terminal.app'e sağ tıkla →
   Bilgi Al → "Rosetta kullanarak aç" seçeneğinin işaretini kaldır, terminali kapat aç.

### "Tamamen çevrimdışı" ne demek

Proje internete çıkmadan cevap üretir; sorular ve belgeler cihazdan çıkmaz. Ama bu
**ilk çalıştırmadan sonra** geçerli: model kataloğu ve model dosyaları ilk kullanımda
ağdan indirilir. Sunum yapacaksan indirmeleri önceden yap.

### Hızlandırma nasıl çalışıyor

macOS'ta hızlandırma ONNX Runtime'ın **WebGPU** execution provider'ı üzerinden gider
(Dawn → Metal). CoreML **değil**, Apple Neural Engine **değil**. Aksini söyleyen blog
yazıları yanıltıyor. Kurulum sonrası `~/.foundry_local_rag/ep/webgpu-ep/` klasöründe
`libonnxruntime_providers_webgpu.dylib` dosyasını görürsün; bu, doğru yolda olduğunun
kanıtıdır.

> Dizin adı `.foundry` değil `.foundry_local_rag`: Foundry Local önbelleği
> `app_name`'e göre ayırır ve bu projenin `app_name` değeri
> `foundry_local_rag`'dir (`backends/foundry.py`). Ayrıntısı bölüm 8.2'de.

---

## 2. Neden macOS'un sistem Python'u kullanılamaz

Bu, projedeki **1 numaralı tuzak**. Dikkatli oku.

macOS 14.6'nın sistem Python'u 3.9.6'dır:

```bash
/usr/bin/python3 -V
# Python 3.9.6
```

Foundry Local SDK 1.x ise **Python >= 3.11** ister. Sorun burada bitmiyor. Asıl sorun
şu: yanlış Python ile `pip install foundry-local-sdk` çalıştırdığında **hata almazsın**.

### pip neden sessizce yanlış sürümü kuruyor

pip, paket sürümlerini `requires_python` alanına göre filtreler. Python 3.9'da 1.x
sürümleri "uygun değil" diye elenir ve pip geriye kalan en yeni sürümü, yani `0.5.1`'i
kurar. Kurulum başarılı görünür.

Bunu kendi gözünle gör. Sistem Python'uyla çalıştır:

```bash
/usr/bin/pip3 index versions foundry-local-sdk
```

Bu makinedeki gerçek çıktı:

```
WARNING: pip index is currently an experimental command. It may be removed/changed in a future release without prior warning.
foundry-local-sdk (0.5.1)
Available versions: 0.5.1, 0.5.0, 0.4.0, 0.3.1, 0.3.0
```

Çıktı **yanıltıcı**. "Available versions" listesinde 1.x hiç görünmüyor. Bu, PyPI'da 1.x
olmadığı anlamına gelmez; sadece *bu yorumlayıcı için* uygun sürümlerin listesi. Aynı
komutu Python 3.12 ortamında çalıştırırsan listede 1.x sürümlerini görürsün.

Yani: bu çıktıya bakıp "demek ki en yeni sürüm 0.5.1" sonucuna varma. Yanlış sonuç.

### İki SDK kuşağı, aynı paket adı

| | 0.x (eski) | 1.x (güncel, bu proje) |
|---|---|---|
| pip paket adı | `foundry-local-sdk` | `foundry-local-sdk` (aynı) |
| import edilen modül | `foundry_local` | `foundry_local_sdk` |
| Python gereksinimi | herhangi | **>= 3.11** |
| Nasıl çalışır | HTTP istemcisi, PATH'te `foundry` CLI gerekir | süreç içi (in-process) yerel çekirdek, CLI gerekmez |
| API | tamamen farklı | tamamen farklı |

Aynı pip adını paylaştıkları için `pip install` seni uyarmaz. 0.5.1 kurulduğunda
`from foundry_local_sdk import ...` satırı `ImportError` verir ve internette aradığın her
örnek kod farklı bir API'yi anlatır.

### Proje bu durumu nasıl yakalıyor

`src/foundry_rag/backends/foundry.py` içindeki `_import_sdk()` fonksiyonu üç şeyi ayrı
ayrı kontrol eder:

1. Yorumlayıcı 3.11'in altındaysa, `pip install` denemeden önce açık mesajla durur.
2. `foundry_local_sdk` import edilemiyor ama `foundry_local` edilebiliyorsa, "eski 0.x
   kurulu" der ve yükseltme komutunu yazar.
3. Hiçbiri yoksa, kurulum komutunu yazar.

`scripts/doctor.py` de aynı kontrolü `importlib.metadata` ile yapar ve sürüm `0.` ile
başlıyorsa `[XX]` işaretiyle raporlar.

### Kural

> Bu proje için **hiçbir zaman** `/usr/bin/pip3` veya sanal ortam dışında `pip install`
> çalıştırma. Önce bölüm 3'teki sanal ortamı aç.

### sqlite hakkında küçük bir not

Sistem Python'unun `sqlite3` modülü uzantı yükleyemez (`enable_load_extension` yok), bu
yüzden `sqlite-vec` gibi vektör uzantıları kullanılamaz. **Bu proje için sorun değil:**
`src/foundry_rag/retrieval.py` içindeki `cosine_similarity()` aramayı numpy ile kaba
kuvvet yapar (kelime tarafı da saf Python/numpy: `lexical.py` içindeki BM25).
`doctor.py` bunu `[!!]` (uyarı) olarak gösterir, hata olarak değil.

---

## 3. Python 3.12 kurulumu ve sanal ortam

### 3.1 Python 3.12'yi kur

```bash
brew install python@3.12
```

**Neden 3.12?** SDK'nın alt sınırı 3.11, ama numpy 2.5 artık 3.11'i desteklemiyor.
3.12 iki tarafı da karşılayan tatlı nokta.

Kurulumu doğrula:

```bash
/opt/homebrew/bin/python3.12 -V
# Python 3.12.x
```

`no such file or directory` alıyorsan Homebrew Apple Silicon için `/opt/homebrew`
altında değil demektir. `brew --prefix` çalıştır ve yolu ona göre düzelt.

### 3.2 Sanal ortamı oluştur

Proje kökünde çalış:

```bash
cd ~/Desktop/foundry-local-rag
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
```

`python3.12` yerine **tam yolu** yazmamızın sebebi: PATH'inde başka bir `python3.12`
olabilir ve yanlış yorumlayıcıyla venv kurmak bölüm 2'deki tuzağa geri döndürür.

### 3.3 Doğrula

Bu üç komut da beklenen çıktıyı vermeli:

```bash
python -V
# Python 3.12.x

which python
# /Users/<kullanici>/Desktop/foundry-local-rag/.venv/bin/python

python -c "import platform, sys; print(platform.machine(), sys.version_info[:2])"
# arm64 (3, 12)
```

`which python` hâlâ `/usr/bin/python3` veya `/Library/Developer/...` gösteriyorsa
`source .venv/bin/activate` çalışmamıştır. Tekrar dene.

### 3.4 Her yeni terminalde

Sanal ortam terminal oturumuna bağlıdır. Yeni bir sekme açtığında:

```bash
cd ~/Desktop/foundry-local-rag
source .venv/bin/activate
```

Prompt'un başında `(.venv)` görüyorsan hazırsın. Bu rehberdeki bundan sonraki her
`python` / `pip` komutu, ortam **açıkken** çalıştırılacak.

`.venv/` klasörü `.gitignore` içinde, repoya girmez.

---

## 4. Bağımlılıkların kurulumu

### 4.1 Kur

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` şunları kurar:

| Paket | Ne için | Not |
|---|---|---|
| `numpy>=1.24` | vektör matrisi, kosinüs benzerliği | çekirdek, her zaman gerekli |
| `foundry-local-sdk>=1.2` | yerel model çalıştırma | `; python_version >= "3.11"` işaretli |
| `openai>=1.40` | SDK'nın istemci tipleri | `; python_version >= "3.11"` işaretli |
| `streamlit>=1.30` | web arayüzü | `app/streamlit_app.py` için |
| `pytest>=7.4` | test | `tests/` altındaki test paketi |

Dosyadaki `; python_version >= "3.11"` işaretleri kasıtlı: yanlış Python'da kurulum
denenirse SDK satırları hiç uygulanmaz, proje de sessizce çevrimdışı yedek backend'e
düşer. Yine de doğru yorumlayıcıyı kullan.

İstersen paketi düzenlenebilir modda da kurabilirsin (`pip install -e .`), ama zorunlu
değil: `app/_bootstrap.py` çalışma anında `src/` klasörünü `sys.path`'e ekler.

### 4.2 1.x sürümünü doğrula

Bu adımı **atlama**. Bölüm 2'deki tuzağın kapandığını burada kanıtlıyorsun.

```bash
pip show foundry-local-sdk
```

Beklenen (sürüm numarası ara sürümlere göre değişebilir, **`1.` ile başlaması** şart):

```
Name: foundry-local-sdk
Version: 1.2.3
Location: /Users/<kullanici>/Desktop/foundry-local-rag/.venv/lib/python3.12/site-packages
```

`Version: 0.5.1` görüyorsan yanlış Python'dasın. Bölüm 3'e dön.

Modülün gerçekten import edilebildiğini de kontrol et:

```bash
python -c "from foundry_local_sdk import Configuration, FoundryLocalManager; print('SDK 1.x tamam')"
# SDK 1.x tamam
```

Eski paketin ortamda **olmadığını** doğrula:

```bash
python -c "import foundry_local" 2>&1 | tail -1
# ModuleNotFoundError: No module named 'foundry_local'
```

Bu `ModuleNotFoundError` **iyi haber**. Eski 0.x kuşağı ortamda yok demek.

---

## 5. `python scripts/doctor.py` çıktısını okumak

```bash
python scripts/doctor.py
```

Bir şey çalışmadığında **ilk çalıştıracağın komut budur**. Elle hata ayıklamaya
başlamadan önce bunu çalıştır.

### İşaretler

| İşaret | Anlamı | Ne yapmalı |
|---|---|---|
| `[ok]` | Kontrol geçti | Bir şey yapma |
| `[!!]` | Uyarı | Proje çalışır, ama bir özellik eksik olabilir |
| `[XX]` | Hata | Altındaki `->` satırındaki komutu uygula |

`[XX]` satırlarının sayısı çıkış koduna yansır: sorun varsa `1`, yoksa `0` döner.
Son satır ya `Her sey yolunda gorunuyor.` ya da `N sorun bulundu. Yukaridaki '->'
satirlarini uygula.` olur.

### Dört bölüm neyi kontrol eder

| Bölüm | Kontrol | Neden önemli |
|---|---|---|
| `--- Platform ---` | `platform.machine()` `arm64` mi | Foundry Local wheel'leri sadece arm64 |
| `--- Python ---` | Sürüm >= 3.11, sqlite uzantı desteği | Bölüm 2'deki tuzak |
| `--- Paketler ---` | numpy, streamlit, SDK kuşağı (0.x mi 1.x mi) | Yanlış SDK'yı yakalar |
| `--- Foundry Local katalogu ---` | `chat_model` ve `embedding_model` alias'ları katalogda var mı | Alias'lar donanıma bağlı |

### Örnek 1: HATALI ortam (sistem Python'u ile)

Aşağıdaki çıktı, bu makinede `/usr/bin/python3 scripts/doctor.py` çalıştırıldığında
gerçekten alınan çıktıdır. Bölüm 3'ü atlarsan böyle görünür:

```
==============================================================
  Yerel RAG Asistani -- ortam kontrolu
==============================================================

--- Platform ---
  [ok]  islemci mimarisi: arm64
  [ok]  isletim sistemi: macOS-14.6-arm64-arm-64bit

--- Python ---
  [XX]  python: 3.9.6 (/Library/Developer/CommandLineTools/usr/bin/python3) -- Foundry Local SDK 1.x >= 3.11 istiyor
         -> brew install python@3.12 && /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
  [!!]  sqlite 3.43.2 / uzanti yukleme: False
         -> sqlite-vec bu yorumlayicida kullanilamaz. Bu proje icin sorun degil: arama numpy ile kaba kuvvet yapiliyor.

--- Paketler ---
  [ok]  numpy 2.0.2
  [ok]  streamlit 1.50.0
  [!!]  foundry-local-sdk kurulu degil (cevrimdisi yedek backend calisir)
         -> pip install 'foundry-local-sdk>=1.2' openai

--- Foundry Local katalogu ---
  [!!]  Foundry Local baslatilamadi: Foundry Local SDK 1.x requires Python >= 3.11, but this interpreter is 3.9.
macOS ships 3.9 as /usr/bin/python3 and pip will silently install the incompatible 0.5.1 SDK instead of erroring.
Fix:  brew install python@3.12 && /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
         -> Cevrimdisi yedek backend ile calisabilirsin: python -m app.cli --backend hashing ingest

==============================================================
  1 sorun bulundu. Yukaridaki '->' satirlarini uygula.
```

Bu çıktının okunuşu, satır satır:

- `arm64` → donanım uygun, sorun donanımda değil.
- `[XX] python: 3.9.6` → **asıl hata bu**. Tek `[XX]` satırı, tek gerçek sorun.
- `sqlite ... uzanti yukleme: False` → uyarı, görmezden gel.
- `foundry-local-sdk kurulu degil` → 3.9 ortamında kurulmamış; doğru davranış.
- Katalog bölümü zaten Python sürümüne takılıyor. **İlk `[XX]`'i düzeltince gerisi
  düzelir**, dördünü ayrı ayrı çözmeye çalışma.

### Örnek 2: DOĞRU ortam (`.venv` açıkken)

Bölüm 3 ve 4'ü uyguladıktan sonra beklenen çıktının biçimi. Sürüm numaraları ve katalog
model sayısı makineden makineye değişir:

```
==============================================================
  Yerel RAG Asistani -- ortam kontrolu
==============================================================

--- Platform ---
  [ok]  islemci mimarisi: arm64
  [ok]  isletim sistemi: macOS-14.6-arm64-arm-64bit

--- Python ---
  [ok]  python: 3.12.x (/Users/<kullanici>/Desktop/foundry-local-rag/.venv/bin/python)
  [ok]  sqlite 3.4x.x / uzanti yukleme: True

--- Paketler ---
  [ok]  numpy 2.x.x
  [ok]  streamlit 1.xx.x
  [ok]  foundry-local-sdk 1.x.x (modul: foundry_local_sdk)

--- Foundry Local katalogu ---
  [ok]  katalogda <sayi> model var
  [ok]  sohbet modeli 'qwen2.5-0.5b': bulundu
  [ok]  embedding modeli 'qwen3-embedding-0.6b': bulundu

==============================================================
  Her sey yolunda gorunuyor.
```

Katalog bölümü ilk çalıştırmada internet ister. Ağ yoksa `katalog bos dondu` uyarısını
görürsün.

`embedding modeli 'qwen3-embedding-0.6b': BULUNAMADI` yazıyorsa `doctor.py` altına bu
donanımda mevcut ilk 15 alias'ı basar. Alias'lar donanıma bağlıdır; listeye bakıp
`FRAG_EMBEDDING_MODEL` ile başka bir alias seçebilirsin (bkz. `.env.example`).

---

## 6. İlk indeksleme ve ilk soru

### 6.1 Önce indirmeyi bil

İlk çalıştırmada toplam **~1.3 GB** model indirmesi ve ayrıca **~146 MB** yerel
çalışma zamanı kütüphanesi inecek. Dağılım:

| Ne zaman iner | Ne iner | Yaklaşık boyut |
|---|---|---|
| İlk `FoundryLocalManager.initialize()` | WebGPU execution provider kütüphanesi | ~146 MB |
| `python -m app.cli ingest` sırasında | `qwen3-embedding-0.6b` | ~520-541 MB |
| İlk `ask` / `chat` sırasında | `qwen2.5-0.5b` | ~735 MB (gpu) / ~862 MB (cpu) |

Sohbet modelinin `ingest` sırasında **inmemesi** normaldir:
`FoundryBackend._ensure_chat_client()` tembeldir, sohbet modelini ilk soruya kadar
yüklemez.

Modeller `~/.foundry_local_rag/cache/models` altına iner. Hiçbir modelde EULA/lisans
onay kapısı yok; hepsi MIT veya Apache-2.0.

> **Uyku moduna dikkat.** İndirme sürerken Mac uykuya geçerse bozuk model önbelleği
> kalabiliyor ve önbellek bütünlük doğrulaması yok (açık hatalar: Foundry-Local #909,
> #906). İndirme bitene kadar makineyi uyandır tut. Bozulursa bölüm 8'deki temizlik
> adımını uygula.

### 6.2 İndeksle

```bash
python -m app.cli ingest
```

Beklenen çıktının yapısı (satır sayıları ve süreler makinene göre değişir; `54 parca`
bu depodaki 8 belge için gerçek değerdir):

```

  Yerel RAG Asistani  --  Microsoft Foundry Local
  Belgelerinden cevap uretir, internete cikmaz.

Belge klasoru : /Users/<kullanici>/Desktop/foundry-local-rag/data/docs
Veritabani    : /Users/<kullanici>/Desktop/foundry-local-rag/data/rag.db
Parca boyutu  : 900 (ortusme 150)

  Downloading embedding model (qwen3-embedding-0.6b)...
  embedding: 100.0%
  embedding: qwen3-embedding-0.6b-<varyant> [<cihaz> / <execution_provider>]
Backend: foundry-local (chat=qwen2.5-0.5b, embed=qwen3-embedding-0.6b, dim=1024)

  Embedding: 54/54 parca

8 belge -> 54 parca (54 yeni kayit) / <sure> sn

Hazir. Soru sormak icin: python -m app.cli chat
```

Kontrol edeceğin üç şey:

1. **`Backend: foundry-local`** yazıyor mu? `hashing-offline` yazıyorsa 6.5'e bak.
2. **`dim=1024`** mü? `qwen3-embedding-0.6b` 1024 boyutlu vektör üretir. Bu değer koda
   gömülü değil; `FoundryBackend.embedding_dim` kısa bir metni embed edip ölçer.
3. **`embedding: ... [<cihaz> / <execution_provider>]`** satırındaki varyant. Model
   id'si `-generic-gpu` ile bitiyorsa hızlandırılmış build çalışıyor; `-generic-cpu`
   ile bitiyorsa CPU build'i seçilmiş demektir.

> **Embedding modelinde `-generic-cpu` görmen normaldir, hata değildir.** Apple
> Silicon'da `qwen3-embedding-0.6b`'nin `-generic-gpu` varyantı vektörün içine
> Inf/NaN yazıyor; hata da modelde değil, SDK'nın JSON serileştiricisinde patlıyor
> ("positive and negative infinity cannot be written as valid JSON"). Bu yüzden
> `backends/foundry.py` içindeki `_embedding_device_default()` macOS arm64'te
> `device="auto"` iken **embedding için bilerek CPU varyantını seçer**. `embed()`
> ayrıca bu hatayı yakalayıp tek seferlik CPU'ya geçiş yapar. Zorlamak istersen
> `FRAG_DEVICE=gpu`, kalıcı olarak kapatmak istersen `FRAG_DEVICE=cpu`.
> Bu kural yalnızca embedding modeli içindir; sohbet modelinin varyantını Foundry
> Local kendi seçer.

> **Açık hata: #858 / #895.** GPU execution provider doğru kaydolsa bile bazen yalnızca
> CPU varyantları görünüyor ve sessizce yavaş build çalışıyor. Fark edilmesinin tek
> yolu bu satırı okumak; bu yüzden `describe_variant()` fonksiyonu `load()` sonrası
> `model.id` ve `execution_provider` değerlerini yazdırıyor. Bu madde **sohbet
> modeli** için geçerlidir — embedding tarafındaki CPU seçimi yukarıda anlatıldığı
> gibi kasıtlıdır.

### 6.3 İndeksi kontrol et

```bash
python -m app.cli info
```

Bu depoda `--backend hashing` ile indekslendiğinde alınan gerçek çıktı:

```
Veritabani : /Users/<kullanici>/Desktop/foundry-local-rag/data/rag.db
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
  - 02-foundry-local.md
  - 03-embedding-ve-vektor-arama.md
  - 04-sqlite-ile-yerel-depolama.md
  - 05-prompt-muhendisligi.md
  - 06-belge-parcalama.md
  - 07-proje-mimarisi.md
  - 08-test-ve-degerlendirme.md
```

Foundry Local ile indekslediysen ilk iki meta satırı şöyle olur:

```
  embedding_signature    foundry-local:qwen3-embedding-0.6b:1024
  backend                foundry-local
```

`embedding_signature` satırı önemli: `RagPipeline._check_index()` her açılışta bunu
şimdiki backend'in imzasıyla karşılaştırır.

### 6.4 İlk soru

```bash
python -m app.cli ask "Belge parcalama neden gerekli?"
```

İlk `ask` çağrısında sohbet modeli (`qwen2.5-0.5b`) inecek, bu yüzden ilk soru
sonrakilerden yavaştır.

Çıktının yapısı: önce cevap metni, sonra kaynaklar, sonra zamanlama. Aşağıdaki çıktı
`--backend hashing` ile alınan gerçek çıktıdır — Foundry Local ile cevap metni bir dil
modeli tarafından yazılır, **kaynaklar ve zamanlama bloğunun biçimi aynıdır**:

```
SDK yöneticisi başlatıldığında servis otomatik olarak ayağa kalkar, gerekli
model indirilir ve belleğe yüklenir. [02-foundry-local.md]

(Not: Foundry Local kurulu olmadığı için bu cevap bir dil modeli tarafından yazılmadı; belgelerden doğrudan alıntılandı.)

Kaynaklar:
  [1] 02-foundry-local.md > Servis Modeli
      guven 0.391 | anlam 0.074 | kelime 10.29 | bulan: ikisi

  getirme: 0 ms | uretim: 0.00 sn

Kaynaklilik: %50 (1/2 cumle dayanakli) -- 1 cumle bağlamda doğrulanamadı  [mod: generative]
  [!] (0.19) (Not: Foundry Local kurulu olmadığı için bu cevap bir dil modeli...
      ^ Bu cumleler getirilen belgelerde dogrulanamadi. Modelin kendi ezberinden eklemis olabilecegi kisimlar bunlar.
```

Kaynak satırındaki dört sayı: `guven` cevap/reddetme kararında kullanılan skor,
`anlam` kosinüs benzerliği, `kelime` BM25 skoru, `bulan` ise parçayı hangi
aramanın getirdiği (`anlam` / `kelime` / `ikisi`). Getirme hibrittir: vektör
araması ile BM25 birlikte çalışır ve sonuçlar RRF ile birleştirilir
(`src/foundry_rag/retrieval.py`, `hybrid_search()`).

Son blok `groundedness.py`'nin denetimidir: cevabın her cümlesi getirilen
parçalara karşı puanlanır, dayanağı olmayanlar `[!]` ile işaretlenir. Kapatmak
için `FRAG_CHECK_GROUNDEDNESS=0`.

Parantez içindeki "(Not: Foundry Local kurulu olmadığı için...)" satırını görüyorsan
**dil modeli çalışmıyor**, çevrimdışı yedek backend cevap veriyor demektir. Foundry
Local doğru kuruluysa bu satır çıkmaz.

Cevap yerine `Bu bilgi elimdeki belgelerde yok.` görebilirsin. Bu bir hata değil: hiçbir
parça `min_similarity` eşiğini (varsayılan `0.30`) geçmemiştir ve `RagPipeline.answer()`
modeli hiç çağırmadan durur. Kasıtlı bir tasarım — model uydursun diye çağırmıyoruz.

### 6.5 Diğer çalıştırma yolları

```bash
python -m app.cli chat                        # etkileşimli döngü, cevap akarak yazılır
python -m app.cli ask "soru" --no-sources     # kaynakları gizle
python -m app.cli --top-k 6 ask "soru"        # daha çok parça getir
streamlit run app/streamlit_app.py            # tarayıcı arayüzü
python -m pytest tests/ -q                    # testler, hepsi çevrimdışı
python eval/evaluate.py                       # sadece getirme metrikleri
python eval/evaluate.py --generate            # cevap üretimini de ölç (yavaş)
```

`chat` içinden çıkmak için `q`, `quit`, `exit`, `cik` yazabilir ya da Ctrl-C
kullanabilirsin.

### 6.6 Foundry Local olmadan çalıştırmak

Varsayılan backend `auto`: Foundry Local erişilebilirse onu kullanır, değilse görünür
bir uyarıyla çevrimdışı yedeğe (`HashingBackend`) düşer. Uyarı şöyle görünür:

```
[!] Foundry Local kullanilamiyor, cevrimdisi yedek backend'e gecildi.
    Sebep: <gercek sebep>
    Ayrinti icin: python scripts/doctor.py
```

Üç seçenek var:

| Değer | Davranış | Ne zaman |
|---|---|---|
| `auto` (varsayılan) | Foundry varsa onu kullan, yoksa yedeğe düş | İlk gün, kurulum sürerken |
| `foundry` | Foundry zorunlu, yoksa yüksek sesle hata ver | Kurulum bitince; sessiz bozulmayı önler |
| `hashing` | Her zaman çevrimdışı yedek | Test, CI, Intel Mac |

```bash
python -m app.cli --backend hashing ingest    # Foundry Local olmadan indeksle
python -m app.cli --backend foundry ask "..."  # sessiz düşüşü kapat, gerçek hatayı gör
```

`HashingBackend` **semantik bir embedder değildir**: hash'lenmiş kelime ve karakter
n-gram'ları eşleştirir, cevabı da üretmez — en iyi eşleşen cümleleri alıntılar. Bu
kasıtlı bir taban çizgisi. `eval/evaluate.py --backend hashing` ile ölçülen
değerler (33 soruluk set, `top_k=4`):

| Metrik | Yalnız vektör, `min_similarity=0.15` | Hibrit + kalibre, `min_similarity=0.30` (varsayılan) |
|---|---|---|
| Recall@4 | %72.0 | %88.0 |
| MRR | 0.650 | 0.793 |
| Reddetme doğruluğu | %87.5 | %100.0 |
| Genel doğruluk | %75.8 | %90.9 |

Soldaki sütun yalnızca vektör aramasının (`FRAG_HYBRID=0`) sonucudur; sağdaki
sütun deponun **varsayılan** yapılandırmasıdır (BM25 + vektör, RRF füzyonu,
`eval/calibrate.py` ile seçilmiş eşik). Bu sayılar gerçek embedding modeliyle
karşılaştırma yapman için var. `eval/questions.json` içinde 33 soru vardır:
25 cevaplanabilir, 8 cevaplanamaz.

### 6.7 Backend değiştirirsen yeniden indeksle

En sık yapılan hata: `hashing` ile indeksleyip `foundry` ile soru sormak. Vektör uzayları
uyumsuz olduğu için `RagPipeline._check_index()` çalışmayı reddeder:

```
Indeks farkli bir embedding modeliyle olusturulmus.
  indekste: hashing-offline:512
  simdiki : foundry-local:qwen3-embedding-0.6b:1024
Vektor uzaylari uyumsuz. Yeniden indeksle:
  python -m app.cli ingest
```

Çözüm mesajın içinde: `python -m app.cli ingest` ile yeniden indeksle. Bu bir arıza
değil, kasıtlı bir koruma — aksi halde anlamsız benzerlik skorları alırdın.

### 6.8 Cevap kalitesi hakkında dürüst not

`qwen2.5-0.5b` küçük bir modeldir ve **belgeye dayalı (grounded) cevaplama için
zayıftır**. Kurulumun doğru çalıştığını göstermeye yeter, ödev kalitesinde cevap
beklemeyin. Gerçek kalite istiyorsan daha büyük bir sohbet modeline geç:

```bash
export FRAG_CHAT_MODEL=qwen3-1.7b     # ~1490 MB
# veya
export FRAG_CHAT_MODEL=qwen3-4b       # ~3083 MB
```

Sohbet modelini değiştirmek yeniden indeksleme gerektirmez; indeks yalnızca **embedding**
modeline bağlıdır. Diğer ayarlar için `.env.example` dosyasına bak.

Denemek isteyip de bulamayacağın modeller: `Phi-4-mini-instruct-generic-cpu` arm64'te
desteklenmiyor (Microsoft'un kendi blocklist'inde), `deepseek-r1-1.5b`nin Mac varyantı
hiç yok.

---

## 7. `foundry` CLI kurmalı mıyım?

**Hayır.** Bu proje CLI olmadan çalışır. SDK 1.x çalışma zamanını kendi içinde taşır ve
çıkarımı süreç içinde (in-process) yapar; ayrı bir servis ya da PATH'te `foundry`
komutu gerekmez. `pip install -r requirements.txt` yeterlidir.

Bunu bilmek önemli, çünkü internetteki birçok örnek 0.x kuşağına ait ve orada CLI
zorunluydu.

### Yanlışlıkla kurabileceğin iki şey

| Komut | Ne yapar | Bu projede |
|---|---|---|
| `pip install -r requirements.txt` | SDK 1.x + çalışma zamanı | **Doğru olan bu** |
| `brew tap microsoft/foundrylocal` + `brew install foundrylocal` | ~6 ay eski tap'ten **v0.8.119** kurar | Kurma |
| `brew install foundry` | **Tamamen başka bir yazılım** (Ethereum geliştirme aracı) | Kesinlikle kurma |

### `brew install foundrylocal` neden tuzak

Homebrew tap'i (`microsoft/foundrylocal`) yaklaşık 6 ay geride ve **v0.8.119** kuruyor.
Bu sürüm embedding desteğinden (`minFLVersion 1.1.0`) **önceki** bir sürüm. Sonuç: brew
ile kurduğun CLI `qwen3-embedding-0.6b` modelini kataloğunda **göremez**. Modelin
yokmuş gibi görünür, sen de olmayan bir sorunu ayıklamaya çalışırsın.

### `brew install foundry` neden tehlikeli

`foundry` (sonunda `local` olmadan) Ethereum akıllı sözleşme geliştirme araç setidir.
Microsoft ile ilgisi yoktur. PATH'ine `forge`, `cast`, `anvil` gibi komutlar ekler,
diskte yer kaplar ve bu projeye hiçbir katkısı olmaz. Yanlışlıkla kurduysan:

```bash
brew uninstall foundry
```

### Gerçekten CLI'ye ihtiyacın olursa

Bu projede yok, ama başka bir sebeple istiyorsan Homebrew'dan değil, GitHub releases
sayfasındaki `.pkg` dosyasından kur. Sadece orada güncel sürüm var.

---

## 8. Kurulumu geri alma

Sıfırdan başlamak ya da diski boşaltmak için. Sırayla uygula.

### 8.1 Sanal ortamı sil

```bash
deactivate                 # ortam açıksa
rm -rf ~/Desktop/foundry-local-rag/.venv
```

Bu, `pip install` ile gelen her şeyi (SDK dahil) siler. `.venv/` zaten `.gitignore`
içinde, repo etkilenmez.

### 8.2 Model önbelleğini ve çalışma zamanını sil

Foundry Local önbelleği **`app_name`'e göre ayırır.** Bu projenin `app_name`
değeri `foundry_local_rag`'dir (`backends/foundry.py` içinde sabit), dolayısıyla
bu projenin indirdiği her şey `~/.foundry_local_rag` altındadır:

| Yol | İçerik |
|---|---|
| `~/.foundry_local_rag/cache/models/` | İndirilen model dosyaları (GB'larca olabilir) |
| `~/.foundry_local_rag/ep/webgpu-ep/` | WebGPU execution provider kütüphanesi |
| `~/.foundry_local_rag/logs/` | Günlük dosyaları |

`~/.foundry` dizinini de görebilirsin: başka bir `app_name` kullanan bir araç
(ya da `foundry` CLI'ı) onu oluşturur. **Bu projenin modelleri orada değildir**,
o yüzden sadece `~/.foundry`'yi silmek diski boşaltmaz.

Önce ne kadar yer kapladıklarına bak, sonra sil:

```bash
du -sh ~/.foundry_local_rag ~/.foundry 2>/dev/null
rm -rf ~/.foundry_local_rag
```

**Sadece bozuk modelleri temizlemek** istiyorsan (uyku modu kaynaklı bozulma —
Foundry-Local #909 / #906) tamamını silmene gerek yok:

```bash
rm -rf ~/.foundry_local_rag/cache/models
```

Bir sonraki çalıştırmada modeller yeniden iner. Önbellek bütünlük doğrulaması olmadığı
için, "model yükleniyor ama tuhaf davranıyor" durumunda ilk denenecek şey budur.

### 8.3 Proje verilerini sil

```bash
rm -f ~/Desktop/foundry-local-rag/data/rag.db
rm -f ~/Desktop/foundry-local-rag/eval/results.jsonl
```

İndeks yeniden üretilebilir; `python -m app.cli ingest` ile geri gelir. Bu dosyalar
`.gitignore` içindedir.

`data/docs/` klasörünü **silme** — bilgi tabanının kaynağı orası.

### 8.4 İsteğe bağlı: Python 3.12'yi kaldır

```bash
brew uninstall python@3.12
```

Başka projelerin de kullanıyor olabileceğini unutma. Emin değilsen bırak, sadece ~150 MB.

### 8.5 Tam sıfırlama, tek blok

```bash
cd ~/Desktop/foundry-local-rag
deactivate 2>/dev/null
rm -rf .venv data/rag.db eval/results.jsonl
rm -rf ~/.foundry_local_rag
```

Sonra bölüm 3'ten devam et.

---

## Sık karşılaşılan hatalar

| Belirti | Sebep | Çözüm |
|---|---|---|
| `ModuleNotFoundError: No module named 'foundry_local_sdk'` | Eski 0.x kurulu veya SDK hiç kurulu değil | Bölüm 3-4 |
| `pip show` → `Version: 0.5.1` | Python 3.9 ile kurulmuş | Bölüm 2-3 |
| `Backend: hashing-offline` yazıyor | `auto` yedeğe düştü | `--backend foundry` ile gerçek sebebi gör, sonra `doctor.py` |
| `Indeks farkli bir embedding modeliyle olusturulmus` | Backend değişti, indeks eski | `python -m app.cli ingest` |
| `Veritabani bos. Once belgeleri indeksle` | Hiç indeksleme yapılmamış | `python -m app.cli ingest` |
| Sohbet modelinin id'si `-generic-cpu` ile bitiyor | GPU varyantı görünmüyor (#858 / #895) | Bilinen açık hata; çalışır ama yavaştır |
| Embedding modelinin id'si `-generic-cpu` ile bitiyor | Kasıtlı: GPU varyantı Apple Silicon'da Inf/NaN üretiyor (`_embedding_device_default()`) | Bir şey yapma. Zorlamak istersen `FRAG_DEVICE=gpu` |
| Cevap yazıldıktan sonra `IndexError` | Streaming döngüsü son boş chunk'ta patlıyor (#905) | Bu depoda korumalı: `if not chunk.choices: continue` |
| Model yüklendi ama tuhaf davranıyor | İndirme sırasında uyku → bozuk önbellek (#909 / #906) | `rm -rf ~/.foundry_local_rag/cache/models` |
| `katalog bos dondu` | İlk çalıştırmada internet yok | Ağa bağlan |
| Streamlit'te ikinci `initialize()` çökmesi | SDK singleton'ı iki kez başlatılıyor | Bu depoda korumalı: `if FoundryLocalManager.instance is None` |

---

## Kurulum sonrası kontrol listesi

- [ ] `python -V` → `3.12.x`
- [ ] `which python` → `.../.venv/bin/python`
- [ ] `pip show foundry-local-sdk` → `Version: 1.x`
- [ ] `python scripts/doctor.py` → `Her sey yolunda gorunuyor.`
- [ ] `python -m pytest tests/ -q` → tüm testler geçti
- [ ] `python -m app.cli ingest` → `Backend: foundry-local (... dim=1024)`
- [ ] `python -m app.cli info` → `Parca : 54`, `Belge : 8`
- [ ] `python -m app.cli ask "..."` → cevap + `Kaynaklar:` bloğu
- [ ] `streamlit run app/streamlit_app.py` → tarayıcı arayüzü açılıyor

Hepsi işaretliyse kurulum tamam.
