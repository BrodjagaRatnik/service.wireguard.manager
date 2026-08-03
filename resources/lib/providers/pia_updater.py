""" ./resources/lib/providers/pia_updater.py
https://github.com/pia-foss/manual-connections/
    dns_str = "10.0.0.243, 10.0.0.241, 1.1.1.1, 9.9.9.9"

SERVER_LIST_URL = "https://serverlist.piaservers.net/vpninfo/servers/v6"
"""
import json
import os
import ssl
import time
import socket
import urllib.error
import urllib.parse
import urllib.request
from logger import log_message
from providers import routing
from providers import pia_config

SERVER_LIST_URL = "https://serverlist.piaservers.net/vpninfo/servers/v6"


def update(user, password, country_ids, config_dir):
    selected_list = [i.strip().lower() for i in country_ids.split(',') if i.strip()]

    from state_manager import get_active_vpn

    if os.path.exists(config_dir) is True:
        for filename in os.listdir(config_dir):
            if filename.startswith("pia_") and filename.endswith(".config"):
                file_id = filename.replace("pia_", "").replace(".config", "")
                if file_id not in selected_list:
                    try:
                        os.remove(os.path.join(config_dir, filename))
                    except Exception as r_err:
                        log_message(f"PIA Updater: Server array tracking error skipped {r_err}", 3)

    raw_data = None
    for attempt in range(3):
        try:
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(SERVER_LIST_URL, headers={'User-Agent': 'PIA-VPN/3.5.0 (Linux)'})

            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                raw_payload = resp.read().decode('utf-8').strip()
                if "\n" in raw_payload:
                    raw_data = raw_payload.splitlines()[0].strip()
                else:
                    raw_data = raw_payload
            break
        except urllib.error.URLError as url_err:
            if "101" in str(url_err) or "unreachable" in str(url_err).lower():
                if attempt == 0:
                    time.sleep(3.0)
                    continue
            log_message(f"PIA Updater: URL Error: {url_err}", 3)
            return False
        except Exception as fetch_err:
            log_message(f"PIA Updater: Fetch Error: {fetch_err}", 3)
            return False

    if raw_data is None:
        return False

    try:
        data = json.loads(raw_data)
        name_mapping = {}
        compiled_files_count = 0
        total_nodes_count = 0

        config_latency = getattr(pia_config, "MAX_LATENCY", 0.05)
        latency_tiers = [config_latency, 0.15, 0.30, 0.60, 1.00]

        for rid in selected_list:
            region_node = None
            for r in data.get('regions', []):
                if r['id'].lower() == rid:
                    region_node = r
                    break

            if not region_node or region_node.get('offline', False):
                continue

            servers_dict = region_node.get('servers', {})
            if not isinstance(servers_dict, dict):
                continue

            wg_servers = servers_dict.get('wg', [])
            if not wg_servers or not isinstance(wg_servers, list):
                continue

            valid_candidates = []
            for srv in wg_servers:
                if isinstance(srv, dict) and srv.get('ip') and srv.get('cn'):
                    valid_candidates.append(srv)

            if not valid_candidates:
                continue

            log_message(f"PIA Speed Profiler: Evaluating nodes for region profile ID: {rid}", 0)
            verified_servers = []

            for max_latency in latency_tiers:
                log_message(f"PIA Speed Profiler: Scanning nodes under threshold tier: {max_latency * 1000:.0f}ms", 0)
                for srv in valid_candidates:
                    srv_ip = str(srv.get('ip'))
                    start_t = time.time()
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(max_latency)
                        s.connect((srv_ip, 443))
                        s.close()
                        elapsed = time.time() - start_t
                        verified_servers.append((elapsed, srv))
                    except (socket.timeout, ConnectionRefusedError, OSError):
                        continue
                if verified_servers:
                    break

            if verified_servers:
                verified_servers.sort(key=lambda x: x[0])
                final_servers = [item[1] for item in verified_servers]
                fastest_ms = float(verified_servers[0][0]) * 1000.0
                log_message(f"PIA Speed Profiler: Fastest server discovered responding in {fastest_ms:.1f}ms", 0)
                log_message("PIA Speed Profiler: Sorting array. Placing optimal node at index zero.", 0)
            else:
                log_message("PIA Speed Profiler: No targets cleared latency ceiling. Using raw payload metrics.", 2)
                final_servers = valid_candidates

            server_ips = [str(x.get('ip')) for x in final_servers]
            server_cns = [str(x.get('cn')) for x in final_servers]

            region_name = str(region_node.get('name', rid))
            safe_key = f"PIA_{region_name.replace(' ', '_')}".lower()
            name_mapping[safe_key] = rid

            v_temp = region_name.replace('Optimized', 'Optimize')
            clean_region_name = v_temp.replace('optimized', 'Optimize')

            os.makedirs(config_dir, exist_ok=True)
            file_path = os.path.join(config_dir, f"pia_{rid}.config")
            with open(file_path, 'w') as f:
                f.write("[provider_wireguard]\nType = WireGuard\n")
                f.write(f"Name = PIA_{clean_region_name.replace(' ', '_')}\n")
                f.write(f"Host = {server_ips[0]}\n")
                f.write(f"WireGuard.Pool = {','.join(server_ips)}\n")
                f.write(f"WireGuard.CN_Pool = {','.join(server_cns)}\n")
                f.write("WireGuard.MTU = 1380\n")
                f.write("WireGuard.PublicKey = placeholder\n")
                f.write("WireGuard.Address = 10.0.0.1/32\n")

            compiled_files_count += 1
            total_nodes_count += len(server_ips)

        from state_manager import get_file_path
        map_path = get_file_path('pia_map')
        if map_path is not None:
            try:
                with open(map_path, 'w') as mf:
                    json.dump(name_mapping, mf)
            except Exception:
                pass

        from state_manager import write_state
        if os.path.exists('/sys/class/net/wg0') is True:
            log_message("PIA Updater: Active interface detected. Scheduling deferred reconnect.", 1)
            boot_target = get_active_vpn()
            if boot_target:
                write_state('reconnect', str(boot_target))

        return True

    except Exception as e:
        log_message(f"PIA Updater: {e}", 3)
        return False


def build_final_config(wg_data, pk, server_ip, region_id, region_name=None, raw_cn_str="", allowed_ips_mode=1):
    dns_str = "10.0.0.243, 10.0.0.241"
    if not region_name:
        region_name = region_id
    safe_name = region_name.replace(' ', '_')
    port_str = str(wg_data.get('server_port', '1337'))
    allowed_ips = routing.get_allowed_ips(use_split_default=True)
    dynamic_mtu = routing.get_optimal_mtu()

    return (
        "[provider_wireguard]\n"
        "Type = WireGuard\n"
        f"Name = PIA_{safe_name}\n"
        f"Host = {server_ip}\n"
        f"WireGuard.MTU = {dynamic_mtu}\n"
        f"WireGuard.Address = {wg_data['peer_ip']}/32\n"
        f"WireGuard.PrivateKey = {pk}\n"
        f"WireGuard.PublicKey = {wg_data['server_key']}\n"
        f"WireGuard.DNS = {dns_str}\n"
        f"WireGuard.EndpointPort = {port_str}\n"
        f"WireGuard.AllowedIPs = {allowed_ips}\n"
        "WireGuard.PersistentKeepalive = 25\n"
        f"WireGuard.CN_Pool = {raw_cn_str}\n"
    )
