''' ./resources/lib/country_selector.py '''
import os
import sys
import time

if 'utils' in sys.modules and 'service.wireguard.manager' not in str(sys.modules.get('utils')):
    del sys.modules['utils']

import xbmcaddon
import xbmcgui
import xbmcvfs
from logger import log_message
from utils import fetch_url
from vpn_config import PROVIDER_MAP

_ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
_LIB = os.path.join(ADDON_PATH, 'resources', 'lib')

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

if ('utils' in sys.modules and
        'service.wireguard.manager' not in str(sys.modules.get('utils'))):
    del sys.modules['utils']


def run():
    addon = xbmcaddon.Addon('service.wireguard.manager')
    provider = addon.getSettingInt("vpn_provider")

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
        return

    setting_id = p_data.get("countries_setting", "selected_countries")
    raw_saved = addon.getSetting(setting_id)
    saved_ids = [s.strip() for s in raw_saved.split(",") if s.strip()]

    data = fetch_url(p_data["api_url"])
    if not data:
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
        regions = [
            r for r in data.get('regions', [])
            if isinstance(r.get('servers', {}).get('wg'), list)
            and len(r['servers']['wg']) > 0
        ]
        regions.sort(key=lambda x: x['name'])
        names = [r['name'] for r in regions]
        ids = [r['id'] for r in regions]

    preselect = [i for i, val in enumerate(ids) if val in saved_ids]
    selected = xbmcgui.Dialog().multiselect(
        f"Select {p_data['name']} Regions", names, preselect=preselect
    )

    if selected is not None:
        t_start = time.perf_counter()

        selected_ids = [ids[i] for i in selected]
        id_string = ",".join(selected_ids)

        addon.setSetting(setting_id, id_string)

        ICON_INFO = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')
        title = "[B][COLOR ffffff00]ACTION REQUIRED!!![/COLOR][/B]"
        message = (
            "Selection cached. You [B]MUST[/B] press [B]'OK'[/B] in the "
            "main settings menu to apply changes!"
        )
        xbmcgui.Dialog().notification(title, message, ICON_INFO, 2500)

        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        log_msg = f"PERF: Country selection took {t_elapsed:.2f}ms"
        log_message(log_msg, 0)


if __name__ == '__main__':
    run()
