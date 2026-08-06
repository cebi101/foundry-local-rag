# Windows Kurulum Rehberi

Bu rehber, projeyi sıfırdan bir Windows makinede çalışır hale getirir. Komutlar
kopyala-yapıştır çalışacak şekilde yazıldı; her adımda **ne göreceğin** de yazıyor.

Rehberi sırayla uygula. Adımları atlarsan, Windows'a özgü iki tuzağa (bölüm 2 ve
bölüm 3.3) düşersin ve saatlerce anlamsız hata mesajı okursun.

**Bittiğinde elinde ne olacak:**

- `py -3.12` tabanlı bir sanal ortam (`.venv`)
- Foundry Local SDK 1.x, doğru sürüm
- `data\docs\` içindeki 8 Türkçe ders notundan üretilmiş bir vektör indeksi
- Terminalden ve tarayıcıdan soru sorabildiğin, internete çıkmayan bir RAG asistanı

**Tahmini süre:** komutlar 10-15 dakika, model indirmeleri internet hızına bağlı.

> ### Bu rehberin doğrulama durumu — önce bunu oku
>
> Deponun ölçülmüş sayıları (`%97` doğruluk, `0.35 sn` getirme, `-generic-cpu`
> embedding varyantı) **macOS Apple Silicon üzerinde** üretildi. Bu rehber
> koddaki platform dallarından ve Foundry Local'in belgelenmiş Windows
> desteğinden yazıldı; **komut çıktıları bir Windows makinede satır satır
> doğrulanmadı.**
>
> Pratikte bunun anlamı:
>
> - **Platformdan bağımsız olan her şey aynen geçerlidir.** Getirme mantığı,
>   BM25, RRF füzyonu, Türkçe morfoloji, kaynaklılık denetimi, eşik kalibrasyonu
>   ve testlerin tamamı saf Python + numpy'dir. CI bunları her push'ta Ubuntu
>   üzerinde çalıştırıyor, yani "yalnızca macOS'ta çalışıyor" diye bir durum yok.
> - **Donanıma bağlı olan şeyler değişir.** Hangi model varyantının seçileceği,
>   hangi execution provider'ın kullanılacağı ve indirme boyutları Windows'ta
>   farklıdır. Bu rehber nereye bakacağını söyler, sayıyı önceden söylemez.
> - **Eşik yeniden kalibre edilmelidir.** `FRAG_MIN_SIMILARITY` embedding
>   modelinin skor dağılımına bağlıdır. Bölüm 6.7'ye bak.
>
> Bir adım burada yazandan farklı davranırsa bu bir hata raporudur, senin
> hatan değil: çıktıyı not al ve `docs/TROUBLESHOOTING.md`'ye ekle.

---

## Hızlı kontrol listesi

Aceleci isen sıra bu. Her satırın ayrıntısı ilgili bölümde.

- [ ] 64-bit Windows 10 (22H2+) veya Windows 11 mi? (bölüm 1)
- [ ] Microsoft Store'un sahte `python` kısayoluna **güvenme**, sebebini oku (bölüm 2)
- [ ] `winget install Python.Python.3.12` (bölüm 3.1)
- [ ] `py -3.12 -m venv .venv` (bölüm 3.2)
- [ ] PowerShell script çalıştırma izni: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (bölüm 3.3)
- [ ] `.venv\Scripts\Activate.ps1` (bölüm 3.3)
- [ ] `pip install -r requirements.txt` (bölüm 4)
- [ ] `pip show foundry-local-sdk` → `Version: 1.x` (bölüm 4.2)
- [ ] `python scripts\doctor.py` → "Her sey yolunda gorunuyor." (bölüm 5)
- [ ] `python -m app.cli ingest` (bölüm 6)
- [ ] `python -m app.cli ask "Belge parcalama neden gerekli?"` (bölüm 6)
- [ ] `winget install Microsoft.FoundryLocal` **gerekmiyor** (bölüm 7)

---

## 1. Ön koşullar

| Gereksinim | Zorunlu değer | Nasıl kontrol edilir | Karşılanmazsa |
|---|---|---|---|
| İşletim sistemi | Windows 10 22H2+ veya Windows 11 | `winver` | Yükselt. |
| Mimari | 64-bit (x64 veya ARM64) | `echo $env:PROCESSOR_ARCHITECTURE` | 32-bit Python ile SDK wheel'i kurulamaz. |
| RAM | ~8 GB | `systeminfo \| findstr /C:"Total Physical Memory"` | 8 GB altında iki modeli aynı anda tutmak zorlaşır. |
| Boş disk | ~3 GB | `Get-PSDrive C` | Modeller + çalışma zamanı sığmaz. |
| İnternet | Sadece ilk çalıştırmada | — | Katalog ve model dosyaları ilk kullanımda ağdan çekilir. |
| Terminal | Windows Terminal önerilir | — | Eski `conhost` penceresi Türkçe karakterlerde sorun çıkarabilir. |

`echo $env:PROCESSOR_ARCHITECTURE` çıktısının okunuşu:

| Çıktı | Anlamı |
|---|---|
| `AMD64` | Normal 64-bit Intel/AMD makine. Beklenen durum. |
| `ARM64` | Snapdragon/ARM Windows. Desteklenir. |
| `x86` | 32-bit süreç. Terminal veya Python 32-bit; bölüm 3'te 64-bit kur. |

### Hangi terminali kullanmalıyım

Bu rehberdeki komutlar **PowerShell** içindir. Windows 11'de varsayılan olarak
gelen Windows Terminal'i kullan; Windows 10'daysan Microsoft Store'dan kur.

Eski `cmd.exe` de çalışır, ama iki komut farklıdır:

| İş | PowerShell | cmd.exe |
|---|---|---|
| Sanal ortamı aç | `.venv\Scripts\Activate.ps1` | `.venv\Scripts\activate.bat` |
| Ortam değişkeni ata | `$env:FRAG_TOP_K = "6"` | `set FRAG_TOP_K=6` |

Rehberde PowerShell biçimini kullanacağım.

### "Tamamen çevrimdışı" ne demek

Proje internete çıkmadan cevap üretir; sorular ve belgeler cihazdan çıkmaz. Ama bu
**ilk çalıştırmadan sonra** geçerli: model kataloğu ve model dosyaları ilk kullanımda
ağdan indirilir. Sunum yapacaksan indirmeleri önceden yap.

### Hızlandırma nasıl çalışıyor

Windows'ta hızlandırma, makinendeki donanıma göre Foundry Local tarafından seçilir:
NVIDIA GPU'da CUDA, Snapdragon X makinelerde NPU, hiçbiri yoksa CPU. Bu seçimi
SDK'nın `download_and_register_eps()` çağrısı yapar
(`src/foundry_rag/backends/foundry.py`, `_ensure_manager()` içinde).

Bu, macOS'tan **anlamlı biçimde farklı** bir noktadır ve iki sonucu vardır:

1. **Windows'ta execution provider indirmesi gerçek iş yapar.** macOS'ta bu çağrı
   çoğunlukla boşa döner (hızlandırma WebGPU üzerinden gider), o yüzden kod hatayı
   ölümcül saymaz. Windows'ta ilk çalıştırmada burada birkaç yüz MB inebilir.
2. **macOS'un CPU zorlama kuralı Windows'ta uygulanmaz.** Kod şunu yapar:

   ```python
   # src/foundry_rag/backends/foundry.py
   def _embedding_device_default() -> str:
       if platform.system() == "Darwin" and platform.machine() == "arm64":
           return "cpu"
       return "auto"
   ```

   Yani embedding modelinin GPU varyantını bilerek atlayan kural **yalnızca Apple
   Silicon içindir**. Windows'ta varsayılan `auto`'dur ve varyantı Foundry Local
   seçer. macOS dokümanındaki "embedding'de `-generic-cpu` görmen normaldir" notu
   burada geçerli değil.

Yine de güvenlik ağı yerinde duruyor: `embed()` içindeki `_is_non_finite_failure()`
kontrolü platformdan bağımsızdır. Windows'ta da bir varyant Inf/NaN üretirse tek
seferlik CPU'ya geçilir.

---

## 2. Windows'un `python` tuzağı

Bu, Windows'taki **1 numaralı tuzak**. macOS'un eski Python'u nasıl bir tuzaksa
(bkz. [SETUP_MACOS.md](SETUP_MACOS.md) bölüm 2), Windows'un da kendine özgü bir
tanesi var — ama sebebi tamamen farklı.

Windows Python ile **gelmez**. Buna rağmen temiz bir Windows 11'de `python`
yazdığında bir hata almazsın; Microsoft Store açılır:

```powershell
PS> python
# Microsoft Store penceresi açılır, "Python 3.x" ürün sayfası gösterilir
```

Sebebi: Windows, `python.exe` ve `python3.exe` adında **App Execution Alias**
(uygulama yürütme takma adı) kısayolları kurar. Bunlar gerçek yorumlayıcı değil,
Store'a yönlendiren 0 baytlık saplamalardır.

Bunun neden önemli olduğu şurada ortaya çıkıyor: bu saplamalar `PATH`'te
gerçek Python kurulumundan **önce** gelebilir. O zaman şu senaryo oluşur:

1. Python'u kurarsın, çalışır.
2. Bir gün `python` komutu yine Store'u açar.
3. `pip install` çalıştırırsın, "komut bulunamadı" ya da yanlış ortama kurulum alırsın.

### Çözüm: `py` başlatıcısını kullan

Python'un Windows kurulumu `py.exe` adında bir **başlatıcı** (launcher) getirir.
`py`, saplamalardan etkilenmez ve hangi sürümü istediğini açıkça söylemene izin verir:

```powershell
py -0        # kurulu tüm Python sürümlerini listele
py -3.12 -V  # 3.12'yi çağır
```

Bu rehberde sanal ortamı **her zaman `py -3.12` ile** kuracağız. Sanal ortam bir kez
kurulduktan sonra içindeki `python` komutu doğrudan doğru yorumlayıcıya gider, yani
saplama sorunu ortadan kalkar.

### İstersen saplamaları kapat

Zorunlu değil, ama ileride kafa karışıklığını önler:

**Ayarlar → Uygulamalar → Gelişmiş uygulama ayarları → Uygulama yürütme takma adları**
→ `python.exe` ve `python3.exe` satırlarını **kapat**.

### Kural

> Bu proje için sanal ortamı **her zaman** `py -3.12 -m venv .venv` ile kur.
> Çıplak `python -m venv` yazma; hangi yorumlayıcıya gittiği garanti değil.

### SDK sürüm tuzağı burada da geçerli

macOS dokümanındaki 0.x/1.x karışıklığı Windows'ta da aynen vardır, çünkü sebebi
işletim sistemi değil pip'in kendisidir: pip, sürümleri `requires_python` alanına
göre filtreler. Python 3.10 veya altındaysan `pip install foundry-local-sdk`
**hata vermez**, sessizce bir yıllık `0.5.1` sürümünü kurar.

| | 0.x (eski) | 1.x (güncel, bu proje) |
|---|---|---|
| pip paket adı | `foundry-local-sdk` | `foundry-local-sdk` (aynı) |
| import edilen modül | `foundry_local` | `foundry_local_sdk` |
| Python gereksinimi | herhangi | **>= 3.11** |
| Nasıl çalışır | HTTP istemcisi, PATH'te `foundry` CLI gerekir | süreç içi, CLI gerekmez |
| API | tamamen farklı | tamamen farklı |

Windows'ta 3.9 gibi eski bir sürümü kazara kullanmak macOS'taki kadar kolay değil
(Windows eski bir Python dayatmıyor), ama makinede başka bir projeden kalma 3.10
varsa aynı sonuca varırsın. Bölüm 4.2'deki doğrulamayı atlama.

---

## 3. Python 3.12 kurulumu ve sanal ortam

### 3.1 Python 3.12'yi kur

```powershell
winget install Python.Python.3.12
```

**Neden 3.12?** SDK'nın alt sınırı 3.11, ama numpy 2.5 artık 3.11'i desteklemiyor.
3.12 iki tarafı da karşılayan tatlı nokta.

`winget` yoksa (eski Windows 10) [python.org/downloads](https://www.python.org/downloads/)
adresinden 64-bit yükleyiciyi indir. Yükleyicide **"Add python.exe to PATH"**
kutusunu işaretle.

Kurulumdan sonra **terminali kapat ve yeniden aç** — `PATH` değişikliği açık
pencerelere yansımaz. Sonra doğrula:

```powershell
py -0
```

Beklenen çıktının biçimi (sürümler makinene göre değişir, listede `3.12` **olmalı**):

```
 -V:3.12 *        Python 3.12 (64-bit)
 -V:3.11          Python 3.11 (64-bit)
```

`py: command not found` alıyorsan başlatıcı kurulmamış demektir; python.org
yükleyicisini "Repair" ile çalıştırıp **"py launcher"** kutusunu işaretle.

### 3.2 Sanal ortamı oluştur

Proje kökünde çalış:

```powershell
cd $HOME\Desktop\foundry-local-rag
py -3.12 -m venv .venv
```

`py -3.12` yazmamızın sebebi bölüm 2: çıplak `python` komutu Store saplamasına
ya da başka bir sürüme gidebilir.

### 3.3 PowerShell script izni — Windows'un 2 numaralı tuzağı

Şimdi ortamı açmayı dene:

```powershell
.venv\Scripts\Activate.ps1
```

Muhtemelen bunu alacaksın:

```
.venv\Scripts\Activate.ps1 cannot be loaded because running scripts is
disabled on this system. For more information, see about_Execution_Policies
at https://go.microsoft.com/fwlink/?LinkID=135170.
    + CategoryInfo          : SecurityError: (:) [], PSSecurityException
    + FullyQualifiedErrorId : UnauthorizedAccess
```

**Bu bir arıza değil.** Windows'un varsayılan PowerShell yürütme ilkesi
`Restricted`'dır: hiçbir script çalışmaz. Sanal ortam etkinleştirme dosyası da bir
script olduğu için engellenir.

Kalıcı çözüm (yalnızca kendi kullanıcın için, yönetici gerekmez):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

`RemoteSigned` ne demek: **yerel olarak yazdığın** scriptler çalışır, internetten
indirilenler imza ister. Kendi makinende geliştirme yapmak için makul ve yaygın
ayardır. `Unrestricted` yapma, gerek yok.

Onayla ve tekrar dene:

```powershell
Get-ExecutionPolicy -Scope CurrentUser
# RemoteSigned

.venv\Scripts\Activate.ps1
```

Yürütme ilkesini değiştiremiyorsan (kurumsal/okul makinesi olabilir) iki çıkış
yolu var:

```powershell
# a) Tek seferlik, yalnızca bu pencere için
powershell -ExecutionPolicy Bypass -File .venv\Scripts\Activate.ps1

# b) cmd.exe kullan, .bat dosyası ilkeye takılmaz
.venv\Scripts\activate.bat
```

### 3.4 Doğrula

Bu üç komut da beklenen çıktıyı vermeli:

```powershell
python -V
# Python 3.12.x

Get-Command python | Select-Object -ExpandProperty Source
# C:\Users\<kullanici>\Desktop\foundry-local-rag\.venv\Scripts\python.exe

python -c "import platform, sys; print(platform.machine(), sys.version_info[:2])"
# AMD64 (3, 12)
```

`Get-Command python` hâlâ `WindowsApps` içinde bir yol gösteriyorsa (`...\Microsoft\
WindowsApps\python.exe`) ortam **açılmamış** ve bölüm 2'deki saplamaya bakıyorsun.
Etkinleştirmeyi tekrar dene.

Prompt'un başında `(.venv)` görüyorsan hazırsın.

### 3.5 Her yeni terminalde

Sanal ortam terminal oturumuna bağlıdır. Yeni bir sekme açtığında:

```powershell
cd $HOME\Desktop\foundry-local-rag
.venv\Scripts\Activate.ps1
```

Bu rehberdeki bundan sonraki her `python` / `pip` komutu, ortam **açıkken**
çalıştırılacak. `.venv\` klasörü `.gitignore` içinde, repoya girmez.

### 3.6 Uzun yol (long path) sınırı

Windows'un klasik `MAX_PATH` sınırı 260 karakterdir. Model önbelleği derin bir
klasör ağacıdır, ve projeyi zaten derin bir yola klonladıysan (`C:\Users\<uzun ad>\
OneDrive\Belgeler\Okul\Yaz Okulu\...`) sınıra yaklaşabilirsin.

İki önlem, en ucuzu ilki:

1. **Projeyi kısa bir yola klonla.** `C:\dev\foundry-local-rag` gibi. Bu rehberdeki
   `$HOME\Desktop\...` yolu da genelde yeterince kısadır.
2. **Uzun yol desteğini aç** (yönetici PowerShell, bir kez, yeniden başlatma ister):

   ```powershell
   New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
     -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
   ```

> **OneDrive uyarısı.** Masaüstü/Belgeler klasörün OneDrive ile eşitleniyorsa,
> `.venv` ve model önbelleği buluta yüklenmeye çalışılır: yavaşlar, kotanı yer ve
> "dosya kullanımda" hataları çıkarabilir. Projeyi OneDrive dışında bir yere
> (`C:\dev\`) koymak en temizi.

---

## 4. Bağımlılıkların kurulumu

### 4.1 Kur

```powershell
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

### 4.2 1.x sürümünü doğrula

Bu adımı **atlama**. Bölüm 2'nin sonundaki tuzağın kapandığını burada kanıtlıyorsun.

```powershell
pip show foundry-local-sdk
```

Beklenen (ara sürüm değişebilir, **`1.` ile başlaması** şart):

```
Name: foundry-local-sdk
Version: 1.2.3
Location: C:\Users\<kullanici>\Desktop\foundry-local-rag\.venv\Lib\site-packages
```

`Version: 0.5.1` görüyorsan Python 3.11'in altındasın. Bölüm 3'e dön.

Modülün gerçekten import edilebildiğini de kontrol et:

```powershell
python -c "from foundry_local_sdk import Configuration, FoundryLocalManager; print('SDK 1.x tamam')"
# SDK 1.x tamam
```

Eski paketin ortamda **olmadığını** doğrula:

```powershell
python -c "import foundry_local" 2>&1 | Select-Object -Last 1
# ModuleNotFoundError: No module named 'foundry_local'
```

Bu `ModuleNotFoundError` **iyi haber**. Eski 0.x kuşağı ortamda yok demek.

### 4.3 Türkçe çıktı için UTF-8

Proje Türkçe metinle çalışır. Dosya okuma tarafında sorun yok — `pipeline.py`
belgeleri açıkça `encoding="utf-8"` ile okur. Riskli olan tek yer **çıktıyı
yönlendirmek**:

```powershell
python -m app.cli ask "RAG nedir?" > cevap.txt
```

Konsola yazarken Python Windows'ta Unicode'u doğrudan konsola verir ve sorun
çıkmaz. Ama çıktıyı bir dosyaya veya boruya yönlendirdiğinde konsol devreden
çıkar ve **sistemin yerel kod sayfası** devreye girer:

| Windows dil ayarı | Kod sayfası | Türkçe karakterler |
|---|---|---|
| Türkçe | `cp1254` | Sorunsuz — `ı ğ ş İ Ö Ü Ç` bu tabloda var |
| İngilizce / çoğu diğer dil | `cp1252` | **Patlar** — `ı`, `ğ`, `ş` bu tabloda yok |

Yani hata, Windows'un dili Türkçe *değilse* çıkar — ki okul ve kurum
makinelerinde en yaygın durum budur:

```
UnicodeEncodeError: 'charmap' codec can't encode character 'ı' ...
```

Tek satırlık kalıcı çözüm — Python'un UTF-8 modunu aç:

```powershell
$env:PYTHONUTF8 = "1"
```

Her oturumda yazmamak için PowerShell profiline ekle:

```powershell
Add-Content $PROFILE '$env:PYTHONUTF8 = "1"'
```

---

## 5. `python scripts\doctor.py` çıktısını okumak

```powershell
python scripts\doctor.py
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

`doctor.py` **platform duyarlıdır**: mimari kuralını ve önerdiği düzeltme komutunu
çalıştığı işletim sistemine göre seçer (`architecture_status()` ve
`venv_setup_command()`). Windows'ta `AMD64` ve `ARM64` geçerli mimarilerdir; sana
Homebrew ya da Rosetta öneren bir satır **görmemelisin**. Görürsen bu bir
hatadır, bildir.

### Dört bölüm neyi kontrol eder

| Bölüm | Kontrol | Neden önemli |
|---|---|---|
| `--- Platform ---` | Mimari bu OS için desteklenenler arasında mı | 32-bit Python'da SDK wheel'i yok |
| `--- Python ---` | Sürüm >= 3.11, sqlite uzantı desteği | Bölüm 2'deki SDK tuzağı |
| `--- Paketler ---` | numpy, streamlit, SDK kuşağı (0.x mi 1.x mi) | Yanlış SDK'yı yakalar |
| `--- Foundry Local katalogu ---` | `chat_model` ve `embedding_model` alias'ları katalogda var mı | Alias'lar donanıma bağlı |

### Beklenen çıktı (doğru ortam)

Bölüm 3 ve 4'ü uyguladıktan sonra çıktının biçimi şöyle olmalı. Sürüm numaraları,
mimari ve katalog model sayısı makineden makineye değişir:

```
==============================================================
  Yerel RAG Asistani -- ortam kontrolu
==============================================================

--- Platform ---
  [ok]  islemci mimarisi: AMD64
  [ok]  isletim sistemi: Windows-11-10.0.22631-SP0

--- Python ---
  [ok]  python: 3.12.x (C:\Users\<kullanici>\...\.venv\Scripts\python.exe)
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

Katalog bölümü ilk çalıştırmada internet ister. Ağ yoksa `katalog bos dondu`
uyarısını görürsün.

`embedding modeli 'qwen3-embedding-0.6b': BULUNAMADI` yazıyorsa `doctor.py` altına
bu donanımda mevcut ilk 15 alias'ı basar. **Alias'lar donanıma bağlıdır ve
Windows'ta macOS'takinden farklı olabilir.** Listeye bakıp `FRAG_EMBEDDING_MODEL`
ile başka bir alias seçebilirsin (bkz. [.env.example](../.env.example)). Embedding
modelini değiştirirsen yeniden indekslemen gerekir.

---

## 6. İlk indeksleme ve ilk soru

### 6.1 Önce indirmeyi bil

İlk çalıştırmada model dosyaları ve donanımına uygun execution provider inecek.
Toplam **~1.3 GB** civarı bekle; kesin dağılım seçilen varyantlara göre değişir.

| Ne zaman iner | Ne iner |
|---|---|
| İlk `FoundryLocalManager.initialize()` | Donanımına uygun execution provider (CUDA / NPU / CPU) |
| `python -m app.cli ingest` sırasında | `qwen3-embedding-0.6b` |
| İlk `ask` / `chat` sırasında | `qwen2.5-0.5b` |

Sohbet modelinin `ingest` sırasında **inmemesi** normaldir:
`FoundryBackend._ensure_chat_client()` tembeldir, sohbet modelini ilk soruya kadar
yüklemez.

Modeller `%USERPROFILE%\.foundry_local_rag` altına iner (bkz. bölüm 8.2). Hiçbir
modelde EULA/lisans onay kapısı yok; hepsi MIT veya Apache-2.0.

> **Uyku moduna dikkat.** İndirme sürerken makine uykuya geçerse bozuk model
> önbelleği kalabiliyor ve önbellek bütünlük doğrulaması yok (açık hatalar:
> Foundry-Local #909, #906). İndirme bitene kadar makineyi uyanık tut. Bozulursa
> bölüm 8.2'deki temizlik adımını uygula.

### 6.2 İndeksle

```powershell
python -m app.cli ingest
```

Beklenen çıktının yapısı (`54 parca` bu depodaki 8 belge için gerçek değerdir;
varyant ve süre makinene göre değişir):

```
  Yerel RAG Asistani  --  Microsoft Foundry Local
  Belgelerinden cevap uretir, internete cikmaz.

Belge klasoru : C:\Users\<kullanici>\Desktop\foundry-local-rag\data\docs
Veritabani    : C:\Users\<kullanici>\Desktop\foundry-local-rag\data\rag.db
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

1. **`Backend: foundry-local`** yazıyor mu? `hashing-offline` yazıyorsa 6.6'ya bak.
2. **`dim=1024`** mü? `qwen3-embedding-0.6b` 1024 boyutlu vektör üretir. Bu değer
   koda gömülü değil; `FoundryBackend.embedding_dim` kısa bir metni embed edip ölçer.
3. **`embedding: ... [<cihaz> / <execution_provider>]`** satırı. Bu satır, hangi
   varyantın gerçekten seçildiğini söyleyen tek yerdir.

> **Açık hata: #858 / #895.** GPU execution provider doğru kaydolsa bile bazen
> yalnızca CPU varyantları görünüyor ve sessizce yavaş build çalışıyor. Fark
> etmenin tek yolu yukarıdaki satırı okumaktır; `describe_variant()` bu yüzden
> `load()` sonrası `model.id` ve `execution_provider` değerlerini yazdırıyor.
> NVIDIA GPU'lu bir makinede `[... / CPUExecutionProvider]` görüyorsan bu hataya
> denk gelmiş olabilirsin.

Varyantı elle zorlamak istersen:

```powershell
$env:FRAG_DEVICE = "gpu"    # ya da "cpu"
python -m app.cli ingest
```

### 6.3 İndeksi kontrol et

```powershell
python -m app.cli info
```

Foundry Local ile indekslediysen ilk iki meta satırı şöyle olmalı:

```
Meta:
  embedding_signature    foundry-local:qwen3-embedding-0.6b:1024
  backend                foundry-local
```

`embedding_signature` satırı önemli: `RagPipeline._check_index()` her açılışta bunu
şimdiki backend'in imzasıyla karşılaştırır. Ayrıntısı 6.5'te.

### 6.4 İlk soru

```powershell
python -m app.cli ask "Belge parcalama neden gerekli?"
```

İlk `ask` çağrısında sohbet modeli (`qwen2.5-0.5b`) inecek, bu yüzden ilk soru
sonrakilerden yavaştır.

Çıktının yapısı: önce cevap metni, sonra kaynaklar, sonra zamanlama, sonra
kaynaklılık denetimi:

```
<cevap metni> [06-belge-parcalama.md]

Kaynaklar:
  [1] 06-belge-parcalama.md > Neden Parcalama
      guven 0.612 | anlam 0.612 | kelime 11.40 | bulan: ikisi

  getirme: <n> ms | uretim: <n> sn

Kaynaklilik: %100 (2/2 cumle dayanakli)  [mod: generative]
```

Kaynak satırındaki dört sayı: `guven` cevap/reddetme kararında kullanılan skor,
`anlam` kosinüs benzerliği, `kelime` BM25 skoru, `bulan` ise parçayı hangi
aramanın getirdiği (`anlam` / `kelime` / `ikisi`).

Son blok `groundedness.py`'nin denetimidir: cevabın her cümlesi getirilen parçalara
karşı puanlanır, dayanağı olmayanlar `[!]` ile işaretlenir. Kapatmak için
`$env:FRAG_CHECK_GROUNDEDNESS = "0"`.

**`[mod: extractive-fallback]` görürsen bu bir hata değildir.** Varsayılan
`answer_mode="auto"` önce üretir, sonra kaynaklılığı ölçer; üretilen cevap kendi
bağlamı tarafından desteklenmiyorsa belgelerden doğrudan alıntıya düşer. Küçük
modeller Türkçede sık sık buna takılır — sebebi ve ölçümleri
[README](../README.md#5-kaynaklılık-denetimi-devre-kesici-olarak) ve
`src/foundry_rag/extractive.py` içinde.

Cevap yerine `Bu bilgi elimdeki belgelerde yok.` görebilirsin. Bu da bir hata
değil: hiçbir parça `min_similarity` eşiğini geçmemiştir ve `RagPipeline.answer()`
modeli hiç çağırmadan durur. Kasıtlı tasarım — model uydursun diye çağırmıyoruz.
Bunu çok sık görüyorsan 6.7'ye bak.

### 6.5 Backend değiştirirsen yeniden indeksle

En sık yapılan hata: `hashing` ile indeksleyip `foundry` ile soru sormak. Vektör
uzayları uyumsuz olduğu için `RagPipeline._check_index()` çalışmayı reddeder:

```
Indeks farkli bir embedding modeliyle olusturulmus.
  indekste: hashing-offline:512
  simdiki : foundry-local:qwen3-embedding-0.6b:1024
Vektor uzaylari uyumsuz. Yeniden indeksle:
  python -m app.cli ingest
```

Çözüm mesajın içinde. Bu bir arıza değil, kasıtlı bir koruma — aksi halde anlamsız
benzerlik skorları alırdın.

### 6.6 Foundry Local olmadan çalıştırmak

Varsayılan backend `auto`: Foundry Local erişilebilirse onu kullanır, değilse
görünür bir uyarıyla çevrimdışı yedeğe (`HashingBackend`) düşer:

```
[!] Foundry Local kullanilamiyor, cevrimdisi yedek backend'e gecildi.
    Sebep: <gercek sebep>
    Ayrinti icin: python scripts/doctor.py
```

| Değer | Davranış | Ne zaman |
|---|---|---|
| `auto` (varsayılan) | Foundry varsa onu kullan, yoksa yedeğe düş | İlk gün, kurulum sürerken |
| `foundry` | Foundry zorunlu, yoksa yüksek sesle hata ver | Kurulum bitince; sessiz bozulmayı önler |
| `hashing` | Her zaman çevrimdışı yedek | Test, CI, kurulum sorunlu makine |

```powershell
python -m app.cli --backend hashing ingest      # Foundry Local olmadan indeksle
python -m app.cli --backend foundry ask "..."   # sessiz düşüşü kapat, gerçek hatayı gör
```

`hashing` backend **semantik bir embedder değildir**: hash'lenmiş kelime ve karakter
n-gram'ları eşleştirir, cevabı da üretmez — en iyi eşleşen cümleleri alıntılar. Bu
kasıtlı bir taban çizgisidir ve **her platformda aynı sonucu verir**; CI'da ölçülen
değerler (33 soruluk set, `top_k=4`): Recall@4 %88.0, MRR 0.793, reddetme %100,
genel doğruluk %90.9.

### 6.7 Eşiği kendi makinende kalibre et

Bu, Windows'ta **atlanmaması gereken** adım.

`min_similarity` ne zaman cevap verileceğine karar verir. Doğru değeri korpusa,
retriever'a ve **embedding modelinin skor dağılımına** bağlıdır. Depoda ölçülmüş
iki değer var:

| Backend | Optimum `min_similarity` | Nerede ölçüldü |
|---|---|---|
| `hashing` | `0.30` (koddaki varsayılan) | Platformdan bağımsız |
| `foundry` | `0.40` | macOS arm64, `qwen3-embedding-0.6b` |

Windows'ta aynı alias farklı bir varyanta çözülebilir. Değeri tahmin etme, ölç:

```powershell
python eval\calibrate.py --backend foundry
```

Bu, 66 noktalık bir ızgarayı tarar ve takas eğrisiyle birlikte optimum noktayı
basar. Çıkan değeri ayarla:

```powershell
$env:FRAG_MIN_SIMILARITY = "0.40"   # calibrate.py ne dediyse o
```

Sonra ölç:

```powershell
python eval\evaluate.py --backend foundry
```

macOS referans sonucu: Recall@4 %96.0, MRR 0.960, reddetme %100, genel %97.0.
Seninki farklı çıkarsa bu bir arıza değil — farklı donanım, farklı varyant. Önemli
olan kalibrasyondan **sonraki** sayıdır.

### 6.8 Diğer çalıştırma yolları

```powershell
python -m app.cli chat                        # etkileşimli döngü, cevap akarak yazılır
python -m app.cli ask "soru" --no-sources     # kaynakları gizle
python -m app.cli --top-k 6 ask "soru"        # daha çok parça getir
streamlit run app\streamlit_app.py            # tarayıcı arayüzü
python -m pytest tests\ -q                    # testler, hepsi çevrimdışı
python eval\evaluate.py                       # sadece getirme metrikleri
```

`chat` içinden çıkmak için `q`, `quit`, `exit`, `cik` yazabilir ya da Ctrl-C
kullanabilirsin.

İlk `streamlit run` çalıştırmanda Windows Defender Güvenlik Duvarı ağ erişimi
sorabilir. **"Özel ağlar"** yeterlidir; uygulama yalnızca `localhost` dinler.

### 6.9 Cevap kalitesi hakkında dürüst not

`qwen2.5-0.5b` küçük bir modeldir ve **Türkçede zayıftır**. Kurulumun doğru
çalıştığını göstermeye yeter, ödev kalitesinde cevap beklemeyin. Daha iyi sonuç
için:

```powershell
$env:FRAG_CHAT_MODEL = "qwen3-1.7b"
```

Sohbet modelini değiştirmek yeniden indeksleme gerektirmez; indeks yalnızca
**embedding** modeline bağlıdır.

---

## 7. Foundry Local CLI kurmalı mıyım?

**Hayır.** Bu proje CLI olmadan çalışır. SDK 1.x çalışma zamanını kendi içinde
taşır ve çıkarımı süreç içinde (in-process) yapar; ayrı bir servis ya da PATH'te
`foundry` komutu gerekmez. `pip install -r requirements.txt` yeterlidir.

Yani şu **gerekmiyor**:

```powershell
winget install Microsoft.FoundryLocal   # bu proje için gerekli değil
```

Bunu bilmek önemli, çünkü internetteki birçok örnek 0.x kuşağına ait ve orada CLI
zorunluydu. `foundry model run ...` ile başlayan bir eğitim izliyorsan, eski
kuşağa bakıyorsun demektir.

CLI'yi başka bir sebeple kurarsan zararı yok — sadece bu projenin ona ihtiyacı
olmadığını bil. Depodaki `app_name` ayrımı sayesinde iki taraf birbirinin model
önbelleğini de bozmaz (bölüm 8.2).

---

## 8. Kurulumu geri alma

Sıfırdan başlamak ya da diski boşaltmak için. Sırayla uygula.

### 8.1 Sanal ortamı sil

```powershell
deactivate                 # ortam açıksa
Remove-Item -Recurse -Force .venv
```

Bu, `pip install` ile gelen her şeyi (SDK dahil) siler. `.venv\` zaten
`.gitignore` içinde, repo etkilenmez.

`Remove-Item` "dosya kullanımda" derse hâlâ açık bir Python süreci vardır; tüm
terminalleri ve `streamlit` süreçlerini kapat.

### 8.2 Model önbelleğini ve çalışma zamanını sil

Foundry Local önbelleği **`app_name`'e göre ayırır.** Bu projenin `app_name`
değeri `foundry_local_rag`'dir (`backends/foundry.py` içinde sabit), dolayısıyla
bu projenin indirdiği her şey ev dizinindeki `.foundry_local_rag` klasörü
altındadır — yani `C:\Users\<kullanici>\.foundry_local_rag`. Gözünle görmek için:

```powershell
explorer "$env:USERPROFILE\.foundry_local_rag"
```

| Alt klasör | İçerik |
|---|---|
| `cache\models\` | İndirilen model dosyaları (GB'larca olabilir) |
| `ep\` | Execution provider kütüphaneleri |
| `logs\` | Günlük dosyaları |

`.foundry` adında ayrı bir klasör de görebilirsin: başka bir `app_name` kullanan bir
araç (ya da `foundry` CLI'ı) onu oluşturur. **Bu projenin modelleri orada
değildir**, o yüzden sadece onu silmek diski boşaltmaz.

Önce ne kadar yer kapladığına bak, sonra sil:

```powershell
"{0:N0} MB" -f ((Get-ChildItem "$env:USERPROFILE\.foundry_local_rag" -Recurse -File |
  Measure-Object Length -Sum).Sum / 1MB)

Remove-Item -Recurse -Force "$env:USERPROFILE\.foundry_local_rag"
```

**Sadece bozuk modelleri temizlemek** istiyorsan (uyku modu kaynaklı bozulma —
Foundry-Local #909 / #906) tamamını silmene gerek yok:

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.foundry_local_rag\cache\models"
```

Bir sonraki çalıştırmada modeller yeniden iner. Önbellek bütünlük doğrulaması
olmadığı için, "model yükleniyor ama tuhaf davranıyor" durumunda ilk denenecek
şey budur.

### 8.3 Proje verilerini sil

```powershell
Remove-Item -Force data\rag.db, eval\results.jsonl -ErrorAction SilentlyContinue
```

İndeks yeniden üretilebilir; `python -m app.cli ingest` ile geri gelir. Bu dosyalar
`.gitignore` içindedir.

`data\docs\` klasörünü **silme** — bilgi tabanının kaynağı orası.

### 8.4 İsteğe bağlı: Python 3.12'yi kaldır

```powershell
winget uninstall Python.Python.3.12
```

Başka projelerin de kullanıyor olabileceğini unutma.

### 8.5 Tam sıfırlama, tek blok

```powershell
cd $HOME\Desktop\foundry-local-rag
deactivate
Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue
Remove-Item -Force data\rag.db, eval\results.jsonl -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:USERPROFILE\.foundry_local_rag" -ErrorAction SilentlyContinue
```

Sonra bölüm 3'ten devam et.

---

## Sık karşılaşılan hatalar

Windows'a özgü olanlar önce, ortak olanlar sonra.

| Belirti | Sebep | Çözüm |
|---|---|---|
| `python` yazınca Microsoft Store açılıyor | App Execution Alias saplaması | Bölüm 2 — `py -3.12` kullan |
| `Activate.ps1 cannot be loaded ... scripts is disabled` | PowerShell `Restricted` ilkesi | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (bölüm 3.3) |
| `Get-Command python` → `...\WindowsApps\python.exe` | Sanal ortam açık değil | `.venv\Scripts\Activate.ps1` |
| `py: command not found` | Başlatıcı kurulmamış | python.org yükleyicisi → Repair → "py launcher" |
| `UnicodeEncodeError: 'charmap' codec` | Çıktı yönlendirilirken kod sayfası | `$env:PYTHONUTF8 = "1"` (bölüm 4.3) |
| Yol/dosya adı hataları, "path too long" | `MAX_PATH` 260 sınırı | Bölüm 3.6 |
| `.venv` yavaş, "dosya kullanımda" | OneDrive eşitlemesi | Projeyi OneDrive dışına taşı (bölüm 3.6) |
| `Remove-Item` "dosya kullanımda" diyor | Açık Python/streamlit süreci | Terminalleri kapat, tekrar dene |
| `pip show` → `Version: 0.5.1` | Python 3.11'in altında kurulmuş | Bölüm 2 sonu, bölüm 3 |
| `ModuleNotFoundError: No module named 'foundry_local_sdk'` | Eski 0.x kurulu veya SDK hiç kurulu değil | Bölüm 3-4 |
| `Backend: hashing-offline` yazıyor | `auto` yedeğe düştü | `--backend foundry` ile gerçek sebebi gör, sonra `doctor.py` |
| `Indeks farkli bir embedding modeliyle olusturulmus` | Backend veya embedding modeli değişti | `python -m app.cli ingest` |
| `Veritabani bos. Once belgeleri indeksle` | Hiç indeksleme yapılmamış | `python -m app.cli ingest` |
| Sürekli `Bu bilgi elimdeki belgelerde yok.` | Eşik bu embedding modeline göre yüksek | `python eval\calibrate.py` (bölüm 6.7) |
| `[mod: extractive-fallback]` | Üretilen cevap kaynaklı değildi, alıntıya düşüldü | Kasıtlı davranış; daha büyük model dene (6.9) |
| NVIDIA GPU var ama `CPUExecutionProvider` | Açık hata #858 / #895 | Çalışır ama yavaştır; `$env:FRAG_DEVICE = "gpu"` dene |
| Cevap yazıldıktan sonra `IndexError` | Streaming döngüsü son boş chunk'ta patlıyor (#905) | Bu depoda korumalı: `if not chunk.choices: continue` |
| Model yüklendi ama tuhaf davranıyor | İndirme sırasında uyku → bozuk önbellek (#909 / #906) | Bölüm 8.2'deki `cache\models` temizliği |
| `katalog bos dondu` | İlk çalıştırmada internet yok | Ağa bağlan |
| Streamlit'te ikinci `initialize()` çökmesi | SDK singleton'ı iki kez başlatılıyor | Bu depoda korumalı: `if FoundryLocalManager.instance is None` |

Daha ayrıntılı vaka analizleri: [TROUBLESHOOTING.md](TROUBLESHOOTING.md). Oradaki
komutlar macOS biçimindedir; `brew install python@3.12 && ... source
.venv/bin/activate` gördüğün her yerde bu rehberin bölüm 3'ündeki Windows
karşılığını uygula. Sebep-sonuç analizleri platformdan bağımsızdır.

---

## Kurulum sonrası kontrol listesi

- [ ] `python -V` → `3.12.x`
- [ ] `Get-Command python` → `...\.venv\Scripts\python.exe`
- [ ] `pip show foundry-local-sdk` → `Version: 1.x`
- [ ] `python scripts\doctor.py` → `Her sey yolunda gorunuyor.`
- [ ] `python -m pytest tests\ -q` → tüm testler geçti
- [ ] `python -m app.cli ingest` → `Backend: foundry-local (... dim=1024)`
- [ ] `python -m app.cli info` → `Parca : 54`, `Belge : 8`
- [ ] `python -m app.cli ask "..."` → cevap + `Kaynaklar:` bloğu
- [ ] `python eval\calibrate.py --backend foundry` → kendi eşiğini ölçtün
- [ ] `streamlit run app\streamlit_app.py` → tarayıcı arayüzü açılıyor

Hepsi işaretliyse kurulum tamam.
