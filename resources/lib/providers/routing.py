""" ./resources/lib/providers/routing.py """
import os
import re
import subprocess
from logger import log_message
from network_utils import get_default_gateway


def get_allowed_ips(
    lan_bypass: bool = False,
    custom_bypass_subnets: list = None,
    use_split_default: bool = False,
    provider_requires_split: bool = False
) -> str:
    if use_split_default is True or provider_requires_split is True:
        return "0.0.0.0/1, 128.0.0.0/1"
    return "0.0.0.0/0, ::/0"


def get_optimal_mtu() -> str:
    chosen_mtu = "1380"
    try:
        from vpn_utils import get_active_interface
        target_iface = get_active_interface()
        if not target_iface:
            out_route = subprocess.check_output(["ip", "route", "show", "default"], text=True)
            for line in out_route.splitlines():
                if "dev" in line:
                    parts = line.split()
                    idx = parts.index("dev")
                    if idx + 1 < len(parts):
                        target_iface = parts[idx + 1]
                        break
        if target_iface and (os.path.exists(f"/sys/class/net/{target_iface}/mtu") is True):
            with open(f"/sys/class/net/{target_iface}/mtu", "r") as f:
                phys_mtu = int(f.read().strip())
            calculated_wg_mtu = phys_mtu - 80
            if calculated_wg_mtu >= 1420:
                chosen_mtu = "1420"
            elif calculated_wg_mtu >= 1400:
                chosen_mtu = "1400"
            elif calculated_wg_mtu >= 1380:
                chosen_mtu = "1380"
            else:
                chosen_mtu = "1280"
    except Exception as mtu_err:
        log_message(f"Routing: Kernel MTU calculation failure: {mtu_err}", 2)
    return chosen_mtu


def setup_vpn_routing(sid: str, requires_endpoint_route: bool) -> None:
    if requires_endpoint_route is True:
        try:
            from network_utils import resolve_server_ip
            server_ip = resolve_server_ip(sid)
            if not server_ip:
                from network_utils import CONFIG_DIR
                config_file = os.path.join(CONFIG_DIR, f"{sid}.config")
                if os.path.exists(config_file):
                    with open(config_file, "r") as f:
                        for line in f:
                            if "host" in line.lower() and "=" in line:
                                raw_host = line.split("=")[-1].strip()
                                ip_match = re.search(
                                    r"([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})",
                                    raw_host
                                )
                                if ip_match:
                                    server_ip = ip_match.group(1)
                                    break
            if server_ip:
                gw_out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
                local_gw = get_default_gateway()
                local_dev = None
                for line in gw_out.splitlines():
                    if "dev" in line and "wg0" not in line:
                        parts = line.split("dev")[-1].strip().split()
                        if parts:
                            local_dev = parts
                            break
                if local_gw is not None and local_dev is not None:
                    subprocess.run(
                        ["ip", "route", "add", server_ip, "via", local_gw, "dev", local_dev],
                        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
        except Exception:
            pass
        try:
            subprocess.run(
                ["ip", "route", "add", "0.0.0.0/128.0.0.0", "dev", "wg0"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["ip", "route", "add", "128.0.0.0/128.0.0.0", "dev", "wg0"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            from network_utils import get_dns_from_config
            dns_ips = get_dns_from_config(sid)
            for dns_target in dns_ips:
                subprocess.run(
                    ["ip", "route", "del", dns_target],
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        except Exception:
            pass
    else:
        try:
            subprocess.run(
                ["ip", "route", "add", "default", "dev", "wg0"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass
