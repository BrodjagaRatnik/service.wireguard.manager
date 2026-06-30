""" ./resources/lib/vpn_utils.py """
import kodi_env
import json
import subprocess
import time
import datetime
from logger import log_message
from vpn_config import CONNMAN_RESTART_DELAY

try:
    import xbmc
    HAS_KODI = True
except ImportError:
    HAS_KODI = False


def get_addon_path():
    return kodi_env.ADDON_DIR


def is_interface_active(interface_name="wg0"):
    try:
        with open("/proc/net/dev", "r") as f:
            content = f.read()
            return f"{interface_name}:" in content
    except Exception:
        return False


def flush_connman_dns_cache():
    try:
        subprocess.run(["systemctl", "restart", "connman"], check=False)
        subprocess.run(["systemctl", "restart", "connman-vpn"], check=False)

        if HAS_KODI is True:
            xbmc.sleep(CONNMAN_RESTART_DELAY)
        else:
            time.sleep(CONNMAN_RESTART_DELAY / 1000.0)
        try:
            vpn_out = subprocess.check_output(["connmanctl", "services"], text=True)
            for vpn_line in vpn_out.splitlines():
                if "vpn_" in vpn_line and any(state in vpn_line for state in ["* ", "R "]):
                    vpn_parts = vpn_line.strip().split()
                    if vpn_parts:
                        subprocess.run(
                            ["connmanctl", "disconnect", vpn_parts[-1]],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
        except Exception:
            pass

        out = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in out.splitlines():
            if "_" in line and any(x in line for x in ("ethernet_", "wifi_")):
                parts = line.strip().split()
                if not parts:
                    continue
                srv_id = parts[-1]
                subprocess.run(["connmanctl", "config", srv_id, "--nameservers"], check=False)
                ipv4_info = subprocess.check_output(
                    ["connmanctl", "service", srv_id, "ipv4"],
                    text=True, stderr=subprocess.DEVNULL
                ).replace(" ", "")
                if "Method=dhcp" in ipv4_info:
                    subprocess.run(["connmanctl", "config", srv_id, "--ipv4", "dhcp"], check=False)

        subprocess.run(["ip", "link", "delete", "wg0"], stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["ip", "route", "flush", "cache"], check=False)
        subprocess.run(["ip", "route", "show", "match", "0.0.0.0/0"], check=False)
    except Exception:
        pass


def get_active_interface():
    for attempt in range(2):
        try:
            out = subprocess.check_output(
                ["ip", "route", "show", "default"],
                text=True,
                stderr=subprocess.DEVNULL
            )
            interfaces = []
            for line in out.splitlines():
                parts = line.split()
                if "dev" in parts:
                    dev_idx = parts.index("dev") + 1
                    if dev_idx < len(parts):
                        interfaces.append(parts[dev_idx])
            for iface in interfaces:
                if "wg" in iface.lower() or "vpn" in iface.lower():
                    return str(iface)
            if interfaces:
                return str(interfaces[0])
        except Exception as e:
            log_message(f"VPN_Utils: Interface lookup error: {e}", 3)
            return None
        if attempt == 0:
            time.sleep(0.15)
    return None


def check_interface_status():
    try:
        out = subprocess.check_output(["connmanctl", "services"], text=True)
        eth = any(line.startswith("*") and "ethernet" in line for line in out.splitlines())
        wifi = any(line.startswith("*") and "wifi" in line for line in out.splitlines())
        return eth, wifi
    except Exception as e:
        log_message(f"VPN_Utils: Interface status validation check failure: {e}", 3)
        return False, False


def fetch_vpn_metadata():
    t_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    try:
        res = subprocess.check_output(
            [
                "curl", "-s", "-k",
                "--interface", "wg0",
                "--connect-timeout", "4.0",
                "--max-time", "6.0",
                "https://1.1.1.1/cdn-cgi/trace"
            ],
            text=True
        )
        ip = "Unknown"
        country = "??"
        for line in res.splitlines():
            if line.startswith("ip="):
                ip = line.split("=")[1].strip()
            if line.startswith("loc="):
                country = line.split("=")[1].strip()
        if ip != "Unknown":
            log_message(f"VPN_Utils: Cloudflare trace provider selected at {t_stamp}", 0)
            return ip, country
    except Exception:
        pass

    try:
        res = subprocess.check_output(
            [
                "curl", "-s", "--interface", "wg0",
                "--connect-timeout", "4.0", "--max-time", "6.0",
                "https://ipinfo.io"
            ],
            text=True
        )
        if res and res.strip():
            data = json.loads(res)
            if "ip" in data:
                log_message(f"VPN_Utils: Ipinfo provider selected at {t_stamp}", 0)
                return data.get("ip", "Unknown"), data.get("country", "??")
    except Exception:
        pass

    try:
        res = subprocess.check_output(
            [
                "curl", "-s", "--interface", "wg0",
                "--connect-timeout", "4.0", "--max-time", "6.0",
                "https://geojs.io"
            ],
            text=True
        )
        if res and res.strip():
            data = json.loads(res)
            if "ip" in data:
                log_message(f"VPN_Utils: Geojs provider selected at {t_stamp}", 0)
                return data.get("ip", "Unknown"), data.get("country", "??")
    except Exception as e:
        log_message(f"VPN_Utils: All metadata fallbacks failed at {t_stamp}: {e}", 2)

    if HAS_KODI:
        try:
            import xbmcgui
            title = "[B][COLOR FFFF0000]VPN Connection Error[/COLOR][/B]"
            msg = "[COLOR FFE6E6FA]Data path blocked. Please update configs or choose another country/region.[/COLOR]"
            xbmcgui.Dialog().ok(title, msg)
        except Exception:
            pass

    return None, None


def setup_pia_handshake(sid, provider_data, addon_obj, has_kodi):
    from providers.pia_utils import setup_pia_handshake as resolve_pia_handshake
    try:
        return resolve_pia_handshake(sid, provider_data, addon_obj, has_kodi)
    finally:
        kodi_env.clear_script_globals()
