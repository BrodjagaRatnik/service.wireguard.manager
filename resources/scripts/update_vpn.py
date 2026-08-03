""" ./resources/scripts/update_vpn.py """
import kodi_env
import sys
import os
from vpn_config import PROVIDER_MAP
from logger import log_message

SCRIPT_PATH = os.path.dirname(__file__)
LIB_PATH = os.path.normpath(os.path.join(SCRIPT_PATH, "..", "lib"))

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)


def main():
    try:
        addon_obj = kodi_env.get_addon_instance()
        if not addon_obj:
            return

        provider_idx = addon_obj.getSettingInt("vpn_provider")
        config_dir = "/storage/.config/wireguard/"

        p_data = PROVIDER_MAP.get(provider_idx)
        if not p_data:
            return

        provider_module = p_data["module"]

        if provider_idx == 0:
            token = addon_obj.getSetting("vpn_token")
            countries = addon_obj.getSetting("selected_countries")
            provider_module.update(token, countries, config_dir)

        elif provider_idx == 1:
            user = addon_obj.getSetting("pia_user")
            pw = addon_obj.getSetting("pia_pass")
            countries = addon_obj.getSetting("selected_countries")
            provider_module.update(user, pw, countries, config_dir)

        elif provider_idx == 2:
            account = addon_obj.getSetting("mullvad_account")
            countries = addon_obj.getSetting("mullvad_filter")
            mtu = addon_obj.getSettingInt("mullvad_mtu")
            provider_module.generate_mullvad_configs(account, countries, mtu)
            provider_module.convert_to_connman_configs()

        elif provider_idx == 99:
            path = addon_obj.getSetting("custom_path")
            provider_module.update(path, config_dir)

    except Exception as e:
        log_message(f"Script Error: {e}", 3)

    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    main()
