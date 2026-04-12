import sys
import os
import subprocess

try:
    import xbmc
    import xbmcgui
    import xbmcaddon
    KODI_MODE = True
    ADDON = xbmcaddon.Addon('service.wireguard.manager')
    ADDON_PATH = ADDON.getAddonInfo('path')

    sys.path.append(os.path.join(ADDON_PATH, 'resources', 'lib'))
    from logger import log_message
    
    MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
    ICON_OK = os.path.join(MEDIA_PATH, 'update_ok.png')
    ICON_ERR = os.path.join(MEDIA_PATH, 'error.png')
except ImportError:
    KODI_MODE = False

def log_event(msg, level=xbmc.LOGINFO if KODI_MODE else 1):
    if KODI_MODE:
        log_message(f"Control: {msg}", level)
    else:
        print(f"CONTROL: {msg}")

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
            log_event("Restarting watchdog service...")
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

            log_event(f"Status check: {real_status}")
            if KODI_MODE:
                xbmcgui.Dialog().notification("Watchdog", f"Status: {real_status}", icon, 3000)

        elif action == "clear":
            if KODI_MODE and not xbmcgui.Dialog().yesno("Confirm Reset", "Delete all VPN configurations?"):
                return

            log_event("Clearing configs and disconnecting VPN...")
            subprocess.run("connmanctl services | grep -E 'NordVPN|vpn_' | awk '{print $NF}' | xargs -I {} connmanctl disconnect {}", shell=True)
            subprocess.run("rm -f /storage/.config/wireguard/*.config", shell=True)

            if os.path.exists("/tmp/vpn_manager_active.txt"):
                os.remove("/tmp/vpn_manager_active.txt")
                
            subprocess.run(["systemctl", "restart", "connman-vpn"])
            
            if KODI_MODE:
                xbmcgui.Dialog().notification("VPN Manager", "All configs cleared", ICON_OK, 3000)
                xbmc.executebuiltin('Container.Refresh')

    except Exception as e:
        log_event(f"Control Error ({action}): {e}", xbmc.LOGERROR if KODI_MODE else 2)
        if KODI_MODE:
            xbmcgui.Dialog().notification("Error", f"{action.capitalize()} failed", ICON_ERR, 4000)

if __name__ == "__main__":
    control_service()
