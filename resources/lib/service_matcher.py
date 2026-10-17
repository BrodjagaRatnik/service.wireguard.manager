""" LibreELEC ./resources/lib/service_matcher.py """
import os
import json
import re
from state_manager import get_file_path, CONFIG_DIR


def _active_name_forms(active_now):
    base = str(active_now).strip().lower().replace(".config", "").replace(".conf", "")
    tokens = base.split()
    while tokens and tokens[0].startswith("*"):
        tokens = tokens[1:]
    forms = []
    if tokens:
        forms.append(tokens)
        if len(tokens) > 1:
            forms.append(tokens[:-1])
    return forms


def _squeeze_form(value):
    return str(value).strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _underscore_form(value):
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _load_nord_country_map():
    map_path = get_file_path('nord_map')
    if map_path is None or os.path.exists(map_path) is not True:
        return {}
    try:
        with open(map_path, "r") as f:
            loaded_map = json.load(f)
        if isinstance(loaded_map, dict):
            return {k.lower(): v.lower() for k, v in loaded_map.items()}
    except Exception:
        pass
    return {}


def _extract_country_code_from_nord_filename(filename):
    base = str(filename).strip().lower().replace(".config", "").replace(".conf", "")
    match = re.match(r"^nord_([a-z]{2})\d+$", base)
    if match:
        return match.group(1)
    return None


def _find_matching_country_name(target_name):
    nord_map = _load_nord_country_map()
    if not nord_map:
        return None

    squeezed_target = _squeeze_form(target_name)
    if not squeezed_target:
        return None

    sorted_keys = sorted(nord_map.keys(), key=len, reverse=True)
    for country_name in sorted_keys:
        squeezed_key = _squeeze_form(country_name)
        if squeezed_key and squeezed_key in squeezed_target:
            return country_name

    return None


def _country_code_for_label(label):
    if label is None or not label:
        return None

    base = str(label).strip().lower().replace(".config", "").replace(".conf", "")
    basename_match = re.match(r"^nord_([a-z]{2})\d+$", base)
    if basename_match:
        return basename_match.group(1)

    country_name = _find_matching_country_name(base)
    if not country_name:
        return None

    nord_map = _load_nord_country_map()
    resolved_code = nord_map.get(country_name, "")
    if not resolved_code:
        return None
    return str(resolved_code).lower()


def is_nord_match(vpn_target, active_now):
    if vpn_target is None or not vpn_target:
        return False
    if active_now is None or not active_now:
        return False

    target_code = _country_code_for_label(vpn_target)
    active_code = _country_code_for_label(active_now)

    if not target_code or not active_code:
        return False

    return target_code == active_code


def find_nord_profile_for_target(vpn_target):
    if vpn_target is None or not vpn_target:
        return None

    country_name = _find_matching_country_name(vpn_target)
    if not country_name:
        return None

    nord_map = _load_nord_country_map()
    expected_code = nord_map.get(country_name, "").lower()
    if not expected_code:
        return None

    try:
        candidates = [
            entry for entry in os.listdir(CONFIG_DIR)
            if entry.startswith(f"nord_{expected_code}") and entry.endswith(".config")
        ]
    except Exception:
        return None

    if not candidates:
        return None

    candidates.sort()
    return candidates[0].replace(".config", "")


def is_pia_match(vpn_target, active_now):
    if vpn_target is None or not vpn_target:
        return False
    if active_now is None or not active_now:
        return False

    v_clean = _underscore_form(vpn_target)

    map_path = get_file_path('pia_map')
    name_map = {}
    if map_path is not None and os.path.exists(map_path) is True:
        try:
            with open(map_path, "r") as f:
                name_map = json.load(f)
        except Exception:
            name_map = {}

    for form_tokens in _active_name_forms(active_now):
        a_clean = _underscore_form(" ".join(form_tokens))

        mapped_value = name_map.get(v_clean)
        if mapped_value is not None:
            m_clean = _underscore_form(mapped_value)
            if m_clean in a_clean or a_clean in m_clean:
                return True

        v_key_lookup = v_clean.replace("optimize", "optimized")
        mapped_value = name_map.get(v_key_lookup)
        if mapped_value is not None:
            m_clean = _underscore_form(mapped_value)
            if m_clean in a_clean or a_clean in m_clean:
                return True

        for key, val in name_map.items():
            k_clean = _underscore_form(key)
            val_clean = _underscore_form(val)

            if v_clean in k_clean or k_clean in v_clean:
                val_base = val_clean.split('_')[0]
                if val_base in a_clean or a_clean in val_base:
                    return True

    return False


def is_mullvad_match(vpn_target, active_now):
    if vpn_target is None or not vpn_target:
        return False
    if active_now is None or not active_now:
        return False

    v_country = _mullvad_country_token(vpn_target)
    if not v_country:
        return False

    for form_tokens in _active_name_forms(active_now):
        a_country = _mullvad_country_token(" ".join(form_tokens))
        if a_country == v_country:
            return True

    return False


def _mullvad_country_token(value):
    cleaned = str(value).strip().lower().replace(".config", "").replace(".conf", "")
    parts = [p for p in re.split(r"[\s_\-]+", cleaned) if p]
    for index, token in enumerate(parts):
        if token == "mullvad" and index + 1 < len(parts):
            return parts[index + 1]
    return None


def is_custom_match(vpn_target, active_now):
    if vpn_target is None or not vpn_target:
        return False
    if active_now is None or not active_now:
        return False

    v_cust = _squeeze_form(vpn_target).replace("custom", "")
    if not v_cust:
        return False

    for form_tokens in _active_name_forms(active_now):
        a_cust = _squeeze_form(" ".join(form_tokens)).replace("custom", "")
        if v_cust == a_cust:
            return True

    return False


_PROVIDER_PROFILE_RESOLVERS = {
    "nordvpn": find_nord_profile_for_target,
}


def find_profile_for_target(provider_name, vpn_target):
    if provider_name is None or not provider_name:
        return None

    resolver = _PROVIDER_PROFILE_RESOLVERS.get(str(provider_name).lower())
    if resolver is None:
        return None
    return resolver(vpn_target)
