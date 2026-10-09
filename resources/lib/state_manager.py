""" ./resources/lib/state_manager.py """
import json
import os

try:
    import xbmcvfs
    PROFILE_DIR = xbmcvfs.translatePath('special://profile/addon_data/service.wireguard.manager')
except ImportError:
    _ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))
    _USERDATA_ROOT = os.path.join(os.path.dirname(_ADDON_ROOT), "userdata")
    PROFILE_DIR = os.path.join(_USERDATA_ROOT, "addon_data", "service.wireguard.manager")

_STORAGE_ROOT = os.path.abspath(
    os.path.join(PROFILE_DIR, os.pardir, os.pardir, os.pardir, os.pardir)
)
CONFIG_DIR = os.path.join(_STORAGE_ROOT, ".config", "wireguard")
SYSTEMD_DIR = os.path.join(_STORAGE_ROOT, ".config", "system.d")

FILE_MAP = {
    'active': 'vpn_manager_active.txt',
    'manual': 'vpn_manual_active.txt',
    'reconnect': 'vpn_reconnect_count.txt',
    'disconnect': 'vpn_intentional_disconnect.txt',
    'blackout': 'vpn_blackout_active.lock',
    'pia_map': 'pia_name_map.json',
    'pia_cache': 'pia_token_cache.json',
    'mullvad_settings': 'mullvad_settings.ini',
    'connector_lock': 'vpn_connector_active.lock',
    'notif_lock': 'vpn_notif_sent.lock',
    'dns_backup': 'vpn_dns_backup.json',
    'cycle_fail_state': 'vpn_cycle_fail_state.json',
    'slots': 'vpn_slot_map.json'
}


def get_file_path(key):
    if key not in FILE_MAP:
        return None
    try:
        if not os.path.exists(PROFILE_DIR):
            os.makedirs(PROFILE_DIR, exist_ok=True)
    except Exception:
        pass
    return os.path.join(PROFILE_DIR, FILE_MAP[key])


def clear_startup_states():
    startup_keys = ['active', 'reconnect', 'dns_backup']
    for key in startup_keys:
        path = get_file_path(key)
        if path is not None and (os.path.exists(path) is True):
            try:
                os.remove(path)
            except Exception:
                pass


def write_state(key, content):
    path = get_file_path(key)
    if path is None:
        return False
    try:
        with open(path, 'w') as f:
            f.write(str(content))
        return True
    except Exception:
        return False


def read_state(key):
    path = get_file_path(key)
    if path is None or (os.path.exists(path) is False):
        return None
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return None


def get_active_vpn():
    path = get_file_path('active')
    if path is not None and (os.path.exists(path) is True):
        try:
            with open(path, "r") as f:
                return f.read().strip() or None
        except Exception:
            return None
    return None


def set_active_vpn(name):
    path = get_file_path('active')
    if path is None:
        return
    try:
        if name:
            with open(path, "w") as f:
                f.write(name.strip())
        elif os.path.exists(path) is True:
            os.remove(path)
    except Exception:
        pass


def get_slot_assignments():
    raw = read_state('slots')
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, TypeError):
        pass
    return {}


def get_slot_assignment(slot_id):
    slot_entry = get_slot_assignments().get(str(slot_id))
    if isinstance(slot_entry, dict):
        return slot_entry.get('vpn_name'), slot_entry.get('addon_id')
    return None, None


def save_slot_assignment(slot_id, vpn_name, addon_id):
    assignments = get_slot_assignments()
    assignments[str(slot_id)] = {'vpn_name': vpn_name, 'addon_id': addon_id}
    return write_state('slots', json.dumps(assignments))


def clear_slot_assignment(slot_id):
    assignments = get_slot_assignments()
    if str(slot_id) in assignments:
        del assignments[str(slot_id)]
    return write_state('slots', json.dumps(assignments))
