''' ./resources/lib/vpn_core.py '''
import os
import sys
if 'utils' in sys.modules and 'service.wireguard.manager' not in str(sys.modules.get('utils')):
    del sys.modules['utils']

import xbmc
import xbmcaddon
import xbmcvfs
import subprocess
import shutil
import xbmcgui
import time
import base64
from logger import log_message
from vpn_config import PROVIDER_MAP

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
CONFIG_DIR = '/storage/.config/wireguard/'
_LIB = xbmcvfs.translatePath(os.path.join(_ADDON.getAddonInfo('path'), 'resources', 'lib'))

sys.path = [p for p in sys.path if 'script.module.srgssr' not in p]
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

ICON_INFO = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')
ICON_UPDATE = os.path.join(ADDON_PATH, 'resources', 'media', 'update.png')
ICON_UPDATE_OK = os.path.join(ADDON_PATH, 'resources', 'media', 'update_ok.png')


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
    """Checks if NordVPN configurations are older than 3.5 days, ignoring PIA."""
    try:
        if os.path.exists(CONFIG_DIR):
            files = [
                os.path.join(CONFIG_DIR, f)
                for f in os.listdir(CONFIG_DIR)
                if f.startswith('nord_') and f.endswith('.config')
            ]

            if not files:
                return

            latest_file = max(files, key=os.path.getmtime)
            if (time.time() - os.path.getmtime(latest_file)) > 302400:
                title = "[B][COLOR FFBF00FF]╠══ [ WG Manager ] ══╣[/COLOR][/B]"
                msg = "[B][COLOR FFFFFF00]NordVPN Server list is 3.5 Days old.[/COLOR][/B]"
                xbmcgui.Dialog().notification(title, msg, ICON_UPDATE, 5000)

    except Exception as e:
        log_message(f"Update VPN configurations check older than... failure: {e}", 3)


def run_update(direct_token=None, force_provider=None):

    if force_provider is not None:
        provider_idx = force_provider
    else:
        provider_idx = _ADDON.getSettingInt("vpn_provider")

    p_data = PROVIDER_MAP.get(provider_idx)

    if not p_data:
        return False

    provider_name = p_data["name"]

    if provider_idx == 1:
        from providers import pia
        provider_module = pia
    else:
        provider_module = p_data["module"]

    success = False

    if provider_idx == 1:
        country_setting = "selected_countries_pia"
    else:
        country_setting = "selected_countries"

    countries = _ADDON.getSetting(country_setting)

    progress = xbmcgui.DialogProgress()
    progress.create("WG Manager", f"Updating {provider_name}...")

    try:
        if provider_idx == 0:
            token = direct_token if direct_token else _ADDON.getSetting("vpn_token")
            token = token.strip().replace('"', '').replace("'", "")

            if not token or len(token) < 10:
                progress.close()
                title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
                msg = "[COLOR FFFFFF00]Invalid Token. Please check settings.[/COLOR]"
                xbmcgui.Dialog().ok(title, msg)
                return False

            progress.update(40, f"Fetching {provider_name} servers...")
            success = provider_module.update(token, countries, CONFIG_DIR)

        elif provider_idx == 1:
            user = ""
            raw_pw = ""

            try:
                files = [f for f in os.listdir(CONFIG_DIR) if f.lower().endswith('.txt')]
                if files:
                    custom_file = os.path.join(CONFIG_DIR, files[0])
                    with open(custom_file, 'r') as f:
                        lines = [line.strip() for line in f.readlines() if line.strip()]
                        if len(lines) >= 2:
                            user = lines[0]
                            raw_pw = lines[1]
                            log_message(f"Direct File Import Success from {files[0]}: {user}", 0)
            except Exception as e:
                log_message(f"File Scan/Read Error: {str(e)}", 0)

            if not user:
                user = _ADDON.getSetting("pia_user").strip()
            if not raw_pw:
                raw_pw = _ADDON.getSetting("pia_pass").strip()

            target_pw = direct_token if direct_token else raw_pw

            try:
                clean_pw = str(target_pw).strip()
                missing_padding = len(clean_pw) % 4
                if missing_padding:
                    clean_pw += '=' * (4 - missing_padding)
                pw = base64.b64decode(clean_pw).decode('utf-8').strip()
            except Exception as e:
                log_message(f"Provider authentication fallback triggered due to decode failure: {e}", 3)
                pw = target_pw

            if not user or not pw:
                if 'progress' in locals() and progress is not None:
                    try:
                        progress.close()
                    except Exception:
                        pass

                missing_items = []
                if not user:
                    missing_items.append("PIA Username")
                if not pw:
                    missing_items.append("PIA Password")

                missing_str = " and ".join(missing_items)

                log_message(f"PIA Configuration Error: Cannot proceed because {missing_str} is missing or blank.", 3)

                title = "[B]≡ [ CREDENTIALS MISSING ] ≡[/B]"
                msg = (
                    f"[COLOR ffff0000]Your {missing_str} is missing![/COLOR]\n\n"
                    "[COLOR FFFFFF00]Please enter your complete PIA credentials inside the configuration "
                    "menu, click 'OK' to save them, and try connecting again.[/COLOR]"
                )
                xbmcgui.Dialog().ok(title, msg)
                return False

            progress.update(40, f"Registering {provider_name} keys...")

            from providers import pia
            success = pia.update(user, pw, countries, CONFIG_DIR)

        elif provider_idx == 99:
            path = _ADDON.getSetting("custom_path")
            if not path or not os.path.exists(path):
                progress.close()
                title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
                msg = "[COLOR FFFFFF00]Select a valid .config file.[/COLOR]"
                xbmcgui.Dialog().ok(title, msg)
                return False

            progress.update(50, "Importing Custom Config...")
            success = provider_module.update(path, CONFIG_DIR)

        progress.close()

        if success:
            log_message(f"Core: Success {provider_name} updated successfully.", 1)
            xbmc.executebuiltin('Container.Refresh')
            return True

        title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
        msg = "[COLOR FFFFFF00]Error. Failed to update {provider_name}.[/COLOR]"
        xbmcgui.Dialog().ok(title, msg)
        return False

    except Exception as e:
        log_message(f"Core: Update exception: {e}", 3)
        if progress:
            progress.close()
        return False
