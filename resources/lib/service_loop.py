''' ./resources/lib/service_loop.py '''
import os
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from logger import log_message
from vpn_config import WATCHDOG_HEARTBEAT
from vpn_core import check_for_updates


def execute_monitor_loop(instance):

    current_time = time.time()

    if not hasattr(instance, 'last_update_check'):
        instance.last_update_check = 0.0

    if (current_time - instance.last_update_check) > 21600:
        instance.last_update_check = current_time
        try:
            log_message("Service Loop: Running automated background VPN age check...", 0)
            addon_path = xbmcvfs.translatePath(instance._ADDON.getAddonInfo('path'))
            media_path = os.path.join(addon_path, 'resources', 'media')
            check_for_updates(media_path)
        except Exception as e:
            log_message(f"Service Loop: Background update check exception: {e}", 3)

    if os.path.exists('/tmp/vpn_intentional_disconnect.txt'):
        instance.cleanup_count = 0
        return

    if xbmc.Player().isPlayingVideo():
        instance.cleanup_count = 0
        return

    active_now = instance.vpn_ops.get_active_vpn()

    if not active_now:
        try:
            if os.path.exists('/sys/class/net/'):
                interfaces = os.listdir('/sys/class/net/')
                wg_ifs = [
                    i for i in interfaces
                    if i.startswith(('wg', 'pia', 'wireguard'))
                ]

                if wg_ifs:
                    config_dir = '/storage/.config/wireguard/'
                    if os.path.exists(config_dir):
                        configs = [
                            c.replace('.config', '').replace('.conf', '')
                            for c in os.listdir(config_dir)
                            if c.endswith(('.config', '.conf'))
                        ]
                        for c in configs:
                            if any(c in iface or iface in c for iface in wg_ifs):
                                active_now = c
                                break

                    if not active_now:
                        active_now = wg_ifs[0]

        except Exception as e:
            log_msg = f"Monitor: Kernel interface scan failed: {e}"
            log_message(log_msg, 0)

    is_manual = (
        xbmcgui.Window(10000)
        .getProperty('vpn_manual_session')
        .lower() == 'true'
        or os.path.exists('/tmp/vpn_manual_active.txt')
    )

    is_home = xbmc.getCondVisibility(
        "Window.IsActive(home) | Window.IsActive(10000)"
    )
    plugin = xbmc.getInfoLabel("Container.PluginName")
    folder = xbmc.getInfoLabel("Container.FolderPath")

    is_manual_file = os.path.exists('/tmp/vpn_manual_active.txt')
    is_manual_prop = xbmcgui.Window(10000).getProperty('vpn_manual_session').lower() == 'true'

    if is_home and (is_manual_file or is_manual_prop):
        instance.cleanup_count = 0
        return

    match_found = False

    is_local_video_dir = (
        not is_home
        and folder
        and any(proto in folder.lower() for proto in ["smb://", "nfs://", "sftp://", "vfs://", "/storage/"])
    )

    if not is_home and plugin.startswith("plugin.video."):
        provider_id = instance._ADDON.getSettingInt("vpn_provider")

        if provider_id != 1:
            for i in range(1, 9):
                target = instance._ADDON.getSetting(f"map_{i}_addon")
                vpn_target = instance._ADDON.getSetting(f"vpn_{i}_name")
                if target and (target in folder or target == plugin):

                    v_clean = (
                        "" if not vpn_target else
                        vpn_target.lower().replace(' ', '').strip()
                    )
                    a_clean = (
                        "" if not active_now else
                        active_now.lower().replace(' ', '').strip()
                    )
                    if not active_now:
                        log_msg = f"Monitor: Connecting to profile: {vpn_target}"
                        log_message(log_msg, 0)
                        is_match = False
                    else:
                        is_match = (
                            (v_clean == a_clean)
                            or (v_clean in a_clean)
                            or (a_clean in v_clean)
                            or (v_clean.replace('_', '')
                                in a_clean.replace('_', ''))
                        )

                    if is_match:
                        match_found = True
                    else:
                        match_found = True
                        log_msg = f"Switching location map path to target: {vpn_target}."
                        log_message(log_msg, 1)

                        xbmcgui.Window(10000).setProperty('vpn_manual_session', 'false')
                        if os.path.exists('/tmp/vpn_manual_active.txt'):
                            try:
                                os.remove('/tmp/vpn_manual_active.txt')
                            except Exception:
                                pass

                        instance.vpn_ops.disconnect_vpn(silent=True)
                        time.sleep(0.5)

                        sid = instance.get_service_id_by_name(vpn_target)
                        if sid:
                            instance.vpn_ops.connect_vpn(str(vpn_target), str(sid))
                        else:
                            err_msg = (
                                "Monitor Error: Connection tracking target ID "
                                f"for profile {vpn_target} not found."
                            )
                            log_message(err_msg, 3)
                    break

    elif is_local_video_dir and active_now:
        match_found = True
        instance.cleanup_count = 0

    if not match_found and active_now and not is_manual:
        instance.cleanup_count += 1

        try:
            fresh_addon = xbmcaddon.Addon('service.wireguard.manager')
            user_timeout_sec = float(fresh_addon.getSettingInt("home_timeout_sec") or 5)
        except Exception:
            user_timeout_sec = 5.0

        elapsed_time_sec = instance.cleanup_count * (WATCHDOG_HEARTBEAT / 1000.0)

        if elapsed_time_sec >= user_timeout_sec:
            instance.cleanup_count = 0

            log_msg = (
                f"Home timeout ({user_timeout_sec}s) reached. "
                f"Disconnecting active profile [{active_now}]."
            )
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
