# Hafta 5 -- Test, Değerlendirme ve Performans

**Faz 3: Kapanış**

Bu haftaya kadar çalışan bir sistem kurdun. Bu hafta onun **ne kadar iyi** çalıştığını
sayıyla söylemeyi öğreneceksin. Haftanın sonunda şu üç soruya rakamla cevap
verebiliyor olman gerekiyor:

1. Sistem doğru belgeyi ne sıklıkla buluyor?
2. Bilmediği bir şey sorulduğunda uyduruyor mu, yoksa "bilmiyorum" diyor mu?
3. Bir ayarı değiştirdiğimde sistem iyileşti mi, kötüleşti mi?

Üçüncü soru en önemlisidir ve gözle bakarak cevaplanamaz.

---

## Bu haftada dokunacağın dosyalar

| Dosya | Ne var içinde |
|---|---|
| `eval/questions.json` | 33 soru: 25 cevaplanabilir + 8 cevaplanamaz |
| `eval/evaluate.py` | `evaluate_one()`, `summarize()`, `run_quality_gate()` |
| `eval/calibrate.py` | `evaluate_grid_point()`, `Point.balanced` |
| `src/foundry_rag/groundedness.py` | `check()`, `support_score()`, `GroundednessReport` |
| `.github/workflows/ci.yml` | "Retrieval quality gate" adımı |

## Ön koşullar

```bash
cd ~/Desktop/foundry-local-rag
source .venv/bin/activate
python -m pytest tests/ -q          # 163 test geçmeli
python -m app.cli info              # indekste 54 parça görünmeli
```

---

## 1. Teori

### 1.1 İki ayrı şeyi ayrı ölçmek

Bir RAG sistemi iki bileşenden oluşur ve **ikisi ayrı ayrı ölçülmelidir**:

- **Getirme (retrieval):** doğru parça bulundu mu? Bu, dil modelinden bağımsızdır.
- **Üretim (generation):** bulunan parçadan doğru cevap çıkarıldı mı?

Sıra önemlidir. Getirme başarısızsa üretimi ölçmek anlamsızdır — model olmayan
bilgiden doğru cevap üretemez. Önce getirmeyi düzelt, sonra üretime bak.

Bu ayrımın pratik değeri bu projede ölçüldü: getirme **%97 genel doğrulukta**
çalışırken üretim (`qwen2.5-0.5b`, Türkçe) tamamen kullanılamaz durumdaydı. İki
metrik tek sayıya karıştırılsaydı bu görülemezdi.

### 1.2 Recall@K

En temel getirme metriği: **doğru kaynak, getirilen ilk K parça içinde var mı?**

```
Recall@K = (doğru kaynağı ilk K'da bulan soru sayısı) / (cevaplanabilir soru sayısı)
```

`top_k=4` ile çalışıyorsak Recall@4 ölçeriz. Recall K arttıkça artar — bu bir
başarı değil, tanım gereğidir. K'yı büyütüp Recall'ün yükselmesine sevinmek
klasik bir hatadır; bağlam penceresi dolar ve üretim kalitesi düşer.

### 1.3 MRR (Ortalama Karşılıklı Sıra)

Recall doğru kaynağın **kaçıncı sırada** geldiğini umursamaz. Birinci sırada
gelmesiyle dördüncü sırada gelmesi aynı sayılır. Oysa modele verilen bağlamda
doğru parçanın önde olması önemlidir.

```
MRR = ortalama( 1 / doğru kaynağın sırası )
```

Doğru kaynak 1. sıradaysa 1.0, 2. sıradaysa 0.5, 4. sıradaysa 0.25 katkı verir.
Hiç bulunamadıysa 0.

**Elle hesaplama örneği.** Üç soru, sıraları 1, 3 ve bulunamadı:

```
MRR = (1/1 + 1/3 + 0) / 3 = (1.0 + 0.333 + 0) / 3 = 0.444
```

Bu hesabı `eval/evaluate.py` içindeki `summarize()` fonksiyonunda bul ve
kodun aynı şeyi yaptığını doğrula (A5.2).

### 1.4 Reddetme doğruluğu ve cevaplanamaz sorular

Bir RAG sisteminin en tehlikeli hatası yanlış cevap vermek değil, **bilmediği bir
konuda kendinden emin şekilde uydurmasıdır**. Kullanıcı yanlış cevabı fark
edebilir; kendinden emin uydurmayı fark edemez.

Bunu ölçmenin tek yolu, cevabı bilgi tabanında **kesinlikle bulunmayan** sorular
sormaktır:

```
Reddetme doğruluğu = (doğru şekilde reddedilen) / (cevaplanamaz soru sayısı)
```

`eval/questions.json` içinde bu sorular `expected_source: null` ile işaretlidir
ve setin **8/33'ünü** oluşturur. Yaklaşık üçte bir iyi bir orandır: daha azı
istatistiksel olarak anlamsız, daha fazlası setin ağırlığını asıl işten kaydırır.

### 1.5 Dengeli skor: neden aritmetik ortalama yalan söyler

Recall ve reddetme doğruluğu **birbirinin aleyhine** hareket eder. Eşiği
düşürürsen her şeyi cevaplarsın: Recall %100, reddetme %0. Eşiği yükseltirsen
hiçbir şeyi cevaplamazsın: Recall %0, reddetme %100. İkisi de işe yaramaz sistem.

Aritmetik ortalama bu tuzağı gizler:

| Sistem | Recall | Reddetme | Aritmetik | Harmonik |
|---|---|---|---|---|
| Her şeyi cevaplayan | %100 | %0 | **%50** | **%0** |
| Hiçbir şeyi cevaplamayan | %0 | %100 | **%50** | **%0** |
| Dengeli | %88 | %100 | %94 | **%93.6** |

`eval/calibrate.py` içindeki `Point.balanced` bu yüzden **harmonik ortalama**
kullanır: iki taraftan biri feda edilirse skor sıfıra gider.

### 1.6 Eşik modele bağlıdır

Bu projenin en pahalı dersi. `min_similarity` bir sabit değil, **skor dağılımına
bağlı bir ayardır**. Aynı sayı farklı modellerde farklı şey ifade eder:

| Backend | Optimum `min_similarity` | Recall | Reddetme | Genel |
|---|---|---|---|---|
| `hashing` (çevrimdışı yedek) | **0.30** | %88.0 | %100.0 | %90.9 |
| `foundry` (qwen3-embedding-0.6b) | **0.40** | %96.0 | %100.0 | %97.0 |

Bedeli ölçüldü: proje başında eşik `0.15`'ti ve tahmin edilmişti. Yalnız-vektör
getirme için makuldü. BM25 eklenince skor dağılımı altından kaydı ve **reddetme
doğruluğu %87.5'ten %12.5'e çöktü** — kod doğruydu, eşik eskimişti.

**Kural: modeli, korpusu veya retriever'ı değiştirdiysen yeniden kalibre et.**

### 1.7 Kaynaklılık: üretimi ölçmek

Getirme metrikleri modelin ne yazdığını umursamaz. Doğru parçayı getirip yanlış
cevap üretmek mümkündür. `src/foundry_rag/groundedness.py` bunu ölçer: cevabın
her cümlesini getirilen parçalara karşı puanlar, dayanağı olmayanları işaretler.

```python
report = answer.groundedness
print(report.summary())        # "Kaynaklilik: %100 (3/3 cumle dayanakli)"
for v in report.unsupported:
    print(v.score, v.text)
```

Ölçüm yöntemi: Türkçe morfoloji üzerinden IDF ağırlıklı içerik kelimesi örtüşmesi.
Nadir kelimeler ağır basar, işlev kelimeleri (`ve`, `bir`, `için`) hiç sayılmaz.
Hiç görülmemiş bir terim **maksimum** ağırlık alır — uydurma tam da öyle kelime
getirir.

Bu bir NLI (doğal dil çıkarımı) modeli değildir. Çelişkiyi ve ortak kelimesi
olmayan eş anlamlıyı yakalayamaz. Ama ikinci bir model indirmesi gerektirmez ve
asıl önemli hatayı güvenilir biçimde yakalar: **modelin bağlamda hiç geçmeyen bir
şeyi iddia etmesi.**

### 1.8 Performans profili

Ölçülmesi gereken üç süre vardır:

| Aşama | Bu makinede ölçülen |
|---|---|
| Sorgunun embedding'i + arama | **0.33 sn** (foundry backend) |
| | 0.00 sn (hashing backend) |
| Cevap üretimi | **346 sn** (qwen2.5-0.5b, CPU, Türkçe, dejenere) |

Darboğaz neredeyse her zaman üçüncüsüdür. Getirmeyi optimize etmek, üretim 1000
kat daha yavaşken anlamsızdır. Önce ölç, sonra optimize et.

---

## 2. Alıştırmalar

### A5.1 -- Kendi değerlendirme setini genişlet

**Amaç:** İyi bir test sorusunun neye benzediğini öğrenmek.

**Adımlar:**
1. `eval/questions.json` dosyasını aç, yapısını incele.
2. Kendi bilgi tabanından **10 soru** ekle: 7 cevaplanabilir + 3 cevaplanamaz.
3. Cevaplanabilir sorularda `expected_source` alanına cevabın gerçekten bulunduğu
   dosya adını yaz. Emin değilsen belgeyi aç ve doğrula.
4. Cevaplanamaz sorularda `expected_source` **`null`** olmalı. Bu sorular bilgi
   tabanınla ilgisiz olmalı — "kısmen ilgili" sorular ölçümü bulanıklaştırır.
5. Çalıştır:
   ```bash
   python eval/evaluate.py --backend hashing --no-save
   ```

**Beklenen çıktı:** Soru sayısı 43'e çıkmalı. Metrikler bir miktar değişecek.

**Değerlendirme ölçütü:** Eklediğin cevaplanamaz sorulardan hiçbiri yanlışlıkla
cevaplanmıyor. Cevaplanıyorsa ya soru yeterince ilgisiz değil, ya eşik düşük.

---

### A5.2 -- MRR'i elle doğrula

**Amaç:** Metriğe körü körüne güvenmemek.

**Adımlar:**
1. `eval/evaluate.py` içinde `summarize()` fonksiyonunu bul, MRR satırını oku.
2. Değerlendirmeyi çalıştır ve çıktıdaki **sıra** sütununu not al.
3. İlk 5 cevaplanabilir sorunun sırasını kağıda yaz, MRR'lerini elle hesapla.
4. Kodun aynı sonucu verdiğini doğrula.

**Değerlendirme ölçütü:** Elle hesabınla kodun sonucu tutuyor. Tutmuyorsa hangi
sorunun sırasını yanlış okuduğunu bul.

---

### A5.3 -- Eşiği veriden seç

**Amaç:** Ayar seçmenin tahmin değil ölçüm işi olduğunu görmek.

**Adımlar:**
```bash
python eval/calibrate.py --backend hashing
```

Çıktı 66 noktalık bir ızgaradır (11 `min_similarity` × 6 `lexical_scale`).

**İnceleme soruları — cevaplarını yaz:**
1. `min_similarity` artarken Recall neden **düşüyor**?
2. Reddetme doğruluğu neden **yükseliyor**?
3. `lexical_scale=2.0` satırlarında reddetme neden hiç yükselmiyor?
   (İpucu: `saturate(x, 2.0)` küçük BM25 skorlarını bile yüksek güvene çeviriyor.)
4. En iyi nokta `balanced` metriğine göre seçiliyor. `overall` seçseydin hangi
   nokta kazanırdı? Aradaki fark ne anlama gelir?

Sonra Foundry Local ile tekrarla ve iki tabloyu karşılaştır:
```bash
python eval/calibrate.py --backend foundry
```

**Değerlendirme ölçütü:** İki backend için farklı optimum eşik bulundu ve
öğrenci bunun **neden** böyle olduğunu (skor dağılımları farklı) açıklayabiliyor.

---

### A5.4 -- Kenar durumları

**Amaç:** Sistemin çökmediğini değil, **anlaşılır davrandığını** doğrulamak.

Aşağıdaki tabloyu doldur:

| Girdi | Komut | Beklenen | Gerçekleşen |
|---|---|---|---|
| Boş sorgu | `python -m app.cli ask ""` | anlaşılır mesaj | |
| Sadece boşluk | `python -m app.cli ask "   "` | anlaşılır mesaj | |
| Çok uzun sorgu | 2000 karakterlik metin | çökmez | |
| İlgisiz sorgu | `ask "fotosentez kloroplast"` | "belgelerde yok" | |
| Boş veritabanı | `FRAG_DB_PATH=/tmp/bos.db ... ask "x"` | ne yapması gerektiğini söyler | |

**Değerlendirme ölçütü:** Hiçbiri Python traceback'i basmıyor. Her biri
kullanıcıya **ne yapması gerektiğini** söylüyor.

---

### A5.5 -- Performans profili çıkar

**Amaç:** Darboğazı tahmin etmeyip ölçmek.

**Adımlar:**
1. 10 soru seç. Her biri için `answer.retrieval_seconds` ve
   `answer.generation_seconds` değerlerini kaydet:
   ```python
   from foundry_rag import RagPipeline, Settings
   s = Settings.from_env()
   with RagPipeline(s) as rag:
       for q in sorular:
           a = rag.answer(q)
           print(f"{a.retrieval_seconds:.3f}\t{a.generation_seconds:.3f}\t{q[:40]}")
   ```
2. Ortalamayı ve en yavaş/en hızlı soruyu raporla.
3. Hangisi toplam sürenin yüzde kaçı?

**Değerlendirme ölçütü:** Öğrenci "üretim darboğaz" sonucuna **kendi
ölçümüyle** varıyor, ders notundan okuyarak değil.

---

### A5.6 -- Kaynaklılık denetimini kullan

**Amaç:** Getirme doğruyken üretimin çöp olabileceğini görmek.

**Adımlar:**
1. Foundry Local ile bir soru sor ve kaynaklılık raporunu incele:
   ```bash
   FRAG_MIN_SIMILARITY=0.40 python -m app.cli --backend foundry \
     ask "Kosinüs benzerliği neden vektörün uzunluğundan etkilenmez?"
   ```
2. Çıktının sonundaki `Kaynaklilik: %..` satırını ve `[mod: ...]` etiketini oku.
3. Aynı soruyu `FRAG_ANSWER_MODE=generative` ile sor ve karşılaştır.

**Bu projede ölçülen:** Getirme mükemmeldi (doğru parça 1. sırada, güven 0.741)
ama üretilen 15 cümlenin **hiçbiri** doğrulanamadı. Kaynaklılık %0 çıktı ve
`auto` mod devreye girip alıntıya düştü.

**Değerlendirme ölçütü:** Öğrenci, getirme metriklerinin iyi olmasının cevabın
iyi olduğu anlamına gelmediğini bir örnekle gösterebiliyor.

---

### A5.7 -- Kalite kapısını kır

**Amaç:** CI'ın neden gerektiğini deneyerek anlamak.

**Adımlar:**
1. Önce geçtiğini gör:
   ```bash
   python eval/evaluate.py --backend hashing --no-save --gate
   echo "çıkış kodu: $?"        # 0 olmalı
   ```
2. Şimdi getirmeyi kasten bozup tekrar çalıştır:
   ```bash
   FRAG_TOP_K=1 python eval/evaluate.py --backend hashing --no-save --gate
   echo "çıkış kodu: $?"        # 1 olmalı
   ```
3. `.github/workflows/ci.yml` içindeki "Retrieval quality gate" adımını bul.

**Cevabını yaz:** Birim testler bu düşüşü neden yakalayamazdı?

**Değerlendirme ölçütü:** Öğrenci "testler kodun bozulduğunu yakalar, kalite
kapısı **kalitenin** düştüğünü yakalar" ayrımını kendi cümleleriyle kurabiliyor.

---

### A5.8 -- Takımlar arası çapraz test

**Amaç:** Kendi sorularına göre ayarlanmış bir sistemin yabancı sorularda nasıl
davrandığını görmek.

**Adımlar:**
1. Başka bir takımın bilgi tabanını al, indeksle.
2. **Kendi** sorularını sor. Çoğu cevaplanamaz olacak — sistem reddediyor mu?
3. O takımın sorularını kendi bilgi tabanına sor.
4. İki yönde de reddetme doğruluğunu ölç.

**Değerlendirme ölçütü:** Sistem yabancı sorularda uydurmuyor. Uyduruyorsa eşik
kendi setine aşırı uyarlanmış (overfit) demektir.

---

## 3. Haftanın çıktı kriteri

- [ ] `eval/questions.json` en az 43 soru içeriyor (10'u öğrenci tarafından eklendi)
- [ ] `eval/results.jsonl` en az 5 kayıtlı çalıştırma içeriyor
- [ ] Kalibrasyon tablosu çıkarıldı ve optimum eşik `.env` dosyasına yazıldı
- [ ] Kenar durumu tablosu (A5.4) dolduruldu
- [ ] Performans profili raporlandı, darboğaz belirlendi
- [ ] `python eval/evaluate.py --gate` geçiyor
- [ ] Bulgular raporu yazıldı: hangi ayar neyi ne kadar değiştirdi

---

## 4. Sık yapılan hatalar

**Sadece cevaplanabilir soru koymak.** En kolay ve en yanıltıcı hata. Böyle bir
setle her zaman %100 alırsın ve sistemin uydurup uydurmadığını hiç öğrenemezsin.

**K'yı büyütüp Recall'e sevinmek.** Recall K ile birlikte tanım gereği artar.
Anlamlı olan, K sabitken Recall'ün artmasıdır.

**Tek çalıştırmaya bakmak.** `eval/results.jsonl` bu yüzden var. "Geçen haftakinden
iyi mi?" sorusuna geçmiş kayıt olmadan cevap verilemez.

**Eşiği bir kez ayarlayıp unutmak.** Korpus veya model değiştiğinde eşik eskir.
Bu projede tam olarak bu oldu ve reddetme doğruluğu %12.5'e düştü.

**Getirme bozukken üretimi ayarlamaya çalışmak.** Sistem doğru parçayı
getiremiyorsa istem mühendisliği yapmanın faydası yoktur. Önce Recall.

---

## 5. Hafta 6'ya hazırlık

Elindeki sayılar final sunumunun omurgasıdır. Hafta 6'da bunları bir rapora ve
demoya dönüştüreceksin. Şimdiden şunları bir yere kaydet:

- kalibrasyon tablosu ve seçtiğin eşik
- yalnız-vektör ile hibrit karşılaştırması
- performans profili
- kaynaklılık denetiminin bir uydurmayı yakaladığı somut örnek

Son madde sunumun en çarpıcı kısmı olacak.
