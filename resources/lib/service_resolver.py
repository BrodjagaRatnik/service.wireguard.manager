''' .resources/lib/service_resolver.py '''
import os
import re
import subprocess
import sys
from logger import log_message

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


def resolve_service_id(addon, name):
    try:
        search_name = name
        provider_id = addon.getSettingInt("vpn_provider")

        if provider_id in [0, 99] and name:
            conf_dir = '/storage/.config/wireguard/'
            p_prefix = "nord_" if provider_id == 0 else "custom_"
            clean_target = (
                name.lower()
                .replace('nordvpn', '')
                .replace('custom', '')
                .replace('_', '')
                .replace('-', '')
                .strip()
            )

            if os.path.exists(conf_dir):
                for filename in os.listdir(conf_dir):
                    if (filename.startswith(p_prefix)
                            and filename.endswith((".config", ".conf"))):
                        full_path = os.path.join(conf_dir, filename)

                        try:
                            with open(full_path, 'r') as f:
                                content = f.read()

                            name_match = re.search(r'^\s*Name\s*=\s*(.*)', content, re.MULTILINE)
                            if name_match:
                                actual_config_name = name_match.group(1).strip()
                                clean_config_name = (
                                    actual_config_name.lower()
                                    .replace('nordvpn', '')
                                    .replace('custom', '')
                                    .replace('_', '')
                                    .replace('-', '')
                                    .strip()
                                )

                                if (clean_target == clean_config_name
                                        or clean_config_name in clean_target
                                        or clean_target in clean_config_name):
                                    search_name = actual_config_name
                                    break
                        except Exception:
                            pass

        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():
            if search_name in line:
                return line.split()[-1]

    except Exception as e:
        log_message(f"Service lookup error for {name}: {e}", 3)
        return None
