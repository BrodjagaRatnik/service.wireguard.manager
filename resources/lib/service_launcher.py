''' resources/lib/service_launcher.py '''
import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, sys, subprocess

def start():
    _ADDON = xbmcaddon.Addon('service.wireguard.manager')
    ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
    LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
    if LIB_PATH not in sys.path: sys.path.append(LIB_PATH)

    from vpn_config import WATCHDOG_HEARTBEAT
    import vpn_ops
    from logger import log_message 

    class WGManagerService(xbmc.Monitor):
        def __init__(self):
            super().__init__()
            self.cleanup_count = 0
            xbmcgui.Window(10000).setProperty('vpn_manual_session', '')

            for path in ['/tmp/vpn_manual_active.txt', '/storage/.kodi/temp/vpn_manual_active.txt']:
                if os.path.exists(path):
                    try: 
                        os.remove(path)
                        xbmc.log(f"service.wireguard.manager: Cleaned up old Safety Pin at {path}", xbmc.LOGDEBUG)
                    except: pass

            vpn_ops.disconnect_vpn(silent=True)
            log_message("Service Startup: Monitor Service Initialized", xbmc.LOGINFO)

        def get_service_id_by_name(self, name):
            try:
                out = subprocess.check_output(["connmanctl", "services"], text=True)
                for line in out.splitlines():
                    if name in line: return line.split()[-1]
            except: return None

        def run_loop(self):
            active_now = vpn_ops.get_active_vpn()
            manual_prop = xbmcgui.Window(10000).getProperty('vpn_manual_session').lower() == 'true'
            is_manual = manual_prop or os.path.exists('/tmp/vpn_manual_active.txt') or os.path.exists('/storage/.kodi/temp/vpn_manual_active.txt')

            if xbmc.Player().isPlayingVideo(): 
                self.cleanup_count = 0
                return

            is_home = xbmc.getCondVisibility("Window.IsActive(home) | Window.IsActive(10000)")
            plugin = xbmc.getInfoLabel("Container.PluginName")
            folder = xbmc.getInfoLabel("Container.FolderPath")

            match_found = plugin.startswith("plugin.video.") if plugin else False

            if not is_home and plugin:
                for i in range(1, 9):
                    target = _ADDON.getSetting(f"map_{i}_addon")
                    vpn = _ADDON.getSetting(f"vpn_{i}_name")
                    if target and (target in folder or target == plugin):
                        match_found = True
                        v_clean = vpn.replace('_', ' ').strip()
                        a_clean = active_now.replace('_', ' ').strip() if active_now else None
                        
                        if a_clean != v_clean:
                            log_message(f"Service Startup: {target} override, switching to {vpn}.", xbmc.LOGINFO)
                            xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
                            vpn_ops.disconnect_vpn(silent=True)
                            vpn_ops.connect_vpn(vpn, self.get_service_id_by_name(vpn))
                        return

            if not match_found and active_now:
                if is_manual:
                    self.cleanup_count = 0
                    return 

                if is_home:
                    log_message("Service Startup: Home detected. Disconnecting.", xbmc.LOGINFO)
                    vpn_ops.disconnect_vpn(silent=False)
                    self.cleanup_count = 0
                else:
                    self.cleanup_count += 1
                    if self.cleanup_count >= 5:
                        log_message("Service Startup: Outside mapping. Disconnecting.", xbmc.LOGINFO)
                        vpn_ops.disconnect_vpn(silent=False)
                        self.cleanup_count = 0

    monitor = WGManagerService()
    while not monitor.abortRequested():
        monitor.run_loop()
        if monitor.waitForAbort(WATCHDOG_HEARTBEAT / 1000.0): break
