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
            log_message(f"Core: Installing watchdog service to {dest}", 1)
            shutil.copy2(source, dest)
            subprocess.run(["systemctl", "daemon-reload"])
            subprocess.run(["systemctl", "enable", name])
            subprocess.run(["systemctl", "start", name])
            xbmcgui.Dialog().notification("VPN Manager", "Watchdog Installed & Started", os.path.join(media_path, 'update_ok.png'), 3000)
        else:
            res = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True)
            if "active" not in res.stdout:
                log_message(f"Core: Watchdog service inactive, attempting start.", 3)
                subprocess.run(["systemctl", "start", name])
                log_message(f"WAIT_START: Service Initialization ({SERVICE_INIT_DELAY}ms) | PURPOSE: {SERVICE_INIT_PURPOSE}", 0)
                xbmc.sleep(SERVICE_INIT_DELAY)
                log_message("WAIT_END: Service Initialization", 0)
    except Exception as e:
        log_message(f"Core: Service Installation failed: {e}", 3)

def check_for_updates(media_path):
    config_dir = '/storage/.config/wireguard/'
    try:
        if os.path.exists(config_dir):
            files = [os.path.join(config_dir, f) for f in os.listdir(config_dir) if f.endswith('.config')]
            if not files: return
            latest_file = max(files, key=os.path.getmtime)
            file_age = time.time() - os.path.getmtime(latest_file)
            if file_age > 604800:
                log_message("Core: Server list is over 7 days old. Notifying user.", 1)
                xbmcgui.Dialog().notification("NordVPN Manager", "Server list is over 7 days old.", os.path.join(media_path, 'update.png'), 5000)
    except Exception as e:
        log_message(f"Core: Update Check failed: {e}", 3)

def run_update(token):
    raw_path = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
    addon_path = os.path.normpath(raw_path) 
    full_script_path = os.path.join(addon_path, 'resources', 'scripts', 'update_nordvpn_servers.py')

    countries = _ADDON.getSetting("selected_countries")
    
    if not token or token.strip() == "":
        xbmcgui.Dialog().ok("VPN Manager", "Please enter your [B]NordVPN Token[/B] in the settings first.")
        return

    progress = xbmcgui.DialogProgress()
    progress.create("VPN Manager", "Updating NordVPN Servers...")
    progress.update(20, f"Generating: {countries}")

    try:
        if not os.path.exists(full_script_path):
            log_message("Core: Python script not found at {full_script_path}", 3)
            progress.close()
            xbmcgui.Dialog().ok("Error", "Update script missing from resources/scripts/")
            return

        log_message("Core: Running Python regen for: {countries}", 0)

        res = subprocess.run([sys.executable, full_script_path, token, countries], capture_output=True, text=True, timeout=120)
        
        if res.returncode == 0:
            log_message("Core: Server regeneration successful.", 1)
            progress.update(100, "Update Complete!")
            xbmc.sleep(500)
            progress.close()
            xbmcgui.Dialog().ok("Success", f"Configs Regenerated for:[CR][COLOR yellow]{countries}[/COLOR]")
            xbmc.executebuiltin('Container.Refresh')
        else:
            log_message(f"Core: Script error: {res.stderr}", 3)
            progress.close()
            xbmcgui.Dialog().ok("Error", "Update failed. Check token or API connectivity.")

    except Exception as e:
        log_message("Core: Update exception: {e}", 3)
        if progress: progress.close()
