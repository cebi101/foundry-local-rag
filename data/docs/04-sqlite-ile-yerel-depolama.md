# SQLite ile Yerel Veri Depolama

## SQLite Nedir?

SQLite, sunucusuz ve kendi kendine yeten bir SQL veritabanı motorudur. Tüm
veritabanı tek bir dosyada tutulur. Ayrı bir sunucu süreci kurmak, port açmak veya
kullanıcı yetkilendirmesi yapmak gerekmez. Dünyada en yaygın kullanılan veritabanı
motorudur; telefonlarda, tarayıcılarda, uçak sistemlerinde ve sayısız masaüstü
uygulamasında çalışır.

## Bu Projede Neden SQLite?

- **Kurulum yok:** Python'un standart kütüphanesinde `sqlite3` modülü hazır gelir.
  Ek paket kurmaya gerek yoktur.
- **Tek dosya:** Veritabanı `rag.db` gibi tek bir dosyadır. Kopyalanabilir,
  yedeklenebilir, silinip yeniden üretilebilir.
- **Çevrimdışı:** Ağ bağlantısı gerektirmez, projenin tamamen yerel çalışma hedefine
  uygundur.
- **Kalıcılık:** Embedding üretmek yavaş bir işlemdir. Bir kez üretip veritabanına
  yazınca, uygulama her açıldığında yeniden hesaplamaya gerek kalmaz.

## Şema Tasarımı

Bu proje için iki tablo yeterlidir. Birincisi belge parçalarını ve vektörlerini
tutar, ikincisi indeksin hangi ayarlarla üretildiğini kaydeder.

Parça tablosunda bulunması gerekenler:

- **id:** birincil anahtar
- **source:** parçanın geldiği dosyanın adı (kaynak gösterme için şart)
- **chunk_index:** parçanın belge içindeki sırası
- **content:** parçanın ham metni
- **embedding:** vektörün ikili (binary) hâli
- **dim:** vektörün boyut sayısı
- **content_hash:** aynı içeriğin tekrar tekrar indekslenmesini önlemek için

Meta tablosunda ise embedding modelinin adı, vektör boyutu ve parçalama ayarları
saklanır. Böylece indeks ile sorgu arasındaki uyumsuzluk çalışma anında tespit
edilebilir.

## Vektörleri Saklama Yöntemleri

Bir ondalıklı sayı listesini SQLite'a yazmanın üç yolu vardır:

1. **JSON metni:** Okunması kolaydır, gözle incelenebilir. Ancak yer israfıdır ve
   okurken metinden sayıya çevirme maliyeti vardır.
2. **BLOB (ikili):** Vektör doğrudan ham baytlar olarak yazılır. En kompakt ve en
   hızlı yöntemdir. 384 boyutlu bir `float32` vektör tam olarak 1536 bayt tutar.
3. **Ayrı satırlar:** Her boyut için bir satır açmak. Ölçeklenmez, kullanılmaz.

Bu projede **BLOB** tercih edilir. NumPy ile yazma ve okuma tek satırdır: vektör
`float32` tipine çevrilip baytlara dönüştürülür, okurken aynı tiple geri
yorumlanır. Burada dikkat edilmesi gereken tek nokta, yazarken ve okurken **aynı
veri tipinin** kullanılmasıdır; `float32` yazıp `float64` okumak bozuk vektör verir.

## Temel SQL İşlemleri

Öğrencilerin bu projede rahatça kullanması gereken SQL komutları sınırlıdır:
tablo oluşturma, satır ekleme, koşullu sorgulama, sayım ve silme. Karmaşık
birleştirmelere (JOIN) veya alt sorgulara gerek yoktur.

Python'da parametreli sorgu kullanmak önemlidir. Değerleri metin birleştirmeyle
sorguya gömmek yerine yer tutucu kullanılmalıdır; bu hem SQL enjeksiyonunu önler
hem de tip dönüşümlerini doğru yapar.

## İşlem (Transaction) Yönetimi

Yüzlerce parçayı tek tek eklerken her ekleme sonrası veritabanına yazmak yavaştır.
Tüm eklemeleri tek bir işlem içinde yapıp sonunda bir kez onaylamak (commit)
indeksleme süresini belirgin biçimde kısaltır. Python'un `sqlite3` bağlantısı
`executemany` ile toplu ekleme de destekler.

## Yeniden İndeksleme

Belgeler değiştiğinde indeksin güncellenmesi gerekir. En basit ve en güvenli
strateji, veritabanını silip sıfırdan üretmektir. Daha gelişmiş bir yaklaşım,
her parçanın içerik özetini (hash) saklayıp yalnızca değişen parçaları yeniden
işlemektir. Küçük bilgi tabanlarında sıfırdan üretmek genellikle yeterince hızlıdır.
