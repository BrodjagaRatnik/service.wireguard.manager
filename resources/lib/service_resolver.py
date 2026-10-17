""" LibreELEC ./resources/lib/service_resolver.py """
import kodi_env
import os
import re
import subprocess
import sys
from logger import log_message
from state_manager import CONFIG_DIR
from vpn_config import PROVIDER_MAP

ADDON_DIR = kodi_env.ADDON_DIR
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


def _clean_label(label, strip_tokens):
    cleaned = str(label).lower()
    for token in strip_tokens:
        cleaned = cleaned.replace(token, "")
    return cleaned.replace("_", "").replace("-", "").replace(" ", "").strip()


def _provider_search_tokens(p_data):
    tokens = []
    provider_name = str(p_data.get("name", "") or "").lower()
    if provider_name:
        tokens.append(provider_name)
    for extra_name in p_data.get("aliases", []):
        alias_token = str(extra_name or "").lower()
        if alias_token and alias_token not in tokens:
            tokens.append(alias_token)
    return tokens


def resolve_service_id(addon, name):
    try:
        search_name = name
        provider_id = addon.getSettingInt("vpn_provider")
        p_data = PROVIDER_MAP.get(provider_id, {})

        profile_prefixes = [str(p_data.get("prefix", "") or "")]
        profile_prefixes.extend(str(extra or "") for extra in p_data.get("extra_prefixes", []))
        profile_prefixes = [prefix for prefix in profile_prefixes if prefix]

        strip_tokens = _provider_search_tokens(p_data)

        if name and profile_prefixes and os.path.exists(CONFIG_DIR):
            clean_target = _clean_label(name, strip_tokens)

            for filename in os.listdir(CONFIG_DIR):
                if (filename.startswith(tuple(profile_prefixes))
                        and filename.endswith((".config", ".conf"))):
                    full_path = os.path.join(CONFIG_DIR, filename)

                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        name_match = re.search(r'^\s*Name\s*=\s*(.*)', content, re.MULTILINE)
                        if name_match:
                            actual_config_name = name_match.group(1).strip()
                            clean_config_name = _clean_label(actual_config_name, strip_tokens)

                            if (clean_target == clean_config_name
                                    or clean_config_name in clean_target
                                    or clean_target in clean_config_name):
                                search_name = actual_config_name
                                break
                    except Exception:
                        pass

            if search_name == name:
                from service_matcher import find_profile_for_target
                fallback_profile = find_profile_for_target(p_data.get("name"), name)
                if fallback_profile:
                    fallback_path = os.path.join(CONFIG_DIR, f"{fallback_profile}.config")
                    if os.path.exists(fallback_path):
                        try:
                            with open(fallback_path, 'r', encoding='utf-8') as f:
                                fallback_content = f.read()
                            fallback_match = re.search(
                                r'^\s*Name\s*=\s*(.*)', fallback_content, re.MULTILINE
                            )
                            if fallback_match:
                                search_name = fallback_match.group(1).strip()
                            else:
                                search_name = fallback_profile
                        except Exception:
                            search_name = fallback_profile

        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():
            if search_name in line:
                return line.split()[-1]

    except Exception as e:
        log_message(f"Service Resolver: lookup error for {name}: {e}", 3)
        return None
