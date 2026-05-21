''' .resources/scripts/update_vpn.py '''
import sys
import os
import xbmcaddon
from vpn_config import PROVIDER_MAP
from logger import log_message

script_path = os.path.dirname(__file__)
lib_path = os.path.join(script_path, '..', 'lib')
sys.path.append(os.path.normpath(lib_path))


def main():
    addon = xbmcaddon.Addon('service.wireguard.manager')
    provider_idx = addon.getSettingInt("vpn_provider")
    config_dir = '/storage/.config/wireguard/'

    p_data = PROVIDER_MAP.get(provider_idx)
    if not p_data:
        return

    provider_module = p_data["module"]

    try:
        if provider_idx == 0:
            token = addon.getSetting("vpn_token")
            countries = addon.getSetting("selected_countries")
            provider_module.update(token, countries, config_dir)

        elif provider_idx == 1:
            user = addon.getSetting("pia_user")
            pw = addon.getSetting("pia_pass")
            countries = addon.getSetting("selected_countries")
            provider_module.update(user, pw, countries, config_dir)

        elif provider_idx == 99:
            path = addon.getSetting("custom_path")
            provider_module.update(path, config_dir)

    except Exception as e:
        log_message(f"Script Error: {e}", 3)


if __name__ == "__main__":
    main()
