# Hafta 6 -- Dokümantasyon, Kod Temizliği ve Final Sunumu

**Faz 3: Kapanış** | Yaz okulu, tam zamanlı

Bu hafta **yeni özellik yazılmaz**. Elindeki sistem ne kadar iyiyse o kadardır; bu
haftanın işi onu başkasının anlayabileceği, çalıştırabileceği ve değerlendirebileceği
hale getirmektir.

Yaz okulunun sonunda notunu belirleyen şey, tek başına çalışan bir kod değil; şu
zincirin tamamıdır:

```
çalışan kod  ->  ölçülmüş sonuç  ->  okunabilir depo  ->  anlaşılır sunum
```

Zincirin herhangi bir halkası kopuksa geri kalanı görünmez olur. Kimse çalıştıramadığı
bir projeyi değerlendiremez; kimse ölçmediğin bir iyileştirmeye inanmaz.

Bu haftanın sonunda elinde şunlar olacak:

- Doldurulmuş bir **proje raporu / README**
- Temizlenmiş, testleri geçen bir **kod tabanı**
- GitHub'a itilmiş, `.gitignore`'u doğru bir **depo**
- Provası yapılmış **10 dakikalık sunum** ve **canlı demo**

---

## 1. Ön koşullar

Hafta 1-5'te kurduğun ortam ayakta olmalı.

```bash
cd ~/Desktop/foundry-local-rag
source .venv/bin/activate

python --version              # 3.11 veya üstü olmalı
python scripts/doctor.py      # ortam kontrolü
python -m pytest tests/ -q    # 163 test, hepsi geçmeli
python -m app.cli info        # indekste kaç parça / kaç belge var?
```

`python --version` çıktısı `3.9.6` diyorsa venv aktif değildir. Foundry Local SDK 1.x
**Python >= 3.11** ister; Python 3.9'da `pip install foundry-local-sdk` hata vermeden
eski **0.5.1** sürümünü kurar ve modül adı `foundry_local_sdk` yerine `foundry_local`
olur. Çözüm: `brew install python@3.12`, ardından yeni bir venv.

> **Kod dondurma (code freeze).** Bu haftanın ilk günü itibarıyla yeni özellik
> eklemeyi bırak. Sadece şu üç şey serbest: hata düzeltme, silme, dokümantasyon.
> Sunumdan bir gün önce yazılan "küçük bir iyileştirme" canlı demoyu bozan şeyin ta
> kendisidir.

---

## 2. Haftanın önerilen takvimi

| Gün | İş | Çıktı |
| --- | --- | --- |
| 1 | Kod dondurma, temizlik kontrol listesi (Bölüm 4) | `pytest` yeşil, ölü kod silinmiş |
| 2 | Rapor / README yazımı (Bölüm 3) | `README.md` bütün başlıkları dolu |
| 3 | Git düzeni, GitHub'a itme, CI'ın yeşil olması (Bölüm 5) | Depo linki hazır |
| 4 | Sunum slaytları + demo provası (Bölüm 6 ve 7) | Süre tutulmuş en az 2 prova |
| 5 | Final sunumları | Rubriğe göre değerlendirme (Bölüm 8) |

---

## 3. Proje raporu / README şablonu

Rapor ayrı bir dosya olmak zorunda değil. Bu projede rapor = deponun `README.md`
dosyasıdır. Sebebi basit: iki ayrı dosya tutarsan biri mutlaka eskir.

### 3.1 Sekiz zorunlu başlık

| Başlık | Cevaplaması gereken soru | En sık hata |
| --- | --- | --- |
| Problem | Bu yazılım olmasa kim, hangi işi nasıl yapıyor? | Teknolojiyle başlamak ("RAG yaptık") |
| Çözüm | Sistem kullanıcıya ne veriyor? | Özellik listesi yazıp faydayı atlamak |
| Mimari | Veri hangi sırayla nereden geçiyor? | Kutu çizip dosya adı vermemek |
| Kurulum | Sıfır makinede kaç komutla ayağa kalkar? | Kendi makinesinde çalışan ama yazılmamış adımlar |
| Kullanım | Tipik üç komut nedir? | Sadece `--help` çıktısını yapıştırmak |
| Ölçümler | Ne kadar iyi? Neye göre? | Sayı vermeden "iyi çalışıyor" demek |
| Sınırlar | Ne zaman çalışmaz? | Bu bölümü hiç yazmamak |
| Öğrenilenler | Baştan başlasan neyi değiştirirdin? | "Çok şey öğrendik" cümlesi |

### 3.2 Doldurulacak şablon

Aşağıdaki bloğu kendi deponun `README.md` dosyasına kopyala ve köşeli parantezli
yerleri doldur. Doldurmadığın satırı **sil**, boş bırakma.

```markdown
# [Proje adı]

[Tek cümlelik tanım: kime, ne yapıyor. En fazla 25 kelime.]

[Ekran görüntüsü veya 5 satırlık örnek çıktı.]

---

## Problem

[Hangi somut ihtiyaç? Kim, şu anda bu işi nasıl yapıyor ve neresi zahmetli?
2-4 cümle. Teknoloji adı geçmesin.]

[Neden düz bir LLM sohbeti yetmiyor: model senin belgelerini bilmiyor ve
bilmediğinde uyduruyor. Neden internete çıkan bir servis yetmiyor: belgeler
cihazdan çıkmamalı.]

## Çözüm

[Kullanıcı ne yapıyor, karşılığında ne alıyor? 3-5 madde.]

- Belgeler `[klasör]` içine konur.
- `[komut]` ile indekslenir.
- `[komut]` ile soru sorulur; cevap **kaynak göstererek** gelir.
- Cevap belgelerde yoksa sistem uydurmaz: "[reddetme cümlesi]" der.

## Mimari

[Akış şeması: soru -> embedding -> vektör arama -> bağlam -> LLM -> cevap]

| Katman | Dosya | Sorumluluk |
| --- | --- | --- |
| Ayarlar | `src/.../config.py` | [ ] |
| Parçalama | `src/.../chunking.py` | [ ] |
| Depolama | `src/.../store.py` | [ ] |
| Getirme | `src/.../retrieval.py` | [ ] |
| İstem | `src/.../prompts.py` | [ ] |
| Boru hattı | `src/.../pipeline.py` | [ ] |
| Model erişimi | `src/.../backends/` | [ ] |
| Arayüz | `app/` | [ ] |

**Tasarım kararları ve gerekçeleri:**

| Karar | Alternatif | Neden bu seçildi |
| --- | --- | --- |
| [ ] | [ ] | [ ] |
| [ ] | [ ] | [ ] |
| [ ] | [ ] | [ ] |

## Kurulum

**Gereksinimler:** [işletim sistemi + mimari], Python [sürüm], [disk], [RAM]

```bash
[komut 1]
[komut 2]
[komut 3]
```

Kurulum doğrulama:

```bash
[doğrulama komutu]     # beklenen çıktı: [ ]
```

## Kullanım

```bash
[indeksleme komutu]
[tek soru komutu]
[etkileşimli komut]
```

Ayarlar: [ortam değişkeni öneki] ile geçersiz kılınır. Tam liste: `[dosya]`.

| Ayar | Varsayılan | Ne işe yarar |
| --- | --- | --- |
| [ ] | [ ] | [ ] |

## Ölçümler

Değerlendirme seti: **[N] soru** ([X] cevaplanabilir + [Y] cevaplanamaz).

```bash
[getirme ölçümü komutu]        # ör. python eval/evaluate.py --backend [B]
[kalibrasyon komutu]           # ör. python eval/calibrate.py --backend [B]
```

**Karşılaştırma tablosu.** En az iki satır zorunlu: bir taban çizgisi ve bir değişiklik.

| Yapılandırma | Recall@K | MRR | Reddetme doğruluğu | Dengeli skor | Genel doğruluk | Ort. süre |
| --- | --- | --- | --- | --- | --- | --- |
| [taban çizgisi] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [değişiklik 1] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [değişiklik 2] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

**Eşik kalibrasyonu.** Eşiği tahmin etmediğini göster: ızgara taramasının birkaç
satırını ve seçtiğin noktayı yaz.

| `lexical_scale` | `min_similarity` | Recall | Reddetme | Genel | Dengeli |
| --- | --- | --- | --- | --- | --- |
| [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| [ ] | **[seçilen]** | [ ] | [ ] | [ ] | **[ ]** |
| [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

Seçim ölçütü: [hangi metrik? neden?]. Seçilen değerler: `FRAG_MIN_SIMILARITY=[ ]`,
`FRAG_LEXICAL_SCALE=[ ]`.

**Kaynaklılık (cevap denetimi).** [Doğru bir cevapta yüzde kaç? Kasten bozulmuş bir
cevapta yüzde kaç?]

| Girdi | Kaynaklılık | Dayanaksız cümle |
| --- | --- | --- |
| [gerçek cevap] | [ ] | [ ] |
| [uydurma cevap] | [ ] | [ ] |

**Kalite kapısı.** `[kapı komutu]` CI'da çalışıyor; eşikler: Recall >= [ ],
reddetme >= [ ], genel >= [ ]. Altına düşerse derleme kırılır.

[Tablodan çıkan tek cümlelik sonuç. Hangi değişiklik işe yaradı, hangisi yaramadı?]

## Sınırlar

- [Ne zaman yanlış cevap verir?]
- [Hangi donanımda çalışmaz?]
- [Hangi ölçekte yavaşlar?]
- [Hangi dil / belge türü desteklenmiyor?]
- [Eşzamanlı kullanıcı desteği var mı?]

## Öğrenilenler

- [Beklediğinden zor çıkan şey ve neden]
- [Ölçünce yanlış olduğu anlaşılan varsayım]
- [Baştan başlasan farklı yapacağın tek şey]

## Lisans

[ ]
```

### 3.3 Bu depodaki karşılıkları

Şablonu doldururken kendi deponu okumadan yazma. Bu projede kaynak şunlar:

| Şablon bölümü | Nereden alınır |
| --- | --- |
| Mimari tablosu | `docs/ARCHITECTURE.md` ve `src/foundry_rag/` modül docstring'leri |
| Kurulum | `docs/SETUP_MACOS.md`, `requirements.txt`, `scripts/doctor.py` |
| Kullanım / ayarlar | `src/foundry_rag/config.py` (`Settings`) ve `.env.example` |
| Ölçümler | `eval/questions.json`, `eval/evaluate.py`, kendi `eval/results.jsonl` kayıtların |
| Sınırlar | README "Gereksinimler ve sınırlar" + "Bilinen üst-akış hataları" |

Bu deponun ölçülmüş sonuçları (çevrimdışı `hashing` backend, `top_k=4`):

| Yapılandırma | Recall@4 | MRR | Reddetme doğruluğu | Genel doğruluk |
| --- | --- | --- | --- | --- |
| Yalnız vektör, eşik `0.15` (`FRAG_HYBRID=0`) | %72.0 | 0.650 | %87.5 | %75.8 |
| Hibrit + kalibre eşik `0.30` (varsayılan) | %88.0 | 0.793 | %100.0 | %90.9 |

Kendi tablona bu iki satırı **karşılaştırma zemini** olarak koy. Tek bir satırlık
tablo hiçbir şey anlatmaz; iki satır olduğu anda anlatmaya başlar.

> `eval/results.jsonl` dosyası `.gitignore` içindedir, yani GitHub'a gitmez.
> Rapora girecek sayıları oradan **elle** markdown tablosuna taşı. Sunumdan sonra
> "sayılar bilgisayarımda kalmış" diyecek durumda olma.

---

## 4. Kod temizliği kontrol listesi

Sıra önemli: önce sil, sonra yeniden adlandır, sonra yorum yaz. Ters sırada
yaparsan sileceğin kodu güzelleştirmiş olursun.

### 4.1 Debug print'lerini kaldır

Her `print` kötü değildir. Ayrım şu:

| Meşru | Kaldırılmalı |
| --- | --- |
| `app/` katmanındaki kullanıcı çıktısı (`app/cli.py`) | `src/foundry_rag/` içine serpiştirilmiş `print(x)` |
| `verbose` bayrağına bağlı ilerleme satırı (`pipeline.py` içindeki `Embedding: n/m` satırı) | `print("buraya geldi")`, `print(vector[:5])` |
| Kullanıcının bilmesi **zorunlu** uyarı (`backends/__init__.py`, `auto` yedeğe düşerken `stderr`'e yazan blok) | Yorum satırına alınmış eski `print`'ler |

Aramak için:

```bash
grep -rn "print(" src/foundry_rag/
grep -rn "TODO\|FIXME\|XXX\|HACK" src app tests eval scripts
grep -rn "breakpoint()\|import pdb" src app tests eval scripts
```

`src/foundry_rag/` altında `verbose` koşuluna bağlı olmayan bir `print` görüyorsan
ya sil ya da bayrağın arkasına al. Kütüphane katmanı ekrana kendi başına yazmaz.

`backends/__init__.py` içindeki yedeğe düşme uyarısı bilerek koşulsuzdur ve bilerek
`stderr`'e gider: kullanıcının istediğinden çok daha zayıf bir modelle cevap almış
olması asla sessiz kalmamalıdır. Bu, "gereksiz print" değil, bir güvenlik kararıdır.

### 4.2 Fonksiyon ve değişken isimleri

Kurallar:

- Fonksiyon adı **fiil**, veri adı **isim**: `chunk_document()`, `search()`,
  `encode_vector()` / `settings`, `hits`, `matrix`.
- Boolean isim bir soruya cevap versin: `grounded`, `answerable`, `refused`, `hit`.
  `flag`, `check`, `status2` değil.
- Kısaltma kullanma; istisna: alanın standart terimleri (`vec`, `emb`, `db`, `idx`)
  ve tek satırlık kapsamdaki döngü değişkenleri (`i`, `r`).
- `_` ile başlayan ad "bu modülün dışından çağrılmaz" demektir. `_import_sdk()`,
  `_batched()`, `_tail_overlap()` böyle. Dışarıdan çağırdığın bir `_` fonksiyonu
  varsa ya adı yanlış ya tasarım.
- Aynı kavrama iki isim verme. Bu depoda getirilen parça her yerde `hit`, kaydedilmiş
  parça her yerde `record`. Yarısına `result` deseydin okuyucu ikisini ayırt edemezdi.

Kontrol:

```bash
grep -rn "def " src/foundry_rag/ | wc -l      # kaç fonksiyon var?
grep -rn "def \(tmp\|test2\|foo\|bar\|helper\|process\|handle\)" src app
```

`process()` veya `handle()` gibi bir ad görürsen: bu fonksiyon *neyi* işliyor?
Cevabı ada yaz.

### 4.3 Yorum kalitesi: "ne" değil "neden"

Kodun ne yaptığını kod söyler. Yorum, **koda bakarak anlaşılamayacak** olanı söyler:
alternatifin neden reddedildiğini, hangi hatanın etrafından dolanıldığını, hangi
varsayımın geçerli olduğunu.

Kötü (kodu tekrar ediyor):

```python
# vektörü normalize et
vector = vector / norm
```

İyi (bu depodan, `src/foundry_rag/retrieval.py`, `search()` docstring'i):

> Eşik önemlidir: eşik olmasaydı, külliyatta cevabı olmayan bir soru bile "en az kötü"
> parçaları döndürür, model de onlardan bir cevap uydururdu. Hiçbir şey döndürmemek
> boru hattının "bilmiyorum" diyebilmesini sağlar.

İyi (bu depodan, `src/foundry_rag/backends/foundry.py`, streaming döngüsü):

```python
# The final chunk can arrive with an empty `choices` list. Microsoft's
# own tutorial indexes into it unguarded and crashes with IndexError
# right after printing the answer (Foundry-Local issue #905, open,
# reproduced on macOS arm64 + WebGPU + SDK 1.2.3). Skip such chunks.
if not getattr(chunk, "choices", None):
    continue
```

Bu yorum olmasa, altı ay sonra biri "bu kontrol gereksiz" deyip silerdi ve hata geri
gelirdi. Yorumun işi tam olarak budur.

Yorum yazarken sorulacak tek soru: **"Bu satırı silmek isteyen birini durdurur mu?"**
Durdurmuyorsa yorum değil, gürültüdür.

Kontrol listesi:

- [ ] Her modülün başında ne işe yaradığını söyleyen bir docstring var.
- [ ] Public fonksiyonların docstring'i var; `_` ile başlayanların tek satırı yeter.
- [ ] Sıra dışı görünen her satırın yanında **neden** öyle yazıldığı yazıyor
      (örnek: `store.py` içindeki float32 uyarısı, `chunking.py` içindeki başlık öneki
      gerekçesi).
- [ ] Kodu tekrar eden yorum kalmadı.
- [ ] Yorumdaki iddialar hâlâ doğru. Kod değişip yorum kalmışsa yorum artık yalandır.

### 4.4 Ölü kod

Ölü kod, testi olmayan ve çağrılmayan koddur. Silmekten çekinme: git'te duruyor.

```bash
# hiç çağrılmayan fonksiyonları elle tara
grep -rn "def " src/foundry_rag/ | sed 's/.*def \([a-zA-Z_][a-zA-Z0-9_]*\).*/\1/' | sort -u

# her ad için: tanımı dışında geçiyor mu?
grep -rn "fonksiyon_adi" src app tests eval scripts
```

Silinecekler:

- Yorum satırına alınmış kod blokları (git zaten tutuyor).
- Kullanılmayan `import`'lar.
- Hiçbir yerden çağrılmayan fonksiyon ve sınıflar.
- Bir deneme için eklenip geri alınmayan ayarlar ve bayraklar.
- `data/` altında unutulmuş deneme veritabanları ve `docs/` altında yarım dosyalar.

Sözdizimi ve import kontrolü, ek paket kurmadan:

```bash
python -m compileall -q src app tests eval scripts
python -c "import foundry_rag, foundry_rag.pipeline, foundry_rag.backends"
```

İsteğe bağlı olarak bir linter kurabilirsin (bu projenin bağımlılıklarında yoktur):

```bash
pip install ruff
ruff check .
```

### 4.5 Tutarlı biçimlendirme

Tek kural: **depo kendi içinde tutarlı olsun.** Bu depoda geçerli olanlar:

| Konu | Bu depodaki karar |
| --- | --- |
| Girinti | 4 boşluk |
| Satır uzunluğu | ~95 karakter civarı |
| Dize tırnağı | çift tırnak |
| Import sırası | stdlib -> üçüncü parti -> yerel; her grup arasında boş satır |
| `from __future__ import annotations` | her modülün başında |
| Tip ipuçları | public fonksiyonlarda zorunlu |
| Kod dili | İngilizce (kod, docstring); kullanıcıya görünen metinler Türkçe |
| Bölüm ayırıcı | `# -- bölüm adı ---...` biçiminde yorum satırı |

Dosyaların sonunda tek bir yeni satır olsun, sonda boşluk kalmasın:

```bash
grep -rn " $" src app tests | head        # satır sonu boşlukları
```

### 4.6 Testler geçiyor

```bash
python -m pytest tests/ -q                 # 163 test
python -m app.cli --backend hashing ingest
python -m app.cli --backend hashing info
python -m app.cli --backend hashing ask "Kosinüs benzerliği nedir?"
python eval/evaluate.py --backend hashing --no-save --gate
python scripts/doctor.py
```

Bu altı komut, `.github/workflows/ci.yml` içindeki CI adımlarının aynısıdır. Yerelde
geçiyorsa CI'da da geçer. Testler `hashing` backend ile çalışır: çevrimdışıdır, model
indirmez ve deterministiktir.

Bir test kırıldıysa iki seçeneğin var: kodu düzelt ya da testin yanlış olduğunu
**gerekçesiyle** yaz. Testi silmek üçüncü seçenek değildir.

### 4.7 Teslim öncesi son kontrol

- [ ] `git status` temiz.
- [ ] `python -m pytest tests/ -q` -- 163 test geçiyor.
- [ ] `src/` altında `verbose` bayrağına bağlı olmayan debug `print` yok.
- [ ] `TODO` / `FIXME` kalmadı (ya da hepsi README "Sınırlar" bölümünde yazılı).
- [ ] Kullanılmayan import ve fonksiyon yok.
- [ ] Her modülün başında docstring var.
- [ ] Temiz bir klonda kurulum adımları baştan sona çalışıyor (Bölüm 5.7).

---

## 5. Git / GitHub temel akışı

Sunumdan önce kodun GitHub'da olmalı. Aşağısı bu proje için gereken minimumdur.

### 5.1 Tek seferlik kurulum

```bash
git config --global user.name  "Ad Soyad"
git config --global user.email "eposta@ornek.com"

cd ~/Desktop/foundry-local-rag
git init                       # zaten bir depoysa bu adımı atla
git add -A
git commit -m "İlk sürüm: çalışan RAG boru hattı"
```

### 5.2 Günlük döngü

```bash
git status                     # ne değişti?
git diff                       # tam olarak ne değişti?
git add src/foundry_rag/prompts.py
git commit -m "Sistem isteminde reddetme kuralını netleştir"
git log --oneline              # geçmişi gör
```

`git add -A` yerine dosya adı vermeyi alışkanlık edin. `-A` ile ne eklediğini
görmeden commit atarsan bir gün 250 MB'lık veritabanını da eklersin.

### 5.3 Dal (branch)

`main` her zaman çalışır durumda kalır. Riskli her iş dalda yapılır:

```bash
git switch -c hafta6-dokumantasyon    # yeni dal aç ve geç
# ... değişiklikler ...
git add -A && git commit -m "README ölçüm tablosunu doldur"

git switch main                       # ana dala dön
git merge hafta6-dokumantasyon        # birleştir
git branch -d hafta6-dokumantasyon    # dalı sil
```

Sunum sabahı `main` üzerinde deneme yapma. Demo `main`'den çalıştırılır.

### 5.4 GitHub'a itme

```bash
git remote add origin https://github.com/<kullanici>/<depo>.git
git push -u origin main
```

İlk `push`'tan sonra `git push` yeter. CI (`.github/workflows/ci.yml`) her `push` ve
her pull request'te otomatik çalışır: Python **3.9** ve **3.12** üzerinde testleri,
CLI'ı, eval setini ve `doctor.py`'yi koşturur. 3.9 kasıtlıdır -- macOS'un sistem
Python'u odur ve çekirdek kütüphane orada da import edilebilmelidir.

GitHub'daki "Actions" sekmesinde yeşil tik yoksa sunuma girme.

### 5.5 `.gitignore`: depoya girmeyecekler

Kural: **yeniden üretilebilen veya gizli olan hiçbir şey depoya girmez.**

| Girmez | Neden |
| --- | --- |
| `data/*.db`, `data/*.db-wal`, `data/*.db-shm` | `python -m app.cli ingest` ile yeniden üretilir; ayrıca embedding'ler backend'e özeldir |
| `foundry_local_data/`, `.foundry/` | Model önbelleği, gigabaytlarca; GitHub dosya başına 100 MB'ı reddeder |
| `.venv/`, `venv/`, `env/` | Makineye özgü; `requirements.txt` zaten var |
| `__pycache__/`, `*.pyc` | Derleme çıktısı |
| `.pytest_cache/`, `.ruff_cache/`, `.coverage` | Araç önbelleği |
| `.env` | Kişisel ayarlar ve sırlar; şablonu `.env.example` olarak paylaşılır |
| `eval/results.jsonl` | Ölçüm günlüğü; makineye ve koşuya özel |
| `.DS_Store` | macOS artığı |

Bu deponun `.gitignore` dosyası bunları zaten içerir. Kendi bilgi tabanını
`data/mydocs/` altına koyduysan ve gizli belgeler varsa, onu da ekle.

### 5.6 Yanlışlıkla eklediysen

Bir dosyayı commit'ledikten sonra takipten çıkarmak:

```bash
git rm --cached data/rag.db
echo "data/*.db" >> .gitignore
git commit -m "Veritabanını takipten çıkar"
```

Dosya diskte kalır, sadece git'ten düşer. Ancak **geçmişten silinmez**: eskiden
push edilmiş büyük bir dosya deponun boyutunda kalmaya devam eder. Bu yüzden
`.gitignore` en baştan doğru olmalıdır.

Bir sır (API anahtarı, parola) push edildiyse: dosyayı silmek yetmez, **sırrı iptal
et**. Push edilen sır sızmış sayılır.

### 5.7 Temiz klon testi

Sunumdan önce mutlaka yap. Kendi makinende çalışması hiçbir şey kanıtlamaz.

```bash
cd /tmp
git clone https://github.com/<kullanici>/<depo>.git klon-testi
cd klon-testi
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/doctor.py
python -m app.cli --backend hashing ingest
python -m app.cli --backend hashing ask "RAG nedir?"
```

Buradaki her hata, jürinin karşılaşacağı hatadır. README'yi bu testin sonucuna göre
düzelt.

---

## 6. Sunum yapısı -- 10 dakika

Toplam **10 dakika**. Süre tutulur. Aşağıdaki dağılım pazarlık konusu değil: en
büyük dilim demoya ayrılmıştır, çünkü jüriyi ikna eden şey çalışan yazılımdır.

| Süre | Bölüm | İçerik | Slayt |
| --- | --- | --- | --- |
| 0:00-1:00 | **Problem** | Kim, hangi işi, neden zahmetli yapıyor. Neden düz LLM ve neden bulut servis yetmiyor. | 1-2 |
| 1:00-3:00 | **Mimari** | Tek akış şeması + dosya adları. En fazla 3 tasarım kararı ve gerekçesi. | 3-4 |
| 3:00-7:00 | **Canlı demo** | Bölüm 7'deki üç senaryo, bu sırayla. | yok (terminal) |
| 7:00-9:00 | **Ölçümler** | Eval seti, metrikler, en az iki satırlık karşılaştırma tablosu, bir başarısızlık örneği. | 5-6 |
| 9:00-10:00 | **Öğrenilenler** | Beklenmedik zorluk, yanlış çıkan varsayım, baştan başlasan ne değiştirirdin. | 7 |

Toplam **7 slayt yeter**. Slayt sayısı arttıkça anlatım kalitesi düşer.

### 6.1 Bölüm bölüm ne söylenir

**Problem (1 dk).** İlk cümlede teknoloji adı geçmesin.

> "Ders notlarımız sekiz markdown dosyasında dağınık duruyor. Bir soruyu cevaplamak
> için hangi dosyada olduğunu hatırlamak gerekiyor. Bulut tabanlı bir asistan bu
> notları kendi sunucusuna yüklemek zorunda; biz notların cihazdan çıkmasını
> istemiyoruz."

**Mimari (2 dk).** Tek şema. Her kutunun altında dosya adı olsun:

```
data/docs/*.md
   -> chunk_document()    chunking.py    başlık duyarlı, örtüşmeli parçalar
   -> backend.embed()     backends/      her parça -> vektör
   -> add_chunks()        store.py       SQLite, float32 BLOB
soru
   -> backend.embed()     backends/      soru -> vektör
   -> hybrid_search()     retrieval.py   kosinüs + BM25, RRF, top_k=4, eşik 0.30
   -> build_messages()    prompts.py     5 kurallı sistem istemi + bağlam
   -> backend.chat()      backends/      yerel LLM
   -> cevap + kaynaklar
```

Anlatılacak en fazla üç karar. Öneri:

1. **Neden `Backend` soyutlaması var?** Aynı boru hattı hem Foundry Local hem
   `hashing` ile çalışıyor; testler model indirmeden koşuyor
   (`src/foundry_rag/backends/base.py`).
2. **Neden vektörler float32 BLOB olarak saklanıyor?** JSON yerine ham bayt: küçük
   ve tek `numpy` çağrısıyla geri okunuyor. Yazarken float32, okurken float64
   kullanırsan sessizce çöp elde edersin (`store.py`).
3. **Neden `min_similarity` eşiği var ve neden veriden seçildi?** Eşiksiz bir
   sistem, cevabı olmayan soruda "en az kötü" parçaları döndürür ve model
   uydurur (`retrieval.py`, `hybrid_search()`). Eşik tahmin edilmedi;
   `eval/calibrate.py` ızgara taramasıyla seçildi.

**Ölçümler (2 dk).** Tek tablo, en az iki satır. Ardından **bir başarısızlık örneği**:
sistemin yanlış cevapladığı gerçek bir soru ve sebebine dair hipotezin. Kendi
hatasını gösteren ekip, hepsini gizleyen ekipten daha güvenilir görünür.

**Öğrenilenler (1 dk).** Üç madde, her biri tek cümle. "Çok şey öğrendik" cümlesi
kurma; somut ol:

> "Parça boyutunu küçültmenin getirmeyi otomatik iyileştireceğini varsaymıştık;
> ölçtüğümüzde Recall düştü, çünkü cevap iki parçaya bölünüyordu."

---

## 7. Canlı demo senaryosu

Demo 4 dakikadır ve **üç şey zorunludur**. Sırayı değiştirme: (a) sistemin çalıştığını,
(b) dürüst olduğunu, (c) gerçekten yerel olduğunu bu sırayla kanıtlar.

### 7.1 Demo öncesi hazırlık (sunumdan önceki gün)

- [ ] Modeller indirilmiş ve önbellekte. İlk çalıştırmada sohbet + embedding modeli
      birlikte yaklaşık **1.3 GB** indirir, ayrıca ~146 MB yerel kütüphane. Bunu
      sahnede yapma.
- [ ] `python -m app.cli ingest` en az bir kez Foundry backend ile koşmuş; `info`
      çıktısında `embedding_signature` dolu.
- [ ] Soracağın soruları **yaz ve dene**. Doğaçlama soru sorma.
- [ ] Terminal yazı tipi büyütülmüş (en az 18 punto), pencere tam ekran.
- [ ] Bildirimler kapalı, ekran koruyucu kapalı.
- [ ] Plan B hazır: `--backend hashing` ile aynı üç senaryonun ekran kaydı.

> **Uyarı.** "Çevrimdışı" ifadesi **ilk çalıştırmadan sonrası** için geçerlidir.
> Katalog ve model dosyaları ilk kullanımda ağdan çekilir. Wi-Fi'ı kapatmadan önce
> modellerin önbellekte olduğundan emin ol.

### 7.2 (a) Cevaplanabilir soru + kaynak gösterimi

```bash
python -m app.cli ask "Kosinüs benzerliği nasıl hesaplanır?"
```

Beklenen çıktının yapısı (`app/cli.py`, `cmd_ask` ve `_print_sources`):

```
<cevap metni, iddiaların sonunda [dosya-adi.md] biçiminde kaynak>

Kaynaklar:
  [1] 03-embedding-ve-vektor-arama.md > <bölüm>
      guven 0.xxx | anlam 0.xxx | kelime x.xx | bulan: ikisi
  [2] ...

  getirme: xx ms | uretim: x.xx sn

Kaynaklilik: %100 (3/3 cumle dayanakli)
```

Ekranda **göstererek** söylenecekler:

1. Cevabın içindeki köşeli parantezli kaynak: bu, sistem isteminin 3. kuralının
   sonucudur (`src/foundry_rag/prompts.py`).
2. `Kaynaklar` listesi ve skorlar: `guven` cevap/reddetme kararında kullanılan
   skor, `anlam` kosinüs benzerliği, `kelime` BM25 skoru, `bulan` parçayı hangi
   aramanın getirdiği. Cevabın nereden geldiği denetlenebilir.
3. Süre satırı: getirme milisaniye, üretim saniye mertebesinde. Darboğaz modeldir,
   arama değil.
4. `Kaynaklilik` satırı: `groundedness.py` cevabın her cümlesini getirilen
   parçalara karşı puanlar; dayanaksız cümleler `[!]` ile işaretlenir.

Ardından kaynak dosyayı aç ve cevabın gerçekten orada yazdığını göster. Bu tek hareket,
"uydurmuyor" iddianı slayttan daha iyi kanıtlar.

### 7.3 (b) Cevaplanamaz soru + "bilmiyorum" davranışı

```bash
python -m app.cli ask "Mercimek çorbası tarifi nedir?"
```

Beklenen:

```
Bu bilgi elimdeki belgelerde yok.
```

Kaynak listesi **basılmaz**, çünkü eşiği geçen parça yoktur.

Anlatılacak: bu cümle modelden gelmiyor olabilir. İki savunma katmanı var:

| Katman | Nerede | Ne yapar |
| --- | --- | --- |
| 1. Eşik | `retrieval.py` -> `hybrid_search()`, `min_similarity=0.30` | Hiçbir parça eşiği geçmezse boş liste döner |
| 2. Boru hattı | `pipeline.py` -> `RagPipeline.answer()` | Hit yoksa modeli hiç çağırmaz, `NO_CONTEXT_ANSWER` döndürür |
| 3. İstem | `prompts.py` -> `SYSTEM_PROMPT` 2. kural | Parça geldiği hâlde cevap yoksa modele reddetmesini söyler |

Sahnede hangi katmanın devreye girdiğini söyle. Kaynak listesi hiç basılmadıysa 1. ve
2. katman; kaynak basıldığı hâlde "belgelerde yok" dendiyse 3. katman çalışmıştır.

Sonra ölçüme bağla: değerlendirme setindeki 33 sorunun **8'i kasıtlı olarak
cevaplanamaz**. Reddetme doğruluğu deponun varsayılan yapılandırmasında
**%100.0** (kalibre edilmemiş yalnız-vektör hâlinde %87.5 idi). Bu, "bazen
bilmiyorum diyor" değil, ölçülmüş bir davranıştır.

### 7.4 (c) İnterneti kapat, aynı soruları tekrarla

```bash
# 1) Wi-Fi'ı kapat (menü çubuğundan, ekranda görünsün)
# 2) Bağlantının gerçekten gittiğini göster
ping -c 2 example.com          # hata vermeli

# 3) Aynı iki soruyu tekrarla -- backend'i açıkça foundry ver
python -m app.cli --backend foundry ask "Kosinüs benzerliği nasıl hesaplanır?"
python -m app.cli --backend foundry ask "Mercimek çorbası tarifi nedir?"
```

**Neden `auto` değil `foundry`?** `auto` modunda Foundry Local başlatılamazsa sistem
sessizce `hashing` yedeğine düşer (uyarı `stderr`'e basılır) ve bu durumda indeks
imzası uyuşmadığı için şu hatayı alırsın:

```
Indeks farkli bir embedding modeliyle olusturulmus.
```

Yani `auto` ile demo yaparsan, gerçekte hangi modelin cevap verdiğini kanıtlayamazsın.
`--backend foundry` "Foundry Local zorunlu, yoksa yüksek sesle patla" demektir; canlı
demoda istediğin davranış budur.

`-v` bayrağı yüklenen modeli ve execution provider'ı yazdırır. Bayrak **alt komuttan
önce** gelmelidir:

```bash
python -m app.cli --backend foundry -v ask "Kosinüs benzerliği nasıl hesaplanır?"
```

Söylenecek cümle:

> "Ağ kapalı. Aynı sorular aynı cevapları veriyor. Model `qwen2.5-0.5b` ve
> `qwen3-embedding-0.6b` bu makinede, süreç içinde çalışıyor; ne belgeler ne sorular
> cihazdan çıkıyor."

Demo bitince Wi-Fi'ı geri açmayı unutma.

### 7.5 Demo kural listesi

- [ ] Komutlar bir dosyaya önceden yazılmış, kopyala-yapıştır ile çalıştırılıyor.
- [ ] Demo sırasında kod düzenlenmiyor.
- [ ] Terminal geçmişi temiz (`clear`), önceki denemeler görünmüyor.
- [ ] Her komuttan önce ne beklediğini **söyle**, sonra çalıştır. Sessiz bekleyiş
      izleyiciyi kaybettirir.
- [ ] Bir şey patlarsa: 20 saniyeden fazla uğraşma, ekran kaydına geç, sunuma devam et.
- [ ] Model ilk kez indiriliyorsa demo başarısızdır. Önceden indir.

---

## 8. Değerlendirme rubriği (100 puan)

| Kategori | Puan |
| --- | --- |
| Çalışırlık | 30 |
| Ölçüm ve değerlendirme | 20 |
| Kod kalitesi | 20 |
| Dokümantasyon | 15 |
| Sunum | 15 |
| **Toplam** | **100** |

### 8.1 Çalışırlık -- 30 puan

| Seviye | Puan | Ölçüt |
| --- | --- | --- |
| Yetersiz | 0-11 | Temiz klonda kurulum tamamlanmıyor ya da `ingest` hata veriyor. Demo yapılamadı. |
| Gelişmekte | 12-18 | Sadece `hashing` backend ile çalışıyor. Foundry Local hiç ayağa kalkmadı. Bazı komutlar elle müdahale istiyor. |
| Yeterli | 19-25 | `ingest`, `ask`, `chat`, `info` çalışıyor. Foundry backend ile en az bir kez uçtan uca cevap üretilmiş. Cevaplar kaynak gösteriyor. |
| Örnek | 26-30 | Üç demo senaryosunun üçü de canlı ve sorunsuz. İnternet kapalıyken çalışıyor. Hatalı girdilerde (boş soru, boş indeks, uyumsuz imza) anlaşılır hata mesajı veriyor. Web arayüzü de ayakta. |

### 8.2 Ölçüm ve değerlendirme -- 20 puan

| Seviye | Puan | Ölçüt |
| --- | --- | --- |
| Yetersiz | 0-7 | Hiç ölçüm yok; "iyi çalışıyor" iddiası sayısız. |
| Gelişmekte | 8-12 | `evaluate.py` bir kez koşturulmuş, tek satır sonuç var. Cevaplanamaz sorular ele alınmamış. |
| Yeterli | 13-16 | En az iki yapılandırma karşılaştırılmış (örn. taban çizgisi ile `hashing`/`foundry` ya da farklı `top_k`). Recall@K, MRR ve reddetme doğruluğu birlikte raporlanmış. Sayılar tabloda. |
| Örnek | 17-20 | Üç veya daha fazla koşu, tek değişken değiştirilerek yapılmış. Sonuçlar yorumlanmış: hangi değişiklik neden işe yaradı/yaramadı. En az bir başarısız soru incelenip sebebi açıklanmış. Kendi bilgi tabanında da ölçüm var. |

### 8.3 Kod kalitesi -- 20 puan

| Seviye | Puan | Ölçüt |
| --- | --- | --- |
| Yetersiz | 0-7 | Testler kırık ya da hiç yok. Ölü kod, debug `print`'leri, yoruma alınmış bloklar duruyor. Her şey tek dosyada. |
| Gelişmekte | 8-12 | Testler geçiyor ama dosya ayrımı zayıf; isimler tutarsız; yorumlar kodu tekrar ediyor. |
| Yeterli | 13-16 | Tüm testler (bu depoda 145) geçiyor. Katmanlar ayrık (parçalama / depolama / getirme / istem / boru hattı / arayüz). İsimler tutarlı, ölü kod yok, `src/` içinde koşulsuz `print` yok. |
| Örnek | 17-20 | Yorumlar "neden"i açıklıyor (reddedilen alternatif, dolanılan hata). Hata mesajları çözümü de söylüyor. Yeni test eklenmiş. Kritik sınır durumları (boş belge, uyumsuz boyut, bozuk indeks) kodda yakalanıyor. CI yeşil. |

### 8.4 Dokümantasyon -- 15 puan

| Seviye | Puan | Ölçüt |
| --- | --- | --- |
| Yetersiz | 0-5 | README yok ya da tek paragraf. Kurulum adımları eksik. |
| Gelişmekte | 6-9 | Kurulum ve kullanım var ama temiz klonda takılıyor. Mimari ve sınırlar yazılmamış. |
| Yeterli | 10-12 | Sekiz başlığın hepsi dolu. Komutlar kopyalanınca çalışıyor. Ölçüm tablosu var. Sınırlar dürüstçe yazılmış. |
| Örnek | 13-15 | Temiz klon testi yapılmış ve README ona göre düzeltilmiş. Tasarım kararları gerekçeleriyle yazılı. Bilinen hatalar (üst-akış sorunları dâhil) ve geçici çözümleri belgelenmiş. `.env.example` güncel. |

### 8.5 Sunum -- 15 puan

| Seviye | Puan | Ölçüt |
| --- | --- | --- |
| Yetersiz | 0-5 | Süre aşıldı ya da yarısı kullanılamadı. Demo yok. Slayt okunuyor. |
| Gelişmekte | 6-9 | Süre kabaca tutuyor ama demo kayıttan. Sorulara cevap verilemiyor. Problem tanımı teknolojiyle başlıyor. |
| Yeterli | 10-12 | 10 dakika içinde bitiyor. Üç demo senaryosundan en az ikisi canlı. Ölçümler gösteriliyor. Ekip üyelerinin katkısı belli. |
| Örnek | 13-15 | Süre dakikası dakikasına tutuyor. Üç senaryo da canlı, internet kapatma dâhil. Bir başarısızlık örneği kendi isteğiyle gösteriliyor. Jüri sorularına kod üzerinden cevap veriliyor. |

---

## 9. Sık yapılan sunum hataları

| Hata | Neden olur | Ne yap |
| --- | --- | --- |
| Modeli sahnede indirmek | İlk çalıştırma denenmemiştir; ~1.3 GB indirme başlar | Bir gün önce `ingest` çalıştır, önbelleği doldur |
| `--backend auto` ile demo | Foundry patlarsa sessizce `hashing`'e düşer, sonra imza hatası gelir | Demoda `--backend foundry` kullan |
| Wi-Fi'ı kapatıp ilk kez çalıştırmak | Katalog ilk kullanımda ağdan çekilir | Önce ağ açıkken bir kez çalıştır, sonra kapat |
| Kurulum adımlarını anlatmakla 4 dakika harcamak | Slaytlar kurulum ekran görüntüleriyle dolu | Kurulum README'de; sunumda tek cümle |
| Mimariyi kutu çizip dosya adı vermeden anlatmak | Şema soyut kalır, kodla bağı kurulmaz | Her kutunun altına dosya adı yaz |
| Sayı vermeden "iyi çalışıyor" demek | Ölçüm yapılmamıştır | Recall@K / MRR / reddetme doğruluğu tablosu göster |
| Tek satırlık ölçüm tablosu | Karşılaştırma zemini yok | En az iki satır: taban çizgisi + değişiklik |
| Doğaçlama soru sormak | "Şunu da deneyelim" refleksi | Soruları önceden yaz ve dene |
| Hata çıkınca 3 dakika debug etmek | Panik | 20 saniye kuralı: kayda geç, devam et |
| Slaytı okumak | Provasızlık | Slaytta en fazla 6 satır; anlatım sende |
| Sınırları gizlemek | "Zayıf görünürüz" korkusu | Sınırlarını bilen ekip daha güvenilirdir |
| Tek kişinin konuşması | Rol dağıtılmamıştır | Her üyeye bir bölüm ver, geçişleri prova et |
| Süreyi provasız tahmin etmek | "10 dakika uzun" sanısı | Kronometreyle en az iki tam prova |
| Sunumdan bir saat önce kod değiştirmek | "Küçük bir düzeltme" | Kod dondurma kuralına uy |

---

## 10. Haftanın çıktı kriteri

Aşağıdakilerin hepsi sağlanmalı:

- [ ] `README.md` içinde sekiz başlığın (problem, çözüm, mimari, kurulum, kullanım,
      ölçümler, sınırlar, öğrenilenler) hepsi dolu.
- [ ] Ölçüm tablosunda en az **iki** yapılandırma satırı var ve sayılar kendi
      `eval/results.jsonl` koşularından geliyor.
- [ ] `python -m pytest tests/ -q` -- 163 test geçiyor.
- [ ] `src/foundry_rag/` altında `verbose` bayrağına bağlı olmayan debug `print` yok;
      `TODO` / `FIXME` kalmadı.
- [ ] Kod GitHub'da; `git status` temiz; Actions sekmesinde CI yeşil.
- [ ] `.gitignore` doğru: `data/*.db`, model önbelleği, `.venv/`, `.env` depoda değil.
- [ ] Temiz klon testi (`/tmp` altında klonlayıp kurma) baştan sona çalışıyor.
- [ ] Sunum en fazla 7 slayt ve kronometreyle **iki kez** prova edilmiş.
- [ ] Üç demo senaryosu (cevaplanabilir + cevaplanamaz + internet kapalı) sırasıyla
      denenmiş ve komutları bir dosyaya yazılmış.
- [ ] Plan B ekran kaydı hazır.

---

## 11. Yaz okulundan sonra

Bu depoyu bırakacaksan, bırakmadan önce README'nin "Sınırlar" bölümüne devam edecek
kişi için üç madde ekle. Bir sonraki adım için birkaç somut yön:

| Yön | Neden ilginç | Nereden başlanır |
| --- | --- | --- |
| Daha büyük sohbet modeli | `qwen2.5-0.5b` Türkçede zayıf; `qwen3-1.7b` (~1490 MB) veya `qwen3-4b` (~3083 MB) belirgin fark yaratır | `FRAG_CHAT_MODEL=qwen3-1.7b`, sonra aynı eval'i koştur |
| Sorgu genişletme / yeniden yazma | Kötü ifade edilmiş soru kötü sonuç verir; soruyu modelle yeniden yazmak recall'u artırabilir | `pipeline.py`, `RagPipeline.retrieve()` |
| Yeniden sıralama (re-rank) | Top-20 getirip ilk 4'ü modelle yeniden sıralamak MRR'ı yükseltir | `hybrid_search()` çağrısını iki aşamalı hale getir |
| Ölçek | Kaba kuvvet arama ~100 bin parçaya kadar uygundur | Yaklaşık en yakın komşu (ANN) indeksleri araştır |

Devam etmesen bile depoyu arşivleme: iş görüşmelerinde "çalıştırılabilir ve ölçülmüş"
bir proje, anlatılan on projeden değerlidir.
