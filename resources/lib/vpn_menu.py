''' ./resources/lib/vpn_menu.py '''
import os
import sys
import xbmc
import xbmcgui
import xbmcaddon
import subprocess

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = _ADDON.getAddonInfo('path')
sys.path.append(os.path.join(ADDON_PATH, 'resources', 'lib'))

UI_BUFFER_DELAY_MENU = 500 
UI_BUFFER_PURPOSE_MENU = "Makes the menu feel snappy and responsive to clicks"

from logger import log_message
import vpn_ops

def show_menu(media_path, shell_script, token):
    try:
        raw_state = vpn_ops.get_active_vpn()
        active_name = raw_state.replace('_', ' ').strip() if raw_state else None

        output = subprocess.check_output(["connmanctl", "services"], text=True)
        lines = output.splitlines()
        
        menu_items = []
        mapping = []

        if active_name:
            item_reset = xbmcgui.ListItem(f"[B][COLOR white]DISCONNECT[/COLOR] [COLOR yellow]({active_name})[/COLOR][/B]")
            item_reset.setArt({'icon': os.path.join(media_path, 'reset.png')}) 
            menu_items.append(item_reset)
            mapping.append("DISCONNECT")

        for s in lines:
            if "NordVPN" in s:
                sid = s.split()[-1]
                name = s.replace(sid, "").strip("* Rd").strip().replace('_', ' ')
                is_active = (name == active_name)
                
                if is_active:
                    label = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR] {name}[/B]"
                    icon_file = 'vpn_on.png'
                else:
                    label = f"[B][COLOR white]{name}[/COLOR][/B]"
                    icon_file = 'vpn_off.png'
                
                item = xbmcgui.ListItem(label)
                item.setArt({'icon': os.path.join(media_path, icon_file)})
                menu_items.append(item)
                mapping.append((name, sid))

        item_update = xbmcgui.ListItem("[B]Update/Regenerate [COLOR yellow]VPN Configs[/B][/COLOR]")
        item_update.setArt({'icon': os.path.join(media_path, 'update.png')})
        menu_items.append(item_update)
        mapping.append("REGEN")

        choice = xbmcgui.Dialog().select("NordVPN Manager", menu_items, useDetails=True)
        if choice >= 0:
            action = mapping[choice]
            
            if action == "DISCONNECT":
                log_message(f"Menu: Manual disconnect requested for {active_name}", xbmc.LOGINFO)
                vpn_ops.disconnect_vpn()
            
            elif action == "REGEN":
                from vpn_core import run_update
                run_update(shell_script, token)
                show_menu(media_path, shell_script, token)
            
            else:
                target_name, target_sid = action
                t_clean = target_name.replace('_', ' ').strip()

                if active_name == t_clean:
                    return

                try:
                    xbmcgui.Window(10000).setProperty('vpn_manual_session', 'true')
                    for path in ['/tmp/vpn_manual_active.txt', '/storage/.kodi/temp/vpn_manual_active.txt']:
                        try:
                            with open(path, 'w') as f:
                                f.write("manual")
                            log_message(f"Menu: Safety Pin created at {path}", xbmc.LOGDEBUG)
                        except:
                            continue
                except Exception as e:
                    log_message(f"Menu Flag Error: {e}", xbmc.LOGERROR)

                log_message(f"WAIT: UI Buffer Menu ({UI_BUFFER_DELAY_MENU}ms) | PURPOSE: {UI_BUFFER_PURPOSE_MENU}", xbmc.LOGDEBUG)              
                xbmc.sleep(UI_BUFFER_DELAY_MENU)

                log_message(f"Menu: Manual connection requested for {target_name}", xbmc.LOGINFO)
                vpn_ops.connect_vpn(target_name, target_sid)

    except Exception as e:
        log_message(f"Menu: Error {e}", xbmc.LOGERROR)
