# Adres planı (v3)

Bu sayfadaki her değer `configs/v3/` altındaki cihaz yapılandırmalarından ya da `docs/v3/erisim-matrisi.json` dosyasından alınmıştır. Tablo ile yapılandırma çelişirse doğru olan yapılandırmadır.

## Ağlar

| VLAN | Ad | Ağ | Ağ geçidi (sanal) | CORE1 | CORE2 | Adres dağıtımı | Erişim listesi |
|---|---|---|---|---|---|---|---|
| 10 | DOKTORLAR | 192.168.10.0/24 | .1 | .2 | .3 | DHCP | ACL-DOKTOR |
| 20 | HEMSIRELER | 192.168.20.0/24 | .1 | .2 | .3 | DHCP | ACL-HEMSIRE |
| 30 | IDARI | 192.168.30.0/24 | .1 | .2 | .3 | DHCP | ACL-IDARI |
| 40 | BILGI-ISLEM | 192.168.40.0/24 | .1 | .2 | .3 | DHCP | ACL-BT |
| 50 | SUNUCULAR | 192.168.50.0/24 | .1 | .2 | .3 | Elle | ACL-SUNUCU |
| 70 | TIBBI-CIHAZLAR | 192.168.70.0/24 | .1 | .2 | .3 | Elle | ACL-TIBBI |
| 80 | KAMERALAR | 192.168.80.0/24 | .1 | .2 | .3 | Elle | ACL-KAMERA |
| 90 | MISAFIR | 192.168.90.0/24 | .1 | .2 | .3 | DHCP | ACL-MISAFIR |
| 99 | CIHAZ-YONETIM | 192.168.99.0/24 | .1 | .2 | .3 | Elle | ACL-YONETIM |
| 100 | CEKIRDEK-GECIS | 10.0.0.8/30 | yok | .9 | .10 | Elle | yok |
| 999 | KULLANILMAYAN | adres yok | | | | | |

- **Ağ geçidi (sanal):** iki çekirdek anahtarın HSRP ile paylaştığı adres. HSRP, iki cihazın tek bir ağ geçidi adresini paylaşıp biri bozulunca diğerinin devralmasını sağlayan protokoldür.
- **VLAN 999:** kullanılmayan portların ve trunk hatlarının etiketsiz (native) VLAN'ının konduğu boş ağdır; hiçbir yere yönlendirilmez.
- **DMZ (192.168.60.0/24)** bir VLAN değildir; kenar yönlendiricinin (EDGE) ayrı bir fiziksel portundadır. DMZ, dışarıya açık sunucunun iç ağdan ayrı tutulduğu bölgedir.

## Yönlendirme bağlantıları

| Bağlantı | Ağ | Uçlar |
|---|---|---|
| CORE1 Fa0/24 – EDGE Gi0/0 | 10.0.0.0/30 | CORE1 10.0.0.2, EDGE 10.0.0.1 |
| CORE2 Fa0/24 – EDGE Gi0/1 | 10.0.0.4/30 | CORE2 10.0.0.6, EDGE 10.0.0.5 |
| CORE1 – CORE2 (VLAN 100, EtherChannel üzerinden) | 10.0.0.8/30 | CORE1 10.0.0.9, CORE2 10.0.0.10 |
| EDGE Gi0/2 – DMZ-WEB | 192.168.60.0/24 | EDGE 192.168.60.1, DMZ-WEB 192.168.60.10 |
| EDGE Se0/0/0 – ISP Se2/0 (seri hat) | 203.0.113.0/30 | EDGE 203.0.113.2, ISP 203.0.113.1 |
| ISP Fa0/0 – INTERNET-SRV | 198.51.100.0/24 | ISP 198.51.100.1, INTERNET-SRV 198.51.100.10 |
| ISP Fa1/0 – DIS-PC | 192.0.2.0/24 | ISP 192.0.2.1, DIS-PC 192.0.2.10 |

İnternet tarafındaki üç ağ (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) belgelerde örnek olarak kullanılmak üzere ayrılmış adres bloklarıdır (RFC 5737); gerçek bir kuruma ait değildir.

OSPF yönlendirici kimlikleri: CORE1 10.255.0.1, CORE2 10.255.0.2, EDGE 10.255.0.3. Hepsi alan 0'dadır.

## Uç cihazlar

| Cihaz | Adres | VLAN | Bağlı olduğu port | Adres kaynağı |
|---|---|---|---|---|
| PC-DOKTOR | 192.168.10.100 | 10 | ACC-KAT1 Fa0/1 | DHCP |
| PC-HEMSIRE | 192.168.20.100 | 20 | ACC-KAT1 Fa0/2 | DHCP |
| TIBBI-CIHAZ | 192.168.70.10 | 70 | ACC-KAT1 Fa0/3 | Elle |
| PC-IDARI | 192.168.30.100 | 30 | ACC-KAT2 Fa0/1 | DHCP |
| PC-BT | 192.168.40.100 | 40 | ACC-KAT2 Fa0/2 | DHCP |
| PC-MISAFIR | 192.168.90.100 | 90 | ACC-KAT2 Fa0/3 | DHCP |
| KAMERA | 192.168.80.10 | 80 | ACC-KAT2 Fa0/4 | Elle |
| DNS01 | 192.168.50.10 | 50 | ACC-SRV Fa0/1 | Elle |
| SRV01 | 192.168.50.20 | 50 | ACC-SRV Fa0/2 | Elle |
| LOG01 | 192.168.50.30 | 50 | ACC-SRV Fa0/3 | Elle |
| NVR01 | 192.168.50.40 | 50 | ACC-SRV Fa0/4 | Elle |
| DMZ-WEB | 192.168.60.10 | (DMZ) | EDGE Gi0/2 | Elle |
| INTERNET-SRV | 198.51.100.10 | (internet) | ISP Fa0/0 | Elle |
| DIS-PC | 192.0.2.10 | (internet) | ISP Fa1/0 | Elle |

DHCP ile adres alan bilgisayarların `.100` adresi, o ağda ilk isteği yanıtlayan çekirdeğin (CORE1) havuzunun ilk adresidir; ölçüm anındaki değerdir, elle verilmiş değildir.

## Sunucu rolleri

| Sunucu | Rol |
|---|---|
| DNS01 | İç ad çözümleme: `srv01`, `dns01`, `log01`, `nvr01.buhara.local` ve `web.buhara.local` (DMZ-WEB) |
| SRV01 | Hasta bilgi sistemi uygulamasını temsil eden web sunucusu |
| LOG01 | Kayıt (syslog) ve saat (NTP) sunucusu |
| NVR01 | Kamera kayıt sunucusunu temsil eden web sunucusu |
| DMZ-WEB | Hastanenin dışarıya açık web sitesi |
| INTERNET-SRV | İnterneti temsil eder: web sunucusu ve genel DNS (`www.ornek-site.test`, `www.buharahastanesi.test`) |

## Ağ cihazlarının yönetim adresleri

| Cihaz | Model | Yönetim adresi | Not |
|---|---|---|---|
| CORE1 | 3560-24PS | 192.168.99.2 | HSRP önceliği 110 (etkin), STP önceliği 4096 (kök) |
| CORE2 | 3560-24PS | 192.168.99.3 | HSRP önceliği 100 (yedek), STP önceliği 8192 |
| ACC-KAT1 | 2960-24TT | 192.168.99.11 | VLAN 10, 20, 70 |
| ACC-KAT2 | 2960-24TT | 192.168.99.12 | VLAN 30, 40, 80, 90 |
| ACC-SRV | 2960-24TT | 192.168.99.13 | VLAN 50 |
| EDGE | 2911 | 10.0.0.1 (CORE1 yönü), 10.0.0.5 (CORE2 yönü) | NAT, DMZ, ISS bağlantısı |
| ISP | Router-PT | yönetilmiyor | İnternet servis sağlayıcıyı temsil eder, hastaneye ait değildir |

## DHCP havuzları

DHCP sunucusu iki çekirdek anahtardır. Her ağın havuzu ikiye bölünmüştür; böylece bir çekirdek kapalıyken diğeri adres dağıtmayı sürdürür ve ikisi aynı adresi vermez.

| Ağ | CORE1 dağıtır | CORE2 dağıtır | Ağ geçidi | DNS |
|---|---|---|---|---|
| 192.168.10.0/24 | .100 – .149 | .150 – .199 | 192.168.10.1 | 192.168.50.10 |
| 192.168.20.0/24 | .100 – .149 | .150 – .199 | 192.168.20.1 | 192.168.50.10 |
| 192.168.30.0/24 | .100 – .149 | .150 – .199 | 192.168.30.1 | 192.168.50.10 |
| 192.168.40.0/24 | .100 – .149 | .150 – .199 | 192.168.40.1 | 192.168.50.10 |
| 192.168.90.0/24 (misafir) | .100 – .149 | .150 – .199 | 192.168.90.1 | 198.51.100.10 |

Misafir ağına iç DNS yerine internetteki DNS verilir; misafirler iç sunucu adlarını çözemez ve iç ağdaki hiçbir adrese paket gönderemez.

## Trunk hatları

Trunk, birden çok VLAN'ı tek kablodan etiketleyerek taşıyan hattır. Her trunk yalnızca gereken VLAN'ları taşır.

| Hat | İzinli VLAN'lar |
|---|---|
| CORE1/CORE2 Fa0/1 – ACC-KAT1 Gi0/1, Gi0/2 | 10, 20, 70, 99 |
| CORE1/CORE2 Fa0/2 – ACC-KAT2 Gi0/1, Gi0/2 | 30, 40, 80, 90, 99 |
| CORE1/CORE2 Fa0/3 – ACC-SRV Gi0/1, Gi0/2 | 50, 99 |
| CORE1 – CORE2 Po1 (Gi0/1 + Gi0/2) | 10, 20, 30, 40, 50, 70, 80, 90, 99, 100 |

Bütün trunk hatlarında etiketsiz VLAN 999'dur. Erişim anahtarlarına giden hatlarda otomatik trunk pazarlığı (DTP) `switchport nonegotiate` ile kapatılmıştır; çekirdekler arası hat elle trunk kipindedir.
