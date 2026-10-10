# Tasarım kararları (v3)

Her karar için üç şey yazılı: ne seçildi, neden seçildi, bedeli ne. Ölçüm ya da gözlem içeren her cümle bir kanıt dosyasına bağlıdır. Bu bir Packet Tracer benzetimidir; buradaki sonuçlar gerçek bir ağın başarım ya da güvenlik kanıtı değildir.

## İlk sürümden farkı

| Konu | v1 / v2 | v3 |
|---|---|---|
| Yönlendirme | Tek yönlendirici, tek trunk (router-on-a-stick) | İki çekirdek anahtarda sanal arayüzler (SVI), aralarında HSRP |
| Yedeklilik | Yok | İkinci çekirdek, çift uplink, EtherChannel, OSPF |
| İnternet | Yok | Kenar yönlendirici, NAT, ISS ve internet benzetimi |
| DMZ | İç ağla aynı yönlendiricide bir VLAN | Kenar yönlendiricide ayrı arayüz, dışarıdan yalnızca 80/443 |
| Ağlar | 6 VLAN | 9 kullanıcı/servis VLAN'ı: tıbbi cihaz, kamera, misafir ve cihaz yönetimi eklendi |
| Kayıt ve saat | Yok | Merkezi syslog ve NTP |
| Kural denetimi | Tek cihazı modelleyen betik | Paketi birden çok cihazdan ve NAT'tan geçiren betik, bozma testleri |

## 1. Çekirdek ve dağıtım tek katmanda

**Karar.** Üç katmanlı (erişim, dağıtım, çekirdek) klasik yapı yerine iki katman kullanıldı: erişim anahtarları ve yönlendirme yapan iki çekirdek anahtar. Bu düzene "collapsed core" denir; dağıtım ve çekirdek görevleri aynı cihazda toplanır.

**Neden.** Tek binalı, üç erişim anahtarlı bir ağda ayrı bir dağıtım katmanı yalnızca cihaz ve arıza noktası ekler.

**Bedeli.** Ağ büyürse (çok sayıda bina ya da kat) çekirdek anahtarların port ve işlem yükü artar; o noktada dağıtım katmanı ayrılır.

## 2. VLAN'lar arası yönlendirme çekirdek anahtarda

**Karar.** Her VLAN'ın ağ geçidi çekirdek anahtardaki bir sanal arayüzdür (SVI). v1'deki tek yönlendirici ve tek trunk kaldırıldı.

**Neden.** v1'de bütün VLAN'lar arası trafik tek bir kablodan iki kez geçiyordu ve o kablo ya da yönlendirici bozulduğunda ağın tamamı duruyordu. Çekirdek anahtar yönlendirmeyi kendi içinde yapar ve ikinci bir çekirdekle yedeklenebilir.

**Bedeli.** Erişim listeleri artık iki cihazda da aynı tutulmak zorunda. Bu, testle güvenceye alındı: `tests/test_acl_check_v3.py` iki çekirdekteki listelerin aynı olduğunu ve her kuralın iki çekirdekte de aynı sonucu verdiğini denetler.

## 3. Ağ geçidi yedekliliği: HSRP, kökü aynı çekirdekte

**Karar.** Her VLAN'da iki çekirdek `.1` sanal adresini HSRP ile paylaşır. CORE1 önceliği 110 ve `preempt` ile etkin, CORE2 yedektir. Spanning Tree kökü de CORE1'dir (öncelik 4096; CORE2 8192).

**Neden.** Bilgisayarlar tek bir ağ geçidi adresi bilir; o adresin sahibi cihaz bozulduğunda adresi diğerinin devralması gerekir. STP kökünü HSRP'de etkin olan cihazla aynı yapmak, 2. katmandaki yolun ve 3. katmandaki ağ geçidinin aynı cihazda buluşmasını sağlar; aksi halde trafik gereksiz yere iki çekirdek arasında dolaşır.

**Bedeli.** Yük paylaşımı yok: olağan durumda bütün VLAN'ların ağ geçidi CORE1'dir. VLAN'ları iki çekirdek arasında bölmek mümkündür ama kök ve HSRP ayarlarını VLAN başına eşlemeyi gerektirir; bu ölçekte karmaşıklığına değmez.

**Kanıt.** [`kanit/core1-ntp-hsrp.txt`](kanit/core1-ntp-hsrp.txt), arıza testleri: [test sonuçları](test-sonuclari.md#yedeklilik).

## 4. Rapid PVST ve uç port korumaları

**Karar.** Bütün anahtarlarda `spanning-tree mode rapid-pvst`. Uç cihaz portlarında PortFast ve BPDU Guard.

**Neden.** Her erişim anahtarı iki çekirdeğe bağlı olduğundan ağda bilerek bırakılmış döngüler var; bunları STP keser. Rapid sürümü yedek yola klasik STP'den daha hızlı geçer. PortFast bilgisayar portlarını beklemeden açar; BPDU Guard o porta yanlışlıkla ya da kötü niyetle bir anahtar takılırsa portu kapatır.

**Kanıt.** Erişim anahtarının bir uplink'i kesildiğinde kayıp olmadı, geri takıldığında 5 paket kayboldu: [test sonuçları](test-sonuclari.md#yedeklilik).

## 5. Çekirdekler arası bağlantı: EtherChannel

YAPILACAK: Packet Tracer'daki son sınamadan sonra yazılacak.

## 6. Erişim listeleri kaynağa en yakın yerde ve varsayılan yasak

**Karar.** Her ağın kuralları, o ağın çekirdek anahtara **giriş** yönünde (SVI üzerinde `in`) uygulanır. Kullanıcı ağlarının listeleri aynı kalıbı izler: önce izin verilen iç hedefler, sonra bütün özel adres aralıklarına `deny`, en sonda kalan her şeye (yani internete) `permit`. Tıbbi cihaz, kamera, sunucu ve yönetim ağlarının listeleri `deny ip any any` ile biter.

**Neden.** Yasak bir paket ağa girdiği ilk noktada düşer; çekirdeği ve diğer hatları meşgul etmez. "Önce izinli iç hedefler, sonra bütün iç adresler yasak" kalıbı, yeni bir iç ağ eklendiğinde eski listelerin o ağa kendiliğinden kapalı kalmasını sağlar; izin vermeyi unutmak, yasaklamayı unutmaktan daha güvenli bir hatadır.

**Bedeli.** Listeler durum bilgisi tutmaz (bkz. karar 7) ve aynı VLAN içindeki iki cihaz arasındaki trafiği süzmez.

**Kanıt.** [`erisim-matrisi.md`](erisim-matrisi.md), [`kanit/core1-acl-sayaclari.txt`](kanit/core1-acl-sayaclari.txt), [test sonuçları](test-sonuclari.md#erişim-kuralları).

## 7. `established` bir güvenlik duvarı değildir

**Karar.** Yanıt trafiği `established` anahtar sözcüğü (TCP'de ACK ya da RST bayrağı taşıyan paketler) ve ICMP `echo-reply` türü ile ayırt edilir. UDP yanıtları için kaynak portuna göre ayrı satır yazılmıştır (DNS yanıtı, NTP yanıtı).

**Neden.** Çekirdekteki 3560 anahtarlar bağlantı durumunu izleyerek süzme yapamaz; orada yönlü kural yazmanın yolu budur. Kenar yönlendiricide de aynı yöntem kullanıldı; durum izleyen bir çözüm (ayrı bir güvenlik duvarı cihazı ya da yönlendiricinin bölge tabanlı güvenlik duvarı özelliği) bu çalışmanın kapsamı dışında bırakıldı.

**Bedeli.** Liste bağlantının gerçekten içeriden başlatılıp başlatılmadığını bilmez; yalnızca paketin bayrağına bakar. ACK bayrağını elle koyan biri kuralın "yanıt" kısmından geçebilir (bağlantı kuramaz ama paket ulaşır). Gerçek bir hastane ağında bölgeler arasına durum izleyen bir güvenlik duvarı konur. Bu yüzden bu depoda "güvenlik duvarı" sözcüğü kullanılmıyor.

## 8. İnternet ve DMZ ayrı bir kenar yönlendiricide

**Karar.** NAT, dış erişim listesi ve DMZ, çekirdekten ayrı bir yönlendiricidedir (EDGE). DMZ bir VLAN değil, EDGE'in ayrı bir arayüzüdür.

- İnternete yalnızca dört personel ağı ve misafir ağı çıkabilir (`NAT-IZINLI` listesi). Sunucular, tıbbi cihazlar, kameralar ve cihaz yönetimi ağı NAT listesinde yoktur.
- Dışarıdan yalnızca 203.0.113.2 adresinin 80 ve 443 numaralı portları DMZ-WEB'e yönlendirilir (sabit port eşlemesi).
- DMZ sunucusu hiçbir yere bağlantı başlatamaz (`ACL-DMZ-GIRIS`).

**Neden.** DMZ'deki sunucu internete açık olduğu için ele geçirilme olasılığı en yüksek cihazdır. Onu çekirdekten ayrı bir cihazın arkasına koymak, iç ağa ulaşmak isteyen bir paketin iki ayrı cihazın kuralından geçmesini gerektirir. Tıbbi cihazların NAT listesinde olmaması ikinci bir kattır: çekirdekteki kural yanlışlıkla gevşetilse bile bu cihazların paketleri internete çıkarken çevrilmez.

**Bedeli.** EDGE tektir; bozulursa internet ve DMZ erişimi kesilir (iç ağ çalışmaya devam eder). ISS bağlantısı da tektir.

**Kanıt.** [`kanit/edge-nat.txt`](kanit/edge-nat.txt), [test sonuçları](test-sonuclari.md#nat-internet-ve-dmz).

## 9. Kenar yönlendirici iki çekirdeğe de bağlı; yollar OSPF ile

**Karar.** EDGE her çekirdeğe ayrı bir yönlendirilmiş bağlantıyla (`/30`) bağlıdır. Yolları OSPF dağıtır; EDGE varsayılan yolu `default-information originate` ile duyurur. Çekirdeklerde `passive-interface default` vardır: OSPF yalnızca EDGE'e giden bağlantıda ve çekirdekler arası geçiş VLAN'ında konuşur, kullanıcı ağlarına OSPF paketi gönderilmez.

**Neden.** Sabit yollarla bir çekirdek kapandığında EDGE'in dönüş trafiğini diğerine çevirmesi elle müdahale ister. OSPF komşusunu kaybettiğinde yolu kendisi kaldırır.

**Ölçümle bulunan sorun ve düzeltmesi.** İlk arıza testinde CORE1 geri geldiğinde HSRP ağ geçidini 2-4 saniyede geri aldı, ama OSPF komşuluğu ancak yaklaşık 35 saniye sonra kuruldu. Arada CORE1 ağ geçidiydi ama internete giden yolu bilmiyordu; paketler "Destination host unreachable" yanıtıyla düştü. Sebep, Ethernet bağlantılarında OSPF'in varsayılan olarak "yayın ağı" gibi davranıp bir seçim süresi beklemesiydi. Yalnızca iki cihazın bulunduğu uplink'lerde `ip ospf network point-to-point` ile bu bekleme kaldırıldı. Son testte OSPF komşuluğu HSRP'den 5-7 saniye sonra kuruldu.

Gerçek IOS'ta aynı sorunu çözmenin bir yolu daha vardır: `standby preempt delay` ile HSRP'nin ağ geçidini geri almasını geciktirmek. Packet Tracer 9.0.1 bu komutu kabul etmedi.

**Kanıt.** [`kanit/ariza-core1-geri-donus.txt`](kanit/ariza-core1-geri-donus.txt), [`kanit/ariza4-core1-yeniden-yukleme-sonrasi.txt`](kanit/ariza4-core1-yeniden-yukleme-sonrasi.txt), [test sonuçları](test-sonuclari.md#yedeklilik).

## 10. ISS bağlantısı seri hat

**Karar.** EDGE ile ISP arasındaki bağlantı, EDGE'e eklenen HWIC-2T modülündeki seri porttur.

**Neden.** Cisco 2911'in üç Gigabit portu vardır ve üçü de doludur: iki çekirdek ve DMZ. Dördüncü bağlantı için modül eklemek gerekti.

**Bedeli.** Seri hat gerçek kurulumlarda artık pek kullanılmaz; burada yalnızca "ISS'e giden ayrı bir arayüz" görevini görür. Hız ya da başarımla ilgili hiçbir çıkarım yapılmamalıdır.

## 11. DHCP çekirdeklerde, havuz ikiye bölünmüş

**Karar.** Beş kullanıcı ağının adres havuzu iki çekirdek arasında bölündü: CORE1 `.100-.149`, CORE2 `.150-.199`. Sunucular, tıbbi cihazlar, kameralar ve ağ cihazları elle adreslidir.

**Neden.** Adres dağıtımı tek bir cihaza bağlı kalırsa o cihaz kapandığında yeni bağlanan bilgisayarlar adres alamaz. Aralıkları bölmek, iki cihazın birbirinden habersiz aynı adresi vermesini önler. Erişim kuralları sabit adreslere yazıldığı için sunucu tarafı elle adreslidir (v1'deki "sunucu DHCP'den adres alıyor, kural sabit adrese yazılmış" hatası bu yüzden tekrarlanmadı).

**Bedeli.** İki havuz birbirinin kiralarını bilmez ve her biri adreslerin yarısını kullanabilir. Gerçek bir ağda bu iş için yedekli çalışan bir DHCP hizmeti (örneğin iki sunucu arasında kira eşitlemesi) tercih edilir.

## 12. Misafir ağı yalnızca internete çıkar

**Karar.** Misafir ağından iç ağların hiçbirine (DNS ve DMZ dahil) paket gidemez; misafirlere DNS olarak internetteki sunucu verilir. Bilgi İşlem ağı da misafir ağına bağlanamaz.

**Neden.** Misafir cihazları kurumun denetiminde değildir. İç DNS'e erişim bile iç sunucu adlarının öğrenilmesine yol açar. Yalıtımın iki yönlü olması, yönetim bilgisayarlarının denetimsiz bir ağa bağlantı açmasını da engeller.

**Kanıt.** [test sonuçları](test-sonuclari.md#erişim-kuralları).

## 13. Tıbbi cihazlar ve kameralar tek hedefe konuşur

**Karar.** Tıbbi cihaz ağı yalnızca SRV01'e, kamera ağı yalnızca NVR01'e, yalnızca web portlarından bağlanabilir. İkisi de internete çıkamaz.

**Neden.** Bu tür cihazların yazılımını güncellemenin zor olduğu varsayıldı; bu yüzden ele geçirilseler bile ulaşabilecekleri yer tek bir sunucuyla sınırlandı.

**Bedeli.** Kamera akışı gerçekte RTSP gibi bir protokolle taşınır; Packet Tracer'da bu servis olmadığı için bağlantı HTTP ile temsil edildi.

## 14. Cihaz yönetimi

**Karar.** Altı ağ cihazında: yalnızca SSH sürüm 2 (`transport input ssh`), yerel kullanıcı, `enable secret`, bütün vty hatlarında (0-4 ve 5-15) yalnızca Bilgi İşlem ağına izin veren `access-class`, giriş uyarısı (banner). Erişim anahtarlarının yönetim adresleri ayrı bir VLAN'dadır (99).

**Neden.** Telnet parolayı açık metin taşır. `access-class`, yol üzerindeki bir kural gevşese bile cihazın kendisinin yalnızca yönetim ağını kabul etmesini sağlar. İki vty aralığının ikisi de yapılandırıldı, çünkü yalnızca ilk beş hattı koruyup kalanını unutmak bilinen bir hatadır; denetim aracı her vty bloğunu ayrı ayrı sınar.

**Bedeli.** Kullanıcı hesapları her cihazda ayrı tutulur; merkezi kimlik doğrulama (AAA, RADIUS ya da TACACS+) yoktur. Konsol hatlarında parola yoktur (bkz. [sınırlamalar](sinirlamalar.md)).

**Kanıt.** [test sonuçları](test-sonuclari.md#cihaz-yönetimi).

## 15. Erişim portları

**Karar.** Uç cihaz portlarında port güvenliği (en çok 2 MAC adresi, `sticky`, ihlalde `restrict`). Kullanılmayan bütün portlar kapalı ve boş bir VLAN'da (999). Trunk hatlarında etiketsiz VLAN da 999'dur ve her trunk yalnızca gereken VLAN'ları taşır. VTP `transparent` kipindedir.

**Neden.** Boş bir porta takılan cihaz ağa girememeli. `restrict`, ihlal eden adresin paketlerini düşürür ve sayar ama portu kapatmaz; böylece yanlış bir cihaz takıldığında asıl cihazın bağlantısı kesilmez. Etiketsiz VLAN'ın kullanıcı VLAN'larından farklı olması, etiket atlatma (VLAN hopping) saldırısının bilinen bir biçimini engeller. VTP'nin kapalı olması, ağa eklenen bir anahtarın VLAN listesini silmesini önler.

**Bedeli.** `sticky` ile öğrenilen adresler yapılandırmaya yazılır; bir bilgisayar değiştirildiğinde eski adresin elle silinmesi gerekir. En çok 2 adres, tek bilgisayarın yanında ikinci bir cihaza (örneğin telefon) yer bırakır; daha sıkı bir ortamda 1 yapılır.

## 16. Merkezi kayıt ve saat

**Karar.** Altı ağ cihazı kayıtlarını LOG01'e (syslog) gönderir ve saatini LOG01'den (NTP) alır. Kayıtlarda milisaniyeli zaman damgası açıktır.

**Neden.** Bir olay birden çok cihazda iz bırakır; kayıtlar tek yerde ve aynı saatle durmazsa sıralamak mümkün olmaz. Cihaz yeniden başladığında kendi kayıtları silinir; sunucudaki kopya kalır.

**Bedeli.** LOG01 tektir. Benzetimde saat kaynağı LOG01'in kendi saatidir; gerçek zamana bağlı değildir.

**Kanıt.** [`ekran-goruntuleri/32-log01-syslog-kayitlari.jpg`](ekran-goruntuleri/32-log01-syslog-kayitlari.jpg), [`kanit/core1-ntp-hsrp.txt`](kanit/core1-ntp-hsrp.txt).

## 17. Kurallar iki ayrı yolla doğrulanır

**Karar.** Erişim kuralları hem Packet Tracer'da elle (ping, tarayıcı, SSH) hem de `tools/acl_check_v3.py` ile sınandı. Araç, cihazlardan dışa aktarılan yapılandırmayı okur ve matristeki bütün kaynak, hedef ve servis üçlülerini (izinli olmayanlar dahil, 1109 deneme) yürütür.

**Neden.** Elle test yalnızca denediğiniz bağlantıyı doğrular; "yasak olması gereken ama açık kalmış" bir bağlantıyı bulmak için hepsini denemek gerekir. Araç bunu saniyeler içinde yapar. Buna karşılık araç bir modeldir; komutun cihazda gerçekten kabul edildiğini ancak cihaz gösterir.

**İki yöntemin birbirini yakaladığı yerler.**

- Araç, cihazdan alınan yapılandırmada NTP kurallarının eksik olduğunu buldu. Sebep: Packet Tracer `eq ntp` yazımını kabul etmemiş, bu satırlar cihaza girmemişti ve uzun bir yapıştırma sırasında fark edilmemişti. Kurallar `eq 123` ile yeniden yazıldı; ardından cihazların saati eşitlendi.
- Bozma testleri (yapılandırmayı bilerek bozup aracın fark edip etmediğine bakan testler) aracın bir eksiğini buldu: sabit NAT satırı silindiğinde araç dış web erişimini hâlâ açık sayıyordu. Araç düzeltildi.

**Kanıt.** `python -m unittest discover -s tests`, [`tests/test_acl_check_v3.py`](../../tests/test_acl_check_v3.py).

## 18. Parolalar depoda yok

**Karar.** `configs/v3/` altındaki dosyalar cihazlardan dışa aktarılan metindir; parola özetleri `tools/yapilandirma_temizle.py` ile `DEGISTIR_...` yer tutucularına çevrilmiştir. Bir test, bu klasörde parola özeti kalmadığını denetler.

**Bedeli.** `packet-tracer/buhara-v3.pkt` dosyasının içinde laboratuvar için atanmış parolalar bulunur (bkz. [kurulum](../../README.md)). Bunlar yalnızca bu benzetim için üretilmiş değerlerdir; başka hiçbir yerde kullanılmamalıdır.
