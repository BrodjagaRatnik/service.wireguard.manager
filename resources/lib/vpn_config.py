""" resources/lib/vpn_config.py """
import sys

if 'utils' in sys.modules and 'service.wireguard.manager' not in str(sys.modules.get('utils')):
    del sys.modules['utils']

import os
from logger import log_message

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


def is_pi5():
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return 'raspberry pi 5' in f.read().lower()
    except Exception as e:
        log_message(f"Hardware check error: {e}", 3)
        return False


PI5 = is_pi5()


""" vpn_ops.py """
PROP_SYNC_DELAY = 100
""" Stops Kodi from getting confused if two updates happen at once """
OS_RELEASE_DELAY = 1500 if PI5 else 2000
""" Gives the system time to completely kill the old VPN tunnel """
CONN_POLL_INTERVAL = 500 if PI5 else 1000
""" Fast-check to catch the exact second the VPN connects """
ROUTE_PROP_DELAY = 500 if PI5 else 1000
""" Waiting for the internet path to be ready for use """

""" vpn_ops.py & reconnect_helper.py """
DHCP_RECOVERY_DELAY = 1200 if PI5 else 2400
"""
When the Pi is "awake" but it doesn't have an IP address yet. This constant tells the script how long to wait for
Router to assign a local IP (DHCP) before it tries to restart the VPN.
"""
VPN_CONNECTION_TIMEOUT = 10000 if PI5 else 20000
"""
De maximale tijd (ms) die de progress bar wacht op een succesvolle verbinding.
Pi 5 is razendsnel (20s is ruim), Pi 4 heeft meer tijd nodig (30s veiligheidsmarge).
"""

""" service_launcher.py & service.py """
WATCHDOG_HEARTBEAT = 1000 if PI5 else 2500
""" The heartbeat that checks if your internet cable is plugged in """
WATCHDOG_SETTLE_DELAY = 11000 if PI5 else 22000
"""
Stops the script from restarting the VPN too fast during a network crash.
"""

""" service_launcher.py & service.py & reconnect_helper.py """
WATCHDOG_RECOVERY_DELAY = 2000 if PI5 else 2500
""" Prevents a restart if the VPN tunnel just blips for a second """

""" reconnect_helper.py """
HELPER_MAX_WAIT = 4000 if PI5 else 6000
""" Max seconds to wait for wg0 before giving up on an attempt """
HELPER_PIA_RECOVERY_DELAY = 2500 if PI5 else 3500
"""
FIX: Safety time delay (ms) applied strictly to PIA server clusters
to let routing gateways stabilize before running handshake handshakes.
"""

""" service.py """
SHIELD_SLEEP_DELAY = 5000 if PI5 else 5000
"""
How long the Watchdog waits when the Reconnect Helper is working.
"""

""" service_control.py """
SYSTEMD_POLL_DELAY = 300 if PI5 else 400
""" Wait for Linux to finish the Start/Stop command """

""" vpn_core.py """
SERVICE_INIT_DELAY = 400 if PI5 else 600
""" Wait for the system to fully 'birth' the new VPN process """

""" vpn_menu.py """
UI_BUFFER_DELAY_MENU = 100 if PI5 else 400
""" Give Kodi time to process the button click animation before connecting """

""" Central Provider Mapping
./resources/lib/service_launcher.py
./resources/lib/vpn_ops.py
./resources/lib/list_assets.py
./resources/lib/main_launcher.py
./resources/lib/service_control.py
./resources/lib/network_utils.py
./resources/lib/vpn_menu.py

Below need editing if adding new VPN provider!
./resources/scripts/update_vpn.py (if provider_idx == 0:)
./resources/lib/country_selector.py (if provider == 0:)
./resources/lib/vpn_core.py (if provider == 0:)
./resources/lib/setup_helper.py (prefixes = ("nord_", "pia_", "custom_", "template"))
"""
PROVIDER_MAP = {
    0: {
        "name": "NordVPN",
        "api_url": "https://api.nordvpn.com/v1/servers/countries",
        "setting": "vpn_token",
        "countries_setting": "selected_countries",
        "prefix": "nord_",
        "label": "Nord Token"
    },
    1: {
        "name": "PIA",
        "api_url": "https://serverlist.piaservers.net/vpninfo/servers/v6",
        "setting": "pia_pass",
        "user_setting": "pia_user",
        "countries_setting": "selected_countries_pia",
        "prefix": "pia_",
        "label": "PIA Credentials"
    },
    99: {
        "name": "Custom",
        "setting": "custom_path",
        "prefix": "custom_",
        "label": "Config File"
    }
}

try:
    import xbmc
    KODI_VERSION = xbmc.getInfoLabel('System.BuildVersion').split('.')[0]
    HAS_KODI = True

    from providers import nordvpn, pia, custom
    PROVIDER_MAP[0]["module"] = nordvpn
    PROVIDER_MAP[1]["module"] = pia
    PROVIDER_MAP[99]["module"] = custom

except Exception as e:
    HAS_KODI = False

    err_msg = str(e)
    if "No module named 'xbmc'" in err_msg or "No module named 'xbmcaddon'" in err_msg:
        log_message("Background daemon initialization active (Kodi env absent).", 0)
    else:
        log_message(f"CRITICAL: vpn_config initialization failed: {err_msg}", 3)
