''' .resources/lib/providers/nordvpn.py

    user_data = fetch_url("https://api.nordvpn.com/v1/users/services/credentials", token)

        url = (
            "https://api.nordvpn.com/v1/servers/recommendations"
            f"?filters[servers_technologies][identifier]=wireguard_udp"
            f"&filters[country_id]={c_id.strip()}&limit=1"
        )

'''
import os
import socket
import subprocess
import sys
import xbmcaddon
import xbmcvfs
from logger import log_message
from utils import fetch_url

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
_LIB = xbmcvfs.translatePath(os.path.join(_ADDON.getAddonInfo('path'), 'resources', 'lib'))

sys.path = [p for p in sys.path if 'script.module.srgssr' not in p]
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

NORD_DNS = "103.86.96.100, 103.86.99.100"


def update(token, country_ids, config_dir):
    log_message("NordVPN: Starting update process.", 0)

    user_data = fetch_url("https://api.nordvpn.com/v1/users/services/credentials", token)

    if not user_data or 'nordlynx_private_key' not in user_data:
        log_message(f"NordVPN: Private Key fetch failed. Response: {user_data}", 3)
        return False

    priv_key = user_data['nordlynx_private_key']
    log_message("NordVPN: Private key successfully retrieved.", 0)

    ids = [i.strip() for i in country_ids.split(',')]
    success_count = 0

    for c_id in ids:
        log_message(f"NordVPN: Fetching recommendation for Country ID: {c_id}", 0)
        url = (
            "https://api.nordvpn.com/v1/servers/recommendations"
            f"?filters[servers_technologies][identifier]=wireguard_udp"
            f"&filters[country_id]={c_id.strip()}&limit=1"
        )

        servers = fetch_url(url)

        if not servers or not isinstance(servers, list) or len(servers) == 0:
            log_message(f"NordVPN: No servers found for Country ID {c_id}", 2)
            continue

        data = servers[0]
        try:
            hostname = data.get('hostname')
            log_message(f"NordVPN: Processing server: {hostname}", 0)

            try:
                ip = socket.gethostbyname(hostname)
            except Exception as dns_err:
                log_message(f"NordVPN: DNS failed for {hostname}: {dns_err}", 3)
                continue

            country_name = data['locations'][0]['country']['name'].replace(' ', '_')

            wg_tech = None
            for t in data.get('technologies', []):
                if t.get('identifier') == 'wireguard_udp':
                    wg_tech = t
                    break

            if not wg_tech:
                log_message(f"NordVPN: 'wireguard_udp' tech not found for {hostname}", 3)
                continue

            meta = wg_tech.get('metadata', [])
            pub_key = next((m['value'] for m in meta if m['name'] == 'public_key'), None)
            port = next((m['value'] for m in meta if m['name'] == 'port'), '51820')

            if not pub_key:
                log_message(f"NordVPN: Public Key missing in metadata for {hostname}", 3)
                continue

            config = (
                "[provider_wireguard]\n"
                "Type = WireGuard\n"
                f"Name = NordVPN_{country_name}\n"
                f"Host = {ip}\n"
                "WireGuard.Address = 10.5.0.2/32\n"
                "WireGuard.ListenPort = 51820\n"
                "WireGuard.MTU = 1420\n"
                f"WireGuard.PrivateKey = {priv_key}\n"
                f"WireGuard.PublicKey = {pub_key}\n"
                f"WireGuard.DNS = {NORD_DNS}\n"
                "WireGuard.AllowedIPs = 0.0.0.0/0\n"
                f"WireGuard.EndpointPort = {port}\n"
                "WireGuard.PersistentKeepalive = 25\n"
            )

            file_path = os.path.join(config_dir, f"nord_{country_name.lower()}.config")
            with open(file_path, 'w') as f:
                f.write(config)

            log_message(f"NordVPN: Successfully saved config: {file_path}", 0)
            success_count += 1

        except Exception as e:
            log_message(f"NordVPN: Critical error processing server ID {c_id}: {e}", 3)
            continue

    if success_count > 0:
        log_message(f"NordVPN: Finalizing {success_count} configs.", 0)
        finalize_configs(config_dir)
        return True

    log_message("NordVPN: Finished loop with 0 successes.", 0)
    return False


def finalize_configs(config_dir):
    try:
        files = [os.path.join(config_dir, f) for f in os.listdir(config_dir) if f.startswith("nord_")]
        if files:
            subprocess.run(["chmod", "600"] + files, check=False)
            subprocess.run(["systemctl", "restart", "connman-vpn"], check=False)
            log_message("NordVPN: Configs updated and service restarted.", 1)
    except Exception as e:
        log_message(f"NordVPN: Finalization failed: {e}", 3)
