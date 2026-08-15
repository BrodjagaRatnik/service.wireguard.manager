""" ./resources/lib/service_matcher.py """
import os
import json
from state_manager import get_file_path


def is_nord_match(vpn_target, active_now):
    if vpn_target is None:
        return False
    if not vpn_target:
        return False
    if active_now is None:
        return False
    if not active_now:
        return False

    v_clean = str(vpn_target).strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    a_raw = str(active_now).strip().lower()

    parts = a_raw.split()
    if not parts:
        return False

    if len(parts) == 1:
        a_name = a_raw.replace(".config", "").replace(".conf", "")
    else:
        service_id = parts[-1]
        if service_id.startswith("vpn_"):
            a_name = a_raw[:a_raw.rfind(service_id)].strip()
        else:
            a_name = a_raw.replace(service_id, "").strip()

    for flag in ["*", "R", "A", "O", "d"]:
        if a_name.startswith(flag + " "):
            a_name = a_name[2:].strip()

    a_clean = a_name.strip().lower().replace("_", "").replace("-", "").replace(" ", "")

    v_nord = v_clean.replace("nordvpn", "").replace("nord", "")
    a_nord = a_clean.replace("nordvpn", "").replace("nord", "")

    if v_nord == a_nord:
        return True

    return False


def is_pia_match(vpn_target, active_now):
    if vpn_target is None:
        return False
    if not vpn_target:
        return False
    if active_now is None:
        return False
    if not active_now:
        return False

    v_clean = str(vpn_target).strip().lower().replace(' ', '_').replace('-', '_')
    a_raw = str(active_now).strip().lower()

    parts = a_raw.split()
    if not parts:
        return False

    if len(parts) == 1:
        a_name = a_raw.replace(".config", "").replace(".conf", "")
    else:
        service_id = parts[-1]
        if service_id.startswith("vpn_"):
            a_name = a_raw[:a_raw.rfind(service_id)].strip()
        else:
            a_name = a_raw.replace(service_id, "").strip()

    for flag in ["*", "R", "A", "O", "d"]:
        if a_name.startswith(flag + " "):
            a_name = a_name[2:].strip()

    a_clean = a_name.strip().lower().replace(' ', '_').replace('-', '_')

    map_path = get_file_path('pia_map')
    if map_path is not None and os.path.exists(map_path) is True:
        try:
            with open(map_path, "r") as f:
                name_map = json.load(f)

            mapped_value = name_map.get(v_clean)
            if mapped_value is not None:
                m_clean = str(mapped_value).strip().lower().replace('-', '_')
                if m_clean in a_clean or a_clean in m_clean:
                    return True

            v_key_lookup = v_clean.replace("optimize", "optimized")
            mapped_value = name_map.get(v_key_lookup)
            if mapped_value is not None:
                m_clean = str(mapped_value).strip().lower().replace('-', '_')
                if m_clean in a_clean or a_clean in m_clean:
                    return True

            for key, val in name_map.items():
                k_clean = str(key).strip().lower().replace(' ', '_').replace('-', '_')
                val_clean = str(val).strip().lower().replace(' ', '_').replace('-', '_')

                if v_clean in k_clean or k_clean in v_clean:
                    val_base = val_clean.split('_')[0]
                    if val_base in a_clean or a_clean in val_base:
                        return True
        except Exception:
            pass

    return False


def is_mullvad_match(vpn_target, active_now):
    if vpn_target is None or not vpn_target:
        return False
    if active_now is None or not active_now:
        return False

    v_clean = str(vpn_target).strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    a_raw = str(active_now).strip().lower()

    parts = a_raw.split()
    if not parts:
        return False

    if len(parts) == 1:
        a_name = a_raw.replace(".config", "").replace(".conf", "")
    else:
        service_id = parts[-1]
        if service_id.startswith("vpn_"):
            a_name = a_raw[:a_raw.rfind(service_id)].strip()
        else:
            a_name = a_raw.replace(service_id, "").strip()

    for flag in ["*", "R", "A", "O", "d"]:
        if a_name.startswith(flag + " "):
            a_name = a_name[2:].strip()

    a_clean = a_name.strip().lower().replace("_", "").replace("-", "").replace(" ", "")

    v_mullvad = v_clean.replace("mullvad", "")
    a_mullvad = a_clean.replace("mullvad", "")

    if v_mullvad == a_mullvad:
        return True

    return False


def is_custom_match(vpn_target, active_now):
    if vpn_target is None:
        return False
    if not vpn_target:
        return False
    if active_now is None:
        return False
    if not active_now:
        return False

    v_clean = str(vpn_target).strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    a_raw = str(active_now).strip()

    parts = a_raw.split()
    if not parts:
        return False

    if len(parts) == 1:
        a_name = a_raw.replace(".config", "").replace(".conf", "")
    else:
        service_id = parts[-1]
        if service_id.startswith("vpn_"):
            a_name = a_raw[:a_raw.rfind(service_id)].strip()
        else:
            a_name = a_raw.replace(service_id, "").strip()

    for flag in ["*", "R", "A", "O", "d"]:
        if a_name.startswith(flag + " "):
            a_name = a_name[2:].strip()

    a_clean = a_name.strip().lower().replace("_", "").replace("-", "").replace(" ", "")

    v_cust = v_clean.replace("custom", "")
    a_cust = a_clean.replace("custom", "")

    if v_cust == a_cust:
        return True

    return False
