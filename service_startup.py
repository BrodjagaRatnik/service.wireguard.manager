import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, sys, subprocess, time

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
if LIB_PATH not in sys.path: sys.path.append(LIB_PATH)

from vpn_config import *
from logger import log_message as original_log_message
import vpn_ops

def log_message(msg, level=xbmc.LOGINFO):
    original_log_message(msg, level)

class WGManagerService(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        vpn_ops.disconnect_vpn(silent=True)
        log_message("Monitor Service Initialized", xbmc.LOGINFO)

    def get_service_id_by_name(self, name):
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            for line in out.splitlines():
                if name in line: return line.split()[-1]
        except: return None

    def run_loop(self):
        active_now = vpn_ops.get_active_vpn()
        is_manual = xbmcgui.Window(10000).getProperty('vpn_manual_session') == 'true'

        if xbmc.Player().isPlayingVideo(): return

        is_home = xbmc.getCondVisibility("Window.IsActive(home) | Window.IsActive(10000)")
        plugin = xbmc.getInfoLabel("Container.PluginName")
        folder = xbmc.getInfoLabel("Container.FolderPath")

        match_found = False
        if not is_home and plugin:
            log_message(f"Monitor: Checking triggers. VPN: {active_now} | Plugin: {plugin}", xbmc.LOGDEBUG)
            for i in range(1, 6):
                target = _ADDON.getSetting(f"map_{i}_addon")
                vpn = _ADDON.getSetting(f"vpn_{i}_name")
                if target and (target in folder or target == plugin):
                    match_found = True
                    v_clean = vpn.replace('_', ' ').strip()
                    a_clean = active_now.replace('_', ' ').strip() if active_now else None
                    
                    if a_clean != v_clean:
                        log_message(f"Trigger: Match found for {target}. Switching to {vpn}.")

                        xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
                        vpn_ops.disconnect_vpn(silent=True)
                        vpn_ops.connect_vpn(vpn, self.get_service_id_by_name(vpn))
                    return

        if not match_found and active_now and not is_manual:
             if is_home or not plugin:
                 log_message("Auto-cleanup: Home detected. Disconnecting.")
                 vpn_ops.disconnect_vpn(silent=False)
             else:
                 if self.waitForAbort(3): return 
                 still_plugin = xbmc.getInfoLabel("Container.PluginName")
                 still_folder = xbmc.getInfoLabel("Container.FolderPath")
                 still_outside = True
                 for j in range(1, 6):
                     t = _ADDON.getSetting(f"map_{j}_addon")
                     if t and (t in still_folder or t == still_plugin):
                         still_outside = False
                         break
                 if still_outside:
                     log_message(f"Auto-cleanup: Outside mapping. Disconnecting.")
                     vpn_ops.disconnect_vpn(silent=False)

if __name__ == '__main__':
    monitor = WGManagerService()
    while not monitor.abortRequested():
        monitor.run_loop()
        if monitor.waitForAbort(WATCHDOG_HEARTBEAT / 1000.0): break
