''' ./resources/lib/vpn_core_upd.py '''
import os
import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui
from logger import log_message
from vpn_config import PROVIDER_MAP

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

            progress.update(30, f"Fetching {provider_name} servers...")
            success = provider_module.update(token, countries, CONFIG_DIR)
            if success:
                progress.update(100, "Update complete!")

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
                            log_message(f"Core Update: Direct File Import Success from {files[0]}: {user}", 0)
            except Exception as e:
                log_message(f"Core Update: File Scan/Read Error: {str(e)}", 3)

            if not user:
                user = _ADDON.getSetting("pia_user").strip()

            if not raw_pw:
                from wm_utils import safe_decrypt_password
                pw = safe_decrypt_password(_ADDON.getSetting("pia_pass"))
            else:
                from wm_utils import safe_decrypt_password
                pw = safe_decrypt_password(raw_pw)

            if direct_token:
                pw = str(direct_token).strip()

            if not user or not pw:
                progress.close()

                missing_items = []
                if not user:
                    missing_items.append("PIA Username")
                if not pw:
                    missing_items.append("PIA Password")

                missing_str = " and ".join(missing_items)
                log_message(f"Core Update: PIA Configuration Error: Missing {missing_str}.", 3)

                title = "[B]≡ [ CREDENTIALS MISSING ] ≡[/B]"
                msg = (
                    f"[COLOR ffff0000]Your {missing_str} is missing![/COLOR]\n\n"
                    "[COLOR FFFFFF00]Please enter your complete PIA credentials inside the configuration "
                    "menu, click 'OK' to save them, and try connecting again.[/COLOR]"
                )
                xbmcgui.Dialog().ok(title, msg)
                return False

            progress.update(60, f"Registering {provider_name} keys...")
            success = pia.update(user, pw, countries, CONFIG_DIR)
            if success:
                progress.update(100, "Update complete!")

        elif provider_idx == 99:
            path = _ADDON.getSetting("custom_path")
            if not path or not os.path.exists(path):
                progress.close()
                title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
                msg = "[COLOR FFFFFF00]Select a valid .config file.[/COLOR]"
                xbmcgui.Dialog().ok(title, msg)
                return False

            progress.update(90, "Importing Custom Config...")
            success = provider_module.update(path, CONFIG_DIR)
            if success:
                progress.update(100, "Import complete!")

        progress.close()

        if success:
            log_message(f"Core Update: Success {provider_name} updated successfully.", 1)
            xbmc.executebuiltin('Container.Refresh')
            return True

        title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
        msg = f"[COLOR FFFFFF00]Error. Failed to update {provider_name}.[/COLOR]"
        xbmcgui.Dialog().ok(title, msg)
        return False

    except Exception as e:
        log_message(f"Core Update: Update exception: {e}", 3)
        progress.close()
        return False
