''' ./resources/lib/vpn_connector.py '''
import base64
import json
import os
import re
import ssl
import subprocess
import time
import urllib.request
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
from providers import pia

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

    if HAS_KODI and _ADDON:
        provider_id = _ADDON.getSettingInt("vpn_provider")
    else:
        provider_id = 0

    if provider_id == 1:
        p_data = PROVIDER_MAP.get(provider_id, {})

        try:
            user = _ADDON.getSetting("pia_user")
            raw_pw = _ADDON.getSetting("pia_pass")

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

            if config_path:
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
                        url = p_data.get('api_url')
                        if url:
                            ctx = ssl._create_unverified_context()
                            req = urllib.request.Request(url, headers={'User-Agent': 'PIA-VPN/3.5.0 (Linux)'})
                            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                                raw_data = resp.read().decode('utf-8').strip()

                                if "\n" in raw_data:
                                    clean_raw = raw_data.split("\n")[0].strip()
                                else:
                                    clean_raw = raw_data.strip()

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
                        xbmc.sleep(1500)
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
                xbmc.executebuiltin("ActivateWindow(home)")
                xbmcgui.Dialog().ok(title, msg)
                log_message("PIA Connection Cool Down start", 1)
                xbmc.Monitor().waitForAbort(10)
                log_message("PIA Connection Cool Down over.", 1)
                title = "[B][COLOR FFE6E6FA]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
                msg = "[COLOR FFFFFF00]Network cool down over. Ready to retry connection.[/COLOR]"
                xbmcgui.Dialog().notification(title, msg, ICON_INFO, 5000)

            return False

    log_message(f"Operation: Connecting to {vpn_name}", 0)
    disable_connman_ipv6()

    pbg = None
    if not silent:
        pbg = xbmcgui.DialogProgressBG()
        pbg.create("VPN Manager", f"Connecting to {vpn_name}...")

    subprocess.run(["connmanctl", "connect", sid], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    connected = False
    MAX_STEPS = int(VPN_CONNECTION_TIMEOUT / DHCP_RECOVERY_DELAY)
    STEP_PERCENT = 100.0 / MAX_STEPS

    for i in range(1, MAX_STEPS + 1):
        if pbg and HAS_KODI:
            pbg.update(int(i * STEP_PERCENT), message=f"Verifying... ({int((i*DHCP_RECOVERY_DELAY)/1000)}s)")

        if HAS_KODI:
            xbmc.sleep(DHCP_RECOVERY_DELAY)
        else:
            time.sleep(DHCP_RECOVERY_DELAY / 1000.0)
        try:
            check = subprocess.check_output(["connmanctl", "services"], text=True)
            if any(sid in line and ("* R" in line or "* O" in line) for line in check.splitlines()):
                if "wg0" in subprocess.check_output(["ip", "route"], text=True):
                    connected = True
                    break
        except Exception as e:
            log_message(f"Connection verification check failure: {e}", 3)

    if pbg and HAS_KODI:
        pbg.close()

    if connected:
        subprocess.run(["ip", "route", "flush", "cache"], check=False)
        instance.set_active_vpn(vpn_name)
        set_secure_dns(vpn_name, vpn_active=True)

        if HAS_KODI:
            xbmc.sleep(ROUTE_PROP_DELAY)
        else:
            time.sleep(ROUTE_PROP_DELAY / 1000.0)

        if not silent and HAS_KODI:
            try:
                res = subprocess.check_output(["curl", "-s", "--max-time", "5", "https://ipinfo.io"], text=True)
                data = json.loads(res)
                ip, country = data.get("ip", "Unknown"), data.get("country", "??")
                title = "[B][COLOR FF00FF00]▄■ [ CONNECTED ] ■▄[/COLOR][/B]"
                msg = (
                    f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
                    f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • [COLOR FFFF8C00]({country})[/COLOR][/B]"
                )
                xbmcgui.Dialog().notification(title, msg, ICON_CON, 4500)
            except Exception as e:
                log_message(f"Connection metadata look up failed: {e}", 3)

                title = "[B][COLOR FFFF0000]▀■▄ SERVER TIMEOUT ▄■▀[/COLOR][/B]"
                msg = (
                    "[B][COLOR FFFFFF00]"
                    f"{vpn_name} server is not working or dropping data!"
                    "[/COLOR][/B]"
                )
                xbmcgui.Dialog().notification(title, msg, ICON_ERROR, 5500)

                instance.disconnect_vpn(silent=True)
                return False

        return True

    if not silent and HAS_KODI:
        err_msg = (
            "Handshake failed. Check credentials."
            if get_default_gateway() else "Internet lost."
        )
        xbmcgui.Dialog().notification(
            "[B][COLOR ffff0000]▀■▄ VPN FAILURE ▄■▀[/COLOR][/B]",
            err_msg, ICON_ERROR, 5000
        )

    instance.disconnect_vpn(silent=True)
    return False
