''' resources/lib/service_launcher.py '''
import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, sys, subprocess, time

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

import vpn_ops 
try:
    from vpn_config import WATCHDOG_HEARTBEAT
except ImportError:
    WATCHDOG_HEARTBEAT = 2000

class WGManagerService(xbmc.Monitor):
    def __init__(self, addon, vpn_ops_mod):
        super().__init__()
        self._ADDON = addon
        self.vpn_ops = vpn_ops_mod
        self.cleanup_count = 0
        
        time.sleep(2) 
        
        is_enabled = self._ADDON.getSetting('disconnect_on_start').lower() == 'true'
        xbmc.log(f"service.wireguard.manager: Startup Check [Enabled: {is_enabled}]", xbmc.LOGINFO)

        if is_enabled:
            try:
                out = subprocess.check_output(["connmanctl", "services"], text=True)
                if any("vpn_" in line and ("* " in line or "R " in line) for line in out.splitlines()):
                    xbmc.log("service.wireguard.manager: Startup cleanup. Force disconnecting VPN...", xbmc.LOGINFO)

                    xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
                    for p in ['/tmp/vpn_manual_active.txt', '/storage/.kodi/temp/vpn_manual_active.txt']:
                        if os.path.exists(p):
                            try: os.remove(p)
                            except: pass
                            
                    self.vpn_ops.disconnect_vpn(silent=True)
            except: pass

        xbmc.log("service.wireguard.manager: Monitor Service Initialized & Ready", xbmc.LOGINFO)

    def get_service_id_by_name(self, name):
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            for line in out.splitlines():
                if name in line: return line.split()[-1]
        except: return None

    def run_loop(self):
        active_now = self.vpn_ops.get_active_vpn()
        manual_prop = xbmcgui.Window(10000).getProperty('vpn_manual_session').lower() == 'true'
        is_manual = manual_prop or os.path.exists('/tmp/vpn_manual_active.txt') or os.path.exists('/storage/.kodi/temp/vpn_manual_active.txt')

        if xbmc.Player().isPlayingVideo(): 
            self.cleanup_count = 0
            return

        is_home = xbmc.getCondVisibility("Window.IsActive(home) | Window.IsActive(10000)")
        plugin = xbmc.getInfoLabel("Container.PluginName")
        folder = xbmc.getInfoLabel("Container.FolderPath")
        match_found = False

        if not is_home and plugin.startswith("plugin.video."):
            for i in range(1, 9):
                target = self._ADDON.getSetting(f"map_{i}_addon")
                vpn_target = self._ADDON.getSetting(f"vpn_{i}_name")
                
                if target and (target in folder or target == plugin):
                    match_found = True
                    
                    v_clean = vpn_target.replace('_', '').replace(' ', '').lower() if vpn_target else ""
                    a_clean = active_now.replace('_', '').replace(' ', '').lower() if active_now else ""
                    
                    if v_clean and a_clean != v_clean:
                        try:
                            xbmc.log(f"service.wireguard.manager: {target} match! Switching to {vpn_target}", xbmc.LOGINFO)

                            xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
                            for p in ['/tmp/vpn_manual_active.txt', '/storage/.kodi/temp/vpn_manual_active.txt']:
                                if os.path.exists(p):
                                    try: os.remove(p)
                                    except: pass
                            
                            self.vpn_ops.disconnect_vpn(silent=True)

                            sid = self.get_service_id_by_name(vpn_target)
                            if sid:
                                self.vpn_ops.connect_vpn(str(vpn_target), str(sid))
                            self.cleanup_count = 0
                            return 
                        except Exception as e:
                            xbmc.log(f"service.wireguard.manager: Mapping error: {e}", xbmc.LOGERROR)
                            return
                    
                    self.cleanup_count = 0
                    return 

        if not match_found:
            current_active = self.vpn_ops.get_active_vpn()
            
            if current_active:
                if is_manual:
                    self.cleanup_count = 0
                    return 

                self.cleanup_count += 1

                if self.cleanup_count >= 5:
                    try:
                        xbmc.log("service.wireguard.manager: Home timeout reached. Disconnecting.", xbmc.LOGINFO)
                        self.vpn_ops.disconnect_vpn(silent=False)
                        self.cleanup_count = 0
                    except: pass
        else:
            self.cleanup_count = 0

def start():
    monitor = WGManagerService(_ADDON, vpn_ops)
    while not monitor.abortRequested():
        monitor.run_loop()
        if monitor.waitForAbort(WATCHDOG_HEARTBEAT / 1000.0): break
