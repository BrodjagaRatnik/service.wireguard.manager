""" ./resources/lib/service_launcher.py """
import kodi_env
import os
import time
import threading
from logger import log_message
from vpn_config import PI2, PI3, PI4, PI5, COLD_BOOT_CONNECT_DELAY, WATCHDOG_HEARTBEAT
import vpn_ops
from service_updater import handle_settings_update
from service_resolver import resolve_service_id
from service_loop import execute_monitor_loop
from vpn_core import check_for_updates
from wm_utils import flush_connman_sockets
from vpn_utils import is_interface_active
from tunnel_checker import run_tunnel_sanity_check
from state_manager import get_file_path
import dialog

try:
    import xbmc
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
            self.last_bg_check_time = time.time()
            self.last_socket_flush_time = 0
            self.cleanup_count = 0
            self.last_tunnel_check_time = time.time()
            self.blackout_gate_logged = False

            if PI5:
                hardware = "Raspberry Pi 5"
            elif PI4:
                hardware = "Raspberry Pi 4"
            elif PI3:
                hardware = "Raspberry Pi 3"
            elif PI2:
                hardware = "Raspberry Pi 2"
            else:
                hardware = "Generic Device"

            log_message(f"Service Launcher: Hardware timings loaded for {hardware}", 1)
            log_message("Service Launcher: Monitor Service Initialized & Ready", 1)

        def onSettingsChanged(self):
            handle_settings_update(self._ADDON)

            try:
                from wm_utils import encrypt_setting_to_base64
                encrypt_setting_to_base64("pia_pass")
                encrypt_setting_to_base64("account_number")

            except Exception as e:
                log_err = f"Service Launcher: Settings encryption helper unavailable: {e}"
                log_message(log_err, 2)

        def get_service_id_by_name(self, name):
            return resolve_service_id(self._ADDON, name)

        def run_loop(self):
            blackout_path = get_file_path("blackout")
            if blackout_path is not None and os.path.exists(blackout_path) is True:
                if self.blackout_gate_logged is False:
                    log_message("Service Launcher: Blackout lock present. Pausing monitor loop.", 1)
                    self.blackout_gate_logged = True
                return
            if self.blackout_gate_logged is True:
                log_message("Service Launcher: Blackout cleared. Resuming monitor loop.", 1)
                self.blackout_gate_logged = False

            execute_monitor_loop(self)
            current_time = time.time()
            addon_path = kodi_env.ADDON_DIR
            media_path = os.path.join(addon_path, "resources", "media")

            if (current_time - getattr(self, "last_socket_flush_time", 0.0)) >= 60.0:
                self.last_socket_flush_time = current_time
                try:
                    flush_connman_sockets()
                except Exception as e:
                    log_message(f"Service Launcher: Failed to run socket garbage collector: {e}", 3)

            if (current_time - self.last_bg_check_time) >= 1800.0:
                self.last_bg_check_time = current_time

                if is_interface_active("wg0"):
                    log_message("Service Launcher: Tunnel is active. Deferring update to tunnel sanity check.", 0)
                else:
                    try:
                        log_message("Service Launcher: No active tunnel. Executing scheduled update.", 0)
                        check_for_updates(media_path)
                    except Exception as e:
                        log_err = f"Service Launcher: Update verification failure: {e}"
                        log_message(log_err, 3)

            if (current_time - self.last_tunnel_check_time) >= 300.0:
                self.last_tunnel_check_time = current_time
                if self._ADDON.getSettingBool("check_tunnel"):
                    try:
                        threading.Thread(target=run_tunnel_sanity_check, daemon=True).start()
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
    service_started_at = time.monotonic()

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
    state_file = get_file_path("active")

    if state_file is not None and os.path.exists(state_file) is True:
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
                dialog.notify_tunnel_restored(boot_target, country if ip and ip != "Unknown" else None)
                log_message(f"Service Launcher: Profile [{boot_target}] connected safely. Tunnel restored after restart", 1)
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
                elapsed_ms = (time.monotonic() - service_started_at) * 1000.0
                remaining_ms = COLD_BOOT_CONNECT_DELAY - elapsed_ms
                gate_aborted = False
                if remaining_ms > 0:
                    gate_log = f"Service Launcher: Cold boot connect gate holding for {remaining_ms:.0f} ms."
                    log_message(gate_log, 0)
                    gate_aborted = monitor.waitForAbort(remaining_ms / 1000.0)
                    if gate_aborted:
                        log_message("Service Launcher: Abort during connect gate. Skipping cold boot connect.", 2)

                if gate_aborted is False:
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
                            vpn_ops.connect_vpn(str(boot_target), str(sid), silent=True)
                            log_msg = f"Service Launcher: Connecting profile [{boot_target}] safely after cold boot."
                            log_message(log_msg, 1)
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
