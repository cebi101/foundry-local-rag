# Belge Parçalama (Chunking)

## Neden Parçalıyoruz?

Bir belgeyi bütün hâlde embedding'e vermek iki sorun doğurur. Birincisi, embedding
modellerinin girdi uzunluğu sınırlıdır; uzun metin sessizce kırpılır. İkincisi ve
daha önemlisi, uzun bir belgenin tek vektörü, belgedeki tüm konuların ortalamasını
temsil eder ve hiçbir konuyu iyi temsil etmez. On sayfalık bir el kitabının tek
vektörü, içindeki spesifik bir soruya isabetli eşleşmez.

Çözüm, belgeyi anlamlı küçük parçalara bölmek ve her parçayı ayrı ayrı
vektörleştirmektir. Böylece getirme adımı, cevabın gerçekten bulunduğu paragrafı
seçebilir.

## Parça Boyutu Dengesi

Parça boyutu seçimi doğrudan cevap kalitesini etkiler:

- **Parçalar çok küçükse:** Bağlam kopar. "Bu yöntem üç adımdan oluşur" cümlesi bir
  parçada, adımlar başka parçada kalırsa model eksik cevap verir.
- **Parçalar çok büyükse:** Getirme isabeti düşer, alakasız metin bağlama karışır ve
  bağlam penceresi boşa harcanır.

Pratikte 300 ile 800 karakter arası (yaklaşık 1-3 paragraf) çoğu belge için iyi
çalışır. Bu programda varsayılan olarak orta bir değer kullanılır ve ayardan
değiştirilebilir.

## Örtüşme (Overlap)

Parçalar keskin sınırlarla bölünürse, sınıra denk gelen bir bilgi ikiye ayrılır ve
hiçbir parçada tam olarak bulunmaz. Bunu önlemek için parçalar arasında **örtüşme**
bırakılır: her parça, bir öncekinin son bir miktar karakterini tekrar içerir.

Tipik örtüşme, parça boyutunun %10 ile %20'si kadardır. Örtüşme depolama ve
hesaplama maliyetini bir miktar artırır ama sınırda kaybolan bilgiyi kurtarır.

## Parçalama Stratejileri

**Sabit uzunlukta bölme:** Metni belirli karakter sayısında keser. Uygulaması en
kolayıdır ama cümlelerin ortasından bölebilir.

**Ayraca göre bölme:** Önce paragraf sınırlarından (boş satır), sonra cümle
sınırlarından böler. Anlam bütünlüğünü daha iyi korur. Bu projede kullanılan
yaklaşım budur: metin önce paragraflara ayrılır, paragraflar hedef boyuta ulaşana
kadar birleştirilir, hedefi tek başına aşan paragraf cümlelerine bölünür.

**Yapıya göre bölme:** Markdown başlıkları, bölüm numaraları gibi belge yapısını
kullanır. Başlık bilgisini her parçanın başına eklemek getirme kalitesini belirgin
biçimde artırır, çünkü parça bağlamından koptuğunda bile hangi bölüme ait olduğu
bilinir.

## Meta Veri Eklemek

Her parçayla birlikte en az şu bilgiler saklanmalıdır: kaynak dosya adı, parçanın
belge içindeki sırası ve varsa başlık. Kaynak dosya adı kaynak gösterme için
zorunludur. Sıra bilgisi, gerekirse komşu parçaları da getirmeye imkân verir.

## Kalite Kontrolü

Parçalama kodu yazıldıktan sonra çıktısı gözle kontrol edilmelidir. Bakılacak
noktalar: parçalar cümle ortasından kesiliyor mu, çok kısa artık parçalar oluşuyor
mu, örtüşme çalışıyor mu, boş parçalar üretiliyor mu. İyi bir kontrol yöntemi,
en kısa ve en uzun beş parçayı yazdırıp incelemektir.

Getirme sonuçları kötüyse ilk şüpheli embedding modeli değil, parçalama
stratejisidir. Bu programda öğrencilerin en sık öğrendiği derslerden biri budur.
