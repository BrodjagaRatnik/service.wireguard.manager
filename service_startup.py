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

def disable_connman_ipv6():
    """Forces IPv6 off for all physical interfaces."""
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                subprocess.run(["connmanctl", "config", service_id, "--ipv6", "off"], check=False)
        return True
    except Exception as e:
        xbmc.log(f"WG_MANAGER: IPv6 Disable Error: {e}", xbmc.LOGERROR)
    return False

def enable_connman_ipv6():
    """Restores IPv6 to auto mode for physical interfaces."""
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                subprocess.run(["connmanctl", "config", service_id, "--ipv6", "auto"], check=False)
    except: pass

class WGManagerService(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.active_vpn_name = None
        self.icon_con = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_connected.png')
        self.icon_dis = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_disconnected.png')
        xbmc.log("[service.wireguard.manager] Monitor Service Initialized", xbmc.LOGINFO)

    def get_service_id_by_name(self, name):
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            for line in out.splitlines():
                if name in line:
                    return line.split()[-1]
        except: return None

    def manage_vpn(self, vpn_name):
        if self.active_vpn_name == vpn_name: return

        if self.active_vpn_name:
            xbmc.log(f"WG_MANAGER: Disconnecting {self.active_vpn_name}", xbmc.LOGINFO)
            old_id = self.get_service_id_by_name(self.active_vpn_name)
            if old_id: subprocess.run(["connmanctl", "disconnect", old_id])
            subprocess.run(["ifconfig", "eth0", "metric", "1"], check=False)
            subprocess.run(["connmanctl", "enable", "wifi"], check=False)
            enable_connman_ipv6()
            subprocess.run(["ip", "route", "flush", "cache"], check=False)
            xbmcgui.Dialog().notification("Network", "VPN Disconnected", self.icon_dis, 3000)
            self.active_vpn_name = None

        if vpn_name:
            current_id = self.get_service_id_by_name(vpn_name)
            if not current_id: return
            
            disable_connman_ipv6()

            try:
                status = subprocess.check_output(["connmanctl", "state"], text=True)
                if "ethernet" in status.lower():
                    subprocess.run(["connmanctl", "disable", "wifi"], check=False)
                    subprocess.run(["ifconfig", "eth0", "metric", "100"], check=False)
                    time.sleep(1)
            except: pass

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
                ip = "Unknown"
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
        while not self.abortRequested():
            if xbmc.Player().isPlaying():
                if self.waitForAbort(5): break
                continue
            
            folder = xbmc.getInfoLabel("Container.FolderPath")
            plugin = xbmc.getInfoLabel("Container.PluginName")
            match = False
            
            for i in range(1, 6):
                target = ADDON.getSetting(f"map_{i}_addon")
                vpn = ADDON.getSetting(f"vpn_{i}_name")
                if target and vpn and (target in folder or target == plugin):
                    self.manage_vpn(vpn)
                    match = True
                    break
            
            if not match and self.active_vpn_name: self.manage_vpn(None)
            if self.waitForAbort(2): break

if __name__ == '__main__':
    service = WGManagerService()
    service.run_loop()
