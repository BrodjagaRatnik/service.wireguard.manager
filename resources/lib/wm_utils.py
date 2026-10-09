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
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

from logger import log_message
from state_manager import get_file_path
import dialog

BASE64_PREFIX = "b64:"
B64_REGEX = re.compile(r"^b64:([A-Za-z0-9+/=]+)$")
CONNMAN_ALERT_SHOWN = False


def get_addon_dir():
    return kodi_env.ADDON_DIR


ADDON_DIR = get_addon_dir()


def _build_blackout_assets():
    addon_dir = get_addon_dir()
    icon = os.path.join(addon_dir, "resources", "media", "router-network-error-alert.png")
    sound = os.path.join(addon_dir, "resources", "media", "networkerror.wav")
    title = "[B][COLOR ffff0000]▀■▄ NO NETWORK DETECTED! ▄■▀[/COLOR][/B]"
    msg = "[COLOR fffffff00]Check Wifi|Wire|Modem|Telecom provider.[/COLOR]"
    return title, msg, icon, sound


def show_blackout_ui_in_kodi():
    if not HAS_KODI:
        log_message("Wm Utils: show_blackout_ui_in_kodi() called outside Kodi runtime, aborting.", 3)
        return

    title, msg, icon, sound = _build_blackout_assets()
    try:
        xbmc.executebuiltin("PlayerControl(Stop)")
        xbmc.executebuiltin("Action(Stop)")
        try:
            player = xbmc.Player()
            if player.isPlaying():
                player.stop()
                log_message("Wm Utils: Blackout forced active playback stop via Player API.", 0)
        except Exception:
            pass
        xbmc.executebuiltin("Dialog.Close(all,true)")
        log_message("Wm Utils: Blackout stop and close actions dispatched.", 0)
        dialog.notify_custom(title, msg, "router-network-error-alert.png", 14000, sound=False)
        log_message("Wm Utils: Blackout notification dispatched.", 0)
        if os.path.exists(sound) is True:
            try:
                xbmc.Player().play(sound)
                log_message("Wm Utils: Blackout alert sound started via player preemption.", 0)
            except Exception:
                xbmc.executebuiltin(f"PlayMedia({sound},1)")
        else:
            xbmc.executebuiltin("PlayAction(rightclick)")
    except Exception as blackout_fault:
        log_message(f"Wm Utils: Blackout UI execution failed in Kodi context: {blackout_fault}", 3)


def trigger_blackout_ui():
    lock_path = get_file_path("blackout")
    if lock_path is None or (os.path.exists(lock_path) is True):
        return

    log_message("Wm Utils: NO INTERNET CONNECTION DETECTED! Check Wifi|Wire|Modem|Telecom provider.", 3)

    try:
        with open(lock_path, "w") as f:
            f.write("active")
    except Exception:
        pass

    real_kodi = getattr(kodi_env, "HAS_KODI_IMPORTS", False) is True

    if real_kodi is True:
        try:
            show_blackout_ui_in_kodi()
            return
        except Exception:
            pass

    try:
        subprocess.run(
            ["kodi-send", "--action=RunScript(service.wireguard.manager,blackout)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        log_message("Wm Utils: Blackout UI dispatch to Kodi runtime failed.", 3)


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


def flush_connman_sockets() -> bool:
    global CONNMAN_ALERT_SHOWN
    try:
        res = subprocess.run(["pidof", "connmand"], capture_output=True, text=True)
        if res.returncode != 0 or not res.stdout.strip():
            return False

        pids = sorted([int(x) for x in res.stdout.strip().split()])
        pid = pids[0]
        fd_dir = f"/proc/{pid}/fd"
        limits_file = f"/proc/{pid}/limits"

        if not os.path.exists(fd_dir) or not os.path.exists(limits_file):
            return False

        max_files = 512
        try:
            with open(limits_file, "r") as f:
                for line in f:
                    if "Max open files" in line:
                        digits = re.findall(r'\d+', line)
                        if digits:
                            max_files = int(digits[0])
                        break
        except Exception as e:
            log_message(f"Wm Utils: Error parsing proc limits: {e}", 2)

        threshold_restart = int(max_files * 0.80)
        threshold_alert = int(max_files * 0.90)

        try:
            fds = os.listdir(fd_dir)
        except OSError:
            return False

        current_count = len(fds)
        if current_count < threshold_restart:
            CONNMAN_ALERT_SHOWN = False
            return False

        socket_count = 0
        for fd in fds:
            try:
                link = os.readlink(f"{fd_dir}/{fd}")
                if "socket" in link.lower() or "anon_inode" in link.lower():
                    socket_count += 1
            except OSError:
                continue

        if current_count >= threshold_restart and socket_count > 0:
            vpn_active = os.path.exists("/sys/class/net/wg0")

            if vpn_active:
                if current_count >= threshold_alert:
                    if not CONNMAN_ALERT_SHOWN:
                        dialog.show_ok(
                            "WireGuard Manager Alert",
                            f"ConnMan socket leak has reached dangerous levels!\n"
                            f"Current Count: {current_count} / {max_files} FDs (>=90%)\n"
                            "Please cycle your VPN connection to safely clear resources."
                        )
                        CONNMAN_ALERT_SHOWN = True
                else:
                    msg = (
                        f"Wm Utils: Connman socket leak detected ({socket_count}/{current_count} FDs). "
                        f"Limit is {max_files}. VPN is active. Skipping restart."
                    )
                    log_message(msg, 2)

                return False

            CONNMAN_ALERT_SHOWN = False
            msg = (
                f"Wm Utils: Connman leak at {current_count}/{max_files} FDs (>=80%). "
                f"VPN is inactive. Executing safe background network reclamation..."
            )
            log_message(msg, 1)
            cmd = "systemctl restart connman && sleep 3 && ip link set eth0 up 2>/dev/null; ip link set wlan0 up 2>/dev/null"
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
        try:
            if current_count >= threshold_restart:
                kodi_env.clear_script_globals()
        except Exception:
            pass
