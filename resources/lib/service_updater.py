''' .resources/lib/service_updater.py '''
import os
import sys
from logger import log_message

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


def handle_settings_update(addon):
    if os.path.exists('/tmp/vpn_notif_sent.lock'):
        try:
            os.remove('/tmp/vpn_notif_sent.lock')
        except Exception:
            pass

    if not addon.getSettingBool("first_run"):
        return

    provider_id = addon.getSettingInt("vpn_provider")
    config_dir = "/storage/.config/wireguard/"
    if provider_id < 0:
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

                if not raw_pw.startswith('b64:'):
                    encoded_string = safe_encrypt_password(pw)
                    addon.setSetting("pia_pass", encoded_string)
                    log_msg = "Service Updater: New plain text password detected. Saved cleanly to Kodi settings."
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
