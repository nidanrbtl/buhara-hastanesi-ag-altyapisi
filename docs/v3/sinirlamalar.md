# Bilinen sınırlamalar (v3)

Bu sayfa, tasarımın yapmadığı ya da benzetimin gösteremediği şeyleri listeler. Buradaki maddeler eksik değil, bilerek belgelenmiş sınırlardır.

## Bu bir benzetimdir

- **Benzetim sonucu üretim kanıtı değildir.** Bütün testler Cisco Packet Tracer 9.0.1'de yapıldı. Gerçek donanımda zamanlamalar, komut desteği ve hata davranışı farklı olabilir. Bu depoda başarım, kapasite ya da herhangi bir standarda uyum iddiası yoktur.
- **Kişisel verilerin korunmasıyla ilgili bir uyum iddiası yoktur.** Ağ bölümlendirmesi böyle bir uyumun yalnızca küçük bir teknik parçası olabilir; tek başına hiçbir şeyi kanıtlamaz.
- **İki ortam birbirine bağlı değildir.** Packet Tracer benzetimi ile VirtualBox'taki Windows Server laboratuvarı ayrı çalışır. Packet Tracer'daki DNS01, Windows sunucusu değildir.
- **İnternet tarafı temsilidir.** ISP, INTERNET-SRV ve DIS-PC yalnızca NAT'ı ve dışarıdan erişimi sınamak için vardır. ISP yönlendiricisi hastaneye ait olmadığı için sıkılaştırılmadı.
- **Benzetim saati gerçek saat değildir.** Packet Tracer'ın saati bilgisayarın yüküne göre yavaşlayıp hızlanabilir; test sonuçlarındaki saniyeler cihaz kayıtlarından alınmıştır ve gerçek donanım için ölçüm sayılmaz.
- **Saat gerçek zamana bağlı değildir.** NTP kaynağı LOG01'in kendi saatidir. Cihazların birbiriyle eşit saat göstermesi sınandı; saatin doğru olması sınanmadı.

## Packet Tracer 9.0.1'in kabul etmediği komutlar

`% Invalid input` veren komutlarda ısrar edilmedi; eşdeğeri seçildi ya da eksiklik buraya yazıldı.

| Komut | Nerede | Yerine ne yapıldı |
|---|---|---|
| `standby <grup> preempt delay minimum <sn>` | 3560 | HSRP gecikmesi yerine OSPF bağlantı türü değiştirildi (tasarım kararı 9) |
| `ip ospf network point-to-point` (SVI üzerinde) | 3560, Vlan100 | Yalnızca yönlendirilmiş portlarda uygulandı; çekirdekler arası VLAN yayın türünde kaldı |
| ACL'de `eq ntp` | 3560 | `eq 123` |
| `terminal length 0` | denenen cihazlarda | Çıktılar sayfa sayfa okundu ya da yapılandırma dosyaya aktarıldı |
| `show ... \| include ...` | denenen cihazlarda | Süzme yapılmadan okundu |
| `show running-config interface <ad>` | denenen cihazlarda | Tam yapılandırma dışa aktarıldı |
| `show ip ospf interface Vlan100` | 3560 | `show ip ospf neighbor` kullanıldı |

Kanıt: [`kanit/ariza-core1-geri-donus.txt`](kanit/ariza-core1-geri-donus.txt) dosyasının sonu.

## Güvenlik

- **Erişim listeleri durum bilgisi tutmaz.** Yanıt trafiği TCP bayrağına ve ICMP türüne bakılarak ayırt edilir (tasarım kararı 7). Bölgeler arasında durum izleyen bir güvenlik duvarı yoktur.
- **Aynı VLAN içindeki trafik süzülmez.** Aynı ağdaki iki cihaz çekirdek anahtara uğramadan konuşur. Örneğin sunucular kendi aralarında, iki doktor bilgisayarı kendi aralarında serbesttir. Bunu sınırlamak için özel VLAN (private VLAN) ya da cihaz üzerindeki güvenlik duvarları gerekir; ikisi de yapılmadı.
- **Konsol hatlarında parola yoktur.** Cihaza fiziksel olarak ulaşan biri kullanıcı kipine girebilir (yetkili kip için `enable secret` gerekir). Cihazların kilitli bir odada olduğu varsayıldı.
- **Merkezi kimlik doğrulama yoktur.** Kullanıcı hesabı her cihazda ayrı tutulur; AAA, RADIUS ya da TACACS+ kullanılmadı. Kimin hangi komutu çalıştırdığı kaydedilmez.
- **Yönlendirme ve yedeklilik protokollerinde kimlik doğrulama yoktur.** OSPF ve HSRP paketleri doğrulanmaz. OSPF kullanıcı ağlarında kapalıdır (`passive-interface default`), ama HSRP kullanıcı VLAN'larında çalışmak zorundadır; aynı VLAN'daki bir cihaz sahte HSRP paketi gönderebilir.
- **DHCP ve ARP sahteciliğine karşı önlem yoktur.** DHCP snooping ve dinamik ARP denetimi yapılandırılmadı.
- **HTTPS yalnızca kural düzeyinde sınandı.** Packet Tracer testleri tarayıcıdan HTTP (80) ile yapıldı. 443 numaralı port için yazılan kurallar denetim aracıyla doğrulandı; sertifika yönetimi kapsam dışıdır.
- **Cihazlar engelledikleri paketlere yanıt verir.** Yasak bir ping'de kaynak cihaz, çekirdek anahtardan ya da kenar yönlendiriciden "Destination host unreachable" yanıtı aldı (internetten gelen ping'de de). Bu, karşı tarafa bir kuralın varlığını belli eder. Gerçek kurulumda bu yanıtlar en azından dış arayüzde kapatılır (`no ip unreachables`); burada kapatılmadı.
- **Kamera akışı HTTP ile temsil edildi.** Gerçek kameraların kullandığı akış protokolleri Packet Tracer'da yoktur.
- **Parolalar.** Depodaki yapılandırma dosyalarında parola yoktur (`DEGISTIR_...`). `.pkt` dosyasının içindeki laboratuvar parolaları yalnızca bu benzetim içindir.

## Yedeklilik

- **Çekirdekler arası bağlantı demeti bazı denemelerden sonra tek yönde çalışmadı.** CORE1'in portları elle kapatılıp açıldığında, bazı denemelerin ardından EtherChannel'ın bir üyesi CORE1'den CORE2'ye çerçeve taşımadı; CORE2 bazı VLAN'larda kendini de ağ geçidi sandı. Cihaz `reload` ile yeniden başlatıldığında ve dosya yeniden açıldığında görülmedi. Sebebi bulunamadı; sabit kip çözmedi. Ayrıntı: [tasarım kararı 5](tasarim-kararlari.md#5-çekirdekler-arası-bağlantı-etherchannel-lacp). Arıza testinden sonra iki çekirdekte `show etherchannel summary` ve `show standby brief` ile denetlemek gerekir.
- **Geçiş kayıpsız değildir.** Bir çekirdek kapandığında ve geri geldiğinde birkaç saniyelik kesinti olur. Ölçülen değerler [test sonuçları](test-sonuclari.md#yedeklilik) sayfasındadır.
- **Tek kalan noktalar.** Kenar yönlendirici (EDGE), ISS bağlantısı, her erişim anahtarının kendisi ve sunucuların her biri (DNS01, SRV01, LOG01, NVR01) yedeksizdir. Yedekli olan: çekirdek anahtar, ağ geçidi, erişim anahtarlarının uplink'i ve çekirdekler arası bağlantı.
- **DHCP havuzları birbirinden habersizdir.** İki çekirdek ayrı aralıklardan dağıtır; kiralar eşitlenmez.
- **Uç cihazlar tek kabloyla bağlıdır.** Sunucularda çift ağ kartı ya da çift anahtara bağlantı yoktur.

## Testlerde görülen ve bilinmesi gereken davranışlar

- **İlk paket kaybı.** Uzun süre konuşmamış iki cihaz arasındaki ilk ping çoğu zaman zaman aşımına uğrar; cihazlar önce birbirinin donanım adresini (ARP) öğrenir. Dosya yeniden açıldıktan sonraki ilk denemede 4 pingin 2'si kayboldu, hemen ardından yapılan ikinci denemede 4'ü de yanıtlandı. Aynı sebeple ilk DNS sorgusu bir kez zaman aşımına uğrayıp ikinci denemede yanıtlandı.
- **Packet Tracer'ın ping özeti bir denemede tutarsızdı.** Dördüncü arıza testinde özet satırı "Sent = 83, Received = 89, Lost = 0" yazdı; oysa ekranda 12 "Request timed out" satırı vardı. O testte kayıp, özet satırından değil satırlar sayılarak raporlandı ([görüntü](ekran-goruntuleri/34-ariza4-istatistik-satiri-tutarsiz.jpg)).
- **İç kullanıcılar siteye dış adresten ulaşmaz.** İç ağdan hastanenin dış adresine (203.0.113.2) erişim yapılandırılmadı ve sınanmadı; iç kullanıcılar web sitesine DMZ adresiyle ya da iç DNS adıyla (`web.buhara.local`) ulaşır.
- **Port güvenliği öğrenilen adresi yapılandırmaya yazar.** Bir bilgisayar değiştirildiğinde eski adresin elle silinmesi gerekir.
