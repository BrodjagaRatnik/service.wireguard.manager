import time
import subprocess
import logging
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = '/storage/.kodi/temp/wireguard_manager.log'

logging.basicConfig(
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=1)],
    level=logging.INFO,
    format='%(asctime)s - WATCHDOG - %(levelname)s - %(message)s'
)

logging.basicConfig(level=logging.INFO, format='WG_Manager [Watchdog]: %(message)s')

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
        if "wg0" in routes: return

        if "default" not in routes:
            logging.info(f"Restoring gateway {current_gw} on {interface}")
            subprocess.run(["route", "add", "default", "gw", current_gw, interface])
    except Exception as e:
        logging.error(f"Watchdog error: {e}")

if __name__ == "__main__":
    logging.info("Watchdog background service starting...")

    while SAVED_GATEWAY is None:
        get_default_gateway()
        if SAVED_GATEWAY: break
        time.sleep(2)
    
    logging.info(f"Network active ({SAVED_GATEWAY}). Monitoring started.")
    
    while True:
        watchdog_logic()
        time.sleep(10)
