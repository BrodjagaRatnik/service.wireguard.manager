""" ./resources/lib/state_manager.py """
import os

try:
    import xbmcvfs
    PROFILE_DIR = xbmcvfs.translatePath('special://profile/addon_data/service.wireguard.manager')
except ImportError:
    PROFILE_DIR = "/storage/.kodi/userdata/addon_data/service.wireguard.manager"

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
    'dns_backup': 'vpn_dns_backup.json'
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
