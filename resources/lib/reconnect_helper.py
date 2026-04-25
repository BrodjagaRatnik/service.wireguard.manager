''' ./resources/lib/reconnect_helper.py '''
import os, sys, time, subprocess
from network_utils import get_default_gateway

try:
    import xbmc, xbmcgui
    KODI_AVAILABLE = True
except ImportError:
    KODI_AVAILABLE = False

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path: sys.path.insert(0, LIB_PATH)

try:
    from vpn_config import DHCP_RECOVERY_DELAY, WATCHDOG_RECOVERY_DELAY
except ImportError:
    DHCP_RECOVERY_DELAY = 2000
    WATCHDOG_RECOVERY_DELAY = 2000

from vpn_ops import disconnect_vpn, connect_vpn
from logger import log_message

MAX_RETRIES = 10
HELPER_LOCK = "/tmp/vpn_helper.lock"
RETRY_FILE = "/tmp/vpn_reconnect_count.txt"

def get_retry_count():
    if os.path.exists(RETRY_FILE):
        try:
            with open(RETRY_FILE, "r") as f: return int(f.read().strip())
        except: return 0
    return 0

def increment_retry():
    count = get_retry_count() + 1
    try:
        with open(RETRY_FILE, "w") as f: 
            f.write(str(count))
            f.flush()
            os.fsync(f.fileno()) 
    except: pass
    return count

def run_reconnect():
    if os.path.exists(HELPER_LOCK):
        return
    try:
        with open(HELPER_LOCK, 'w') as f: f.write("locked")
    except:
        pass

    time.sleep(2)
    vpn_name = None
    sid = None
    state_path = "/tmp/vpn_manager_active.txt"

    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f: vpn_name = f.read().strip()
        except: pass

    if (not vpn_name or vpn_name.lower() == "true") and KODI_AVAILABLE:
        vpn_name = xbmcgui.Window(10000).getProperty('vpn_manual_session')

    if not vpn_name or vpn_name.lower() == "true":
        if os.path.exists(HELPER_LOCK): os.remove(HELPER_LOCK)
        return

    try:
        while True:
            count = get_retry_count()
            if count >= MAX_RETRIES:
                log_message(f"Helper: Max retries ({MAX_RETRIES}) reached. Standing down.", 2)
                if os.path.exists(RETRY_FILE): os.remove(RETRY_FILE)
                break

            gw_ready = False
            sleep_time = DHCP_RECOVERY_DELAY / 1000.0 
            
            for i in range(1, 7):
                if get_default_gateway():
                    gw_ready = True
                    break
                time.sleep(sleep_time)
            
            if not gw_ready:
                new_count = increment_retry()
                log_message(f"Helper: No gateway. Attempt {new_count}/{MAX_RETRIES}", 1)
                continue

            log_message(f"Helper: Reconnecting to {vpn_name} (Attempt {count + 1}/{MAX_RETRIES})...", 1)
            disconnect_vpn(silent=True)

            time.sleep(2)

            try:
                search_term = vpn_name.replace(' ', '_')
                out = subprocess.check_output(["connmanctl", "services"], text=True)
                sid = next((line.split()[-1] for line in out.splitlines() if search_term in line), None)
            except: sid = None

            if sid and connect_vpn(vpn_name, sid):
                log_message(f"Helper: Connected. Waiting for stability...", 0)

                stability_wait = (WATCHDOG_RECOVERY_DELAY * 2) / 1000.0
                time.sleep(stability_wait)

                check_wg = subprocess.run(['ip', 'link', 'show', 'wg0'], capture_output=True)
                if check_wg.returncode == 0:
                    log_message("Helper: Connection stable. Resetting counter.", 0)
                    if os.path.exists(RETRY_FILE): os.remove(RETRY_FILE)
                    break

            increment_retry()
            log_message("Helper: Reconnect failed. Retrying...", 0)

    finally:
        if os.path.exists(HELPER_LOCK):
            try:
                os.remove(HELPER_LOCK)
                log_message("Helper: Task finished, lock released.", 0)
            except:
                pass

if __name__ == "__main__":
    run_reconnect()
