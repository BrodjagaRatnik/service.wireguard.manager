''' ./resources/lib/list_assets.py '''
import json
import os
import subprocess
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from logger import log_message
from vpn_config import PROVIDER_MAP

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
_LIB = os.path.join(_PATH, 'resources', 'lib')
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

ICON_INFO = os.path.join(_PATH, 'resources', 'media', 'icon.png')


def get_wg_services():
    services = []
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        valid_prefixes = []
        for p in PROVIDER_MAP.values():
            if 'name' in p:
                valid_prefixes.append(f"{p['name']}_")
            if 'prefix' in p:
                valid_prefixes.append(f"{p['prefix'].title()}")

        for line in out.splitlines():
            if not any(prefix in line for prefix in valid_prefixes):
                continue
            parts = line.split()
            if not parts:
                continue
            service_id = parts[-1]
            name = line.replace(service_id, "").strip("* ARd ").strip()
            services.append({"name": name, "id": service_id})
    except Exception as e:
        try:
            log_message(f"Wizard Error: {e}", 3)
        except Exception as logger_error:
            fallback_msg = f"Wizard Error: {e} | Logger fallback failure: {logger_error}\n"
            sys.stderr.write(fallback_msg)
            sys.stderr.flush()
    return services


def run_wizard():

    slots = [f"Slot {i}" for i in range(1, 9)]
    sel_slot = xbmcgui.Dialog().select("Assign VPN to which Slot?", slots)
    if sel_slot == -1:
        return
    slot_id = sel_slot + 1

    actions = ["Assign VPN & Addon", "Clear Slot (Reset)"]
    sel_action = xbmcgui.Dialog().select(f"Action for Slot {slot_id}", actions)
    if sel_action == -1:
        return

    if sel_action == 1:
        _ADDON.setSetting(f"vpn_{slot_id}_name", "")
        _ADDON.setSetting(f"map_{slot_id}_addon", "")

        title = "[B][COLOR FFE6E6FA]≡ [ WireGuard Manager ] ≡[/COLOR][/B]"
        msg = f"[COLOR FFFFFF00]Slot {slot_id} reset[/COLOR]"
        _ADDON.setSetting(f"vpn_{slot_id}_name", "")
        _ADDON.setSetting(f"map_{slot_id}_addon", "")
        xbmcgui.Dialog().notification(title, msg, ICON_INFO, 3000)
        return

    services = get_wg_services()
    if not services:
        title = "[B]≡ ERROR ≡[/B]"
        msg = "[COLOR FFFFFF00]No VPN services found.\nGenerate configs first.[/COLOR]"
        xbmcgui.Dialog().ok(title, msg)
        return

    display_names = [s['name'] for s in services]
    sel_vpn = xbmcgui.Dialog().select("Select VPN Profile", display_names)
    if sel_vpn == -1:
        return

    chosen_vpn_name = services[sel_vpn]['name']

    rpc = '{"jsonrpc":"2.0","method":"Addons.GetAddons","params":{"type":"xbmc.python.pluginsource","enabled":true},"id":1}'
    try:
        rpc_res = xbmc.executeJSONRPC(rpc)
        data = json.loads(rpc_res)
        addons = [a['addonid'] for a in data.get('result', {}).get('addons', [])]
        addons.sort()
    except Exception as e:
        log_message(f"Wizard: JSON-RPC Error: {e}", 3)
        addons = []

    if not addons:
        title = "[B]≡ ERROR ≡[/B]"
        msg = "[COLOR FFFFFF00]No video addons found.[/COLOR]"
        xbmcgui.Dialog().ok(title, msg)
        return

    sel_addon = xbmcgui.Dialog().select("Select Trigger Addon", addons)
    if sel_addon == -1:
        return

    _ADDON.setSetting(f"vpn_{slot_id}_name", chosen_vpn_name)
    _ADDON.setSetting(f"map_{slot_id}_addon", addons[sel_addon])

    title = "[B][COLOR FFE6E6FA]≡ [ WireGuard Manager ] ≡[/COLOR][/B]"
    msg = f"[COLOR FFFFFF00]Slot {slot_id} Saved[/COLOR]"
    xbmcgui.Dialog().notification(title, msg, ICON_INFO, 3000)


if __name__ == '__main__':
    run_wizard()
