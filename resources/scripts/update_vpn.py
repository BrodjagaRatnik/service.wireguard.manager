""" ./resources/scripts/update_vpn.py """
import os
import sys
import kodi_env
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
            import providers.mullvad_utils as m_utils
            account = addon_obj.getSetting("account_number")
            countries = addon_obj.getSetting("filter")
            mtu = addon_obj.getSettingInt("mtu")
            owned = addon_obj.getSettingBool("wg_owned")
            m_utils.generate_mullvad_configs(
                account_id=account,
                country_filter=countries,
                mtu_setting=mtu,
                owned=owned
            )

        elif provider_idx == 99:
            path = addon_obj.getSetting("custom_path")
            provider_module.update(path, config_dir)

    except Exception as e:
        log_message(f"Script Error: {e}", 3)

    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    main()
