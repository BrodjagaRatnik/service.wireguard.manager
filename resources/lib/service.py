import time, subprocess, os, sys, signal

addon_dir = '/storage/.kodi/addons/service.wireguard.manager'
lib_path = os.path.join(addon_dir, 'resources', 'lib')
if lib_path not in sys.path:
    sys.path.append(lib_path)

try:
    from logger import log_message
except ImportError:
    def log_message(msg, level=None): print(f"LOG: {msg}")

def handle_signal(signum, frame):
    log_message("Watchdog: Forced check triggered by config update.")
    watchdog_logic()

signal.signal(signal.SIGHUP, handle_signal)

def wait_for_network():
    log_message("Watchdog: Waiting for ConnMan network state...")
    for i in range(30):
        try:
            out = subprocess.check_output(["connmanctl", "state"], text=True)
            if "State = ready" in out or "State = online" in out:
                log_message(f"Watchdog: Network ready.")
                return True
        except: pass
        time.sleep(1)
    return False

SAVED_GATEWAY = None

def get_default_gateway():
    global SAVED_GATEWAY
    try:
        out = subprocess.check_output(["ip", "-4", "route", "show", "default"], text=True)
        if "default" in out:
            parts = out.split()
            via_idx = parts.index("via")
            SAVED_GATEWAY = parts[via_idx + 1]
            log_message(f"Watchdog: Saved default gateway {SAVED_GATEWAY}")
            return SAVED_GATEWAY
    except: pass
    return SAVED_GATEWAY

def watchdog_logic():
    try:
        routes = subprocess.check_output(["ip", "route"], text=True)

        if "wg0" in routes: 
            return

        if "default" not in routes and SAVED_GATEWAY:
            log_message("Watchdog: Connection drop detected. Restoring gateway...")
            res = subprocess.run(["route", "add", "default", "gw", SAVED_GATEWAY, "eth0"], 
                                 capture_output=True, text=True)
            if res.returncode == 0:
                log_message(f"Watchdog: Successfully restored gateway {SAVED_GATEWAY}")
            else:
                log_message(f"Watchdog: Restore failed: {res.stderr.strip()}")
    except Exception as e:
        log_message(f"Watchdog Error: {str(e)}")

if __name__ == "__main__":
    wait_for_network()

    while SAVED_GATEWAY is None:
        get_default_gateway()
        if SAVED_GATEWAY: break
        time.sleep(2)
        
    log_message("Watchdog: Monitoring loop started.")
    while True:
        watchdog_logic()
        time.sleep(5)
