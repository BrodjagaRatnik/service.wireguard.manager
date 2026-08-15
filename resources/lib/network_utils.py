""" ./resources/lib/network_utils.py """
import json
import os
import re
import subprocess
from logger import log_message
from state_manager import get_file_path

CONFIG_DIR = "/storage/.config/wireguard/"


def get_default_gateway():
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
                line_parts = line.split()
                if "via" in line_parts:
                    return line_parts[line_parts.index("via") + 1]
    except Exception as e:
        log_message(f"Network Utils: Failed to resolve default gateway: {e}", 3)
    return None


def resolve_server_ip(sid):
    try:
        if "vpn_" in sid:
            parts = sid.split('_')
            if len(parts) >= 5 and all(p.isdigit() for p in parts[1:5]):
                return f"{parts[1]}.{parts[2]}.{parts[3]}.{parts[4]}"
    except Exception:
        pass
    return None


def get_dns_from_config(vpn_name):
    dns_list = []
    if not vpn_name:
        return dns_list

    search_terms = [w.strip().lower() for w in vpn_name.replace('-', '_').split('_') if len(w.strip()) > 1]
    if not search_terms:
        return dns_list

    target_path = None
    if os.path.exists(CONFIG_DIR):
        best_match_count = 0
        for f_name in os.listdir(CONFIG_DIR):
            f_lower = f_name.lower()
            if f_lower.endswith(('.config', '.conf')):
                match_count = 0
                for term in search_terms:
                    if term in f_lower:
                        match_count += 1
                if match_count > best_match_count:
                    best_match_count = match_count
                    target_path = os.path.join(CONFIG_DIR, f_name)

    if not target_path and os.path.exists(CONFIG_DIR):
        files = [f for f in os.listdir(CONFIG_DIR) if f.lower().endswith(('.config', '.conf'))]
        if files:
            target_path = os.path.join(CONFIG_DIR, files[0])

    if target_path:
        try:
            with open(target_path, 'r') as f:
                content = f.read()
                match = re.search(r"(?:WireGuard\.)?DNS\s*=\s*(.*)", content, re.IGNORECASE)
                if match:
                    dns_list = [d.strip() for d in match.group(1).split(",")]
                    log_message(f"Network Utils: Dynamically extracted DNS from resolved path: {target_path}", 0)
        except Exception as e:
            log_message(f"Network Utils: Error parsing file {target_path}: {e}", 3)

    return dns_list


def set_secure_dns(vpn_name=None, vpn_active=True):
    backup_path = get_file_path("dns_backup")
    try:
        if vpn_active:
            if backup_path and not os.path.exists(backup_path) and os.path.exists("/etc/resolv.conf"):
                try:
                    with open("/etc/resolv.conf", "r") as orig_f:
                        orig_lines = orig_f.readlines()
                    with open(backup_path, "w") as backup_f:
                        json.dump(orig_lines, backup_f)
                    log_message("Network Utils: Dynamic registry backup completed for resolv.conf", 0)
                except Exception:
                    pass

            dns_servers = get_dns_from_config(vpn_name)
            if dns_servers:
                lines = [f"nameserver {dns_ip}" for dns_ip in dns_servers]
                with open("/etc/resolv.conf", "w") as f:
                    f.write("\n".join(lines) + "\n")
                log_message(f"Network Utils: Enforced {len(dns_servers)} VPN DNS servers to resolv.conf", 0)
        else:
            restored = False
            if backup_path and os.path.exists(backup_path):
                try:
                    with open(backup_path, "r") as backup_f:
                        orig_lines = json.load(backup_f)
                    with open("/etc/resolv.conf", "w") as f:
                        f.writelines(orig_lines)
                    os.remove(backup_path)
                    restored = True
                    log_message("Network Utils: Successfully restored baseline platform DHCP DNS registers", 0)
                except Exception:
                    log_message("Network Utils: Dynamic backup recovery pass faulted internally", 2)

            if not restored:
                fallback_dns = []
                gateway_ip = None
                try:
                    gateway_ip = get_default_gateway()
                except Exception:
                    pass

                if not gateway_ip:
                    try:
                        route_output = subprocess.check_output(["ip", "route", "show"]).decode("utf-8")
                        for route_line in route_output.splitlines():
                            if "scope link" in route_line and "src" in route_line:
                                tokens = route_line.split()
                                raw_ip = tokens[0].split("/")[0]
                                octets = raw_ip.split(".")
                                if len(octets) == 4:
                                    gateway_ip = f"{octets[0]}.{octets[1]}.{octets[2]}.1"
                                    dev_index = tokens.index("dev") + 1
                                    interface_dev = tokens[dev_index]
                                    subprocess.call([
                                        "ip", "route", "add", "default", "via",
                                        gateway_ip, "dev", interface_dev
                                    ])
                                    log_message("Network Utils: Forced recovery of default system route", 1)
                                    break
                    except Exception:
                        pass

                if gateway_ip:
                    fallback_dns.append("nameserver " + str(gateway_ip).strip())

                try:
                    if os.path.exists("/etc/resolv.conf"):
                        with open("/etc/resolv.conf", "r") as current_f:
                            for current_line in current_f:
                                if current_line.strip().startswith("search"):
                                    fallback_dns.append(current_line.strip())
                except Exception:
                    pass

                with open("/etc/resolv.conf", "w") as f:
                    f.write("\n".join(fallback_dns) + "\n")
                log_message("Network Utils: Restored clean dynamic DHCP gateway fallback environment", 0)
    except Exception:
        log_message("Network Utils: Direct resolv.conf synchronization failed catastrophically", 3)


def toggle_sysctl_ipv6(disable=True):
    val_disable = "1" if disable else "0"
    val_ra_auto = "0" if disable else "1"
    targets = ["all", "default"]
    proc_path = "/proc/sys/net/ipv6/conf/"
    if os.path.exists(proc_path):
        try:
            active_adapters = [d for d in os.listdir(proc_path) if d not in ["lo", "wg0", "wireguard"]]
            targets.extend(active_adapters)
        except Exception:
            pass
    for interface in targets:
        try:
            subprocess.run(
                ["sysctl", "-w", f"net.ipv6.conf.{interface}.disable_ipv6={val_disable}"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["sysctl", "-w", f"net.ipv6.conf.{interface}.accept_ra={val_ra_auto}"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["sysctl", "-w", f"net.ipv6.conf.{interface}.autoconf={val_ra_auto}"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            continue


def manage_connman_services(ipv6_mode="off"):
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            if "_" in line:
                parts = line.strip().split()
                if parts:
                    sid = parts[-1]
                    subprocess.run(
                        ["connmanctl", "config", sid, "--ipv6", ipv6_mode],
                        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
    except Exception:
        pass


def disable_connman_ipv6():
    try:
        toggle_sysctl_ipv6(disable=True)
        manage_connman_services(ipv6_mode="off")
        gw_out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        local_dev = None
        for line in gw_out.splitlines():
            if "dev" in line and "wg0" not in line:
                tokens = line.split("dev")[-1].strip().split()
                if tokens:
                    local_dev = tokens[0]
                    break
        if local_dev:
            subprocess.run(
                ["sysctl", "-w", f"net.ipv6.conf.{local_dev}.disable_ipv6=1"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["sysctl", "-w", f"net.ipv6.conf.{local_dev}.accept_ra=0"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["ip", "-6", "addr", "flush", "dev", local_dev],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    except Exception:
        pass


def enable_connman_ipv6():
    toggle_sysctl_ipv6(disable=False)
    manage_connman_services(ipv6_mode="auto")


def is_physically_connected(interface):
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
        log_message(f"Network Utils: Carrier status check failed for {interface}: {e}", 3)
        return False


def get_profile_allowed_ips(sid):
    try:
        config_path = f"/storage/.config/wireguard/{sid}.config"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                for line in f:
                    if "allowedips" in line.lower() and "=" in line:
                        return line.split("=")[-1].strip()
    except Exception:
        pass
    return ""
