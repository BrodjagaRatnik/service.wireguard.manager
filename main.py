import sys
import os
import xbmc
import xbmcgui
import xbmcaddon

ADDON = xbmcaddon.Addon()
TOKEN = ADDON.getSettings().getString("vpn_token")
ADDON_PATH = ADDON.getAddonInfo('path')
MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
SHELL_SCRIPT = os.path.join(ADDON_PATH, 'resources', 'update_servers.sh')
SERVICE_NAME = "vpn-watchdog.service"
SOURCE_SERVICE = os.path.join(ADDON_PATH, 'resources', 'data', SERVICE_NAME)
DEST_SERVICE = os.path.join('/storage/.config/system.d/', SERVICE_NAME)

def log_message(msg, level=xbmc.LOGINFO):
    xbmc.log(f"WG_MANAGER_SCRIPT: {msg}", level)

if __name__ == '__main__':
    sys.path.append(os.path.join(ADDON_PATH, 'resources', 'lib'))

    args_str = "|".join(sys.argv).lower()
    log_message(f"Arguments Received: {args_str}")

    try:
        from setup_helper import ensure_setup, perform_cleanup
        from vpn_core import install_service, run_update
    except ImportError as e:
        log_message(f"Critical Import Error: {e}", xbmc.LOGERROR)
        sys.exit()

    if "reinstall" in args_str:
        log_message("Action Triggered: Reinstalling Service...")
        try:
            install_service(SOURCE_SERVICE, DEST_SERVICE, SERVICE_NAME, MEDIA_PATH)
            xbmcgui.Dialog().notification("WG Manager", "Reinstall Complete", os.path.join(MEDIA_PATH, 'update_ok.png'), 3000)
        except Exception as e:
            log_message(f"Reinstall Failed: {e}", xbmc.LOGERROR)
        sys.exit()

    if any(cmd in args_str for cmd in ["status", "restart", "clear"]):
        import service_control
        service_control.control_service()
        sys.exit()

    elif "regen" in args_str:
        run_update(SHELL_SCRIPT, TOKEN)
        if "manual" not in args_str:
            xbmcgui.Dialog().notification("VPN Manager", "Servers Updated", os.path.join(MEDIA_PATH, 'update_ok.png'), 3000)
            sys.exit()

    elif "cleanup" in args_str:
        perform_cleanup()
        sys.exit()

    elif "import_token" in args_str:
        token_file = xbmcgui.Dialog().browse(1, "Select Token File", "files", ".txt|.key")
        if token_file:
            with open(token_file, 'r') as f:
                ADDON.setSetting("vpn_token", f.read().strip())
        sys.exit()

    if ensure_setup(ADDON_PATH, MEDIA_PATH):
        sys.exit()

    if "manual" in args_str or len(sys.argv) == 1:
        if not TOKEN or TOKEN.strip() == "":
            xbmc.executebuiltin('Addon.OpenSettings(service.wireguard.manager)')
        else:
            try:
                import vpn_menu
                vpn_menu.show_menu(MEDIA_PATH, SHELL_SCRIPT, TOKEN)
            except Exception as e:
                log_message(f"Menu Load Error: {e}", xbmc.LOGERROR)
