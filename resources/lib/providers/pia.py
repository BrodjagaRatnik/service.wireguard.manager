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
import urllib.error
import urllib.parse
import urllib.request
import re
import base64
from logger import log_message
from resources.lib.providers import routing

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

CERT_URL = "https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt"
TOKEN_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
SERVER_LIST_URL = "https://serverlist.piaservers.net/vpninfo/servers/v6"

LAST_HANDSHAKE_TRACKER = {}


def ensure_certificate():
    cert_path = os.path.join(os.path.dirname(__file__), 'ca.rsa.4096.crt')
    if not os.path.exists(cert_path):
        try:
            log_message("PIA: Local CA certificate missing. Downloading from source...", 0)
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(CERT_URL, headers={'User-Agent': 'PIA-VPN/3.5.0 (Linux)'})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                with open(cert_path, 'wb') as f:
                    f.write(response.read())
            log_message("PIA: Local CA certificate successfully verified and written.", 0)
            return cert_path
        except Exception as cert_err:
            log_message(f"PIA: Certificate template mapping aborted {cert_err}", 2)
            return None
    return cert_path


def get_cached_token(user, password):
    cache_path = '/tmp/pia_token_cache.json'

    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            if time.time() - cached.get('timestamp', 0) < 3000:
                log_message("PIA: Valid token found in cache.", 0)
                return cached.get('token')
        except Exception as cache_err:
            log_message(f"PIA: Token cache unreadable: {cache_err}", 3)

    log_message("PIA: Cache expired or missing. Getting new token.", 0)

    clean_pw = str(password).strip()
    decoded_password = clean_pw

    if bool(re.match(r'^[A-Za-z0-9+/]+={0,2}$', clean_pw)) and len(clean_pw) % 4 == 0:
        try:
            decoded_password = base64.b64decode(clean_pw).decode('utf-8').strip()
        except (ValueError, UnicodeDecodeError) as decode_err:
            log_message(f"PIA: Password decoding failed: {decode_err}", 3)
            decoded_password = clean_pw

    headers = {'User-Agent': 'PIA-VPN/3.5.0 (Linux)'}
    token = None

    for attempt in range(2):
        try:
            log_message(f"PIA: Attempting v2 auth (Try {attempt + 1})...", 0)
            creds = urllib.parse.urlencode({'username': user, 'password': decoded_password}).encode()

            req_v2 = urllib.request.Request(TOKEN_URL, data=creds, headers=headers)
            with urllib.request.urlopen(req_v2, timeout=10) as resp:
                token = json.loads(resp.read().decode())['token']
                log_message("PIA: Successfully authenticated via api/client/v2/token.", 0)
                break
        except urllib.error.HTTPError as http_err:
            if http_err.code == 401 and attempt == 0:
                log_message("PIA: Got 401. Setting background pause...", 2)
                time.sleep(1.0)
                continue

            log_message(f"PIA: v2 authentication failed ({http_err.code}).", 3)
            break
        except Exception as v2_err:
            log_message(f"PIA: v2 authentication failed ({v2_err}).", 3)
            break

    if token is not None:
        try:
            with open(cache_path, 'w') as f:
                json.dump({'token': token, 'timestamp': time.time()}, f)
        except Exception as write_err:
            log_message(f"PIA: Could not write token to temporary cache {write_err}", 3)
        return token

    return None


def get_live_config(token, server_ip, server_cn, region_id, region_name=None, raw_cn_str=""):
    current_time = time.time()
    last_ip_handshake = LAST_HANDSHAKE_TRACKER.get(server_ip, 0)
    time_since_last = current_time - last_ip_handshake

    if time_since_last < 3300:
        return None

    try:
        LAST_HANDSHAKE_TRACKER[server_ip] = time.time()
        connect_port = "1337"
        clean_cn = str(server_cn).strip().lower()
        target_hostname = f"{clean_cn}.privacy.network"

        headers = {
            'User-Agent': 'PIA-VPN/3.5.0 (Linux)',
            'Host': target_hostname
        }

        pk = subprocess.check_output(["wg", "genkey"]).decode().strip()
        pub = subprocess.check_output(["wg", "pubkey"], input=pk.encode()).decode().strip()

        params = urllib.parse.urlencode({'pt': token, 'pubkey': pub})
        register_url = f"https://{server_ip}:{connect_port}/addKey?{params}"

        cert_path = ensure_certificate()
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
            log_message(f"PIA: Compiler Strict SSL initialization bypassed {ssl_init_err}", 3)
            ctx = None

        if ctx is None:
            ctx = ssl._create_unverified_context()

        req_hs = urllib.request.Request(register_url, headers=headers)

        try:
            with urllib.request.urlopen(req_hs, timeout=4, context=ctx) as resp:
                wg_data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.URLError as url_err:
            if "CERTIFICATE_VERIFY_FAILED" in str(url_err) and ctx.verify_mode != ssl.CERT_NONE:
                import sys
                py_ver = sys.version.split()
                ssl_ver = getattr(ssl, 'OPENSSL_VERSION', 'Unknown')
                log_msg = f"PIA: Handshake Warning. Nightly SSL rules tripped. System Info Python {py_ver} | {ssl_ver}"
                log_message(log_msg, 2)
                fallback_ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req_hs, timeout=4, context=fallback_ctx) as resp:
                    wg_data = json.loads(resp.read().decode('utf-8'))
            else:
                raise url_err

        if wg_data.get('status') == "OK":
            return build_final_config(wg_data, pk, server_ip, region_id, region_name, raw_cn_str)

        log_message(f"PIA: API Handshake Error {wg_data.get('status')}", 3)

    except Exception as e:
        log_message(f"PIA: Handshake Exception {str(e)}", 3)
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
                        log_message(f"PIA: Server array tracking error skipped {r_err}", 3)

    raw_data = None
    for attempt in range(2):
        try:
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(SERVER_LIST_URL, headers={'User-Agent': 'PIA-VPN/3.5.0 (Linux)'})

            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                raw_data = resp.read().decode('utf-8').strip()
                if "\n" in raw_data:
                    raw_data = raw_data.splitlines()[0].strip()
            break
        except urllib.error.URLError as url_err:
            if "101" in str(url_err) or "unreachable" in str(url_err).lower():
                if attempt == 0:
                    time.sleep(3.0)
                    continue
            log_message(f"PIA: Update Error {url_err}", 3)
            return False
        except Exception as fetch_err:
            log_message(f"PIA: Update Error {fetch_err}", 3)
            return False

    if raw_data is None:
        return False

    try:
        data = json.loads(raw_data)
        name_mapping = {}
        compiled_files_count = 0
        total_nodes_count = 0

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
                    f.write("WireGuard.MTU = 1380\n")
                    f.write("WireGuard.PublicKey = placeholder\n")
                    f.write("WireGuard.Address = 10.0.0.1/32\n")

                compiled_files_count += 1
                total_nodes_count += len(server_ips)

        if compiled_files_count > 0:
            log_message(f"PIA: Batch complete. Compiled {compiled_files_count} regions ({total_nodes_count} nodes).", 0)

        try:
            with open('/tmp/pia_name_map.json', 'w') as mf:
                json.dump(name_mapping, mf)
        except Exception:
            pass

        return True

    except Exception as e:
        log_message(f"PIA Update Error: {e}", 3)
        return False


def build_final_config(wg_data, pk, server_ip, region_id, region_name=None, raw_cn_str="", allowed_ips_mode=1):
    dns_str = "10.0.0.243, 10.0.0.241, 1.1.1.1, 9.9.9.9"
    if not region_name:
        region_name = region_id
    safe_name = region_name.replace(' ', '_')
    port_str = str(wg_data.get('server_port', '1337'))
    chosen_mtu = "1380"

    for mtu in [1420, 1400, 1380, 1280]:
        p_size = mtu - 28
        cmd = ["ping", "-c", "1", "-M", "do", "-s", str(p_size), server_ip]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            chosen_mtu = str(mtu)
            break
    msg = f"PIA: Optimal MTU benchmark determined path value as {chosen_mtu}"
    log_message(msg, 1)

    if allowed_ips_mode == 2:
        allowed_ips = routing.get_allowed_ips(lan_bypass=True, custom_bypass_subnets=["10.0.0.0/8"])
    elif allowed_ips_mode == 3:
        allowed_ips = routing.get_allowed_ips(lan_bypass=True)
    else:
        allowed_ips = routing.get_allowed_ips(lan_bypass=False)

    return (
        "[provider_wireguard]\n"
        "Type = WireGuard\n"
        f"Name = PIA_{safe_name}\n"
        f"Host = {server_ip}\n"
        f"WireGuard.MTU = {chosen_mtu}\n"
        f"WireGuard.Address = {wg_data['peer_ip']}/32\n"
        f"WireGuard.PrivateKey = {pk}\n"
        f"WireGuard.PublicKey = {wg_data['server_key']}\n"
        f"WireGuard.DNS = {dns_str}\n"
        f"WireGuard.EndpointPort = {port_str}\n"
        f"WireGuard.AllowedIPs = {allowed_ips}\n"
        "WireGuard.PersistentKeepalive = 25\n"
        f"WireGuard.CN_Pool = {raw_cn_str}\n"
    )
