''' ./resources/lib/network_utils.py '''
import os
import re
import subprocess
from logger import log_message
from vpn_config import PROVIDER_MAP

CONFIG_DIR = "/storage/.config/wireguard/"


def get_default_gateway():
    import subprocess
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True).strip()
        if not out:
            return None

        parts = out.split()
        if "via" in parts:
            return parts[parts.index("via") + 1]

        if "dev" in parts:
            dev = parts[parts.index("dev") + 1]
            out_dev = subprocess.check_output(["ip", "route", "show", "dev", dev], text=True)
            for line in out_dev.splitlines():
                if "via" in line:
                    return line.split()[2]

    except Exception as e:
        log_message(f"Failed to resolve default gateway: {e}", 3)
    return None


def get_dns_from_config(vpn_name):
    dns_list = []
    if not vpn_name:
        return dns_list

    clean_name = vpn_name.lower().replace(' ', '_')
    for p in PROVIDER_MAP.values():
        clean_name = clean_name.replace(p['prefix'].lower(), '')

    target_path = None
    for p in PROVIDER_MAP.values():
        filename = f"{p['prefix'].lower()}{clean_name}.config"
        path = os.path.join(CONFIG_DIR, filename)
        if os.path.exists(path):
            target_path = path
            break

    if target_path:
        try:
            with open(target_path, 'r') as f:
                content = f.read()
                match = re.search(r"(?:WireGuard\.)?DNS\s*=\s*(.*)", content, re.IGNORECASE)
                if match:
                    dns_list = [d.strip() for d in match.group(1).split(",")]
        except Exception as e:
            log_message(f"Error reading DNS from {target_path}: {e}", 3)
    return dns_list


def set_secure_dns(vpn_name=None, vpn_active=True):
    dns_servers = get_dns_from_config(vpn_name) if vpn_active else []
    try:
        ipv6_val = "1" if vpn_active else "0"
        sysctl_cmd = ["sysctl", "-w", f"net.ipv6.conf.all.disable_ipv6={ipv6_val}"]
        subprocess.run(
            sysctl_cmd, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            if "ethernet_" in line or "wifi_" in line:
                sid = line.split()[-1]
                if vpn_active and dns_servers:
                    subprocess.run(["connmanctl", "config", sid, "--nameservers"] + dns_servers, check=False)
                    subprocess.run(["connmanctl", "config", sid, "--domains", "."], check=False)
                else:
                    subprocess.run(["connmanctl", "config", sid, "--nameservers"], check=False)
                    subprocess.run(["connmanctl", "config", sid, "--domains"], check=False)

        if vpn_active and dns_servers:
            with open("/etc/resolv.conf", "w") as f:
                f.write("# Hardened VPN DNS\n")
                for dns in dns_servers:
                    f.write(f"nameserver {dns}\n")

    except Exception as e:
        log_message(f"DNS setup failed: {e}", 3)


def disable_connman_ipv6():
    try:
        sysctl_cmd = ["sysctl", "-w", "net.ipv6.conf.all.disable_ipv6=1"]
        subprocess.run(
            sysctl_cmd, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            sid = line.split()[-1]
            if sid.startswith(("ethernet_", "wifi_")):
                subprocess.run(
                    ["connmanctl", "config", sid, "--ipv6", "off"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
    except Exception as e:
        log_message(f"IPv6 disabling routine failed: {e}", 3)


def enable_connman_ipv6():
    try:
        sysctl_cmd = ["sysctl", "-w", "net.ipv6.conf.all.disable_ipv6=0"]
        subprocess.run(
            sysctl_cmd, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            sid = line.split()[-1]
            if sid.startswith(("ethernet_", "wifi_")):
                subprocess.run(
                    ["connmanctl", "config", sid, "--ipv6", "auto"],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
    except Exception as e:
        log_message(f"IPv6 enabling routine failed: {e}", 3)


def is_physically_connected(interface):
    import os

    carrier_path = f"/sys/class/net/{interface}/carrier"
    operstate_path = f"/sys/class/net/{interface}/operstate"

    try:
        if interface.startswith("wlan"):
            if os.path.exists(operstate_path):
                with open(operstate_path, 'r') as f:
                    return f.read().strip().lower() in ['up', 'dormant']
            return False

        if os.path.exists(carrier_path):
            try:
                with open(carrier_path, 'r') as f:
                    return f.read().strip() == '1'
            except OSError as e:
                if e.errno == 22 and os.path.exists(operstate_path):
                    with open(operstate_path, 'r') as f:
                        return f.read().strip().lower() == 'up'
                return False

        return False

    except Exception as e:
        log_message(f"Carrier status check failed for {interface}: {e}", 3)
        return False
