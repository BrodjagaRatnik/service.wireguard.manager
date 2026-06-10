""" ./resources/lib/service_loop.py """
import os
import sys
import xbmc
import xbmcgui
import json
from logger import log_message
from vpn_config import WATCHDOG_HEARTBEAT


def is_nord_match(vpn_target, active_now):
    if vpn_target is None:
        return False
    if not vpn_target:
        return False
    if active_now is None:
        return False
    if not active_now:
        return False

    v_clean = str(vpn_target).strip().lower()
    a_raw = str(active_now).strip()

    parts = a_raw.split()
    if not parts:
        return False

    service_id = parts[-1]
    a_display = a_raw.replace(service_id, "").strip("* ARd ").strip()
    a_clean = a_display.lower()

    if v_clean == a_clean:
        return True
    if v_clean in a_clean:
        return True
    if a_clean in v_clean:
        return True

    v_strip = v_clean.replace("_", "").replace("-", "").replace(" ", "")
    a_strip = a_clean.replace("_", "").replace("-", "").replace(" ", "")

    if v_strip == a_strip:
        return True
    if v_strip in a_strip:
        return True
    if a_strip in v_strip:
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

    v_clean = str(vpn_target).strip().lower()
    a_clean = str(active_now).strip().lower()

    if v_clean == a_clean:
        return True
    if v_clean in a_clean:
        return True
    if a_clean in v_clean:
        return True

    map_path = "/tmp/pia_name_map.json"
    if os.path.exists(map_path) is True:
        try:
            with open(map_path, "r") as f:
                name_map = json.load(f)

            mapped_value = name_map.get(v_clean)
            if mapped_value is not None:
                m_clean = str(mapped_value).strip().lower()
                if m_clean == a_clean:
                    return True
                if m_clean in a_clean:
                    return True
                if a_clean in m_clean:
                    return True

            for key, val in name_map.items():
                k_clean = str(key).strip().lower()
                v_clean_val = str(val).strip().lower()
                if k_clean in v_clean or v_clean in k_clean:
                    if v_clean_val in a_clean or a_clean in v_clean_val:
                        return True
        except Exception:
            pass

    return False


def execute_monitor_loop(instance):
    if xbmc.Player().isPlayingVideo():
        instance.cleanup_count = 0
        return

    active_now = instance.vpn_ops.get_active_vpn()

    if not active_now:
        try:
            if os.path.exists('/sys/class/net/'):
                prefixes = ('nord', 'custom', 'pia', 'wireguard', 'wg')
                wg_ifs = [i for i in os.listdir('/sys/class/net/') if i.startswith(prefixes)]

                if wg_ifs:
                    active_ifs = []
                    for iface in wg_ifs:
                        try:
                            with open(f'/sys/class/net/{iface}/operstate', 'r') as f:
                                if 'up' in f.read().lower():
                                    active_ifs.append(iface)
                        except Exception:
                            pass

                    if active_ifs:
                        config_dir = '/storage/.config/wireguard/'
                        if os.path.exists(config_dir):
                            configs = [
                                c.replace('.config', '').replace('.conf', '')
                                for c in os.listdir(config_dir)
                                if c.endswith(('.config', '.conf'))
                            ]
                            for c in configs:
                                if any(c in iface or iface in c for iface in active_ifs):
                                    active_now = c
                                    break

                        if not active_now:
                            active_now = str(active_ifs[0])
        except Exception as e:
            log_message(f"Service Loop: Kernel interface scan failed: {e}", 1)

    is_manual = (
        os.path.exists('/tmp/vpn_manual_active.txt')
        or xbmcgui.Window(10000).getProperty('vpn_manual_session').lower() == 'true'
    )
    is_home = xbmc.getCondVisibility("Window.IsActive(home) | Window.IsActive(10000)")
    plugin = xbmc.getInfoLabel("Container.PluginName")
    folder = xbmc.getInfoLabel("Container.FolderPath")

    if is_home and is_manual:
        instance.cleanup_count = 0
        return

    match_found = False
    is_addon_active = plugin.startswith("plugin.video.") or (folder and "plugin.video." in folder.lower())

    if not is_home and is_addon_active:
        for i in range(1, 9):
            target = instance._ADDON.getSetting(f"map_{i}_addon")
            vpn_target = instance._ADDON.getSetting(f"vpn_{i}_name")

            if target and (target in folder or target == plugin):
                if not vpn_target or not active_now:
                    is_match = False
                else:
                    if "pia" in str(vpn_target).lower() or "pia" in str(active_now).lower():
                        is_match = is_pia_match(vpn_target, active_now)
                    else:
                        is_match = is_nord_match(vpn_target, active_now)

                if is_match:
                    match_found = True
                else:
                    match_found = False
                    log_message(f"Service Loop: Switching location map path to target: {vpn_target}.", 1)

                    xbmcgui.Window(10000).setProperty('vpn_manual_session', 'false')
                    if os.path.exists('/tmp/vpn_manual_active.txt'):
                        try:
                            os.remove('/tmp/vpn_manual_active.txt')
                        except Exception:
                            pass

                    instance.vpn_ops.disconnect_vpn(silent=True, flush_dns=False)

                    if "resources.lib.providers.pia_utils" in sys.modules:
                        try:
                            pia_mod = sys.modules["resources.lib.providers.pia_utils"]
                            if hasattr(pia_mod, "pia_token_cache"):
                                pia_mod.pia_token_cache = {}
                        except Exception:
                            pass

                    sid = instance.get_service_id_by_name(vpn_target)
                    if sid:
                        instance.vpn_ops.connect_vpn(str(vpn_target), str(sid))
                    else:
                        err_msg = f"Service Loop: Target ID for profile {vpn_target} not found."
                        log_message(err_msg, 3)
                break

    if not match_found and active_now and not is_manual:
        instance.cleanup_count += 1

        try:
            user_timeout_sec = float(instance._ADDON.getSettingInt("home_timeout_sec") or 5)
        except Exception:
            user_timeout_sec = 5.0

        elapsed_time_sec = instance.cleanup_count * (WATCHDOG_HEARTBEAT / 1000.0)

        if elapsed_time_sec >= user_timeout_sec:
            instance.cleanup_count = 0
            log_msg = f"Service Loop: Home timeout reached. Disconnecting profile [{active_now}]."
            log_message(log_msg, 1)

            xbmcgui.Window(10000).setProperty('vpn_manual_session', 'false')
            if os.path.exists('/tmp/vpn_manual_active.txt'):
                try:
                    os.remove('/tmp/vpn_manual_active.txt')
                except Exception:
                    pass

            instance.vpn_ops.disconnect_vpn(silent=False, flush_dns=True)
    else:
        instance.cleanup_count = 0
