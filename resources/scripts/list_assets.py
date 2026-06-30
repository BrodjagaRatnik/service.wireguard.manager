""" ./resources/scripts/list_assets.py """
import json
import os
import subprocess
import sys

try:
    import kodi_env
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
    import kodi_env

from logger import log_message
from vpn_config import PROVIDER_MAP

try:
    import xbmc
    import xbmcgui
    HAS_KODI_UI = True
except ImportError:
    HAS_KODI_UI = False


def get_addon_path():
    return kodi_env.ADDON_DIR


def inject_lib_path():
    path = get_addon_path()
    lib_path = os.path.join(path, "resources", "lib")
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)


def get_wg_services():
    services = []
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        valid_prefixes = []
        for p in PROVIDER_MAP.values():
            if "name" in p:
                valid_prefixes.append(f"{p['name']}_")
            if "prefix" in p:
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
            log_message(f"List Assets: {e}", 3)
        except Exception as logger_error:
            fallback_msg = f"Wizard Error: {e} | Logger fallback failure: {logger_error}\n"
            sys.stderr.write(fallback_msg)
            sys.stderr.flush()
    return services


def run_wizard():
    inject_lib_path()
    addon_obj = kodi_env.get_addon_instance()

    if not addon_obj or not HAS_KODI_UI:
        log_message("List Assets: Environment missing Kodi abstractions. Execution stopped.", 2)
        kodi_env.clear_script_globals()
        return

    addon_path = get_addon_path()
    icon_info = os.path.join(addon_path, "resources", "media", "icon.png")

    slots = []
    for i in range(1, 9):
        saved_vpn = addon_obj.getSetting(f"vpn_{i}_name")
        saved_addon = addon_obj.getSetting(f"map_{i}_addon")

        if saved_vpn and saved_addon:
            addon_clean = saved_addon.replace("plugin.video.", "")
            slots.append(f"[COLOR FFFFFF00]Slot {i} ({saved_vpn} -> {addon_clean})[/COLOR]")
        else:
            slots.append(f"Slot {i}")

    sel_slot = xbmcgui.Dialog().select("Assign VPN to which Slot?", slots)
    if sel_slot == -1:
        kodi_env.clear_script_globals()
        return
    slot_id = sel_slot + 1

    actions = ["Assign VPN & Addon", "Clear Slot (Reset)"]
    sel_action = xbmcgui.Dialog().select(f"Action for Slot {slot_id}", actions)
    if sel_action == -1:
        kodi_env.clear_script_globals()
        return

    if sel_action == 1:
        addon_obj.setSetting(f"vpn_{slot_id}_name", "")
        addon_obj.setSetting(f"map_{slot_id}_addon", "")

        title = "[B][COLOR FFE6E6FA]≡ [ WireGuard Manager ] ≡[/COLOR][/B]"
        msg = f"[COLOR FFFFFF00]Slot {slot_id} reset[/COLOR]"
        addon_obj.setSetting(f"vpn_{slot_id}_name", "")
        addon_obj.setSetting(f"map_{slot_id}_addon", "")
        xbmcgui.Dialog().notification(title, msg, icon_info, 3000)
        kodi_env.clear_script_globals()
        return

    services = get_wg_services()
    if not services:
        title = "[B]≡ ERROR ≡[/B]"
        msg = "[COLOR FFFFFF00]No VPN services found.\nGenerate configs first.[/COLOR]"
        xbmcgui.Dialog().ok(title, msg)
        kodi_env.clear_script_globals()
        return

    display_names = [s["name"] for s in services]
    sel_vpn = xbmcgui.Dialog().select("Select VPN Profile", display_names)
    if sel_vpn == -1:
        kodi_env.clear_script_globals()
        return

    chosen_vpn_name = services[sel_vpn]["name"]

    rpc = (
        '{"jsonrpc":"2.0","method":"Addons.GetAddons",'
        '"params":{"type":"xbmc.python.pluginsource","enabled":true},"id":1}'
    )
    try:
        rpc_res = xbmc.executeJSONRPC(rpc)
        data = json.loads(rpc_res)
        addons = [a["addonid"] for a in data.get("result", {}).get("addons", [])]
        addons.sort()
    except Exception as e:
        log_message(f"List Assets: JSON-RPC Error: {e}", 3)
        addons = []

    if not addons:
        title = "[B]≡ ERROR ≡[/B]"
        msg = "[COLOR FFFFFF00]No video addons found.[/COLOR]"
        xbmcgui.Dialog().ok(title, msg)
        kodi_env.clear_script_globals()
        return

    sel_addon = xbmcgui.Dialog().select("Select Trigger Addon", addons)
    if sel_addon == -1:
        kodi_env.clear_script_globals()
        return

    addon_obj.setSetting(f"vpn_{slot_id}_name", chosen_vpn_name)
    addon_obj.setSetting(f"map_{slot_id}_addon", addons[sel_addon])

    title = "[B][COLOR FFE6E6FA]≡ [ WireGuard Manager ] ≡[/COLOR][/B]"
    msg = f"[COLOR FFFFFF00]Slot {slot_id} Saved[/COLOR]"
    xbmcgui.Dialog().notification(title, msg, icon_info, 3000)
    kodi_env.clear_script_globals()


if __name__ == "__main__":
    run_wizard()
