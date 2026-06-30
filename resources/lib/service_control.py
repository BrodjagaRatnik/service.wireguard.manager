""" ./resources/lib/service_control.py """
import kodi_env
import os
import subprocess
import sys
from logger import log_message
from vpn_config import PROVIDER_MAP, SYSTEMD_POLL_DELAY
from state_manager import get_file_path

try:
    import xbmc
    import xbmcgui
    HAS_KODI_UI = True
except ImportError:
    HAS_KODI_UI = False


def control_service():
    service_name = "vpn-watchdog.service"
    raw_args = "|".join(sys.argv).lower()

    addon_path = kodi_env.ADDON_DIR
    media_path = os.path.join(addon_path, "resources", "media")
    icon_ok = os.path.join(media_path, "update_ok.png")
    icon_err = os.path.join(media_path, "error.png")

    if "restart" in raw_args:
        action = "restart"
    elif "clear" in raw_args:
        action = "clear"
    else:
        action = "status"

    try:
        if action == "restart":
            log_message("Service Control: Restarting watchdog service...", 0)
            subprocess.run(["systemctl", "restart", service_name], check=True)
            if kodi_env.HAS_KODI_IMPORTS and HAS_KODI_UI:
                title = "[B][COLOR FFBF00FF]≡ [ WATCHDOG ] ≡[/COLOR][/B]"
                msg = "[COLOR FFFFFF00]Service Restarted[/COLOR]"
                xbmcgui.Dialog().notification(title, msg, icon_ok, 3000)

        elif action == "status":
            if not os.path.exists(f"/storage/.config/system.d/{service_name}"):
                real_status = "Not Installed"
            else:
                real_status = "unknown"
                for i in range(1, 6):
                    result = subprocess.run(
                        ["systemctl", "is-active", service_name],
                        capture_output=True,
                        text=True
                    )
                    real_status = result.stdout.strip()
                    if real_status == "active":
                        break
                    if kodi_env.HAS_KODI_IMPORTS and HAS_KODI_UI:
                        xbmc.sleep(SYSTEMD_POLL_DELAY)

                if real_status == "activating":
                    real_status = "Initializing..."

            log_message(f"Service Control: Watchdog service {real_status}", 0)
            if kodi_env.HAS_KODI_IMPORTS and HAS_KODI_UI:
                icon_path = os.path.join(addon_path, "resources", "media", "icon.png")
                title = "[B][COLOR FFBF00FF]≡ [ WATCHDOG ] ≡[/COLOR][/B]"
                msg = f"[COLOR FFFFFF00]Status: [/COLOR][COLOR FFE6E6FA]{real_status}[/COLOR]"
                xbmcgui.Dialog().notification(title, msg, icon_path, 3000)

        elif action == "clear":
            if kodi_env.HAS_KODI_IMPORTS and HAS_KODI_UI:
                confirmed = xbmcgui.Dialog().yesno("Confirm Reset", "Delete all VPN configurations?")
                if not confirmed:
                    kodi_env.clear_script_globals()
                    return

            log_message("Service Control: Clearing configs and disconnecting VPN...", 0)

            p_names = "|".join([p["name"] for p in PROVIDER_MAP.values()])

            disconnect_cmd = (
                f"connmanctl services | grep -E '{p_names}|vpn_wireguard' | "
                "awk '{{print $NF}}' | xargs -I {{}} connmanctl disconnect {{}}"
            )
            subprocess.run(disconnect_cmd, shell=True)
            subprocess.run("rm -f /storage/.config/wireguard/*.config", shell=True)

            keys_to_remove = ["active", "disconnect", "manual", "reconnect"]

            for key in keys_to_remove:
                f = get_file_path(key)
                if f is not None and os.path.exists(f) is True:
                    try:
                        os.remove(f)
                    except Exception as e:
                        log_message(f"Service Control: Cleanup failure for {f}: {e}", 3)

            subprocess.run(["systemctl", "restart", "connman-vpn"])

            if kodi_env.HAS_KODI_IMPORTS and HAS_KODI_UI:
                title = "[B][COLOR FFBF00FF]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
                message = "[COLOR FFFFFF00]All configs cleared[/COLOR]"
                xbmcgui.Dialog().notification(title, message, icon_ok, 4000)
                xbmc.executebuiltin("Container.Refresh")

    except Exception as e:
        log_message(f"Service Control: ({action}): {e}", 3)
        if kodi_env.HAS_KODI_IMPORTS and HAS_KODI_UI:
            title = "[B][COLOR FFBF00FF]≡ ERROR ≡[/COLOR][/B]"
            message = f"[COLOR FFFFFF00]{action.capitalize()} failed[/COLOR]"
            xbmcgui.Dialog().notification(title, message, icon_err, 5000)
    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    control_service()
