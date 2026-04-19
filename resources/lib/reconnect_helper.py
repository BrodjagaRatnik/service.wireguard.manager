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

def run_reconnect():
    open(HELPER_LOCK, 'w').close()
    
    try:
        if os.path.exists("/tmp/vpn_intentional_disconnect.txt"):
            return

        count = 0
        if os.path.exists(RETRY_FILE):
            try:
                with open(RETRY_FILE, "r") as f: count = int(f.read().strip())
            except: pass

        if count >= 10:
            log_message(f"Helper: Max retries (10) reached. Standing down.", 2) # LOGWARNING
            return

        gw_ready = False
        for i in range(1, 7):
            if get_default_gateway():
                gw_ready = True
                break
            time.sleep(5)
        
        if not gw_ready: return

        state_path = "/tmp/vpn_manager_active.txt"
        vpn_name = None
        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as f: vpn_name = f.read().strip()
            except: pass

        if vpn_name and vpn_name.lower() != "true":
            disconnect_vpn(silent=True)
            time.sleep(2.0)

            try:
                search_term = vpn_name.replace(' ', '_')
                out = subprocess.check_output(["connmanctl", "services"], text=True)
                sid = next((line.split()[-1] for line in out.splitlines() if search_term in line), None)
                
                if sid:
                    log_message(f"Helper: Reconnecting (Attempt {count + 1}/10)...", 1) # LOGINFO
                    if connect_vpn(vpn_name, sid):
                        if os.path.exists(RETRY_FILE): os.remove(RETRY_FILE)
                    else:
                        with open(RETRY_FILE, "w") as f: f.write(str(count + 1))
            except: pass
    finally:
        if os.path.exists(HELPER_LOCK): os.remove(HELPER_LOCK)

if __name__ == "__main__":
    run_reconnect()
