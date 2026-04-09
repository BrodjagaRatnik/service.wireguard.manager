import xbmc
import xbmcgui
import xbmcaddon
import os
import json
import subprocess

def get_wg_services():
    services = []
    try:
        out = subprocess.check_output(["connmanctl", "services"]).decode()
        for line in out.splitlines():
            if "vpn_" in line:
                parts = line.split()
                # Extract ID (e.g., 212_103_50_43) and Friendly Name
                raw_id = parts[-1].replace("vpn_", "")
                name = " ".join(parts[1:-1])
                services.append({"name": name, "id": raw_id})
    except Exception as e:
        xbmc.log(f"WG_WIZARD: Error fetching services: {e}", xbmc.LOGERROR)
    return services

def run_wizard():
    addon = xbmcaddon.Addon()

    slots = ["Slot 1", "Slot 2", "Slot 3", "Slot 4", "Slot 5"]
    sel_slot = xbmcgui.Dialog().select("Assign VPN to which Slot?", slots)
    if sel_slot == -1: return
    slot_id = sel_slot + 1

    actions = ["Assign VPN & Addon", "Clear Slot (Reset)"]
    sel_action = xbmcgui.Dialog().select(f"Action for Slot {slot_id}", actions)
    if sel_action == -1: return

    if sel_action == 1:
        addon.setSetting(f"vpn_{slot_id}_name", "")
        addon.setSetting(f"map_{slot_id}_addon", "")
        xbmcgui.Dialog().notification("WG Manager", f"Slot {slot_id} reset", "", 3000)
        return

    services = get_wg_services()
    if not services:
        xbmcgui.Dialog().ok("Error", "No VPN services found. Check .config files.")
        return
    
    display_names = [s['name'] for s in services]
    sel_vpn = xbmcgui.Dialog().select("Select VPN Profile", display_names)
    if sel_vpn == -1: return
    chosen_vpn_id = services[sel_vpn]['id']

    rpc = '{"jsonrpc":"2.0","method":"Addons.GetAddons","params":{"type":"xbmc.python.pluginsource","enabled":true},"id":1}'
    data = json.loads(xbmc.executeJSONRPC(rpc))
    addons = [a['addonid'] for a in data.get('result', {}).get('addons', [])]
    
    if not addons:
        xbmcgui.Dialog().ok("Error", "No video addons found.")
        return

    sel_addon = xbmcgui.Dialog().select("Select Trigger Addon", addons)
    if sel_addon == -1: return
    chosen_addon_id = addons[sel_addon]

    addon.setSetting(f"vpn_{slot_id}_name", chosen_vpn_id)
    addon.setSetting(f"map_{slot_id}_addon", chosen_addon_id)
    
    xbmcgui.Dialog().notification("WG Manager", f"Slot {slot_id} Ready!", "", 3000)
