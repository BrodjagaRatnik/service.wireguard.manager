import os
import shutil
import subprocess
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
from logger import log_message

def perform_cleanup(silent=False):
    keymap = xbmcvfs.translatePath('special://userdata/keymaps/wireguard_manager_key.xml')
    service_file = '/storage/.config/system.d/vpn-watchdog.service'
    connman_config = '/storage/.config/connman_main.conf'
    wg_config_path = '/storage/.config/wireguard/'
    template_file = os.path.join(wg_config_path, 'template.config')
    
    try:
        log_message("Starting factory reset cleanup...")

        if os.path.exists(keymap):
            os.remove(keymap)
            log_message(f"Removed keymap: {keymap}")

        if os.path.exists(connman_config):
            os.remove(connman_config)
            log_message("Removed connman_main.conf")

        if os.path.exists(wg_config_path):
            if os.path.exists(template_file):
                os.remove(template_file)
                log_message("Removed WireGuard template.config")

            for filename in os.listdir(wg_config_path):
                if filename.startswith("nord_") and filename.endswith(".config"):
                    try:
                        os.remove(os.path.join(wg_config_path, filename))
                        log_message(f"Cleanup: Removed config {filename}")
                    except:
                        pass

        if os.path.exists(service_file):
            log_message("Disabling and removing vpn-watchdog.service")
            subprocess.run(["systemctl", "stop", "vpn-watchdog.service"], check=False)
            subprocess.run(["systemctl", "disable", "vpn-watchdog.service"], check=False)
            os.remove(service_file)
            subprocess.run(["systemctl", "daemon-reload"], check=False)

        if not silent:
            xbmcgui.Dialog().ok("WireGuard Manager", "All configs, templates, and services successfully removed.")
            
    except Exception as e:
        log_message(f"Cleanup Error: {e}", xbmc.LOGERROR)

def ensure_setup(addon_path, media_path):
    addon = xbmcaddon.Addon()
    keymap_dest = xbmcvfs.translatePath('special://userdata/keymaps/wireguard_manager_key.xml')
    keymap_source = os.path.join(addon_path, 'resources', 'keymaps', 'wireguard_manager_key.xml')
    
    wg_config_path = '/storage/.config/wireguard/'
    template_dest = os.path.join(wg_config_path, 'template.config')
    template_source = os.path.join(addon_path, 'resources', 'data', 'template.config')
    
    service_dest = '/storage/.config/system.d/vpn-watchdog.service'
    service_source = os.path.join(addon_path, 'resources', 'data', 'vpn-watchdog.service')
    
    connman_dest = '/storage/.config/connman_main.conf'
    connman_source = os.path.join(addon_path, 'resources', 'data', 'connman_main.conf')
    
    setup_updated = False

    if not os.path.exists(connman_dest):
        try:
            log_message("ConnMan config missing. Installing connman_main.conf...")
            if os.path.exists(connman_source):
                shutil.copy2(connman_source, connman_dest)
                subprocess.run(["systemctl", "restart", "connman"], check=False)
                log_message("connman_main.conf installed and ConnMan restarted.")
                setup_updated = True
        except Exception as e:
            log_message(f"ConnMan Setup Error: {e}", xbmc.LOGERROR)

    if not os.path.exists(service_dest):
        try:
            log_message("Service file missing. Installing vpn-watchdog.service...")
            if not os.path.exists(os.path.dirname(service_dest)):
                os.makedirs(os.path.dirname(service_dest))
            if os.path.exists(service_source):
                shutil.copy2(service_source, service_dest)
                subprocess.run(["systemctl", "daemon-reload"], check=False)
                subprocess.run(["systemctl", "enable", "vpn-watchdog.service"], check=False)
                subprocess.run(["systemctl", "start", "vpn-watchdog.service"], check=False)
                log_message("vpn-watchdog.service installed and started.")
                setup_updated = True
        except Exception as e:
            log_message(f"Service Install Error: {e}", xbmc.LOGERROR)

    if not os.path.exists(template_dest):
        try:
            log_message("Copying WireGuard template.config...")
            if not os.path.exists(wg_config_path):
                os.makedirs(wg_config_path)
            if os.path.exists(template_source):
                shutil.copy2(template_source, template_dest)
                log_message("template.config copied to wireguard folder.")
        except Exception as e:
            log_message(f"Template Copy Error: {e}", xbmc.LOGERROR)

    keymap_installed = False
    if not os.path.exists(keymap_dest) or addon.getSettingBool("first_run"):
        try:
            log_message("Installing WireGuard Manager keymaps...")
            if os.path.exists(keymap_source):
                dest_dir = os.path.dirname(keymap_dest)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                shutil.copy2(keymap_source, keymap_dest)
                addon.setSettingBool("first_run", False)
                keymap_installed = True
        except Exception as e:
            log_message(f"Keymap Setup Error: {e}", xbmc.LOGERROR)

    if keymap_installed:
        if xbmcgui.Dialog().yesno("WireGuard Manager", 
            "Keymaps installed. Restart Kodi now to activate them?"):
            log_message("User triggered RestartApp for keymaps.")
            xbmc.executebuiltin('RestartApp')
            return True

    if addon.getSetting("vpn_token") == "":
        log_message("No VPN Token found. Prompting user...")
        choice = xbmcgui.Dialog().select("WireGuard Manager: Token Required", [
            "Import Token from File (Recommended)",
            "Enter Token Manually",
            "Exit"
        ])
        
        if choice == 0:
            token_file = xbmcgui.Dialog().browse(1, "Select Token File", "files", ".txt|.key")
            if token_file:
                try:
                    with open(token_file, 'r') as f:
                        token_content = f.read().strip()
                        addon.setSetting("vpn_token", token_content)
                        log_message("VPN Token imported from file successfully.")
                        xbmcgui.Dialog().notification("WireGuard Manager", "Token saved.", xbmcgui.NOTIFICATION_INFO, 5000)
                        return True
                except Exception as e:
                    log_message(f"Token Read Error: {e}", xbmc.LOGERROR)
            return False

        elif choice == 1:
            keyboard = xbmc.Keyboard("", "Enter NordVPN Token", False)
            keyboard.doModal()
            if keyboard.isConfirmed() and keyboard.getText():
                addon.setSetting("vpn_token", keyboard.getText())
                log_message("VPN Token entered manually.")
                xbmcgui.Dialog().notification("WireGuard Manager", "Token saved.", xbmcgui.NOTIFICATION_INFO, 5000)
                return True
        
        elif choice == 2 or choice == -1:
            log_message("User exited token setup.")
            return "EXIT_SIGNAL"

    return setup_updated
