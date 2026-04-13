import os
import sys
import xbmc
import xbmcgui
import xbmcaddon
import subprocess

ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = ADDON.getAddonInfo('path')
sys.path.append(os.path.join(ADDON_PATH, 'resources', 'lib'))

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
                
                label = f"[B][COLOR ff00ff7f][CONNECTED][/COLOR] {name}[/B]" if is_active else name
                item = xbmcgui.ListItem(label)

                icon_file = 'vpn_on.png' if is_active else 'vpn_off.png'
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
                log_message(f"Menu: Manual disconnect requested for {active_name}")
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

                xbmcgui.Window(10000).setProperty('vpn_manual_session', 'true')
                
                log_message(f"Menu: Manual connection requested for {target_name}")
                vpn_ops.connect_vpn(target_name, target_sid)

    except Exception as e:
        log_message(f"Menu Error: {e}", xbmc.LOGERROR)
