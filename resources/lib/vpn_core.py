''' ./resources/lib/vpn_core.py '''
import os
import xbmcaddon
import xbmcvfs
import subprocess
import shutil
import xbmcgui
import time
from logger import log_message
from vpn_config import PROVIDER_MAP
from resources.lib.vpn_core_upd import run_update as execute_vpn_update

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
CONFIG_DIR = '/storage/.config/wireguard/'
_LIB = xbmcvfs.translatePath(os.path.join(_ADDON.getAddonInfo('path'), 'resources', 'lib'))
ICON_INFO = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')
ICON_UPDATE = os.path.join(ADDON_PATH, 'resources', 'media', 'update.png')
ICON_UPDATE_OK = os.path.join(ADDON_PATH, 'resources', 'media', 'update_ok.png')
LAST_RUN_TIMESTAMP = 0
CONFIG_DIR = '/storage/.config/wireguard'


def install_service(source, dest, name, media_path):
    try:
        dest_dir = os.path.dirname(dest)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        shutil.copy2(source, dest)
        subprocess.run(["systemctl", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "enable", name], check=False)
        subprocess.run(["systemctl", "restart", name], check=False)

        title = "[B][COLOR FFBF00FF]╠══ [ WG Manager ] ══╣[/COLOR][/B]"
        msg = "[B][COLOR FFFFFF00]Watchdog Installed.[/COLOR][/B]"
        xbmcgui.Dialog().notification(title, msg, ICON_UPDATE_OK, 4000)

        return True

    except Exception as e:
        log_message(f"Core: Service Installation failed: {e}", 3)
        return False


def check_for_updates(media_path):
    global LAST_RUN_TIMESTAMP

    try:
        if time.localtime().tm_year < 2026:
            return

        provider_idx = _ADDON.getSettingInt("vpn_provider")
        p_data = PROVIDER_MAP.get(provider_idx)

        if not p_data or not p_data.get("needs_file_check", False):
            return

        provider_name = p_data["name"]
        file_prefix = p_data["prefix"]

        if os.path.exists(CONFIG_DIR):
            files = [
                f for f in os.listdir(CONFIG_DIR)
                if f.startswith(file_prefix) and f.endswith('.config')
            ]

            if not files:
                return

            try:
                slider_val = _ADDON.getSetting('update_interval_days')
                slider_days = int(float(slider_val)) if slider_val else 3
                if slider_days <= 0:
                    slider_days = 3
            except ValueError:
                slider_days = 3

            max_age_seconds = slider_days * 86400
            current_time = int(time.time())

            try:
                last_update_val = _ADDON.getSetting('last_vpn_update_time')
                last_update_time = int(last_update_val) if last_update_val else 0
            except ValueError:
                last_update_time = 0

            first_file_path = os.path.join(CONFIG_DIR, files[0])
            file_age_seconds = current_time - int(os.path.getmtime(first_file_path))

            log_msg = (
                f"Core: current_time={current_time}, "
                f"last_update_time={last_update_time}, "
                f"file_age={file_age_seconds}, "
                f"max_age={max_age_seconds}"
            )
            log_message(log_msg, 0)

            if LAST_RUN_TIMESTAMP != 0 and (current_time - LAST_RUN_TIMESTAMP) >= 60:
                LAST_RUN_TIMESTAMP = 0

            if LAST_RUN_TIMESTAMP != 0:
                return

            if current_time < last_update_time:
                _ADDON.setSetting('last_vpn_update_time', str(current_time))
                return

            if file_age_seconds > max_age_seconds:
                if (current_time - last_update_time) < 120:
                    log_msg = "Core: Run skipped. Update recently attempted but files are unchanged."
                    log_message(log_msg, 0)
                    return

                update_successful = run_update()

                if update_successful:

                    LAST_RUN_TIMESTAMP = current_time

                    title = (
                        f"[B][COLOR FFBF00FF]╠══ [ WG Manager: "
                        f"{provider_name} ] ══╣[/COLOR][/B]"
                    )
                    msg = (
                        f"[B][COLOR FFFFFF00]{provider_name} server list "
                        f"has been successfully updated![/COLOR][/B]"
                    )
                    xbmcgui.Dialog().notification(
                        title, msg, ICON_UPDATE_OK, 3000
                    )

                else:

                    title = (
                        f"[B][COLOR FFFF3333]╠══ [ WG Manager: "
                        f"{provider_name} ] ══╣[/COLOR][/B]"
                    )
                    msg = (
                        f"[B][COLOR FFFFFFFF]Update failed. Using existing "
                        f"server list ({slider_days} Days old).[/COLOR][/B]"
                    )
                    xbmcgui.Dialog().notification(
                        title, msg, ICON_UPDATE, 4500
                    )

                try:
                    new_age = current_time - int(os.path.getmtime(first_file_path))
                    if new_age < 30:
                        _ADDON.setSetting('last_vpn_update_time', str(current_time))
                        log_message("Core: Update successful. File timestamps updated.", 0)
                    else:
                        log_message("Core: Update completed but files on disk did not change.", 0)
                except Exception:
                    pass
            else:
                log_message("Core: Update skipped. Configurations are still fresh.", 0)

    except Exception as e:
        log_message(f"Update VPN configurations check older than... failure: {e}", 3)


def run_update(direct_token=None, force_provider=None):
    return execute_vpn_update(direct_token=direct_token, force_provider=force_provider)
