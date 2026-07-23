""" ./resources/scripts/killswitch.py """
import subprocess
import ipaddress
import re
from logger import log_message


def get_live_lan_subnet():
    try:
        state_out = subprocess.run(["connmanctl", "state"], capture_output=True, text=True).stdout
        match_service = re.search(r"Services\s*=\s*\[\s*([a-zA-Z0-9_\-]+)", state_out)

        if not match_service:
            return "192.168.0.0/16"

        active_service = match_service.group(1)
        props_out = subprocess.run(["connmanctl", "services", active_service], capture_output=True, text=True).stdout
        ipv4_match = re.search(r"IPv4\s*=\s*\[([^\]]+)\]", props_out)
        if ipv4_match:
            ipv4_data = ipv4_match.group(1)
            ip_addr = re.search(r"Address=([0-9\.]+)", ipv4_data)
            netmask = re.search(r"Netmask=([0-9\.]+)", ipv4_data)

            if ip_addr and netmask:
                interface = ipaddress.IPv4Interface(f"{ip_addr.group(1)}/{netmask.group(1)}")
                return str(interface.network)

    except Exception:
        pass

    return "192.168.0.0/16"


class ZeroHardcodeKillSwitch:
    def __init__(self, vpn_server_ip):
        self.vpn_server_ip = vpn_server_ip
        self.enabled = False

    def enable(self):
        if self.enabled:
            return

        live_lan = get_live_lan_subnet()
        log_message(f"KillSwitch: Target local subnet detected as {live_lan}", 0)
        commands = [
            "iptables -N LE_WG_KILLSWITCH",
            "iptables -A LE_WG_KILLSWITCH -o lo -j ACCEPT",
            f"iptables -A LE_WG_KILLSWITCH -d {live_lan} -j ACCEPT",
            f"iptables -A LE_WG_KILLSWITCH -d {self.vpn_server_ip} -j ACCEPT",
            "iptables -A LE_WG_KILLSWITCH -o vpn_+ -j ACCEPT",
            "iptables -A LE_WG_KILLSWITCH -o wg+ -j ACCEPT",
            "iptables -A LE_WG_KILLSWITCH -o eth+ -j DROP",
            "iptables -A LE_WG_KILLSWITCH -o wlan+ -j DROP",
            "iptables -I OUTPUT 1 -j LE_WG_KILLSWITCH"
        ]

        for cmd in commands:
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.enabled = True
        log_message("KillSwitch: Firewall killswitch successfully engaged.", 1)

    def disable(self):
        if not self.enabled:
            return

        commands = [
            "iptables -D OUTPUT -j LE_WG_KILLSWITCH",
            "iptables -F LE_WG_KILLSWITCH",
            "iptables -X LE_WG_KILLSWITCH"
        ]

        for cmd in commands:
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.enabled = False
        log_message("KillSwitch: Firewall killswitch successfully disengaged.", 1)
