''' ./resources/lib/service.py '''
import sys

if 'utils' in sys.modules and 'service.wireguard.manager' not in str(sys.modules.get('utils')):
    del sys.modules['utils']

import os
import subprocess
import threading
import time
from logger import log_message
from network_utils import get_default_gateway, is_physically_connected
from vpn_config import (
    SHIELD_SLEEP_DELAY,
    WATCHDOG_HEARTBEAT,
    WATCHDOG_SETTLE_DELAY,
)

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
ADDON_PATH = ADDON_DIR
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

try:
    import xbmc
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

STATE_FILE = "/tmp/vpn_manager_active.txt"
INTENTIONAL_FILE = "/tmp/vpn_intentional_disconnect.txt"
HELPER_SCRIPT = os.path.join(LIB_PATH, "reconnect_helper.py")
RETRY_FILE = "/tmp/vpn_reconnect_count.txt"
LAST_INTERFACE = None
BLACKOUT_ALERTED = False
SAVED_GATEWAY = None


def get_active_interface():
    try:
        out = subprocess.check_output(
            ["ip", "route", "show", "default"],
            text=True,
            stderr=subprocess.DEVNULL
        )
        interfaces = []
        for line in out.splitlines():
            parts = line.split()
            if "dev" in parts:
                dev_idx = parts.index("dev") + 1
                if dev_idx < len(parts):
                    interfaces.append(parts[dev_idx])

        for iface in interfaces:
            if "wg" in iface.lower() or "vpn" in iface.lower():
                return iface

        if interfaces:
            return interfaces[0]

        return None
    except Exception as e:
        log_message(f"Interface lookup error: {e}", 3)
        return None


def check_interface_status():
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        eth = any(line.startswith("*") and "ethernet" in line for line in out.splitlines())
        wifi = any(line.startswith("*") and "wifi" in line for line in out.splitlines())
        return eth, wifi
    except Exception as e:
        log_message(f"Interface status validation check failure: {e}", 3)
        return False, False


def trigger_blackout_ui():
    if os.path.exists('/tmp/vpn_blackout_active.lock'):
        return

    with open('/tmp/vpn_blackout_active.lock', 'w') as f:
        f.write('active')

    icon = os.path.join(ADDON_DIR, 'resources', 'media', 'router-network-error-alert.png')
    sound = os.path.join(ADDON_DIR, 'resources', 'media', 'networkerror.wav')
    title = "[B][COLOR ffff0000]▀■▄ NO NETWORK DETECTED! ▄■▀[/COLOR][/B]"
    msg = "[COLOR fffffff00]Check Wifi|Wire|Modem|Telecom provider.[/COLOR]"

    try:
        xbmc.executebuiltin('PlayerControl(Stop)')
        xbmc.executebuiltin('Action(Stop)')
        xbmc.executebuiltin('Dialog.Close(all,true)')
        xbmc.executebuiltin(f'Notification("{title}", "{msg}", 14000, "{icon}")')

        if os.path.exists(sound):
            subprocess.run(
                [
                    'kodi-send',
                    f'--action=PlayMedia("{sound}", 1)'
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            xbmc.executebuiltin('PlayAction(rightclick)')

    except (ImportError, Exception):
        try:
            subprocess.run(
                [
                    'kodi-send',
                    '--action=PlayerControl(Stop);Action(Stop);Dialog.Close(all,true)'
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            subprocess.run(
                [
                    'kodi-send',
                    f'--action=Notification("{title}", "{msg}", 14000, "{icon}")'
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if os.path.exists(sound):
                subprocess.run(
                    [
                        'kodi-send',
                        f'--action=PlayMedia("{sound}", 1)'
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception:
            pass

    log_message("Service: NO INTERNET CONNECTION DETECTED! Check Wifi|Wire|Modem|Telecom provider.", 3)


def watchdog_logic():
    global LAST_INTERFACE, BLACKOUT_ALERTED

    eth_link = is_physically_connected("eth0")
    wifi_link = is_physically_connected("wlan0")

    if not eth_link and not wifi_link:
        time.sleep(2.0)
        eth_link = is_physically_connected("eth0")
        wifi_link = is_physically_connected("wlan0")

        if not eth_link and not wifi_link:
            if not BLACKOUT_ALERTED:
                log_message("Service: TOTAL PHYSICAL DISCONNECT. Triggering Blackout UI.", 3)
                subprocess.run(['pkill', '-f', HELPER_SCRIPT], check=False)
                threading.Thread(target=trigger_blackout_ui, daemon=True).start()
                BLACKOUT_ALERTED = True
            return

    if BLACKOUT_ALERTED:
        log_message("Service: Physical connection restored.", 1)

        if os.path.exists('/tmp/vpn_blackout_active.lock'):
            try:
                os.remove('/tmp/vpn_blackout_active.lock')
            except Exception as e:
                log_message(f"Error removing blackout lock file: {e}", 3)

        BLACKOUT_ALERTED = False

    current_iface = get_active_interface()
    wg0_active = current_iface and ("vpn" in current_iface.lower() or "wg" in current_iface.lower())

    if wg0_active:
        LAST_INTERFACE = current_iface
    else:
        should_be_active = os.path.exists(STATE_FILE) and not os.path.exists(INTENTIONAL_FILE)

        if should_be_active:
            log_message("Service: Internet detected but Tunnel missing. Triggering Helper...", 1)
            subprocess.run(["ip", "route", "flush", "cache"], check=False)
            subprocess.Popen([sys.executable, HELPER_SCRIPT])
            time.sleep(WATCHDOG_SETTLE_DELAY / 1000.0)
            return

    eth_online, wifi_online = check_interface_status()

    if eth_online and current_iface == "wlan0":
        log_message("Service: Ethernet detected. Prioritizing eth0 over wlan0...", 0)
        subprocess.run(["ip", "route", "del", "default", "dev", "wlan0"], stderr=subprocess.DEVNULL, check=False)
        if SAVED_GATEWAY:
            subprocess.run(["ip", "route", "replace", "default", "via", SAVED_GATEWAY, "dev", "eth0"], check=False)

        subprocess.Popen([sys.executable, HELPER_SCRIPT])
        time.sleep(WATCHDOG_SETTLE_DELAY / 1000.0)
        return

    if (eth_online or wifi_online) and not current_iface and SAVED_GATEWAY:
        target_dev = "eth0" if eth_online else "wlan0"
        log_message(f"Service: No route found. Forcing {SAVED_GATEWAY} on {target_dev}", 1)
        subprocess.run(["ip", "route", "replace", "default", "via", SAVED_GATEWAY, "dev", target_dev], check=False)
        current_iface = get_active_interface()

    if current_iface in ['eth0', 'wlan0']:
        if LAST_INTERFACE != current_iface:
            if os.path.exists(RETRY_FILE):
                try:
                    os.remove(RETRY_FILE)
                except Exception as e:
                    log_message(f"Interface change cleanup error: {e}", 3)
            LAST_INTERFACE = current_iface


if __name__ == "__main__":

    while SAVED_GATEWAY is None:
        SAVED_GATEWAY = get_default_gateway()
        if SAVED_GATEWAY:
            break

        if not BLACKOUT_ALERTED:
            threading.Thread(target=trigger_blackout_ui, daemon=True).start()
            BLACKOUT_ALERTED = True

        log_message("Service: Waiting for gateway...", 2)
        time.sleep(SHIELD_SLEEP_DELAY / 1000.0)

    BLACKOUT_ALERTED = False
    LAST_INTERFACE = get_active_interface()
    log_message(f"Service: Initialized on {LAST_INTERFACE}. Monitoring started.", 1)

    shield_logged = False

    while True:
        if os.path.exists("/tmp/vpn_manual_active.txt") or os.path.exists("/tmp/vpn_intentional_disconnect.txt"):
            if not shield_logged:
                log_message("Service: SHIELD ACTIVE - SESSION FOUND. Pausing watchdog.", 0)
                shield_logged = True
        else:
            if shield_logged:
                log_message("Service: Shield cleared. Resuming watchdog operation.", 0)
            shield_logged = False
            watchdog_logic()

        time.sleep(WATCHDOG_HEARTBEAT / 1000.0)
