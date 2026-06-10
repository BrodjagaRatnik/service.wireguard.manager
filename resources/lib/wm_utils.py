""" ./resources/lib/wm_utils.py """
import base64
import html
import os
import re
import socket
import subprocess

try:
    import xbmc
    import xbmcaddon
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

from logger import log_message

BASE64_PREFIX = "b64:"
B64_REGEX = re.compile(r"^b64:([A-Za-z0-9+/=]+)$")
ADDON_DIR = "/storage/.kodi/addons/service.wireguard.manager"


def trigger_blackout_ui():
    if os.path.exists("/tmp/vpn_blackout_active.lock"):
        return
    try:
        with open("/tmp/vpn_blackout_active.lock", "w") as f:
            f.write("active")
    except Exception:
        pass
    icon = os.path.join(ADDON_DIR, "resources", "media", "router-network-error-alert.png")
    sound = os.path.join(ADDON_DIR, "resources", "media", "networkerror.wav")
    title = "[B][COLOR ffff0000]▀■▄ NO NETWORK DETECTED! ▄■▀[/COLOR][/B]"
    msg = "[COLOR fffffff00]Check Wifi|Wire|Modem|Telecom provider.[/COLOR]"
    try:
        xbmc.executebuiltin("PlayerControl(Stop)")
        xbmc.executebuiltin("Action(Stop)")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin(f'Notification("{title}", "{msg}", 14000, "{icon}")')
        if os.path.exists(sound):
            subprocess.run(
                ["kodi-send", f'--action=PlayMedia("{sound}", 1)'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            xbmc.executebuiltin("PlayAction(rightclick)")
    except (ImportError, Exception):
        try:
            subprocess.run(
                ["kodi-send", "--action=PlayerControl(Stop);Action(Stop);Dialog.Close(all,true)"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["kodi-send", f'--action=Notification("{title}", "{msg}", 14000, "{icon}")'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if os.path.exists(sound):
                subprocess.run(
                    ["kodi-send", f'--action=PlayMedia("{sound}", 1)'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        except Exception:
            pass
    log_message("Wm Utils: NO INTERNET CONNECTION DETECTED! Check Wifi|Wire|Modem|Telecom provider.", 3)


def get_ip_from_host(hostname):
    try:
        return socket.gethostbyname(hostname)
    except Exception as e:
        log_message(f"Wm Utils: DNS Lookup failed for {hostname}: {e}", 2)
        return None


def safe_encrypt_password(raw_password: str) -> str:
    if not raw_password:
        return ""
    normalized = html.unescape(raw_password)
    bytes_payload = normalized.encode("utf-8")
    b64_string = base64.b64encode(bytes_payload).decode("utf-8")
    return f"{BASE64_PREFIX}{b64_string}"


def encrypt_setting_to_base64(setting_id: str) -> str:
    if not HAS_KODI:
        return ""
    addon = xbmcaddon.Addon('service.wireguard.manager')
    raw_value = addon.getSetting(setting_id).strip()
    if not raw_value or raw_value.startswith(BASE64_PREFIX):
        return raw_value
    try:
        final_payload = safe_encrypt_password(raw_value)
        addon.setSetting(setting_id, final_payload)
        msg = f"Wm Utils: Automatically encrypted setting '{setting_id}' to Base64 format."
        log_message(msg, 0)
        return final_payload
    except Exception as e:
        log_message(f"Wm Utils: Encryption failed for '{setting_id}': {e}", 3)
        return raw_value


def safe_decrypt_password(stored_password: str) -> str:
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
