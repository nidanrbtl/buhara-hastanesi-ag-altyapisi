# Test sonuçları (v3)

Bütün testler Cisco Packet Tracer 9.0.1'de, `packet-tracer/buhara-v3.pkt` üzerinde yapıldı. Her satırda beklenen sonuç, gözlenen sonuç ve kanıt dosyası var. Kanıtı olmayan hiçbir sonuç yazılmadı; sınanmayan şeyler sayfanın sonunda ayrıca listelendi.

Kanıt türleri: `ekran-goruntuleri/` altındaki görüntüler ve `kanit/` altındaki, cihaz konsolundan kopyalanmış metinler. Saatler cihaz saatidir (benzetim saati), gerçek saat değildir.

## Yöntem

- Bağlantı testleri uç cihazların komut satırından (`ping`, `nslookup`, `ssh`, `telnet`) ve web tarayıcısından yapıldı. Yalnızca ping ile yetinilmedi, çünkü kuralların çoğu porta göre ayrım yapıyor: örneğin doktor SRV01'in web sayfasını açabilir ama ona ping atamaz.
- "Engellendi" sonucunun iki görünümü var: ping'de çekirdek anahtardan gelen `Destination host unreachable` yanıtı, tarayıcıda ve SSH'de zaman aşımı.
- Aynı kurallar ayrıca denetim aracıyla, cihazlardan dışa aktarılan yapılandırma üzerinde sınandı (sayfanın sonunda).

## Temel bağlantı

| # | Deneme | Beklenen | Gözlenen | Kanıt |
|---|---|---|---|---|
| T1 | PC-DOKTOR DHCP'den adres alır | 192.168.10.100-199 arası adres, ağ geçidi .1 | 192.168.10.100, ağ geçidi 192.168.10.1 | [02](ekran-goruntuleri/02-doktor-ipconfig-agGecidi-ping-srv01-ping-engelli.jpg) |
| T2 | Beş DHCP ağının her birinde kiralama | Her ağda bir kiralama | CORE1'de 10, 20, 30, 40 ve 90 ağlarında `.100` kiralamaları | [`kanit/asama2-core1.txt`](kanit/asama2-core1.txt) |
| T3 | PC-DOKTOR ağ geçidine ping | 4/4 | 4/4 | [02](ekran-goruntuleri/02-doktor-ipconfig-agGecidi-ping-srv01-ping-engelli.jpg) |
| T4 | PC-DOKTOR `nslookup srv01.buhara.local` | 192.168.50.20 | 192.168.50.20 (sunucu 192.168.50.10) | [01](ekran-goruntuleri/01-doktor-nslookup-srv01.jpg) |
| T5 | HSRP: CORE1 bütün VLAN'larda etkin, CORE2 yedek | 9 grupta Active / Standby | 9 grupta Active, yedek `.3` | [`kanit/asama2-core1.txt`](kanit/asama2-core1.txt) |
| T6 | Trunk hatları yalnızca izinli VLAN'ları taşır | Adres planındaki listeler | Po1, Fa0/1, Fa0/2, Fa0/3 listeleri planla aynı, etiketsiz VLAN 999 | [`kanit/core1-etherchannel-trunk.txt`](kanit/core1-etherchannel-trunk.txt) |

## Erişim kuralları

| # | Kaynak | Deneme | Beklenen | Gözlenen | Kanıt |
|---|---|---|---|---|---|
| E1 | PC-DOKTOR | SRV01 web, adla (`http://srv01.buhara.local`) | Açılır | Sayfa açıldı | [04](ekran-goruntuleri/04-doktor-srv01-web-adla.jpg) |
| E2 | PC-DOKTOR | SRV01'e ping | Engellenir | 0/4, `Destination host unreachable` (192.168.10.2) | [02](ekran-goruntuleri/02-doktor-ipconfig-agGecidi-ping-srv01-ping-engelli.jpg) |
| E3 | PC-DOKTOR | Hastane web sitesi (DMZ) | Açılır | Sayfa açıldı | [05](ekran-goruntuleri/05-doktor-dmz-web.jpg) |
| E4 | PC-DOKTOR | CORE1'e SSH (192.168.99.2) | Engellenir | Zaman aşımı | [03](ekran-goruntuleri/03-doktor-internet-ping-ssh-engelli.jpg) |
| E5 | PC-HEMSIRE | SRV01 web | Engellenir | `Request Timeout` | [07](ekran-goruntuleri/07-hemsire-srv01-web-engelli.jpg) |
| E6 | PC-HEMSIRE | Hastane web sitesi (DMZ) | Açılır | Sayfa açıldı | [08](ekran-goruntuleri/08-hemsire-dmz-web.jpg) |
| E7 | PC-IDARI | SRV01 web | Engellenir | Zaman aşımı | [09](ekran-goruntuleri/09-idari-srv01-web-engelli.jpg) |
| E8 | PC-MISAFIR | SRV01, PC-DOKTOR ve DMZ-WEB'e ping | Üçü de engellenir | Üçünde 0/4, `Destination host unreachable` (192.168.90.2) | [10](ekran-goruntuleri/10-misafir-ic-aglar-engelli.jpg) |
| E9 | PC-MISAFIR | İnternet sitesi, adla (`http://www.ornek-site.test`) | Açılır | Sayfa açıldı | [11](ekran-goruntuleri/11-misafir-internet-web-adla.jpg) |
| E10 | TIBBI-CIHAZ | SRV01 web | Açılır | Sayfa açıldı | [12](ekran-goruntuleri/12-tibbi-cihaz-srv01-web.jpg) |
| E11 | TIBBI-CIHAZ | İnternet sunucusuna ve NVR01'e ping | İkisi de engellenir | İkisinde 0/4 | [13](ekran-goruntuleri/13-tibbi-cihaz-internet-nvr-engelli.jpg) |
| E12 | KAMERA | NVR01 web | Açılır | Sayfa açıldı | [14](ekran-goruntuleri/14-kamera-nvr01-web.jpg) |
| E13 | KAMERA | SRV01 web | Engellenir | Zaman aşımı | [15](ekran-goruntuleri/15-kamera-srv01-web-engelli.jpg) |
| E14 | PC-BT | SRV01'e ping | 4/4 | 4/4 | [21](ekran-goruntuleri/21-bt-srv01-ping-misafir-engelli.jpg) |
| E15 | PC-BT | PC-MISAFIR'e ping | Engellenir | Zaman aşımı (görüntüde ilk satır) | [21](ekran-goruntuleri/21-bt-srv01-ping-misafir-engelli.jpg) |

CORE1'deki erişim listelerinin eşleşme sayaçları: [`kanit/core1-acl-sayaclari.txt`](kanit/core1-acl-sayaclari.txt).

## NAT, internet ve DMZ

| # | Kaynak | Deneme | Beklenen | Gözlenen | Kanıt |
|---|---|---|---|---|---|
| N1 | PC-DOKTOR | İnternet sunucusuna ping (198.51.100.10) | Yanıt alır | 3/4 (bir zaman aşımı; bkz. dürüstlük notu 1) | [03](ekran-goruntuleri/03-doktor-internet-ping-ssh-engelli.jpg) |
| N2 | PC-DOKTOR | İnternet sitesi (web) | Açılır | Sayfa açıldı | [06](ekran-goruntuleri/06-doktor-internet-web-nat.jpg) |
| N3 | EDGE | Çeviri tablosu | İç adres 203.0.113.2'ye çevrilir | `192.168.10.100` → `203.0.113.2` kayıtları; 2 sabit, 10 dinamik çeviri | [`kanit/edge-nat.txt`](kanit/edge-nat.txt), [29](ekran-goruntuleri/29-edge-nat-ve-acl-sayaclari.jpg) |
| N4 | DIS-PC | Hastane sitesi, adla (`http://www.buharahastanesi.test`) | Açılır | DMZ-WEB sayfası açıldı | [17](ekran-goruntuleri/17-internetten-hastane-web-adla.jpg) |
| N5 | DIS-PC | Hastanenin dış adresine ping | Engellenir | 0/4 | [18](ekran-goruntuleri/18-internetten-ping-ozel-adres-ssh-engelli.jpg) |
| N6 | DIS-PC | İç adrese ping (192.168.50.20) | Ulaşamaz | 0/4; ISS yönlendiricisi yol bilmiyor | [18](ekran-goruntuleri/18-internetten-ping-ozel-adres-ssh-engelli.jpg) |
| N7 | DIS-PC | Dış adrese SSH | Engellenir | Zaman aşımı | [18](ekran-goruntuleri/18-internetten-ping-ozel-adres-ssh-engelli.jpg) |
| N8 | DMZ-WEB | SRV01, PC-DOKTOR ve internete ping | Üçü de engellenir | Üçünde 0/4 | [16](ekran-goruntuleri/16-dmz-baglanti-baslatamaz.jpg) |
| N9 | DMZ-WEB | Kendi ağ geçidine ping | 4/4 | 4/4 | [16](ekran-goruntuleri/16-dmz-baglanti-baslatamaz.jpg) |

## Cihaz yönetimi

| # | Kaynak | Deneme | Beklenen | Gözlenen | Kanıt |
|---|---|---|---|---|---|
| Y1 | PC-BT | CORE1'e Telnet | Kabul edilmez | Bağlantı açılır açılmaz karşı taraf kapattı | [19](ekran-goruntuleri/19-bt-telnet-kapali-ssh-core1.jpg) |
| Y2 | PC-BT | CORE1'e SSH | Oturum açılır, uyarı metni görünür | Oturum açıldı; `show ssh` sürüm 1.99, `aes128-cbc` | [19](ekran-goruntuleri/19-bt-telnet-kapali-ssh-core1.jpg) |
| Y3 | PC-BT | CORE2, ACC-KAT1 ve EDGE'e SSH | Üçünde oturum açılır | Üçünde oturum açıldı | [20](ekran-goruntuleri/20-bt-ssh-core2-acc-edge.jpg) |
| Y4 | PC-DOKTOR | CORE1'e SSH | Engellenir | Zaman aşımı | [03](ekran-goruntuleri/03-doktor-internet-ping-ssh-engelli.jpg) |
| Y5 | DIS-PC | EDGE'in dış adresine SSH | Engellenir | Zaman aşımı | [18](ekran-goruntuleri/18-internetten-ping-ozel-adres-ssh-engelli.jpg) |

ACC-KAT2 ve ACC-SRV'ye SSH oturumu elle açılmadı; bu iki cihazın vty ayarları denetim aracıyla doğrulandı (aşağıda).

## Kayıt ve saat

| # | Deneme | Beklenen | Gözlenen | Kanıt |
|---|---|---|---|---|
| K1 | CORE1 saatini LOG01'den alır | `Clock is synchronized` | Eşitlendi, katman (stratum) 2, kaynak 192.168.50.30 | [`kanit/core1-ntp-hsrp.txt`](kanit/core1-ntp-hsrp.txt) |
| K2 | LOG01'e cihazlardan kayıt düşer | Birden çok cihazdan kayıt | CORE1 (192.168.50.2), CORE2 (192.168.50.3) ve EDGE'den (10.0.0.1, 10.0.0.5) 16 kayıt | [32](ekran-goruntuleri/32-log01-syslog-kayitlari.jpg) |
| K3 | Sunucudaki kayıt saati cihaz saatiyle uyuşur | Aynı dakika | LOG01'de 06:36-06:38 PM, cihaz konsolunda 18:36-18:38 | [32](ekran-goruntuleri/32-log01-syslog-kayitlari.jpg) |

Erişim anahtarlarından (192.168.99.11 ve 192.168.99.13) gelen kayıtlar NTP kurulmadan önceki bir oturumda görüldü; o görüntü saklanmadığı için burada kanıt olarak gösterilmiyor. Erişim anahtarlarının syslog ve NTP trafiğine izin veren kurallar denetim aracıyla doğrulandı.

## Yedeklilik

Yöntem: PC-DOKTOR'dan internet sunucusuna sürekli ping (`ping -t 198.51.100.10`) atılırken arıza oluşturuldu ve kaybolan paketler sayıldı. "Çekirdek arızası" CORE1'in bütün bağlantı portlarının `shutdown` ile kapatılmasıdır; cihazın gücü kesilmedi.

### Çekirdek arızası ve geri dönüş

| # | Durum | Geçişte kayıp | Geri dönüşte kayıp | Toplam | Kanıt |
|---|---|---|---|---|---|
| A1 | İlk kurulum | 6 | 13 | 219 paketten 20 | [22](ekran-goruntuleri/22-ariza1-core1-kapali-yedege-gecis.jpg), [23](ekran-goruntuleri/23-ariza1-geri-donus-kara-delik.jpg), [`kanit/ariza-core1-geri-donus.txt`](kanit/ariza-core1-geri-donus.txt) |
| A2 | Uplink'lerde OSPF noktadan noktaya yapıldıktan sonra | 5 | 7 | 67 paketten 12 | [25](ekran-goruntuleri/25-ariza2-ospf-p2p-sonrasi.jpg), [26](ekran-goruntuleri/26-ariza2-istatistik.jpg) |
| A3 | EtherChannel üyeleri düzeltildikten sonra | 6 | 7 | 88 paketten 13 | [30](ekran-goruntuleri/30-ariza3-etherchannel-sonrasi-istatistik.jpg), [31](ekran-goruntuleri/31-ariza3-etherchannel-sonrasi-kayiplar.jpg) |
| A4 | Dosya kapatılıp yeniden açıldıktan sonra | 5 | 7 | 12 (satır sayılarak) | [33](ekran-goruntuleri/33-ariza4-yeniden-yukleme-sonrasi-kayiplar.jpg), [34](ekran-goruntuleri/34-ariza4-istatistik-satiri-tutarsiz.jpg), [`kanit/ariza4-core1-yeniden-yukleme-sonrasi.txt`](kanit/ariza4-core1-yeniden-yukleme-sonrasi.txt) |

Ne anlama geliyor:

- **Trafik her testte kendiliğinden geri geldi**; hiçbirinde elle müdahale gerekmedi.
- **A1'deki 13 kayıp bir tasarım hatasıydı ve düzeltildi.** CORE1 geri geldiğinde ağ geçidi rolünü 2-4 saniyede aldı ama internete giden yolu yaklaşık 35 saniye sonra öğrendi. Düzeltmeden sonra bu aralık A4'te 5-7 saniyeye indi (tasarım kararı 9).
- **A4'te CORE2 ağ geçidi rolünü arızadan 6-9 saniye sonra devraldı** ([35](ekran-goruntuleri/35-ariza4-core2-hsrp-kayitlari.jpg)). HSRP'nin varsayılan bekleme süresi 10 saniyedir; zamanlayıcılar kısaltılmadı.
- A3'te geçişteki 6 kayıp görüntüde yoktur; toplamdan (13) geri dönüşte görülen 7 çıkarılarak bulunmuştur.
- A1 ve A2 yapılırken çekirdekler arası EtherChannel aslında kurulmamıştı (üyeler "suspended" durumdaydı, tasarım kararı 5); bu iki testin sayıları o durumu yansıtır.

### A4'ten sonra bulunan kusur

YAPILACAK: Packet Tracer'daki son sınamadan sonra tamamlanacak. Bulgu: [`kanit/lacp-uye-ayrik-kaldi-core2.txt`](kanit/lacp-uye-ayrik-kaldi-core2.txt).

### Erişim anahtarının uplink'i

| # | Deneme | Beklenen | Gözlenen | Kanıt |
|---|---|---|---|---|
| U1 | ACC-KAT1'in CORE1'e giden hattı kapatıldı | Trafik diğer hattan sürer | Kayıp yok | [27](ekran-goruntuleri/27-uplink-kesildi-kayip-yok.jpg) |
| U2 | Aynı hat geri açıldı | Kısa kesinti, sonra düzelir | 68 paketten 5'i kayboldu; son 4'ü art arda ve test durdurulduğunda sürüyordu. Hemen ardından yapılan 4 pinglik deneme 4/4 | [28](ekran-goruntuleri/28-uplink-geri-takildi-istatistik.jpg) |

## Araçla doğrulama

```
$ python tools/acl_check_v3.py configs/v3 docs/v3/erisim-matrisi.json
1109/1109 deneme beklendiği gibi (224 izinli, 885 yasak beklentisi)

$ python -m unittest discover -s tests
Ran 54 tests ... OK
```

- 1109 deneme, matristeki 14 uç cihazın birbirine 5 servisle bütün birleşimlerini, ağ geçidi pinglerini, DHCP isteklerini, 6 ağ cihazının SSH yönetimini (her vty bloğu ayrı) ve altyapı akışlarını (syslog, NTP) kapsar. Her deneme iki çekirdeğin de etkin olduğu durum için ayrı ayrı yürütülür.
- Araç, cihazlardan dışa aktarılan yapılandırmayı okur; elle yazılmış bir kopyayı değil.
- Araç bir modeldir: anahtarlamayı, yönlendirme protokolünü ve ARP'yi modellemez. Bu yüzden yukarıdaki elle testlerin yerini tutmaz, onları tamamlar.

## Dürüstlük notları

1. **İlk paket kaybı.** N1'de 4 pingin biri zaman aşımına uğradı. Uzun süre konuşmamış cihazlar arasında ilk paketlerin kaybolması testlerde tekrar tekrar görüldü; sebep adres çözümlemesidir (ARP). En açık örnek dosya yeniden açıldıktan hemen sonradır: ilk denemede 2/4, arkasından yapılan aynı denemede 4/4 ([36](ekran-goruntuleri/36-yeniden-acilis-sonrasi-ilk-ping.jpg)).
2. **Ada göre ilk web denemesi bir kez başarısız oldu.** Tarayıcıda adla yapılan ilk denemelerden biri açılmadı, yinelendiğinde açıldı. Sebebi ayrıca incelenmedi; ilk DNS sorgusunun zaman aşımına uğraması ile uyumludur.
3. **EDGE'de SSH oturumundan çıkış.** EDGE'deki SSH oturumunda `exit` yazıldıktan sonra istemci "Connection timed out" iletisi gösterdi ([20](ekran-goruntuleri/20-bt-ssh-core2-acc-edge.jpg)). Oturum açılmış ve komut istemi gelmişti; ileti çıkış anına aittir.
4. **A4'te Packet Tracer'ın özet satırı yanlıştı** ("Sent = 83, Received = 89, Lost = 0"). Kayıp, ekrandaki zaman aşımı satırları sayılarak yazıldı.
5. **`show ssh` sürümü 1.99 gösteriyor.** Cihazlarda `ip ssh version 2` ayarlı olmasına karşın Packet Tracer oturum sürümünü 1.99 olarak yazdı; aynı çıktıda "No SSHv1 server connections running" satırı da var ([19](ekran-goruntuleri/19-bt-telnet-kapali-ssh-core1.jpg)). Gözlendiği gibi aktarıldı, yorumlanmadı.
6. **Geçiş kayıpsız değildir.** Her çekirdek arızasında 5-6, her geri dönüşte 7 paket kayboldu (düzeltmelerden sonra).

## Sınanmayanlar

- CORE2'nin arızası (yalnızca CORE1'in arızası sınandı).
- EDGE'in ya da ISS bağlantısının arızası (yedeği yok; bkz. [sınırlamalar](sinirlamalar.md)).
- Tarayıcıdan HTTPS (443). Kurallar araçla doğrulandı.
- Port güvenliği ihlali (porta üçüncü bir adres bağlanması) ve BPDU Guard'ın tetiklenmesi. Ayarların cihazda olduğu yapılandırma dosyalarından görülebilir; davranışları sınanmadı.
- İki çekirdekten aynı anda DHCP kiralaması ve CORE1 kapalıyken CORE2'den adres alma.
- Yük altında davranış. Benzetim başarım ölçmez.
