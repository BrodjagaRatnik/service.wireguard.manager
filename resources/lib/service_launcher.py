''' ./resources/lib/service_launcher.py '''
import os
import sys
import xbmc
import xbmcaddon
import xbmcvfs
from logger import log_message
from vpn_config import PI5, WATCHDOG_HEARTBEAT
import vpn_ops
from service_updater import handle_settings_update
from service_resolver import resolve_service_id
from service_loop import execute_monitor_loop
from vpn_core import check_for_updates

try:
    from setup_helper import ensure_setup
except ImportError:
    from setup_utils import ensure_setup

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


class WGManagerService(xbmc.Monitor):

    def __init__(self, addon, vpn_ops_mod):
        super().__init__()
        self._ADDON = addon
        self.vpn_ops = vpn_ops_mod
        self.cleanup_count = 0

        hardware = "Raspberry Pi 5" if PI5 else "Raspberry Pi 4"
        log_message(f"Hardware timings loaded for {hardware}", 1)
        log_message("Monitor Service Initialized & Ready", 1)

    def onSettingsChanged(self):
        handle_settings_update(self._ADDON)

        try:
            addon_path = xbmcvfs.translatePath(self._ADDON.getAddonInfo('path'))
            media_path = os.path.join(addon_path, 'resources', 'media')
            check_for_updates(media_path)
        except Exception as e:
            log_message(f"Settings change validation error: {e}", 3)

    def get_service_id_by_name(self, name):
        return resolve_service_id(self._ADDON, name)

    def run_loop(self):
        execute_monitor_loop(self)


def start():
    addon = xbmcaddon.Addon('service.wireguard.manager')
    path = xbmcvfs.translatePath(addon.getAddonInfo('path'))

    if not addon.getSettingBool("first_run"):
        if ensure_setup(path, silent=True) is True:
            addon.setSettingBool("first_run", True)
            xbmc.executebuiltin('UpdateAddonByReadme()')

    try:
        monitor = WGManagerService(addon, vpn_ops)
    except Exception as e:
        log_message(f"CRITICAL: Monitor failed to start: {e}", 3)
        return

    try:
        is_enabled = addon.getSetting('disconnect_on_start').lower() == 'true'
        log_msg = f"Startup Cleaner: Verified configuration [Enabled: {is_enabled}]"
        log_message(log_msg, 0)

        if is_enabled:
            pre_active = monitor.vpn_ops.get_active_vpn()

            for f in ['/tmp/vpn_manager_active.txt', '/tmp/vpn_reconnect_count.txt']:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as e:
                        log_message(f"Cleanup error removing {f}: {e}", 3)

            with open('/tmp/vpn_intentional_disconnect.txt', 'w') as f:
                f.write('startup_clean')

            if pre_active:
                log_msg = f"Startup Cleaner: Actively disconnecting live tunnel profile: {pre_active}"
                log_message(log_msg, 1)
            else:
                log_message("Startup Cleaner: Disconnect instruction sent (No active tunnel connection found)", 0)

            monitor.vpn_ops.disconnect_vpn(silent=True)

    except Exception as e:
        log_message(f"Startup Cleaner Error: {e}", 3)

    try:
        hb = WATCHDOG_HEARTBEAT / 1000.0
    except Exception as e:
        log_message(f"Watchdog interval calculation failure: {e}", 3)
        hb = 1.0

    while not monitor.abortRequested():
        monitor.run_loop()
        if monitor.waitForAbort(hb):
            break


if __name__ == '__main__':
    start()
