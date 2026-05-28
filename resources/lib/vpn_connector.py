''' ./resources/lib/vpn_connector.py '''
import os
import subprocess
import time
from logger import log_message
from vpn_config import (
    DHCP_RECOVERY_DELAY,
    PROVIDER_MAP,
    ROUTE_PROP_DELAY,
    VPN_CONNECTION_TIMEOUT,
)
from network_utils import (
    set_secure_dns,
    disable_connman_ipv6,
    get_default_gateway
)

try:
    import xbmc
    import xbmcaddon
    import xbmcgui
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

ADDON_ID = 'service.wireguard.manager'

if HAS_KODI:
    _ADDON = xbmcaddon.Addon(ADDON_ID)
    ADDON_PATH = _ADDON.getAddonInfo('path')
else:
    _ADDON = None
    ADDON_PATH = '/storage/.kodi/addons/service.wireguard.manager'

ICON_CON = os.path.join(ADDON_PATH, 'resources', 'media', 'vpn_connected.png')
ICON_ERROR = os.path.join(ADDON_PATH, 'resources', 'media', 'error.png')
ICON_INFO = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')


def connect_vpn(vpn_name, sid, instance, silent=False):
    provider_id = _ADDON.getSettingInt("vpn_provider") if (HAS_KODI and _ADDON) else 0

    from vpn_utils import is_interface_active, verify_tunnel_routing, fetch_vpn_metadata, setup_pia_handshake

    if provider_id == 1:
        p_data = PROVIDER_MAP.get(provider_id, {})
        pia_success = setup_pia_handshake(sid, p_data, _ADDON, HAS_KODI)
        if not pia_success:
            return False

    log_message(f"Operation: Connecting to {vpn_name}", 0)
    disable_connman_ipv6()

    pbg = None
    if not silent and HAS_KODI:
        pbg = xbmcgui.DialogProgressBG()
        pbg.create("VPN Manager", f"Connecting to {vpn_name}...")

    subprocess.run(["connmanctl", "connect", sid], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    connected = False
    MAX_STEPS = int(VPN_CONNECTION_TIMEOUT / DHCP_RECOVERY_DELAY)
    STEP_PERCENT = 100.0 / MAX_STEPS

    for i in range(1, MAX_STEPS + 1):
        if pbg and HAS_KODI:
            pbg.update(int(i * STEP_PERCENT), message=f"Verifying... ({int((i*DHCP_RECOVERY_DELAY)/1000)}s)")

        if is_interface_active("wg0") and verify_tunnel_routing():
            connected = True
            break

        if HAS_KODI:
            xbmc.sleep(DHCP_RECOVERY_DELAY)
        else:
            time.sleep(DHCP_RECOVERY_DELAY / 1000.0)

    if pbg and HAS_KODI:
        pbg.close()

    if connected:
        log_message(f"Operation: Successfully connected to {vpn_name}", 1)
        subprocess.run(["ip", "route", "flush", "cache"], check=False)
        instance.set_active_vpn(vpn_name)
        set_secure_dns(vpn_name, vpn_active=True)

        if HAS_KODI:
            xbmc.sleep(ROUTE_PROP_DELAY)
        else:
            time.sleep(ROUTE_PROP_DELAY / 1000.0)

        if not silent and HAS_KODI:
            ip, country = fetch_vpn_metadata()
            if ip:
                title = "[B][COLOR FF00FF00]▄■ [ CONNECTED ] ■▄[/COLOR][/B]"
                msg = (
                    f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
                    f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • [COLOR FFFF8C00]({country})[/COLOR][/B]"
                )
            else:
                title = "[B][COLOR FFFFFF00]▄■ [ CONNECTED ] ■▄[/COLOR][/B]"
                msg = f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n[B]Tunnel active[/B]"
            xbmcgui.Dialog().notification(title, msg, ICON_CON, 4500)

        return True

    if not silent and HAS_KODI:
        err_msg = "Handshake failed. Check credentials." if get_default_gateway() else "Internet lost."
        xbmcgui.Dialog().notification("[B][COLOR ffff0000]▀■▄ VPN FAILURE ▄■▀[/COLOR][/B]", err_msg, ICON_ERROR, 5000)

    instance.disconnect_vpn(silent=True)
    return False
