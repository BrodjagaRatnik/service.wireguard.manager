''' ./resources/lib/service_control.py '''
import os
import sys
import subprocess
from logger import log_message
from vpn_config import (
    PROVIDER_MAP,
    SYSTEMD_POLL_DELAY,
)

try:
    import xbmc
    import xbmcgui
    import xbmcaddon
    KODI_MODE = True
except ImportError as e:
    KODI_MODE = False
    sys.stderr.write(f"CONTROL CRITICAL: Kodi environment missing or failed initialization: {e}\n")
    sys.stderr.flush()

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

if KODI_MODE:
    _ADDON = xbmcaddon.Addon('service.wireguard.manager')
    ADDON_PATH = _ADDON.getAddonInfo('path')
    MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
    ICON_OK = os.path.join(MEDIA_PATH, 'update_ok.png')
    ICON_ERR = os.path.join(MEDIA_PATH, 'error.png')


def control_service():
    service_name = "vpn-watchdog.service"
    raw_args = "|".join(sys.argv).lower()

    if "restart" in raw_args:
        action = "restart"
    elif "clear" in raw_args:
        action = "clear"
    else:
        action = "status"

    try:
        if action == "restart":
            log_message("Restarting watchdog service...", 0)
            subprocess.run(["systemctl", "restart", service_name], check=True)
            if KODI_MODE:
                title = "[B][COLOR FFBF00FF]≡ [ WATCHDOG ] ≡[/COLOR][/B]"
                msg = "[COLOR FFFFFF00]Service Restarted[/COLOR]"
                xbmcgui.Dialog().notification(title, msg, ICON_OK, 3000)

        elif action == "status":
            if not os.path.exists(f'/storage/.config/system.d/{service_name}'):
                real_status = "Not Installed"
                icon = ICON_ERR if KODI_MODE else None
            else:
                for i in range(1, 6):
                    result = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)
                    real_status = result.stdout.strip()
                    if real_status == "active":
                        break
                    if KODI_MODE:
                        xbmc.sleep(SYSTEMD_POLL_DELAY)

                if KODI_MODE:
                    icon = ICON_OK if real_status == "active" else ICON_ERR
                if real_status == "activating":
                    real_status = "Initializing..."

            log_message(f"Status check: {real_status}", 0)
            if KODI_MODE:
                icon = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')
                title = "[B][COLOR FFBF00FF]≡ [ WATCHDOG ] ≡[/COLOR][/B]"
                msg = f"[COLOR FFFFFF00]Status: [/COLOR][COLOR FFE6E6FA]{real_status}[/COLOR]"
                xbmcgui.Dialog().notification(title, msg, icon, 3000)

        elif action == "clear":
            if KODI_MODE and not xbmcgui.Dialog().yesno("Confirm Reset", "Delete all VPN configurations?"):
                return

            log_message("Clearing configs and disconnecting VPN...", 0)

            p_names = "|".join([p['name'] for p in PROVIDER_MAP.values()])

            disconnect_cmd = (
                f"connmanctl services | grep -E '{p_names}|vpn_wireguard' | "
                "awk '{{print $NF}}' | xargs -I {{}} connmanctl disconnect {{}}"
            )
            subprocess.run(disconnect_cmd, shell=True)
            subprocess.run("rm -f /storage/.config/wireguard/*.config", shell=True)

            files_to_remove = [
                "/tmp/vpn_manager_active.txt",
                "/tmp/vpn_intentional_disconnect.txt",
                "/tmp/vpn_manual_active.txt",
                "/tmp/vpn_reconnect_count.txt"
            ]

            for f in files_to_remove:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as e:
                        log_message(f"Service control cleanup failure for {f}: {e}", 3)

            subprocess.run(["systemctl", "restart", "connman-vpn"])

            if KODI_MODE:
                title = "[B][COLOR FFBF00FF]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
                message = "[COLOR FFFFFF00]All configs cleared[/COLOR]"
                xbmcgui.Dialog().notification(title, message, ICON_OK, 4000)
                xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        log_message(f"Control Error ({action}): {e}", 3)
        if KODI_MODE:
            title = "[B][COLOR FFBF00FF]≡ ERROR ≡[/COLOR][/B]"
            message = f"[COLOR FFFFFF00]{action.capitalize()} failed[/COLOR]"
            xbmcgui.Dialog().notification(title, message, ICON_ERR, 5000)


if __name__ == "__main__":
    control_service()
