# Embedding ve Vektör Arama

## Embedding Nedir?

Embedding, bir metin parçasının anlamını temsil eden sayı dizisidir (vektör).
Örneğin 384 boyutlu bir embedding, metni 384 tane ondalıklı sayıdan oluşan bir
listeye dönüştürür. Bu dönüşümü yapan modele **embedding modeli** denir.

Embedding'in kritik özelliği şudur: **anlamca benzer metinler, vektör uzayında
birbirine yakın konumlanır.** "Kedi mırlıyor" ile "Kedi ses çıkarıyor" cümlelerinin
vektörleri birbirine yakınken, "Vergi beyannamesi son tarihi" cümlesinin vektörü
uzakta kalır.

## Anahtar Kelime Aramasından Farkı

Klasik anahtar kelime aramasında sorgudaki kelimelerin belgede geçmesi gerekir.
"Otomobil fiyatları" araması, "araba ücretleri" yazan bir belgeyi bulamaz.
Embedding tabanlı **anlamsal arama** ise kelimeler farklı olsa bile anlam
yakınlığını yakalar. RAG'in getirme adımının anahtar kelime aramasından üstün
olmasının sebebi budur.

## Kosinüs Benzerliği

İki vektörün ne kadar benzer olduğunu ölçmek için en yaygın yöntem **kosinüs
benzerliğidir**. İki vektör arasındaki açının kosinüsünü hesaplar:

    benzerlik(A, B) = (A · B) / (||A|| * ||B||)

Burada `A · B` nokta çarpımı, `||A||` ise vektörün uzunluğudur (normu). Sonuç
genellikle -1 ile 1 arasındadır:

- **1'e yakın:** metinler anlamca çok benzer
- **0 civarı:** metinler ilgisiz
- **Negatif:** metinler zıt yönde (metin embedding'lerinde nadiren görülür)

Kosinüs benzerliği vektörün uzunluğunu değil yönünü karşılaştırdığı için, uzun ve
kısa metinleri adil biçimde karşılaştırır. Uzunluğun etkisini tamamen ortadan
kaldırmak için vektörler önceden **normalize** edilir (birim uzunluğa getirilir).
Normalize edilmiş vektörlerde kosinüs benzerliği, basit nokta çarpımına eşittir ve
hesaplama belirgin biçimde hızlanır.

## Vektör Arama Nasıl Çalışır?

RAG'in getirme adımı şu sırayla işler:

1. Bilgi tabanındaki her metin parçası için önceden bir embedding üretilir ve
   saklanır. Bu işlem bir kez yapılır ve **indeksleme** olarak adlandırılır.
2. Kullanıcı soru sorduğunda, sorunun embedding'i **aynı model ile** üretilir.
3. Sorunun vektörü ile saklanan tüm vektörler arasındaki benzerlik hesaplanır.
4. En yüksek benzerliğe sahip ilk K parça (top-K) seçilir ve bağlam olarak
   döndürülür.

**Çok önemli kural:** İndeksleme ve sorgu aşamasında mutlaka aynı embedding modeli
kullanılmalıdır. Farklı modellerin vektör uzayları uyumsuzdur; karıştırıldığında
benzerlik skorları anlamsız çıkar. Bu yüzden veritabanına hangi modelle
indekslendiği bilgisi de kaydedilmelidir.

## Kaba Kuvvet Arama ve Ölçeklenme

Küçük bilgi tabanlarında (birkaç bin parçaya kadar) tüm vektörleri belleğe alıp
hepsiyle tek tek benzerlik hesaplamak yeterlidir. Buna **kaba kuvvet (brute force)
arama** denir. NumPy ile matris çarpımı olarak yazıldığında birkaç bin vektör
milisaniyeler içinde taranır.

Bilgi tabanı yüz binlerce parçaya çıktığında kaba kuvvet yavaşlar. Bu noktada
**yaklaşık en yakın komşu (ANN)** algoritmaları ve özel vektör veritabanları devreye
girer. Ancak bu programın ölçeğinde kaba kuvvet hem yeterli hem de öğrenmesi çok
daha kolaydır.

## Top-K Seçimi

Kaç parça getirileceği (K) bir denge meselesidir:

- **K çok küçükse:** doğru cevabı içeren parça kaçırılabilir.
- **K çok büyükse:** bağlam penceresi dolar, alakasız metin modelin dikkatini
  dağıtır ve cevap kalitesi düşer.

Küçük yerel modellerde 3 ile 5 arası bir K genellikle iyi çalışır. Ayrıca bir
**benzerlik eşiği** koymak faydalıdır: eşiğin altındaki parçalar hiç getirilmez,
böylece bilgi tabanında karşılığı olmayan sorularda model "bilmiyorum" diyebilir.
