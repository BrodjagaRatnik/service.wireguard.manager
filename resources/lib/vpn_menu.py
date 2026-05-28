''' ./resources/lib/vpn_menu.py '''
import os
import sys
import xbmc
import xbmcgui
import xbmcaddon
import subprocess
from vpn_config import (
    PROVIDER_MAP,
    UI_BUFFER_DELAY_MENU,
)
from logger import log_message
import vpn_ops

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = _ADDON.getAddonInfo('path')
_LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')

if _LIB_PATH not in sys.path:
    sys.path.append(_LIB_PATH)


def show_menu(media_path, provider_index):
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

        valid_prefixes = [p['name'] for p in PROVIDER_MAP.values()] + ["Manual", "custom"]

        for s in lines:
            if any(p in s for p in valid_prefixes):
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

        item_update = xbmcgui.ListItem("[B]Update, Regenerate [COLOR yellow]VPN Configs[/B][/COLOR]")
        item_update.setArt({'icon': os.path.join(media_path, 'update.png')})
        menu_items.append(item_update)
        mapping.append("REGEN")

        p_data = PROVIDER_MAP.get(int(provider_index))
        title = f"{p_data['name']} Manager" if p_data else "VPN Manager"

        choice = xbmcgui.Dialog().select(title, menu_items, useDetails=True)
        if choice >= 0:
            action = mapping[choice]

            if action == "DISCONNECT":
                vpn_ops.disconnect_vpn()

            elif action == "REGEN":
                from vpn_core import run_update
                if run_update():
                    show_menu(media_path, provider_index)

            else:
                target_name, target_sid = action
                if active_name == target_name.replace('_', ' ').strip():
                    return

                xbmcgui.Window(10000).setProperty('vpn_manual_session', 'true')

                try:
                    with open('/tmp/vpn_manual_active.txt', 'w') as f:
                        f.write(target_name)
                except Exception as e:
                    log_message(f"Menu: Could not write manual flag: {e}", 2)

                xbmc.sleep(UI_BUFFER_DELAY_MENU)

                log_message(f"Menu: Manual connection requested for {target_name}", 1)
                vpn_ops.connect_vpn(target_name, target_sid)

    except Exception as e:
        log_message(f"Menu Error: {e}", 3)
