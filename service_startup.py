import xbmc
import xbmcaddon
import os
import sys
import subprocess
import xbmcgui
import time
import json

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
sys.path.append(LIB_PATH)

from vpn_core import install_service, check_for_updates
from setup_helper import ensure_setup

class WGManagerService(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.active_vpn_name = None
        self.icon_con = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_connected.png')
        self.icon_dis = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_disconnected.png')
        xbmc.log("[service.wireguard.manager] Monitor Service Initialized", xbmc.LOGINFO)

    def get_service_id_by_name(self, name):
        """Finds the real vpn_xxx ID by matching the Friendly Name label."""
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            for line in out.splitlines():
                if name in line:
                    parts = line.split()
                    real_id = parts[-1] 
                    if real_id.startswith("vpn_"):
                        return real_id
        except Exception as e:
            xbmc.log(f"WG_MANAGER: Lookup error: {e}", xbmc.LOGERROR)
        return None

    def set_wifi(self, state):
        cmd = "enable" if state else "disable"
        try:
            subprocess.run(["connmanctl", cmd, "wifi"], check=False)
            xbmc.log(f"WG_MANAGER: Wi-Fi {cmd}d", xbmc.LOGINFO)
        except:
            pass

    def is_eth_connected(self):
        try:
            status = subprocess.check_output(["connmanctl", "state"], text=True)
            return "ethernet" in status.lower()
        except:
            return False

    def manage_vpn(self, vpn_name):
        if self.active_vpn_name == vpn_name:
            return

        import json

        if self.active_vpn_name:
            xbmc.log(f"WG_MANAGER: Disconnecting {self.active_vpn_name}", xbmc.LOGINFO)
            old_id = self.get_service_id_by_name(self.active_vpn_name)
            if old_id:
                subprocess.run(["connmanctl", "disconnect", old_id])

            subprocess.run(["ifconfig", "eth0", "metric", "1"], check=False)
            self.set_wifi(True) 
            xbmcgui.Dialog().notification("Network", "VPN Disconnected", self.icon_dis, 3000)
            self.active_vpn_name = None

        if vpn_name:
            current_id = self.get_service_id_by_name(vpn_name)
            if not current_id:
                return

            if self.is_eth_connected():
                self.set_wifi(False)
                subprocess.run(["ifconfig", "eth0", "metric", "100"], check=False)
                time.sleep(1)

            pbg = xbmcgui.DialogProgressBG()
            pbg.create("VPN Manager", f"Connecting to {vpn_name}...")
            
            subprocess.run(["connmanctl", "connect", current_id])
            
            connected = False
            for i in range(1, 11):
                pbg.update(i * 10, message=f"Verifying... ({i}s)")
                xbmc.sleep(1000)
                check = subprocess.check_output(["connmanctl", "services"], text=True)
                if any(current_id in line and ("* R" in line or "* O" in line) for line in check.splitlines()):
                    connected = True
                    break
            pbg.close()

            if connected:
                self.active_vpn_name = vpn_name
                try:
                    res = subprocess.check_output(["curl", "-s", "https://ipinfo.io"], timeout=5, text=True)
                    data = json.loads(res)
                    ip = data.get("ip", "Unknown")
                    msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}\nIP: [COLOR yellow]{ip}[/COLOR]"
                except:
                    msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}"
                
                xbmcgui.Dialog().notification("VPN Status", msg, self.icon_con, 4000)
            else:
                xbmcgui.Dialog().notification("VPN Error", "Connection Timed Out", "", 5000)

    def run_loop(self):
        MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
        SERVICE_NAME = "vpn-watchdog.service"
        SOURCE_SERVICE = os.path.join(ADDON_PATH, 'resources', 'data', SERVICE_NAME)
        DEST_SERVICE = '/storage/.config/system.d/' + SERVICE_NAME

        try:
            ensure_setup(ADDON_PATH, MEDIA_PATH)
            install_service(SOURCE_SERVICE, DEST_SERVICE, SERVICE_NAME, MEDIA_PATH)
            check_for_updates(MEDIA_PATH)
        except Exception as e:
            xbmc.log(f"[service.wireguard.manager] Startup Error: {e}", xbmc.LOGERROR)

        while not self.abortRequested():
            if xbmc.Player().isPlaying():
                if self.waitForAbort(5): break
                continue

            current_path = xbmc.getInfoLabel("Container.FolderPath")
            found_match = False

            for i in range(1, 6):
                target_addon = ADDON.getSetting(f"map_{i}_addon")
                vpn_friendly_name = ADDON.getSetting(f"vpn_{i}_name")
                
                if target_addon and vpn_friendly_name and target_addon in current_path:
                    self.manage_vpn(vpn_friendly_name)
                    found_match = True
                    break

            if not found_match and self.active_vpn_name:
                self.manage_vpn(None)

            if self.waitForAbort(2): 
                break

if __name__ == '__main__':
    service = WGManagerService()
    service.run_loop()
