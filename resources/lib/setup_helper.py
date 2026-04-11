import os
import shutil
import subprocess
import xbmc
import xbmcgui
import xbmcaddon

def perform_cleanup(silent=False):
    import os, subprocess, xbmc, xbmcgui
    
    keymap = '/storage/.kodi/userdata/keymaps/wireguard_manager_key.xml'
    service_file = '/storage/.config/system.d/vpn-watchdog.service'
    wg_config_path = '/storage/.config/wireguard/'
    
    try:
        if os.path.exists(keymap):
            os.remove(keymap)

        if os.path.exists(wg_config_path):
            for filename in os.listdir(wg_config_path):
                if filename.startswith("nord_") and filename.endswith(".config"):
                    try:
                        os.remove(os.path.join(wg_config_path, filename))
                        xbmc.log(f"WG Manager Cleanup: Removed {filename}", xbmc.LOGINFO)
                    except:
                        pass

        if os.path.exists(service_file):
            subprocess.run(["systemctl", "stop", "vpn-watchdog.service"], check=False)
            subprocess.run(["systemctl", "disable", "vpn-watchdog.service"], check=False)
            os.remove(service_file)
            subprocess.run(["systemctl", "daemon-reload"], check=False)
            subprocess.run(["systemctl", "restart", "connman"], check=False)

        if not silent:
            xbmcgui.Dialog().ok("Factory Reset", "NordVPN configs, keymaps, and system services successfully removed.")
            
    except Exception as e:
        xbmc.log(f"Cleanup Error: {e}", xbmc.LOGERROR)
'''
def disable_connman_ipv6():
    import subprocess
    updated = False
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                inspect = subprocess.check_output(["connmanctl", "inspect", service_id], text=True)
                if "IPv6.Method = off" not in inspect:
                    subprocess.run(["connmanctl", "config", service_id, "--ipv6", "off"], check=False)
                    updated = True
    except Exception as e:
        import xbmc
        xbmc.log(f"WG Manager: IPv6 Check Error: {e}", xbmc.LOGERROR)
    return updated
'''
def ensure_setup(addon_path, media_path):
    import os, shutil, xbmc, xbmcgui, xbmcaddon
    addon = xbmcaddon.Addon()
    keymap_dest = '/storage/.kodi/userdata/keymaps/wireguard_manager_key.xml'
    keymap_source = os.path.join(addon_path, 'resources', 'keymaps', 'wireguard_manager_key.xml')
    keymap_installed = False
    if not os.path.exists(keymap_dest) or addon.getSettingBool("first_run"):
        try:
            if os.path.exists(keymap_source):
                if not os.path.exists(os.path.dirname(keymap_dest)):
                    os.makedirs(os.path.dirname(keymap_dest))
                shutil.copy2(keymap_source, keymap_dest)
                addon.setSettingBool("first_run", False)
                keymap_installed = True
        except Exception as e:
            xbmc.log(f"Setup Error: {e}", xbmc.LOGERROR)

    if keymap_installed:
        if xbmcgui.Dialog().yesno("Restart Required", 
            "Keymaps installed. Restart Kodi now to activate them?"):
            xbmc.executebuiltin('RestartApp')
            return True

    ipv6_fixed = disable_connman_ipv6()
    token_added = False
    if addon.getSetting("vpn_token") == "":
        choice = xbmcgui.Dialog().select("NordVPN Token Required", [
            "Import Token from File (Recommended)",
            "Enter Token Manually",
            "Skip for Now"
        ])
        if choice == 0:
            xbmc.executebuiltin('RunScript(service.wireguard.manager,import_token)')
            return True 
        elif choice == 1:
            keyboard = xbmc.Keyboard("", "Enter NordVPN Token", False)
            keyboard.doModal()
            if keyboard.isConfirmed() and keyboard.getText():
                addon.setSetting("vpn_token", keyboard.getText())
                token_added = True

    if token_added or ipv6_fixed:
        msg = "Leak protection & Token updated." if token_added and ipv6_fixed else \
              "IPv6 Leak Protection applied." if ipv6_fixed else "Token saved."
        xbmcgui.Dialog().notification("WG Manager", msg, xbmcgui.NOTIFICATION_INFO, 5000)
        return True

    return False
