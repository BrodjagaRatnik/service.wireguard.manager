''' ./resources/lib/main_launcher.py '''
import sys, os, xbmc, xbmcgui, xbmcaddon, xbmcvfs

def run():
    ADDON = xbmcaddon.Addon('service.wireguard.manager')
    ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
    LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
    if LIB_PATH not in sys.path:
        sys.path.append(LIB_PATH)
        
    from logger import log_message

    TOKEN = ADDON.getSetting("vpn_token")
    MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
    SERVICE_NAME = "vpn-watchdog.service"
    SOURCE_SERVICE = os.path.join(ADDON_PATH, 'resources', 'data', SERVICE_NAME)
    DEST_SERVICE = os.path.join('/storage/.config/system.d/', SERVICE_NAME)

    try:
        from setup_helper import ensure_setup
        if ensure_setup(ADDON_PATH, MEDIA_PATH):
            log_message("Setup check triggered a system action. Exiting.", 0)
            return
    except Exception as e:
        log_message(f"Main: Critical Setup Error {e}", 3)

    args_str = "|".join(sys.argv).lower()

    if len(sys.argv) > 1 and ("resources/lib" in args_str or args_str.endswith(".py")):
        if "list_assets.py" in args_str:
            log_message("Main: Launching Setup Wizard...", 1)
            try:
                import list_assets
                list_assets.run_wizard()
            except Exception as e:
                log_message(f"Main: Wizard Error {e}", 3)
        return

    if any(cmd in args_str for cmd in ["status", "restart", "clear", "reinstall", "regen", "cleanup", "import_token"]):
        log_message(f"Processing Command: {args_str}", 1)
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
                run_update(TOKEN)
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
            log_message(f"Main: Execution Error on {args_str}: {e}", 3)
            xbmcgui.Dialog().ok("Error", f"Command failed: {e}")
        return

    if "manual" in args_str or len(sys.argv) <= 1:
        if not TOKEN or TOKEN.strip() == "":
            log_message("Main: No token found, redirecting to settings.", 0)
            xbmc.executebuiltin('Addon.OpenSettings(service.wireguard.manager)')
        else:
            try:
                import vpn_menu
                vpn_menu.show_menu(MEDIA_PATH, TOKEN)
            except Exception as e:
                log_message(f"Main: Menu Load Error {e}", 3)
                xbmc.executebuiltin('Addon.OpenSettings(service.wireguard.manager)')
