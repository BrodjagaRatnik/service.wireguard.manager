''' .resources/lib/utils.py '''
import json
import base64
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import html
import re
import xbmcaddon
from logger import log_message

BASE64_PREFIX = "b64:"
B64_REGEX = re.compile(r"^b64:([A-Za-z0-9+/=]+)$")
context = ssl._create_unverified_context()


def fetch_url(url, token=None, user=None, password=None, post_data=None):
    import ssl

    headers = {
        'User-Agent': 'service.wireguard.manager/1.0',
        'Accept': 'application/json'
    }

    clean_password = password

    if token:
        clean_token = str(token).strip()
        auth_str = f"token:{clean_token}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('ascii')
        headers['Authorization'] = f"Basic {auth_bytes}"
        log_message(f"Wm Utils: Using Token Auth for {url}", 0)

    elif user and clean_password:
        auth_str = f"{user.strip()}:{clean_password.strip()}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('ascii')
        headers['Authorization'] = f"Basic {auth_bytes}"
        log_message(f"Wm Utils: Using Basic Auth for user: {user.strip()}", 1)

    try:
        data_bytes = None

        if "client/v2/token" in url:
            if 'Authorization' in headers:
                del headers['Authorization']
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            payload = post_data if post_data else {'username': user.strip(), 'password': clean_password.strip()}
            data_bytes = urllib.parse.urlencode(payload).encode('utf-8')
            log_message("Wm Utils: Intercepted PIA Token Request - Enforcing Form Data", 1)

        elif "client/v3/token" in url:
            data_bytes = b''
            headers['Content-Type'] = 'application/json'
            log_message("Wm Utils: Intercepted PIA v3 Token Request - Enforcing Empty Body", 1)

        elif post_data is not None:
            if isinstance(post_data, dict) and 'username' in post_data and 'password' in post_data:
                data_bytes = urllib.parse.urlencode(post_data).encode('utf-8')
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                log_message("Wm Utils: Converting post_data to Form Data", 1)
            else:
                data_bytes = json.dumps(post_data).encode('utf-8')
                headers['Content-Type'] = 'application/json'
                log_message("Wm Utils: Converting post_data to JSON", 1)
        else:
            data_bytes = None

        req = urllib.request.Request(url, data=data_bytes, headers=headers)
        log_message(f"Wm Utils: Sending request to: {url}", 0)

        try:
            req_ctx = ssl.create_default_context()
        except Exception:
            req_ctx = ssl._create_unverified_context()

        with urllib.request.urlopen(req, timeout=10, context=req_ctx) as response:
            raw_body = response.read().decode('utf-8').strip()

            if raw_body:
                try:
                    return json.loads(raw_body)
                except Exception:
                    log_message("Wm Utils: Whole body JSON parse failed, trying line-by-line fallback...", 2)

                for line in raw_body.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        return json.loads(line)
                    except Exception:
                        continue

                log_message("Wm Utils: JSON ERROR: No valid JSON object could be extracted from payload.", 3)
                return None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        log_message(f"Wm Utils: HTTP ERROR: {e.code} on {url}. Body: {error_body}", 3)
        try:
            return json.loads(error_body)
        except Exception as json_err:
            log_message(f"Wm Utils: HTTP Error body parsing failed: {json_err}", 3)
            return None
    except Exception as e:
        log_message(f"Wm Utils: UNKNOWN ERROR on {url}: {e}", 3)
        return None


def get_ip_from_host(hostname):
    try:
        return socket.gethostbyname(hostname)
    except Exception as e:
        log_message(f"Wm Utils: DNS Lookup failed for {hostname}: {e}", 2)
        return None


def safe_encrypt_password(raw_password: str) -> str:
    """Cleans Kodi XML escaping and encrypts safely with a prefix."""
    if not raw_password:
        return ""
    normalized = html.unescape(raw_password)
    bytes_payload = normalized.encode("utf-8")
    b64_string = base64.b64encode(bytes_payload).decode("utf-8")
    return f"{BASE64_PREFIX}{b64_string}"


def encrypt_setting_to_base64(setting_id: str) -> str:
    """Wrapper for Kodi settings change events."""
    addon = xbmcaddon.Addon('service.wireguard.manager')
    raw_value = addon.getSetting(setting_id).strip()

    if not raw_value or raw_value.startswith(BASE64_PREFIX):
        return raw_value

    try:
        final_payload = safe_encrypt_password(raw_value)
        addon.setSetting(setting_id, final_payload)

        msg = f"Wm Utils: Automatically encrypted setting '{setting_id}' to Base64 format."
        log_message(msg, 1)
        return final_payload
    except Exception as e:
        log_message(f"Wm Utils: Encryption failed for '{setting_id}': {e}", 3)
        return raw_value


def safe_decrypt_password(stored_password: str) -> str:
    """Validates and extracts raw characters for API handshakes."""
    if not stored_password:
        return ""

    match = B64_REGEX.match(stored_password)
    if not match:
        return html.unescape(stored_password)

    try:
        b64_payload = match.group(1)
        missing_padding = len(b64_payload) % 4
        if missing_padding:
            b64_payload += "=" * (4 - missing_padding)

        decoded_bytes = base64.b64decode(b64_payload)
        raw_string = decoded_bytes.decode("utf-8")
        return html.unescape(raw_string)
    except Exception:
        return html.unescape(stored_password)
