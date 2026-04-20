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

from vpn_config import *
from vpn_ops import disconnect_vpn, connect_vpn
from logger import log_message

HELPER_LOCK = "/tmp/vpn_helper.lock"
RETRY_FILE = "/tmp/vpn_reconnect_count.txt"
MAX_RETRIES = 10

def get_retry_count():
    if os.path.exists(RETRY_FILE):
        try:
            with open(RETRY_FILE, "r") as f: return int(f.read().strip())
        except: return 0
    return 0

def increment_retry():
    count = get_retry_count() + 1
    try:
        with open(RETRY_FILE, "w") as f: f.write(str(count))
    except: pass
    return count

def run_reconnect():
    vpn_name = None
    sid = None
    state_path = "/tmp/vpn_manager_active.txt"

    if not os.path.exists(HELPER_LOCK):
        open(HELPER_LOCK, 'w').close()
    
    try:
        check_wg = subprocess.run(['ip', 'link', 'show', 'wg0'], capture_output=True)
        if check_wg.returncode == 0:
            log_message("Helper: Tunnel already active or in progress. Exiting instance.", 0)
            return

        if os.path.exists("/tmp/vpn_intentional_disconnect.txt"):
            return

        count = get_retry_count()
        if count >= MAX_RETRIES:
            log_message(f"Helper: Max retries ({MAX_RETRIES}) reached. Standing down.", 2)
            return

        gw_ready = False
        for i in range(1, 7):
            if get_default_gateway():
                gw_ready = True
                break
            time.sleep(5)
        
        if not gw_ready:
            increment_retry()
            return

        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as f: vpn_name = f.read().strip()
            except: pass

        if (not vpn_name or vpn_name.lower() == "true") and KODI_AVAILABLE:
            vpn_name = xbmcgui.Window(10000).getProperty('vpn_manual_session')

        if not vpn_name or vpn_name.lower() == "true":
            return

        log_message(f"Helper: Connection lost to {vpn_name}. Starting cleanup...", 1)
        disconnect_vpn(silent=True)
        time.sleep(2.0)

        try:
            search_term = vpn_name.replace(' ', '_')
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            sid = next((line.split()[-1] for line in out.splitlines() if search_term in line), None)
        except: pass

        if vpn_name and sid:
            log_message(f"Helper: Reconnecting to {vpn_name} (Attempt {count + 1}/{MAX_RETRIES})...", 1)
            if connect_vpn(vpn_name, sid):
                if os.path.exists(RETRY_FILE):
                    try: os.remove(RETRY_FILE)
                    except: pass
            else:
                new_count = increment_retry()
                log_message(f"Helper: Reconnect failed ({new_count}/{MAX_RETRIES}).", 2)

    finally:
        if os.path.exists(HELPER_LOCK):
            os.remove(HELPER_LOCK)

if __name__ == "__main__":
    run_reconnect()
