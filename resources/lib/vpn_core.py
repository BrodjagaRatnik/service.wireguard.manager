''' ./resources/lib/vpn_core.py '''
import os, sys, xbmc, xbmcaddon, xbmcvfs, subprocess, shutil, xbmcgui, time

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
UI_BUFFER_DELAY = 800
UI_BUFFER_PURPOSE = "Keeps the 'Connected' message on screen long enough to read"
SERVICE_INIT_DELAY = 400
SERVICE_INIT_PURPOSE = "Systemd PID spawning buffer"

sys.path.append(os.path.join(ADDON_PATH, 'resources', 'lib'))
from logger import log_message
from network_utils import get_default_gateway

def install_service(source, dest, name, media_path):
    try:
        if not os.path.exists(dest):
            log_message(f"Core: Installing watchdog service to {dest}", xbmc.LOGINFO)
            shutil.copy2(source, dest)
            subprocess.run(["systemctl", "daemon-reload"])
            subprocess.run(["systemctl", "enable", name])
            subprocess.run(["systemctl", "start", name])
            xbmcgui.Dialog().notification("VPN Manager", "Watchdog Installed & Started", os.path.join(media_path, 'update_ok.png'), 3000)
        else:
            res = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True)
            if "active" not in res.stdout:
                log_message(f"Core: Watchdog service inactive, attempting start.", xbmc.LOGINFO)
                subprocess.run(["systemctl", "start", name])
                log_message(f"WAIT_START: Service Initialization ({SERVICE_INIT_DELAY}ms) | PURPOSE: {SERVICE_INIT_PURPOSE}", xbmc.LOGDEBUG)
                xbmc.sleep(SERVICE_INIT_DELAY)
                log_message("WAIT_END: Service Initialization", xbmc.LOGDEBUG)
    except Exception as e:
        log_message(f"Core: Service Installation failed: {e}", xbmc.LOGERROR)

def check_for_updates(media_path):
    config_dir = '/storage/.config/wireguard/'
    try:
        if os.path.exists(config_dir):
            files = [os.path.join(config_dir, f) for f in os.listdir(config_dir) if f.endswith('.config')]
            if not files: return
            latest_file = max(files, key=os.path.getmtime)
            file_age = time.time() - os.path.getmtime(latest_file)
            if file_age > 604800:
                log_message("Core: Server list is over 7 days old. Notifying user.", xbmc.LOGINFO)
                xbmcgui.Dialog().notification("NordVPN Manager", "Server list is over 7 days old.", os.path.join(media_path, 'update.png'), 5000)
    except Exception as e:
        log_message(f"Core: Update Check failed: {e}", xbmc.LOGERROR)

def run_update(shell_script, token):
    raw_path = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
    addon_path = os.path.normpath(raw_path) 
    full_script_path = os.path.join(addon_path, 'resources', 'update_servers.sh')

    if not os.path.exists(full_script_path):
        full_script_path = os.path.join(addon_path, 'resources', 'lib', 'update_servers.sh')

    if not os.path.exists(full_script_path):
        res_dir = os.path.join(addon_path, 'resources')
        content = os.listdir(res_dir) if os.path.exists(res_dir) else "DIR NOT FOUND"
        xbmc.log(f"service.wireguard.manager: File missing! Content of {res_dir}: {content}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Error", "Update script not found in resources folder.")
        return

    countries = _ADDON.getSetting("selected_countries")
    
    if not token or token.strip() == "":
        xbmcgui.Dialog().ok("VPN Manager", "Please enter your [B]NordVPN Token[/B] in the settings first.")
        return

    progress = xbmcgui.DialogProgress()
    progress.create("VPN Manager", "Updating NordVPN Servers...")
    progress.update(20, f"Generating: {countries}")

    try:
        if os.path.exists(full_script_path):
            subprocess.run(["sed", "-i", "s/\\r//", full_script_path])
            subprocess.run(["chmod", "+x", full_script_path])
        else:
            xbmc.log(f"service.wireguard.manager: Script not found at {full_script_path}", xbmc.LOGERROR)
            progress.close()
            xbmcgui.Dialog().ok("Error", "Core update script missing.")
            return

        xbmc.log(f"service.wireguard.manager: Running config update for: {countries}", xbmc.LOGINFO)

        res = subprocess.run([full_script_path, token, countries], capture_output=True, text=True, timeout=90)
        
        if res.returncode == 0:
            xbmc.log("service.wireguard.manager: Config update successful.", xbmc.LOGINFO)
            progress.update(100, "Update Complete!")
            xbmc.sleep(1000)
            progress.close()
            xbmcgui.Dialog().ok("Success", f"Configs Regenerated for:[CR][COLOR yellow]{countries}[/COLOR]")
            xbmc.executebuiltin('Container.Refresh')
        else:
            xbmc.log(f"service.wireguard.manager: Update script failed: {res.stderr}", xbmc.LOGERROR)
            progress.close()
            xbmcgui.Dialog().ok("Error", "Update failed. Check token and network.")

    except Exception as e:
        xbmc.log(f"service.wireguard.manager: Update exception: {e}", xbmc.LOGERROR)
        if progress: progress.close()
