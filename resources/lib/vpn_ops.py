import xbmc
import xbmcgui
import xbmcaddon
import subprocess
import time
import json
import os
from logger import log_message
from network_utils import set_secure_dns, disable_connman_ipv6, enable_connman_ipv6

ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_CON = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_connected.png')
ICON_DIS = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_disconnected.png')
STATE_FILE = "/tmp/vpn_manager_active.txt"

def set_active_vpn(name):
    try:
        if name:
            with open(STATE_FILE, "w") as f:
                f.write(name.strip())
        elif os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    except Exception as e:
        log_message(f"State Error: {e}")

def get_active_vpn():
    """Reads the current active VPN name from the state file."""
    state_path = "/tmp/vpn_manager_active.txt"
    
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                content = f.read().strip()
                return content if content else None
        except Exception as e:
            if 'log_message' in globals():
                log_message(f"State Read Error: {e}", xbmc.LOGDEBUG)
            return None
    return None

def get_default_gateway():
    """Dynamically finds the current system gateway."""
    try:
        out = subprocess.check_output(["ip", "-4", "route", "show", "default"], text=True)
        if "default" in out:
            parts = out.split()
            return parts[parts.index("via") + 1]
    except:
        pass
    return None

def disconnect_vpn(silent=False):
    xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
    
    log_message("Network: Cleaning up VPN and restoring defaults", xbmc.LOGINFO)

    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():
            if "vpn_" in line and ("* " in line or "R " in line):
                subprocess.run(["connmanctl", "disconnect", line.split()[-1]], check=False)

        route_out = subprocess.check_output(["route", "-n"], text=True)
        for line in route_out.splitlines():
            if " UGH " in line or " H " in line:
                parts = line.split()
                if parts:
                    subprocess.run(["route", "del", "-host", parts[0]], check=False)

        gw = get_default_gateway()
        if gw:
            subprocess.run(["route", "add", "default", "gw", gw], check=False)
            subprocess.run(["ip", "route", "flush", "cache"], check=False)
            log_message(f"Network: Gateway restored via {gw}")
        else:
            log_message("Network: Gateway missing. Watchdog will restore from memory.", xbmc.LOGWARNING)

    except Exception as e:
        log_message(f"Disconnect Error: {e}", xbmc.LOGERROR)

    enable_connman_ipv6()
    set_secure_dns(vpn_active=False)
    set_active_vpn(None)
    
    if not silent:
        icon = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_disconnected.png')
        xbmcgui.Dialog().notification("Network", "VPN Disconnected", icon, 3000)

def connect_vpn(vpn_name, sid):
    raw_state = get_active_vpn()
    active_clean = raw_state.replace('_', ' ').strip() if raw_state else None
    target_clean = vpn_name.replace('_', ' ').strip()
    
    if active_clean == target_clean:
        return True

    log_message(f"Action: Connecting to {vpn_name}", xbmc.LOGINFO)
    disable_connman_ipv6()
    
    pbg = xbmcgui.DialogProgressBG()
    pbg.create("VPN Manager", f"Connecting to {vpn_name}...")
    subprocess.run(["connmanctl", "connect", sid], check=False)
    
    connected = False
    for i in range(1, 16):
        pbg.update(int(i * 6.6), message=f"Verifying... ({i}s)")
        xbmc.sleep(1000)
        try:
            check = subprocess.check_output(["connmanctl", "services"], text=True)
            if any(sid in line and ("* R" in line or "* O" in line) for line in check.splitlines()):
                route_check = subprocess.check_output(["ip", "route"], text=True)
                if "wg0" in route_check:
                    connected = True
                    break
        except: pass
    pbg.close()

    if connected:
        set_active_vpn(target_clean)
        set_secure_dns(vpn_name, vpn_active=True)
        xbmc.sleep(2000) 
        try:
            res = subprocess.check_output(["curl", "-s", "--max-time", "5", "https://ipinfo.io"], text=True)
            data = json.loads(res)
            ip = data.get("ip", "Unknown")
            country = data.get("country", "??")
            msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}\nIP: [COLOR yellow]{ip}[/COLOR] ({country})"
        except:
            msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}"
            
        xbmcgui.Dialog().notification("VPN Secured", msg, ICON_CON, 2500)
        return True
    
    error_icon = os.path.join(ADDON_PATH, 'resources', 'media', 'error.png')
    xbmcgui.Dialog().notification("VPN Error", "Tunnel failed to initialize", error_icon, 5000)
    disconnect_vpn(silent=True)
    return False
