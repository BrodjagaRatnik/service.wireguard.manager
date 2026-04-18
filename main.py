import sys
import os
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
sys.path.append(LIB_PATH)
from logger import log_message

TOKEN = ADDON.getSettings().getString("vpn_token")
MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
SHELL_SCRIPT = os.path.join(ADDON_PATH, 'resources', 'update_servers.sh')
SERVICE_NAME = "vpn-watchdog.service"
SOURCE_SERVICE = os.path.join(ADDON_PATH, 'resources', 'data', SERVICE_NAME)
DEST_SERVICE = os.path.join('/storage/.config/system.d/', SERVICE_NAME)

if __name__ == '__main__':
    try:
        from setup_helper import ensure_setup
        if ensure_setup(ADDON_PATH, MEDIA_PATH):
            log_message("Setup check triggered a system action (Restart/Redirect). Exiting.", xbmc.LOGDEBUG)
            sys.exit(0)
    except Exception as e:
        log_message(f"Critical Setup Error: {e}", xbmc.LOGERROR)

    args_str = "|".join(sys.argv).lower()

    if len(sys.argv) > 1 and ("resources/lib" in args_str or args_str.endswith(".py")):
        if "list_assets.py" in args_str:
            log_message("Launching Setup Wizard...", xbmc.LOGINFO)
            try:
                import list_assets
                list_assets.run_wizard()
            except Exception as e:
                log_message(f"Wizard Error: {e}", xbmc.LOGERROR)
        sys.exit(0)

    if any(cmd in args_str for cmd in ["status", "restart", "clear", "reinstall", "regen", "cleanup", "import_token"]):
        log_message(f"Processing Command: {args_str}", xbmc.LOGINFO)
        try:
            if "reinstall" in args_str:
                from vpn_core import install_service
                install_service(SOURCE_SERVICE, DEST_SERVICE, SERVICE_NAME, MEDIA_PATH)
                xbmcgui.Dialog().notification("WireGuard Manager", "Reinstall Complete", os.path.join(MEDIA_PATH, 'update_ok.png'), 3000)
            
            elif any(cmd in args_str for cmd in ["status", "restart", "clear"]):
                import service_control
                service_control.control_service()
            
            elif "regen" in args_str:
                from vpn_core import run_update
                run_update(SHELL_SCRIPT, TOKEN)
                if "manual" not in args_str:
                    xbmcgui.Dialog().notification("VPN Manager", "Servers Updated", os.path.join(MEDIA_PATH, 'update_ok.png'), 3000)
            
            elif "cleanup" in args_str:
                from setup_helper import perform_cleanup
                perform_cleanup()
            
            elif "import_token" in args_str:
                token_file = xbmcgui.Dialog().browse(1, "Select Token File", "files", ".txt|.key")
                if token_file:
                    with open(token_file, 'r') as f:
                        new_token = f.read().strip()
                        ADDON.setSetting("vpn_token", new_token)
                        TOKEN = new_token
        
        except Exception as e:
            log_message(f"Execution Error on {args_str}: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("Error", f"Command failed: {e}")
        
        sys.exit(0)

    if "manual" in args_str or len(sys.argv) <= 1:
        if not TOKEN or TOKEN.strip() == "":
            log_message("No token found, redirecting to settings.", xbmc.LOGDEBUG)
            xbmc.executebuiltin('Addon.OpenSettings(service.wireguard.manager)')
        else:
            try:
                import vpn_menu
                vpn_menu.show_menu(MEDIA_PATH, SHELL_SCRIPT, TOKEN)
            except Exception as e:
                log_message(f"Menu Load Error: {e}", xbmc.LOGERROR)
                xbmc.executebuiltin('Addon.OpenSettings(service.wireguard.manager)')
