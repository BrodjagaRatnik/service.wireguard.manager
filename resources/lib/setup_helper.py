import os
import shutil
import subprocess
import xbmc
import xbmcgui
import xbmcaddon

from resources.lib.vpn_core import log

def perform_cleanup(silent=False):
    keymap = '/storage/.kodi/userdata/keymaps/wireguard_manager_key.xml'
    service_file = '/storage/.config/system.d/vpn-watchdog.service'
    
    try:
        if os.path.exists(keymap):
            os.remove(keymap)
            log("Cleanup: Keymap removed")

        if os.path.exists(service_file):
            subprocess.run(["systemctl", "stop", "vpn-watchdog.service"])
            subprocess.run(["systemctl", "disable", "vpn-watchdog.service"])
            os.remove(service_file)
            subprocess.run(["systemctl", "daemon-reload"])
            log("Cleanup: Watchdog service removed")

        if not silent:
            xbmcgui.Dialog().ok("Factory Reset", "System files removed.\nSettings inside Kodi remain.")
            
    except Exception as e:
        log(f"Cleanup Error: {e}", xbmc.LOGERROR)

def ensure_setup(addon_path, media_path):

    import os
    import shutil
    import xbmc
    import xbmcgui
    import xbmcaddon

    addon = xbmcaddon.Addon()

    lib_path = os.path.join(addon_path, 'resources', 'lib')
    init_file = os.path.join(lib_path, '__init__.py')
    shell_script = os.path.join(addon_path, 'resources', 'update_servers.sh')
    keymap_source = os.path.join(addon_path, 'resources', 'keymaps', 'wireguard_manager_key.xml')
    keymap_dest = '/storage/.kodi/userdata/keymaps/wireguard_manager_key.xml'

    if not os.path.exists(init_file):
        try:
            with open(init_file, 'a'):
                os.utime(init_file, None)
            xbmc.log("[service.wireguard.manager] Created missing __init__.py", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[service.wireguard.manager] Failed to create __init__.py: {e}", xbmc.LOGERROR)

    if os.path.exists(shell_script):
        try:
            os.chmod(shell_script, 0o755)
        except Exception as e:
            xbmc.log(f"[service.wireguard.manager] Chmod Error: {e}", xbmc.LOGERROR)

    is_first_run = addon.getSettings().getBool("first_run")

    if not os.path.exists(keymap_dest) or is_first_run:
        try:

            if os.path.exists(keymap_source):

                if not os.path.exists(os.path.dirname(keymap_dest)):
                    os.makedirs(os.path.dirname(keymap_dest))
                
                shutil.copy2(keymap_source, keymap_dest)
                xbmc.log(f"[service.wireguard.manager] Keymap installed to {keymap_dest}", xbmc.LOGINFO)

            addon.setSettingBool("first_run", False)

            header = "Reboot Required"
            message = "Remote shortcuts (Blue Button) installed.\nA reboot is required to activate them.\nReboot now?"
            
            if xbmcgui.Dialog().yesno(header, message):
                xbmc.log("[service.wireguard.manager] User initiated reboot.", xbmc.LOGINFO)
                xbmc.executebuiltin('Reboot')
                return True
                
        except Exception as e:
            xbmc.log(f"[service.wireguard.manager] Setup Error: {e}", xbmc.LOGERROR)

    return False
