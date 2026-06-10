''' ./resources/lib/providers/nord_utils.py '''
import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xbmcaddon
import xbmcvfs
from logger import log_message

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
_LIB = xbmcvfs.translatePath(os.path.join(_ADDON.getAddonInfo('path'), 'resources', 'lib'))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def resolve_host_fallback(hostname):
    import socket
    try:
        res = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if res and len(res) > 0:
            return res[0][4][0]
    except Exception:
        pass
    return None


def fetch_nord_url(url, token=None, post_data=None):
    headers = {
        'User-Agent': 'service.wireguard.manager/1.0',
        'Accept': 'application/json'
    }

    if token:
        clean_token = str(token).strip()
        auth_str = f"token:{clean_token}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('ascii')
        headers['Authorization'] = f"Basic {auth_bytes}"
        log_message(f"Nord Utils: Using Token Auth for {url}", 0)

    parsed_url = urllib.parse.urlparse(url)
    target_host = parsed_url.netloc
    resolved_ip = resolve_host_fallback(target_host)

    if resolved_ip:
        headers['Host'] = target_host
        url = url.replace(target_host, resolved_ip)

    try:
        data_bytes = None
        if post_data is not None:
            data_bytes = json.dumps(post_data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
            log_message("Nord Utils: Converting post_data to JSON", 0)

        req = urllib.request.Request(url, data=data_bytes, headers=headers)
        log_message(f"Nord Utils: Sending request to {url}", 0)

        try:
            req_ctx = ssl.create_default_context()
            req_ctx.check_hostname = False
            req_ctx.verify_mode = ssl.CERT_NONE
        except Exception:
            req_ctx = ssl._create_unverified_context()

        t_start = time.perf_counter()

        with urllib.request.urlopen(req, timeout=4, context=req_ctx) as response:
            raw_body = response.read().decode('utf-8').strip()

            t_elapsed = (time.perf_counter() - t_start) * 1000.0
            log_message(f"Nord Utils: Network execution took {t_elapsed:.2f}ms", 0)

            if raw_body:
                return json.loads(raw_body)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        log_message(f"Nord Utils: HTTP ERROR {e.code} on {url}. Body: {error_body}", 3)
        try:
            return json.loads(error_body)
        except Exception:
            return None
    except Exception as e:
        log_message(f"Nord Utils: UNKNOWN ERROR on {url}: {e}", 3)
        return None
