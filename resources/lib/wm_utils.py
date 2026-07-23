""" ./resources/lib/wm_utils.py """
import kodi_env
import base64
import html
import os
import re
import socket
import subprocess

try:
    import xbmc
    import xbmcgui
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

from logger import log_message
from state_manager import get_file_path

BASE64_PREFIX = "b64:"
B64_REGEX = re.compile(r"^b64:([A-Za-z0-9+/=]+)$")
LAST_RESTART_TIMES = {
    "connman": 0.0,
    "connman-vpn": 0.0
}


def get_addon_dir():
    return kodi_env.ADDON_DIR


ADDON_DIR = get_addon_dir()
CONNMAN_ALERT_SHOWN = False


def trigger_blackout_ui():
    lock_path = get_file_path("blackout")
    if lock_path is None or (os.path.exists(lock_path) is True):
        return
    try:
        with open(lock_path, "w") as f:
            f.write("active")
    except Exception:
        pass
    addon_dir = get_addon_dir()
    icon = os.path.join(addon_dir, "resources", "media", "router-network-error-alert.png")
    sound = os.path.join(addon_dir, "resources", "media", "networkerror.wav")
    title = "[B][COLOR ffff0000]▀■▄ NO NETWORK DETECTED! ▄■▀[/COLOR][/B]"
    msg = "[COLOR fffffff00]Check Wifi|Wire|Modem|Telecom provider.[/COLOR]"
    try:
        xbmc.executebuiltin("PlayerControl(Stop)")
        xbmc.executebuiltin("Action(Stop)")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmcgui.Dialog().notification(title, msg, icon, 14000, False)
        if os.path.exists(sound) is True:
            xbmc.executebuiltin(f"PlayMedia({sound},1)")
        else:
            xbmc.executebuiltin("PlayAction(rightclick)")
    except (ImportError, Exception):
        try:
            subprocess.run(
                ["kodi-send", "--action=PlayerControl(Stop);Action(Stop);Dialog.Close(all,true)"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            escaped_title = title.replace('"', '\\"')
            escaped_msg = msg.replace('"', '\\"')
            notify_action = f'Notification("{escaped_title}","{escaped_msg}",14000,"{icon}")'
            subprocess.run(
                ["kodi-send", f"--action={notify_action}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if os.path.exists(sound) is True:
                subprocess.run(
                    ["kodi-send", f'--action=PlayMedia("{sound}",1)'],
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
    addon = kodi_env.get_addon_instance()
    if not addon:
        return ""
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


def flush_connman_sockets(threshold=400) -> bool:
    global CONNMAN_ALERT_SHOWN
    try:
        res = subprocess.run(["pidof", "connmand"], capture_output=True, text=True)

        if res.returncode != 0 or not res.stdout.strip():
            return False

        pids = sorted([int(x) for x in res.stdout.strip().split()])
        pid = pids[0]
        fd_dir = f"/proc/{pid}/fd"

        if not os.path.exists(fd_dir):
            return False

        try:
            fds = os.listdir(fd_dir)
        except OSError:
            return False

        current_count = len(fds)

        if current_count < threshold:
            return False

        socket_count = 0
        for fd in fds:
            try:
                fd_path = f"{fd_dir}/{fd}"
                link = os.readlink(fd_path)
                if "socket:" in link:
                    socket_count += 1
            except OSError:
                continue

        if current_count >= threshold and socket_count > 0:
            vpn_active = os.path.exists("/sys/class/net/wg0")

            if vpn_active:
                msg = (
                    f"Wm Utils: Connman socket leak detected ({socket_count}/{current_count} FDs). "
                    f"VPN connection is active. Skipping restart to protect tunnel integrity."
                )
                log_message(msg, 1)

                if current_count >= 724 and not CONNMAN_ALERT_SHOWN:
                    try:
                        dialog = xbmcgui.Dialog()
                        dialog.ok(
                            "WireGuard Manager Alert",
                            f"ConnMan socket leak has reached dangerous levels!\n"
                            f"Current Count: {current_count} FDs\n"
                            "Please cycle your VPN connection to safely clear resources."
                        )
                        CONNMAN_ALERT_SHOWN = True
                    except Exception as e:
                        log_message(f"Wm Utils: Failed to render Kodi OK dialog: {e}", 2)

                return False

            CONNMAN_ALERT_SHOWN = False
            msg = (
                f"Wm Utils: Connman socket leak detected ({socket_count}/{current_count} FDs). "
                f"VPN connection is inactive. Executing safe background network reclamation..."
            )
            log_message(msg, 1)

            cmd = "systemctl restart connman && ifconfig eth0 up 2>/dev/null; ifconfig wlan0 up 2>/dev/null"
            subprocess.Popen(
                ["nohup", "sh", "-c", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return True

        return False
    except (IndexError, ValueError, OSError) as e:
        log_message(f"Wm Utils: Internal exception during connmand socket monitoring: {e}", 3)
        return False

    finally:
        kodi_env.clear_script_globals()
