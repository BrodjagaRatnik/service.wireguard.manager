import time
import subprocess
import os
import sys

try:
    import xbmc
    import xbmcaddon
    ADDON = xbmcaddon.Addon('service.wireguard.manager')
    ADDON_PATH = ADDON.getAddonInfo('path')
    sys.path.append(os.path.join(ADDON_PATH, 'resources', 'lib'))
    from logger import log_message
    KODI_MODE = True
except ImportError:
    KODI_MODE = False

def log_event(msg, level=2):
    if KODI_MODE:
        log_message(f"Watchdog: {msg}", level)
    else:
        print(f"WATCHDOG: {msg}")

SAVED_GATEWAY = None

def get_default_interface():
    try:
        out = subprocess.check_output(["ip", "route"], text=True)
        for line in out.splitlines():
            if "default via" in line:
                parts = line.split()
                return parts[parts.index("dev") + 1]
    except: pass
    return "eth0"

def get_default_gateway():
    global SAVED_GATEWAY
    try:
        out = subprocess.check_output(["ip", "-4", "route", "show", "default"], text=True)
        if "default" in out:
            parts = out.split()
            if "via" in parts:
                SAVED_GATEWAY = parts[parts.index("via") + 1]
                return SAVED_GATEWAY
    except: pass
    return SAVED_GATEWAY

def watchdog_logic():
    try:
        current_gw = get_default_gateway()
        if not current_gw: return 
            
        interface = get_default_interface()
        routes = subprocess.check_output(["route"], text=True)

        if "wg0" in routes:
            return

        if "default" not in routes:
            log_event(f"Gateway lost! Restoring {current_gw} on {interface}", 4)
            subprocess.run(["route", "add", "default", "gw", current_gw, interface], check=False)
    except Exception as e:
        log_event(f"Error: {e}", 4)

if __name__ == "__main__":
    log_event("Starting background monitoring...")

    while SAVED_GATEWAY is None:
        get_default_gateway()
        if SAVED_GATEWAY: break
        time.sleep(2)
    
    log_event(f"Network active ({SAVED_GATEWAY}). Monitoring every 10s.")
    
    while True:
        watchdog_logic()
        time.sleep(10)
