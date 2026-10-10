# Erişim matrisi (v3)

Kural: **bu sayfada yazmayan her bağlantı yasaktır.** Asıl kaynak, makinenin okuyabildiği [`erisim-matrisi.json`](erisim-matrisi.json) dosyasıdır; bu sayfa ondan ve cihaz yapılandırmalarından üretilmiştir.

## Özet

| Kim | Nereye erişebilir | Nereye erişemez |
|---|---|---|
| Doktorlar | Hasta bilgi sistemi (SRV01, yalnızca web), iç DNS, hastane web sitesi (DMZ), internet | Diğer bölümler, diğer sunucular, cihaz yönetimi; SRV01'e ping ve SSH |
| Hemşireler | İç DNS, hastane web sitesi, internet | SRV01 (hasta verisi), diğer bölümler, sunucular |
| İdari personel | İç DNS, hastane web sitesi, internet | SRV01 (hasta verisi), diğer bölümler, sunucular |
| Bilgi İşlem | Bütün iç ağlar, sunucular, DMZ, ağ cihazlarının SSH yönetimi, internet | Misafir ağı |
| Tıbbi cihazlar | Yalnızca SRV01 (web) | İnternet dahil geri kalan her yer |
| Kameralar | Yalnızca NVR01 (web) | İnternet dahil geri kalan her yer |
| Misafirler | Yalnızca internet | İç ağların tamamı (DNS ve DMZ dahil) |
| DMZ web sunucusu | Hiçbir yere bağlantı başlatamaz; yalnızca gelen isteklere yanıt verir | İç ağ ve internet |
| İnternet | Yalnızca hastanenin dış adresinde web (80 ve 443) | İç adresler, SSH, ping |

İki ayrıntı:

- **İdari personel SRV01'e erişemez.** En az yetki ilkesi uygulandı: bu tasarımda hasta verisine yalnızca işi gereği ihtiyacı olduğu varsayılan grup (doktorlar) erişir.
- **Hemşirelerin SRV01'e erişememesi** v1'deki kuralın aynısıdır ve bu depoda bölümler arası ayrımı göstermek için korunmuştur. Gerçek bir hastanede hemşirelerin de hasta kaydına erişmesi beklenir; böyle bir ayrım ağ katmanında değil, uygulamadaki rol yetkileriyle yapılır. Buradaki kural bir gereksinim değil, bir gösterimdir.

## İzinlerin tam listesi ve gerekçeleri

| Kaynak | Hedef | Servisler | Gerekçe |
|---|---|---|---|
| PC-DOKTOR | DNS01 | dns | Ad çözümleme |
| PC-DOKTOR | SRV01 | web, web-tls | Hasta bilgi sistemi uygulaması |
| PC-DOKTOR | DMZ-WEB | web, web-tls | Hastane web sitesi |
| PC-DOKTOR | INTERNET-SRV | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| PC-DOKTOR | DIS-PC | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| PC-HEMSIRE | DNS01 | dns | Ad çözümleme |
| PC-HEMSIRE | DMZ-WEB | web, web-tls | Hastane web sitesi |
| PC-HEMSIRE | INTERNET-SRV | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| PC-HEMSIRE | DIS-PC | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| PC-IDARI | DNS01 | dns | Ad çözümleme |
| PC-IDARI | DMZ-WEB | web, web-tls | Hastane web sitesi |
| PC-IDARI | INTERNET-SRV | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| PC-IDARI | DIS-PC | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| PC-BT | PC-DOKTOR | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | PC-HEMSIRE | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | PC-IDARI | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | DNS01 | ping, web, web-tls, dns, ssh | Yönetim ve ad çözümleme |
| PC-BT | SRV01 | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | LOG01 | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | NVR01 | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | DMZ-WEB | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | TIBBI-CIHAZ | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | KAMERA | ping, web, web-tls, ssh | Yönetim ve sorun giderme |
| PC-BT | INTERNET-SRV | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| PC-BT | DIS-PC | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| TIBBI-CIHAZ | SRV01 | web, web-tls | Cihaz verisini uygulamaya gönderme |
| KAMERA | NVR01 | web, web-tls | Kayıt sunucusuna bağlanma (gerçekte RTSP; benzetimde HTTP ile temsil edilir) |
| PC-MISAFIR | INTERNET-SRV | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| PC-MISAFIR | DIS-PC | ping, web, web-tls, dns, ssh | İnternet (NAT ile) |
| INTERNET-SRV | HASTANE-WEB-DIS | web, web-tls | Dışarıdan yalnızca DMZ web (sabit NAT) |
| DIS-PC | HASTANE-WEB-DIS | web, web-tls | Dışarıdan yalnızca DMZ web (sabit NAT) |

Servis adları: `ping` (ICMP yankı), `web` (TCP 80), `web-tls` (TCP 443), `dns` (UDP 53), `ssh` (TCP 22).

Bunlara ek olarak her ağdaki cihaz kendi ağ geçidine ping atabilir, DHCP kullanan ağlarda adres isteği geçer, ağ cihazları LOG01'e kayıt (UDP 514) ve saat (UDP 123) trafiği gönderir, ağ cihazlarının SSH yönetimi yalnızca Bilgi İşlem ağından yapılır.

## Yapılandırmadan hesaplanan tablo

Aşağıdaki tablo elle yazılmadı; `python tools/acl_check_v3.py configs/v3 docs/v3/erisim-matrisi.json --tablo` komutunun çıktısıdır. Her hücre, depodaki cihaz yapılandırmalarına göre o kaynaktan o hedefe **geçen** servisleri gösterir. "yasak" hiçbir servisin geçmediği anlamına gelir.

| Kaynak \ Hedef | PC-DOKTOR | PC-HEMSIRE | PC-IDARI | PC-BT | DNS01 | SRV01 | LOG01 | NVR01 | DMZ-WEB | TIBBI-CIHAZ | KAMERA | PC-MISAFIR | INTERNET-SRV | DIS-PC | HASTANE-WEB-DIS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **PC-DOKTOR** | - | yasak | yasak | yasak | dns | web, web-tls | yasak | yasak | web, web-tls | yasak | yasak | yasak | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh |  |
| **PC-HEMSIRE** | yasak | - | yasak | yasak | dns | yasak | yasak | yasak | web, web-tls | yasak | yasak | yasak | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh |  |
| **PC-IDARI** | yasak | yasak | - | yasak | dns | yasak | yasak | yasak | web, web-tls | yasak | yasak | yasak | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh |  |
| **PC-BT** | ping, web, web-tls, ssh | ping, web, web-tls, ssh | ping, web, web-tls, ssh | - | ping, web, web-tls, dns, ssh | ping, web, web-tls, ssh | ping, web, web-tls, ssh | ping, web, web-tls, ssh | ping, web, web-tls, ssh | ping, web, web-tls, ssh | ping, web, web-tls, ssh | yasak | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh |  |
| **DNS01** | yasak | yasak | yasak | yasak | - | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh | yasak | yasak | yasak | yasak | yasak | yasak |  |
| **SRV01** | yasak | yasak | yasak | yasak | ping, web, web-tls, dns, ssh | - | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh | yasak | yasak | yasak | yasak | yasak | yasak |  |
| **LOG01** | yasak | yasak | yasak | yasak | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh | - | ping, web, web-tls, dns, ssh | yasak | yasak | yasak | yasak | yasak | yasak |  |
| **NVR01** | yasak | yasak | yasak | yasak | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh | - | yasak | yasak | yasak | yasak | yasak | yasak |  |
| **DMZ-WEB** | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | - | yasak | yasak | yasak | yasak | yasak |  |
| **TIBBI-CIHAZ** | yasak | yasak | yasak | yasak | yasak | web, web-tls | yasak | yasak | yasak | - | yasak | yasak | yasak | yasak |  |
| **KAMERA** | yasak | yasak | yasak | yasak | yasak | yasak | yasak | web, web-tls | yasak | yasak | - | yasak | yasak | yasak |  |
| **PC-MISAFIR** | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | - | ping, web, web-tls, dns, ssh | ping, web, web-tls, dns, ssh |  |
| **INTERNET-SRV** | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | - |  | web, web-tls |
| **DIS-PC** | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak | yasak |  | - | web, web-tls |

Tabloyu okurken:

- Aynı ağdaki iki cihaz (örneğin sunucular kendi aralarında) çekirdek anahtara uğramadan konuşur; erişim listeleri bu trafiği süzmez. Bu bir sınırlamadır, bkz. [bilinen sınırlamalar](sinirlamalar.md).
- Bilgi İşlem satırındaki "ssh" ya da "web", kuralın o trafiğe izin verdiğini gösterir; hedef cihazda o servisin çalıştığını göstermez.
- Son sütun (HASTANE-WEB-DIS, 203.0.113.2) hastanenin internetten görünen adresidir; iç cihazlar siteye bu adresten değil DMZ adresinden ulaşır.

## Doğrulama

`python tools/acl_check_v3.py configs/v3 docs/v3/erisim-matrisi.json` komutu matristeki her kaynak, hedef ve servis üçlüsünü (izinli olanları ve olmayanları) cihaz yapılandırmaları üzerinde yürütür. Son çalıştırmanın özeti:

```
1109/1109 deneme beklendiği gibi (224 izinli, 885 yasak beklentisi)
```

Araç bir benzetimdir; aynı kuralların Packet Tracer'da elle sınanmış sonuçları [test sonuçları](test-sonuclari.md) sayfasındadır.
