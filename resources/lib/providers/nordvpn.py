""" .resources/lib/providers/nordvpn.py

    user_data = fetch_nord_url("https://api.nordvpn.com/v1/users/services/credentials", token=token)

        url = (
            "https://api.nordvpn.com/v1/servers/recommendations"
            f"?filters[servers_technologies][identifier]=wireguard_udp"
            f"&filters[country_id]={c_id.strip()}&limit=1"
        )

"""
import kodi_env
import os
import re
import socket
import subprocess
import sys
import time
from logger import log_message
from providers.nord_utils import fetch_nord_url
from state_manager import get_active_vpn, write_state
import dialog

NORD_DNS = "103.86.96.100, 103.86.99.100"


def update(token, country_ids, config_dir):
    addon_obj = kodi_env.get_addon_instance()
    if not addon_obj:
        return False

    addon_path = kodi_env.ADDON_DIR
    lib_path = os.path.join(addon_path, "resources", "lib")

    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)

    progress = dialog.TaskProgress("NordVPN Profile Update", "Retrieving credentials...", enabled=True)

    log_message("NordVPN: Starting update process.", 0)
    active_vpn_name = get_active_vpn()

    t_start_auth = time.perf_counter()
    user_data = fetch_nord_url("https://api.nordvpn.com/v1/users/services/credentials", token=token)
    t_elapsed_auth = (time.perf_counter() - t_start_auth) * 1000.0
    log_message(f"NordVPN: Credentials endpoint took {t_elapsed_auth:.2f}ms", 0)

    if not user_data or "nordlynx_private_key" not in user_data:
        log_message(f"NordVPN: Private Key fetch failed. Response {user_data}", 3)
        progress.close()
        return False

    priv_key = user_data["nordlynx_private_key"]
    log_message("NordVPN: Private key successfully retrieved.", 0)

    ids = [i.strip() for i in country_ids.split(",")]
    total_ids = len(ids)
    success_count = 0
    cancelled = False

    for c_pos, c_id in enumerate(ids, start=1):
        if progress.iscanceled():
            log_message("NordVPN: Update cancelled by user.", 2)
            cancelled = True
            break

        progress.update(
            int(((c_pos - 1) * 100) / total_ids),
            f"Country {c_pos}/{total_ids}: fetching recommendations"
        )

        log_message(f"NordVPN: Fetching recommendations for Country ID {c_id}", 0)
        url = (
            "https://api.nordvpn.com/v1/servers/recommendations"
            f"?filters[servers_technologies][identifier]=wireguard_udp"
            f"&filters[country_id]={c_id.strip()}&limit=5"
        )

        t_start_srv = time.perf_counter()
        servers = fetch_nord_url(url)
        t_elapsed_srv = (time.perf_counter() - t_start_srv) * 1000.0
        log_message(f"NordVPN: Recommendation query for ID {c_id} took {t_elapsed_srv:.2f}ms", 0)

        if not servers or not isinstance(servers, list) or len(servers) == 0:
            log_message(f"NordVPN: No servers found for Country ID {c_id}", 2)
            continue

        config_written_for_country = 0

        for idx, data in enumerate(servers, start=1):
            try:
                hostname = data.get("hostname", "")
                log_message(f"NordVPN: Processing candidate {idx}/{len(servers)} ({hostname})", 0)

                progress.update(
                    int((((c_pos - 1) * 5 + idx) * 100) / (total_ids * 5)),
                    f"Country {c_pos}/{total_ids} - server {idx}/{len(servers)}: {hostname}"
                )

                try:
                    ip = socket.gethostbyname(hostname)
                except Exception:
                    try:
                        ip = socket.getaddrinfo(hostname, None, socket.AF_INET)[0][4][0]
                    except Exception as dns_err:
                        log_message(f"NordVPN: DNS failed for {hostname} {dns_err}", 2)
                        continue

                country_raw = data["locations"][0]["country"]["name"]
                city_raw = data["locations"][0]["country"]["city"]["name"]
                server_num = "".join(filter(str.isdigit, hostname))
                friendly_name = f"NordVPN {country_raw} {city_raw} {server_num}"
                wg_tech = None
                for t in data.get("technologies", []):
                    if t.get("identifier") == "wireguard_udp":
                        wg_tech = t
                        break

                if not wg_tech:
                    log_message(f"NordVPN: 'wireguard_udp' tech not found for {hostname}", 2)
                    continue

                meta = wg_tech.get("metadata", [])
                pub_key = next((m["value"] for m in meta if m["name"] == "public_key"), None)
                port = next((m["value"] for m in meta if m["name"] == "port"), "51820")

                if not pub_key:
                    log_message(f"NordVPN: Public Key missing in metadata for {hostname}", 2)
                    continue

                config = (
                    "[provider_wireguard]\n"
                    "Type = WireGuard\n"
                    f"Name = {friendly_name}\n"
                    f"Host = {ip}\n"
                    "WireGuard.Address = 10.5.0.2/32\n"
                    "WireGuard.ListenPort = 51820\n"
                    "WireGuard.MTU = 1420\n"
                    f"WireGuard.PrivateKey = {priv_key}\n"
                    f"WireGuard.PublicKey = {pub_key}\n"
                    f"WireGuard.DNS = {NORD_DNS}\n"
                    "WireGuard.AllowedIPs = 0.0.0.0/0, ::/0\n"
                    f"WireGuard.EndpointPort = {port}\n"
                    "WireGuard.PersistentKeepalive = 25\n"
                )

                code_match = re.match(r"^([a-zA-Z]+)", hostname)
                country_code = code_match.group(1).lower() if code_match else country_raw[:3].lower()

                base_name = f"nord_{country_code}{idx:02d}"
                if len(base_name) > 15:
                    log_message(
                        f"NordVPN: generated interface name '{base_name}' exceeds 15 chars, "
                        f"truncating (host: {hostname})", 2
                    )
                    base_name = base_name[:15]

                file_path = os.path.join(config_dir, f"{base_name}.config")
                with open(file_path, "w") as f:
                    f.write(config)

                log_message(f"NordVPN: Saved candidate {file_path} (host: {hostname})", 0)
                success_count += 1
                config_written_for_country += 1

            except Exception as e:
                log_message(f"NordVPN: Candidate {idx} failed: {e}", 2)
                continue

        if config_written_for_country == 0:
            log_message(f"NordVPN: All {len(servers)} candidate servers failed for Country ID {c_id}", 3)

    progress.close()

    if success_count > 0:
        log_message(f"NordVPN: Finalizing {success_count} configs.", 0)
        finalize_configs(config_dir)

        if os.path.exists('/sys/class/net/wg0') is True and active_vpn_name:
            log_message("NordVPN: Active interface detected. Scheduling deferred reconnect.", 1)
            write_state('reconnect', str(active_vpn_name))
        return True

    if cancelled:
        return False

    log_message(f"NordVPN: Update failed for IDs {country_ids}", 3)
    return False


def finalize_configs(config_dir):
    try:
        files = [os.path.join(config_dir, f) for f in os.listdir(config_dir) if f.startswith("nord_")]
        if files:
            subprocess.run(["chmod", "600"] + files, check=False)
            subprocess.run(["systemctl", "restart", "connman-vpn"], check=False)
            log_message("NordVPN: Configs updated and service restarted.", 0)
    except Exception as e:
        log_message(f"NordVPN: Finalization failed: {e}", 3)

    finally:
        kodi_env.clear_script_globals()
