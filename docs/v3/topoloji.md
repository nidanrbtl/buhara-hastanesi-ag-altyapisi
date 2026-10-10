# Topoloji (v3)

## Şema

```mermaid
flowchart TB
    subgraph INTERNET["İnternet (benzetim)"]
        DISPC["DIS-PC<br/>192.0.2.10"]
        ISP["ISP<br/>Router-PT"]
        INETSRV["INTERNET-SRV<br/>198.51.100.10<br/>web + genel DNS"]
    end

    subgraph KENAR["Kenar"]
        EDGE["EDGE (2911)<br/>NAT, dış erişim listesi<br/>203.0.113.2"]
        DMZ["DMZ-WEB<br/>192.168.60.10"]
    end

    subgraph CEKIRDEK["Çekirdek (3. katman, HSRP + OSPF)"]
        CORE1["CORE1 (3560)<br/>HSRP etkin, STP kök<br/>DHCP .100-.149"]
        CORE2["CORE2 (3560)<br/>HSRP yedek<br/>DHCP .150-.199"]
    end

    subgraph ERISIM["Erişim (2. katman)"]
        ACC1["ACC-KAT1 (2960)<br/>VLAN 10, 20, 70"]
        ACC2["ACC-KAT2 (2960)<br/>VLAN 30, 40, 80, 90"]
        ACCS["ACC-SRV (2960)<br/>VLAN 50"]
    end

    subgraph KAT1["Kat 1"]
        DOK["PC-DOKTOR<br/>VLAN 10"]
        HEM["PC-HEMSIRE<br/>VLAN 20"]
        TIB["TIBBI-CIHAZ<br/>VLAN 70"]
    end

    subgraph KAT2["Kat 2"]
        IDA["PC-IDARI<br/>VLAN 30"]
        BT["PC-BT<br/>VLAN 40"]
        MIS["PC-MISAFIR<br/>VLAN 90"]
        KAM["KAMERA<br/>VLAN 80"]
    end

    subgraph SUNUCU["Sunucular (VLAN 50)"]
        DNS["DNS01 .10"]
        SRV["SRV01 .20<br/>hasta bilgi sistemi"]
        LOG["LOG01 .30<br/>syslog + NTP"]
        NVR["NVR01 .40<br/>kamera kaydı"]
    end

    DISPC --- ISP
    INETSRV --- ISP
    ISP ---|"seri hat 203.0.113.0/30"| EDGE
    EDGE ---|"Gi0/2"| DMZ
    EDGE ---|"10.0.0.0/30"| CORE1
    EDGE ---|"10.0.0.4/30"| CORE2
    CORE1 ===|"EtherChannel Po1<br/>2 x Gigabit"| CORE2
    CORE1 --- ACC1
    CORE1 --- ACC2
    CORE1 --- ACCS
    CORE2 -.- ACC1
    CORE2 -.- ACC2
    CORE2 -.- ACCS
    ACC1 --- DOK
    ACC1 --- HEM
    ACC1 --- TIB
    ACC2 --- IDA
    ACC2 --- BT
    ACC2 --- MIS
    ACC2 --- KAM
    ACCS --- DNS
    ACCS --- SRV
    ACCS --- LOG
    ACCS --- NVR
```

Kesikli çizgiler, erişim anahtarlarının ikinci çekirdeğe (CORE2) giden yedek hatlarıdır. Her erişim anahtarı iki çekirdeğe de bağlıdır; aradaki döngüyü Spanning Tree (STP) keser. STP, anahtarlar arasındaki yedek kabloların döngü oluşturmasını önlemek için bir yolu bekletir ve asıl yol kesilince onu açar. CORE1 bütün VLAN'larda kök anahtar olacak şekilde ayarlanmıştır (öncelik 4096; CORE2 8192). ACC-KAT1'de VLAN 10 için doğrulandı: CORE1'e giden port `Root FWD`, CORE2'ye giden port `Altn BLK` ([kanıt](kanit/acc-kat1-stp-port-guvenligi.txt)). Diğer iki erişim anahtarında aynı denetim yapılmadı.

## Packet Tracer görünümü

![buhara-v3.pkt mantıksal görünüm](ekran-goruntuleri/00-topoloji.jpg)

Görüntü, `packet-tracer/buhara-v3.pkt` dosyası açıldıktan ve bağlantılar oturduktan sonra alınmıştır.

## Katmanlar ve görevleri

| Katman | Cihazlar | Görev |
|---|---|---|
| İnternet (benzetim) | ISP, INTERNET-SRV, DIS-PC | Hastane dışını temsil eder; NAT'ı ve dışarıdan erişimi sınamak için vardır |
| Kenar | EDGE, DMZ-WEB | Adres çevirisi (NAT), dışarıdan gelen trafiğin süzülmesi, dışa açık sunucunun iç ağdan ayrılması |
| Çekirdek | CORE1, CORE2 | VLAN'lar arası yönlendirme, erişim listeleri, ağ geçidi yedekliliği (HSRP), DHCP |
| Erişim | ACC-KAT1, ACC-KAT2, ACC-SRV | Uç cihazların bağlandığı portlar, port güvenliği |

Adresler ve port eşlemeleri için bkz. [adres planı](adres-plani.md).
