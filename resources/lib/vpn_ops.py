''' ./resources/lib/vpn_ops.py '''
import os
import subprocess
import time
from logger import log_message
from vpn_config import (
    DHCP_RECOVERY_DELAY,
    OS_RELEASE_DELAY,
    PROP_SYNC_DELAY,
    PROVIDER_MAP,
)
from network_utils import (
    set_secure_dns,
    enable_connman_ipv6,
    get_default_gateway
)

try:
    import xbmc
    import xbmcaddon
    import xbmcgui
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

ADDON_ID = 'service.wireguard.manager'

if HAS_KODI:
    _ADDON = xbmcaddon.Addon(ADDON_ID)
    ADDON_PATH = _ADDON.getAddonInfo('path')
else:
    _ADDON = None
    ADDON_PATH = '/storage/.kodi/addons/service.wireguard.manager'

STATE_FILE = "/tmp/vpn_manager_active.txt"
INTENTIONAL_DISCONNECT_FILE = "/tmp/vpn_intentional_disconnect.txt"
ICON_CON = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_connected.png')
ICON_DIS = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_disconnected.png')
ICON_ERROR = os.path.join(ADDON_PATH, 'resources', 'media', 'error.png')
ICON_ERROR_NETWORK = os.path.join(ADDON_PATH, 'resources', 'media', 'router-network-error-alert.png')
ICON_INFO = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')
SOUND = os.path.join(ADDON_PATH, 'resources', 'media', 'error.wav')


def get_active_vpn():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return f.read().strip() or None
        except Exception as e:
            log_message(f"Active VPN state read error: {e}", 3)
            return None
    return None


def set_active_vpn(name):
    try:
        if name:
            with open(STATE_FILE, "w") as f:
                f.write(name.strip())
        elif os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    except Exception as e:
        log_message(f"Operation: State Error {e}", 3)


def disconnect_vpn(silent=False):
    if not silent and HAS_KODI:
        xbmcgui.Window(10000).setProperty('vpn_manual_session', '')

    for path in ['/tmp/vpn_manual_active.txt', '/storage/.kodi/temp/vpn_manual_active.txt']:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                log_message(f"Disconnect error removing {path}: {e}", 3)

    try:
        open(INTENTIONAL_DISCONNECT_FILE, 'w').close()
    except Exception as e:
        log_message(f"Disconnect error creating intentional flag file: {e}", 3)

    if HAS_KODI:
        xbmcgui.Window(10000).setProperty('vpn_intentional_disconnect', 'true')
        xbmcgui.Window(10000).setProperty('vpn_manual_session', '')
        xbmc.sleep(PROP_SYNC_DELAY)
    else:
        time.sleep(PROP_SYNC_DELAY / 1000.0)

    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        p_names = "|".join([p['name'] for p in PROVIDER_MAP.values()])

        for line in out.splitlines():
            if (("vpn_" in line or any(p in line for p in p_names.split('|')))
                    and ("* " in line or "R " in line)):
                subprocess.run(
                    ["connmanctl", "disconnect", line.split()[-1]],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

    except Exception as e:
        log_message(f"Operation: Disconnect Error {e}", 3)

    enable_connman_ipv6()
    set_secure_dns(vpn_active=False)
    set_active_vpn(None)

    if not silent and HAS_KODI:
        title = "[B][COLOR FFDF00FF]▄■ [ VPN Network ] ■▄[/COLOR][/B]"
        msg = "[B]╠══ [COLOR FFDF00FF][ DISCONNECTED ][/COLOR] ══╣[/B]"
        xbmcgui.Dialog().notification(title, msg, ICON_DIS, 4500)

    if HAS_KODI:
        xbmc.sleep(OS_RELEASE_DELAY)
    else:
        time.sleep(OS_RELEASE_DELAY / 1000.0)

    gw = get_default_gateway()
    if not gw:
        log_message("Operation: Default route lost. Attempting restoration...", 0)
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            phys_service = next(
                (
                    line.split()[-1] for line in out.splitlines()
                    if line.startswith(('*', 'R')) and "vpn_" not in line
                ),
                None
            )

            if phys_service:
                subprocess.run(["connmanctl", "config", phys_service, "--ipv4", "dhcp"], check=False)
                log_message(f"Operation: DHCP Recovery ({DHCP_RECOVERY_DELAY}ms)", 0)
                if HAS_KODI:
                    xbmc.sleep(DHCP_RECOVERY_DELAY)
                else:
                    time.sleep(DHCP_RECOVERY_DELAY / 1000.0)
                gw = get_default_gateway()
        except Exception as e:
            log_message(f"Route restoration failure: {e}", 3)

    if gw:
        try:
            out_route = subprocess.check_output(["ip", "route", "show", "default"], text=True)
            route_is_missing = "default" not in out_route
            serv = subprocess.check_output(["connmanctl", "services"], text=True)
            target_dev = "eth0" if "ethernet" in serv else "wlan0"
            subprocess.run(["ip", "route", "replace", "default", "via", gw, "dev", target_dev], check=False)
            if route_is_missing:
                log_message(f"Operation: Route restored via {gw} on {target_dev}", 0)
        except Exception as e:
            log_message(f"Operation: Route Restore Error {e}", 3)

    if HAS_KODI:
        xbmcgui.Window(10000).setProperty('vpn_intentional_disconnect', '')

    if os.path.exists(INTENTIONAL_DISCONNECT_FILE):
        try:
            os.remove(INTENTIONAL_DISCONNECT_FILE)
        except Exception as e:
            log_message(f"Error removing intentional disconnect file: {e}", 1)


def connect_vpn(vpn_name, sid, silent=False):
    import vpn_connector
    import sys
    instance = sys.modules[__name__]
    return vpn_connector.connect_vpn(vpn_name, sid, instance, silent=silent)
