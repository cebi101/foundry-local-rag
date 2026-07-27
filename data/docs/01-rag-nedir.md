# RAG (Retrieval-Augmented Generation) Nedir?

## Tanım

RAG, Türkçesiyle "Getirmeyle Zenginleştirilmiş Üretim", bir dil modelinin cevabını
kendi eğitim verisiyle sınırlı bırakmak yerine, dışarıdan getirilen ilgili belgelerle
destekleyen bir tasarım desenidir. Model soruyu tek başına cevaplamaz; önce soruya
ilgili metin parçaları bulunur, bu parçalar modele bağlam olarak verilir ve model
cevabı bu bağlama dayanarak üretir.

## RAG'in Üç Adımı

RAG kısaltması üç aşamanın baş harflerinden gelir:

1. **Retrieve (Getir):** Kullanıcının sorusu bir vektöre dönüştürülür ve bilgi
   tabanındaki en benzer metin parçaları bulunur. Bu adımda genellikle embedding
   tabanlı anlamsal arama kullanılır.
2. **Augment (Zenginleştir):** Bulunan metin parçaları, kullanıcının sorusuyla
   birlikte modele gönderilecek isteme (prompt) eklenir. Modele "sadece bu bağlamı
   kullan" talimatı verilir.
3. **Generate (Üret):** Dil modeli, zenginleştirilmiş istemi okuyup cevabı üretir.
   Cevap artık modelin ezberine değil, verilen belgelere dayanır.

## RAG Neden Gereklidir?

Büyük dil modellerinin üç temel sınırı vardır ve RAG bu üçünü de hedefler:

- **Halüsinasyon:** Model bilmediği bir konuda kendinden emin şekilde yanlış cevap
  üretebilir. Bağlam verildiğinde bu davranış belirgin biçimde azalır.
- **Bilgi kesme tarihi:** Modelin eğitim verisi belirli bir tarihte durur. Eğitim
  sonrası oluşan bilgileri model bilmez. RAG ile güncel belgeler anlık olarak
  sunulabilir.
- **Özel/kurum içi veri:** Şirket el kitapları, ders notları, iç prosedürler modelin
  eğitim verisinde hiç bulunmaz. RAG bu veriyi modele bağlam olarak taşır.

Ek olarak RAG, cevabın hangi kaynaktan geldiğini göstermeye imkân verir. Buna
**kaynak gösterme (citation)** denir ve kullanıcının cevabı doğrulamasını sağlar.

## RAG ile Fine-Tuning Arasındaki Fark

Fine-tuning, modelin ağırlıklarını yeni veriyle yeniden eğitmektir. Pahalıdır, veri
her değiştiğinde tekrarlanması gerekir ve kaynak gösteremez. RAG ise modele
dokunmaz; sadece istem zamanında bağlam ekler. Belge eklemek veya çıkarmak için
veritabanını güncellemek yeterlidir. Küçük ve sık değişen bilgi tabanları için RAG
neredeyse her zaman doğru tercihtir.

## Basit Bağlam Enjeksiyonundan Farkı

Belgeleri doğrudan isteme yapıştırmak da bir tür bağlam enjeksiyonudur, ancak
modelin bağlam penceresi sınırlıdır. Yüzlerce sayfayı isteme sığdıramazsınız.
RAG'in katkısı, o yüzlerce sayfadan yalnızca soruya ilgili birkaç paragrafı
seçmesidir. Yani RAG = akıllı seçim + bağlam enjeksiyonu.

## Yerel (Offline) RAG

Bu programda kurulan sistemin ayırt edici özelliği tamamen yerel çalışmasıdır.
Hem embedding üretimi hem cevap üretimi kullanıcının kendi bilgisayarında yapılır,
belgeler hiçbir zaman internete çıkmaz. Bu, gizli veriyle çalışan kurumlar ve
internet erişimi kısıtlı ortamlar için kritik bir avantajdır.
