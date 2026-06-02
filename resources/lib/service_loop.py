''' ./resources/lib/service_loop.py '''
import os
import xbmc
import xbmcgui
from logger import log_message
from vpn_config import WATCHDOG_HEARTBEAT


def execute_monitor_loop(instance):
    if xbmc.Player().isPlayingVideo():
        instance.cleanup_count = 0
        return

    active_now = instance.vpn_ops.get_active_vpn()

    if not active_now:
        try:
            if os.path.exists('/sys/class/net/'):
                wg_ifs = [
                    i for i in os.listdir('/sys/class/net/')
                    if i.startswith(('wg', 'pia', 'wireguard'))
                ]

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
                            active_now = active_ifs[0]
        except Exception as e:
            log_message(f"Service Loop: Kernel interface scan failed: {e}", 1)

    is_manual = (
        os.path.exists('/tmp/vpn_manual_active.txt') or
        xbmcgui.Window(10000).getProperty('vpn_manual_session').lower() == 'true'
    )
    is_home = xbmc.getCondVisibility("Window.IsActive(home) | Window.IsActive(10000)")
    plugin = xbmc.getInfoLabel("Container.PluginName")
    folder = xbmc.getInfoLabel("Container.FolderPath")

    if is_home and is_manual:
        instance.cleanup_count = 0
        return

    match_found = False

    is_addon_active = (
        plugin.startswith("plugin.video.") or
        (folder and "plugin.video." in folder.lower())
    )

    if not is_home and is_addon_active:
        for i in range(1, 9):
            target = instance._ADDON.getSetting(f"map_{i}_addon")
            vpn_target = instance._ADDON.getSetting(f"vpn_{i}_name")

            if target and (target in folder or target == plugin):
                v_clean = vpn_target.lower().replace(' ', '').strip() if vpn_target else ""
                a_clean = active_now.lower().replace(' ', '').strip() if active_now else ""

                if not active_now:
                    log_message(f"Service Loop: Connecting to profile: {vpn_target}", 0)
                    is_match = False
                else:
                    is_match = (
                        (v_clean == a_clean) or (v_clean in a_clean) or (a_clean in v_clean) or
                        (v_clean.replace('_', '') in a_clean.replace('_', ''))
                    )

                if is_match:
                    match_found = True
                else:
                    match_found = True
                    log_message(f"Service Loop: Switching location map path to target: {vpn_target}.", 1)

                    xbmcgui.Window(10000).setProperty('vpn_manual_session', 'false')
                    if os.path.exists('/tmp/vpn_manual_active.txt'):
                        try:
                            os.remove('/tmp/vpn_manual_active.txt')
                        except Exception:
                            pass

                    instance.vpn_ops.disconnect_vpn(silent=True)

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
            log_msg = f"Service Loop: Home timeout ({user_timeout_sec}s) reached. Disconnecting active profile [{active_now}]."
            log_message(log_msg, 1)

            xbmcgui.Window(10000).setProperty('vpn_manual_session', 'false')
            if os.path.exists('/tmp/vpn_manual_active.txt'):
                try:
                    os.remove('/tmp/vpn_manual_active.txt')
                except Exception:
                    pass

            instance.vpn_ops.disconnect_vpn(silent=False)
    else:
        instance.cleanup_count = 0
