""" ./resources/scripts/killswitch.py """
import ipaddress
import subprocess
from logger import log_message


def _parse_cidr_network(cidr_token):
    try:
        return str(ipaddress.ip_interface(cidr_token).network)
    except ValueError:
        return None


def _default_route_device():
    try:
        route_out = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True
        ).stdout
        for route_line in route_out.splitlines():
            tokens = route_line.split()
            if "dev" in tokens:
                dev_index = tokens.index("dev") + 1
                if dev_index < len(tokens):
                    return tokens[dev_index]
    except Exception:
        pass
    return None


def _device_networks(device):
    networks = []
    try:
        addr_out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "dev", device],
            capture_output=True, text=True
        ).stdout
        for addr_line in addr_out.splitlines():
            tokens = addr_line.split()
            if len(tokens) >= 4:
                network = _parse_cidr_network(tokens[3])
                if network and network not in networks:
                    networks.append(network)
    except Exception:
        pass
    return networks


def get_local_lan_subnets():
    networks = []
    primary_device = _default_route_device()
    if primary_device:
        networks.extend(_device_networks(primary_device))
    try:
        addr_out = subprocess.run(
            ["ip", "-4", "-o", "addr"],
            capture_output=True, text=True
        ).stdout
        for addr_line in addr_out.splitlines():
            tokens = addr_line.split()
            if len(tokens) < 4:
                continue
            iface = tokens[1]
            if iface == "lo" or iface.startswith("wg") or iface.startswith("vpn"):
                continue
            network = _parse_cidr_network(tokens[3])
            if network and network not in networks:
                networks.append(network)
    except Exception as scan_fault:
        log_message(f"KillSwitch: Interface enumeration failed: {scan_fault}", 2)
    return networks


class ZeroHardcodeKillSwitch:
    def __init__(self, vpn_server_ip):
        self.vpn_server_ip = vpn_server_ip
        self.enabled = False

    def enable(self):
        if self.enabled:
            return True
        local_subnets = get_local_lan_subnets()
        if local_subnets:
            log_message(f"KillSwitch: Target local subnets detected as {', '.join(local_subnets)}", 0)
        else:
            log_message("KillSwitch: No local subnets detected. Engaging fail-closed for LAN traffic.", 1)
        commands = [
            "iptables -N LE_WG_KILLSWITCH",
            "iptables -A LE_WG_KILLSWITCH -o lo -j ACCEPT"
        ]
        for subnet in local_subnets:
            commands.append(f"iptables -A LE_WG_KILLSWITCH -d {subnet} -j ACCEPT")
        commands.extend([
            f"iptables -A LE_WG_KILLSWITCH -d {self.vpn_server_ip} -j ACCEPT",
            "iptables -A LE_WG_KILLSWITCH -o vpn_+ -j ACCEPT",
            "iptables -A LE_WG_KILLSWITCH -o wg+ -j ACCEPT",
            "iptables -A LE_WG_KILLSWITCH -p udp --dport 53 -o eth+ -j DROP",
            "iptables -A LE_WG_KILLSWITCH -p tcp --dport 53 -o eth+ -j DROP",
            "iptables -A LE_WG_KILLSWITCH -p udp --dport 53 -o wlan+ -j DROP",
            "iptables -A LE_WG_KILLSWITCH -p tcp --dport 53 -o wlan+ -j DROP",
            "iptables -A LE_WG_KILLSWITCH -o eth+ -j DROP",
            "iptables -A LE_WG_KILLSWITCH -o wlan+ -j DROP",
            "iptables -I OUTPUT 1 -j LE_WG_KILLSWITCH"
        ])
        for cmd in commands:
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.enabled = True
        log_message("KillSwitch: Firewall killswitch successfully engaged.", 0)
        return True

    def disable(self, reason="disengaged"):
        if not self.enabled:
            return True
        commands = [
            "iptables -D OUTPUT -j LE_WG_KILLSWITCH",
            "iptables -F LE_WG_KILLSWITCH",
            "iptables -X LE_WG_KILLSWITCH"
        ]
        for cmd in commands:
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.enabled = False
        if reason == "switch":
            log_message("KillSwitch: Firewall rules temporarily opened for connection cycle.", 1)
        elif reason == "recovery":
            log_message("KillSwitch: Purging firewall rules for emergency tunnel recovery.", 1)
        else:
            log_message("KillSwitch: Firewall killswitch successfully deactivated.", 1)
        return True
