# Proje Mimarisi

## Genel Yapı

Bu projedeki tüm bileşenler tek bir bilgisayarda çalışır. Sistem dört katmandan
oluşur:

1. **Arayüz katmanı:** Kullanıcının soru sorduğu yer. Komut satırı arayüzü veya
   basit bir web arayüzü olabilir. Görevi yalnızca soruyu almak ve cevabı
   göstermektir; iş mantığı içermez.
2. **Boru hattı (pipeline) katmanı:** Sorunun embedding'ini üretir, ilgili parçaları
   getirir, istemi kurar ve modeli çağırır. Uygulamanın beyni burasıdır.
3. **Veri katmanı:** SQLite veritabanı. Belge parçalarını, embedding vektörlerini ve
   indeks meta verisini tutar.
4. **Yapay zekâ katmanı:** Foundry Local üzerinden çalışan yerel modeller. Biri
   embedding üretir, diğeri cevabı yazar.

## Veri Akışı

Kullanıcı soru sorduğunda sırasıyla şunlar olur:

    Soru
      -> embedding modeline gönderilir, soru vektörü üretilir
      -> veritabanındaki tüm vektörlerle benzerlik hesaplanır
      -> en benzer K parça seçilir
      -> parçalar + soru bir isteme yerleştirilir
      -> istem yerel dil modeline gönderilir
      -> model cevabı üretir
      -> cevap + kaynak listesi kullanıcıya döner

Bu akışın tamamı yereldedir. Hiçbir adımda internete çıkılmaz.

## İki Ayrı Süreç: İndeksleme ve Sorgulama

Sistemin iki farklı çalışma modu vardır ve bunları karıştırmamak önemlidir.

**İndeksleme (ingest)** nadiren, belgeler değiştiğinde çalışır. Belgeleri okur,
parçalara böler, her parçanın embedding'ini üretir ve veritabanına yazar. Yavaş bir
işlemdir çünkü her parça için model çalıştırılır.

**Sorgulama (query)** her soruda çalışır. Yalnızca sorunun embedding'ini üretir,
gerisi veritabanı okuması ve bir model çağrısıdır. Hızlıdır.

Bu ayrım sayesinde ağır işlem bir kez yapılır, uygulama her açıldığında
tekrarlanmaz.

## Modüllere Ayırma

Kod tek bir dosyada yazılabilir ama büyüdükçe okunamaz hâle gelir. Sorumluluklara
göre ayırmak hem bakımı hem test edilebilirliği kolaylaştırır. Bu projede
kullanılan ayrım şöyledir:

- **config:** Ayarlar. Model adları, veritabanı yolu, parça boyutu, top-K değeri.
  Sabitleri kodun içine dağıtmak yerine tek yerde toplamak, deneme yapmayı
  kolaylaştırır.
- **chunking:** Metni parçalara bölme. Saf fonksiyon, dış bağımlılığı yok, kolayca
  test edilir.
- **store:** Veritabanı işlemleri. Şema oluşturma, parça yazma, parça okuma.
- **backends:** Model çağrıları. Embedding üretme ve sohbet tamamlama.
- **retrieval:** Benzerlik hesabı ve top-K seçimi.
- **pipeline:** Yukarıdakileri birleştirip cevap üreten ana akış.

## Arayüz Bağımsızlığı

İş mantığı arayüzden tamamen ayrı tutulmalıdır. Cevap üreten fonksiyon, kendisini
kimin çağırdığını bilmemelidir. Bu sayede aynı fonksiyon hem komut satırından hem
web arayüzünden hem de testlerden çağrılabilir. Arayüz değiştirmek, iş mantığına
dokunmadan mümkün olur.

## Soyutlama Katmanı: Backend

Model çağrıları doğrudan iş mantığının içine yazılmamalıdır. Araya bir arayüz
konur: "embedding üret" ve "cevap üret" işlemlerini tanımlayan soyut bir sözleşme.
Foundry Local bu sözleşmeyi uygulayan bir gerçeklemedir.

Bu tasarımın faydası nettir: Foundry Local kurulu olmayan bir makinede veya otomatik
testlerde, aynı sözleşmeyi uygulayan sahte (deterministik) bir gerçekleme
kullanılabilir. Böylece uygulama her ortamda çalışır ve testler model indirmeye
ihtiyaç duymaz.

## Hata Durumları

Sağlam bir uygulama şu durumları öngörmelidir: veritabanı boş (henüz indeksleme
yapılmamış), Foundry Local servisi çalışmıyor, model indirilmemiş, sorgu boş, hiçbir
parça benzerlik eşiğini geçmiyor. Her biri için kullanıcıya ne yapması gerektiğini
söyleyen açık bir mesaj döndürmek, sessizce çökmekten çok daha iyidir.
