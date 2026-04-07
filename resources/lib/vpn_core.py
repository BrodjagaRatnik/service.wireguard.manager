import os
import xbmc
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = '/storage/.kodi/temp/wireguard_manager.log'

_logger = logging.getLogger("WG_Manager")
_logger.setLevel(logging.INFO)

if not _logger.handlers:

    handler = RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=1)
    handler.setFormatter(logging.Formatter('%(asctime)s - CORE - %(levelname)s - %(message)s'))
    _logger.addHandler(handler)

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"WG_Manager: {msg}", level)

    if level >= xbmc.LOGERROR:
        _logger.error(msg)
    elif level == xbmc.LOGWARNING:
        _logger.warning(msg)
    else:
        _logger.info(msg)

def install_service(source, dest, name, media_path):
    import subprocess 
    import shutil
    import xbmcgui
    try:
        if not os.path.exists(dest):
            log(f"Installing watchdog service to {dest}")
            shutil.copy2(source, dest)
            subprocess.run(["systemctl", "daemon-reload"])
            subprocess.run(["systemctl", "enable", name])
            subprocess.run(["systemctl", "start", name])
            xbmcgui.Dialog().notification("VPN Manager", "Watchdog Installed & Started", os.path.join(media_path, 'update_ok.png'), 3000)
        else:
            res = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True)
            if "active" not in res.stdout:
                subprocess.run(["systemctl", "start", name])
                xbmc.sleep(500) 
    except Exception as e:
        log(f"Service Installation Error: {e}", xbmc.LOGERROR)

def check_for_updates(media_path):
    import time
    import xbmcgui
    config_dir = '/storage/.config/wireguard/'
    try:
        if os.path.exists(config_dir):
            files = [os.path.join(config_dir, f) for f in os.listdir(config_dir) if f.endswith('.config')]
            if not files: return
            
            latest_file = max(files, key=os.path.getmtime)
            file_age = time.time() - os.path.getmtime(latest_file)
            
            if file_age > 604800:
                xbmcgui.Dialog().notification("NordVPN Manager", "Server list is over 7 days old.", os.path.join(media_path, 'update.png'), 5000)
    except Exception as e:
        log(f"Update Check Error: {e}", xbmc.LOGERROR)

def run_update(shell_script, token):
    import subprocess
    import xbmcaddon
    import xbmcgui
    addon = xbmcaddon.Addon()
    countries = addon.getSettings().getString("selected_countries")
    
    if not token or token.strip() == "":
        xbmcgui.Dialog().ok("VPN Manager", "Please enter your [B]NordVPN Token[/B] in the settings first.")
        return

    progress = xbmcgui.DialogProgress()
    progress.create("VPN Manager", "Updating NordVPN Servers...")
    progress.update(20, f"Generating: {countries}")

    try:
        subprocess.run(["sed", "-i", "s/\\r//", shell_script])
        subprocess.run(["chmod", "+x", shell_script])
        
        res = subprocess.run([shell_script, token, countries], capture_output=True, text=True, timeout=60)
        
        if res.returncode == 0:
            progress.update(100, "Update Complete!")
            xbmc.sleep(800)
            progress.close()
            xbmcgui.Dialog().ok("Success", f"Configs Regenerated for:[CR][COLOR yellow]{countries}[/COLOR]")
            xbmc.executebuiltin('Container.Refresh')
        else:
            log(f"Update failed: {res.stderr}", xbmc.LOGERROR)
            progress.close()
            xbmcgui.Dialog().ok("Error", "Update failed. Check token and network.")
    except Exception as e:
        log(f"Update Error: {e}", xbmc.LOGERROR)
        if progress: progress.close()

def get_default_gateway():
    import subprocess
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"]).decode()
        parts = out.split()
        if "via" in parts:
            return parts[parts.index("via") + 1]
    except: pass
    return None
