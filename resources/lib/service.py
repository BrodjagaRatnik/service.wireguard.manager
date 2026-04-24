''' ./resources/lib/service.py '''
import time, subprocess, os, sys, threading
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

try:
    from vpn_config import *
except ImportError:
    WATCHDOG_HEARTBEAT, WATCHDOG_SETTLE_DELAY, WATCHDOG_RECOVERY_DELAY = 1000, 20000, 1500

STATE_FILE = "/tmp/vpn_manager_active.txt"
INTENTIONAL_FILE = "/tmp/vpn_intentional_disconnect.txt"
HELPER_SCRIPT = os.path.join(LIB_PATH, "reconnect_helper.py")
HELPER_LOCK = "/tmp/vpn_helper.lock"
RETRY_FILE = "/tmp/vpn_reconnect_count.txt"

LAST_INTERFACE = None
BLACKOUT_ALERTED = False
SAVED_GATEWAY = None

def log_message(msg, level=1):
    try:
        if HAS_XBMC: xbmc.log(f"service.wireguard.manager [WATCHDOG]: {msg}", level)
        else:
            if level > 0:
                lvl = {1:"INFO", 2:"WARNING", 3:"ERROR"}.get(level, "INFO")
                print(f"WATCHDOG [{lvl}]: {msg}", flush=True)
    except: pass

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

def trigger_blackout_ui():
    """Aggressive background thread to kill frozen streams immediately."""
    try:
        icon = os.path.join(ADDON_DIR, 'resources', 'media', 'router-network-error-alert.png')
        sound = os.path.join(ADDON_DIR, 'resources', 'media', 'networkerror.wav')

        subprocess.run(['kodi-send', '--action=PlayerControl(Stop)'], check=False)
        subprocess.run(['kodi-send', '--action=Action(Stop)'], check=False)
        subprocess.run(['kodi-send', '--action=Dialog.Close(all,true)'], check=False)
        
        title = "[B][COLOR ffff0000]NO INTERNET CONNECTION DETECTED![/COLOR][/B]"
        msg = "[COLOR fffffff00]Check Wifi|Wire|Modem|Telecom provider.[/COLOR]"
        
        subprocess.run(['kodi-send', f'--action=Notification("{title}", "{msg}", 15000, "{icon}")'], check=False)
        log_message("Service: NO INTERNET CONNECTION DETECTED!", 3)

        if os.path.exists(sound):
            subprocess.run(['kodi-send', f'--action=PlayMedia("{sound}", 1)'], check=False)
        else:
            subprocess.run(['kodi-send', '--action=PlayAction(rightclick)'], check=False)
    except: pass

def watchdog_logic():
    global LAST_INTERFACE, BLACKOUT_ALERTED

    if os.path.exists(HELPER_LOCK):
        log_message("Service: Shield Active (Helper is running). Skipping check.", 0)
        if time.time() - os.path.getmtime(HELPER_LOCK) > 180:
            log_message("Service: Helper lock appears stuck. Clearing.", 2)
            try: os.remove(HELPER_LOCK)
            except: pass
        return 

    eth_link, wifi_link = is_physically_connected("eth0"), is_physically_connected("wlan0")
    if not eth_link and not wifi_link:
        if not BLACKOUT_ALERTED:
            log_message("Service: PHYSICAL DISCONNECT: No link detected.", 3)
            threading.Thread(target=trigger_blackout_ui, daemon=True).start()
            BLACKOUT_ALERTED = True
        return 
    
    BLACKOUT_ALERTED = False

    eth_online, wifi_online = check_interface_status()
    current_iface = get_active_interface()

    if not os.path.exists(STATE_FILE) or os.path.exists(INTENTIONAL_FILE): 
        return

    if (eth_online or wifi_online) and not current_iface and SAVED_GATEWAY:
        target_dev = "eth0" if eth_online else "wlan0"
        subprocess.run(["ip", "route", "replace", "default", "via", SAVED_GATEWAY, "dev", target_dev], check=False)
        time.sleep(1.0)
        current_iface = get_active_interface()

    try:
        vpn_active = subprocess.run(['ip', 'link', 'show', 'wg0'], capture_output=True).returncode == 0
        if not vpn_active:
            try:
                f = open("/tmp/vpn_helper.lock", 'w')
                f.write("locked")
                f.close()
                log_message("Service: Lock created at /tmp/vpn_helper.lock", 0)
            except Exception as e:
                log_message(f"Service: FATAL - Could not create lock file: {e}", 3)
            
            log_message("Service: Network change or tunnel loss. Triggering Helper...", 1)
            subprocess.run(['kodi-send', f'--action=RunScript("{HELPER_SCRIPT}")'], check=False)
            
            time.sleep(WATCHDOG_SETTLE_DELAY / 1000.0)
            return

    except Exception as e:
        log_message(f"Service: Watchdog Error: {e}", 2)

    if current_iface in ['eth0', 'wlan0']:
        if LAST_INTERFACE != current_iface:
            if os.path.exists(RETRY_FILE):
                try: os.remove(RETRY_FILE)
                except: pass
            log_message(f"Service: Interface changed to {current_iface}. Resetting retry counter.", 1)
        LAST_INTERFACE = current_iface

if __name__ == "__main__":
    while SAVED_GATEWAY is None:
        SAVED_GATEWAY = get_default_gateway()
        if SAVED_GATEWAY: break
        log_message("Service: Waiting for gateway...", 2)
        time.sleep(5)
    
    LAST_INTERFACE = get_active_interface()
    log_message(f"Service: Initialized on {LAST_INTERFACE}. Monitoring started.", 1)
    while True:
        if os.path.exists("/tmp/vpn_helper.lock"):
            log_message("Service: SHIELD ACTIVE - LOCK FOUND. Sleeping...", 0)
            time.sleep(5)
            continue

        watchdog_logic()
        time.sleep(WATCHDOG_HEARTBEAT / 1000.0)
