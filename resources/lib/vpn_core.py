import os, sys, xbmc, xbmcaddon, subprocess, shutil, xbmcgui, time
from vpn_config import *

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = _ADDON.getAddonInfo('path')

sys.path.append(os.path.join(ADDON_PATH, 'resources', 'lib'))
from logger import log_message

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
        log_message(f"Core Error: Service Installation failed: {e}", xbmc.LOGERROR)

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
        log_message(f"Core Error: Update Check failed: {e}", xbmc.LOGERROR)

def run_update(shell_script, token):
    countries = _ADDON.getSettings().getString("selected_countries")
    if not token or token.strip() == "":
        xbmcgui.Dialog().ok("VPN Manager", "Please enter your [B]NordVPN Token[/B] in the settings first.")
        return
    progress = xbmcgui.DialogProgress()
    progress.create("VPN Manager", "Updating NordVPN Servers...")
    progress.update(20, f"Generating: {countries}")
    try:
        subprocess.run(["sed", "-i", "s/\\r//", shell_script])
        subprocess.run(["chmod", "+x", shell_script])
        log_message(f"Core: Running config update for: {countries}", xbmc.LOGINFO)
        res = subprocess.run([shell_script, token, countries], capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            log_message("Core: Config update successful.", xbmc.LOGINFO)
            progress.update(100, "Update Complete!")
            log_message(f"WAIT_START: UI Buffer ({UI_BUFFER_DELAY}ms) | PURPOSE: {UI_BUFFER_PURPOSE}", xbmc.LOGDEBUG)
            xbmc.sleep(UI_BUFFER_DELAY)
            log_message("WAIT_END: UI Buffer", xbmc.LOGDEBUG)
            progress.close()
            xbmcgui.Dialog().ok("Success", f"Configs Regenerated for:[CR][COLOR yellow]{countries}[/COLOR]")
            xbmc.executebuiltin('Container.Refresh')
        else:
            log_message(f"Core Error: Update script failed: {res.stderr}", xbmc.LOGERROR)
            progress.close()
            xbmcgui.Dialog().ok("Error", "Update failed. Check token and network.")
    except Exception as e:
        log_message(f"Core Error: Update failed: {e}", xbmc.LOGERROR)
        if progress: progress.close()

def get_default_gateway():
    try:
        out = subprocess.check_output(["ip", "-4", "route", "show", "default"], text=True)
        for line in out.splitlines():
            if "via" in line and "wg0" not in line:
                parts = line.split()
                return parts[parts.index("via") + 1]
    except: 
        pass

    return GATEWAY_FALLBACK
