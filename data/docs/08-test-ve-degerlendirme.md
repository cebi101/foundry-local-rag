# Test ve Değerlendirme

## Neden Ölçüyoruz?

Bir RAG sisteminin "iyi çalıştığı" gözle bakarak anlaşılmaz. Birkaç soruda güzel
cevap veren sistem, başka sorularda uydurabilir. Ayrıca istem veya parça boyutu
değiştirildiğinde bir yerde iyileşip başka yerde bozulma olur. Bunu görmenin tek
yolu sabit bir soru setiyle düzenli ölçüm yapmaktır.

## İki Ayrı Şeyi Ölçmek

RAG sisteminde iki bileşen ayrı ayrı değerlendirilmelidir:

**Getirme kalitesi:** Doğru parça getirildi mi? Bu, modelden bağımsızdır. Ölçmek
için her test sorusuna, cevabın hangi kaynak dosyada olduğu önceden yazılır. Sonra
getirilen parçaların kaynağı bu beklentiyle karşılaştırılır. Yaygın metrikler:

- **Recall@K:** İlk K parça içinde doğru kaynak var mı?
- **MRR (Ortalama Karşılıklı Sıra):** Doğru kaynak kaçıncı sırada geldi? Birinci
  sırada gelmesi, beşinci sırada gelmesinden değerlidir.

**Üretim kalitesi:** Getirilen doğru parçadan model doğru cevabı çıkarabildi mi?
Getirme başarısızsa üretimi ölçmek anlamsızdır; önce getirme düzeltilmelidir.

## Cevaplanabilir ve Cevaplanamaz Sorular

İyi bir test seti iki tür soru içerir:

1. **Cevaplanabilir sorular:** Cevabı bilgi tabanında bulunan sorular. Sistem doğru
   ve kaynağa dayalı cevap vermelidir.
2. **Cevaplanamaz sorular:** Cevabı bilgi tabanında kesinlikle bulunmayan sorular.
   Sistem "bu bilgi elimdeki belgelerde yok" demelidir.

İkinci grup çoğu zaman atlanır ama en az birincisi kadar önemlidir. Bir RAG
sisteminin en tehlikeli hatası, bilmediği bir konuda kendinden emin şekilde
uydurmasıdır. Cevaplanamaz sorular tam olarak bunu yakalar. Test setinin
yaklaşık üçte biri bu tür sorulardan oluşmalıdır.

## Kenar Durumları

Şunlar da test edilmelidir: boş sorgu, yalnızca boşluktan oluşan sorgu, çok uzun
sorgu, bilgi tabanıyla hiç ilgisi olmayan sorgu, veritabanı boşken sorgu. Bunların
her biri çökme değil, anlaşılır bir mesaj üretmelidir.

## Performans Ölçümü

Yerel modellerde kullanıcı deneyimini belirleyen şey cevap süresidir. Ölçülmesi
gereken üç süre vardır: sorgunun embedding süresi, benzerlik arama süresi ve
modelin cevap üretme süresi. Genellikle üçüncüsü toplamın büyük kısmını oluşturur.

Yavaşlık durumunda başvurulacak çareler sırasıyla: daha az parça getirmek, daha
küçük model kullanmak, embedding'leri önbelleğe almak ve modeli uygulama açılışında
bir kez yükleyip her soruda yeniden yüklememektir.

## Birim Testleri

Değerlendirme setinden ayrı olarak, kodun parçaları da test edilmelidir. Model
gerektirmeden test edilebilecek şeyler: parçalama fonksiyonu (doğru sayıda parça,
doğru örtüşme, boş girdi), veritabanı katmanı (yazılan vektör aynen okunuyor mu),
kosinüs benzerliği (bilinen vektörlerde beklenen sonuç), istem kurma fonksiyonu
(bağlam doğru biçimde yerleşiyor mu).

Bu testlerin model indirmeye ihtiyaç duymaması için sahte bir backend kullanılır.
Sahte backend, metinden deterministik biçimde vektör üretir; aynı metin her zaman
aynı vektörü verir. Böylece testler hızlı, tekrarlanabilir ve çevrimdışı çalışır.

## Sonuçları Kaydetmek

Her değerlendirme çalıştırmasının sonucu bir dosyaya yazılmalıdır: hangi ayarlarla
çalıştırıldı, kaç soru soruldu, kaçı doğru, ortalama süre ne oldu. Bu kayıtlar
olmadan "geçen haftaki hâlinden daha mı iyi?" sorusuna cevap verilemez.
