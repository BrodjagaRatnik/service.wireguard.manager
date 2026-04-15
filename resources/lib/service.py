import time, subprocess, os, sys, signal

addon_dir = '/storage/.kodi/addons/service.wireguard.manager'
lib_path = os.path.join(addon_dir, 'resources', 'lib')
if lib_path not in sys.path:
    sys.path.append(lib_path)

try:
    from logger import log_message
except ImportError:
    def log_message(msg, level=None): print(f"LOG: {msg}")

LAST_INTERFACE = None
SAVED_GATEWAY = None
STATE_FILE = "/tmp/vpn_manager_active.txt"
HELPER_SCRIPT = "/storage/.kodi/addons/service.wireguard.manager/resources/lib/reconnect_helper.py"

def get_active_interface():
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        if "dev" in out:
            return out.split()[out.split().index("dev") + 1]
    except: pass
    return None

def check_interface_status():
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        eth = any(line.startswith("*") and "ethernet" in line for line in out.splitlines())
        wifi = any(line.startswith("*") and "wifi" in line for line in out.splitlines())
        return eth, wifi
    except: return False, False

def get_default_gateway():
    global SAVED_GATEWAY
    try:
        out = subprocess.check_output(["ip", "-4", "route", "show", "default"], text=True)
        if "default" in out:
            parts = out.split()
            new_gw = parts[parts.index("via") + 1]
            if new_gw != SAVED_GATEWAY:
                SAVED_GATEWAY = new_gw
                log_message(f"Watchdog: System gateway identified as {SAVED_GATEWAY}")
            return SAVED_GATEWAY
    except:
        pass

    if SAVED_GATEWAY:
        return SAVED_GATEWAY
    
    return None

def watchdog_logic():
    global LAST_INTERFACE, SAVED_GATEWAY

    STATE_FILE = "/tmp/vpn_manager_active.txt"
    if not os.path.exists(STATE_FILE):
        return

    try:
        file_age = time.time() - os.path.getmtime(STATE_FILE)
        if file_age < 20:
            return
    except: pass

    eth_online, wifi_online = check_interface_status()
    current_iface = get_active_interface()
    HELPER_SCRIPT = "/storage/.kodi/addons/service.wireguard.manager/resources/lib/reconnect_helper.py"
    
    try:
        if LAST_INTERFACE == "eth0" and not eth_online:
            log_message("Watchdog: Ethernet lost! Triggering Reconnect Helper...")
            subprocess.run(['kodi-send', f'--action=RunScript("{HELPER_SCRIPT}")'], check=False)
            LAST_INTERFACE = "wlan0"
            time.sleep(15) 
            return

        if LAST_INTERFACE == "wlan0" and eth_online:
            log_message("Watchdog: Ethernet back! Triggering Reconnect Helper...")
            subprocess.run(['kodi-send', f'--action=RunScript("{HELPER_SCRIPT}")'], check=False)
            LAST_INTERFACE = "eth0"
            time.sleep(15)
            return

        routes = subprocess.check_output(["ip", "route"], text=True)
        if "wg0" not in routes and (eth_online or wifi_online):
            log_message("Watchdog: VPN tunnel missing. Triggering Reconnect Helper...")
            subprocess.run(['kodi-send', f'--action=RunScript("{HELPER_SCRIPT}")'], check=False)
            time.sleep(15)
            return

        if "wg0" not in routes and "default" not in routes and SAVED_GATEWAY:
            log_message("Watchdog: Path lost. Restoring gateway...")
            subprocess.run(["route", "add", "default", "gw", SAVED_GATEWAY], check=False)

    except Exception as e:
        log_message(f"Watchdog Error: {e}")

    if current_iface:
        LAST_INTERFACE = current_iface

if __name__ == "__main__":

    while SAVED_GATEWAY is None:
        get_default_gateway()
        if SAVED_GATEWAY: break
        time.sleep(2)

    LAST_INTERFACE = get_active_interface()
    log_message(f"Watchdog: Initialized on {LAST_INTERFACE}. Loop started.")
    
    while True:
        watchdog_logic()
        time.sleep(5)
