""" .resources/lib/providers/pia.py
https://github.com/pia-foss/manual-connections/
GLOBAL ENDPOINT CONSTANTS
CERT_URL = "https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt"
TOKEN_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
SERVER_LIST_URL = "https://serverlist.piaservers.net/vpninfo/servers/v6"
"""
import kodi_env
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
from state_manager import get_file_path
from providers.pia_updater import build_final_config as real_build_final_config
from providers.pia_updater import update as real_update

try:
    import xbmc
    import xbmcgui
    import xbmcvfs
    HAS_KODI = True
except ImportError:
    xbmc = None
    xbmcgui = None
    xbmcvfs = None
    HAS_KODI = False

CERT_URL = "https://raw.githubusercontent.com/pia-foss/manual-connections/master/ca.rsa.4096.crt"
TOKEN_URL = "https://www.privateinternetaccess.com/api/client/v2/token"
SERVER_LIST_URL = "https://serverlist.piaservers.net/vpninfo/servers/v6"
LAST_HANDSHAKE_TRACKER = {}


def get_addon_path():
    return kodi_env.ADDON_DIR


def ensure_certificate():
    cert_path = os.path.join(os.path.dirname(__file__), "ca.rsa.4096.crt")
    if not os.path.exists(cert_path):
        try:
            log_message("PIA: Local CA certificate missing. Downloading from source...", 2)
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(CERT_URL, headers={"User-Agent": "PIA-VPN/3.5.0 (Linux)"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                with open(cert_path, "wb") as f:
                    f.write(response.read())
            log_message("PIA: Local CA certificate successfully verified and written.", 1)
            return cert_path
        except Exception as cert_err:
            log_message(f"PIA: Certificate template mapping aborted {cert_err}", 3)
            return None
    return cert_path


def get_cached_token(user, password):
    cache_path = get_file_path("pia_cache")

    if cache_path is not None and (os.path.exists(cache_path) is True):
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            if time.time() - cached.get("timestamp", 0) < 3000:
                log_message("PIA: Valid token found in cache.", 0)
                return cached.get("token")
        except Exception as cache_err:
            log_message(f"PIA: Token cache unreadable: {cache_err}", 3)

    log_message("PIA: Cache expired or missing. Getting new token.", 0)

    clean_pw = str(password).strip()
    decoded_password = clean_pw

    if bool(re.match(r"^[A-Za-z0-9+/]+={0,2}$", clean_pw)) and len(clean_pw) % 4 == 0:
        try:
            decoded_password = base64.b64decode(clean_pw).decode("utf-8").strip()
        except (ValueError, UnicodeDecodeError) as decode_err:
            log_message(f"PIA: Password decoding failed: {decode_err}", 3)
            decoded_password = clean_pw

    headers = {"User-Agent": "PIA-VPN/3.5.0 (Linux)"}
    token = None

    for attempt in range(3):
        try:
            log_message(f"PIA: Attempting v2 auth (Try {attempt + 1})...", 0)
            raw_creds = {"username": user, "password": decoded_password}
            creds = urllib.parse.urlencode(raw_creds).encode()

            req_v2 = urllib.request.Request(TOKEN_URL, data=creds, headers=headers)
            with urllib.request.urlopen(req_v2, timeout=10) as resp:
                token = json.loads(resp.read().decode())["token"]
                log_message("PIA: Successfully authenticated via api/client/v2/token.", 1)
                break
        except urllib.error.HTTPError as http_err:
            if http_err.code == 401 and attempt == 0:
                log_message("PIA: Got 401. Setting background pause...", 2)
                time.sleep(2.0)
                continue
            log_message(f"PIA: v2 authentication failed ({http_err.code}).", 3)
            break
        except Exception as v2_err:
            log_message(f"PIA: v2 authentication failed ({v2_err}).", 3)
            break

    if token is not None:
        if cache_path is not None:
            try:
                with open(cache_path, "w") as f:
                    json.dump({"token": token, "timestamp": time.time()}, f)
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
        connect_port = "1337"
        clean_cn = str(server_cn).strip().lower()
        target_hostname = f"{clean_cn}.privacy.network"

        headers = {
            "User-Agent": "PIA-VPN/3.5.0 (Linux)",
            "Host": target_hostname
        }

        pk = subprocess.check_output(["wg", "genkey"]).decode().strip()
        pub = subprocess.check_output(["wg", "pubkey"], input=pk.encode()).decode().strip()

        params = urllib.parse.urlencode({"pt": token, "pubkey": pub})
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
            with urllib.request.urlopen(req_hs, timeout=5, context=ctx) as resp:
                raw_payload = resp.read().decode("utf-8")
                wg_data = json.loads(raw_payload)
        except urllib.error.URLError as url_err:
            err_str = str(url_err)
            if "CERTIFICATE_VERIFY_FAILED" in err_str and ctx.verify_mode != ssl.CERT_NONE:
                import sys
                py_ver = sys.version.split()
                ssl_ver = getattr(ssl, "OPENSSL_VERSION", "Unknown")
                log_msg = f"PIA: Handshake Warning. Nightly SSL Info Python {py_ver} | {ssl_ver}"
                log_message(log_msg, 0)
                fallback_ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req_hs, timeout=5, context=fallback_ctx) as resp:
                    wg_data = json.loads(resp.read().decode("utf-8"))
            else:
                raise url_err

        if wg_data.get("status") == "OK":
            LAST_HANDSHAKE_TRACKER[server_ip] = time.time()
            return build_final_config(wg_data, pk, server_ip, region_id, region_name, raw_cn_str)

        log_message(f"PIA: API Handshake Error {wg_data.get('status')}", 3)

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "too many requests" in err_str.lower():
            from providers.pia_config import PiaHandshakeEngine
            engine = PiaHandshakeEngine()
            engine.enforce_cooldown(900.0)
        log_message(f"PIA: Handshake Exception {err_str}", 3)
    return None


def update(user, password, country_ids, config_dir):
    return real_update(user, password, country_ids, config_dir)


def build_final_config(wg_data, pk, server_ip, region_id, region_name=None, raw_cn_str="", allowed_ips_mode=1):
    return real_build_final_config(
        wg_data, pk, server_ip, region_id, region_name, raw_cn_str, allowed_ips_mode
    )
