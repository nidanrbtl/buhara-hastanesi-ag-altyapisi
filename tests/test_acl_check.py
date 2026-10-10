"""
acl_check betiğinin ve depodaki yapılandırma dosyalarının testleri.

Çalıştırma (depo kökünden): python -m unittest discover -s tests
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

import acl_check  # noqa: E402
from acl_check import Packet, parse_config, parse_rule  # noqa: E402


def load_config(version: str) -> acl_check.RouterConfig:
    return parse_config((ROOT / "configs" / version / "RTR01.cfg").read_text(encoding="utf-8"))


def load_expectations(version: str) -> dict:
    return json.loads((ROOT / "tests" / f"beklentiler_{version}.json").read_text(encoding="utf-8"))


SAMPLE = """
interface GigabitEthernet0/0.10
 encapsulation dot1Q 10
 ip address 10.0.10.1 255.255.255.0
 ip access-group KULLANICI in
interface GigabitEthernet0/0.20
 encapsulation dot1Q 20
 ip address 10.0.20.1 255.255.255.0
 ip access-group SUNUCU-CIKIS out
interface GigabitEthernet0/1
 ip address 10.0.30.1 255.255.255.0
 shutdown
ip access-list extended KULLANICI
 remark web sunucusuna yalnizca http
 permit tcp 10.0.10.0 0.0.0.255 host 10.0.20.5 eq www
 permit icmp any any echo
 permit tcp any any established
 deny ip any any
ip access-list extended SUNUCU-CIKIS
 deny tcp any host 10.0.20.9
 permit ip any any
"""


class RuleParsingTests(unittest.TestCase):
    def test_host_any_and_wildcard_addresses(self):
        rule = parse_rule("permit ip 192.168.20.0 0.0.0.255 host 192.168.50.2")
        self.assertTrue(rule.source.matches(IP("192.168.20.77")))
        self.assertFalse(rule.source.matches(IP("192.168.21.77")))
        self.assertTrue(rule.destination.matches(IP("192.168.50.2")))
        self.assertFalse(rule.destination.matches(IP("192.168.50.3")))
        self.assertTrue(parse_rule("deny ip any any").source.matches(IP("8.8.8.8")))

    def test_ports_by_number_name_and_range(self):
        rule = parse_rule("permit udp any eq bootpc any eq 67")
        self.assertEqual((rule.source_port.low, rule.destination_port.low), (68, 67))
        ranged = parse_rule("permit tcp any any range 1000 2000")
        self.assertTrue(ranged.destination_port.matches(1500))
        self.assertFalse(ranged.destination_port.matches(2001))

    def test_sequence_numbers_and_remarks(self):
        self.assertIsNone(parse_rule("remark DHCP istekleri"))
        self.assertFalse(parse_rule("10 deny ip 192.168.20.0 0.0.0.255 host 192.168.50.2").permit)

    def test_standard_list_matches_source_only(self):
        rule = parse_rule("permit 192.168.40.0 0.0.0.255", standard=True)
        packet = Packet("tcp", IP("192.168.40.9"), IP("1.2.3.4"), 50000, 22)
        self.assertTrue(rule.matches(packet))
        single = parse_rule("permit 192.168.40.5", standard=True)
        self.assertFalse(single.matches(packet))

    def test_unknown_option_is_an_error_not_a_silent_permit(self):
        with self.assertRaises(ValueError):
            parse_rule("permit tcp any any eq 80 log")
        with self.assertRaises(ValueError):
            parse_rule("permit gre any any")


class ForwardingTests(unittest.TestCase):
    def setUp(self):
        self.config = parse_config(SAMPLE)

    def test_first_matching_rule_decides(self):
        http = Packet("tcp", IP("10.0.10.7"), IP("10.0.20.5"), 50000, 80)
        ssh = Packet("tcp", IP("10.0.10.7"), IP("10.0.20.5"), 50000, 22)
        self.assertTrue(acl_check.forward(self.config, http).allowed)
        verdict = acl_check.forward(self.config, ssh)
        self.assertFalse(verdict.allowed)
        self.assertIn("deny ip any any", verdict.reason)

    def test_established_lets_replies_through_but_not_new_connections(self):
        new = Packet("tcp", IP("10.0.10.7"), IP("10.0.20.8"), 50000, 443)
        reply = Packet("tcp", IP("10.0.10.7"), IP("10.0.20.8"), 443, 50000, established=True)
        self.assertFalse(acl_check.forward(self.config, new).allowed)
        self.assertTrue(acl_check.forward(self.config, reply).allowed)

    def test_outbound_list_is_applied_on_the_exit_interface(self):
        blocked = Packet("tcp", IP("10.0.10.7"), IP("10.0.20.9"), 80, 50000, established=True)
        self.assertFalse(acl_check.forward(self.config, blocked).allowed)

    def test_same_network_traffic_does_not_cross_the_router(self):
        local = Packet("tcp", IP("10.0.10.7"), IP("10.0.10.8"), 50000, 22)
        self.assertTrue(acl_check.forward(self.config, local).allowed)

    def test_no_route_and_shutdown_interface(self):
        self.assertFalse(acl_check.forward(self.config, Packet("icmp", IP("10.0.10.7"), IP("8.8.8.8"), icmp_type="echo")).allowed)
        self.assertFalse(acl_check.forward(self.config, Packet("icmp", IP("10.0.10.7"), IP("10.0.30.5"), icmp_type="echo")).allowed)

    def test_ping_needs_the_reply_to_get_back(self):
        # 10.0.20.5 -> 10.0.10.7: istek geçer, yanıt (echo-reply) KULLANICI listesinde engellenir.
        self.assertFalse(acl_check.ping(self.config, IP("10.0.20.5"), IP("10.0.10.7")).allowed)
        self.assertTrue(acl_check.ping(self.config, IP("10.0.10.7"), IP("10.0.20.5")).allowed)

    def test_undefined_list_permits_everything(self):
        config = parse_config("interface G0/0\n ip address 10.1.1.1 255.255.255.0\n ip access-group YOK in\n"
                              "interface G0/1\n ip address 10.1.2.1 255.255.255.0\n")
        self.assertTrue(acl_check.ping(config, IP("10.1.1.5"), IP("10.1.2.5")).allowed)

    def test_empty_inbound_list_has_implicit_deny(self):
        config = parse_config("interface G0/0\n ip address 10.1.1.1 255.255.255.0\n ip access-group L in\n"
                              "interface G0/1\n ip address 10.1.2.1 255.255.255.0\n"
                              "ip access-list extended L\n permit tcp any any eq 80\n")
        self.assertFalse(acl_check.ping(config, IP("10.1.1.5"), IP("10.1.2.5")).allowed)


class DhcpCheckTests(unittest.TestCase):
    def test_dns_server_inside_a_leasable_range_is_reported(self):
        config = parse_config(
            "ip dhcp excluded-address 10.0.0.1\n"
            "ip dhcp pool A\n network 10.0.0.0 255.255.255.0\n default-router 10.0.0.1\n dns-server 10.0.0.10\n"
            "interface G0/0\n ip address 10.0.0.1 255.255.255.0\n"
        )
        self.assertEqual(acl_check.is_leasable(config, IP("10.0.0.10")), "A")
        self.assertIsNone(acl_check.is_leasable(config, IP("10.0.0.1")))
        self.assertEqual(len(acl_check.check_dhcp(config)), 1)

    def test_gateway_must_be_a_router_address(self):
        config = parse_config(
            "ip dhcp pool A\n network 10.0.0.0 255.255.255.0\n default-router 10.0.0.254\n"
            "interface G0/0\n ip address 10.0.0.1 255.255.255.0\n"
        )
        self.assertIn("ağ geçidi", acl_check.check_dhcp(config)[0])


class FirstVersionTests(unittest.TestCase):
    """configs/v1: Packet Tracer dosyasındaki yapılandırma."""

    def setUp(self):
        self.config = load_config("v1")

    def test_model_reproduces_the_results_in_the_screenshots(self):
        rows = acl_check.run_expectations(self.config, load_expectations("v1"))
        self.assertTrue(all(row["ok"] for row in rows), [row for row in rows if not row["ok"]])

    def test_only_rule_is_nurses_to_srv01(self):
        hosts = load_expectations("v1")["hosts"]
        table = acl_check.ping_matrix(self.config, hosts)
        blocked = {(row[0], table[0][i]) for row in table[1:] for i, cell in enumerate(row) if cell == "hayır"}
        self.assertEqual(blocked, {("HEMSIRE-PC", "SRV01"), ("SRV01", "HEMSIRE-PC")})

    def test_dhcp_problems_are_detected(self):
        problems = acl_check.check_dhcp(self.config)
        self.assertTrue(any("192.168.10.10" in p and p.startswith("DMZ") for p in problems))
        self.assertTrue(any("farklı DNS" in p for p in problems))

    def test_second_version_expectations_fail_here(self):
        rows = acl_check.run_expectations(self.config, load_expectations("v2"))
        self.assertGreater(sum(not row["ok"] for row in rows), 20)


class SecondVersionTests(unittest.TestCase):
    """configs/v2: düzeltilmiş yapılandırma."""

    def setUp(self):
        self.config = load_config("v2")
        self.switch = (ROOT / "configs" / "v2" / "SW01.cfg").read_text(encoding="utf-8")

    def test_every_expectation_holds(self):
        rows = acl_check.run_expectations(self.config, load_expectations("v2"))
        self.assertGreaterEqual(len(rows), 70)
        self.assertEqual([row for row in rows if not row["ok"]], [])

    def test_dhcp_settings_are_consistent(self):
        self.assertEqual(acl_check.check_dhcp(self.config), [])

    def test_static_addresses_are_never_leased(self):
        for address in load_expectations("v2")["hosts"].values():
            if address.startswith(("192.168.50.", "192.168.60.")):
                self.assertIsNone(acl_check.is_leasable(self.config, IP(address)), address)
        self.assertIsNone(acl_check.is_leasable(self.config, IP("192.168.40.2")), "SW01 yönetim adresi")

    def test_every_filtered_interface_with_a_pool_lets_dhcp_in(self):
        for pool in self.config.dhcp_pools.values():
            interface = next(i for i in self.config.interfaces.values() if i.address == pool.default_router)
            self.assertTrue(acl_check.dhcp_request(self.config, interface.name).allowed, interface.name)

    def test_referenced_lists_exist(self):
        for interface in self.config.interfaces.values():
            for name in (interface.acl_in, interface.acl_out):
                if name:
                    self.assertIn(name, self.config.acls, f"{interface.name}: {name}")
        self.assertIn(self.config.vty_acl, self.config.acls)

    def test_every_list_ends_with_an_explicit_deny(self):
        for name, rules in self.config.acls.items():
            if name.endswith("-GIRIS"):
                self.assertEqual(rules[-1].text, "deny ip any any", name)

    def test_switch_trunk_carries_exactly_the_routed_vlans(self):
        routed = set()
        for name, interface in self.config.interfaces.items():
            if "." in name and interface.address:
                routed.add(int(name.split(".")[1]))
        allowed = re.search(r"switchport trunk allowed vlan ([\d,]+)", self.switch).group(1)
        self.assertEqual({int(v) for v in allowed.split(",")}, routed)
        defined = {int(v) for v in re.findall(r"^vlan (\d+)$", self.switch, flags=re.MULTILINE)}
        self.assertTrue(routed <= defined)

    def test_native_vlan_matches_on_both_ends(self):
        switch_native = re.search(r"switchport trunk native vlan (\d+)", self.switch).group(1)
        router = (ROOT / "configs" / "v2" / "RTR01.cfg").read_text(encoding="utf-8")
        router_native = re.search(r"encapsulation dot1Q (\d+) native", router).group(1)
        self.assertEqual(switch_native, router_native)

    def test_no_real_passwords_in_the_repository(self):
        for path in (ROOT / "configs" / "v2").glob("*.cfg"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if re.match(r"\s*(enable secret|username .* secret|.*password) ", line) and "password-encryption" not in line:
                    self.assertIn("DEGISTIR_", line, f"{path.name}: {line}")


class CommandLineTests(unittest.TestCase):
    def test_exit_code_reflects_the_result(self):
        import contextlib
        import io

        def run(version_config: str, version_expect: str) -> int:
            with contextlib.redirect_stdout(io.StringIO()):
                return acl_check.main([
                    str(ROOT / "configs" / version_config / "RTR01.cfg"),
                    str(ROOT / "tests" / f"beklentiler_{version_expect}.json"),
                    "--matrix",
                ])

        self.assertEqual(run("v2", "v2"), 0)
        self.assertEqual(run("v1", "v2"), 1)
        self.assertEqual(run("v1", "v1"), 1)  # denemeler tutar, DHCP uyarıları kalır


if __name__ == "__main__":
    unittest.main()
