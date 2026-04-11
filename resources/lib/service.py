import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = '/storage/.kodi/temp/wireguard_manager.log'

try:
    import xbmc
    KODI_MODE = True
except ImportError:
    KODI_MODE = False
logger = logging.getLogger("WG_Watchdog")
if not logger.handlers:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=1)
    handler.setFormatter(logging.Formatter('%(asctime)s - WATCHDOG - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def log_important(msg):
    logger.info(msg)
    if KODI_MODE:
        xbmc.log(f"[service.wireguard.manager] {msg}", xbmc.LOGINFO)
    else:
        print(f"LOG (IMP): {msg}")

def log_debug(msg):
    if KODI_MODE:
        xbmc.log(f"[service.wireguard.manager] {msg}", xbmc.LOGINFO)
    else:
        print(f"LOG (DEBUG): {msg}")

SAVED_GATEWAY = None

def get_default_interface():
    try:
        out = subprocess.check_output(["ip", "route"]).decode()
        for line in out.splitlines():
            if "default via" in line:
                return line.split()[line.split().index("dev") + 1]
    except: pass
    return "eth0"

def get_default_gateway():
    global SAVED_GATEWAY
    try:
        out = subprocess.check_output(["ip", "-4", "route", "show", "default"]).decode()
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
        routes = subprocess.check_output(["route"]).decode()

        if "wg0" in routes:
            log_debug("Watchdog check: VPN route active.")
            return

        if "default" not in routes:
            log_important(f"Gateway lost! Restoring {current_gw} on {interface}")
            subprocess.run(["route", "add", "default", "gw", current_gw, interface])
    except Exception as e:
        log_important(f"Watchdog error: {e}")

if __name__ == "__main__":
    log_important("Watchdog background service starting...")

    while SAVED_GATEWAY is None:
        get_default_gateway()
        if SAVED_GATEWAY: break
        time.sleep(2)
    
    log_important(f"Network active ({SAVED_GATEWAY}). Monitoring started.")
    
    while True:
        watchdog_logic()
        time.sleep(10)
