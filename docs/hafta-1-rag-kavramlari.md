# Hafta 1 -- RAG Kavramları ve Yerel AI Kurulumu

**Faz 1: Temel Öğrenme** | Yaz okulu, tam zamanlı | Ön koşul: Python temelleri (fonksiyon, sınıf, sanal ortam), terminal kullanımı

Bu hafta iki iş yapılır: RAG'in ne olduğunu kavramsal olarak öğrenmek ve kendi makinenizde çalışan bir geliştirme ortamı kurmak. Hafta sonunda elinizde soru cevaplayabilen bir sistem olacak -- henüz gerçek bir dil modeli olmadan.

---

## 1. Öğrenme hedefleri

Hafta sonunda aşağıdakilerin hepsini yapabiliyor olmalısınız. Her madde ölçülebilir bir davranıştır, "anlamak" değildir.

- [ ] RAG'in üç adımını (retrieve, augment, generate) sırasıyla yazabilmek ve her adımın bu depodaki hangi fonksiyona karşılık geldiğini dosya adıyla birlikte söyleyebilmek.
- [ ] "Halüsinasyon" kelimesini, dil modelinin uydurma davranışını anlatan somut bir örnekle tanımlayabilmek ve bu depodaki hangi üç mekanizmanın (benzerlik eşiği, sistem istemi kuralı, kaynaklılık denetimi) buna karşı koyduğunu göstermek.
- [ ] RAG ile fine-tuning arasındaki üç farkı (maliyet, güncelleme kolaylığı, kaynak gösterebilme) sayabilmek.
- [ ] Projenin dört ayırt edici parçasını (Türkçe morfoloji, hibrit getirme, kaynaklılık denetimi, eşik kalibrasyonu) dosya adıyla eşleştirmek ve her birinin hangi hataya karşı durduğunu birer cümleyle söylemek.
- [ ] `ask` çıktısındaki `bulan:` etiketinin üç değerini (`anlam`, `kelime`, `ikisi`) hangi aramanın karşılığı olduğunu söylemek; sistemde iki ayrı getirme yöntemi çalıştığını fark etmek.
- [ ] macOS'ta Python 3.11+ sanal ortamı kurmak ve `python scripts/doctor.py` çıktısındaki her satırın ne anlama geldiğini açıklamak.
- [ ] Foundry Local'ın ne olduğunu ve bu projede neden `foundry` CLI'ının gerekmediğini açıklamak.
- [ ] `python -m app.cli --backend hashing ingest` ve `ask` komutlarını çalıştırıp çıktıdaki parça sayısı, benzerlik skoru ve kaynak satırlarını yorumlamak.
- [ ] `Backend` soyut sınıfının neden var olduğunu, "Foundry Local kurulu olmadan sistem nasıl çalışıyor?" sorusuna cevap vererek açıklamak.
- [ ] Bir belgeye bakıp 3 cevaplanabilir ve 2 cevaplanamaz soru üretmek; sistemin bu iki gruba verdiği farklı tepkiyi yazılı olarak karşılaştırmak.

---

## 2. Teorik içerik

### 2.1 RAG'in çözdüğü problem

Bir dil modeli, eğitim verisinde gördüğü bilgiyi ağırlıklarında taşır. Bunun üç doğrudan sonucu vardır:

| Sınır | Ne demek | RAG'in cevabı |
|---|---|---|
| Halüsinasyon | Model bilmediği konuda kendinden emin şekilde yanlış üretir | Cevabı üretmeden önce modele ilgili belge parçaları verilir |
| Bilgi kesme tarihi | Eğitim verisi belirli bir tarihte durur | Belgeler istem zamanında sunulur, model yeniden eğitilmez |
| Özel veri | Ders notunuz, şirket el kitabınız eğitim verisinde yoktur | Kendi belgeleriniz bilgi tabanı olur |

Bunlara bir dördüncüsü eklenir: **kaynak gösterme**. RAG, cevabın hangi dosyadan geldiğini söyleyebilir; saf bir dil modeli söyleyemez. Bu depoda her cevap `[01-rag-nedir.md]` biçiminde kaynak taşır.

Bu maddelerin uzun anlatımı `data/docs/01-rag-nedir.md` dosyasındadır. O dosya aynı zamanda sistemin bilgi tabanının bir parçasıdır -- yani bu hafta okuduğunuz metin, sisteme sorduğunuz sorunun cevabının kaynağıdır.

### 2.2 Retrieve -- Augment -- Generate

RAG kısaltması üç aşamanın baş harflerinden gelir. Bu depoda üçü de ayrı dosyalardadır:

| Adım | Ne yapar | Kod karşılığı |
|---|---|---|
| **Retrieve** (Getir) | Soruyu vektöre çevirir, bilgi tabanındaki en ilgili parçaları bulur | `RagPipeline.retrieve()` -> `src/foundry_rag/pipeline.py`, ardından `hybrid_search()` -> `src/foundry_rag/retrieval.py` |
| **Augment** (Zenginleştir) | Bulunan parçaları soruyla birlikte bir isteme paketler | `build_messages()` -> `src/foundry_rag/prompts.py` |
| **Generate** (Üret) | Dil modeli istemi okur ve cevabı yazar | `Backend.chat()` / `Backend.stream_chat()` -> `src/foundry_rag/backends/` |

Bunların ötesinde bir de **ingest** (indeksleme) akışı vardır ve sorgu akışından ayrıdır:

```
data/docs/*.md
   -> chunk_document()      src/foundry_rag/chunking.py    (900 karakter, 150 karakter örtüşme)
   -> backend.embed()       src/foundry_rag/backends/
   -> VectorStore.add_chunks()  src/foundry_rag/store.py   (data/rag.db, float32 BLOB)
```

İndeksleme yavaştır ve nadiren çalışır; sorgulama hızlıdır ve sürekli çalışır. `pipeline.py` bu ikisini bilerek ayırır -- ayırmasaydı uygulama her açılışta bütün belgeleri yeniden embedding'e sokardı.

Sorgu tarafında `RagPipeline.retrieve()` içinde olan tam olarak şudur:

1. `self.backend.embed([question])[0]` -> soru tek bir vektöre dönüşür.
2. `hybrid_search(...)` -> iki arama birlikte koşar: bütün vektörlerle kosinüs benzerliği (`retrieval.py`) ve BM25 kelime araması (`lexical.py`). İki sıralama RRF ile birleştirilir, en iyi 4 parça alınır ve güven skoru `min_similarity`'nin (varsayılan `0.30`) altında kalanlar atılır.

Arama, `numpy` ile kaba kuvvet matris çarpımıdır. Bu ölçekte (bu depoda 54 parça) tek haneli milisaniye sürer; bu yüzden özel bir vektör veritabanına gerek yoktur.

### 2.3 Halüsinasyon ve "bilmiyorum" diyebilmek

Bir RAG sisteminin en tehlikeli hatası, bilmediğini uydurmasıdır. Bu depo buna karşı **üç bağımsız savunma** kurar. İlk ikisi uydurmayı **önler**, üçüncüsü olan biteni **denetler**.

**Savunma 1 -- benzerlik eşiği (`min_similarity = 0.30`).** Getirme, hiçbir parça eşiği geçemezse boş liste döndürür. `RagPipeline.answer()` de boş listeyi görünce dil modelini hiç çağırmaz:

```python
# src/foundry_rag/pipeline.py  --  RagPipeline.answer()
if not hits:
    return Answer(
        question=question,
        text=NO_CONTEXT_ANSWER,
        hits=[],
        retrieval_seconds=retrieval_seconds,
        grounded=False,
    )
```

`NO_CONTEXT_ANSWER` değeri `"Bu bilgi elimdeki belgelerde yok."` sabitidir (`src/foundry_rag/prompts.py`).

Bu `0.30` sayısı tahmin değildir: `eval/calibrate.py` çalıştırılıp 33 soruluk değerlendirme seti üzerinde ölçülerek seçilmiştir. Öncesinde tahmin edilmiş bir `0.15` vardı. Ayrıntısı bölüm 2.5'te.

**Savunma 2 -- sistem istemi.** `prompts.py` içindeki `SYSTEM_PROMPT` beş kural içerir: (1) sadece BAĞLAM bölümünü kullan, (2) cevap bağlamda yoksa aynen "Bu bilgi elimdeki belgelerde yok." de, (3) her iddianın kaynağını köşeli parantezle belirt, (4) kısa yaz, (5) cevabı belirtilen dilde ver.

İkinci savunma birincisi başarısız olduğunda devreye girer: eşiği geçen ama aslında ilgisiz bir parça geldiğinde model yine de "bilmiyorum" diyebilmelidir.

**Savunma 3 -- kaynaklılık denetimi (`src/foundry_rag/groundedness.py`).** İlk iki savunma da modelin isteme uymasına güvenir. Uymazsa kimse fark etmez. Bu yüzden cevap üretildikten **sonra** her cümlesi, getirilen parçalarla karşılaştırılır ve desteklenmeyen cümleler işaretlenir. `RagPipeline.answer()` bunu `groundedness.check(text, hits)` ile çağırır; `Settings.check_groundedness` varsayılan olarak açıktır. `ask` çıktısında şu satır olarak görünür:

```
Kaynaklilik: %83 (5/6 cumle dayanakli) -- 1 cumle bağlamda doğrulanamadı
```

A1.4 alıştırmasında bu savunmaların nerede yeterli, nerede yetersiz kaldığını göreceksiniz.

### 2.4 Foundry Local nedir

Microsoft Foundry Local, dil modellerini bulut yerine kendi makinenizde çalıştıran bir çalışma zamanıdır. Bu projedeki rolü: embedding üretmek ve sohbet cevabı üretmek. İlk indirmeden sonra internet gerekmez.

macOS için doğrulanmış gerçekler:

| Konu | Durum |
|---|---|
| Donanım | **Yalnızca arm64 (Apple Silicon).** Intel Mac için hiçbir build yok. |
| İşletim sistemi | Minimum macOS 14.0 |
| Hızlandırma | ONNX Runtime **WebGPU** (Dawn -> Metal). CoreML **değil**, Apple Neural Engine **değil**. Aksini söyleyen bloglar yanıltıcıdır. |
| Python | SDK 1.x **Python >= 3.11** ister |
| CLI | SDK 1.x çalışma zamanını kendi içinde taşır -- **`foundry` CLI kurmaya gerek yoktur.** Bu proje CLI'sız çalışır. |

Bilinen tuzaklar (hepsi `src/foundry_rag/backends/foundry.py` ve `scripts/doctor.py` içinde dokümante edilmiştir):

- **1 numaralı tuzak:** Python 3.9'da `pip install foundry-local-sdk` hata vermez, sessizce eski **0.5.1** sürümünü kurar. 0.5.1'in modül adı `foundry_local`, güncel sürümünki `foundry_local_sdk`. API'leri tamamen farklıdır. `_import_sdk()` bu durumu tespit edip açık bir hata mesajı verir.
- `brew tap microsoft/foundrylocal` + `brew install foundrylocal`: tap yaklaşık 6 ay eskidir, v0.8.119 kurar. Bu sürüm embedding desteğinden (minFLVersion 1.1.0) öncedir, yani `qwen3-embedding-0.6b` modelini göremez. CLI gerçekten gerekiyorsa GitHub releases'teki `.pkg` kullanılır.
- `brew install foundry` **tamamen başka bir yazılım** kurar (Ethereum aracı).
- Sistem Python'unda `sqlite3` uzantı yükleyemez (`enable_load_extension` yok), yani `sqlite-vec` kullanılamaz. Bu proje için sorun değil: arama numpy ile yapılıyor.

Windows'ta durum:

| Konu | Durum |
|---|---|
| Donanım | x64 ve ARM64 desteklenir. macOS'taki arm64 kısıtı burada yoktur. |
| Hızlandırma | Donanıma göre Foundry Local seçer: NVIDIA'da CUDA, Snapdragon X'te NPU, yoksa CPU. |
| Python | Aynı: SDK 1.x **>= 3.11** ister. Windows Python ile gelmez, kurmanız gerekir. |
| CLI | Aynı: gerekmez. `winget install Microsoft.FoundryLocal` bu proje için gereksizdir. |
| **1 numaralı tuzak** | Farklıdır: `python` komutu Microsoft Store'un sahte kısayoluna gidebilir. Çözüm `py -3.12` başlatıcısıdır. |
| **2 numaralı tuzak** | PowerShell varsayılan olarak script çalıştırmayı yasaklar; `Activate.ps1` engellenir. Çözüm `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |

Ayrıntısı: [SETUP_WINDOWS.md](SETUP_WINDOWS.md). Dikkat edilecek bir nokta: `_embedding_device_default()` içindeki "embedding'i CPU'ya zorla" kuralı **yalnızca Apple Silicon içindir**; Windows'ta varyantı Foundry Local seçer.

Bu projenin kullandığı modeller:

| Rol | Alias | Boyut / not |
|---|---|---|
| Embedding | `qwen3-embedding-0.6b` | 1024 boyutlu vektör, 32K bağlam, 100+ dil, indirme ~520-541 MB |
| Sohbet | `qwen2.5-0.5b` | ~735 MB (gpu) / ~862 MB (cpu); **Türkçe üretimde kullanılamaz** -- aşağıya bakın |

Varsayılanlar `src/foundry_rag/config.py` içindeki `Settings` sınıfındadır. `qwen2.5-0.5b` bu makinede Türkçe sorularda dejenere tekrar döngüsüne giriyor ("kendinden ve kendinden ve kendinden...") ve tek bir soru 346 saniye sürüyor. Dikkat edilecek nokta şudur: aynı soruda **getirme kusursuzdu** (güven 0.741, doğru parça 1. sırada); bozuk olan yalnızca üretimdi. Kaynaklılık denetleyicisi bunu kendiliğinden yakaladı: 15 cümlenin 0'ı dayanaklı. Daha iyi cevap kalitesi için `FRAG_CHAT_MODEL=qwen3-1.7b` (~1490 MB) veya `qwen3-4b` (~3083 MB) kullanılabilir; bu Hafta 1'in konusu değildir.

Açık hatalar (bunları bilerek çalışın):

| Konu | Ne olur | Bu depoda nasıl ele alınmış |
|---|---|---|
| `microsoft/Foundry-Local` **#905** | Microsoft'un kendi RAG tutorial'ındaki streaming döngüsü son boş chunk'ta `IndexError` ile çöker | `foundry.py` içinde `if not getattr(chunk, "choices", None): continue` |
| **#858 / #895** | GPU execution provider doğru kaydolsa bile bazen sadece CPU varyantları görünür; sessizce yavaş build çalışır | `describe_variant()` `load()` sonrası model id + execution provider yazdırır |
| **#909 / #906** | İndirme sırasında uyku modu bozuk model önbelleği bırakabilir; bütünlük doğrulaması yok | İndirme sırasında makineyi uyutmayın |
| GPU embedding varyantı (bu makinede ölçüldü) | `qwen3-embedding-0.6b-generic-gpu:1` vektörde Inf/NaN üretiyor; SDK vektörü JSON'a yazarken `System.ArgumentException` ile çöküyor. Aynı modelin `-generic-cpu:1` varyantı temiz 1024 boyutlu vektör veriyor. Foundry Local varsayılan olarak bozuk olanı seçiyor | `foundry.py` içinde `_is_non_finite_failure()` hatanın imzasını tanıyıp CPU'ya geçiyor; macOS arm64'te `_embedding_device_default()` embedding modelini zaten doğrudan CPU varyantıyla açıyor. `FRAG_DEVICE=gpu` ile geçersiz kılınabilir |
| Execution provider yazımı (bu makinede ölçüldü) | Uzak katalog API'si `WebGPUExecutionProvider`, SDK'nın okuduğu yerel önbellek `WebGpuExecutionProvider` yazıyor. Tam eşleşmeli string karşılaştırması GPU varyantını asla bulamaz | `foundry.py` içinde `_variant_provider()` küçük harfe çevirip karşılaştırıyor |

### 2.5 Bu projede farklı olan ne?

Tipik bir RAG öğreticisi şöyledir: tek bir vektör araması, İngilizce metin, gözle seçilmiş bir benzerlik eşiği ve "cevap güzel görünüyor" ile biten bir değerlendirme. Bu depo dört noktada bundan ayrılır.

**Bu bölüm sadece haritadır.** Amacı, dördünün adını ve hangi dosyada durduğunu tanımanız. Nasıl çalıştıkları ilerleyen haftaların konusu; bu hafta ezberlemeniz gereken tek şey "hangi hataya karşı var" sütunudur.

| # | Ne | Hangi hataya karşı | Kod |
|---|---|---|---|
| 1 | Türkçe morfoloji duyarlı normalizasyon | "belge" ile "belgelerden" ayrı kelime sayılır; Python'un `.lower()`'ı `I` harfini yanlış küçültür | `src/foundry_rag/turkish.py` |
| 2 | Hibrit getirme (BM25 + RRF) | Vektör araması nadir birebir kelimeleri, kelime araması eş anlamlıyı kaçırır | `src/foundry_rag/lexical.py` + `hybrid_search()` -> `retrieval.py` |
| 3 | Kaynaklılık denetimi | Doğru parça getirilse bile modelin o parçada olmayan bir cümle yazması | `src/foundry_rag/groundedness.py` |
| 4 | Veri odaklı eşik kalibrasyonu + CI kalite kapısı | Eşiğin tahminle seçilmesi; kalite düşüşünün sessizce geçmesi | `eval/calibrate.py`, `eval/evaluate.py --gate` |

**1 -- Türkçe morfoloji.** Türkçe eklemeli bir dildir: aynı kök `vektör / vektörler / vektörlerin / vektörlere` diye uzar. Ham kelimeleri karşılaştıran bir kelime araması bunları dört ayrı kelime sayar. `turkish.py` üç iş yapar: `fold_case()` Türkçe'ye özgü küçültme (`I` -> `ı`, `İ` -> `i`), `stem_word()` ek ayıklama, `expand_tokens()` ise her kelimeyi **hem yüzey biçimi hem gövde** olarak üretir. Üçüncüsü kritiktir, çünkü kural tabanlı bir gövdeleyici son ünlünün ek mi kök mü olduğunu bilemez: `belge` -> `belg`, `belgeler` -> `belge`; ikisi hiç buluşmaz. İkisini birden indeksleyince `belge={belge, belg}` ve `belgeler={belgeler, belge}` ortak `belge` üzerinden eşleşir. Gövde bir **recall arttırıcıdır**, doğruluk kaynağı değil. Ölçüm: 12 kelime ailesinin 12'sinde eşleşme, kontrol çiftlerinde (kedi~kahve, vektör~veri, model~modern, bilgi~bilek, sorgu~sormak) 0 yanlış pozitif.

**2 -- Hibrit getirme.** İki arama birlikte koşar: kosinüs benzerliği (anlam) ve BM25 kelime araması (`BM25Index`, `k1=1.5`, `b=0.75`). İki **sıralama** `reciprocal_rank_fusion(..., k=60)` ile birleştirilir. Skorlar değil sıralar toplanır: kosinüs `[-1, 1]` aralığındadır, BM25 sınırsızdır ve korpusa bağlıdır; ham skorları toplamak her korpusta yeniden ayar ister, sıralar ise kalibrasyonsuz karşılaştırılabilir. Kabul kapısı `max(anlam, saturate(kelime, 16.0))` yani **iki aramadan biri emin ise** parça kabul edilir. `ask` çıktısındaki `bulan:` etiketi hangi aramanın bulduğunu söyler -- A1.3'te buna bakacaksınız.

**3 -- Kaynaklılık denetimi.** `groundedness.check(answer, hits)` cevabı cümlelere böler ve her cümlenin terimlerinin ağırlıklı recall'unu getirilen pasajlara karşı hesaplar. Yaygın kelimeler (`ve`, `bir`, `bu`) atılır, nadir kelimeler IDF ile ağır basar, pasajlarda hiç geçmeyen terim **maksimum** ağırlık alır -- uydurma tam da böyle kelime getirir. Bu bir NLI (doğal dil çıkarımı) modeli **değildir**: çelişkiyi ve ortak kelimesi olmayan eş anlamlıyı yakalayamaz. Karşılığında ikinci bir model indirmesi gerektirmez ve asıl önemli hatayı yakalar: modelin bağlamda hiç geçmeyen bir şeyi iddia etmesi. Ölçüm: doğru cevapta %100, uydurma cevapta %0.

**4 -- Kalibrasyon ve kalite kapısı.** `eval/calibrate.py`, `min_similarity` x `lexical_scale` ızgarasını tarar (11 x 6 = 66 nokta) ve her nokta için recall / reddetme / genel / dengeli hesaplar. Seçim ölçütü "dengeli" = recall ile reddetmenin **harmonik** ortalamasıdır; aritmetik olsaydı her soruyu cevaplayıp hiçbirini reddetmeyen bir sistem %50 alırdı. Sorular bir kez embed edilip ızgara boyunca yeniden kullanılır. Sonuç CI'a da bağlıdır: `eval/evaluate.py --gate` metrikler eşiklerin altına düşerse çıkış kodu 1 döndürür ve derlemeyi kırar.

Bu değişikliğin 33 soruluk değerlendirme setindeki karşılığı (`hashing` backend, `top_k=4`):

| Ölçüt | Yalnızca vektör + tahmini eşik (0.15) | Hibrit + kalibre eşik (0.30) |
|---|---|---|
| Recall@4 | %72.0 | %88.0 |
| MRR | 0.650 | 0.793 |
| Reddetme doğruluğu | %87.5 | %100.0 |
| Genel doğruluk | %75.8 | %90.9 |

**Eşik modele bağlıdır.** Aynı 33 soru, gerçek embedding modeliyle (`foundry` backend, `qwen3-embedding-0.6b`):

| min_similarity | Recall@4 | MRR | Reddetme | Genel |
|---|---|---|---|---|
| 0.30 | %100 | 0.973 | %62.5 | %90.9 |
| 0.40 | %96 | 0.960 | %100.0 | %97.0 |

Koddaki varsayılan `0.30`'dur, çünkü testler ve CI çevrimdışı `hashing` backend'ini kullanır. Foundry Local ile çalışacaksanız `FRAG_MIN_SIMILARITY=0.40` yapın. Buradan çıkacak ders eşiğin sayısı değil, **eşiğin bir model özelliği olduğu ve model değişince yeniden ölçülmesi gerektiğidir**.

Dördünün de testi vardır: `python -m pytest tests/ -q` 163 test çalıştırır, hepsi çevrimdışıdır ve bir saniyenin altında biter.

---

## 3. Kaynaklar

Bağlantılar taşınabilir. Bir link ölürse `learn.microsoft.com` üzerinde tablodaki başlığı aratın. **Bu depodaki kod, her zaman en güncel ve doğrulanmış kaynaktır**; bir bloga ile kod çelişirse kod haklıdır.

| Kaynak | Bağlantı | Bu hafta hangi bölüm okunacak |
|---|---|---|
| Microsoft Learn -- What is Foundry Local | `https://learn.microsoft.com/azure/ai-foundry/foundry-local/what-is-foundry-local` | Tamamı. Özellikle "key features" ve desteklenen platformlar bölümü. Yazıda macOS için CoreML/ANE geçiyorsa bölüm 2.4'teki tabloyu esas alın. |
| Microsoft Learn -- Get started with Foundry Local | `https://learn.microsoft.com/azure/ai-foundry/foundry-local/get-started` | Yalnızca kavramsal kısım ve SDK bölümü. **CLI kurulum adımlarını uygulamayın** -- bu proje CLI'sız çalışır. |
| Microsoft Learn -- Retrieval Augmented Generation (RAG) overview | `https://learn.microsoft.com/azure/search/retrieval-augmented-generation-overview` | "What is RAG" ve "Approaches" bölümleri. Azure AI Search'e özgü kısımları atlayın; kavram aynıdır, altyapı farklıdır. |
| GitHub -- microsoft/Foundry-Local | `https://github.com/microsoft/Foundry-Local` | README'nin platform destek tablosu + `samples/` klasöründeki Python örnekleri. |
| GitHub Issues -- #905, #858, #895, #909, #906 | `https://github.com/microsoft/Foundry-Local/issues/905` (numarayı değiştirerek) | Her issue'nun ilk mesajı. Amaç: gerçek yazılımın açık hatalarla geldiğini görmek. |
| Microsoft Tech Community | `https://techcommunity.microsoft.com` | Site içi aramaya "Foundry Local" yazın, son 6 ayın yazılarına bakın. Blog yazılarındaki sürüm numaralarını ve donanım iddialarını `scripts/doctor.py` çıktınızla karşılaştırın. |
| Bu depo -- `data/docs/01-rag-nedir.md` | Yerel dosya | Tamamı. 60 satır. A1.4 alıştırmasının girdisi budur. |
| Bu depo -- `data/docs/02-foundry-local.md` | Yerel dosya | Tamamı. |

---

## 4. Uygulamalı alıştırmalar

Dört alıştırma var. Sırayla yapın: A1.3, A1.2'nin tamamlanmış olmasını gerektirir.

### A1.1 -- Kağıt üzerinde RAG

**Süre:** 45 dakika. **Format:** İkili çalışma, bilgisayarsız.

**Amaç:** RAG'in üç adımını kod yazmadan, insan olarak canlandırmak. Retriever'ın ve LLM'in ayrı iki bileşen olduğunu ve aralarındaki tek iletişim kanalının "bağlam metni" olduğunu somut olarak hissetmek.

**Adımlar**

1. Eşleşin ve rolleri paylaşın: biri **Retriever**, diğeri **LLM**. Rol değişimi 4. adımda yapılacak.
2. Eğitmen her ikiliye 1 sayfalık basılı bir metin verir (örneğin `data/docs/03-embedding-ve-vektor-arama.md` çıktısı). **Metni yalnızca Retriever görür.** LLM metni okumaz, hatta başlığını bile bilmez.
3. Eğitmen metinle ilgili bir soru okur. Süreç şudur:
   - **Retrieve:** Retriever metinde soruya en ilgili en fazla **3 paragrafı** bulur ve sadece o paragrafları kağıda kopyalar. Kendi yorumunu eklemesi yasaktır.
   - **Augment:** Retriever kağıdın başına şunu yazar: "Sadece aşağıdaki metni kullan. Cevap burada yoksa 'Bu bilgi elimdeki belgelerde yok.' de. Her cümlenin sonunda kaçıncı paragraftan geldiğini yaz." Sonra soruyu da ekler ve kağıdı LLM'e verir.
   - **Generate:** LLM **yalnızca** kağıttaki metne bakarak cevabı yazar, her iddianın yanına paragraf numarasını koyar. Kendi bildiğini kullanması yasaktır.
4. Rolleri değiştirin ve 3. adımı yeni bir soruyla tekrarlayın.
5. Eğitmen üçüncü bir soru sorar: **cevabı metinde olmayan** bir soru. Aynı süreci uygulayın.
6. İkili olarak yarım sayfalık bir not yazın: Retriever yanlış paragrafı seçtiğinde ne oldu? LLM cevabı uydurmaya kalktı mı? 5. adımda hangi rol "bilmiyorum" demek zorunda kaldı?

**Beklenen çıktı**

- Üç soru için doldurulmuş üç "bağlam kağıdı" (paragraflar + talimat + soru).
- Üç cevap, her cümlede paragraf numarası ile.
- Yarım sayfalık ikili gözlem notu.

**Değerlendirme ölçütü**

| Ölçüt | Geçer |
|---|---|
| Rol ayrımı | LLM rolündeki kişi hiçbir aşamada asıl metne bakmadı |
| Kaynak gösterme | Üç cevabın da her iddiasında paragraf numarası var |
| Reddetme | 5. adımdaki soruda cevap "Bu bilgi elimdeki belgelerde yok." oldu, uydurma yapılmadı |
| Gözlem notu | Retriever hatasının LLM cevabını nasıl bozduğuna dair en az bir somut örnek içeriyor |

---

### A1.2 -- Ortam kurulumu ve `doctor.py` çıktısını yorumlama

**Süre:** 2-3 saat (indirme hızına bağlı). **Format:** Bireysel.

**Amaç:** Foundry Local SDK 1.x'in çalışabileceği bir Python ortamı kurmak ve ortam sorunlarını tahmin ederek değil, ölçerek teşhis etmeyi öğrenmek.

**Adımlar**

1. İşletim sisteminizin kurulum rehberini baştan sona okuyun, sonra adımları uygulayın: [SETUP_MACOS.md](SETUP_MACOS.md) veya [SETUP_WINDOWS.md](SETUP_WINDOWS.md). Özet komut dizisi:

   **macOS:**

   ```bash
   brew install python@3.12
   cd ~/Desktop/foundry-local-rag
   /opt/homebrew/bin/python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   **Windows (PowerShell):**

   ```powershell
   winget install Python.Python.3.12
   cd $HOME\Desktop\foundry-local-rag
   py -3.12 -m venv .venv
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   `python@3.12` seçimi keyfi değildir: SDK Python 3.11+ ister, numpy 2.5 ise artık 3.11'i desteklemiyor. 3.12 iki koşulu da sağlar.

2. Hangi Python'u kullandığınızı doğrulayın:

   ```bash
   python --version        # 3.12.x olmali
   which python            # .../foundry-local-rag/.venv/bin/python olmali
   ```

   Windows'ta ikinci komutun karşılığı `Get-Command python`'dur; `...\.venv\Scripts\python.exe` göstermelidir.

   macOS'ta `/usr/bin/python3`, Windows'ta `...\WindowsApps\python.exe` görüyorsanız sanal ortam etkin değildir. Etkinleştirme komutunu tekrarlayın.

3. Ortam kontrolünü çalıştırın:

   ```bash
   python scripts/doctor.py
   ```

4. Çıktıyı satır satır yorumlayın. `scripts/doctor.py` dört blok kontrol eder ve üç işaret kullanır:

   | İşaret | Anlamı | Ne yapmalı |
   |---|---|---|
   | `[ok]` | Sorun yok | Bir şey yapma |
   | `[!!]` | Uyarı; sistem çalışır ama bir yetenek eksik | Not al, gerekiyorsa `->` satırını uygula |
   | `[XX]` | Hata; düzeltilmeden devam edilmez | `->` satırındaki komutu çalıştır |

   Kontrol blokları:

   | Blok | Ne bakar | Sık görülen sonuç |
   |---|---|---|
   | `--- Platform ---` | `platform.machine()` arm64 mi | Apple Silicon'da `[ok]`, Intel'de `[!!]` |
   | `--- Python ---` | Sürüm >= 3.11 mi, `sqlite3` uzantı yükleyebiliyor mu | 3.12'de `[ok]`; sqlite satırı `[!!]` çıkabilir, bu proje için sorun değil |
   | `--- Paketler ---` | numpy, streamlit, `foundry-local-sdk` sürümü ve modül adı | SDK kurulu değilse `[!!]`, 0.x kuruluysa `[XX]` |
   | `--- Foundry Local katalogu ---` | Katalog `qwen2.5-0.5b` ve `qwen3-embedding-0.6b` alias'larını çözüyor mu | İlk çalıştırmada internet gerekir; başlatılamazsa `[!!]` |

   Script sonunda sorun sayısını yazar ve sorun varsa çıkış kodu 1 döndürür.

5. Çıktının tamamını bir dosyaya kaydedin ve her `[!!]` / `[XX]` satırı için bir cümlelik açıklama yazın:

   ```bash
   python scripts/doctor.py > ~/hafta1-doctor-ciktisi.txt 2>&1
   ```

**Beklenen çıktı**

- `~/hafta1-doctor-ciktisi.txt` dosyası.
- `--- Platform ---` ve `--- Python ---` bloklarında `[XX]` **bulunmaması**.
- Her `[!!]` ve `[XX]` satırı için "bu ne demek, sistemi nasıl etkiler" açıklaması içeren kısa bir not.

**Değerlendirme ölçütü**

| Ölçüt | Geçer |
|---|---|
| Doğru yorumlayıcı | `which python` sanal ortamı gösteriyor, sürüm 3.11+ |
| Paket kontrolü | `foundry-local-sdk` için `[XX]` yok; kuruluysa modül adı `foundry_local_sdk` |
| Yorum kalitesi | Uyarı satırlarının açıklaması "hata var" demiyor; hangi yeteneğin eksik kaldığını söylüyor |
| Tuzak farkındalığı | Öğrenci, 0.5.1 tuzağının neden `pip` hatası vermeden oluştuğunu bir cümleyle açıklayabiliyor |

---

### A1.3 -- Foundry Local olmadan çalışan RAG

**Süre:** 1 saat. **Format:** Bireysel.

**Amaç:** Model indirmeden, sistemin uçtan uca çalıştığını görmek ve bunu mümkün kılan tasarım kararını (backend soyutlaması) kaynak kodda bulmak.

**Adımlar**

1. Depoyu klonlayın (henüz klonlamadıysanız) ve A1.2'deki sanal ortamı etkinleştirin.
2. İndeksi kurun:

   ```bash
   python -m app.cli --backend hashing ingest
   ```

3. Çıktıdaki şu satırları not edin: kullanılan backend, üretilen parça sayısı, süre.
4. İki soru sorun -- biri cevabı belgelerde olan, biri olmayan:

   ```bash
   python -m app.cli --backend hashing ask "RAG kısaltması hangi üç adımdan gelir?"
   python -m app.cli --backend hashing ask "Bu programın sınav tarihi ne zaman?"
   ```

   Türkçe karakterleri **doğru yazın**. `hashing` backend'i kelimeleri karakter n-gram'larına ayırır; "kısaltması" ile "kisaltmasi" farklı token üretir ve ikincisi hiçbir sonuç getirmeyebilir. Bu, gerçek bir embedding modelinde olmayan bir kısıttır ve tam olarak bu backend'in neden geçici bir çözüm olduğunu gösterir.

5. İndeksin durumuna bakın:

   ```bash
   python -m app.cli --backend hashing info
   ```

6. **Asıl soru: bu nasıl mümkün oluyor?** Şu üç dosyayı bu sırayla okuyun ve cevabı yazın:

   | Dosya | Neye bakın |
   |---|---|
   | `src/foundry_rag/backends/base.py` | `Backend` soyut sınıfı. Kaç metot zorunlu? (`embed`, `chat`, `embedding_dim`) |
   | `src/foundry_rag/backends/hashing.py` | `HashingBackend` bu üç metodu nasıl dolduruyor? `chat()` bir dil modeli mi çağırıyor? |
   | `src/foundry_rag/backends/__init__.py` | `create_backend()` `auto` / `foundry` / `hashing` seçeneklerini nasıl ayırıyor? |

7. `src/foundry_rag/pipeline.py` içinde `RagPipeline` sınıfında `foundry` veya `hashing` kelimesini arayın:

   ```bash
   grep -n "foundry\|hashing" src/foundry_rag/pipeline.py
   ```

   Sonuç boştur. Pipeline hangi backend'i kullandığını **bilmez**. Cevabınızda bu gözleme yer verin.

**Beklenen çıktı**

`ingest` komutu şuna benzer bir çıktı verir (parça sayısı ve süre sizin makinenizde de aynı olmalı, sürenin kendisi değişir):

```
Belge klasoru : /Users/<kullanici>/Desktop/foundry-local-rag/data/docs
Veritabani    : /Users/<kullanici>/Desktop/foundry-local-rag/data/rag.db
Parca boyutu  : 900 (ortusme 150)

Backend: hashing-offline (dim=512)

  Embedding: 54/54 parca

8 belge -> 54 parca (54 yeni kayit) / 0.0 sn
```

Cevaplanabilir soru için, kaynak ve skorları içeren bir cevap:

```
Kaynaklar:
  [1] 01-rag-nedir.md > RAG'in Üç Adımı
      guven 0.499 | anlam 0.159 | kelime 15.93 | bulan: ikisi
```

`guven` cevap/reddetme kararında kullanılan skordur (`anlam` ile doyurulmuş `kelime` skorunun büyüğü), `anlam` kosinüs benzerliği, `kelime` BM25 skoru, `bulan` ise parçayı hangi aramanın getirdiği.

Cevabın sonunda şu not bulunur: `(Not: Foundry Local kurulu olmadığı için bu cevap bir dil modeli tarafından yazılmadı; belgelerden doğrudan alıntılandı.)`

`info` komutu 54 parça, 8 belge ve `embedding_signature = hashing-offline:512` gösterir.

**Değerlendirme ölçütü**

| Ölçüt | Geçer |
|---|---|
| Çalıştırma | `ingest`, `ask`, `info` üçü de hatasız çalıştı; `info` 8 belge / 54 parça gösteriyor |
| Skor okuma | Öğrenci `anlam 0.159` sayısının ne olduğunu (kosinüs benzerliği), `guven` skorundan farkını ve `guven` değerinin neden `0.30` eşiğiyle karşılaştırıldığını söyleyebiliyor |
| Mimari cevabı | Yazılı cevap `Backend` soyut sınıfını, üç zorunlu metodu ve `create_backend()` fabrikasını adıyla anıyor |
| Kanıt | Cevap, `pipeline.py` içinde backend adının geçmediği gözlemine dayanıyor |
| Sınır farkındalığı | Öğrenci `hashing` backend'inin anlamsal değil kelime/karakter eşleşmesi yaptığını ve bunun neden zayıf olduğunu bir örnekle söyleyebiliyor |

---

### A1.4 -- Cevaplanabilir ve cevaplanamaz sorular

**Süre:** 2 saat. **Format:** Bireysel, sonuçlar sınıfça karşılaştırılır.

**Amaç:** Bir RAG sisteminin iki farklı başarısını ayırt etmek: doğru cevap vermek ve **cevap vermemesi gerektiğinde susmak**. Bu ikisi ayrı ölçülür çünkü ayrı sebeplerle bozulurlar.

**Adımlar**

1. `data/docs/01-rag-nedir.md` dosyasını baştan sona okuyun (60 satır, 7 başlık).
2. Beş soru yazın ve bir dosyaya kaydedin:
   - **3 cevaplanabilir soru:** Cevabı bu dosyada açıkça geçen sorular. Farklı başlıkları hedefleyin (örneğin biri "RAG'in Üç Adımı", biri "RAG ile Fine-Tuning Arasındaki Fark", biri "Yerel (Offline) RAG" bölümünden).
   - **2 cevaplanamaz soru:** Konuyla **ilgili görünen** ama cevabı hiçbir belgede olmayan sorular. Kolay olanı seçmeyin. "Bugün hava nasıl?" kolaydır ve bir şey ölçmez; "RAG'de kaç parça getirmek optimaldir?" zordur çünkü sistem benzer kelimeler bulup yanlış bir parça getirebilir.
3. Her soruyu sisteme sorun ve **hem cevabı hem kaynak satırlarını** kaydedin:

   ```bash
   python -m app.cli --backend hashing ask "<sorunuz>"
   ```

4. Sonuçları bir tabloya doldurun:

   | Soru | Cevaplanabilir mi? | Sistem ne dedi | En yüksek benzerlik | Getirilen kaynak(lar) | Doğru davranış mı? |
   |---|---|---|---|---|---|

5. Şu üç durumu ayrı ayrı işaretleyin:
   - **Doğru cevap:** Cevaplanabilir soruya, doğru kaynaktan cevap geldi.
   - **Doğru reddetme:** Cevaplanamaz soruya `Bu bilgi elimdeki belgelerde yok.` cevabı geldi.
   - **Yanlış pozitif:** Cevaplanamaz soru için sistem yine de bir parça getirdi ve cevap üretti. Bu durumda **en yüksek `guven` skorunu not edin** -- muhtemelen varsayılan `0.30` eşiğinin hemen üstündedir.
6. Yarım sayfalık bir analiz yazın. Şu soruları cevaplayın:
   - Yanlış pozitif aldıysanız, `FRAG_MIN_SIMILARITY` değerini yükseltmek bunu çözer miydi? Deneyin: `python -m app.cli --backend hashing --min-similarity 0.45 ask "<soru>"`. Eşiği yükseltmenin bedeli ne oldu -- daha önce doğru cevaplanan sorulardan biri kaybedildi mi?
   - `prompts.py` içindeki 2 numaralı kural olmasaydı ne olurdu?
7. Karşılaştırma: `eval/questions.json` dosyasını açın. 33 soru vardır; 25'i cevaplanabilir, 8'i `expected_source: null` yani cevaplanamaz. Kendi cevaplanamaz sorularınızı oradaki 8 soruyla karşılaştırın -- sizinkiler yeterince zor mu?

**Beklenen çıktı**

- 5 soruluk soru dosyası (3 cevaplanabilir + 2 cevaplanamaz olarak etiketlenmiş).
- 4. adımdaki doldurulmuş tablo, gerçek benzerlik skorlarıyla.
- Yarım sayfalık analiz, eşik denemesinin sonucu dahil.

**Değerlendirme ölçütü**

| Ölçüt | Geçer |
|---|---|
| Soru kalitesi | 3 cevaplanabilir soru dosyanın 3 **farklı** başlığını hedefliyor |
| Zorluk | 2 cevaplanamaz soru konuyla ilgili terimler içeriyor; alakasız ("hava durumu" tipi) değil |
| Ölçüm | Tablodaki benzerlik skorları gerçek çıktıdan kopyalanmış, tahmin değil |
| Analiz | Eşik yükseltme denemesi yapılmış ve bedeli (kaybedilen doğru cevap) yazılmış |
| Kavram | Analiz, doğru cevap ile doğru reddetmenin **ayrı** başarılar olduğunu ifade ediyor |

---

## 5. Hafta sonu çıktı kontrol listesi

Aşağıdakilerin hepsi tamam olmadan Hafta 2'ye geçilmez.

**Ortam**

- [ ] `python --version` çıktısı 3.11 veya üstü, `which python` depo içindeki `.venv`'i gösteriyor
- [ ] `pip install -r requirements.txt` hatasız tamamlandı
- [ ] `python scripts/doctor.py` çıktısı kaydedildi; Platform ve Python bloklarında `[XX]` yok
- [ ] Her `[!!]` satırı için bir cümlelik açıklama yazıldı

**Çalışan sistem**

- [ ] `python -m app.cli --backend hashing ingest` çalıştı ve `8 belge -> 54 parca` çıktısını verdi
- [ ] `python -m app.cli --backend hashing info` 54 parça / 8 belge ve `hashing-offline:512` imzasını gösteriyor
- [ ] En az bir soru cevap ve kaynak satırıyla döndü
- [ ] En az bir soru `Bu bilgi elimdeki belgelerde yok.` cevabını verdi
- [ ] `python -m pytest tests/ -q` çalıştırıldı ve 163 testin hepsi geçti

**Kavramsal**

- [ ] Retrieve / Augment / Generate adımlarının her biri için bir fonksiyon adı + dosya yolu yazılabiliyor
- [ ] Halüsinasyona karşı üç savunmanın (benzerlik eşiği, sistem istemi kuralı, kaynaklılık denetimi) üçü de adıyla söylenebiliyor
- [ ] `foundry` CLI'ının bu projede neden gerekmediği açıklanabiliyor
- [ ] SDK 0.5.1 tuzağının neden `pip` hatası vermeden oluştuğu açıklanabiliyor

**Teslim edilecek dosyalar**

| Alıştırma | Teslim |
|---|---|
| A1.1 | 3 bağlam kağıdı + 3 cevap + ikili gözlem notu |
| A1.2 | `doctor.py` çıktı dosyası + uyarı açıklamaları |
| A1.3 | `ingest` / `ask` / `info` çıktıları + backend soyutlaması yazılı cevabı |
| A1.4 | 5 soruluk dosya + sonuç tablosu + yarım sayfa analiz |
