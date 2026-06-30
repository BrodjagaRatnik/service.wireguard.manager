""" ./resources/lib/service.py """
import kodi_env
import os
import subprocess
import sys
import threading
import time
from logger import log_message
from network_utils import get_default_gateway, is_physically_connected
from vpn_config import (
    SHIELD_SLEEP_DELAY,
    WATCHDOG_HEARTBEAT,
    WATCHDOG_SETTLE_DELAY,
)
from vpn_utils import (
    get_active_interface,
    check_interface_status,
)
from wm_utils import trigger_blackout_ui
from state_manager import get_file_path

try:
    import xbmcgui
    HAS_XBMC = True
except ImportError:
    HAS_XBMC = False

    class MockGUI:

        def Dialog(self):
            return self

        def notification(self, t, m, i, d):
            sys.stderr.write(f"NOTIFY: {t} - {m}\n")
            sys.stderr.flush()

    xbmcgui = MockGUI()

ADDON_DIR = kodi_env.ADDON_DIR
ADDON_PATH = ADDON_DIR
LIB_PATH = os.path.join(ADDON_DIR, "resources", "lib")

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

HELPER_SCRIPT = os.path.join(LIB_PATH, "reconnect_helper.py")
LAST_INTERFACE = None
BLACKOUT_ALERTED = False
SAVED_GATEWAY = None


def watchdog_logic():
    global LAST_INTERFACE, BLACKOUT_ALERTED
    log_message("Watchdog Check: Commencing logical evaluation cycle.", 0)

    conn_lock_path = get_file_path("connector_lock")
    if conn_lock_path is not None and os.path.exists(conn_lock_path) is True:
        log_message("Watchdog Check: Active connector lock found. Aborting evaluation.", 0)
        return

    log_message(f"Watchdog Check: Blackout alert tracking state is {BLACKOUT_ALERTED}", 0)
    if BLACKOUT_ALERTED is True:
        eth_link = is_physically_connected("eth0")
        wifi_link = is_physically_connected("wlan0")
        log_message(f"Watchdog Check: Physical links during blackout: eth0={eth_link}, wlan0={wifi_link}", 0)
        if eth_link or wifi_link:
            log_message("Service: Physical connection restored.", 1)
            blackout_path = get_file_path("blackout")
            if blackout_path is not None and os.path.exists(blackout_path) is True:
                try:
                    os.remove(blackout_path)
                except Exception as e:
                    log_message(f"Service: Error removing blackout lock file: {e}", 3)
            BLACKOUT_ALERTED = False

    current_iface = get_active_interface()
    wg0_active = False

    try:
        if os.path.exists("/sys/class/net/"):
            for iface in os.listdir("/sys/class/net/"):
                if iface.startswith(("vpn_", "wg")):
                    wg0_active = True
                    if not current_iface or current_iface in ["eth0", "wlan0"]:
                        current_iface = iface
                    break
    except Exception:
        pass

    log_msg = f"Watchdog Check: Dynamic evaluation yields wg0_active={wg0_active} ({current_iface})"
    log_message(log_msg, 0)
    if wg0_active is True:
        LAST_INTERFACE = current_iface
        intentional_path = get_file_path("disconnect")
        if intentional_path is not None and os.path.exists(intentional_path) is True:
            try:
                os.remove(intentional_path)
            except Exception:
                pass
    else:
        state_path = get_file_path("active")
        intentional_path = get_file_path("disconnect")
        sf_ex = state_path is not None and os.path.exists(state_path) is True
        if_ex = intentional_path is not None and os.path.exists(intentional_path) is True
        should_be_active = sf_ex and not if_ex
        log_msg = f"Watchdog Check: File targets: state={sf_ex}, intentional={if_ex}, result={should_be_active}"
        log_message(log_msg, 0)

        if should_be_active is True:
            eth_link = is_physically_connected("eth0")
            wifi_link = is_physically_connected("wlan0")
            log_msg = f"Watchdog Check: Carrier detection states: eth0={eth_link}, wlan0={wifi_link}"
            log_message(log_msg, 0)
            if not eth_link and not wifi_link:
                log_message("Watchdog Check: Initial drop caught. Pausing for link stabilization.", 2)
                time.sleep(0.5)
                eth_link = is_physically_connected("eth0")
                wifi_link = is_physically_connected("wlan0")
                log_msg = f"Watchdog Check: Post-pause link check states: eth0={eth_link}, wlan0={wifi_link}"
                log_message(log_msg, 0)
                if not eth_link and not wifi_link:
                    if BLACKOUT_ALERTED is False:
                        log_err = "Service: TOTAL PHYSICAL DISCONNECT. Triggering Blackout UI."
                        log_message(log_err, 3)
                        subprocess.run(["pkill", "-f", HELPER_SCRIPT], check=False)
                        threading.Thread(target=trigger_blackout_ui, daemon=True).start()
                        BLACKOUT_ALERTED = True
                return

            log_message("Service: Internet detected but Tunnel missing. Triggering Helper...", 2)
            proc = subprocess.Popen([sys.executable, HELPER_SCRIPT])
            proc.wait()
            log_msg = f"Watchdog Check: Helper finished. Pausing for settle interval: {WATCHDOG_SETTLE_DELAY}ms"
            log_message(log_msg, 0)
            time.sleep(WATCHDOG_SETTLE_DELAY / 1000.0)
            return

    eth_online, wifi_online = check_interface_status()
    log_msg = f"Watchdog Check: Active default interface={current_iface}, eth={eth_online}, wifi={wifi_online}"
    log_message(log_msg, 0)
    if (eth_online or wifi_online) and not current_iface and not wg0_active:
        log_message("Service: Physical link active but no default route. Triggering Helper...", 2)
        proc = subprocess.Popen([sys.executable, HELPER_SCRIPT])
        proc.wait()
        time.sleep(WATCHDOG_SETTLE_DELAY / 1000.0)
        return

    if current_iface in ["eth0", "wlan0"]:
        log_msg = f"Watchdog Check: Interface transition tracking: last={LAST_INTERFACE}, current={current_iface}"
        log_message(log_msg, 0)
        if LAST_INTERFACE != current_iface:
            log_message(f"Service: Network interface switched to {current_iface}", 1)

            state_path = get_file_path("active")
            if state_path is not None and os.path.exists(state_path) is True:
                log_message("Service: Active profile configuration state found. Forcing reconnect helper.", 2)
                proc = subprocess.Popen([sys.executable, HELPER_SCRIPT])
                proc.wait()
                LAST_INTERFACE = get_active_interface()
                return

            reconnect_path = get_file_path("reconnect")
            if reconnect_path is not None and os.path.exists(reconnect_path) is True:
                try:
                    os.remove(reconnect_path)
                except Exception as e:
                    log_message(f"Service: Interface change cleanup error: {e}", 3)
            LAST_INTERFACE = current_iface


if __name__ == "__main__":
    while SAVED_GATEWAY is None:
        SAVED_GATEWAY = get_default_gateway()
        if SAVED_GATEWAY:
            break
        if BLACKOUT_ALERTED is False:
            threading.Thread(target=trigger_blackout_ui, daemon=True).start()
            BLACKOUT_ALERTED = True
        log_message("Service: Waiting for gateway...", 2)
        time.sleep(SHIELD_SLEEP_DELAY / 1000.0)

    BLACKOUT_ALERTED = False
    LAST_INTERFACE = get_active_interface()
    log_message(f"Service: Initialized on {LAST_INTERFACE}. Monitoring started.", 1)
    shield_logged = False

    try:
        while True:
            manual_path = get_file_path("manual")
            intentional_path = get_file_path("disconnect")
            has_manual = manual_path is not None and os.path.exists(manual_path) is True
            has_intentional = intentional_path is not None and os.path.exists(intentional_path) is True

            if has_manual or has_intentional:
                if not shield_logged:
                    log_message("Service: SHIELD ACTIVE - SESSION FOUND. Pausing watchdog.", 0)
                    shield_logged = True
            else:
                if shield_logged:
                    log_message("Service: Shield cleared. Resuming watchdog operation.", 0)
                shield_logged = False
                watchdog_logic()
            time.sleep(WATCHDOG_HEARTBEAT / 1000.0)
    finally:
        kodi_env.clear_script_globals()
