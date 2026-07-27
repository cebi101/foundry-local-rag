# Microsoft Foundry Local

## Foundry Local Nedir?

Foundry Local, Microsoft'un büyük dil modellerini tamamen kullanıcının kendi
cihazında çalıştırmak için sunduğu uçtan uca yerel yapay zekâ çözümüdür. Hafif bir
çalışma zamanı (runtime), bir model kataloğu, bir komut satırı aracı ve çeşitli
diller için SDK'lardan oluşur.

## Temel Özellikleri

- **Cihaz üstü çıkarım (on-device inference):** Model dosyaları bir kez indirildikten
  sonra tüm çıkarım yerelde yapılır. Bulut hesabı, abonelik veya API anahtarı
  gerekmez.
- **Donanım hızlandırma:** Foundry Local, mevcut donanımı otomatik olarak algılar ve
  uygun model varyantını seçer. CPU, GPU ve NPU hızlandırması desteklenir. Arka
  planda ONNX Runtime GenAI kullanılır.
- **Sıfır ağ çağrısı:** Model indirildikten sonra uygulama tamamen çevrimdışı
  çalışabilir. Veri cihazdan hiç çıkmaz.
- **OpenAI uyumlu API:** Foundry Local yerelde bir HTTP servisi başlatır ve bu servis
  OpenAI'nin sohbet tamamlama (chat completions) API'siyle uyumludur. Bu sayede
  mevcut OpenAI istemci kütüphaneleri, yalnızca `base_url` değiştirilerek
  kullanılabilir.
- **Model kataloğu:** Küçük ve optimize edilmiş modellerden oluşan hazır bir katalog
  sunar. Modeller takma ad (alias) ile çağrılır ve Foundry Local donanıma en uygun
  varyantı kendisi seçer.

## Takma Ad (Alias) Mekanizması

Foundry Local'da modeller `phi-3.5-mini` gibi kısa takma adlarla çağrılır. Aynı
takma ad, farklı donanımlarda farklı fiziksel modele karşılık gelir: CUDA GPU'lu bir
makinede GPU için derlenmiş varyant, GPU'suz bir makinede CPU varyantı seçilir.
Böylece aynı kod farklı bilgisayarlarda değişiklik yapmadan çalışır.

Uygulama kodunda modelin gerçek kimliğini (model id) elde etmek için SDK'nın model
bilgisi sorgulama fonksiyonu kullanılır; API çağrısına bu gerçek kimlik gönderilir.

## Servis Modeli

Foundry Local arka planda bir yerel servis olarak çalışır. SDK yöneticisi
başlatıldığında servis otomatik olarak ayağa kalkar, gerekli model indirilir ve
belleğe yüklenir. Servis, dinamik olarak atanan bir port üzerinde dinler; bu
nedenle uç nokta (endpoint) adresi kodda sabitlenmez, SDK'dan okunur.

## Komut Satırı Aracı

Foundry Local, model ve servis yönetimi için bir komut satırı aracı sunar. Yaygın
kullanılan işlemler şunlardır: kataloğu listelemek, bir modeli indirip çalıştırmak,
önbellekteki modelleri görmek, servisin durumunu sorgulamak ve servisi
başlatıp durdurmak.

## Neden Bu Projede Kullanıyoruz?

Bu programın hedefi öğrencilere bulut maliyeti ve gizlilik endişesi olmadan gerçek
bir yapay zekâ uygulaması yaptırmaktır. Foundry Local, öğrenci dizüstü
bilgisayarlarında ücretsiz ve çevrimdışı çalıştığı için bu hedefe doğrudan hizmet
eder. Öğrenci kredi kartı girmez, kota aşmaz, internet kesildiğinde projesi durmaz.

## Sınırları

Yerelde çalışan modeller, buluttaki dev modellere göre küçüktür. Bu da daha kısa
bağlam penceresi, daha zayıf muhakeme ve İngilizce dışındaki dillerde daha düşük
kalite anlamına gelir. Küçük modellerden iyi sonuç almanın yolu, iyi bir getirme
(retrieval) adımı ve net bir sistem istemidir. Bağlam ne kadar isabetliyse, küçük
modelin cevabı o kadar iyi olur.
