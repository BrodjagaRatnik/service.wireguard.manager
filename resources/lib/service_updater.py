""" ./resources/lib/service_updater.py """
import kodi_env
import os
import sys
from logger import log_message
from state_manager import get_file_path


def inject_lib_path():
    addon_dir = kodi_env.ADDON_DIR
    lib_path = os.path.join(addon_dir, "resources", "lib")
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)


def handle_settings_update(addon):
    inject_lib_path()
    notif_lock = get_file_path("notif_lock")
    if notif_lock is not None and os.path.exists(notif_lock) is True:
        try:
            os.remove(notif_lock)
        except Exception:
            pass

    if addon.getSettingBool("first_run") is False:
        kodi_env.clear_script_globals()
        return

    provider_id = addon.getSettingInt("vpn_provider")
    config_dir = "/storage/.config/wireguard/"
    if provider_id < 0:
        kodi_env.clear_script_globals()
        return

    if provider_id == 1:
        try:
            from providers import pia
            from wm_utils import safe_decrypt_password, safe_encrypt_password

            user = addon.getSetting("pia_user").strip()
            raw_pw = addon.getSetting("pia_pass").strip()
            ids = addon.getSetting("selected_countries_pia").strip()

            if user and raw_pw and ids:
                pw = safe_decrypt_password(raw_pw)

                if not raw_pw.startswith("b64:"):
                    encoded_string = safe_encrypt_password(pw)
                    addon.setSetting("pia_pass", encoded_string)
                    log_msg = "Service Updater: Plain text password detected. Saved cleanly to Kodi settings."
                    log_message(log_msg, 1)

                pia.update(user, pw, ids, config_dir)

        except Exception as e:
            log_message(f"Service Updater: PIA update failed: {e}", 3)

    elif provider_id == 0:
        try:
            from providers import nordvpn
            token = addon.getSetting("vpn_token")
            ids = addon.getSetting("selected_countries").strip()
            if token and ids:
                nordvpn.update(token, ids, config_dir)
        except Exception as e:
            log_message(f"Service Updater: Nord update failed: {e}", 3)

    kodi_env.clear_script_globals()
