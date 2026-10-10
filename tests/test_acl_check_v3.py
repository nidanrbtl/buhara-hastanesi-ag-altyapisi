"""
acl_check_v3 betiğinin ve configs/v3 altındaki cihaz yapılandırmalarının testleri.

Çalıştırma (depo kökünden): python -m unittest discover -s tests

İki tür test var:
1. Depodaki gerçek yapılandırmalar erişim matrisiyle uyuşuyor mu?
2. Yapılandırma bilerek bozulduğunda (bir kural silinince, bir liste arayüzden
   kaldırılınca) betik bunu yakalıyor mu? Yakalamıyorsa "hepsi geçti" sonucunun
   bir anlamı olmaz; bu yüzden her bozma için ayrı test yazıldı.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from ipaddress import IPv4Address as IP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import acl_check_v3 as v3  # noqa: E402
import yapilandirma_temizle  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "v3"
MATRIX = json.loads((ROOT / "docs" / "v3" / "erisim-matrisi.json").read_text(encoding="utf-8"))
HOSTS = {name: IP(address) for name, address in MATRIX["cihazlar"].items()}
PUBLIC = IP(MATRIX["disaridan_gorunen"]["HASTANE-WEB-DIS"])


def read_texts() -> dict[str, str]:
    return {name: (CONFIG_DIR / f"{name}.cfg").read_text(encoding="utf-8") for name in MATRIX["ag_cihazlari"]}


def build(texts: dict[str, str]) -> v3.Network:
    devices = {name: v3.load_device(name, text) for name, text in texts.items()}
    cores = [d for name, d in devices.items() if name.startswith("CORE")]
    others = [d for name, d in devices.items() if not name.startswith("CORE") and name != "EDGE"]
    return v3.Network(cores, devices["EDGE"], others)


def failures(texts: dict[str, str]) -> list[dict]:
    return [row for row in v3.run_matrix(build(texts), MATRIX) if not row["ok"]]


def labels(rows: list[dict]) -> str:
    return "\n".join(row["label"] for row in rows)


def acl_bodies(text: str) -> dict[str, list[str]]:
    """Yapılandırmadaki adlı erişim listelerini (remark satırları hariç) döndürür."""
    bodies: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        match = re.match(r"^ip access-list (?:extended|standard) (\S+)", line)
        if match:
            current = bodies.setdefault(match.group(1), [])
        elif line.startswith(" ") and current is not None:
            if not line.strip().startswith("remark"):
                current.append(line.strip())
        else:
            current = None
    return bodies


class RealConfigTests(unittest.TestCase):
    """Depodaki yapılandırmalar: Packet Tracer'dan dışa aktarılan, parolası temizlenmiş dosyalar."""

    @classmethod
    def setUpClass(cls):
        cls.texts = read_texts()
        cls.network = build(cls.texts)
        cls.core1, cls.core2 = cls.network.cores
        cls.rows = v3.run_matrix(cls.network, MATRIX)

    def test_whole_matrix_matches(self):
        bad = [row for row in self.rows if not row["ok"]]
        self.assertEqual(bad, [], f"Matrisle uyuşmayan denemeler:\n{labels(bad)}")

    def test_matrix_is_exhaustive_enough(self):
        # Varsayılan yasak: izinli denemelerden çok daha fazla yasak denemesi olmalı.
        permitted = sum(row["expected"] for row in self.rows)
        self.assertGreater(len(self.rows), 1000)
        self.assertGreater(len(self.rows) - permitted, permitted * 3)

    def test_doctor_reaches_application_but_cannot_ping_or_ssh_it(self):
        srv = HOSTS["SRV01"]
        doctor = HOSTS["PC-DOKTOR"]
        for core in self.network.cores:
            self.assertTrue(self.network.tcp(doctor, srv, 80, core).allowed)
            self.assertFalse(self.network.ping(doctor, srv, core).allowed)
            self.assertFalse(self.network.tcp(doctor, srv, 22, core).allowed)

    def test_nurse_and_admin_cannot_reach_application_server(self):
        for name in ("PC-HEMSIRE", "PC-IDARI"):
            for core in self.network.cores:
                self.assertFalse(self.network.tcp(HOSTS[name], HOSTS["SRV01"], 80, core).allowed, name)

    def test_guest_reaches_internet_only(self):
        guest = HOSTS["PC-MISAFIR"]
        for core in self.network.cores:
            self.assertTrue(self.network.tcp(guest, HOSTS["INTERNET-SRV"], 80, core).allowed)
            for inside in ("PC-DOKTOR", "PC-BT", "DNS01", "SRV01", "DMZ-WEB", "KAMERA"):
                self.assertFalse(self.network.ping(guest, HOSTS[inside], core).allowed, inside)
                self.assertFalse(self.network.tcp(guest, HOSTS[inside], 80, core).allowed, inside)

    def test_it_cannot_reach_guest_network(self):
        # Yönetim ağı misafir ağına da bağlanamaz: yalıtım iki yönlüdür.
        for core in self.network.cores:
            self.assertFalse(self.network.ping(HOSTS["PC-BT"], HOSTS["PC-MISAFIR"], core).allowed)

    def test_medical_devices_and_cameras_have_single_destination(self):
        for core in self.network.cores:
            self.assertTrue(self.network.tcp(HOSTS["TIBBI-CIHAZ"], HOSTS["SRV01"], 80, core).allowed)
            self.assertFalse(self.network.tcp(HOSTS["TIBBI-CIHAZ"], HOSTS["NVR01"], 80, core).allowed)
            self.assertFalse(self.network.tcp(HOSTS["TIBBI-CIHAZ"], HOSTS["INTERNET-SRV"], 80, core).allowed)
            self.assertTrue(self.network.tcp(HOSTS["KAMERA"], HOSTS["NVR01"], 80, core).allowed)
            self.assertFalse(self.network.tcp(HOSTS["KAMERA"], HOSTS["SRV01"], 80, core).allowed)

    def test_dmz_cannot_start_connections(self):
        for core in self.network.cores:
            for target in ("SRV01", "DNS01", "PC-BT", "INTERNET-SRV"):
                self.assertFalse(self.network.tcp(HOSTS["DMZ-WEB"], HOSTS[target], 80, core).allowed, target)

    def test_internet_sees_only_the_web_ports(self):
        outside = HOSTS["DIS-PC"]
        for core in self.network.cores:
            self.assertTrue(self.network.tcp(outside, PUBLIC, 80, core).allowed)
            self.assertTrue(self.network.tcp(outside, PUBLIC, 443, core).allowed)
            self.assertFalse(self.network.tcp(outside, PUBLIC, 22, core).allowed)
            self.assertFalse(self.network.ping(outside, PUBLIC, core).allowed)
            self.assertFalse(self.network.tcp(outside, HOSTS["SRV01"], 80, core).allowed)

    def test_every_vty_block_is_ssh_only_with_access_class(self):
        devices = [*self.network.cores, self.network.edge, *self.network.others]
        self.assertEqual(len(devices), 6)
        for device in devices:
            self.assertGreaterEqual(len(device.vty_blocks), 2, device.name)  # vty 0 4 ve 5 15
            for block in device.vty_blocks:
                self.assertEqual(block["transport"], ["ssh"], f"{device.name} vty {block['hatlar']}")
                self.assertEqual(block["access_class"], "ACL-SSH-YONETIM", f"{device.name} vty {block['hatlar']}")

    def test_both_cores_carry_identical_access_lists(self):
        # HSRP'de hangi çekirdek etkin olursa olsun aynı kural uygulanmalı.
        one, two = acl_bodies(self.texts["CORE1"]), acl_bodies(self.texts["CORE2"])
        self.assertEqual(sorted(one), sorted(two))
        for name in one:
            if name == "ACL-YONETIM":
                continue  # komşu çekirdeğin adresi doğal olarak farklı olabilir; aşağıda davranışla sınanıyor
            self.assertEqual(one[name], two[name], name)

    def test_every_user_and_server_svi_has_an_inbound_list(self):
        for core in self.network.cores:
            for zone, network in MATRIX["bolgeler"].items():
                if zone == "DMZ":
                    continue  # DMZ çekirdekte değil, EDGE üzerinde
                interface = core.interface_for(IP(network.split("/")[0]) + 10)
                self.assertIsNotNone(interface, f"{core.name} {zone}")
                self.assertTrue(interface.acl_in, f"{core.name} {zone} arayüzünde giriş listesi yok")

    def test_no_password_material_in_repository_configs(self):
        for path in sorted(CONFIG_DIR.glob("*.cfg")):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(yapilandirma_temizle.LEFTOVER.search(text), path.name)
            for line in text.splitlines():
                if re.match(r"^(enable secret|username \S+ secret) ", line):
                    self.assertIn("DEGISTIR_", line, path.name)


class MutationTests(unittest.TestCase):
    """Yapılandırma bozulunca betik hata vermeli. Her test tek bir bozmayı sınar."""

    def setUp(self):
        self.texts = read_texts()

    def mutate(self, names: list[str], old: str, new: str) -> None:
        for name in names:
            self.assertIn(old, self.texts[name], f"{name} içinde beklenen satır yok: {old!r}")
            self.texts[name] = self.texts[name].replace(old, new)

    def test_baseline_has_no_failures(self):
        self.assertEqual(failures(self.texts), [])

    def test_guest_list_removed_from_interface(self):
        self.mutate(["CORE1", "CORE2"], " ip access-group ACL-MISAFIR in\n", "")
        bad = labels(failures(self.texts))
        self.assertIn("PC-MISAFIR -> SRV01", bad)
        self.assertIn("PC-MISAFIR -> PC-BT", bad)

    def test_list_removed_on_one_core_only_is_reported_as_inconsistent(self):
        self.mutate(["CORE2"], " ip access-group ACL-HEMSIRE in\n", "")
        rows = failures(self.texts)
        self.assertTrue(rows)
        self.assertTrue(any(row["allowed"] is None for row in rows), "çekirdekler arası tutarsızlık bildirilmedi")

    def test_internet_inbound_list_removed(self):
        self.mutate(["EDGE"], " ip access-group ACL-INTERNET-GIRIS in\n", "")
        self.assertIn("DIS-PC", labels(failures(self.texts)))

    def test_dmz_list_removed(self):
        self.mutate(["EDGE"], " ip access-group ACL-DMZ-GIRIS in\n", "")
        self.assertIn("DMZ-WEB ->", labels(failures(self.texts)))

    def test_telnet_enabled_on_one_device(self):
        text = self.texts["ACC-KAT1"]
        self.assertIn(" transport input ssh\n", text)
        self.texts["ACC-KAT1"] = text.replace(" transport input ssh\n", " transport input telnet ssh\n", 1)
        self.assertIn("ACC-KAT1 line vty", labels(failures(self.texts)))

    def test_access_class_removed_from_second_vty_block(self):
        # İlk beş hat korunup 5-15 unutulursa da yakalanmalı.
        head, separator, tail = self.texts["CORE1"].partition("line vty 5 15\n")
        self.assertTrue(separator)
        self.texts["CORE1"] = head + separator + tail.replace(" access-class ACL-SSH-YONETIM in\n", "", 1)
        self.assertIn("CORE1 line vty 5 15", labels(failures(self.texts)))

    def test_ntp_rules_missing(self):
        # Packet Tracer "eq ntp" yazımını kabul etmediğinde gerçekte yaşanan durum.
        for name in ("CORE1", "CORE2"):
            kept = [line for line in self.texts[name].splitlines() if "eq 123" not in line]
            self.assertLess(len(kept), len(self.texts[name].splitlines()))
            self.texts[name] = "\n".join(kept) + "\n"
        self.assertIn("ntp", labels(failures(self.texts)))

    def test_static_nat_removed(self):
        self.mutate(["EDGE"], "ip nat inside source static tcp 192.168.60.10 80 203.0.113.2 80", "!")
        self.assertIn("HASTANE-WEB-DIS web", labels(failures(self.texts)))

    def test_guest_network_dropped_from_nat(self):
        self.mutate(["EDGE"], " permit 192.168.90.0 0.0.0.255\n", "")
        self.assertIn("PC-MISAFIR -> INTERNET-SRV", labels(failures(self.texts)))


class SanitizerTests(unittest.TestCase):
    def test_secrets_are_replaced_and_rest_is_untouched(self):
        raw = (
            "hostname X\r\n"
            "enable secret 5 $1$abcd$efghijklmnop\r\n"
            "username btadmin secret 5 $1$abcd$qrstuvwxyz\r\n"
            "line vty 0 4\r\n"
            " password 7 0822455D0A16\r\n"
            " transport input ssh\r\n"
        )
        cleaned = yapilandirma_temizle.clean(raw)
        self.assertNotIn("$1$", cleaned)
        self.assertNotIn("0822455D0A16", cleaned)
        self.assertIn("enable secret DEGISTIR_ENABLE_PAROLASI", cleaned)
        self.assertIn("username btadmin secret DEGISTIR_SSH_PAROLASI", cleaned)
        self.assertIn(" password DEGISTIR_HAT_PAROLASI", cleaned)
        self.assertIn("hostname X\n", cleaned)
        self.assertIn(" transport input ssh\n", cleaned)
        self.assertNotIn("\r", cleaned)

    def test_service_password_encryption_line_is_kept(self):
        self.assertIn("service password-encryption", yapilandirma_temizle.clean("service password-encryption\n"))


if __name__ == "__main__":
    unittest.main()
