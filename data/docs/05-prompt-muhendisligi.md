# Prompt (İstem) Mühendisliği

## İstem Nedir?

İstem, dil modeline gönderilen metindir. Modelin davranışını belirleyen tek girdi
odur. Aynı model, farklı istemlerle çok farklı kalitede cevaplar üretir. Bu yüzden
RAG sisteminde getirme adımı kadar istem tasarımı da belirleyicidir.

## Rol Yapısı: Sistem ve Kullanıcı İstemleri

Sohbet tamamlama API'lerinde mesajların bir **rolü** vardır:

- **system:** Modele kim olduğunu ve hangi kurallara uyacağını söyler. Kullanıcıya
  gösterilmez. Davranışı en güçlü şekilde bu mesaj şekillendirir.
- **user:** Kullanıcının sorusu ve modele sunulan bağlam burada yer alır.
- **assistant:** Modelin daha önceki cevapları. Çok turlu sohbette geçmişi taşır.

RAG'de tipik yerleşim şudur: kurallar sistem mesajına, getirilen belge parçaları ile
kullanıcının sorusu ise kullanıcı mesajına yazılır.

## RAG İçin İyi Bir Sistem İstemi

Bir RAG asistanının sistem isteminde şu maddeler mutlaka bulunmalıdır:

1. **Kapsam sınırı:** "Yalnızca sana verilen bağlamı kullan. Kendi genel bilgini
   kullanma." Bu madde halüsinasyonu azaltan en etkili tek cümledir.
2. **Bilmeme izni:** "Cevap bağlamda yoksa, bilmediğini açıkça söyle." Modele
   bilmeme izni vermezseniz, uydurmayı tercih eder.
3. **Kaynak gösterme:** "Her iddianın sonunda hangi kaynaktan geldiğini belirt."
   Cevabın doğrulanabilir olmasını sağlar.
4. **Biçim ve uzunluk:** "Kısa ve net cevap ver." Küçük modeller serbest
   bırakıldığında gereksiz uzun ve tekrarlı yazma eğilimindedir.
5. **Dil:** "Kullanıcının sorduğu dilde cevap ver." Çok dilli kullanımda gereklidir.

## Bağlamı İsteme Yerleştirme

Getirilen parçalar isteme rastgele yapıştırılmaz. İyi bir yerleşim şuna benzer:
her parça numaralandırılır, kaynak dosya adı parçanın başına yazılır ve parçalar
birbirinden açık bir ayraçla ayrılır. Ardından soru gelir. Bu yapı modele hangi
metnin nereden geldiğini net biçimde gösterir ve kaynak göstermesini kolaylaştırır.

Bağlamın soru ile aynı mesajda ve sorudan **önce** verilmesi genellikle daha iyi
sonuç verir; model önce malzemeyi okur, sonra soruyu görür.

## Sıcaklık (Temperature) Ayarı

Sıcaklık, modelin ne kadar yaratıcı davranacağını belirler. 0'a yakın değerlerde
model en olası kelimeyi seçer ve tutarlı, tekrarlanabilir cevaplar üretir. Yüksek
değerlerde çeşitlilik artar ama uydurma riski de artar.

Belgeye dayalı soru-cevap uygulamalarında sıcaklık **düşük** tutulmalıdır (0 ile 0.3
arası). Amaç yaratıcılık değil, verilen metne sadakattir.

## Sık Yapılan Hatalar

- **Bağlamı vermeden soru sormak:** Getirme adımı boş döndüğünde bile modele soru
  sorulursa, model ezberinden uydurur. Boş bağlamda doğrudan "bilmiyorum" dönmek
  daha doğrudur.
- **Çelişkili talimatlar:** "Sadece bağlamı kullan" deyip ardından "genel bilginle
  destekle" demek modeli kararsız bırakır.
- **Aşırı uzun sistem istemi:** Küçük modellerde uzun kurallar listesi bağlam
  penceresini yer ve modelin dikkatini dağıtır. Beş net madde, yirmi belirsiz
  maddeden iyidir.
- **Bağlam penceresini taşırmak:** Getirilen parçaların toplam uzunluğu modelin
  penceresini aşarsa metin sessizce kırpılır ve cevap bozulur. Parça sayısı ve
  parça boyutu bu sınıra göre seçilmelidir.

## İstemi Test Etmek

İstem değişiklikleri gözle değil, sabit bir soru setiyle ölçülmelidir. Aynı soruları
istem değişmeden önce ve sonra çalıştırıp cevapları karşılaştırmak, hangi
değişikliğin gerçekten iyileştirdiğini gösterir. Bu programda bunun için bir
değerlendirme seti kullanılır.
