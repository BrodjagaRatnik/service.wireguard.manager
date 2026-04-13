import xbmc, xbmcgui, xbmcaddon, os, sys, subprocess

ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = ADDON.getAddonInfo('path')
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
sys.path.append(LIB_PATH)

from logger import log_message
import vpn_ops

class WGManagerService(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        log_message("Monitor Service Initialized", xbmc.LOGINFO)

    def get_service_id_by_name(self, name):
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            for line in out.splitlines():
                if name in line: return line.split()[-1]
        except: return None

    def run_loop(self):
        if xbmc.Player().isPlayingVideo(): return

        is_manual = xbmcgui.Window(10000).getProperty('vpn_manual_session') == 'true'
        is_home = xbmc.getCondVisibility("Window.IsActive(home)")
        active_now = vpn_ops.get_active_vpn()

        if is_home and is_manual and active_now:
            return

        folder = xbmc.getInfoLabel("Container.FolderPath")
        plugin = xbmc.getInfoLabel("Container.PluginName")
        
        match_found = False
        if not is_home:
            for i in range(1, 6):
                target = ADDON.getSetting(f"map_{i}_addon")
                vpn = ADDON.getSetting(f"vpn_{i}_name")
                if target and vpn and (target in folder or target == plugin):
                    match_found = True
                    v_clean = vpn.replace('_', ' ').strip()
                    a_clean = active_now.replace('_', ' ').strip() if active_now else None
                    
                    if a_clean != v_clean:
                        log_message(f"Trigger: Mapping matched. Switching to {vpn}.")
                        xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
                        vpn_ops.disconnect_vpn(silent=True)
                        vpn_ops.connect_vpn(vpn, self.get_service_id_by_name(vpn))
                    break

        if not match_found and active_now and not is_manual:
            if is_home or (plugin and plugin != ""):
                log_message(f"Auto-cleanup: Leaving addon. Disconnecting {active_now}.")
                vpn_ops.disconnect_vpn(silent=False)

if __name__ == '__main__':
    monitor = WGManagerService()
    while not monitor.abortRequested():
        monitor.run_loop()
        if monitor.waitForAbort(1): break
