import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, sys, subprocess, time

ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

from logger import log_message

def is_libreelec():
    try:
        with open('/etc/os-release', 'r') as f:
            return "LibreELEC" in f.read()
    except:
        return False

if not is_libreelec():
    msg = "This addon is designed for LibreELEC only."
    log_message(msg, xbmc.LOGERROR)
    xbmcgui.Dialog().ok("Unsupported OS", msg)
    sys.exit()
else:
    log_message("LibreELEC detected. Continuing startup...", xbmc.LOGINFO)

import vpn_ops
from setup_helper import ensure_setup

class WGManagerService(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.internet_alert_sent = False
        
        log_message("Monitor: Startup reset initiated...", xbmc.LOGINFO)
        ''' silent=False shows the notification, silent=True hides it. '''
        vpn_ops.disconnect_vpn(silent=True)
        self.waitForAbort(2)
        log_message("Monitor Service Initialized", xbmc.LOGINFO)

    def get_service_id_by_name(self, name):
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            for line in out.splitlines():
                if name in line: return line.split()[-1]
        except: return None

    def run_loop(self):
        if xbmc.Player().isPlayingVideo(): 
            return

        is_home = xbmc.getCondVisibility("Window.IsActive(home) | Window.IsActive(10000)")
        folder = xbmc.getInfoLabel("Container.FolderPath")
        plugin = xbmc.getInfoLabel("Container.PluginName")
        active_now = vpn_ops.get_active_vpn()
        is_manual = xbmcgui.Window(10000).getProperty('vpn_manual_session') == 'true'
        
        if (is_home or not plugin) and active_now and not is_manual:
             log_message("Auto-cleanup: Home detected. Disconnecting.")
             vpn_ops.disconnect_vpn(silent=False)
             return

        match_found = False
        if not is_home: 
            log_message(f"Monitor: Checking triggers. VPN: {active_now} | Plugin: {plugin}", xbmc.LOGDEBUG)

            for i in range(1, 6):
                target = ADDON.getSetting(f"map_{i}_addon")
                vpn = ADDON.getSetting(f"vpn_{i}_name")
                
                if target:
                    log_message(f"Trigger Debug: Checking {target}", xbmc.LOGDEBUG)
                    
                    if vpn and (target in folder or target == plugin):
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

            if self.waitForAbort(3): return 
            

            still_folder = xbmc.getInfoLabel("Container.FolderPath")
            still_plugin = xbmc.getInfoLabel("Container.PluginName")
            still_outside = True
            
            for j in range(1, 6):
                t = ADDON.getSetting(f"map_{j}_addon")
                if t and (t in still_folder or t == still_plugin):
                    still_outside = False
                    break
            
            if still_outside:
                log_message(f"Auto-cleanup: No mapping match found. Disconnecting {active_now}.")
                vpn_ops.disconnect_vpn(silent=False)

if __name__ == '__main__':
    MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
    try:
        was_updated = ensure_setup(ADDON_PATH, MEDIA_PATH)

        if was_updated is True:
            icon = os.path.join(MEDIA_PATH, 'icon.png')
            xbmcgui.Dialog().notification(
                "WireGuard Manager", 
                "System files initialized successfully", 
                icon, 
                3000, 
                False
            )
            log_message("Service Setup: First-run installation completed.", xbmc.LOGINFO)
        else:
            log_message("Service Setup: Files already verified.", xbmc.LOGINFO)
        
    except Exception as e:
        log_message(f"Service Setup Error: {e}", xbmc.LOGERROR)

    monitor = WGManagerService()
    while not monitor.abortRequested():
        monitor.run_loop()
        if monitor.waitForAbort(5):
            break
