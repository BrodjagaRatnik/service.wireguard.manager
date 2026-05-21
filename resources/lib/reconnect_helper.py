''' ./resources/lib/reconnect_helper.py '''
import os
import subprocess
import sys
import time
from logger import log_message
from network_utils import get_default_gateway
from vpn_config import DHCP_RECOVERY_DELAY
from vpn_ops import connect_vpn, disconnect_vpn

try:
    import xbmcaddon
    import xbmcgui
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

MAX_RETRIES = 10
RETRY_FILE = "/tmp/vpn_reconnect_count.txt"


def get_retry_count():
    if os.path.exists(RETRY_FILE):
        try:
            with open(RETRY_FILE, "r") as f:
                return int(f.read().strip())
        except Exception as e:
            log_message(f"Failed to read retry count file: {e}", 3)
            return 0
    return 0


def increment_retry():
    count = get_retry_count() + 1
    try:
        with open(RETRY_FILE, "w") as f:
            f.write(str(count))
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        log_message(f"Failed to write incremented retry count: {e}", 3)
    return count


def run_reconnect():
    vpn_name = None
    sid = None
    state_path = "/tmp/vpn_manager_active.txt"

    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                vpn_name = f.read().strip()
        except Exception as e:
            log_message(f"Failed to read vpn manager active state: {e}", 3)

    if (not vpn_name or vpn_name.lower() == "true") and HAS_KODI:
        vpn_name = xbmcgui.Window(10000).getProperty('vpn_manual_session')

    if not vpn_name or vpn_name.lower() == "true":
        return

    try:
        try:
            addon_inst = xbmcaddon.Addon('service.wireguard.manager')
            provider_id = addon_inst.getSettingInt("vpn_provider")
        except Exception:
            provider_id = 1

        while True:
            count = get_retry_count()
            if count >= MAX_RETRIES:
                log_message(f"Helper: Max retries ({MAX_RETRIES}) reached. Standing down.", 2)
                if os.path.exists(RETRY_FILE):
                    os.remove(RETRY_FILE)
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
                log_message(f"Helper: No gateway. Attempt {new_count}/{MAX_RETRIES}", 0)
                continue

            if provider_id == 1 and count > 0:
                try:
                    pia_pause_sec = HELPER_PIA_RECOVERY_DELAY / 1000.0
                except NameError:
                    pia_pause_sec = 4.5

                log_message(f"Helper: Applying PIA recovery pause interval delay ({pia_pause_sec}s)...", 0)
                time.sleep(pia_pause_sec)

            log_message(f"Helper: Reconnecting to {vpn_name} (Attempt {count + 1}/{MAX_RETRIES})...", 1)
            disconnect_vpn(silent=True)
            time.sleep(0.6)

            try:
                search_term = vpn_name.replace(' ', '_')
                search_term_lower = search_term.lower()

                out = subprocess.check_output(["connmanctl", "services"], text=True)

                sid = None
                for line in out.splitlines():
                    if search_term in line or search_term_lower in line:
                        sid = line.split()[-1]
                        break
            except Exception as e:
                log_message(f"Failed to find network service ID for {vpn_name}: {e}", 3)
                sid = None

            if sid and connect_vpn(vpn_name, sid, silent=True):
                log_message("Helper: Connection verified... Task complete.", 0)
                if os.path.exists(RETRY_FILE):
                    os.remove(RETRY_FILE)
                break
            else:
                log_message("Helper: vpn_ops reported failure. Retrying...", 2)
                increment_retry()

    finally:
        log_message("Helper: Task finished.", 1)


if __name__ == "__main__":
    run_reconnect()
