import time, subprocess, os, sys

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path: sys.path.append(LIB_PATH)

try:
    from vpn_config import *
except ImportError:
    WATCHDOG_HEARTBEAT, WATCHDOG_SETTLE_DELAY, WATCHDOG_RECOVERY_DELAY = 2000, 4000, 3000

STATE_FILE = "/tmp/vpn_manager_active.txt"
INTENTIONAL_DISCONNECT_FILE = "/tmp/vpn_intentional_disconnect.txt"
HELPER_SCRIPT = os.path.join(LIB_PATH, "reconnect_helper.py")

def log_message(msg):
    print(f"service.wireguard.manager [WATCHDOG]: {msg}", flush=True)

LAST_INTERFACE = None
SAVED_GATEWAY = None

def get_active_interface():
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        if "dev" in out: return out.split()[out.split().index("dev") + 1]
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
            new_gw = out.split()[out.split().index("via") + 1]
            if new_gw != SAVED_GATEWAY:
                SAVED_GATEWAY = new_gw
                log_message(f"Gateway identified as {SAVED_GATEWAY}")
            return SAVED_GATEWAY
    except: pass
    return SAVED_GATEWAY

def watchdog_logic():
    global LAST_INTERFACE
    if os.path.exists(INTENTIONAL_DISCONNECT_FILE): return 
    if not os.path.exists(STATE_FILE): return
    eth_online, wifi_online = check_interface_status()
    current_iface = get_active_interface()
    
    try:
        vpn_active = "wg0" in subprocess.check_output(["ip", "route"], text=True)
        if LAST_INTERFACE == "wlan0" and eth_online:
            log_message("Ethernet back! Triggering Reconnect...")
            subprocess.run(['kodi-send', f'--action=RunScript("{HELPER_SCRIPT}")'], check=False)
            LAST_INTERFACE = "eth0"
            log_message(f"WAIT_START: Interface Settle ({WATCHDOG_SETTLE_DELAY}ms)")
            time.sleep(WATCHDOG_SETTLE_DELAY / 1000.0)
            return

        if LAST_INTERFACE == "eth0" and not eth_online:
            log_message("Ethernet lost! Triggering Reconnect...")
            subprocess.run(['kodi-send', f'--action=RunScript("{HELPER_SCRIPT}")'], check=False)
            LAST_INTERFACE = "wlan0"
            log_message(f"WAIT_START: Failover Settle ({WATCHDOG_SETTLE_DELAY}ms)")
            time.sleep(WATCHDOG_SETTLE_DELAY / 1000.0)
            return

        if not vpn_active and (eth_online or wifi_online):
            log_message("VPN tunnel missing. Triggering Recovery...")
            subprocess.run(['kodi-send', f'--action=RunScript("{HELPER_SCRIPT}")'], check=False)
            log_message(f"WAIT_START: Tunnel Recovery ({WATCHDOG_RECOVERY_DELAY}ms)")
            time.sleep(WATCHDOG_RECOVERY_DELAY / 1000.0)
            return
    except Exception as e: log_message(f"Error: {e}")
    if current_iface: LAST_INTERFACE = current_iface

if __name__ == "__main__":
    while SAVED_GATEWAY is None:
        get_default_gateway()
        if SAVED_GATEWAY: break
        time.sleep(2)
    LAST_INTERFACE = get_active_interface()
    log_message(f"Initialized on {LAST_INTERFACE}. Monitoring started.")
    while True:
        watchdog_logic()
        time.sleep(WATCHDOG_HEARTBEAT / 1000.0)
