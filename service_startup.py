import xbmc, xbmcaddon, os, sys, subprocess, xbmcgui, time, json

ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = ADDON.getAddonInfo('path')
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
sys.path.append(LIB_PATH)

from network_utils import set_secure_dns, disable_connman_ipv6, enable_connman_ipv6
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
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            for line in out.splitlines():
                if name in line: return line.split()[-1]
        except: return None

    def manage_vpn(self, vpn_name):
        if self.active_vpn_name == vpn_name: return

        if self.active_vpn_name:
            old_id = self.get_service_id_by_name(self.active_vpn_name)
            if old_id: subprocess.run(["connmanctl", "disconnect", old_id])
            subprocess.run(["ifconfig", "eth0", "metric", "1"], check=False)
            subprocess.run(["connmanctl", "enable", "wifi"], check=False)
            enable_connman_ipv6()
            set_secure_dns(vpn_active=False) # RESET DNS
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
                set_secure_dns(vpn_name, vpn_active=True) # SECURE DNS
                try:
                    res = subprocess.check_output(["curl", "-s", "https://ipinfo.io"], timeout=5, text=True)
                    ip = json.loads(res).get("ip", "Unknown")
                    msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}\nIP: [COLOR yellow]{ip}[/COLOR]"
                except:
                    msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}"
                xbmcgui.Dialog().notification("VPN Status", msg, self.icon_con, 4000)
            else:
                xbmcgui.Dialog().notification("VPN Error", "Connection Timed Out", "", 5000)

    def run_loop(self):
        if xbmc.Player().isPlayingVideo():
            return

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

        if not match and self.active_vpn_name: 
            self.manage_vpn(None)

if __name__ == '__main__':
    monitor = WGManagerService()
    while not monitor.abortRequested():
        monitor.run_loop()
        if monitor.waitForAbort(1):
            break
