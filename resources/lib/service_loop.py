""" ./resources/lib/service_loop.py """
import os
import sys
import xbmc
import xbmcgui
from logger import log_message
from vpn_config import WATCHDOG_HEARTBEAT, PROVIDER_MAP
from state_manager import get_file_path
from service_matcher import is_nord_match, is_pia_match, is_custom_match


def execute_monitor_loop(instance):
    if xbmc.Player().isPlayingVideo():
        instance.cleanup_count = 0
        return

    from state_manager import get_active_vpn
    active_now = get_active_vpn()

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
                            active_now = str(active_ifs)
        except Exception as e:
            log_message(f"Service Loop: Kernel interface scan failed: {e}", 1)

    manual_path = get_file_path('manual')
    is_manual = (
        (manual_path is not None and os.path.exists(manual_path) is True)
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
                    v_low = str(vpn_target).lower()
                    is_match = False

                    try:
                        p_id = int(instance._ADDON.getSettingInt("vpn_provider") or 0)
                    except Exception:
                        p_id = 0

                    p_name = "Unknown"
                    if p_id in PROVIDER_MAP:
                        p_name = PROVIDER_MAP[p_id]["name"]

                    if p_name == "NordVPN":
                        is_match = is_nord_match(vpn_target, active_now)
                    elif p_name == "PIA":
                        is_match = is_pia_match(vpn_target, active_now)
                    elif p_name == "Custom":
                        is_match = is_custom_match(vpn_target, active_now)
                    else:
                        if "nord" in v_low:
                            is_match = is_nord_match(vpn_target, active_now)
                        elif "pia" in v_low:
                            is_match = is_pia_match(vpn_target, active_now)
                        else:
                            is_match = is_custom_match(vpn_target, active_now)

                if is_match is True:
                    match_found = True
                    break

                log_message(f"Service Loop: Switching location map path to target: {vpn_target}.", 1)

                xbmcgui.Window(10000).setProperty('vpn_manual_session', 'false')
                if manual_path is not None and os.path.exists(manual_path) is True:
                    try:
                        os.remove(manual_path)
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
                    match_found = True
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
            if manual_path is not None and os.path.exists(manual_path) is True:
                try:
                    os.remove(manual_path)
                except Exception:
                    pass

            from state_manager import set_active_vpn
            set_active_vpn(None)
            instance.vpn_ops.disconnect_vpn(silent=False, flush_dns=True)
    else:
        instance.cleanup_count = 0
