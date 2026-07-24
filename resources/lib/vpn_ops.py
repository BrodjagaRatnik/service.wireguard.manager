""" ./resources/lib/vpn_ops.py """
import kodi_env
import os
import subprocess
import time
from logger import log_message
from vpn_config import (
    DHCP_RECOVERY_DELAY,
    OS_RELEASE_DELAY,
    PROP_SYNC_DELAY,
    PROVIDER_MAP,
    PI5,
    PI4,
    PI3,
    PI2,
)
from network_utils import (
    set_secure_dns,
    enable_connman_ipv6,
    get_default_gateway,
    verify_and_fix_dns,
)
from vpn_utils import flush_connman_dns_cache
from state_manager import get_file_path, set_active_vpn
from resources.scripts.killswitch import ZeroHardcodeKillSwitch

try:
    import xbmc
    import xbmcgui
    HAS_KODI = True
except ImportError:
    HAS_KODI = False


def get_addon_path():
    return kodi_env.ADDON_DIR


def disconnect_vpn(silent=False, flush_dns=True):
    start_time = time.perf_counter()

    try:
        fallback_ks = ZeroHardcodeKillSwitch(vpn_server_ip="0.0.0.0")
        fallback_ks.enabled = True
        fallback_ks.disable()
    except Exception as ks_err:
        log_message(f"VPN Ops: Killswitch manual disengage wrapper error: {ks_err}", 2)

    if silent is False and HAS_KODI is True:
        xbmcgui.Window(10000).setProperty("vpn_manual_session", "")

    paths_to_clean = []
    manual_path = get_file_path("manual")
    if manual_path is not None:
        paths_to_clean.append(manual_path)

    for path in paths_to_clean:
        if os.path.exists(path) is True:
            try:
                os.remove(path)
            except Exception as e:
                log_message(f"VPN Ops: Disconnect error removing {path}: {e}", 3)

    intentional_path = get_file_path("disconnect")
    if intentional_path is not None:
        try:
            open(intentional_path, "w").close()
        except Exception as e:
            log_message(f"VPN Ops: Disconnect error creating intentional flag file: {e}", 3)

    if HAS_KODI is True:
        xbmcgui.Window(10000).setProperty("vpn_intentional_disconnect", "true")
        xbmcgui.Window(10000).setProperty("vpn_manual_session", "")
        xbmc.sleep(PROP_SYNC_DELAY)
    else:
        time.sleep(PROP_SYNC_DELAY / 1000.0)

    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        p_names = "|".join([p["name"] for p in PROVIDER_MAP.values()])

        for line in out.splitlines():
            if (("vpn_" in line or any(p in line for p in p_names.split("|")))
                    and ("* " in line or "R " in line)):
                subprocess.run(
                    ["connmanctl", "disconnect", line.split()[-1]],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

    except Exception as e:
        log_message(f"VPN Ops: Disconnect Error {e}", 3)

    try:
        local_gw = get_default_gateway()
        gw_out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        local_dev = None
        for line in gw_out.splitlines():
            if "dev" in line and "wg0" not in line:
                local_dev = line.split("dev")[1].strip().split()[0]
                break

        if local_gw is not None and local_dev is not None:
            current_routes = subprocess.check_output(["ip", "route", "show"], text=True)
            for line in current_routes.splitlines():
                if f"via {local_gw}" in line and f"dev {local_dev}" in line:
                    parts = line.split()
                    if parts and parts[0] != "default":
                        subprocess.run(
                            ["ip", "route", "del", parts[0], "via", local_gw, "dev", local_dev],
                            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
    except Exception:
        pass

    if flush_dns is True:
        flush_connman_dns_cache()

    set_secure_dns(vpn_active=False)
    set_active_vpn(None)

    if silent is False:
        if HAS_KODI is True:
            xbmc.sleep(OS_RELEASE_DELAY)
        else:
            time.sleep(OS_RELEASE_DELAY / 1000.0)
    try:
        enable_connman_ipv6()
        flush_connman_dns_cache()
    except Exception as e:
        log_message(f"VPN Ops: Post-disconnect IPv6 restoration failed: {e}", 3)

    if silent is False and HAS_KODI is True:
        addon_path = get_addon_path()
        icon_dis = os.path.join(addon_path, "resources", "media", "vpn_disconnected.png")
        title = "[B][COLOR FFDF00FF]▄■ [ VPN Network ] ■▄[/COLOR][/B]"
        msg = "[B]╠══ [COLOR FFDF00FF][ DISCONNECTED ][/COLOR] ══╣[/B]"
        xbmcgui.Dialog().notification(title, msg, icon_dis, 4500)

    gw = get_default_gateway()
    if not gw:
        log_message("VPN Ops: Default route lost. Attempting restoration...", 0)
        try:
            out = subprocess.check_output(["connmanctl", "services"], text=True)
            phys_service = next(
                (
                    line.split()[-1] for line in out.splitlines()
                    if line.startswith(("*", "R")) and "vpn_" not in line
                ),
                None
            )

            if phys_service:
                subprocess.run(["connmanctl", "config", phys_service, "--ipv4", "dhcp"], check=False)
                log_message(f"Operation: DHCP Recovery ({DHCP_RECOVERY_DELAY}ms)", 0)
                if HAS_KODI is True:
                    xbmc.sleep(DHCP_RECOVERY_DELAY)
                else:
                    time.sleep(DHCP_RECOVERY_DELAY / 1000.0)
                gw = get_default_gateway()
        except Exception as e:
            log_message(f"VPN Ops: Route restoration failure: {e}", 3)

    if gw:
        try:
            out_route = subprocess.check_output(["ip", "route", "show", "default"], text=True)
            route_is_missing = "default" not in out_route
            serv = subprocess.check_output(["connmanctl", "services"], text=True)
            target_dev = "eth0" if "ethernet" in serv else "wlan0"
            subprocess.run(["ip", "route", "replace", "default", "via", gw, "dev", target_dev], check=False)
            if route_is_missing is True:
                log_message(f"VPN Ops: Route restored via {gw} on {target_dev}", 0)
        except Exception as e:
            log_message(f"VPN Ops: Route Restore Error {e}", 3)

    if HAS_KODI is True:
        xbmcgui.Window(10000).setProperty("vpn_intentional_disconnect", "")

    if intentional_path is not None and os.path.exists(intentional_path) is True:
        try:
            os.remove(intentional_path)
        except Exception as e:
            log_message(f"VPN Ops: Error removing intentional disconnect file: {e}", 3)

    try:
        verify_and_fix_dns()
    except Exception as dns_err:
        log_message(f"VPN Ops: Failed to execute verify_and_fix_dns: {dns_err}", 3)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    hw_name = (
        "Raspberry Pi 5" if PI5 else
        "Raspberry Pi 4" if PI4 else
        "Raspberry Pi 3" if PI3 else
        "Raspberry Pi 2" if PI2 else "Generic Device"
    )
    actual_allowed_timeout = OS_RELEASE_DELAY + 2000 if silent is False else 2000
    log_message(
        f"Timing Tracker: Tear-down execution completed. "
        f"Hardware Matrix: {hw_name} | "
        f"Disconnect Processing Time: {elapsed_ms:.2f}ms | "
        f"Allowed Timeout: {actual_allowed_timeout}ms", 0
    )

    kodi_env.clear_script_globals()


def connect_vpn(vpn_name, sid, silent=False):
    if not HAS_KODI:
        try:
            log_message(f"VPN Ops: Daemon-driven shell link connect sequence initiated for {vpn_name}", 1)
            res = subprocess.run(["connmanctl", "connect", str(sid)], check=False, capture_output=True, text=True)
            if res.returncode == 0 or "Already connected" in res.stderr or "Already connected" in res.stdout:
                set_active_vpn(vpn_name)
                return True
            log_message(f"VPN Ops: Shell connection failure stdout: {res.stdout} stderr: {res.stderr}", 3)
            return False
        except Exception as shell_err:
            log_message(f"VPN Ops: Daemon fallback connector critical exception: {shell_err}", 3)
            return False
        finally:
            kodi_env.clear_script_globals()

    import vpn_connector
    import sys
    instance = sys.modules[__name__]
    try:
        return vpn_connector.connect_vpn(vpn_name, sid, instance, silent=silent)
    finally:
        kodi_env.clear_script_globals()
