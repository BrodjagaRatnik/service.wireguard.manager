''' ./resources/lib/vpn_utils.py '''
import os
import json
import socket
import ssl
import subprocess
import base64
import re
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


def fetch_vpn_metadata(timeout=2.5):
    try:
        res = subprocess.check_output(["curl", "-s", "--max-time", str(timeout), "https://ipinfo.io"], text=True)
        data = json.loads(res)
        return data.get("ip", "Unknown"), data.get("country", "??")
    except Exception as e:
        log_message(f"External metadata API lookup timed out/failed: {e}", 2)
        return None, None


def setup_pia_handshake(sid, provider_data, addon_obj, has_kodi):

    try:
        user = addon_obj.getSetting("pia_user")
        raw_pw = addon_obj.getSetting("pia_pass")

        try:
            clean_pw = str(raw_pw).strip()
            missing_padding = len(clean_pw) % 4
            if missing_padding:
                clean_pw += '=' * (4 - missing_padding)
            pw = base64.b64decode(clean_pw).decode('utf-8')
        except Exception as e:
            log_message(f"Password decoding failed, using raw password: {e}", 3)
            pw = raw_pw

        target_ip = sid.replace('vpn_', '').replace('_', '.')
        config_path = None
        region_id = None
        conf_dir = '/storage/.config/wireguard/'

        for filename in os.listdir(conf_dir):
            if filename.startswith("pia_") and filename.endswith(".config"):
                full_path = os.path.join(conf_dir, filename)
                with open(full_path, 'r') as f:
                    if target_ip in f.read():
                        config_path = full_path
                        region_id = filename.replace('pia_', '').replace('.config', '')
                        break

        if not config_path:
            return True

        server_cn = ""
        original_name = None

        with open(config_path, 'r') as f:
            content = f.read()
            name_match = re.search(r'^\s*Name\s*=\s*(.*)', content, re.MULTILINE)
            if name_match:
                original_name = name_match.group(1).strip().replace("PIA_", "")
            cn_match = re.search(r'#\s*CN\s*=\s*(.*)', content)
            if cn_match:
                server_cn = cn_match.group(1).strip()

        if not server_cn:
            log_message(f"PIA: CN missing in file, fetching from API for {region_id}", 0)
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
                                        for srv in wg_servers:
                                            if isinstance(srv, dict) and srv.get('ip') == target_ip:
                                                server_cn = srv.get('cn', '')
                                                break
                                        if not server_cn:
                                            first_srv = wg_servers[0]
                                            if isinstance(first_srv, dict):
                                                server_cn = first_srv.get('cn', '')
                                    elif isinstance(wg_servers, dict):
                                        server_cn = wg_servers.get('cn', '')
                                break
            except Exception as e:
                log_message(f"PIA: API fetch error for region {region_id}: {e}", 3)

        log_message(f"PIA: Handshake for {region_id} using CN {server_cn}", 0)

        live_cfg = pia.get_live_config(user, pw, target_ip, server_cn, region_id, region_name=original_name)
        if live_cfg and "[provider_wireguard]" in live_cfg:
            with open(config_path, 'w') as f:
                f.write(live_cfg)
                if has_kodi:
                    xbmc.sleep(1500)
            return True
        else:
            return False

    except Exception as e:
        err_str = str(e)
        log_message(f"PIA Error: {err_str}", 3)

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
                log_message("PIA API Blockade Connection Request start", 1)
                xbmc.Monitor().waitForAbort(15)
                log_message("PIA API Blockade Connection Request over.", 1)
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
                log_message("PIA Connection Cool Down start", 1)
                xbmc.Monitor().waitForAbort(10)
                log_message("PIA Connection Cool Down over.", 1)
                title = "[B][COLOR FFE6E6FA]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
                msg = "[COLOR FFFFFF00]Network cool down over. Ready to retry connection.[/COLOR]"
                xbmcgui.Dialog().notification(title, msg, ICON_INFO, 5000)

        return False
