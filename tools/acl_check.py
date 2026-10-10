"""
Yönlendirici yapılandırmasındaki erişim kurallarını (ACL) ve DHCP ayarlarını denetler.

Betik bir Cisco IOS yapılandırma dosyasını okur, arayüzleri, erişim listelerini ve
DHCP havuzlarını çıkarır; ardından bir beklenti dosyasındaki her bağlantıyı
("hemşire bilgisayarı SRV01'e ping atabilir mi?") kurallar üzerinde adım adım
yürütür ve sonucu beklenenle karşılaştırır.

Kullanım:
    python tools/acl_check.py configs/v2/RTR01.cfg tests/beklentiler_v2.json

Bu bir IOS benzetimi değildir; yalnızca yönlendirme (doğrudan bağlı ağlar) ve
ACL eşleştirme kurallarını modeller. Sonuçların Packet Tracer'da da doğrulanması gerekir.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

PORT_NAMES = {
    "bootps": 67, "bootpc": 68, "domain": 53, "www": 80, "ftp": 21, "ftp-data": 20,
    "telnet": 23, "smtp": 25, "pop3": 110, "tftp": 69, "snmp": 161, "ntp": 123,
}


# --------------------------------------------------------------------------- veri yapıları


@dataclass(frozen=True)
class Address:
    """ACL'deki bir adres tanımı: 'any', 'host A.B.C.D' ya da 'A.B.C.D joker-maske'."""

    base: int = 0
    wildcard: int = 0xFFFFFFFF

    def matches(self, ip: IPv4Address) -> bool:
        return (int(ip) | self.wildcard) == (self.base | self.wildcard)


@dataclass(frozen=True)
class PortMatch:
    operator: str  # eq, neq, gt, lt, range
    low: int
    high: int

    def matches(self, port: int | None) -> bool:
        if port is None:
            return False
        if self.operator == "eq":
            return port == self.low
        if self.operator == "neq":
            return port != self.low
        if self.operator == "gt":
            return port > self.low
        if self.operator == "lt":
            return port < self.low
        return self.low <= port <= self.high


@dataclass(frozen=True)
class Rule:
    permit: bool
    protocol: str  # ip, tcp, udp, icmp
    source: Address
    destination: Address = Address()
    source_port: PortMatch | None = None
    destination_port: PortMatch | None = None
    icmp_type: str | None = None
    established: bool = False
    text: str = ""

    def matches(self, packet: "Packet") -> bool:
        if self.protocol != "ip" and self.protocol != packet.protocol:
            return False
        if not self.source.matches(packet.source) or not self.destination.matches(packet.destination):
            return False
        if self.source_port and not self.source_port.matches(packet.source_port):
            return False
        if self.destination_port and not self.destination_port.matches(packet.destination_port):
            return False
        if self.icmp_type and self.icmp_type != packet.icmp_type:
            return False
        if self.established and not packet.established:
            return False
        return True


@dataclass(frozen=True)
class Packet:
    protocol: str  # tcp, udp, icmp
    source: IPv4Address
    destination: IPv4Address
    source_port: int | None = None
    destination_port: int | None = None
    icmp_type: str | None = None
    established: bool = False  # TCP: ACK ya da RST bayrağı var (ilk SYN paketi değil)


@dataclass
class Interface:
    name: str
    address: IPv4Address | None = None
    network: IPv4Network | None = None
    acl_in: str | None = None
    acl_out: str | None = None
    shutdown: bool = False


@dataclass
class DhcpPool:
    name: str
    network: IPv4Network | None = None
    default_router: IPv4Address | None = None
    dns_server: IPv4Address | None = None


@dataclass
class RouterConfig:
    interfaces: dict[str, Interface] = field(default_factory=dict)
    acls: dict[str, list[Rule]] = field(default_factory=dict)
    dhcp_pools: dict[str, DhcpPool] = field(default_factory=dict)
    dhcp_excluded: list[tuple[IPv4Address, IPv4Address]] = field(default_factory=list)
    vty_acl: str | None = None  # "line vty" altındaki access-class


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str


# --------------------------------------------------------------------------- yapılandırmayı okuma


def _take_address(tokens: list[str]) -> Address:
    """Belirteç listesinin başındaki adres tanımını okur ve listeden çıkarır."""
    first = tokens.pop(0)
    if first == "any":
        return Address()
    if first == "host":
        return Address(int(IPv4Address(tokens.pop(0))), 0)
    return Address(int(IPv4Address(first)), int(IPv4Address(tokens.pop(0))))


def _take_port(tokens: list[str]) -> PortMatch | None:
    if not tokens or tokens[0] not in ("eq", "neq", "gt", "lt", "range"):
        return None
    operator = tokens.pop(0)
    low = _port_number(tokens.pop(0))
    high = _port_number(tokens.pop(0)) if operator == "range" else low
    return PortMatch(operator, low, high)


def _port_number(token: str) -> int:
    return PORT_NAMES[token] if token in PORT_NAMES else int(token)


def parse_rule(text: str, standard: bool = False) -> Rule | None:
    """Tek bir ACL satırını kurala çevirir. 'remark' satırları için None döner."""
    tokens = text.split()
    if tokens and tokens[0].isdigit():  # sıra numarası ("10 permit ...")
        tokens.pop(0)
    if not tokens or tokens[0] == "remark":
        return None
    if tokens[0] not in ("permit", "deny"):
        raise ValueError(f"Anlaşılmayan ACL satırı: {text}")
    permit = tokens.pop(0) == "permit"

    if standard:  # standart liste yalnızca kaynağa bakar; tek adres 'host' sayılır
        if len(tokens) == 1 and tokens[0] != "any":
            tokens.insert(0, "host")
        return Rule(permit, "ip", _take_address(tokens), text=text.strip())

    protocol = tokens.pop(0)
    if protocol not in ("ip", "tcp", "udp", "icmp"):
        raise ValueError(f"Desteklenmeyen protokol '{protocol}': {text}")
    source = _take_address(tokens)
    source_port = _take_port(tokens) if protocol in ("tcp", "udp") else None
    destination = _take_address(tokens)
    destination_port = _take_port(tokens) if protocol in ("tcp", "udp") else None

    icmp_type = None
    established = False
    for token in tokens:
        if protocol == "icmp" and token in ("echo", "echo-reply"):
            icmp_type = token
        elif protocol == "tcp" and token == "established":
            established = True
        else:
            raise ValueError(f"Desteklenmeyen seçenek '{token}': {text}")
    return Rule(permit, protocol, source, destination, source_port, destination_port,
                icmp_type, established, text.strip())


def parse_config(text: str) -> RouterConfig:
    """IOS yapılandırma metninden arayüzleri, erişim listelerini ve DHCP havuzlarını çıkarır."""
    config = RouterConfig()
    interface: Interface | None = None
    pool: DhcpPool | None = None
    acl_name: str | None = None
    acl_standard = False
    in_vty = False

    for raw_line in text.splitlines():
        indented = raw_line.startswith(" ")
        line = raw_line.strip()
        if not line or line.startswith("!"):
            continue
        words = line.split()

        if not indented:  # yeni bir genel komut, önceki blok bitti
            interface = pool = acl_name = None
            in_vty = words[:2] == ["line", "vty"]

        if not indented and words[0] == "interface":
            interface = config.interfaces.setdefault(words[1], Interface(words[1]))
        elif not indented and words[:3] == ["ip", "dhcp", "pool"]:
            pool = config.dhcp_pools.setdefault(words[3], DhcpPool(words[3]))
        elif not indented and words[:3] == ["ip", "dhcp", "excluded-address"]:
            low = IPv4Address(words[3])
            high = IPv4Address(words[4]) if len(words) > 4 else low
            config.dhcp_excluded.append((low, high))
        elif not indented and words[:2] == ["ip", "access-list"]:
            acl_name, acl_standard = words[3], words[2] == "standard"
            config.acls.setdefault(acl_name, [])
        elif not indented and words[0] == "access-list":
            number = words[1]
            rule = parse_rule(" ".join(words[2:]), standard=int(number) < 100)
            config.acls.setdefault(number, [])
            if rule:
                config.acls[number].append(rule)
        elif indented and interface is not None:
            if words[:2] == ["ip", "address"]:
                interface.address = IPv4Address(words[2])
                interface.network = IPv4Network(f"{words[2]}/{words[3]}", strict=False)
            elif words[:2] == ["ip", "access-group"]:
                if words[3] == "in":
                    interface.acl_in = words[2]
                else:
                    interface.acl_out = words[2]
            elif words == ["shutdown"]:
                interface.shutdown = True
        elif indented and pool is not None:
            if words[0] == "network":
                pool.network = IPv4Network(f"{words[1]}/{words[2]}")
            elif words[0] == "default-router":
                pool.default_router = IPv4Address(words[1])
            elif words[0] == "dns-server":
                pool.dns_server = IPv4Address(words[1])
        elif indented and acl_name is not None:
            rule = parse_rule(line, standard=acl_standard)
            if rule:
                config.acls[acl_name].append(rule)
        elif indented and in_vty and words[0] == "access-class" and words[2] == "in":
            config.vty_acl = words[1]
    return config


# --------------------------------------------------------------------------- paketi yürütme


def evaluate_acl(config: RouterConfig, acl_name: str | None, packet: Packet) -> Verdict:
    """Paketi listenin kurallarıyla sırayla karşılaştırır; ilk eşleşen kural geçerlidir."""
    if acl_name is None:
        return Verdict(True, "liste yok")
    if acl_name not in config.acls:
        # IOS'ta tanımlanmamış bir listeye yapılan atıf bütün trafiğe izin verir.
        return Verdict(True, f"{acl_name} tanımlı değil")
    for rule in config.acls[acl_name]:
        if rule.matches(packet):
            return Verdict(rule.permit, f"{acl_name}: {rule.text}")
    return Verdict(False, f"{acl_name}: eşleşen kural yok (örtük deny)")


def _interface_for(config: RouterConfig, ip: IPv4Address) -> Interface | None:
    for interface in config.interfaces.values():
        if interface.network and not interface.shutdown and ip in interface.network:
            return interface
    return None


def forward(config: RouterConfig, packet: Packet, ingress: str | None = None) -> Verdict:
    """
    Paketi yönlendiriciden geçirir: giriş arayüzünün 'in' listesi, hedef ağın bulunması,
    çıkış arayüzünün 'out' listesi. ingress verilmezse giriş arayüzü kaynak adresten bulunur.
    """
    router_addresses = {i.address for i in config.interfaces.values() if i.address}
    if packet.source in router_addresses:
        # Yönlendiricinin kendi ürettiği paketler arayüz listelerinden geçmez.
        return Verdict(True, "yönlendiricinin kendi paketi")

    entry = config.interfaces.get(ingress) if ingress else _interface_for(config, packet.source)
    if entry is None:
        return Verdict(False, f"{packet.source} için giriş arayüzü yok")
    if entry.network and packet.destination in entry.network and packet.destination != entry.address:
        return Verdict(True, "aynı ağ, yönlendiriciden geçmez")

    inbound = evaluate_acl(config, entry.acl_in, packet)
    if not inbound.allowed:
        return inbound

    if packet.destination in router_addresses or packet.destination == IPv4Address("255.255.255.255"):
        return Verdict(True, f"yönlendiricinin kendisine ulaştı ({inbound.reason})")

    exit_ = _interface_for(config, packet.destination)
    if exit_ is None:
        return Verdict(False, f"{packet.destination} için rota yok")
    outbound = evaluate_acl(config, exit_.acl_out, packet)
    if not outbound.allowed:
        return outbound
    return Verdict(True, inbound.reason)


def ping(config: RouterConfig, source: IPv4Address, destination: IPv4Address) -> Verdict:
    """Ping başarılıdır: istek hedefe ulaşır ve yanıt geri döner."""
    request = forward(config, Packet("icmp", source, destination, icmp_type="echo"))
    if not request.allowed:
        return Verdict(False, f"istek engellendi - {request.reason}")
    reply = forward(config, Packet("icmp", destination, source, icmp_type="echo-reply"))
    if not reply.allowed:
        return Verdict(False, f"yanıt engellendi - {reply.reason}")
    return Verdict(True, request.reason)


def tcp_connect(config: RouterConfig, source: IPv4Address, destination: IPv4Address, port: int) -> Verdict:
    """TCP bağlantısı kurulur: SYN gider, SYN-ACK döner, sonraki paketler de geçer."""
    client_port = 50000
    steps = [
        ("SYN", Packet("tcp", source, destination, client_port, port)),
        ("SYN-ACK", Packet("tcp", destination, source, port, client_port, established=True)),
        ("ACK", Packet("tcp", source, destination, client_port, port, established=True)),
    ]
    first_reason = ""
    for label, packet in steps:
        verdict = forward(config, packet)
        if not verdict.allowed:
            return Verdict(False, f"{label} engellendi - {verdict.reason}")
        first_reason = first_reason or verdict.reason
    return Verdict(True, first_reason)


def udp_exchange(config: RouterConfig, source: IPv4Address, destination: IPv4Address, port: int) -> Verdict:
    """UDP sorgusu gider ve yanıtı döner (örneğin DNS)."""
    client_port = 50000
    query = forward(config, Packet("udp", source, destination, client_port, port))
    if not query.allowed:
        return Verdict(False, f"sorgu engellendi - {query.reason}")
    answer = forward(config, Packet("udp", destination, source, port, client_port))
    if not answer.allowed:
        return Verdict(False, f"yanıt engellendi - {answer.reason}")
    return Verdict(True, query.reason)


def ssh_to_router(config: RouterConfig, source: IPv4Address, router_address: IPv4Address) -> Verdict:
    """
    Yönlendiricinin kendisine SSH: paket giriş arayüzünün listesinden, sonra da
    "line vty" altındaki access-class listesinden geçmelidir.
    """
    packet = Packet("tcp", source, router_address, 50000, 22)
    arrival = forward(config, packet)
    if not arrival.allowed:
        return Verdict(False, f"arayüzde engellendi - {arrival.reason}")
    if config.vty_acl is None:
        return Verdict(True, "vty hatlarında access-class yok")
    return evaluate_acl(config, config.vty_acl, packet)


def dhcp_request(config: RouterConfig, interface_name: str) -> Verdict:
    """Adresi olmayan bir istemcinin DHCP isteği arayüzün giriş listesinden geçebiliyor mu?"""
    packet = Packet("udp", IPv4Address("0.0.0.0"), IPv4Address("255.255.255.255"), 68, 67)
    return forward(config, packet, ingress=interface_name)


# --------------------------------------------------------------------------- DHCP denetimleri


def is_leasable(config: RouterConfig, ip: IPv4Address) -> str | None:
    """Adres bir DHCP havuzundan istemciye verilebiliyorsa havuzun adını döndürür."""
    for pool in config.dhcp_pools.values():
        if pool.network is None or ip not in pool.network:
            continue
        if ip in (pool.network.network_address, pool.network.broadcast_address):
            continue
        if any(low <= ip <= high for low, high in config.dhcp_excluded):
            continue
        return pool.name
    return None


def check_dhcp(config: RouterConfig) -> list[str]:
    """DHCP havuzlarındaki tutarsızlıkları listeler (boş liste: sorun yok)."""
    problems = []
    router_addresses = {i.address for i in config.interfaces.values() if i.address}
    for pool in config.dhcp_pools.values():
        if pool.default_router and pool.default_router not in router_addresses:
            problems.append(f"{pool.name}: ağ geçidi {pool.default_router} yönlendiricide tanımlı değil")
        if pool.default_router and pool.network and pool.default_router not in pool.network:
            problems.append(f"{pool.name}: ağ geçidi {pool.default_router} havuzun ağında değil")
        if pool.dns_server:
            owner = is_leasable(config, pool.dns_server)
            if owner:
                problems.append(
                    f"{pool.name}: DNS sunucusu {pool.dns_server}, {owner} havuzundan "
                    "herhangi bir istemciye verilebilecek bir adres"
                )
    dns_servers = {str(p.dns_server) for p in config.dhcp_pools.values() if p.dns_server}
    if len(dns_servers) > 1:
        problems.append("Havuzlar farklı DNS sunucuları dağıtıyor: " + ", ".join(sorted(dns_servers)))
    return problems


# --------------------------------------------------------------------------- beklenti dosyası


def run_expectations(config: RouterConfig, expectations: dict) -> list[dict]:
    """Beklenti dosyasındaki her denemeyi çalıştırır; sonuç satırlarını döndürür."""
    named = {**expectations["hosts"], **expectations.get("router_addresses", {})}
    hosts = {name: IPv4Address(ip) for name, ip in named.items()}
    rows = []
    for test in expectations["tests"]:
        kind = test["kind"]
        if kind == "dhcp":
            verdict = dhcp_request(config, test["interface"])
            label = f"DHCP isteği, {test['interface']}"
        else:
            source, destination = hosts[test["from"]], hosts[test["to"]]
            if kind == "ping":
                verdict = ping(config, source, destination)
                label = f"{test['from']} -> {test['to']} ping"
            elif kind == "tcp":
                verdict = tcp_connect(config, source, destination, test["port"])
                label = f"{test['from']} -> {test['to']} tcp/{test['port']}"
            elif kind == "udp":
                verdict = udp_exchange(config, source, destination, test["port"])
                label = f"{test['from']} -> {test['to']} udp/{test['port']}"
            elif kind == "ssh":
                verdict = ssh_to_router(config, source, destination)
                label = f"{test['from']} -> {test['to']} ssh (cihaz yönetimi)"
            else:
                raise ValueError(f"Bilinmeyen deneme türü: {kind}")
        expected = test["expect"] == "allow"
        rows.append({
            "label": label,
            "expected": expected,
            "allowed": verdict.allowed,
            "ok": verdict.allowed == expected,
            "reason": verdict.reason,
        })
    return rows


def ping_matrix(config: RouterConfig, hosts: dict[str, str]) -> list[list[str]]:
    """Bütün cihaz çiftleri için ping sonucu tablosu (satır: kaynak, sütun: hedef)."""
    names = list(hosts)
    table = [["kaynak \\ hedef", *names]]
    for source in names:
        row = [source]
        for destination in names:
            if source == destination:
                row.append("-")
            else:
                verdict = ping(config, IPv4Address(hosts[source]), IPv4Address(hosts[destination]))
                row.append("evet" if verdict.allowed else "hayır")
        table.append(row)
    return table


def format_table(table: list[list[str]]) -> str:
    widths = [max(len(row[i]) for row in table) for i in range(len(table[0]))]
    return "\n".join("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in table)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Yönlendirici erişim kurallarını beklentilerle karşılaştırır.")
    parser.add_argument("config", type=Path, help="yönlendirici yapılandırma dosyası")
    parser.add_argument("expectations", type=Path, help="beklenti dosyası (JSON)")
    parser.add_argument("--matrix", action="store_true", help="cihazlar arası ping tablosunu da yazdır")
    args = parser.parse_args(argv)

    config = parse_config(args.config.read_text(encoding="utf-8"))
    expectations = json.loads(args.expectations.read_text(encoding="utf-8"))

    rows = run_expectations(config, expectations)
    for row in rows:
        mark = "TAMAM" if row["ok"] else "HATA "
        outcome = "geçti" if row["allowed"] else "engellendi"
        print(f"{mark}  {row['label']}: {outcome}  [{row['reason']}]")
    failures = sum(not row["ok"] for row in rows)

    dhcp_problems = check_dhcp(config)
    print()
    if dhcp_problems:
        print("DHCP denetimi:")
        for problem in dhcp_problems:
            print(f"  UYARI  {problem}")
    else:
        print("DHCP denetimi: sorun yok")

    if args.matrix:
        print("\nPing tablosu:")
        print(format_table(ping_matrix(config, expectations["hosts"])))

    print(f"\n{len(rows) - failures}/{len(rows)} deneme beklendiği gibi, {len(dhcp_problems)} DHCP uyarısı")
    return 1 if failures or dhcp_problems else 0


if __name__ == "__main__":
    sys.exit(main())
