import sys
import os
import subprocess
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = '/storage/.kodi/temp/wireguard_manager.log'

try:
    import xbmc
    import xbmcgui
    import xbmcaddon
    KODI_MODE = True
    ADDON = xbmcaddon.Addon()
    ADDON_PATH = ADDON.getAddonInfo('path')
    MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
    ICON_OK = os.path.join(MEDIA_PATH, 'update_ok.png')
    ICON_ERR = os.path.join(MEDIA_PATH, 'error.png')
except ImportError:
    KODI_MODE = False

logger = logging.getLogger("WG_Control")
if not logger.handlers:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=1)
    handler.setFormatter(logging.Formatter('%(asctime)s - CONTROL - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def log_important(msg):
    logger.info(msg)
    if KODI_MODE:
        xbmc.log(f"[service.wireguard.manager] {msg}", xbmc.LOGINFO)
    else:
        print(f"LOG (IMP): {msg}")

def log_debug(msg):
    if KODI_MODE:
        xbmc.log(f"[service.wireguard.manager] {msg}", xbmc.LOGINFO)
    else:
        print(f"LOG (DEBUG): {msg}")

def control_service():
    service_name = "vpn-watchdog.service"
    raw_args = "|".join(sys.argv).lower()
    
    if "restart" in raw_args:
        action = "restart"
    elif "clear" in raw_args:
        action = "clear"
    else:
        action = "status"

    try:
        if action == "restart":
            log_important("Restarting watchdog service...")
            subprocess.run(["systemctl", "restart", service_name], check=True)
            if KODI_MODE:
                xbmcgui.Dialog().notification("Watchdog", "Service Restarted", ICON_OK, 3000)

        elif action == "status":
            if not os.path.exists(f'/storage/.config/system.d/{service_name}'):
                real_status = "Not Installed"
                icon = ICON_ERR
            else:
                for _ in range(5): 
                    result = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)
                    real_status = result.stdout.strip()
                    if real_status == "active":
                        break
                    if KODI_MODE: xbmc.sleep(400)
                
                icon = ICON_OK if real_status == "active" else ICON_ERR
                if real_status == "activating": real_status = "Initializing..."

            if real_status == "active":
                log_debug(f"Status check: {real_status}")
            else:
                log_important(f"Status alert: {real_status}")

            if KODI_MODE:
                xbmcgui.Dialog().notification("Watchdog", f"Status: {real_status}", icon, 3000)

        elif action == "clear":
            if KODI_MODE and not xbmcgui.Dialog().yesno("Confirm Reset", "Delete all NordVPN configurations?"):
                return
            
            log_important("Clearing configs and disconnecting VPN...")
            subprocess.run("connmanctl services | grep NordVPN | awk '{print $NF}' | xargs -I {} connmanctl disconnect {}", shell=True)
            subprocess.run("rm -f /storage/.config/wireguard/nord_*.config", shell=True)
            subprocess.run(["systemctl", "restart", "connman-vpn"])
            
            if KODI_MODE:
                xbmcgui.Dialog().notification("VPN Manager", "All configs cleared", ICON_OK, 3000)
                xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        log_important(f"Control Error ({action}): {e}")
        if KODI_MODE:
            xbmcgui.Dialog().notification("Error", f"{action.capitalize()} failed", ICON_ERR, 4000)

if __name__ == "__main__":
    control_service()
