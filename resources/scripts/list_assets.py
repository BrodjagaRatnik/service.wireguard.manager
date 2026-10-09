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
from dialog import show_ok, notify_custom
from vpn_config import PROVIDER_MAP
import state_manager

try:
    import xbmc
    import xbmcgui
    HAS_KODI_UI = True
except ImportError:
    HAS_KODI_UI = False

_LEGACY_SETTING_VPN = "vpn_{0}_name"
_LEGACY_SETTING_ADDON = "map_{0}_addon"
_NOTIFICATION_TITLE = "[B][COLOR FFE6E6FA]≡ [ WireGuard Manager ] ≡[/COLOR][/B]"
_NOTIFICATION_SAVED = "[COLOR FFFFFF00]Slot {0} Saved[/COLOR]"
_NOTIFICATION_RESET = "[COLOR FFFFFF00]Slot {0} reset[/COLOR]"


def get_addon_path():
    return kodi_env.ADDON_DIR


def inject_lib_path():
    lib_path = os.path.join(get_addon_path(), "resources", "lib")
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)


def _provider_match_terms():
    terms = []
    for provider in PROVIDER_MAP.values():
        if "name" in provider:
            terms.append(str(provider["name"]).lower())
        if "prefix" in provider:
            terms.append(str(provider["prefix"]).lower())
    return terms


def _profile_file_prefixes():
    prefixes = []
    for provider in PROVIDER_MAP.values():
        if "name" in provider:
            prefixes.append(str(provider["name"]).lower())
        if "prefix" in provider:
            prefixes.append(str(provider["prefix"]).lower())
    return prefixes


def get_connman_services():
    services = []
    try:
        output = subprocess.check_output(["connmanctl", "services"], text=True)
        match_terms = _provider_match_terms()
        for line in output.splitlines():
            lowered_line = line.lower()
            if not any(term in lowered_line for term in match_terms):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            service_id = parts[-1]
            name_tokens = line.replace(service_id, "").split()
            while name_tokens and name_tokens[0].startswith("*"):
                name_tokens = name_tokens[1:]
            if not name_tokens:
                continue
            display_name = " ".join(name_tokens)
            services.append({"name": display_name, "id": service_id})
    except Exception as connman_fault:
        log_message(f"List Assets: Connman service listing failed: {connman_fault}", 3)
    return services


def get_local_profile_services():
    services = []
    config_dir = state_manager.CONFIG_DIR
    if not os.path.isdir(config_dir):
        return services
    try:
        profile_files = sorted(entry for entry in os.listdir(config_dir) if entry.endswith(".config"))
    except Exception as scan_fault:
        log_message(f"List Assets: Local profile scan failed: {scan_fault}", 3)
        return services
    valid_prefixes = _profile_file_prefixes()
    for profile_file in profile_files:
        base_name = os.path.splitext(profile_file)[0]
        lowered_name = base_name.lower()
        if not any(lowered_name.startswith(prefix) for prefix in valid_prefixes):
            continue
        services.append({"name": base_name, "id": base_name})
    return services


def get_wg_services():
    services = get_connman_services()
    if not services:
        log_message("List Assets: Connman returned no matches. Falling back to stored profile files.", 4)
        services = get_local_profile_services()
    return services


def read_slot(slot_id):
    vpn_name, addon_id = state_manager.get_slot_assignment(slot_id)
    if vpn_name and addon_id:
        return vpn_name, addon_id
    addon_obj = kodi_env.get_addon_instance()
    if not addon_obj:
        return None, None
    legacy_vpn = addon_obj.getSetting(_LEGACY_SETTING_VPN.format(slot_id))
    legacy_addon = addon_obj.getSetting(_LEGACY_SETTING_ADDON.format(slot_id))
    return legacy_vpn, legacy_addon


def sync_legacy_slot_settings(addon_obj, slot_id, vpn_name, addon_id):
    addon_obj.setSetting(_LEGACY_SETTING_VPN.format(slot_id), vpn_name)
    addon_obj.setSetting(_LEGACY_SETTING_ADDON.format(slot_id), addon_id)


def run_wizard():
    inject_lib_path()

    try:
        addon_obj = kodi_env.get_addon_instance()

        if not addon_obj or not HAS_KODI_UI:
            log_message("List Assets: Environment missing Kodi abstractions. Execution stopped.", 2)
            return

        slots = []
        for slot_index in range(1, 9):
            saved_vpn, saved_addon = read_slot(slot_index)
            if saved_vpn and saved_addon:
                addon_clean = saved_addon.replace("plugin.video.", "")
                slots.append(
                    f"[COLOR FFFFFF00]Slot {slot_index} ({saved_vpn} -> {addon_clean})[/COLOR]"
                )
            else:
                slots.append(f"Slot {slot_index}")

        sel_slot = xbmcgui.Dialog().select("Assign VPN to which Slot?", slots)
        if sel_slot == -1:
            return
        slot_id = sel_slot + 1

        actions = ["Assign VPN & Addon", "Clear Slot (Reset)"]
        sel_action = xbmcgui.Dialog().select(f"Action for Slot {slot_id}", actions)
        if sel_action == -1:
            return

        if sel_action == 1:
            state_manager.clear_slot_assignment(slot_id)
            sync_legacy_slot_settings(addon_obj, slot_id, "", "")
            notify_custom(_NOTIFICATION_TITLE, _NOTIFICATION_RESET.format(slot_id), "icon.png", 3000)
            return

        services = get_wg_services()
        if not services:
            show_ok(
                "[B]≡ ERROR ≡[/B]",
                "[COLOR FFFFFF00]No VPN profiles found.\nGenerate configs first.[/COLOR]"
            )
            return

        display_names = [service["name"] for service in services]
        sel_vpn = xbmcgui.Dialog().select("Select VPN Profile", display_names)
        if sel_vpn == -1:
            return

        chosen_vpn_name = services[sel_vpn]["name"]

        rpc = (
            '{"jsonrpc":"2.0","method":"Addons.GetAddons",'
            '"params":{"type":"xbmc.python.pluginsource","enabled":true},"id":1}'
        )
        try:
            rpc_res = xbmc.executeJSONRPC(rpc)
            data = json.loads(rpc_res)
            addons = [addon_entry["addonid"] for addon_entry in data.get("result", {}).get("addons", [])]
            addons.sort()
        except Exception as rpc_fault:
            log_message(f"List Assets: JSON-RPC Error: {rpc_fault}", 3)
            addons = []

        if not addons:
            show_ok("[B]≡ ERROR ≡[/B]", "[COLOR FFFFFF00]No video addons found.[/COLOR]")
            return

        sel_addon = xbmcgui.Dialog().select("Select Trigger Addon", addons)
        if sel_addon == -1:
            return

        state_manager.save_slot_assignment(slot_id, chosen_vpn_name, addons[sel_addon])
        sync_legacy_slot_settings(addon_obj, slot_id, chosen_vpn_name, addons[sel_addon])
        notify_custom(_NOTIFICATION_TITLE, _NOTIFICATION_SAVED.format(slot_id), "icon.png", 3000)

    except Exception as wizard_fault:
        log_message(f"List Assets: Allocation module exception: {wizard_fault}", 3)

    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    run_wizard()
