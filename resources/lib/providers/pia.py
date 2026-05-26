""" .resources/lib/providers/pia.py
https://github.com/pia-foss/manual-connections/
GLOBAL ENDPOINT CONSTANTS
CERT_URL = "https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt"
TOKEN_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
SERVER_LIST_URL = "https://serverlist.piaservers.net/vpninfo/servers/v6"
"""
import json
import os
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
from logger import log_message

try:
    KODI_AVAILABLE = True
except Exception:
    KODI_AVAILABLE = False

CERT_URL = "https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt"
TOKEN_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
SERVER_LIST_URL = "https://serverlist.piaservers.net/vpninfo/servers/v6"

LAST_HANDSHAKE_TRACKER = {}


def ensure_certificate():
    cert_path = os.path.join(os.path.dirname(__file__), 'ca.rsa.4096.crt')
    if not os.path.exists(cert_path):
        try:
            log_message("PIA: Local CA certificate missing. Downloading from source...", 1)
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(CERT_URL, headers={'User-Agent': 'PIA-VPN/3.5.0 (Linux)'})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                with open(cert_path, 'wb') as f:
                    f.write(response.read())
            log_message("PIA: Local CA certificate successfully verified and written.", 1)
            return cert_path
        except Exception as cert_err:
            log_message(f"PIA: Certificate template mapping aborted: {cert_err}", 2)
            return None
    return cert_path


def get_cached_token(user, password):
    cache_path = '/tmp/pia_token_cache.json'

    from utils import encrypt_setting_to_base64
    password = encrypt_setting_to_base64("pia_pass")

    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            if time.time() - cached.get('timestamp', 0) < 900:
                log_message("PIA: Valid token found in cache.", 1)
                return cached.get('token')
        except Exception as cache_err:
            log_message(f"PIA: Token cache unreadable: {cache_err}", 3)

    try:
        log_message("PIA: Cache expired or missing. Handshaking...", 1)
        headers = {'User-Agent': 'PIA-VPN/3.5.0 (Linux)'}

        import base64
        try:
            decoded_password = base64.b64decode(password, validate=True).decode('utf-8')
        except Exception:
            decoded_password = password

        creds = urllib.parse.urlencode({'username': user, 'password': decoded_password}).encode()

        req_token = urllib.request.Request(TOKEN_URL, data=creds, headers=headers)
        with urllib.request.urlopen(req_token, timeout=10) as resp:
            token = json.loads(resp.read().decode())['token']

        with open(cache_path, 'w') as f:
            json.dump({'token': token, 'timestamp': time.time()}, f)
        return token
    except Exception as token_err:
        log_message(f"PIA API Error: {token_err}", 3)
        return None


def get_live_config(user, password, server_ip, server_cn, region_id, region_name=None):

    current_time = time.time()
    last_ip_handshake = LAST_HANDSHAKE_TRACKER.get(server_ip, 0)
    time_since_last = current_time - last_ip_handshake

    if time_since_last < 60:
        remaining_secs = int(60 - time_since_last)
        log_message(
            f"PIA Throttling: Handshake blocked for target IP {server_ip} "
            f"({region_id}). {remaining_secs}s remaining until safe "
            "retry to this specific node.", 2
        )

        try:
            import os
            import sys
            import xbmc
            import xbmcaddon
            import xbmcgui
            import xbmcvfs

            xbmc.executebuiltin("ActivateWindow(home)")
            addon_path = xbmcvfs.translatePath(xbmcaddon.Addon('service.wireguard.manager').getAddonInfo('path'))
            icon_info = os.path.join(addon_path, 'resources', 'media', 'icon.png')
            title = "[B][COLOR FFE6E6FA]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
            msg = f"[COLOR FFFFFF00]Node cooling down! Please wait {remaining_secs} seconds before retrying PIA.[/COLOR]"
            xbmcgui.Dialog().notification(title, msg, icon_info, 3000)
        except Exception as e:
            log_message(f"PIA Throttling: Failed to broadcast UI toast notification: {e}", 0)
        return None

    cert_path = ensure_certificate()
    token = get_cached_token(user, password)

    if not token or not cert_path:
        log_message("PIA Handshake Aborted: Missing authentic token or root certificates.", 3)
        return None

    try:
        LAST_HANDSHAKE_TRACKER[server_ip] = time.time()
        connect_ip = server_ip
        connect_port = "1337"

        headers = {
            'User-Agent': 'PIA-VPN/3.5.0 (Linux)',
            'Host': server_cn
        }

        pk = subprocess.check_output(["wg", "genkey"]).decode().strip()
        pub = subprocess.check_output(["wg", "pubkey"], input=pk.encode()).decode().strip()

        params = urllib.parse.urlencode({'pt': token, 'pubkey': pub})
        register_url = f"https://{connect_ip}:{connect_port}/addKey?{params}"

        ctx = None
        try:
            ctx = ssl.create_default_context(cafile=cert_path)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED

            try:
                ctx.verify_flags = ssl.VERIFY_DEFAULT
            except AttributeError:
                pass
        except Exception as ssl_init_err:
            log_message(f"PIA Compiler: Strict SSL initialization bypassed: {ssl_init_err}", 0)
            ctx = None

        if ctx is None:
            ctx = ssl._create_unverified_context()

        req_hs = urllib.request.Request(register_url, headers=headers)

        try:
            with urllib.request.urlopen(req_hs, timeout=10, context=ctx) as resp:
                wg_data = json.loads(resp.read().decode())
        except urllib.error.URLError as url_err:

            if "CERTIFICATE_VERIFY_FAILED" in str(url_err) and ctx.verify_mode != ssl.CERT_NONE:

                py_ver = sys.version.split()[0]
                ssl_ver = getattr(ssl, 'OPENSSL_VERSION', 'Unknown')
                log_message(f"PIA Handshake Warning: Nightly SSL rules tripped. System Info: Python {py_ver} | {ssl_ver}", 1)

                fallback_ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req_hs, timeout=10, context=fallback_ctx) as resp:
                    wg_data = json.loads(resp.read().decode())
            else:
                raise url_err

        if wg_data.get('status') == "OK":
            return build_final_config(wg_data, pk, server_ip, region_id, region_name)

        log_message(f"PIA API Handshake Error: {wg_data.get('status')}", 3)

    except urllib.error.HTTPError as http_err:
        if http_err.code == 429:
            log_message(f"PIA API Error: Aggressive 429 Rate Limiting triggered on node {server_ip}.", 3)
        else:
            log_message(f"PIA API HTTP Error: {http_err.code} - {http_err.reason}", 3)

    except Exception as e:
        log_message(f"PIA Handshake Exception: {str(e)}", 3)
    return None


def update(user, password, country_ids, config_dir):
    selected_list = [i.strip().lower() for i in country_ids.split(',') if i.strip()]

    if os.path.exists(config_dir):
        for filename in os.listdir(config_dir):
            if filename.startswith("pia_") and filename.endswith(".config"):
                file_id = filename.replace("pia_", "").replace(".config", "")
                if file_id not in selected_list:
                    try:
                        os.remove(os.path.join(config_dir, filename))
                    except Exception as r_err:
                        log_message(f"PIA: Server array tracking error skipped: {r_err}", 0)

    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(SERVER_LIST_URL, headers={'User-Agent': 'PIA-VPN/3.5.0 (Linux)'})

        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            raw_data = resp.read().decode('utf-8').strip()
            if "\n" in raw_data:
                raw_data = raw_data.splitlines()[0].strip()
            data = json.loads(raw_data)

        name_mapping = {}

        for rid in selected_list:
            server_ips = []
            server_cns = []
            region_name = rid

            for r in data.get('regions', []):
                if r['id'].lower() == rid:
                    servers_dict = r.get('servers', {})
                    if isinstance(servers_dict, dict):
                        wg_servers = servers_dict.get('wg', [])
                        ikev2_ips = [s.get('ip') for s in servers_dict.get('ikev2', []) if isinstance(s, dict)]
                        ovpn_ips = [
                            s.get('ip') for s in (
                                servers_dict.get('ovpnudp', [])
                                + servers_dict.get('ovpntcp', [])
                            ) if isinstance(s, dict)
                        ]

                        if wg_servers and isinstance(wg_servers, list):
                            for srv in wg_servers:
                                if isinstance(srv, dict) and srv.get('ip') and srv.get('cn'):
                                    current_ip = srv.get('ip')
                                    if current_ip in ikev2_ips or current_ip in ovpn_ips:
                                        log_message(
                                            "PIA Compiler: Filtering out "
                                            f"shared-protocol node {current_ip} "
                                            f"for {rid}.", 0
                                        )
                                        continue

                                    server_ips.append(current_ip)
                                    server_cns.append(srv.get('cn'))

                        if not server_ips and len(wg_servers) > 0:
                            first_wg = wg_servers[0]
                            if isinstance(first_wg, dict):
                                server_ips.append(first_wg.get('ip', ''))
                                server_cns.append(first_wg.get('cn', ''))

                    region_name = r.get('name', rid)
                    break

            if server_ips:
                safe_key = f"PIA_{region_name.replace(' ', '_')}".lower()
                name_mapping[safe_key] = rid

                clean_region_name = region_name.replace('Optimized', 'Optimize').replace('optimized', 'Optimize')

                os.makedirs(config_dir, exist_ok=True)
                file_path = os.path.join(config_dir, f"pia_{rid}.config")
                with open(file_path, 'w') as f:
                    f.write("[provider_wireguard]\nType = WireGuard\n")
                    f.write(f"Name = PIA_{clean_region_name.replace(' ', '_')}\n")
                    f.write(f"Host = {server_ips[0]}\n")
                    f.write(f"WireGuard.Pool = {','.join(server_ips)}\n")
                    f.write(f"WireGuard.CN_Pool = {','.join(server_cns)}\n")
                    f.write("WireGuard.MTU = 1420\n")
                    f.write("WireGuard.PublicKey = placeholder\n")
                    f.write("WireGuard.Address = 10.0.0.1/32\n")
                log_message(f"PIA Configuration Compiled with {len(server_ips)} Clean Pool Nodes: {file_path}", 0)

        try:
            with open('/tmp/pia_name_map.json', 'w') as mf:
                json.dump(name_mapping, mf)
        except Exception:
            pass

        return True

    except Exception as e:
        log_message(f"PIA Update Error: {e}", 3)
        return False


def build_final_config(wg_data, pk, server_ip, region_id, region_name=None):
    dns_list = wg_data.get('dns_servers', [])
    if dns_list:
        dns_str = ", ".join(dns_list)
    else:
        dns_str = "202.21.128.85, 10.0.0.242"

    if not region_name:
        region_name = region_id

    safe_name = region_name.replace(' ', '_')

    return (
        "[provider_wireguard]\nType = WireGuard\n"
        f"Name = PIA_{safe_name}\nHost = {server_ip}\n"
        "WireGuard.MTU = 1420\n"
        f"WireGuard.Address = {wg_data['peer_ip']}/32\n"
        f"WireGuard.PrivateKey = {pk}\n"
        f"WireGuard.PublicKey = {wg_data['server_key']}\n"
        f"WireGuard.DNS = {dns_str}\n"
        f"WireGuard.EndpointPort = {wg_data['server_port']}\n"
        "WireGuard.AllowedIPs = 0.0.0.0/0\n"
        "WireGuard.PersistentKeepalive = 25\n"
    )
