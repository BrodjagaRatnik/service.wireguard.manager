""" ./resources/scripts/country_selector.py """
import os
import sys
import time

try:
    import kodi_env
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lib"))
    import kodi_env

from logger import log_message
from providers.nord_utils import fetch_nord_url
from providers.pia_utils import fetch_pia_url
from providers.mullvad import MullvadApi
from vpn_config import PROVIDER_MAP

try:
    import xbmcgui
    HAS_GUI_IMPORTS = True
except ImportError:
    HAS_GUI_IMPORTS = False


def get_addon_path():
    return kodi_env.ADDON_DIR


def inject_lib_path():
    addon_path = get_addon_path()
    lib_path = os.path.join(addon_path, "resources", "lib")
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)


def run():
    inject_lib_path()

    try:
        addon_obj = kodi_env.get_addon_instance()

        if not addon_obj or not HAS_GUI_IMPORTS:
            msg = "Country Selector: Environment missing Kodi abstractions. Execution stopped."
            log_message(msg, 2)
            return

        addon_path = get_addon_path()
        provider = addon_obj.getSettingInt("vpn_provider")
        log_message(f"Country Selector: Active provider ID = {provider}", 0)

        if provider < 0:
            title = "[B]≡ [ WireGuard MANAGER ] ≡[/B]"
            msg = (
                "[COLOR FFFFFF00]Please save settings after selecting a VPN "
                "Provider in settings.\nAnd fill in, import credentials for "
                "that VPN Provider.[/COLOR]"
            )
            xbmcgui.Dialog().ok(title, msg)
            return

        p_data = PROVIDER_MAP.get(provider)

        if not p_data or "api_url" not in p_data:
            msg = f"Country Selector: Missing valid PROVIDER_MAP configuration for ID {provider}"
            log_message(msg, 3)
            return

        setting_id = p_data.get("countries_setting", "selected_countries")
        raw_saved = addon_obj.getSetting(setting_id)
        saved_ids = [s.strip() for s in raw_saved.split(",") if s.strip()]

        log_message(f"Country Selector: Targeted setting_id = '{setting_id}'", 0)
        log_message(f"Country Selector: Raw saved string content = '{raw_saved}'", 0)
        log_message(f"Country Selector: Normalized saved IDs array = {saved_ids}", 0)

        data = None
        if provider == 0:
            log_message(f"Country Selector: Loading NordVPN API endpoint: {p_data['api_url']}", 0)
            data = fetch_nord_url(p_data["api_url"])
        elif provider == 1:
            log_message(f"Country Selector: Loading PIA API endpoint: {p_data['api_url']}", 0)
            data = fetch_pia_url(p_data["api_url"])
        elif provider == 2:
            log_message(f"Country Selector: Loading Mullvad API database target: {p_data['api_url']}", 0)
            data = MullvadApi.all_wireguard_relays()

        if not data:
            log_message("Country Selector: Target API payload response is completely EMPTY!", 3)
            title = "[B]≡ [ WireGuard MANAGER ERROR ] ≡[/B]"
            msg = (
                "[COLOR FFFFFF00]Could not fetch server list for [/COLOR]"
                f"[COLOR FFE6E6FA]{p_data['name']}[/COLOR]"
            )
            xbmcgui.Dialog().ok(title, msg)
            return

        names = []
        ids = []

        if provider == 0:
            data.sort(key=lambda x: x["name"])
            names = [c["name"] for c in data]
            ids = [str(c["id"]) for c in data]

        elif provider == 1:
            log_message(f"Country Selector: PIA API data structure type = {type(data)}", 0)

            if isinstance(data, dict):
                raw_regions = data.get("regions", [])
            elif isinstance(data, list):
                raw_regions = data
                if len(raw_regions) == 1 and isinstance(raw_regions[0], dict) and "regions" in raw_regions[0]:
                    raw_regions = raw_regions[0]["regions"]
            else:
                raw_regions = []

            regions = []
            for r in raw_regions:
                if not isinstance(r, dict):
                    continue

                servers_dict = r.get("servers", {})
                if isinstance(servers_dict, dict) and ("wg" in servers_dict or "wireguard" in servers_dict):
                    regions.append(r)
                elif "ports" in r or "dns" in r:
                    regions.append(r)
                elif isinstance(r, dict) and "id" in r and "name" in r:
                    regions.append(r)

            log_message(f"Country Selector: Validated regions left: {len(regions)}", 0)

            regions.sort(key=lambda x: x["name"])
            names = [r["name"] for r in regions]
            ids = [str(r["id"]).strip() for r in regions]

        elif provider == 2:
            log_message("Country Selector: Loaded Mullvad public structural elements", 0)
            mullvad_countries = {}

            if isinstance(data, dict) and "countries" in data:
                for c in data["countries"]:
                    if isinstance(c, dict) and "code" in c and "name" in c:
                        code = str(c["code"]).strip()
                        name = str(c["name"]).strip()
                        if code and name and code not in mullvad_countries:
                            mullvad_countries[code] = name

            sorted_mullvad = sorted(mullvad_countries.items(), key=lambda x: x[1])
            names = [item[1] for item in sorted_mullvad]
            ids = [item[0] for item in sorted_mullvad]

        cleaned_saved_ids = [str(sid).strip() for sid in saved_ids]

        log_message(f"Country Selector: First 5 entries available inside raw API mapping: {ids[:5]}", 0)
        log_message(f"Country Selector: Target key comparison values checklist: {cleaned_saved_ids}", 0)

        preselect = [i for i, val in enumerate(ids) if val in cleaned_saved_ids]
        log_message(f"Country Selector: Resulting computed checkbox baseline indices = {preselect}", 0)

        log_message(f"Country Selector: Activating UI multiselect dialog view for {len(names)} entries...", 0)
        selected = xbmcgui.Dialog().multiselect(
            f"Select {p_data['name']} Regions", names, preselect=preselect
        )

        if selected is not None:
            t_start = time.perf_counter()

            selected_ids = [ids[i] for i in selected]
            id_string = ",".join(selected_ids)

            log_message(f"Country Selector: Selection index tracking map register = {selected}", 0)
            log_message(f"Country Selector: Assembled text configuration entry block = '{id_string}'", 0)

            addon_obj.setSetting(setting_id, id_string)

            icon_info = os.path.join(addon_path, "resources", "media", "icon.png")
            title = "[B][COLOR ffffff00]ACTION REQUIRED!!![/COLOR][/B]"
            message = (
                "Selection cached. You [B]MUST[/B] press [B]'OK'[/B] in the "
                "main settings menu to apply changes!"
            )
            xbmcgui.Dialog().notification(title, message, icon_info, 2500)

            t_elapsed = (time.perf_counter() - t_start) * 1000.0
            log_msg = f"Country Selector: Country selection took {t_elapsed:.2f}ms"
            log_message(log_msg, 1)
        else:
            log_message("Country Selector: User interaction loop aborted by closing the interface.", 0)

    except Exception as run_fault:
        log_message(f"Country Selector: Interface thread tracking exception: {run_fault}", 3)

    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    run()
