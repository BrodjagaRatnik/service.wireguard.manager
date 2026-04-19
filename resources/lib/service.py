''' ./resources/lib/service.py '''
import time, subprocess, os, sys
from network_utils import get_default_gateway, is_physically_connected

try:
    import xbmc
    HAS_XBMC = True
except ImportError:
    HAS_XBMC = False
    class MockXBMC:
        LOGDEBUG, LOGINFO, LOGWARNING, LOGERROR = 0, 1, 2, 3
    xbmc = MockXBMC()

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path: sys.path.append(LIB_PATH)

try: from vpn_config import *
except ImportError: WATCHDOG_HEARTBEAT, WATCHDOG_SETTLE_DELAY, WATCHDOG_RECOVERY_DELAY = 5000, 4000, 3000

STATE_FILE, INTENTIONAL_FILE = "/tmp/vpn_manager_active.txt", "/tmp/vpn_intentional_disconnect.txt"
HELPER_SCRIPT, HELPER_LOCK = os.path.join(LIB_PATH, "reconnect_helper.py"), "/tmp/vpn_helper.lock"

LAST_INTERFACE, SAVED_GATEWAY, BLACKOUT_ALERTED = None, None, False

def get_active_interface():
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        if "dev" in out: return out.split()[out.split().index("dev") + 1]
    except: return None

def check_interface_status():
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        eth = any(line.startswith("*") and "ethernet" in line for line in out.splitlines())
        wifi = any(line.startswith("*") and "wifi" in line for line in out.splitlines())
        return eth, wifi
    except: return False, False

def log_message(msg, level=1):
    try:
        if HAS_XBMC: xbmc.log(f"service.wireguard.manager [WATCHDOG]: {msg}", level)
        else:
            if level > 0:
                lvl = {1:"INFO", 2:"WARNING", 3:"ERROR"}.get(level, "INFO")
                print(f"WATCHDOG [{lvl}]: {msg}", flush=True)
    except: pass

def watchdog_logic():
    global LAST_INTERFACE, SAVED_GATEWAY, BLACKOUT_ALERTED
    
    eth_link, wifi_link = is_physically_connected("eth0"), is_physically_connected("wlan0")
    if not eth_link and not wifi_link:
        if not BLACKOUT_ALERTED:
            log_message("PHYSICAL DISCONNECT: No link detected.", 3)
            BLACKOUT_ALERTED = True
        return 
    
    BLACKOUT_ALERTED = False
    if os.path.exists(HELPER_LOCK): return

    eth_online, wifi_online = check_interface_status()
    current_iface = get_active_interface()

    if not os.path.exists(STATE_FILE) or os.path.exists(INTENTIONAL_FILE): return

    if (eth_online or wifi_online) and not current_iface and SAVED_GATEWAY:
        target_dev = "eth0" if eth_online else "wlan0"
        subprocess.run(["ip", "route", "replace", "default", "via", SAVED_GATEWAY, "dev", target_dev], check=False)
        time.sleep(1.0)
        current_iface = get_active_interface()

    try:
        vpn_active = "wg0" in subprocess.check_output(["ip", "route"], text=True)
        if (not vpn_active or (LAST_INTERFACE == "wlan0" and eth_online) or (LAST_INTERFACE == "eth0" and not eth_online)):
            log_message("Network change or tunnel loss. Triggering Helper...", 1)
            subprocess.run(['kodi-send', f'--action=RunScript("{HELPER_SCRIPT}")'], check=False)
            time.sleep(WATCHDOG_SETTLE_DELAY / 1000.0)
    except: pass

    if current_iface and current_iface in ['eth0', 'wlan0']:
        if LAST_INTERFACE != current_iface:
            if os.path.exists("/tmp/vpn_reconnect_count.txt"): os.remove("/tmp/vpn_reconnect_count.txt")
        LAST_INTERFACE = current_iface

if __name__ == "__main__":
    while SAVED_GATEWAY is None:
        SAVED_GATEWAY = get_default_gateway()
        if SAVED_GATEWAY: break
        log_message("Waiting for gateway...", 2)
        time.sleep(5)
    
    LAST_INTERFACE = get_active_interface()
    log_message(f"Initialized on {LAST_INTERFACE}. Monitoring started.", 1)
    while True:
        watchdog_logic()
        time.sleep(WATCHDOG_HEARTBEAT / 1000.0)
