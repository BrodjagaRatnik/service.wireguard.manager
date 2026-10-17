""" LibreELEC ./resources/lib/providers/routing.py """
import os
import re
import subprocess
import socket
import time
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


def get_system_nameservers() -> list:
    nameservers = []
    try:
        if os.path.exists("/etc/resolv.conf") is True:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("nameserver") is True and len(stripped.split()) > 1:
                        candidate = stripped.split()[1]
                        if candidate not in nameservers:
                            nameservers.append(candidate)
    except Exception as resolver_err:
        log_message(f"Routing: System resolver read failure: {resolver_err}", 2)
    return nameservers


def probe_tcp_latency(target_host: str, target_port: int, timeout_seconds: float) -> float:
    latency_ms = None
    try:
        start_t = time.perf_counter()
        probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe_socket.settimeout(timeout_seconds)
        probe_socket.connect((target_host, target_port))
        probe_socket.close()
        latency_ms = (time.perf_counter() - start_t) * 1000.0
    except Exception:
        latency_ms = None
    return latency_ms


def probe_icmp_latency(target_host: str, timeout_seconds: float) -> float:
    latency_ms = None
    try:
        wait_seconds = max(1, int(timeout_seconds))
        out_ping = subprocess.check_output(
            ["ping", "-c", "1", "-W", str(wait_seconds), target_host],
            text=True, stderr=subprocess.DEVNULL, timeout=wait_seconds + 1
        )
        for line in out_ping.splitlines():
            if "time=" in line:
                latency_ms = float(line.split("time=")[-1].split()[0])
                break
    except Exception:
        latency_ms = None
    return latency_ms


def probe_endpoint_latency(
    target_host: str,
    target_port: int,
    timeout_seconds: float,
    require_tls_style_tcp: bool = False
) -> float:
    if require_tls_style_tcp is False:
        icmp_result = probe_icmp_latency(target_host, timeout_seconds)
        if icmp_result is not None:
            return icmp_result
    tcp_result = probe_tcp_latency(target_host, target_port, timeout_seconds)
    if tcp_result is not None:
        return tcp_result
    if require_tls_style_tcp is True:
        return probe_icmp_latency(target_host, timeout_seconds)
    return None


def check_internet_infrastructure(
    latency_threshold_ms: float = 250.0,
    probe_timeout_seconds: float = 2.0
) -> dict:
    report = {
        "gateway_ok": False,
        "gateway": None,
        "interface_ok": False,
        "interface": None,
        "mtu_readable": False,
        "physical_mtu": None,
        "nameservers": [],
        "best_latency_ms": None,
        "infrastructure_ok": False,
    }

    local_gateway = get_default_gateway()
    if local_gateway is not None and str(local_gateway).strip() != "":
        report["gateway_ok"] = True
        report["gateway"] = str(local_gateway)

    target_iface = None
    try:
        from vpn_utils import get_active_interface
        target_iface = get_active_interface()
        if not target_iface:
            out_route = subprocess.check_output(["ip", "route", "show", "default"], text=True)
            for line in out_route.splitlines():
                if "dev" in line and "wg" not in line:
                    parts = line.split()
                    idx = parts.index("dev")
                    if idx + 1 < len(parts):
                        target_iface = parts[idx + 1]
                        break
    except Exception as iface_err:
        log_message(f"Routing: Infrastructure interface discovery failure: {iface_err}", 2)

    if target_iface:
        report["interface"] = str(target_iface)
        try:
            mtu_path = f"/sys/class/net/{target_iface}/mtu"
            if os.path.exists(mtu_path) is True:
                with open(mtu_path, "r") as f:
                    report["physical_mtu"] = int(f.read().strip())
                report["mtu_readable"] = True
            report["interface_ok"] = True
        except Exception as mtu_read_err:
            log_message(f"Routing: Infrastructure MTU read failure: {mtu_read_err}", 2)

    report["nameservers"] = get_system_nameservers()

    for ns_host in report["nameservers"]:
        ns_latency = probe_tcp_latency(ns_host, 53, probe_timeout_seconds)
        if ns_latency is not None:
            if report["best_latency_ms"] is None or ns_latency < report["best_latency_ms"]:
                report["best_latency_ms"] = ns_latency

    latency_ok = False
    if report["best_latency_ms"] is not None:
        if report["best_latency_ms"] <= latency_threshold_ms:
            latency_ok = True

    report["infrastructure_ok"] = report["gateway_ok"] and report["interface_ok"] and latency_ok

    log_message(
        f"Routing: Infrastructure check gateway={report['gateway']} iface={report['interface']} "
        f"mtu={report['physical_mtu']} dns={len(report['nameservers'])} "
        f"best_latency_ms={report['best_latency_ms']} verdict={report['infrastructure_ok']}",
        0
    )
    return report
