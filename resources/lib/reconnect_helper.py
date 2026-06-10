""" ./resources/lib/reconnect_helper.py """
import os
import subprocess
import sys
import time

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

log_message = __import__('logger').log_message
get_default_gateway = __import__('network_utils').get_default_gateway
DHCP_RECOVERY_DELAY = __import__('vpn_config').DHCP_RECOVERY_DELAY

try:
    import xbmcgui
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

MAX_RETRIES = 10
RETRY_FILE = "/tmp/vpn_reconnect_count.txt"
LOCK_FILE = "/tmp/vpn_connector_active.lock"


def get_retry_count():
    if os.path.exists(RETRY_FILE):
        try:
            with open(RETRY_FILE, "r") as f:
                return int(f.read().strip())
        except Exception as e:
            log_message(f"Reconnect Helper: Failed to read retry count file: {e}", 3)
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
        log_message(f"Reconnect Helper: Failed to write incremented retry count: {e}", 3)
    return count


def run_reconnect():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            log_message("Reconnect Helper: Active connector process running. Exiting.", 1)
            return
        except (ValueError, OSError):
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass
    vpn_name = None
    state_path = "/tmp/vpn_manager_active.txt"
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                vpn_name = f.read().strip()
        except Exception as e:
            log_message(f"Reconnect Helper: Failed to read vpn manager active state: {e}", 3)
    if (not vpn_name or vpn_name.lower() == "true") and HAS_KODI:
        vpn_name = xbmcgui.Window(10000).getProperty('vpn_manual_session')
    if not vpn_name or vpn_name.lower() == "true":
        return
    try:
        while True:
            count = get_retry_count()
            if count >= MAX_RETRIES:
                log_message(f"Reconnect Helper: Max retries ({MAX_RETRIES}) reached. Standing down.", 2)
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
                log_message(f"Reconnect Helper: No gateway ready. Attempt {new_count}/{MAX_RETRIES}", 2)
                continue
            log_message(f"Reconnect Helper: Reconnecting to {vpn_name} (Attempt {count + 1}/{MAX_RETRIES})...", 1)
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
                log_message(f"Reconnect Helper: Failed to find network service ID for {vpn_name}: {e}", 3)
                sid = None
            if sid:
                subprocess.run(
                    ["connmanctl", "disconnect", sid],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                res = subprocess.run(
                    ["connmanctl", "connect", sid],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if res.returncode == 0:
                    verified = False
                    for check in range(20):
                        try:
                            with open("/proc/net/dev", "r") as f:
                                if "wg0:" in f.read():
                                    verified = True
                                    break
                        except Exception:
                            pass
                        time.sleep(0.2)
                    if verified:
                        log_message("Reconnect Helper: Connection verified... Task complete.", 1)
                        if os.path.exists(RETRY_FILE):
                            os.remove(RETRY_FILE)
                        break
            log_message("Reconnect Helper: ConnMan reported failure. Retrying...", 2)
            increment_retry()
    finally:
        log_message("Reconnect Helper: Task finished.", 0)


if __name__ == "__main__":
    run_reconnect()
