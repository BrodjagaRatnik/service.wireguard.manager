""" resources/lib/vpn_config.py """
import os
import sys
from logger import log_message

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


def get_hardware_model():
    try:
        if os.path.exists('/proc/device-tree/model'):
            with open('/proc/device-tree/model', 'r') as f:
                raw_data = f.read()
                clean_string = raw_data.replace('\x00', '')
                return clean_string.lower().strip()
    except Exception as e:
        log_message(f"Hardware check error: {e}", 3)
    return ""


MODEL_STRING = get_hardware_model()
PI5 = 'pi 5' in MODEL_STRING or 'raspberry pi 5' in MODEL_STRING
PI4 = 'pi 4' in MODEL_STRING or 'raspberry pi 4' in MODEL_STRING
PI3 = 'pi 3' in MODEL_STRING or 'raspberry pi 3' in MODEL_STRING
PI2 = 'pi 2' in MODEL_STRING or 'raspberry pi 2' in MODEL_STRING

PROP_SYNC_DELAY = 100
OS_RELEASE_DELAY = 1500 if PI5 else (1800 if PI4 else (2000 if (PI3 or PI2) else 1000))
CONN_POLL_INTERVAL = 500 if PI5 else (600 if PI4 else (400 if (PI3 or PI2) else 250))
ROUTE_PROP_DELAY = 100 if PI5 else (150 if PI4 else (150 if (PI3 or PI2) else 100))
DHCP_RECOVERY_DELAY = 200 if PI5 else (300 if PI4 else (250 if (PI3 or PI2) else 100))
VPN_CONNECTION_TIMEOUT = 3000 if PI5 else (4500 if PI4 else (5500 if (PI3 or PI2) else 2500))
WATCHDOG_HEARTBEAT = 1000 if PI5 else (1500 if PI4 else (1200 if (PI3 or PI2) else 500))
WATCHDOG_SETTLE_DELAY = 5000 if PI5 else (6000 if PI4 else (5000 if (PI3 or PI2) else 2500))
WATCHDOG_RECOVERY_DELAY = 2000 if PI5 else (2500 if PI4 else (2000 if (PI3 or PI2) else 1000))
HELPER_MAX_WAIT = 4000 if PI5 else (5000 if PI4 else (4500 if (PI3 or PI2) else 2500))
SHIELD_SLEEP_DELAY = 5000 if PI5 else (5000 if PI4 else (5000 if (PI3 or PI2) else 2500))
SYSTEMD_POLL_DELAY = 300 if PI5 else (400 if PI4 else (300 if (PI3 or PI2) else 150))
SERVICE_INIT_DELAY = 400 if PI5 else (600 if PI4 else (400 if (PI3 or PI2) else 200))
UI_BUFFER_DELAY_MENU = 50 if PI5 else (100 if PI4 else (100 if (PI3 or PI2) else 50))
CONNMAN_RESTART_DELAY = 100 if PI5 else (150 if PI4 else (100 if (PI3 or PI2) else 50))
SANITY_POLL_INTERVAL = 500 if PI5 else (500 if PI4 else (500 if PI3 or PI2 else 500))
SANITY_SETTLE_DELAY = 500 if PI5 else (1000 if PI4 else (1500 if PI3 or PI2 else 500))
"""
PROP_SYNC_DELAY = Stops Kodi from getting confused if two updates happen at once
OS_RELEASE_DELAY = Gives the system time to completely kill the old VPN tunnel
CONN_POLL_INTERVAL = Fast-check to catch the exact second the VPN connects
ROUTE_PROP_DELAY = Waiting for the internet path to be ready for use
DHCP_RECOVERY_DELAY = When the Pi is "awake" but it doesn't have an IP address yet.
This constant tells the script how long to wait for Router to assign a local IP (DHCP)
before it tries to restart the VPN.
VPN_CONNECTION_TIMEOUT = The maximum time (ms) the progress bar waits for a successful connection.
WATCHDOG_HEARTBEAT = The heartbeat that checks if your internet cable is plugged in
WATCHDOG_SETTLE_DELAY = Stops the script from restarting the VPN too fast during a network crash.
WATCHDOG_RECOVERY_DELAY = Prevents a restart if the VPN tunnel just blips for a second
HELPER_MAX_WAIT = Max seconds to wait for wg0 before giving up on an attempt
SHIELD_SLEEP_DELAY = How long the Watchdog waits when the Reconnect Helper is working.
SYSTEMD_POLL_DELAY = Wait for Linux to finish the Start/Stop command
SERVICE_INIT_DELAY = Wait for the system to fully 'birth' the new VPN process
UI_BUFFER_DELAY_MENU = Give Kodi time to process the button click animation before connecting
CONNMAN_RESTART_DELAY = Network Interface Stabilization & Core System State Sync
SANITY_POLL_INTERVAL = How often the health-check asks the system if the dead VPN interface is gone yet
SANITY_SETTLE_DELAY = The final rest time to let the network clean up before starting the fallback recovery
"""

try:
    import xbmc
    KODI_VERSION = xbmc.getInfoLabel("System.BuildVersion").split(".")
    HAS_KODI = True
except Exception as e:
    HAS_KODI = False
    err_msg = str(e)
    if "No module named 'xbmc'" in err_msg or "No module named 'xbmcaddon'" in err_msg:
        log_message("Background daemon initialization active (Kodi env absent).", 0)
    else:
        log_message(f"CRITICAL: vpn_config initialization failed: {err_msg}", 3)

"""
Central Provider Mapping
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


class LProviderMap(dict):

    def __init__(self, data):
        super().__init__(data)
        self._loaded = False

    def _load_modules(self):
        if not self._loaded and HAS_KODI:
            self._loaded = True
            try:
                from providers import nordvpn, pia, mullvad, custom

                nord_dict = super().__getitem__(0)
                pia_dict = super().__getitem__(1)
                mullvad_dict = super().__getitem__(2)
                custom_dict = super().__getitem__(99)
                nord_dict["module"] = nordvpn
                pia_dict["module"] = pia
                mullvad_dict["module"] = mullvad
                custom_dict["module"] = custom

            except Exception as e:
                self._loaded = False
                log_message(f"Failed to load provider modules dynamically: {e}", 3)

    def __getitem__(self, key):
        self._load_modules()
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._load_modules()
        return super().get(key, default)

    def values(self):
        self._load_modules()
        return super().values()

    def items(self):
        self._load_modules()
        return super().items()


PROVIDER_MAP = LProviderMap({
    0: {
        "name": "NordVPN",
        "api_url": "https://api.nordvpn.com/v1/servers/countries",
        "setting": "vpn_token",
        "countries_setting": "selected_countries",
        "prefix": "nord_",
        "label": "Nord Token",
        "needs_file_check": True,
        "requires_endpoint_route": False
    },
    1: {
        "name": "PIA",
        "api_url": "https://serverlist.piaservers.net/vpninfo/servers/v6",
        "setting": "pia_pass",
        "user_setting": "pia_user",
        "countries_setting": "selected_countries_pia",
        "prefix": "pia_",
        "label": "PIA Credentials",
        "needs_file_check": True,
        "requires_endpoint_route": True
    },
    2: {
        "name": "Mullvad",
        "api_url": "https://api.mullvad.net/public/relays/wireguard/v1/",
        "setting": "mullvad_account",
        "countries_setting": "mullvad_filter",
        "prefix": "mullvad_",
        "label": "Mullvad Account",
        "needs_file_check": True,
        "requires_endpoint_route": False
    },
    99: {
        "name": "Custom",
        "setting": "custom_path",
        "prefix": "custom_",
        "label": "Config File",
        "needs_file_check": False,
        "requires_endpoint_route": False
    }
})
