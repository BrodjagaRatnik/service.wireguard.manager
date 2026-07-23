""" ./resources/lib/vpn_connector.py """
import kodi_env
import os
import subprocess
import time
from logger import log_message
from vpn_config import (
    DHCP_RECOVERY_DELAY,
    PROVIDER_MAP,
    ROUTE_PROP_DELAY,
    VPN_CONNECTION_TIMEOUT,
    PI5,
    PI4,
    PI3,
    PI2,
)
from network_utils import (
    set_secure_dns,
    get_default_gateway,
    disable_connman_ipv6
)
from vpn_utils import (
    flush_connman_dns_cache,
    is_interface_active,
    fetch_vpn_metadata,
    setup_pia_handshake
)
from state_manager import get_file_path
from providers.routing import setup_vpn_routing
from resources.scripts.killswitch import ZeroHardcodeKillSwitch

try:
    import xbmc
    import xbmcgui
    HAS_KODI = True
except ImportError:
    HAS_KODI = False


def connect_vpn(vpn_name, sid, instance, silent=False):
    start_time = time.perf_counter()

    lock_path = get_file_path("connector_lock")
    if lock_path is not None:
        try:
            with open(lock_path, "w") as f:
                f.write(str(os.getpid()))
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass

    addon_obj = kodi_env.get_addon_instance()
    provider_id = addon_obj.getSettingInt("vpn_provider") if (HAS_KODI and addon_obj) else 0
    p_data = PROVIDER_MAP.get(provider_id, {})
    p_name = p_data.get("name", "").lower()
    if p_name == "pia":
        log_message("VPN Connector: PIA route detected. Triggering API handshake...", 0)
        if setup_pia_handshake(sid, p_data, addon_obj, HAS_KODI) is False:
            if lock_path is not None and os.path.exists(lock_path) is True:
                try:
                    os.remove(lock_path)
                except Exception:
                    pass
            kodi_env.clear_script_globals()
            return False
    log_message(f"VPN Connector: Connecting to {vpn_name}", 0)

    ks_enabled = addon_obj.getSettingBool("enable_killswitch") if (HAS_KODI and addon_obj) else False
    killswitch = None

    if ks_enabled:
        server_ip = None

        if sid and sid.startswith("vpn_"):
            server_ip = sid[4:].replace("_", ".")

        if server_ip:
            killswitch = ZeroHardcodeKillSwitch(vpn_server_ip=server_ip)
            killswitch.enable()
            xbmc.log(f"WireGuard Manager: Killswitch direct engaged for IP {server_ip}", xbmc.LOGINFO)
        else:
            log_message(f"VPN Connector: Killswitch enabled but could not extract IP from SID '{sid}'", 2)

    pbg = None
    if silent is False and HAS_KODI is True:
        pbg = xbmcgui.DialogProgressBG()
        pbg.create("VPN Manager", f"Connecting to {vpn_name}...")
    subprocess.run(
        ["connmanctl", "connect", sid],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    connected = False
    max_steps = int(VPN_CONNECTION_TIMEOUT / DHCP_RECOVERY_DELAY)
    step_percent = 100.0 / max_steps
    for i in range(1, max_steps + 1):
        if pbg and HAS_KODI:
            pbg.update(int(i * step_percent), message=f"Verifying... ({int((i * DHCP_RECOVERY_DELAY) / 1000)}s)")
        if is_interface_active("wg0") is True:
            connected = True
            break
        if HAS_KODI is True:
            xbmc.sleep(DHCP_RECOVERY_DELAY)
        else:
            time.sleep(DHCP_RECOVERY_DELAY / 1000.0)
    if pbg and HAS_KODI:
        pbg.close()
    if connected is True:
        log_message(f"VPN Connector: Successfully connected to {vpn_name}", 1)
        setup_vpn_routing(sid, bool(p_data.get("requires_endpoint_route")))
        subprocess.run(["ip", "route", "flush", "cache"], check=False)
        instance.set_active_vpn(vpn_name)
        set_secure_dns(vpn_name, vpn_active=True)
        if HAS_KODI is True:
            xbmc.sleep(ROUTE_PROP_DELAY)
        else:
            time.sleep(ROUTE_PROP_DELAY / 1000.0)
        try:
            disable_connman_ipv6()
        except Exception:
            pass

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        hw_name = (
            "Raspberry Pi 5" if PI5 else
            "Raspberry Pi 4" if PI4 else
            "Raspberry Pi 3" if PI3 else
            "Raspberry Pi 2" if PI2 else "Generic Device"
        )
        log_message(
            f"Timing Tracker: Interface routing settled successfully. "
            f"Hardware Matrix: {hw_name} | Settle Time: {elapsed_ms:.2f}ms | "
            f"Allowed Timeout: {VPN_CONNECTION_TIMEOUT}ms", 0
        )

        if HAS_KODI is True:
            addon_path = kodi_env.ADDON_DIR
            icon_con = os.path.join(addon_path, "resources", "media", "vpn_connected.png")
            ip, country = fetch_vpn_metadata()
            if not ip or ip == "Unknown":
                if killswitch:
                    killswitch.disable()
                title = "[B][COLOR FFFF0000]▄■ [ CONNECTION FAILED ] ■▄[/COLOR][/B]"
                msg = f" [B]═≡═ [COLOR FFFFFF00]{vpn_name}[/COLOR] ═≡═[/B]\n[B]No routing / Tunnel offline[/B]"
                xbmcgui.Dialog().notification(title, msg, xbmcgui.NOTIFICATION_ERROR, 5000)
            elif silent is True:
                title = "[B][COLOR FF00FFFF]▄■ [ SYSTEM RESTARTED ] ■▄[/COLOR][/B]"
                msg = (
                    f" [B]═≡═ [COLOR FFFFFF00]Tunnel Restored[/COLOR] ═≡═[/B]\n"
                    f"[B]Profile [COLOR FF32CD32]{vpn_name}[/COLOR] • ({country})[/B]"
                )
                xbmcgui.Dialog().notification(title, msg, icon_con, 4500)
            else:
                title = "[B][COLOR FF00FF00]▄■ [ CONNECTED ] ■▄[/COLOR][/B]"
                msg = (
                    f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
                    f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • "
                    f"[COLOR FFFF8C00]({country})[/COLOR][/B]"
                )
                xbmcgui.Dialog().notification(title, msg, icon_con, 4500)

        if lock_path is not None and os.path.exists(lock_path) is True:
            try:
                os.remove(lock_path)
            except Exception:
                pass
        kodi_env.clear_script_globals()
        return True

    if killswitch:
        killswitch.disable()

    err_msg = "Handshake failed. Refused, rate-limited, or unreachable." if get_default_gateway() else "Internet lost."
    log_message(f"VPN Connector: {err_msg}", 3)
    if silent is False and HAS_KODI is True:
        addon_path = kodi_env.ADDON_DIR
        icon_error = os.path.join(addon_path, "resources", "media", "error.png")
        xbmcgui.Dialog().notification("[B][COLOR ffff0000]▀■▄ VPN FAILURE ▄■▀[/COLOR][/B]", err_msg, icon_error, 5000)
    subprocess.run(["connmanctl", "disconnect", sid], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    instance.disconnect_vpn(silent=True, flush_dns=False)
    flush_connman_dns_cache()
    if lock_path is not None and os.path.exists(lock_path) is True:
        try:
            os.remove(lock_path)
        except Exception:
            pass
    kodi_env.clear_script_globals()
    return False
