import xbmc, xbmcaddon, os, sys, subprocess

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
                if name in line:
                    return line.split()[-1]
        except Exception as e:
            log_message(f"Error fetching service ID for {name}: {e}", xbmc.LOGERROR)
        return None

    def run_loop(self):
        if xbmc.Player().isPlayingVideo():
            return

        folder = xbmc.getInfoLabel("Container.FolderPath")
        plugin = xbmc.getInfoLabel("Container.PluginName")

        trigger_display = "Home/Menu"
        if plugin:
            try:
                trigger_display = xbmcaddon.Addon(plugin).getAddonInfo('name')
            except:
                trigger_display = plugin

        raw_state = vpn_ops.get_active_vpn()
        active_now = None
        is_manual = False
        
        if raw_state and "|" in raw_state:
            active_now, mode = raw_state.split("|")
            is_manual = (mode == "manual")
        else:
            active_now = raw_state

        match_found = False
        for i in range(1, 6):
            target = ADDON.getSetting(f"map_{i}_addon")
            vpn = ADDON.getSetting(f"vpn_{i}_name")
            
            if target and vpn and (target in folder or target == plugin):
                match_found = True
                if active_now != vpn:
                    sid = self.get_service_id_by_name(vpn)
                    if sid:
                        log_message(f"Trigger: {trigger_display} matched mapping {i}. Connecting to {vpn}.", xbmc.LOGINFO)
                        vpn_ops.connect_vpn(vpn, sid, manual=False)
                break

        if not match_found and active_now and not is_manual:
            log_message(f"Auto-cleanup: Leaving {trigger_display}. Disconnecting {active_now}.", xbmc.LOGINFO)
            vpn_ops.disconnect_vpn()

if __name__ == '__main__':
    monitor = WGManagerService()
    log_message("Starting Service background loop...", xbmc.LOGINFO)
    
    try:
        while not monitor.abortRequested():
            monitor.run_loop()
            if monitor.waitForAbort(1):
                break
    except Exception as e:
        log_message(f"Fatal Service Error: {e}", xbmc.LOGERROR)
    finally:
        log_message("Service background loop stopped", xbmc.LOGINFO)
