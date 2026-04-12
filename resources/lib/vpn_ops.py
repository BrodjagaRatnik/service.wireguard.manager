import xbmc, xbmcgui, subprocess, time, json, os, xbmcaddon
from logger import log_message
from network_utils import set_secure_dns, disable_connman_ipv6, enable_connman_ipv6

ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_CON = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_connected.png')
ICON_DIS = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_disconnected.png')
STATE_FILE = "/tmp/vpn_manager_active.txt"

def get_active_vpn():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return f.read().strip()
        except: pass
    return None

def set_active_vpn(name, manual=False):
    try:
        if name:
            mode = "manual" if manual else "auto"
            with open(STATE_FILE, "w") as f:
                f.write(f"{name}|{mode}")
        elif os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    except: pass

def disconnect_vpn():
    log_message("Action: Disconnecting all VPN services", xbmc.LOGINFO)
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():
            if "vpn_" in line and ("* R" in line or "* O" in line):
                sid = line.split()[-1]
                subprocess.run(["connmanctl", "disconnect", sid], check=False)
    except: pass

    subprocess.run(["ifconfig", "eth0", "metric", "1"], check=False)
    subprocess.run(["connmanctl", "enable", "wifi"], check=False)
    enable_connman_ipv6()
    set_secure_dns(vpn_active=False)
    subprocess.run(["ip", "route", "flush", "cache"], check=False)
    
    xbmcgui.Dialog().notification("Network", "VPN Disconnected", ICON_DIS, 3000)
    set_active_vpn(None)

def connect_vpn(vpn_name, sid, manual=False):
    raw_state = get_active_vpn()
    active_name = raw_state.split('|')[0] if raw_state and '|' in raw_state else raw_state
    
    if active_name == vpn_name: return True
    if active_name: disconnect_vpn()

    log_message(f"Action: Connecting to {vpn_name} (Mode: {'Manual' if manual else 'Auto'})", xbmc.LOGINFO)
    disable_connman_ipv6()
    
    pbg = xbmcgui.DialogProgressBG()
    pbg.create("VPN Manager", f"Connecting to {vpn_name}...")
    subprocess.run(["connmanctl", "connect", sid])
    
    connected = False
    for i in range(1, 11):
        pbg.update(i * 10, message=f"Verifying... ({i}s)")
        xbmc.sleep(1000)
        check = subprocess.check_output(["connmanctl", "services"], text=True)
        if any(sid in line and ("* R" in line or "* O" in line) for line in check.splitlines()):
            connected = True
            break
    pbg.close()

    if connected:
        set_active_vpn(vpn_name, manual=manual)
        set_secure_dns(vpn_name, vpn_active=True)
        try:
            res = subprocess.check_output(["curl", "-s", "--max-time", "3", "https://ipinfo.io"], text=True)
            data = json.loads(res)
            ip, country = data.get("ip", "Unknown"), data.get("country", "??")
            msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}\nIP: [COLOR yellow]{ip}[/COLOR] ({country})"
        except:
            msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}"
        
        xbmcgui.Dialog().notification("VPN Status", msg, ICON_CON, 4000)
        return True
    return False
