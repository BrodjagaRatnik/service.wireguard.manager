import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, sys, time, subprocess
from vpn_config import *

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
addon_path = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
lib_path = os.path.join(addon_path, 'resources', 'lib')
if lib_path not in sys.path: sys.path.insert(0, lib_path)

from vpn_ops import disconnect_vpn, connect_vpn
from logger import log_message

if xbmcgui.Window(10000).getProperty('vpn_intentional_disconnect') == 'true':
    log_message("Helper: Intentional disconnect detected. Aborting reconnect.")
    sys.exit()

state_path = "/tmp/vpn_manager_active.txt"
vpn_name = None
if os.path.exists(state_path):
    with open(state_path, "r") as f: vpn_name = f.read().strip()

if not vpn_name or vpn_name.lower() == "true":
    vpn_name = xbmcgui.Window(10000).getProperty('vpn_manual_session')

if not vpn_name or vpn_name.lower() == "true": sys.exit()

disconnect_vpn(silent=True)
log_message(f"WAIT_START: Cleanup Cool-off ({CLEANUP_COOLING_DELAY}ms) | PURPOSE: {CLEANUP_COOLING_PURPOSE}", xbmc.LOGDEBUG)
time.sleep(CLEANUP_COOLING_DELAY / 1000.0)
log_message("WAIT_END: Cleanup Cool-off", xbmc.LOGDEBUG)

try:
    out = subprocess.check_output(["connmanctl", "services"], text=True)
    target_sid = next((l.split()[-1] for l in out.splitlines() if vpn_name.replace(' ', '_') in l), None)
    if target_sid: connect_vpn(vpn_name, target_sid)
except Exception as e: log_message(f"Helper Error: {e}")
