''' ./resources/lib/vpn_utils.py '''
import os
import json
import subprocess
import time
from logger import log_message

try:
    import xbmcaddon
    import xbmcvfs
    HAS_KODI = True
except ImportError:
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


def is_interface_active(interface_name="wg0"):
    try:
        with open("/proc/net/dev", "r") as f:
            content = f.read()
            return f"{interface_name}:" in content
    except Exception:
        return False


def flush_connman_dns_cache():
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():
            if "_" in line and any(x in line for x in ("ethernet_", "wifi_")):
                srv_id = line.strip().split()[-1]
                try:
                    ipv4_info = subprocess.check_output(
                        ["connmanctl", "service", srv_id, "ipv4"],
                        text=True,
                        stderr=subprocess.DEVNULL
                    )
                    if "Method=manual" in ipv4_info.replace(" ", ""):
                        continue
                except subprocess.CalledProcessError:
                    continue
                subprocess.run(["connmanctl", "config", srv_id, "--nameservers"], check=False)
    except Exception:
        pass


def get_active_interface():
    for attempt in range(2):
        try:
            out = subprocess.check_output(
                ["ip", "route", "show", "default"],
                text=True,
                stderr=subprocess.DEVNULL
            )
            interfaces = []
            for line in out.splitlines():
                parts = line.split()
                if "dev" in parts:
                    dev_idx = parts.index("dev") + 1
                    if dev_idx < len(parts):
                        interfaces.append(parts[dev_idx])
            for iface in interfaces:
                if "wg" in iface.lower() or "vpn" in iface.lower():
                    return str(iface)
            if interfaces:
                return str(interfaces[0])
        except Exception as e:
            log_message(f"Service: Interface lookup error: {e}", 3)
            return None
        if attempt == 0:
            time.sleep(0.15)
    return None


def check_interface_status():
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        eth = any(line.startswith("*") and "ethernet" in line for line in out.splitlines())
        wifi = any(line.startswith("*") and "wifi" in line for line in out.splitlines())
        return eth, wifi
    except Exception as e:
        log_message(f"Service: Interface status validation check failure: {e}", 3)
        return False, False


def fetch_vpn_metadata():
    try:
        res = subprocess.check_output(
            ["curl", "-s", "-k", "--connect-timeout", "2.0", "--max-time", "3.0", "https://1.1.1.1/cdn-cgi/trace"],
            text=True
        )
        ip = "Unknown"
        country = "??"
        for line in res.splitlines():
            if line.startswith("ip="):
                ip = line.split("=")[1].strip()
            if line.startswith("loc="):
                country = line.split("=")[1].strip()
        if ip != "Unknown":
            return ip, country
    except Exception:
        pass

    try:
        res = subprocess.check_output(
            ["curl", "-s", "--connect-timeout", "2.0", "--max-time", "5", "https://ipinfo.io"],
            text=True
        )
        data = json.loads(res)
        if "ip" in data:
            return data.get("ip", "Unknown"), data.get("country", "??")
    except Exception:
        pass

    try:
        res = subprocess.check_output(
            ["curl", "-s", "--connect-timeout", "2.0", "--max-time", "3.0", "https://geojs.io"],
            text=True
        )
        data = json.loads(res)
        if "ip" in data:
            return data.get("ip", "Unknown"), data.get("country", "??")
    except Exception as e:
        log_message(f"VPN_Utils: All metadata fallbacks failed: {e}", 2)

    return None, None


def setup_pia_handshake(sid, provider_data, addon_obj, has_kodi):
    from resources.lib.providers.pia_utils import setup_pia_handshake as resolve_pia_handshake
    return resolve_pia_handshake(sid, provider_data, addon_obj, has_kodi)
