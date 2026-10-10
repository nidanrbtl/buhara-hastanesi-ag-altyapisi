"""
v3 tasarımının erişim kurallarını erişim matrisiyle karşılaştırır.

acl_check.py tek bir yönlendiriciyi modeller. v3'te paket birden fazla cihazdan geçer:
kaynak ağın çekirdek anahtardaki sanal arayüzü (SVI) girişte süzer, internet ve DMZ
trafiği ayrıca kenar yönlendiricinin (EDGE) listelerinden ve NAT'tan geçer. Bu betik
Packet Tracer'dan dışa aktarılan running-config dosyalarını okur, erişim matrisindeki
(docs/v3/erisim-matrisi.json) her kaynak, hedef ve servis üçlüsünü bu cihazlar
üzerinde adım adım yürütür ve sonucu matrisle karşılaştırır. Matriste yazmayan her
bağlantının engellenmesi beklenir.

Kullanım:
    python tools/acl_check_v3.py configs/v3 docs/v3/erisim-matrisi.json
    python tools/acl_check_v3.py configs/v3 docs/v3/erisim-matrisi.json --ayrinti
    python tools/acl_check_v3.py configs/v3 docs/v3/erisim-matrisi.json --tablo

Bu bir IOS benzetimi değildir. Modellenenler: SVI ve arayüz erişim listeleri, vty
access-class, HSRP sanal adresi, PAT ve sabit port yönlendirme. Modellenmeyenler:
anahtarlama (VLAN, trunk, STP), yönlendirme protokolü, ARP ve paket parçalama.
Sonuçların Packet Tracer'da da doğrulanması gerekir (docs/v3/test-sonuclari.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, replace
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acl_check import (  # noqa: E402
    PORT_NAMES,
    Interface,
    Packet,
    RouterConfig,
    Verdict,
    evaluate_acl,
    parse_config,
)

# Packet Tracer bazı portları adıyla yazar; acl_check.py'deki tabloya ekleniyor.
PORT_NAMES.update({"syslog": 514, "ssh": 22})

BROADCAST = IPv4Address("255.255.255.255")
CLIENT_PORT = 50000


# --------------------------------------------------------------------------- cihaz modeli


@dataclass(frozen=True)
class StaticNat:
    protocol: str
    local_ip: IPv4Address
    local_port: int
    global_ip: IPv4Address
    global_port: int


@dataclass
class Device:
    """Bir ağ cihazı: acl_check.py'nin okuduğu yapılandırma ve v3'e özgü ekler."""

    name: str
    config: RouterConfig
    virtual: dict[str, IPv4Address] = field(default_factory=dict)  # arayüz -> HSRP sanal adresi
    nat_inside: set[str] = field(default_factory=set)
    nat_outside: set[str] = field(default_factory=set)
    nat_list: str | None = None
    nat_statics: list[StaticNat] = field(default_factory=list)
    vty_blocks: list[dict] = field(default_factory=list)  # her "line vty" bloğu: access-class ve transport

    def interfaces(self) -> list[Interface]:
        return [i for i in self.config.interfaces.values() if i.network and not i.shutdown]

    def interface_for(self, ip: IPv4Address) -> Interface | None:
        for interface in self.interfaces():
            if ip in interface.network:
                return interface
        return None

    def owns(self, ip: IPv4Address) -> Interface | None:
        for interface in self.interfaces():
            if interface.address == ip:
                return interface
        return None

    def acl(self, name: str | None, packet: Packet) -> Verdict:
        verdict = evaluate_acl(self.config, name, packet)
        return Verdict(verdict.allowed, f"{self.name} {verdict.reason}")


def load_device(name: str, text: str) -> Device:
    device = Device(name, parse_config(text))
    interface: str | None = None
    vty: dict | None = None
    for raw_line in text.splitlines():
        words = raw_line.split()
        if not words or words[0] == "!":
            continue
        if not raw_line.startswith(" "):
            interface = words[1] if words[0] == "interface" else None
            vty = None
            if words[:2] == ["line", "vty"]:
                vty = {"hatlar": " ".join(words[2:]), "access_class": None, "transport": None}
                device.vty_blocks.append(vty)
            if words[:5] == ["ip", "nat", "inside", "source", "list"]:
                device.nat_list = words[5]
            elif words[:5] == ["ip", "nat", "inside", "source", "static"] and len(words) >= 10:
                device.nat_statics.append(StaticNat(
                    words[5], IPv4Address(words[6]), int(words[7]), IPv4Address(words[8]), int(words[9])))
        elif interface:
            if words[0] == "standby" and len(words) >= 4 and words[2] == "ip":
                device.virtual[interface] = IPv4Address(words[3])
            elif words == ["ip", "nat", "inside"]:
                device.nat_inside.add(interface)
            elif words == ["ip", "nat", "outside"]:
                device.nat_outside.add(interface)
        elif vty is not None:
            if words[0] == "access-class" and words[-1] == "in":
                vty["access_class"] = words[1]
            elif words[:2] == ["transport", "input"]:
                vty["transport"] = words[2:]
    return device


# --------------------------------------------------------------------------- ağ modeli


class Network:
    """İki çekirdek anahtar, bir kenar yönlendirici ve yönetim adresi olan diğer cihazlar."""

    def __init__(self, cores: list[Device], edge: Device, others: list[Device] | None = None):
        self.cores = cores
        self.edge = edge
        self.others = others or []

    # ---- yardımcılar

    def owner(self, ip: IPv4Address) -> tuple[Device, Interface] | None:
        for device in [*self.cores, self.edge]:
            interface = device.owns(ip)
            if interface:
                return device, interface
        return None

    def is_virtual(self, ip: IPv4Address) -> bool:
        return any(ip in core.virtual.values() for core in self.cores)

    def outside(self) -> Interface:
        name = next(iter(self.edge.nat_outside))
        return self.edge.config.interfaces[name]

    def public_address(self) -> IPv4Address:
        return self.outside().address

    def zone(self, ip: IPv4Address) -> str:
        """'ic' (çekirdeğe bağlı ağ), 'dmz' (yalnızca kenar yönlendiriciye bağlı) ya da 'internet'."""
        if any(core.interface_for(ip) for core in self.cores):
            return "ic"
        interface = self.edge.interface_for(ip)
        if interface and interface.name not in self.edge.nat_outside:
            return "dmz"
        return "internet"

    def translatable(self, packet: Packet) -> bool:
        """Paketin kaynağı internete çıkarken çevrilebiliyor mu (PAT listesi ya da sabit eşleme)?"""
        if self.edge.nat_list and evaluate_acl(self.edge.config, self.edge.nat_list, packet).allowed \
                and self.edge.nat_list in self.edge.config.acls:
            return True
        return any(s.protocol == packet.protocol and s.local_ip == packet.source
                   and s.local_port == packet.source_port for s in self.edge.nat_statics)

    # ---- tek yönlü paket

    def deliver(self, packet: Packet, active: Device, pat_inside: IPv4Address | None = None) -> Verdict:
        """
        Paketi kaynağından hedefine yürütür. 'active' o anda HSRP'de etkin olan çekirdektir;
        iç ağlardaki cihazlar paketlerini ona gönderir. pat_inside, internetten dönen bir
        yanıtın PAT tablosunda hangi iç cihaza ait olduğunu belirtir.
        """
        source_owner = self.owner(packet.source)
        if source_owner:  # ağ cihazının kendi ürettiği paket kendi listelerinden geçmez
            device = source_owner[0]
            if device is self.edge:
                return self._from_edge(packet, own=True)
            return self._from_core(device, packet)

        zone = self.zone(packet.source)
        if zone == "ic":
            entry = active.interface_for(packet.source)
            if packet.destination in entry.network and packet.destination != BROADCAST:
                target = self.owner(packet.destination)
                if target:  # anahtarın o ağdaki kendi adresi: o anahtarın giriş listesi
                    return target[0].acl(target[1].acl_in, packet)
                if self.is_virtual(packet.destination):
                    return active.acl(entry.acl_in, packet)
                return Verdict(True, "aynı ağ, erişim listesinden geçmez")
            inbound = active.acl(entry.acl_in, packet)
            if not inbound.allowed:
                return inbound
            onward = self._from_core(active, packet)
            return onward if not onward.allowed else Verdict(True, inbound.reason)

        if zone == "dmz":
            entry = self.edge.interface_for(packet.source)
            if packet.destination in entry.network and packet.destination != entry.address:
                return Verdict(True, "aynı ağ, erişim listesinden geçmez")
            inbound = self.edge.acl(entry.acl_in, packet)
            if not inbound.allowed:
                return inbound
            onward = self._from_edge(packet, own=False)
            return onward if not onward.allowed else Verdict(True, inbound.reason)

        return self._from_internet(packet, pat_inside)

    def _from_core(self, core: Device, packet: Packet) -> Verdict:
        """Paket 'core' anahtarının içinde; giriş denetimi yapılmış ya da paket anahtarın kendisinin."""
        destination = packet.destination
        if destination == BROADCAST or core.owns(destination) or destination in core.virtual.values():
            return Verdict(True, f"{core.name} kendisine gelen paket")
        exit_ = core.interface_for(destination)
        if exit_ is None:  # bağlı ağ değil: OSPF ile öğrenilen yol kenar yönlendiriciden geçer
            return self._from_edge(packet, own=False)
        outbound = core.acl(exit_.acl_out, packet)
        if not outbound.allowed:
            return outbound
        target = self.owner(destination)
        if target:  # diğer çekirdeğin ya da kenar yönlendiricinin o ağdaki adresi
            return target[0].acl(target[1].acl_in, packet)
        return Verdict(True, "hedef ağa teslim edildi")

    def _from_edge(self, packet: Packet, own: bool) -> Verdict:
        """Paket kenar yönlendiricinin içinde."""
        destination = packet.destination
        if self.edge.owns(destination):
            return Verdict(True, "EDGE kendisine gelen paket")
        exit_ = self.edge.interface_for(destination)
        if exit_ is not None and exit_.name not in self.edge.nat_outside:
            return self.edge.acl(exit_.acl_out, packet)
        if self.zone(destination) == "ic":  # eşit maliyetli iki yol: hangi çekirdekten giderse gitsin geçmeli
            for core in self.cores:
                verdict = self._from_core(core, packet)
                if not verdict.allowed:
                    return verdict
            return Verdict(True, "çekirdek üzerinden teslim edildi")
        if not own and not self.translatable(packet):
            return Verdict(False, "EDGE: kaynak NAT kapsamında değil, ISS özel adrese dönüş yolu bilmez")
        return self.edge.acl(self.outside().acl_out, packet)

    def _from_internet(self, packet: Packet, pat_inside: IPv4Address | None) -> Verdict:
        outside = self.outside()
        if packet.destination != outside.address:
            return Verdict(False, "internetten özel adrese yol yok (yalnızca EDGE'in dış adresi görünür)")
        inbound = self.edge.acl(outside.acl_in, packet)  # giriş listesi NAT'tan önce uygulanır
        if not inbound.allowed:
            return inbound
        for static in self.edge.nat_statics:
            if (static.protocol, static.global_ip, static.global_port) == \
                    (packet.protocol, packet.destination, packet.destination_port):
                inner = replace(packet, destination=static.local_ip, destination_port=static.local_port)
                onward = self._from_edge(inner, own=False)
                return onward if not onward.allowed else Verdict(True, inbound.reason)
        if pat_inside is not None:
            onward = self._from_edge(replace(packet, destination=pat_inside), own=False)
            return onward if not onward.allowed else Verdict(True, inbound.reason)
        return Verdict(True, f"EDGE'in kendisine ulaştı ({inbound.reason})")

    # ---- iki yönlü alışverişler

    def _reply_route(self, source: IPv4Address, destination: IPv4Address, port: int | None,
                     protocol: str) -> tuple[IPv4Address, IPv4Address, IPv4Address | None, int | None]:
        """Yanıt paketinin (kaynak, hedef, PAT iç adresi, kaynak portu) değerlerini döndürür."""
        if self.zone(source) != "internet" and self.zone(destination) == "internet" \
                and not self.owner(destination):
            return destination, self.public_address(), source, port  # yanıt EDGE'in dış adresine gelir
        if self.zone(source) == "internet" and destination == self.public_address():
            for static in self.edge.nat_statics:
                if (static.protocol, static.global_port) == (protocol, port):
                    return static.local_ip, source, None, static.local_port
        return destination, source, None, port

    def _ends_on_device(self, destination: IPv4Address, port: int | None, protocol: str) -> bool:
        """Paket bir ağ cihazının kendi adresinde mi son buluyor (sabit NAT ile içeri aktarılmıyorsa)?"""
        if not (self.owner(destination) or self.is_virtual(destination)):
            return False
        return not any((s.protocol, s.global_ip, s.global_port) == (protocol, destination, port)
                       for s in self.edge.nat_statics)

    def tcp(self, source: IPv4Address, destination: IPv4Address, port: int, active: Device) -> Verdict:
        syn = self.deliver(Packet("tcp", source, destination, CLIENT_PORT, port), active)
        if not syn.allowed:
            return Verdict(False, f"SYN engellendi - {syn.reason}")
        if port != 22 and self._ends_on_device(destination, port, "tcp"):
            # Paket listelerden geçse bile ağ cihazları yalnızca SSH dinler; örneğin sabit NAT
            # satırı silinirse 203.0.113.2:80 kenar yönlendiricinin kendisinde kalır ve yanıtsızdır.
            return Verdict(False, "ağ cihazının kendi adresi: bu portu dinleyen servis yok")
        r_source, r_destination, pat, r_port = self._reply_route(source, destination, port, "tcp")
        syn_ack = self.deliver(
            Packet("tcp", r_source, r_destination, r_port, CLIENT_PORT, established=True), active, pat)
        if not syn_ack.allowed:
            return Verdict(False, f"SYN-ACK engellendi - {syn_ack.reason}")
        ack = self.deliver(Packet("tcp", source, destination, CLIENT_PORT, port, established=True), active)
        if not ack.allowed:
            return Verdict(False, f"ACK engellendi - {ack.reason}")
        return Verdict(True, syn.reason)

    def udp(self, source: IPv4Address, destination: IPv4Address, port: int, active: Device,
            source_port: int = CLIENT_PORT) -> Verdict:
        query = self.deliver(Packet("udp", source, destination, source_port, port), active)
        if not query.allowed:
            return Verdict(False, f"sorgu engellendi - {query.reason}")
        if self._ends_on_device(destination, port, "udp"):
            return Verdict(False, "ağ cihazının kendi adresi: bu portu dinleyen servis yok")
        r_source, r_destination, pat, r_port = self._reply_route(source, destination, port, "udp")
        answer = self.deliver(Packet("udp", r_source, r_destination, r_port, source_port), active, pat)
        if not answer.allowed:
            return Verdict(False, f"yanıt engellendi - {answer.reason}")
        return Verdict(True, query.reason)

    def udp_one_way(self, source: IPv4Address, destination: IPv4Address, port: int, active: Device) -> Verdict:
        return self.deliver(Packet("udp", source, destination, CLIENT_PORT, port), active)

    def ping(self, source: IPv4Address, destination: IPv4Address, active: Device) -> Verdict:
        request = self.deliver(Packet("icmp", source, destination, icmp_type="echo"), active)
        if not request.allowed:
            return Verdict(False, f"istek engellendi - {request.reason}")
        r_source, r_destination, pat, _ = self._reply_route(source, destination, None, "icmp")
        reply = self.deliver(Packet("icmp", r_source, r_destination, icmp_type="echo-reply"), active, pat)
        if not reply.allowed:
            return Verdict(False, f"yanıt engellendi - {reply.reason}")
        return Verdict(True, request.reason)

    def ssh(self, source: IPv4Address, device: Device, address: IPv4Address, active: Device) -> Verdict:
        """Cihazın kendisine SSH: yol üzerindeki listeler, sonra cihazın vty access-class listesi."""
        path = self.tcp(source, address, 22, active)
        if not path.allowed:
            return Verdict(False, f"yolda engellendi - {path.reason}")
        if device.config.vty_acl is None:
            return Verdict(True, f"{device.name} vty hatlarında access-class yok")
        return device.acl(device.config.vty_acl, Packet("tcp", source, address, CLIENT_PORT, 22))

    def dhcp(self, network: IPv4Network, core: Device) -> Verdict:
        """Adresi olmayan istemcinin yayın isteği o ağın SVI giriş listesinden geçebiliyor mu?"""
        entry = core.interface_for(network.network_address + 10)
        packet = Packet("udp", IPv4Address("0.0.0.0"), BROADCAST, 68, 67)
        return core.acl(entry.acl_in, packet)


def load_network(config_dir: Path, matrix: dict) -> Network:
    def read(name: str) -> Device:
        return load_device(name, (config_dir / f"{name}.cfg").read_text(encoding="utf-8"))

    devices = {name: read(name) for name in matrix["ag_cihazlari"]}
    cores = [d for name, d in devices.items() if name.startswith("CORE")]
    others = [d for name, d in devices.items() if not name.startswith("CORE") and name != "EDGE"]
    return Network(cores, devices["EDGE"], others)


# --------------------------------------------------------------------------- matrisi sınama


def _run(network: Network, kind: dict, source: IPv4Address, destination: IPv4Address) -> list[Verdict]:
    """Bir servisi her iki çekirdeğin etkin olduğu durumda ayrı ayrı sınar."""
    verdicts = []
    for active in network.cores:
        if kind["tur"] == "ping":
            verdicts.append(network.ping(source, destination, active))
        elif kind["tur"] == "tcp":
            verdicts.append(network.tcp(source, destination, kind["port"], active))
        elif kind["tur"] == "udp":
            verdicts.append(network.udp(source, destination, kind["port"], active))
        elif kind["tur"] == "udp-tek-yon":
            verdicts.append(network.udp_one_way(source, destination, kind["port"], active))
        elif kind["tur"] == "ntp":
            verdicts.append(network.udp(source, destination, 123, active, source_port=123))
        else:
            raise ValueError(f"Bilinmeyen servis türü: {kind['tur']}")
    return verdicts


def _row(label: str, expected: bool, verdicts: list[Verdict], note: str = "") -> dict:
    allowed = all(v.allowed for v in verdicts)
    consistent = len({v.allowed for v in verdicts}) == 1
    reason = verdicts[0].reason if consistent else "çekirdekler farklı sonuç veriyor: " + \
        " / ".join(v.reason for v in verdicts)
    return {"label": label, "expected": expected, "allowed": allowed if consistent else None,
            "ok": consistent and allowed == expected, "reason": reason, "note": note}


def run_matrix(network: Network, matrix: dict) -> list[dict]:
    """Matristeki izinleri ve matriste yazmayan bütün kaynak-hedef-servis üçlülerini sınar."""
    hosts = {name: IPv4Address(ip) for name, ip in matrix["cihazlar"].items()}
    public = {name: IPv4Address(ip) for name, ip in matrix["disaridan_gorunen"].items()}
    internet = set(matrix["internet_cihazlari"])
    zones = {name: IPv4Network(net) for name, net in matrix["bolgeler"].items()}
    services = matrix["servisler"]
    allowed = {(p["kaynak"], p["hedef"], s) for p in matrix["izinler"] for s in p["servisler"]}
    rows = []

    def same_network(a: IPv4Address, b: IPv4Address) -> bool:
        return any(a in net and b in net for net in zones.values())

    for source_name, source in hosts.items():
        targets = {**hosts, **public} if source_name in internet else hosts
        for target_name, target in targets.items():
            if target_name == source_name or (source_name in internet and target_name in internet):
                continue
            for service_name, kind in services.items():
                expected = (source_name, target_name, service_name) in allowed
                note = ""
                if same_network(source, target):
                    expected, note = True, "aynı ağ"
                rows.append(_row(f"{source_name} -> {target_name} {service_name}", expected,
                                 _run(network, kind, source, target), note))

    for item in matrix.get("ag_gecidi_pingleri", []):
        source = hosts[item["kaynak"]]
        rows.append(_row(f"{item['kaynak']} -> ağ geçidi {item['ag_gecidi']} ping", True,
                         _run(network, {"tur": "ping"}, source, IPv4Address(item["ag_gecidi"]))))

    for zone_name in matrix.get("dhcp_aglari", []):
        rows.append(_row(f"DHCP isteği, {zone_name}", True,
                         [network.dhcp(zones[zone_name], core) for core in network.cores]))

    devices = {d.name: d for d in [*network.cores, network.edge, *network.others]}
    management = matrix.get("ssh_yonetimi", {})
    for device_name, info in matrix.get("ag_cihazlari", {}).items():
        address = IPv4Address(info["adres"])
        for group, expected in (("izinli", True), ("yasak", False)):
            for source_name in management.get(group, []):
                verdicts = [network.ssh(hosts[source_name], devices[device_name], address, active)
                            for active in network.cores]
                rows.append(_row(f"{source_name} -> {device_name} ({address}) cihaz yönetimi ssh",
                                 expected, verdicts))
    if "internetten" in management:
        item = management["internetten"]
        verdicts = [network.ssh(hosts[item["kaynak"]], network.edge, IPv4Address(item["hedef"]), active)
                    for active in network.cores]
        rows.append(_row(f"{item['kaynak']} -> EDGE ({item['hedef']}) cihaz yönetimi ssh", False, verdicts))

    # Yol üzerindeki listelerden bağımsız olarak her vty bloğu tek başına da doğru olmalı.
    for device_name in matrix.get("ag_cihazlari", {}):
        device = devices[device_name]
        for block in device.vty_blocks or [{"hatlar": "yok", "access_class": None, "transport": None}]:
            label = f"{device_name} line vty {block['hatlar']}"
            only_ssh = block["transport"] == ["ssh"]
            rows.append(_row(f"{label}: yalnızca SSH (Telnet kapalı)", True,
                             [Verdict(only_ssh, f"transport input {' '.join(block['transport'] or ['tanımsız'])}")]))
            for group, expected in (("izinli", True), ("yasak", False)):
                for source_name in management.get(group, []):
                    probe = Packet("tcp", hosts[source_name], IPv4Address("0.0.0.0"), CLIENT_PORT, 22)
                    if block["access_class"] is None:
                        verdict = Verdict(True, f"{device_name} vty hattında access-class yok")
                    else:
                        verdict = device.acl(block["access_class"], probe)
                    rows.append(_row(f"{label}: access-class, kaynak {source_name}", expected, [verdict]))

    for flow in matrix.get("altyapi_akislari", []):
        source = IPv4Address(flow["kaynak"])
        target = hosts[flow["hedef"]]
        rows.append(_row(f"{flow['kaynak']} -> {flow['hedef']} {flow['tur']} ({flow['neden']})", True,
                         _run(network, flow, source, target)))
    return rows


def service_table(network: Network, matrix: dict) -> str:
    """Yapılandırmadan hesaplanan erişim tablosu (Markdown): hücrede geçen servisler yazar."""
    hosts = {name: IPv4Address(ip) for name, ip in matrix["cihazlar"].items()}
    public = {name: IPv4Address(ip) for name, ip in matrix["disaridan_gorunen"].items()}
    internet = set(matrix["internet_cihazlari"])
    columns = [*hosts, *public]
    lines = ["| Kaynak \\ Hedef | " + " | ".join(columns) + " |", "|---" * (len(columns) + 1) + "|"]
    for source_name, source in hosts.items():
        cells = []
        for target_name in columns:
            target = hosts.get(target_name) or public[target_name]
            if target_name == source_name:
                cells.append("-")
                continue
            if target_name in public and source_name not in internet:
                cells.append("")  # iç cihazlar hastanenin dış adresini kullanmaz
                continue
            if source_name in internet and target_name in internet:
                cells.append("")  # internetteki iki cihaz arasındaki trafik hastaneden geçmez
                continue
            passed = [name for name, kind in matrix["servisler"].items()
                      if all(v.allowed for v in _run(network, kind, source, target))]
            cells.append(", ".join(passed) if passed else "yasak")
        lines.append(f"| **{source_name}** | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v3 erişim kurallarını erişim matrisiyle karşılaştırır.")
    parser.add_argument("config_dir", type=Path, help="cihaz yapılandırmalarının klasörü (CORE1.cfg, EDGE.cfg ...)")
    parser.add_argument("matrix", type=Path, help="erişim matrisi (JSON)")
    parser.add_argument("--ayrinti", action="store_true", help="geçen denemeleri de yazdır")
    parser.add_argument("--tablo", action="store_true", help="yapılandırmadan hesaplanan erişim tablosunu yazdır")
    args = parser.parse_args(argv)

    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    network = load_network(args.config_dir, matrix)

    if args.tablo:
        print(service_table(network, matrix))
        return 0

    rows = run_matrix(network, matrix)
    for row in rows:
        if row["ok"] and not args.ayrinti:
            continue
        mark = "TAMAM" if row["ok"] else "HATA "
        outcome = {True: "geçti", False: "engellendi", None: "tutarsız"}[row["allowed"]]
        wanted = "izinli" if row["expected"] else "yasak"
        print(f"{mark}  {row['label']}: {outcome} (beklenen: {wanted})  [{row['reason']}]")
    failures = sum(not row["ok"] for row in rows)
    permitted = sum(row["expected"] for row in rows)
    print(f"\n{len(rows) - failures}/{len(rows)} deneme beklendiği gibi "
          f"({permitted} izinli, {len(rows) - permitted} yasak beklentisi)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
