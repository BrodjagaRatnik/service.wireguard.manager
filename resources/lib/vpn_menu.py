import os
import xbmc
import xbmcgui
import subprocess
import json
import time
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = '/storage/.kodi/temp/wireguard_manager.log'
_logger = logging.getLogger("WG_Menu")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=1)
    handler.setFormatter(logging.Formatter('%(asctime)s - MENU - %(levelname)s - %(message)s'))
    _logger.addHandler(handler)

def log_event(msg, level=xbmc.LOGINFO):
    xbmc.log(f"WG_Manager: {msg}", level)
    if level >= xbmc.LOGERROR:
        _logger.error(msg)
    else:
        _logger.info(msg)

def show_menu(media_path, shell_script, token):
    try:
        output = subprocess.check_output(["connmanctl", "services"]).decode("utf-8")
        lines = output.splitlines()
        
        connected_sid = None
        connected_name = None
        for s in lines:
            if "NordVPN" in s and ("* R" in s or "* O" in s):
                connected_sid = s.split()[-1]
                connected_name = s.replace(connected_sid, "").strip("* Rd").strip().replace('_', ' ')
                break

        menu_items = []
        mapping = []

        if connected_sid:
            item_reset = xbmcgui.ListItem(f"[B][COLOR white]DISCONNECT[/COLOR] [COLOR yellow]({connected_name})[/COLOR][/B]")
            item_reset.setArt({'icon': os.path.join(media_path, 'reset.png')}) 
            menu_items.append(item_reset)
            mapping.append("DISCONNECT")

        for s in lines:
            if "NordVPN" in s:
                sid = s.split()[-1]
                name = s.replace(sid, "").strip("* Rd").strip().replace('_', ' ')
                is_active = "* R" in s or "* O" in s
                label = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR] {name}[/B]" if is_active else name
                item = xbmcgui.ListItem(label)
                item.setArt({'icon': os.path.join(media_path, 'vpn_on.png' if is_active else 'vpn_off.png')})
                menu_items.append(item)
                mapping.append(sid)

        item_update = xbmcgui.ListItem("[B]Update/Regenerate [COLOR yellow]VPN Configs[/B][/COLOR]")
        item_update.setArt({'icon': os.path.join(media_path, 'update.png')})
        menu_items.append(item_update)
        mapping.append("REGEN")
        
        choice = xbmcgui.Dialog().select("NordVPN Manager", menu_items, useDetails=True)
        if choice >= 0:
            action = mapping[choice]
            
            if action == "DISCONNECT":
                log_event(f"User requested disconnect from {connected_name}")
                vpn_ids = [m for m in mapping if "vpn_" in m]
                for sid in vpn_ids: subprocess.run(["connmanctl", "disconnect", sid])
                subprocess.run(["ifconfig", "eth0", "metric", "1"], check=False)
                subprocess.run(["connmanctl", "enable", "wifi"], check=False)               
                xbmcgui.Dialog().notification("Network", "VPN Disconnected", os.path.join(media_path, 'vpn_disconnected.png'), 3000)
            
            elif action == "REGEN":
                log_event("User requested VPN config regeneration")
                from resources.lib.vpn_core import run_update
                run_update(shell_script, token)
                show_menu(media_path, shell_script, token) 
            
            else:
                try:
                    state_out = subprocess.check_output(["connmanctl", "state"], text=True)
                    if "ethernet" in state_out.lower():
                        subprocess.run(["connmanctl", "disable", "wifi"], check=False)
                        subprocess.run(["ifconfig", "eth0", "metric", "100"], check=False)
                        xbmc.sleep(1000)
                except:
                    pass

                raw_label = menu_items[choice].getLabel()
                clean_name = raw_label.split('[/COLOR] ')[-1].replace('[/B]', '')
                
                pbg = xbmcgui.DialogProgressBG()
                pbg.create("VPN Manager", f"Connecting to {clean_name}...")
                
                log_event(f"Attempting connection to {clean_name}...")
                subprocess.run(["connmanctl", "connect", action])
                
                connected = False
                for i in range(1, 11):
                    pbg.update(i * 10, message=f"Verifying... ({i}s)")
                    xbmc.sleep(1000)
                    check = subprocess.check_output(["connmanctl", "services"]).decode("utf-8")
                    if any(action in line and ("* R" in line or "* O" in line) for line in check.splitlines()):
                        connected = True
                        break
                pbg.close()
                
                if connected:
                    ip = "Unknown"
                    try:
                        res = subprocess.check_output(["curl", "-s", "https://ipinfo.io"], timeout=5).decode("utf-8")
                        data = json.loads(res)
                        ip = data.get("ip", "Unknown")
                        msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {clean_name}\nIP: [COLOR yellow]{ip}[/COLOR]"
                    except:
                        msg = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR][/B] {clean_name}"
                    
                    log_event(f"Successfully connected to {clean_name} (IP: {ip})")
                    xbmcgui.Dialog().notification("VPN Status", msg, os.path.join(media_path, 'vpn_connected.png'), 4000)
                else:
                    log_event(f"Connection to {clean_name} timed out", xbmc.LOGERROR)
                    xbmcgui.Dialog().notification("VPN Error", "Connection Timed Out", os.path.join(media_path, 'error.png'), 5000)

    except Exception as e:
        log_event(f"Menu Error: {e}", xbmc.LOGERROR)
