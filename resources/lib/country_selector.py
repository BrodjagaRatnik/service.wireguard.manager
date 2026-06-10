''' ./resources/lib/country_selector.py '''
import os
import sys
import time
import xbmcaddon
import xbmcgui
import xbmcvfs
from logger import log_message
from resources.lib.providers.nord_utils import fetch_nord_url
from resources.lib.providers.pia_utils import fetch_pia_url
from resources.lib.vpn_config import PROVIDER_MAP

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
_LIB = os.path.join(ADDON_PATH, 'resources', 'lib')

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)


def run():
    addon = xbmcaddon.Addon('service.wireguard.manager')
    provider = addon.getSettingInt("vpn_provider")
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
        log_message(f"Country Selector: Missing valid PROVIDER_MAP configuration for ID {provider}", 3)
        return

    setting_id = p_data.get("countries_setting", "selected_countries")
    raw_saved = addon.getSetting(setting_id)
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
        data.sort(key=lambda x: x['name'])
        names = [c['name'] for c in data]
        ids = [str(c['id']) for c in data]

    elif provider == 1:
        log_message(f"Country Selector: PIA API data structure type = {type(data)}", 0)

        if isinstance(data, dict):
            raw_regions = data.get('regions', [])
        elif isinstance(data, list):
            raw_regions = data
            if len(raw_regions) == 1 and isinstance(raw_regions[0], dict) and 'regions' in raw_regions[0]:
                raw_regions = raw_regions[0]['regions']
        else:
            raw_regions = []

        regions = []
        for r in raw_regions:
            if not isinstance(r, dict):
                continue

            servers_dict = r.get('servers', {})
            if isinstance(servers_dict, dict) and ('wg' in servers_dict or 'wireguard' in servers_dict):
                regions.append(r)
            elif 'ports' in r or 'dns' in r:
                regions.append(r)
            elif isinstance(r, dict) and 'id' in r and 'name' in r:
                regions.append(r)

        log_message(f"Country Selector: Validated regions left: {len(regions)}", 0)

        regions.sort(key=lambda x: x['name'])
        names = [r['name'] for r in regions]
        ids = [str(r['id']).strip() for r in regions]

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

        addon.setSetting(setting_id, id_string)

        ICON_INFO = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')
        title = "[B][COLOR ffffff00]ACTION REQUIRED!!![/COLOR][/B]"
        message = (
            "Selection cached. You [B]MUST[/B] press [B]'OK'[/B] in the "
            "main settings menu to apply changes!"
        )
        xbmcgui.Dialog().notification(title, message, ICON_INFO, 2500)

        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        log_msg = f"Country Selector: Country selection took {t_elapsed:.2f}ms"
        log_message(log_msg, 1)
    else:
        log_message("Country Selector: User interaction loop aborted by closing the dialog interface framework.", 0)


if __name__ == '__main__':
    run()
