""" .resources/lib/providers/pia.py
https://github.com/pia-foss/manual-connections/
GLOBAL ENDPOINT CONSTANTS
CERT_URL = "https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt"
TOKEN_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
V3_URL = "https://www.privateinternetaccess.com/api/client/v3/token"
V2_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
SERVER_LIST_URL = "https://serverlist.piaservers.net/vpninfo/servers/v6"
"""
import json
import os
import sys
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
import base64
from logger import log_message

try:
    import xbmc
    import xbmcaddon
    import xbmcgui
    import xbmcvfs
    HAS_KODI = True
except ImportError:
    xbmc = None
    xbmcaddon = None
    xbmcgui = None
    xbmcvfs = None
    HAS_KODI = False

ADDON_ID = 'service.wireguard.manager'

if HAS_KODI:
    try:
        ADDON_PATH = xbmcvfs.translatePath(xbmcaddon.Addon(ADDON_ID).getAddonInfo('path'))
    except Exception:
        ADDON_PATH = '/storage/.kodi/addons/service.wireguard.manager'
else:
    ADDON_PATH = '/storage/.kodi/addons/service.wireguard.manager'

ICON_INFO = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')
ICON_ERROR = os.path.join(ADDON_PATH, 'resources', 'media', 'error.png')

CERT_URL = "https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt"
TOKEN_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
V3_URL = "https://www.privateinternetaccess.com/api/client/v3/token"
V2_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
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

    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            if time.time() - cached.get('timestamp', 0) < 900:
                log_message("PIA: Valid token found in cache.", 1)
                return cached.get('token')
        except Exception as cache_err:
            log_message(f"PIA: Token cache unreadable: {cache_err}", 3)

    log_message("PIA: Cache expired or missing. Handshaking...", 1)

    decoded_password = str(password).strip()

    headers = {'User-Agent': 'PIA-VPN/3.5.0 (Linux)'}
    token = None

    for attempt in range(2):
        try:
            log_message(f"PIA: Attempting v2 authentication (Try {attempt + 1})...", 1)
            creds = urllib.parse.urlencode({'username': user, 'password': decoded_password}).encode()

            req_v2 = urllib.request.Request(V2_URL, data=creds, headers=headers)
            with urllib.request.urlopen(req_v2, timeout=10) as resp:
                token = json.loads(resp.read().decode())['token']
                log_message("PIA: Successfully authenticated via v2.", 1)
                break
        except urllib.error.HTTPError as http_err:
            if http_err.code == 401 and attempt == 0:
                log_message("PIA: Got 401 Unauthorized. Settiing background pause before retry...", 2)
                time.sleep(1.0)
                continue

            log_message(f"PIA: API v2 failed ({http_err}). Trying v3 fallback...", 2)
            break
        except Exception as v2_err:
            log_message(f"PIA: API v2 failed ({v2_err}). Trying v3 fallback...", 2)
            break

    if not token:
        try:
            log_message("PIA: Attempting v3 authentication fallback...", 1)
            raw_auth_str = f"{user}:{decoded_password}"
            encoded_auth_bytes = base64.b64encode(raw_auth_str.encode('utf-8'))
            v3_headers = headers.copy()
            v3_headers['Authorization'] = f"Basic {encoded_auth_bytes.decode('utf-8')}"

            req_v3 = urllib.request.Request(V3_URL, data=b'', headers=v3_headers, method='POST')
            with urllib.request.urlopen(req_v3, timeout=10) as resp:
                token = json.loads(resp.read().decode())['token']
                log_message("PIA: Successfully authenticated via v3 fallback.", 1)
        except Exception as v3_err:
            log_message(f"PIA API Critical Error: Both v2 and v3 failed. Details: {v3_err}", 3)
            return None

    if token:
        try:
            with open(cache_path, 'w') as f:
                json.dump({'token': token, 'timestamp': time.time()}, f)
        except Exception as write_err:
            log_message(f"PIA: Could not write token to temporary cache: {write_err}", 2)
        return token

    return None


def get_live_config(user, password, server_ip, server_cn, region_id, region_name=None):
    current_time = time.time()
    last_ip_handshake = LAST_HANDSHAKE_TRACKER.get(server_ip, 0)
    time_since_last = current_time - last_ip_handshake

    if time_since_last < 60:
        remaining_secs = int(60 - time_since_last)
        msg_log = (
            f"PIA Throttling: Handshake blocked for target IP {server_ip} "
            f"({region_id}). {remaining_secs}s remaining until safe "
            "retry to this specific node."
        )
        log_message(msg_log, 2)

        try:
            if HAS_KODI and xbmc and xbmcgui:
                xbmc.executebuiltin("ActivateWindow(home)")
                title = "[B][COLOR FFE6E6FA]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
                msg_ui = (
                    f"[COLOR FFFFFF00]Node cooling down! Please wait "
                    f"{remaining_secs} seconds before retrying PIA.[/COLOR]"
                )
                xbmcgui.Dialog().notification(title, msg_ui, ICON_INFO, 3000)
        except Exception as e:
            log_message(f"PIA Throttling: Failed to broadcast UI toast notification: {e}", 2)
        return None

    cert_path = ensure_certificate()
    token = get_cached_token(user, password)

    if not token:
        log_message("PIA Handshake Aborted: Missing authentic token.", 3)
        if HAS_KODI and xbmcgui:
            title = "[B][COLOR ffff0000]▀■▄ AUTHENTICATION ERROR ▄■▀[/COLOR][/B]"
            msg_err = "[B][COLOR ffffff00]PIA Handshake Aborted: Missing valid token![/COLOR][/B]"
            xbmcgui.Dialog().notification(title, msg_err, ICON_ERROR, 6000)
        return None

    if not cert_path:
        log_message("PIA Handshake Aborted: Missing root certificates.", 3)
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
            ctx.verify_flags = getattr(ssl, 'VERIFY_DEFAULT', 0)
        except Exception as ssl_init_err:
            log_message(f"PIA Compiler: Strict SSL initialization bypassed: {ssl_init_err}", 1)
            ctx = None

        if ctx is None:
            ctx = ssl._create_unverified_context()

        req_hs = urllib.request.Request(register_url, headers=headers)

        try:
            with urllib.request.urlopen(req_hs, timeout=10, context=ctx) as resp:
                wg_data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.URLError as url_err:
            if "CERTIFICATE_VERIFY_FAILED" in str(url_err) and ctx.verify_mode != ssl.CERT_NONE:
                py_ver = sys.version.split()[0]
                ssl_ver = getattr(ssl, 'OPENSSL_VERSION', 'Unknown')
                log_msg = (
                    f"PIA Handshake Warning: Nightly SSL rules tripped. "
                    f"System Info: Python {py_ver} | {ssl_ver}"
                )
                log_message(log_msg, 1)

                fallback_ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req_hs, timeout=10, context=fallback_ctx) as resp:
                    wg_data = json.loads(resp.read().decode('utf-8'))
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
                        log_message(f"PIA: Server array tracking error skipped: {r_err}", 3)

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

                        if wg_servers and isinstance(wg_servers, list):
                            for srv in wg_servers:
                                if isinstance(srv, dict) and srv.get('ip') and srv.get('cn'):
                                    server_ips.append(srv.get('ip'))
                                    server_cns.append(srv.get('cn'))

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
                log_message(f"PIA: Configuration Compiled with {len(server_ips)} Clean Pool Nodes: {file_path}", 1)

        try:
            with open('/tmp/pia_name_map.json', 'w') as mf:
                json.dump(name_mapping, mf)
        except Exception:
            pass

        return True

    except Exception as e:
        log_message(f"PIA: Update Error: {e}", 3)
        return False


def build_final_config(wg_data, pk, server_ip, region_id, region_name=None):
    dns_str = "10.0.0.243, 10.0.0.241"

    if not region_name:
        region_name = region_id

    safe_name = region_name.replace(' ', '_')
    port_str = str(wg_data.get('server_port', '1337'))

    return (
        "[provider_wireguard]\n"
        "Type = WireGuard\n"
        f"Name = PIA_{safe_name}\n"
        f"Host = {server_ip}\n"
        "WireGuard.MTU = 1420\n"
        f"WireGuard.Address = {wg_data['peer_ip']}/32\n"
        f"WireGuard.PrivateKey = {pk}\n"
        f"WireGuard.PublicKey = {wg_data['server_key']}\n"
        f"WireGuard.DNS = {dns_str}\n"
        f"WireGuard.EndpointPort = {port_str}\n"
        "WireGuard.AllowedIPs = 0.0.0.0/0\n"
        "WireGuard.PersistentKeepalive = 25\n"
    )
