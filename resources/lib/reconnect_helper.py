import os, sys, time, subprocess

try:
    import xbmc, xbmcgui, xbmcaddon, xbmcvfs
    KODI_AVAILABLE = True
except ImportError:
    from unittest.mock import MagicMock
    mock_xbmc = MagicMock()
    mock_xbmc.LOGINFO, mock_xbmc.LOGDEBUG, mock_xbmc.LOGERROR = 1, 0, 2
    sys.modules['xbmc'] = mock_xbmc
    sys.modules['xbmcgui'] = MagicMock()
    sys.modules['xbmcaddon'] = MagicMock()
    sys.modules['xbmcvfs'] = MagicMock()
    KODI_AVAILABLE = False

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')
if LIB_PATH not in sys.path: sys.path.insert(0, LIB_PATH)

try:
    from vpn_config import *
    from vpn_ops import disconnect_vpn, connect_vpn
    from logger import log_message
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def run_reconnect():
    vpn_name = None
    sid = None
    state_path = "/tmp/vpn_manager_active.txt"

    intentional = 'false'
    if KODI_AVAILABLE:
        intentional = xbmcgui.Window(10000).getProperty('vpn_intentional_disconnect')
    
    if intentional == 'true' or os.path.exists("/tmp/vpn_intentional_disconnect.txt"):
        log_message("Helper: Intentional disconnect detected. Aborting.", xbmc.LOGDEBUG)
        return

    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                vpn_name = f.read().strip()
        except: pass

    if (not vpn_name or vpn_name.lower() == "true") and KODI_AVAILABLE:
        vpn_name = xbmcgui.Window(10000).getProperty('vpn_manual_session')

    if not vpn_name or vpn_name.lower() == "true":
        log_message("Helper: No active VPN session found in state. Aborting.", xbmc.LOGDEBUG)
        return

    log_message(f"Helper: Connection lost to {vpn_name}. Starting cleanup...", xbmc.LOGINFO)
    disconnect_vpn(silent=True)
    
    log_message(f"WAIT_START: Cleanup Cool-off ({CLEANUP_COOLING_DELAY}ms)", xbmc.LOGDEBUG)
    time.sleep(CLEANUP_COOLING_DELAY / 1000.0)
    log_message("WAIT_END: Cleanup Cool-off", xbmc.LOGDEBUG)

    try:
        search_term = vpn_name.replace(' ', '_')
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():
            if search_term in line:
                sid = line.split()[-1]
                break
    except Exception as e:
        log_message(f"Helper Error finding SID: {e}", xbmc.LOGERROR)

    if vpn_name and sid:
        log_message(f"Helper: Reconnecting to {vpn_name} ({sid})...", xbmc.LOGINFO)
        success = connect_vpn(vpn_name, sid)
        if success:
            log_message(f"Helper: Reconnect to {vpn_name} successful.", xbmc.LOGINFO)
        else:
            log_message(f"Helper: Reconnect to {vpn_name} failed.")
    else:
        log_message(f"Helper: Could not find SID for {vpn_name}. Aborting.", xbmc.LOGERROR)

if __name__ == "__main__":
    try:
        run_reconnect()
    except Exception as e:
        log_message(f"Helper Critical Error: {e}", xbmc.LOGERROR)
