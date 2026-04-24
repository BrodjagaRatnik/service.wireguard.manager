''' ./resources/lib/vpn_ops.py '''
import subprocess, time, json, os, sys

try:
    import xbmc, xbmcgui, xbmcaddon
    KODI_AVAILABLE = True
except ImportError:
    KODI_AVAILABLE = False

ADDON_ID = 'service.wireguard.manager'
STATE_FILE = "/tmp/vpn_manager_active.txt"
INTENTIONAL_DISCONNECT_FILE = "/tmp/vpn_intentional_disconnect.txt"

try:
    from vpn_config import *
except ImportError:
    PROP_SYNC_DELAY, OS_RELEASE_DELAY = 100, 1000
    CONN_POLL_INTERVAL, ROUTE_PROP_DELAY = 300, 200
    DHCP_RECOVERY_DELAY = 2000

try:
    from logger import log_message as kodi_log
    def log_message(msg, level=None):
        if KODI_AVAILABLE: kodi_log(msg, level if level is not None else xbmc.LOGDEBUG)
        else: print(f"{ADDON_ID} [OPS]: {msg}", flush=True)
except ImportError:
    def log_message(msg, level=None): print(f"LOG: {msg}", flush=True)

if KODI_AVAILABLE:
    _ADDON = xbmcaddon.Addon(ADDON_ID)
    ADDON_PATH = _ADDON.getAddonInfo('path')
    ICON_CON = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_connected.png')
    ICON_DIS = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_disconnected.png')
    ICON_ERROR = os.path.join(ADDON_PATH, 'resources', 'media', 'error.png')
    ICON_ERROR_NETWORK = os.path.join(ADDON_PATH, 'resources', 'media', 'router-network-error-alert.png')
else:
    ADDON_PATH = f"/storage/.kodi/addons/{ADDON_ID}"
    ICON_CON = ICON_DIS = ICON_ERROR = ICON_ERROR_NETWORK = ""

from network_utils import set_secure_dns, disable_connman_ipv6, enable_connman_ipv6, get_default_gateway

def get_active_vpn():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: return f.read().strip() or None
        except: return None
    return None

def set_active_vpn(name):
    try:
        if name:
            with open(STATE_FILE, "w") as f: f.write(name.strip())
        elif os.path.exists(STATE_FILE): os.remove(STATE_FILE)
    except Exception as e: log_message(f"Operation: State Error {e}")

def disconnect_vpn(silent=False):
    if not silent:
        xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
        for path in ['/tmp/vpn_manual_active.txt', '/storage/.kodi/temp/vpn_manual_active.txt']:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass

    try: open(INTENTIONAL_DISCONNECT_FILE, 'w').close()
    except: pass

    if KODI_AVAILABLE:
        xbmcgui.Window(10000).setProperty('vpn_intentional_disconnect', 'true')
        xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
   
    log_message(f"WAIT_START: Property Sync ({PROP_SYNC_DELAY}ms) | PURPOSE: {PROP_SYNC_PURPOSE}")
    if KODI_AVAILABLE: xbmc.sleep(PROP_SYNC_DELAY)
    else: time.sleep(PROP_SYNC_DELAY / 1000.0)

    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():
            if "vpn_" in line and ("* " in line or "R " in line):
                subprocess.run(["connmanctl", "disconnect", line.split()[-1]], check=False)
    except Exception as e: log_message(f"Operation: Disconnect Error {e}")

    enable_connman_ipv6()
    set_secure_dns(vpn_active=False)
    set_active_vpn(None)
    
    if not silent and KODI_AVAILABLE:
        xbmcgui.Dialog().notification("Network", "VPN Disconnected...", ICON_DIS, 3000)

    log_message(f"WAIT_START: OS Interface Release ({OS_RELEASE_DELAY}ms) | PURPOSE: {OS_RELEASE_PURPOSE}")
    if KODI_AVAILABLE: xbmc.sleep(OS_RELEASE_DELAY)
    else: time.sleep(OS_RELEASE_DELAY / 1000.0)
 
    gw = get_default_gateway()

    if not gw:
        log_message("Operation: Default route lost. Attempting restoration...", xbmc.LOGDEBUG)
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            phys_service = next((line.split()[-1] for line in out.splitlines() if line.startswith(('*', 'R')) and "vpn_" not in line), None)
            if phys_service:
                subprocess.run(["connmanctl", "config", phys_service, "--ipv4", "dhcp"], check=False)
                
                log_message(f"WAIT: DHCP Recovery ({DHCP_RECOVERY_DELAY}ms)", xbmc.LOGINFO)
                if KODI_AVAILABLE: xbmc.sleep(DHCP_RECOVERY_DELAY)
                else: time.sleep(DHCP_RECOVERY_DELAY / 1000.0)
                
                gw = get_default_gateway()
        except: pass

    if gw:
        try:
            out_route = subprocess.check_output(["ip", "route", "show", "default"], text=True)
            route_is_missing = "default" not in out_route
            
            serv = subprocess.check_output(["connmanctl", "services"], text=True)
            target_dev = "eth0" if "ethernet" in serv else "wlan0"
            subprocess.run(["ip", "route", "replace", "default", "via", gw, "dev", target_dev], check=False)
            
            if route_is_missing:
                log_message(f"Operation: Route restored via {gw} on {target_dev}", xbmc.LOGINFO)
        except Exception as e:
            log_message(f"Operation: Route Restore Error {e}", xbmc.LOGERROR)
    else:
        log_message("Operation: Fatal - No gateway found after restoration attempt.", xbmc.LOGERROR)

    if KODI_AVAILABLE: xbmcgui.Window(10000).setProperty('vpn_intentional_disconnect', '')
    if os.path.exists(INTENTIONAL_DISCONNECT_FILE):
        try: os.remove(INTENTIONAL_DISCONNECT_FILE)
        except: pass

def connect_vpn(vpn_name, sid):
    raw_state = get_active_vpn()
    active_clean = raw_state.replace('_', ' ').strip() if raw_state else None
    target_clean = vpn_name.replace('_', ' ').strip()

    if active_clean == target_clean: 
        return True

    gw = get_default_gateway()
    if not gw:
        log_message(f"Operation: Cannot connect to {vpn_name}. No local gateway detected.", xbmc.LOGERROR)
        if KODI_AVAILABLE:
            title = "[B][COLOR ffff0000]NETWORK ERROR[/COLOR][/B]"
            msg = "[COLOR fffffff00]No Internet detected. Check your Modem/Router.[/COLOR]"
            xbmcgui.Dialog().notification(title, msg, ICON_ERROR_NETWORK, 3000)
        return False

    log_message(f"Operation: Connecting to {vpn_name}", xbmc.LOGINFO)
    disable_connman_ipv6()

    pbg = xbmcgui.DialogProgressBG() if KODI_AVAILABLE else None
    if pbg: pbg.create("VPN Manager", f"Connecting to {vpn_name}...")

    subprocess.run(["connmanctl", "connect", sid], check=False)
    connected = False

    for i in range(1, 16):
        if pbg: pbg.update(int(i * 6.6), message=f"Verifying... ({i}s)")
        log_message(f"WAIT_START: Connection Poll {i} ({CONN_POLL_INTERVAL}ms)", xbmc.LOGDEBUG)
        
        if KODI_AVAILABLE: xbmc.sleep(CONN_POLL_INTERVAL)
        else: time.sleep(CONN_POLL_INTERVAL / 1000.0)
        
        try:
            check = subprocess.check_output(["connmanctl", "services"], text=True)
            if any(sid in line and ("* R" in line or "* O" in line) for line in check.splitlines()):

                if "wg0" in subprocess.check_output(["ip", "route"], text=True):
                    connected = True
                    break
        except: pass
        
    if pbg: pbg.close()

    if connected:
        set_active_vpn(target_clean)
        set_secure_dns(vpn_name, vpn_active=True)
        
        if KODI_AVAILABLE: xbmc.sleep(ROUTE_PROP_DELAY)
        else: time.sleep(ROUTE_PROP_DELAY / 1000.0)
        
        try:
            res = subprocess.check_output(["curl", "-s", "--max-time", "5", "https://ipinfo.io"], text=True)
            data = json.loads(res)
            ip, country = data.get("ip", "Unknown"), data.get("country", "??")
            msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}\nIP: [COLOR yellow]{ip}[/COLOR] ({country})"
        except: 
            msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {vpn_name}"
            
        if KODI_AVAILABLE: xbmcgui.Dialog().notification("VPN Connection is Secured", msg, ICON_CON, 3000)
        return True

    if KODI_AVAILABLE:
        current_gw = get_default_gateway()
        if not current_gw:
            err_msg = "Internet lost during connection attempt."
            log_message(f"Operation: Internet lost during connection attempt.", xbmc.LOGERROR)
        else:
            err_msg = "Handshake failed. Check VPN credentials or server."
            log_message(f"Operation: Handshake failed. Check VPN credentials or server.", xbmc.LOGERROR)
            
        title = "[B][COLOR ffff0000]VPN FAILURE (Internet,Handshake)[/COLOR][/B]"
        xbmcgui.Dialog().notification(title, err_msg, ICON_ERROR, 3000)
        
    disconnect_vpn(silent=True)
    return False
