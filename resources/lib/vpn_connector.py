""" ./resources/lib/vpn_connector.py """
import kodi_env
import os
import subprocess
import time
from logger import log_message
from vpn_config import (
    CONNMAN_SETTLE_DELAY,
    DHCP_RECOVERY_DELAY,
    PROVIDER_MAP,
    ROUTE_PROP_DELAY,
    VPN_CONNECTION_TIMEOUT,
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
    lock_path = get_file_path("connector_lock")

    try:
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
                log_message(f"VPN Connector: Killswitch Firewall engaged for IP {server_ip}", 1)
            else:
                log_message(f"VPN Connector: Killswitch Firewall enabled but could not extract IP from SID '{sid}'", 2)

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

        if CONNMAN_SETTLE_DELAY > 0:
            if HAS_KODI is True:
                xbmc.sleep(CONNMAN_SETTLE_DELAY)
            else:
                time.sleep(CONNMAN_SETTLE_DELAY / 1000.0)

        connected = False
        max_steps = int(VPN_CONNECTION_TIMEOUT / DHCP_RECOVERY_DELAY)
        step_percent = 100.0 / max_steps

        for i in range(1, max_steps + 1):
            if pbg and HAS_KODI:
                msg_str = f"Verifying... ({int((i * DHCP_RECOVERY_DELAY) / 1000)}s)"
                pbg.update(int(i * step_percent), message=msg_str)
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

            try:
                disable_connman_ipv6()
            except Exception:
                pass

            if HAS_KODI is True:
                xbmc.sleep(ROUTE_PROP_DELAY)
            else:
                time.sleep(ROUTE_PROP_DELAY / 1000.0)

            set_secure_dns(vpn_name, vpn_active=True)

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
                else:
                    import sys
                    frame_trace = ""
                    try:
                        curr_frame = sys._getframe()
                        while curr_frame:
                            f_name = curr_frame.f_code.co_filename
                            if f_name:
                                frame_trace += f"|{os.path.basename(f_name)}"
                            curr_frame = curr_frame.f_back
                    except Exception:
                        pass

                    if silent is True and "tunnel_checker" in frame_trace:
                        title = "[B][COLOR FF00FFFF]▄■ [ SYSTEM RESTART ] ■▄[/COLOR][/B]"
                        msg = (
                            f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
                            f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • "
                            f"[COLOR FFFF8C00]({country})[/COLOR] •[/B]"
                        )
                        xbmcgui.Dialog().notification(title, msg, icon_con, 4500)
                    elif silent is True and "service_loop" in frame_trace:
                        title = "[B][COLOR FF00FFFF]▄■ [ MAPPED CONNECT ] ■▄[/COLOR][/B]"
                        msg = (
                            f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
                            f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • "
                            f"[COLOR FFFF8C00]({country})[/COLOR] •[/B]"
                        )
                        xbmcgui.Dialog().notification(title, msg, icon_con, 4500)
                    elif silent is True and "service_launcher" in frame_trace:
                        title = "[B][COLOR FF00FFFF]▄■ [ SYSTEM REBOOT ] ■▄[/COLOR][/B]"
                        msg = (
                            f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
                            f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • "
                            f"[COLOR FFFF8C00]({country})[/COLOR] •[/B]"
                        )
                        xbmcgui.Dialog().notification(title, msg, icon_con, 4500)
                    else:
                        title = "[B][COLOR FF00FF00]▄■ [ CONNECTED ] ■▄[/COLOR][/B]"
                        msg = (
                            f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
                            f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • "
                            f"[COLOR FFFF8C00]({country})[/COLOR] •[/B]"
                        )
                        xbmcgui.Dialog().notification(title, msg, icon_con, 4500)

            return True

        if killswitch:
            killswitch.disable()

        err_msg = "Internet lost."
        if get_default_gateway():
            err_msg = "Handshake failed. Refused, rate-limited, or unreachable."

        if silent is True:
            log_message("VPN Connector: Routing profile transition in progress. Retrying step...", 1)
            if HAS_KODI is True:
                addon_path = kodi_env.ADDON_DIR
                icon_force = os.path.join(addon_path, "resources", "media", "force.png")
                title = "[B][COLOR FFFFFF00]▄■ [ TUNNELLING ] ■▄[/COLOR][/B]"
                msg = f" [B]═≡═ [COLOR FFFFFF00]{vpn_name}[/COLOR] ═≡═[/B]\n[B]Syncing kernel routing state...[/B]"
                xbmcgui.Dialog().notification(title, msg, icon_force, 1500)
        else:
            log_message(f"VPN Connector: {err_msg}", 3)

        if silent is False and HAS_KODI is True:
            addon_path = kodi_env.ADDON_DIR
            icon_error = os.path.join(addon_path, "resources", "media", "error.png")
            xbmcgui.Dialog().notification("[B][COLOR ffff0000]▀■▄ VPN FAILURE ▄■▀[/COLOR][/B]", err_msg, icon_error, 5000)

        subprocess.run(["connmanctl", "disconnect", sid], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        instance.disconnect_vpn(silent=True, flush_dns=False)
        flush_connman_dns_cache()
        return False

    except Exception as connector_fault:
        log_message(f"VPN Connector: Critical framework core failure: {connector_fault}", 3)
        return False

    finally:
        if lock_path is not None and os.path.exists(lock_path) is True:
            try:
                os.remove(lock_path)
            except Exception:
                pass
        kodi_env.clear_script_globals()
