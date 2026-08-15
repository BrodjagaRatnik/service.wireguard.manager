""" ./resources/lib/vpn_core_upd.py """
import kodi_env
import os
from logger import log_message
from vpn_config import PROVIDER_MAP

try:
    import xbmc
    import xbmcgui
    HAS_KODI_UI = True
except ImportError:
    HAS_KODI_UI = False

CONFIG_DIR = "/storage/.config/wireguard"


def get_addon_path():
    return kodi_env.ADDON_DIR


def run_update(direct_token=None, force_provider=None, silent=False):
    progress = None

    try:
        addon_obj = kodi_env.get_addon_instance()
        if not addon_obj:
            return False

        if force_provider is not None:
            provider_idx = force_provider
        else:
            provider_idx = addon_obj.getSettingInt("vpn_provider")

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
        elif provider_idx == 2:
            country_setting = "filter"
        else:
            country_setting = "selected_countries"

        countries = addon_obj.getSetting(country_setting)

        if silent is False and HAS_KODI_UI:
            progress = xbmcgui.DialogProgress()
            progress.create("WG Manager", f"Updating {provider_name}...")

        if provider_idx == 0:
            token = direct_token if direct_token else addon_obj.getSetting("vpn_token")
            token = token.strip().replace('"', '').replace("'", "")

            if not token or len(token) < 10:
                if progress:
                    progress.close()
                if HAS_KODI_UI:
                    title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
                    msg = "[COLOR FFFFFF00]Invalid Token. Please check settings.[/COLOR]"
                    xbmcgui.Dialog().ok(title, msg)
                return False

            if progress:
                progress.update(30, f"Fetching {provider_name} servers...")
            success = provider_module.update(token, countries, CONFIG_DIR)
            if success and progress:
                progress.update(100, "Update complete!")

        elif provider_idx == 1:
            user = ""
            raw_pw = ""

            try:
                files = [f for f in os.listdir(CONFIG_DIR) if f.lower().endswith(".txt")]
                if files:
                    custom_file = os.path.join(CONFIG_DIR, files[0])
                    with open(custom_file, "r") as f:
                        lines = [line.strip() for line in f.readlines() if line.strip()]
                        if len(lines) >= 2:
                            user = lines[0]
                            raw_pw = lines[1]
                            log_message(f"Core Update: Import Success: {user}", 0)
            except Exception as e:
                log_message(f"Core Update: File Scan/Read Error: {str(e)}", 3)

            if not user:
                user = addon_obj.getSetting("pia_user").strip()

            if not raw_pw:
                from wm_utils import safe_decrypt_password
                pw = safe_decrypt_password(addon_obj.getSetting("pia_pass"))
            else:
                from wm_utils import safe_decrypt_password
                pw = safe_decrypt_password(raw_pw)

            if direct_token:
                pw = str(direct_token).strip()

            if not user or not pw:
                if progress:
                    progress.close()

                missing_items = []
                if not user:
                    missing_items.append("PIA Username")
                if not pw:
                    missing_items.append("PIA Password")

                missing_str = " and ".join(missing_items)
                log_message(f"Core Update: PIA Configuration Error: Missing {missing_str}.", 3)

                if HAS_KODI_UI:
                    title = "[B]≡ [ CREDENTIALS MISSING ] ≡[/B]"
                    msg = (
                        f"[COLOR ffff0000]Your {missing_str} is missing![/COLOR]\n\n"
                        "[COLOR FFFFFF00]Please enter your complete PIA credentials inside the "
                        "configuration menu, click 'OK' to save them, and try connecting again.[/COLOR]"
                    )
                    xbmcgui.Dialog().ok(title, msg)
                return False

            if progress:
                progress.update(60, f"Registering {provider_name} keys...")
            success = pia.update(user, pw, countries, CONFIG_DIR)
            if success and progress:
                progress.update(100, "Update complete!")

        elif provider_idx == 2:
            account = direct_token if direct_token else addon_obj.getSetting("account_number")

            from wm_utils import safe_decrypt_password
            account = safe_decrypt_password(account)
            account = "".join(account.split()).strip()

            if not account or not account.isdigit() or len(account) != 16:
                if progress:
                    progress.close()
                if HAS_KODI_UI:
                    title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
                    msg = "[COLOR FFFFFF00]Invalid 16-digit Mullvad account number.[/COLOR]"
                    xbmcgui.Dialog().ok(title, msg)
                    log_message("Core Update: Invalid 16-digit Mullvad account number.", 3)
                return False

            owned_val = addon_obj.getSetting("wg_owned").lower() == "true"

            if progress:
                progress.update(50, f"Generating dynamic {provider_name} environments...")

            try:
                import providers.mullvad_utils as m_utils
                m_utils.generate_mullvad_configs(
                    account_id=account,
                    country_filter=countries,
                    mtu_setting=1380,
                    owned=owned_val
                )
                success = True
            except Exception as m_err:
                log_message(f"Core Update: Mullvad generation failed: {m_err}", 3)
                success = False

            if success and progress:
                progress.update(100, "Update complete!")

        elif provider_idx == 99:
            path = addon_obj.getSetting("custom_path")
            if not path or not os.path.exists(path):
                if progress:
                    progress.close()
                if HAS_KODI_UI:
                    title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
                    msg = "[COLOR FFFFFF00]Select a valid .config file.[/COLOR]"
                    xbmcgui.Dialog().ok(title, msg)
                return False

            if progress:
                progress.update(90, "Importing Custom Config...")
            success = provider_module.update(path, CONFIG_DIR)
            if success and progress:
                progress.update(100, "Import complete!")

        if progress:
            progress.close()

        if success:
            log_message(f"Core Update: {provider_name} profile database updated successfully.", 1)
            if HAS_KODI_UI:
                xbmc.executebuiltin("Container.Refresh")
            return True

        if HAS_KODI_UI:
            title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
            msg = f"[COLOR FFFFFF00]Error. Failed to update {provider_name}.[/COLOR]"
            xbmcgui.Dialog().ok(title, msg)
        return False

    except Exception as e:
        log_message(f"Core Update: Update exception: {e}", 3)
        if progress:
            progress.close()
        return False

    finally:
        kodi_env.clear_script_globals()
