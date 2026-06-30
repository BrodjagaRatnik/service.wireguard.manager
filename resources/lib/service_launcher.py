""" ./resources/lib/service_launcher.py """
import kodi_env
import os
import time
from logger import log_message
from vpn_config import PI4, PI5, WATCHDOG_HEARTBEAT, CONNMAN_SYSTEM_CHECK_INTERVAL
import vpn_ops
from service_updater import handle_settings_update
from service_resolver import resolve_service_id
from service_loop import execute_monitor_loop
from vpn_core import check_for_updates
from wm_utils import check_system_interval

try:
    import xbmc
    import xbmcgui
    import subprocess
    HAS_KODI_MONITOR = True
except ImportError:
    HAS_KODI_MONITOR = False

try:
    from setup_helper import ensure_setup
except ImportError:
    from setup_utils import ensure_setup

if HAS_KODI_MONITOR:

    class WGManagerService(xbmc.Monitor):

        def __init__(self, addon, vpn_ops_mod):
            super().__init__()
            self._ADDON = addon
            self.vpn_ops = vpn_ops_mod
            self.cleanup_count = 0
            self.last_connman_check_time = 0
            self.last_bg_check_time = time.time()

            if PI5:
                hardware = "Raspberry Pi 5"
            elif PI4:
                hardware = "Raspberry Pi 4"
            else:
                hardware = "Generic Device"

            log_message(f"Service Launcher: Hardware timings loaded for {hardware}", 1)
            log_message("Service Launcher: Monitor Service Initialized & Ready", 1)

        def onSettingsChanged(self):
            handle_settings_update(self._ADDON)

            try:
                from vpn_utils import encrypt_setting_to_base64
                encrypt_setting_to_base64("pia_pass")
            except ImportError:
                try:
                    from wm_utils import encrypt_setting_to_base64
                    encrypt_setting_to_base64("pia_pass")
                except Exception as e:
                    log_err = f"Service Launcher: Settings encryption helper unavailable: {e}"
                    log_message(log_err, 2)

        def get_service_id_by_name(self, name):
            return resolve_service_id(self._ADDON, name)

        def run_loop(self):
            execute_monitor_loop(self)
            current_time = time.time()
            addon_path = kodi_env.ADDON_DIR
            media_path = os.path.join(addon_path, "resources", "media")

            if (current_time - self.last_connman_check_time) >= CONNMAN_SYSTEM_CHECK_INTERVAL:
                self.last_connman_check_time = current_time
                try:
                    check_system_interval(media_path)
                except Exception as e:
                    log_err = f"Service Launcher: Network health verification failure: {e}"
                    log_message(log_err, 3)

            if (current_time - self.last_bg_check_time) >= 1800.0:
                self.last_bg_check_time = current_time
                try:
                    check_for_updates(media_path)
                except Exception as e:
                    log_err = f"Service Launcher: Update verification failure: {e}"
                    log_message(log_err, 3)

                if self._ADDON.getSettingBool("check_tunnel"):
                    try:
                        from tunnel_checker import run_tunnel_sanity_check
                        run_tunnel_sanity_check()
                    except Exception as e:
                        log_err = f"Service Launcher: Tunnel health tracking exception: {e}"
                        log_message(log_err, 3)


def start():
    addon_obj = kodi_env.get_addon_instance()
    if not addon_obj or not HAS_KODI_MONITOR:
        log_message("Service Launcher: Abstractions missing. Background monitoring disabled.", 2)
        kodi_env.clear_script_globals()
        return

    path = kodi_env.ADDON_DIR

    if addon_obj.getSettingBool("first_run") is False:
        if ensure_setup(path, silent=True) is True:
            addon_obj.setSettingBool("first_run", True)
            xbmc.executebuiltin("Container.Refresh")

    try:
        monitor = WGManagerService(addon_obj, vpn_ops)
    except Exception as e:
        log_message(f"Service Launcher: Monitor failed to start: {e}", 3)
        return

    disconnect_on_start = addon_obj.getSettingBool("disconnect_on_start")

    boot_target = None
    state_file = '/storage/.kodi/userdata/addon_data/service.wireguard.manager/vpn_manager_active.txt'

    if os.path.exists(state_file) is True:
        try:
            with open(state_file, 'r') as f:
                boot_target = f.read().strip() or None
            if boot_target:
                log_message(f"Service Launcher: Discovered active file target: {boot_target}", 0)
        except Exception:
            boot_target = None

    if disconnect_on_start is True:
        log_message("Service Launcher: disconnect_on_start is Enabled. Flushing active state files.", 0)
        from state_manager import clear_startup_states, write_state
        clear_startup_states()
        write_state('disconnect', 'startup_clean')
        if boot_target:
            log_message(f"Service Launcher: Actively purging live tunnel connection: {boot_target}", 1)
            monitor.vpn_ops.disconnect_vpn(silent=True, flush_dns=True)
            boot_target = None

    if not boot_target:
        log_message("Service Launcher: No active VPN in profile storage. Keeping interface clean.", 0)
    else:
        if os.path.exists('/sys/class/net/wg0') is True:
            try:
                from vpn_utils import fetch_vpn_metadata
                ip, country = fetch_vpn_metadata()
                title = "[B][COLOR FF00FFFF]▄■ [ SYSTEM RESTARTED ] ■▄[/COLOR][/B]"
                icon_path = os.path.join(path, 'resources', 'media', 'icon.png')
                if ip and ip != "Unknown":
                    msg = (
                        f" [B]═≡═ [COLOR FFFFFF00]Tunnel Restored"
                        f"[/COLOR] ═≡═[/B]\n[B]Profile "
                        f"[COLOR FF32CD32]{boot_target}[/COLOR] • ({country})[/B]"
                    )
                else:
                    msg = (
                        f" [B]═≡═ [COLOR FFFFFF00]Tunnel Restored"
                        f"[/COLOR] ═≡═[/B]\n[B]Profile "
                        f"[COLOR FF32CD32]{boot_target}[/COLOR][/B]"
                    )
                dialog = xbmcgui.Dialog()
                dialog.notification(title, msg, icon_path, 4500)
            except Exception:
                pass
        else:
            log_message("Service Launcher: Cold boot detected. Initiating link verification...", 1)
            network_ready = False
            for attempt in range(10):
                try:
                    res = subprocess.run(
                        ["ping", "-c", "1", "-W", "1", "1.1.1.1"],
                        capture_output=True, check=False
                    )
                    if res.returncode == 0:
                        network_ready = True
                        break
                except Exception:
                    pass
                time.sleep(1.0)

            if network_ready is True:
                sid = None
                try:
                    connman_clean_name = boot_target.replace(' ', '_')
                    sid = resolve_service_id(addon_obj, connman_clean_name)
                    if not sid:
                        sid = resolve_service_id(addon_obj, boot_target)
                except Exception:
                    pass

                if sid:
                    try:
                        log_message(f"Service Launcher: Connecting profile [{boot_target}] safely.", 1)
                        vpn_ops.connect_vpn(str(boot_target), str(sid), silent=True)
                    except Exception:
                        pass
                else:
                    log_message(f"Service Launcher: Service ID lookup dropped for {boot_target}", 3)
            else:
                log_message("Service Launcher: Verification loop aborted. Network target down.", 3)

    try:
        hb = WATCHDOG_HEARTBEAT / 1000.0
    except Exception:
        hb = 1.0

    try:
        while monitor.abortRequested() is False:
            monitor.run_loop()
            if monitor.waitForAbort(hb) is True:
                break
    finally:
        del monitor
        global _ADDON_INSTANCE
        _ADDON_INSTANCE = None
        import gc
        gc.collect()


if __name__ == '__main__':
    start()
