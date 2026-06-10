""" ./resources/lib/vpn_connector.py """
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
from vpn_utils import flush_connman_dns_cache

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
    lock_path = "/tmp/vpn_connector_active.lock"
    try:
        with open(lock_path, "w") as f:
            f.write(str(os.getpid()))
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass
    provider_id = _ADDON.getSettingInt("vpn_provider") if (HAS_KODI and _ADDON) else 0
    from vpn_utils import is_interface_active, fetch_vpn_metadata, setup_pia_handshake
    p_data = PROVIDER_MAP.get(provider_id, {})
    p_name = p_data.get("name", "").lower()
    if p_name == "pia":
        log_message("VPN Connector: PIA route detected. Triggering API handshake...", 0)
        if not setup_pia_handshake(sid, p_data, _ADDON, HAS_KODI):
            try:
                os.remove(lock_path)
            except Exception:
                pass
            return False
    log_message(f"VPN Connector: Connecting to {vpn_name}", 0)
    disable_connman_ipv6()
    flush_connman_dns_cache()
    pbg = None
    if not silent and HAS_KODI:
        pbg = xbmcgui.DialogProgressBG()
        pbg.create("VPN Manager", f"Connecting to {vpn_name}...")
    subprocess.run(["connmanctl", "connect", sid], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    connected = False
    max_steps = int(VPN_CONNECTION_TIMEOUT / DHCP_RECOVERY_DELAY)
    step_percent = 100.0 / max_steps
    for i in range(1, max_steps + 1):
        if pbg and HAS_KODI:
            pbg.update(int(i * step_percent), message=f"Verifying... ({int((i * DHCP_RECOVERY_DELAY) / 1000)}s)")
        if is_interface_active("wg0"):
            connected = True
            break
        if HAS_KODI:
            xbmc.sleep(DHCP_RECOVERY_DELAY)
        else:
            time.sleep(DHCP_RECOVERY_DELAY / 1000.0)
    if pbg and HAS_KODI:
        pbg.close()
    if connected:
        log_message(f"VPN Connector: Successfully connected to {vpn_name}", 1)
        subprocess.run(["ip", "route", "flush", "cache"], check=False)
        instance.set_active_vpn(vpn_name)
        set_secure_dns(vpn_name, vpn_active=True)
        if HAS_KODI:
            xbmc.sleep(ROUTE_PROP_DELAY)
        else:
            time.sleep(ROUTE_PROP_DELAY / 1000.0)
        if not silent and HAS_KODI:
            ip, country = fetch_vpn_metadata()
            if ip is not None and ip != "":
                title = "[B][COLOR FF00FF00]▄■ [ CONNECTED ] ■▄[/COLOR][/B]"
                msg = (
                    f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
                    f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • [COLOR FFFF8C00]({country})[/COLOR][/B]"
                )
            else:
                title = "[B][COLOR FFFFFF00]▄■ [ CONNECTED ] ■▄[/COLOR][/B]"
                msg = f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n[B]Tunnel active[/B]"
            xbmcgui.Dialog().notification(title, msg, ICON_CON, 4500)
        try:
            os.remove(lock_path)
        except Exception:
            pass
        return True
    err_msg = (
        "Handshake failed. Refused, rate-limited, or unreachable."
        if get_default_gateway() else "Internet lost."
    )
    log_message(f"VPN Connector: VPN connection, handshake failed. {err_msg}", 3)
    if not silent and HAS_KODI:
        xbmcgui.Dialog().notification("[B][COLOR ffff0000]▀■▄ VPN FAILURE ▄■▀[/COLOR][/B]", err_msg, ICON_ERROR, 5000)
    subprocess.run(["connmanctl", "disconnect", sid], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    flush_connman_dns_cache()
    instance.disconnect_vpn(silent=True, flush_dns=False)
    try:
        os.remove(lock_path)
    except Exception:
        pass
    return False
