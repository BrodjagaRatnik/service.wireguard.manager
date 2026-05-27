''' .resources/lib/utils.py '''
import json
import base64
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from logger import log_message

context = ssl._create_unverified_context()


def fetch_url(url, token=None, user=None, password=None, post_data=None):
    headers = {
        'User-Agent': 'service.wireguard.manager/1.0',
        'Accept': 'application/json'
    }

    clean_password = password
    if password and len(password.strip()) % 4 == 0:
        import string
        pwd_str = password.strip()
        if all(char in string.ascii_letters + string.digits + '+/=' for char in pwd_str):
            try:
                test_decode = base64.b64decode(pwd_str, validate=True).decode('utf-8')
                if all(char in string.printable for char in test_decode):
                    clean_password = test_decode
            except Exception:
                clean_password = password

    if token:
        clean_token = str(token).strip()
        auth_str = f"token:{clean_token}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('ascii')
        headers['Authorization'] = f"Basic {auth_bytes}"
        log_message(f"UTILS DEBUG: Using Token Auth for {url}", 0)

    elif user and password:
        auth_str = f"{user.strip()}:{clean_password.strip()}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('ascii')
        headers['Authorization'] = f"Basic {auth_bytes}"
        log_message(f"UTILS DEBUG: Using Basic Auth for user: {user.strip()}", 0)

    try:
        data_bytes = None

        if "client/v2/token" in url:
            if 'Authorization' in headers:
                del headers['Authorization']
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            payload = post_data if post_data else {'username': user.strip(), 'password': clean_password.strip()}
            data_bytes = urllib.parse.urlencode(payload).encode('utf-8')
            log_message("UTILS DEBUG: Intercepted PIA Token Request - Enforcing Form Data", 0)

        elif post_data is not None:
            if 'username' in post_data and 'password' in post_data:
                data_bytes = urllib.parse.urlencode(post_data).encode('utf-8')
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                log_message("UTILS DEBUG: Converting post_data to Form Data", 0)
            else:
                data_bytes = json.dumps(post_data).encode('utf-8')
                headers['Content-Type'] = 'application/json'
                log_message(f"UTILS DEBUG: Converting post_data to JSON: {post_data}", 0)

        req = urllib.request.Request(url, data=data_bytes, headers=headers)
        log_message(f"UTILS DEBUG: Sending request to: {url}", 0)

        with urllib.request.urlopen(req, timeout=10, context=context) as response:
            response.getcode()
            raw_body = response.read().decode('utf-8').strip()

            if raw_body:
                try:
                    if "\n" in raw_body:
                        raw_body = raw_body.splitlines()[0].strip()

                    return json.loads(raw_body)
                except Exception as e:
                    log_message(f"UTILS JSON ERROR: {e}", 3)
                    return None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        log_message(f"UTILS HTTP ERROR: {e.code} on {url}. Body: {error_body}", 3)
        try:
            return json.loads(error_body)
        except Exception as json_err:
            log_message(f"UTILS HTTP Error body parsing failed: {json_err}", 3)
            return None
    except Exception as e:
        log_message(f"UTILS UNKNOWN ERROR on {url}: {e}", 3)
        return None


def get_ip_from_host(hostname):
    try:
        return socket.gethostbyname(hostname)
    except Exception as e:
        log_message(f"Utils: DNS Lookup failed for {hostname}: {e}", 2)
        return None


def encrypt_setting_to_base64(setting_id):
    import base64
    import xbmcaddon

    addon = xbmcaddon.Addon('service.wireguard.manager')
    raw_value = addon.getSetting(setting_id).strip()

    if not raw_value:
        return ""

    is_base64 = False
    if len(raw_value) % 4 == 0:
        try:
            base64.b64decode(raw_value, validate=True)
            is_base64 = True
        except Exception:
            is_base64 = False

    if not is_base64:
        try:
            encoded_str = base64.b64encode(raw_value.encode('utf-8')).decode('utf-8')
            addon.setSetting(setting_id, encoded_str)
            from logger import log_message
            log_message(f"Utils: Automatically encrypted setting '{setting_id}' to Base64 format.", 1)
            return encoded_str
        except Exception as e:
            from logger import log_message
            log_message(f"Utils: Encryption failed for '{setting_id}': {e}", 3)

    return raw_value
