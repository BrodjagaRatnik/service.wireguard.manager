''' .resources/lib/service_updater.py '''
import base64
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
            user = addon.getSetting("pia_user").strip()
            raw_pw = addon.getSetting("pia_pass").strip()
            ids = addon.getSetting("selected_countries_pia").strip()

            if user and raw_pw and ids:
                try:
                    clean_pw = str(raw_pw).strip()
                    missing_padding = len(clean_pw) % 4
                    if missing_padding:
                        clean_pw += '=' * (4 - missing_padding)
                    pw = base64.b64decode(clean_pw).decode('utf-8').strip()
                except Exception:
                    pw = raw_pw

                pia.update(user, pw, ids, config_dir)
        except Exception as e:
            log_message(f"PIA update failed: {e}", 3)

    elif provider_id == 0:
        try:
            from providers import nordvpn
            token = addon.getSetting("vpn_token")
            ids = addon.getSetting("selected_countries").strip()
            if token and ids:
                nordvpn.update(token, ids, config_dir)
        except Exception as e:
            log_message(f"Nord update failed: {e}", 3)
