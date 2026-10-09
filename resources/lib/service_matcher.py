""" ./resources/lib/service_matcher.py """
import os
import json
import re
from state_manager import get_file_path


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


def _mullvad_country_token(value):
    cleaned = str(value).strip().lower().replace(".config", "").replace(".conf", "")
    parts = [p for p in re.split(r"[\s_\-]+", cleaned) if p]
    for index, token in enumerate(parts):
        if token == "mullvad" and index + 1 < len(parts):
            return parts[index + 1]
    return None


def is_nord_match(vpn_target, active_now):
    if vpn_target is None or not vpn_target:
        return False
    if active_now is None or not active_now:
        return False

    v_nord = _squeeze_form(vpn_target).replace("nordvpn", "").replace("nord", "")
    if not v_nord:
        return False

    for form_tokens in _active_name_forms(active_now):
        a_nord = _squeeze_form(" ".join(form_tokens)).replace("nordvpn", "").replace("nord", "")
        if v_nord == a_nord:
            return True

    return False


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
