''' ./resources/lib/vpn_utils.py '''
import os
import json
import socket
import ssl
import subprocess
from logger import log_message
from providers import pia

try:
    import xbmc
    import xbmcaddon
    import xbmcgui
    import xbmcvfs
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

ADDON_ID = 'service.wireguard.manager'

if HAS_KODI:
    try:
        ADDON_PATH = xbmcvfs.translatePath(xbmcaddon.Addon(ADDON_ID).getAddonInfo('path'))
    except Exception:
        ADDON_PATH = '/storage/.kodi/addons/service.wireguard.manager'
else:
    ADDON_PATH = '/storage/.kodi/addons/service.wireguard.manager'

ICON_INFO = os.path.join(ADDON_PATH, 'resources', 'media', 'icon.png')
ICON_ERROR = os.path.join(ADDON_PATH, 'resources', 'media', 'error.png')


def is_interface_active(interface_name="wg0"):
    return os.path.exists(f"/sys/class/net/{interface_name}")


def verify_tunnel_routing(test_ip="1.1.1.1", timeout=1.5):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((test_ip, 53))
        return True
    except Exception:
        return False


def fetch_vpn_metadata():
    try:
        res = subprocess.check_output(
            ["curl", "-s", "-k", "--connect-timeout", "1.0", "--max-time", "1.5", "https://1.1.1.1/cdn-cgi/trace"],
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
            return ip, country
    except Exception:
        pass

    try:
        res = subprocess.check_output(
            ["curl", "-s", "--connect-timeout", "1.0", "--max-time", "5", "https://ipinfo.io"],
            text=True
        )
        data = json.loads(res)
        if "ip" in data:
            return data.get("ip", "Unknown"), data.get("country", "??")
    except Exception:
        pass

    try:
        res = subprocess.check_output(
            ["curl", "-s", "--connect-timeout", "1.0", "--max-time", "1.5", "https://geojs.io"],
            text=True
        )
        data = json.loads(res)
        if "ip" in data:
            return data.get("ip", "Unknown"), data.get("country", "??")
    except Exception as e:
        log_message(f"VPN_Utils: All metadata fallbacks failed: {e}", 2)

    return None, None


def setup_pia_handshake(sid, provider_data, addon_obj, has_kodi):
    try:
        import re
        from wm_utils import safe_decrypt_password

        user = str(addon_obj.getSetting("pia_user")).strip().lower()
        raw_pw = addon_obj.getSetting("pia_pass")
        pw = safe_decrypt_password(raw_pw)
        config_path = None
        region_id = None
        conf_dir = '/storage/.config/wireguard/'
        target_suffix = sid.replace('vpn_provider_wireguard_pia_', '').replace('vpn_pia_', '')

        for filename in os.listdir(conf_dir):
            if filename.startswith("pia_") and filename.endswith(".config"):
                file_id = filename.replace('pia_', '').replace('.config', '')
                if file_id.lower() == target_suffix.lower():
                    config_path = os.path.join(conf_dir, filename)
                    region_id = file_id
                    break

        if not config_path:
            return True

        target_ip = ""
        pool_cns = []
        original_name = None

        with open(config_path, 'r') as f:
            content = f.read()
            host_match = re.search(r'^\s*Host\s*=\s*(.*)', content, re.MULTILINE)
            if host_match:
                target_ip = host_match.group(1).strip()

            name_match = re.search(r'^\s*Name\s*=\s*(.*)', content, re.MULTILINE)
            if name_match:
                original_name = name_match.group(1).strip().replace("PIA_", "")

            cn_pool_match = re.search(r'^\s*WireGuard\.CN_Pool\s*=\s*(.*)', content, re.MULTILINE)
            if cn_pool_match:
                pool_cns = [c.strip() for c in cn_pool_match.group(1).split(',') if c.strip()]

        if not target_ip:
            log_message("PIA VPN_Utils: Critical Error - Could not extract Host IP from file.", 3)
            return False

        if not pool_cns:
            log_message(f"PIA VPN_Utils: CN pool missing in file, fetching from API for {region_id}", 1)
            try:
                import urllib.request
                url = provider_data.get('api_url')
                if url:
                    ctx = ssl._create_unverified_context()
                    req = urllib.request.Request(url, headers={'User-Agent': 'PIA-VPN/3.5.0 (Linux)'})
                    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                        raw_data = resp.read().decode('utf-8').strip()
                        clean_raw = raw_data.split("\n")[0].strip() if "\n" in raw_data else raw_data.strip()
                        api_data = json.loads(clean_raw)

                        for r in api_data.get('regions', []):
                            if r['id'].lower() == region_id.lower():
                                wg_servers = r.get('servers', {}).get('wg', [])
                                if wg_servers:
                                    if isinstance(wg_servers, list) and len(wg_servers) > 0:
                                        pool_cns = []
                                        for srv in wg_servers:
                                            if isinstance(srv, dict) and srv.get('ip') == target_ip:
                                                if srv.get('cn'):
                                                    pool_cns.append(srv.get('cn'))
                                        if not pool_cns:
                                            pool_cns = [wg_servers[0].get('cn', '')]
                                    elif isinstance(wg_servers, dict):
                                        pool_cns = [wg_servers.get('cn', '')]
                                break
            except Exception as e:
                log_message(f"PIA VPN_Utils: API fetch error for region {region_id}: {e}", 3)

        if not pool_cns:
            log_message("PIA VPN_Utils: Error - No CN nodes available for handshake.", 3)
            return False

        live_cfg = None

        for current_cn in pool_cns:
            if current_cn.lower().startswith('server-'):
                clean_cn = current_cn.strip().replace('server-', 'Server-')
            else:
                clean_cn = current_cn.strip()

            log_message(f"PIA VPN_Utils: Handshake attempt for {region_id} using CN {clean_cn}", 1)
            live_cfg = pia.get_live_config(user, pw, target_ip, clean_cn, region_id, region_name=original_name)

            if live_cfg and "[provider_wireguard]" in live_cfg:
                break

        if live_cfg and "[provider_wireguard]" in live_cfg:
            log_message(f"PIA VPN_Utils: Handshake for {region_id} completed using IP {target_ip}", 1)
            with open(config_path, 'w') as f:
                f.write(live_cfg)
                if has_kodi:
                    xbmc.sleep(1500)
            return True
        else:
            log_message(f"PIA VPN_Utils: Handshake declined by server. Raw response: {live_cfg}", 2)
            return False

    except Exception as general_err:
        log_message(f"PIA VPN_Utils: Critical runtime error: {general_err}", 3)
        return False

    except Exception as e:
        err_str = str(e)
        log_message(f"PIA VPN_Utils: {err_str}", 3)

        if "429" in err_str or "Too Many Requests" in err_str:
            title = "[B]≡ [ API RATE LIMIT ] ≡[/B]"
            msg = (
                "[COLOR ffff0000]PIA API Blocked Your Connection Request![/COLOR]\n\n"
                "Your IP address has been temporarily rate-limited due to too many rapid configuration changes.\n\n"
                "[COLOR ffffff00]SOLUTION:[/COLOR] Please wait [B]15 minutes[/B] before starting this video addon again."
            )
            if has_kodi:
                xbmc.executebuiltin("ActivateWindow(home)")
                xbmcgui.Dialog().ok(title, msg)
                log_message("VPN_Utils: PIA API Blockade Connection Request start", 2)
                xbmc.Monitor().waitForAbort(15)
                log_message("VPN_Utils: PIA API Blockade Connection Request over.", 2)
                title = "[B][COLOR FFE6E6FA]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
                msg = "[COLOR FFFFFF00]PIA API Blockade over you can connect to PIA again.[/COLOR]"
                xbmcgui.Dialog().notification(title, msg, ICON_INFO, 5000)
        else:
            title = "[B]≡ [ CONNECTION FAILURE ] ≡[/B]"
            msg = (
                "[COLOR ffff0000]VPN Handshake Failed to Establish![/COLOR]\n\n"
                f"System Error: [COLOR ffffff00]{err_str}[/COLOR]\n\n"
                "The manager was unable to reach the PIA authorization nodes."
            )
            if has_kodi:
                xbmc.executebuiltin("ActivateWindow(home)")
                xbmcgui.Dialog().ok(title, msg)
                log_message("VPN_Utils: PIA Connection Cool Down start", 2)
                xbmc.Monitor().waitForAbort(10)
                log_message("VPN_Utils: PIA Connection Cool Down over.", 2)
                title = "[B][COLOR FFE6E6FA]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
                msg = "[COLOR FFFFFF00]Network cool down over. Ready to retry connection.[/COLOR]"
                xbmcgui.Dialog().notification(title, msg, ICON_INFO, 5000)

        return False
