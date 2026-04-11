import xbmc
import xbmcgui
import xbmcaddon
import os
import json
import subprocess

def get_wg_services():
    services = []
    try:

        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():

            if "NordVPN_" in line:
                parts = line.split()
                if not parts: continue

                service_id = parts[-1]

                name = "".join([p for p in parts if "NordVPN_" in p])
                
                services.append({"name": name, "id": service_id})
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
        xbmcgui.Dialog().ok("Error", "No NordVPN services found. Regenerate configs first.")
        return
    
    display_names = [s['name'] for s in services]
    sel_vpn = xbmcgui.Dialog().select("Select VPN Profile", display_names)
    if sel_vpn == -1: return

    chosen_vpn_name = services[sel_vpn]['name']

    rpc = '{"jsonrpc":"2.0","method":"Addons.GetAddons","params":{"type":"xbmc.python.pluginsource","enabled":true},"id":1}'
    try:
        rpc_res = xbmc.executeJSONRPC(rpc)
        data = json.loads(rpc_res)
        addons = [a['addonid'] for a in data.get('result', {}).get('addons', [])]
    except:
        addons = []
        
    if not addons:
        xbmcgui.Dialog().ok("Error", "No video addons found.")
        return

    sel_addon = xbmcgui.Dialog().select("Select Trigger Addon", addons)
    if sel_addon == -1: return
    chosen_addon_id = addons[sel_addon]

    addon.setSetting(f"vpn_{slot_id}_name", chosen_vpn_name)
    addon.setSetting(f"map_{slot_id}_addon", chosen_addon_id)
    
    xbmcgui.Dialog().notification("WG Manager", f"Slot {slot_id} -> {chosen_vpn_name}", "", 3000)

if __name__ == '__main__':
    run_wizard()
