""" ./resources/lib/providers/pia_utils.py """
import kodi_env
import base64
import json
import os
import re
import sys
import ssl
import threading
import urllib.parse
import urllib.request
from logger import log_message
from providers import pia

try:
    import xbmc
    HAS_KODI = True
except ImportError:
    HAS_KODI = False


def get_addon_path():
    return kodi_env.ADDON_DIR


def fetch_pia_url(url, token=None, user=None, password=None, post_data=None):
    headers = {
        'User-Agent': 'service.wireguard.manager/1.0',
        'Accept': 'application/json'
    }

    if token:
        auth_str = f"token:{str(token).strip()}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('ascii')
        headers['Authorization'] = f"Basic {auth_bytes}"
    elif user and password:
        auth_str = f"{user.strip()}:{password.strip()}"
        auth_bytes = base64.b64encode(auth_str.encode('utf-8')).decode('ascii')
        headers['Authorization'] = f"Basic {auth_bytes}"

    try:
        data_bytes = None
        if post_data is not None:
            if isinstance(post_data, dict) and 'username' in post_data:
                data_bytes = urllib.parse.urlencode(post_data).encode('utf-8')
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            else:
                data_bytes = json.dumps(post_data).encode('utf-8')
                headers['Content-Type'] = 'application/json'

        req = urllib.request.Request(url, data=data_bytes, headers=headers)

        try:
            req_ctx = ssl.create_default_context()
        except Exception:
            req_ctx = ssl._create_unverified_context()

        with urllib.request.urlopen(req, timeout=10, context=req_ctx) as response:
            raw_body = response.read().decode('utf-8').strip()
            if not raw_body:
                return None

            try:
                return json.loads(raw_body)
            except Exception:
                log_message("PIA Utils: Whole body parse failed, using line fallback.", 0)

            parsed_objects = []
            for line in raw_body.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed_objects.append(json.loads(line))
                except Exception:
                    continue
            return parsed_objects if parsed_objects else None

    except Exception as e:
        log_message(f"PIA Utils: Fetch Failure: {e}", 3)
        return None


def setup_pia_handshake(sid, provider_data, addon_obj, has_kodi):
    ui_module = sys.modules.get('xbmcgui')
    from wm_utils import safe_decrypt_password
    from providers.pia_config import PiaHandshakeEngine

    engine = PiaHandshakeEngine()
    is_blocked, remaining_time = engine.check_rate_limit()

    if is_blocked:
        log_message(f"PIA Utils: Request blocked due to active cooldown. Remaining: {remaining_time}s", 2)
        if has_kodi and ui_module:
            rem_m = int(float(remaining_time)) // 60
            rem_s = int(float(remaining_time)) % 60
            title = "[B]≡ [ COOL DOWN MECHANISM ] ≡[/B]"
            msg = (
                "[COLOR ffff0000]Connection Request Temporarily Blocked![/COLOR]\n\n"
                "This node is in cool-down to protect against upstream API locks.\n"
                f"[COLOR ffffff00]SOLUTION:[/COLOR] Please wait [B]{rem_m}m {rem_s}s[/B] before retrying connection."
            )
            ui_module.Dialog().ok(title, msg)

        return False

    try:
        user = str(addon_obj.getSetting("pia_user")).strip().lower()
        raw_pw = addon_obj.getSetting("pia_pass")
        pw = safe_decrypt_password(raw_pw)
        config_path = None
        region_id = None
        conf_dir = "/storage/.config/wireguard/"
        target_suffix = sid.replace("vpn_provider_wireguard_pia_", "").replace("vpn_pia_", "")

        pure_ip = target_suffix.replace("vpn_", "").replace("_", ".")

        for filename in os.listdir(conf_dir):
            if filename.startswith("pia_") and filename.endswith(".config"):
                path_check = os.path.join(conf_dir, filename)
                try:
                    with open(path_check, "r") as cf:
                        file_content = cf.read()
                    f_id = filename.replace("pia_", "").replace(".config", "")
                    if f_id.lower() == target_suffix.lower() or f"Host = {pure_ip}" in file_content:
                        config_path = path_check
                        region_id = f_id
                        break
                except Exception:
                    continue

        if not config_path:
            log_message(f"PIA Utils: No blueprint found for {target_suffix}", 0)
            return True

        log_message(f"PIA Utils: Found config path={config_path}", 0)
        target_ip = ""
        pool_cns = []
        original_name = None

        with open(config_path, "r") as f:
            content = f.read()
            host_match = re.search(r"^\s*Host\s*=\s*(.*)", content, re.MULTILINE)
            if host_match:
                target_ip = host_match.group(1).strip()

            name_match = re.search(r"^\s*Name\s*=\s*(.*)", content, re.MULTILINE)
            if name_match:
                original_name = name_match.group(1).strip().replace("PIA_", "")

            cn_pool_match = re.search(r"^\s*WireGuard\.CN_Pool\s*=\s*(.*)", content, re.MULTILINE)
            if cn_pool_match:
                pool_cns = [c.strip() for c in cn_pool_match.group(1).split(",") if c.strip()]

        log_message(f"PIA Utils: Parsed IP={target_ip} ID={region_id} CNs={len(pool_cns)}", 0)

        if not target_ip or not pool_cns:
            log_message("PIA VPN_Utils: Missing nodes or Host IP.", 3)
            return False

        log_message("PIA Utils: Requesting single token for pool...", 1)
        local_abuse_triggered = engine.track_and_check_abuse()

        if local_abuse_triggered:
            raise Exception("Global token acquisition failed due to API rate limit 429.")

        active_token = pia.get_cached_token(user, pw)

        if not active_token:
            if os.path.exists(engine.cooldown_file):
                raise Exception("Global token acquisition failed due to API rate limit 429.")
            raise Exception("Global token acquisition failed due to invalid credentials 401.")

        raw_cn_str = ",".join(pool_cns)
        skipping_handshake = False
        live_cfg = None

        for current_cn in pool_cns:
            clean_cn = current_cn.strip().lower()
            log_message(f"PIA Utils: Try CN={clean_cn} IP={target_ip}", 0)

            live_cfg = pia.get_live_config(
                active_token, target_ip, clean_cn, region_id, original_name, raw_cn_str
            )

            if live_cfg is None:
                skipping_handshake = True
                break

            if live_cfg and "[provider_wireguard]" in live_cfg:
                with open(config_path, "w") as f:
                    f.write(live_cfg)
                    if has_kodi:
                        xbmc.sleep(500)
                break

        if skipping_handshake:
            log_message("PIA Utils: Handshake cached (<55m). Using current config file.", 1)
            return True

        if live_cfg and "[provider_wireguard]" in live_cfg:
            log_message("PIA Utils: Handshake OK! Configuration saved.", 1)
            return True
        else:
            raise Exception("PIA Utils: Handshake declined by all upstream target API nodes.", 3)

    except Exception as e:
        err_str = str(e)
        log_message(f"PIA Utils: {err_str}", 3)

        if "429" in err_str or "too many requests" in err_str.lower():
            threading.Thread(target=launch_async_cooldown_notifier, args=(900.0,), daemon=True).start()
            title = "[B]≡ [ API 15 minutes RATE LIMIT ] ≡[/B]"
            msg = (
                "[COLOR ffff0000]PIA API Blocked Your Connection Request![/COLOR]\n\n"
                "Your IP address has been temporarily rate-limited.\n"
                "[COLOR ffffff00]SOLUTION:[/COLOR] Please wait [B]15 minutes[/B] before starting to connect again."
            )
            if has_kodi and ui_module:
                xbmc.executebuiltin("ActivateWindow(home)")
                ui_module.Dialog().ok(title, msg)
        elif "accepted handshake but rejected network data" in err_str.lower():
            title = "[B]≡ [ PIA SERVER DOWN ] ≡[/B]"
            msg = (
                "[COLOR ffff0000]PIA Gateway Server is Currently Broken![/COLOR]\n\n"
                "The tunnel connected successfully but no internet data can flow.\n"
                "[COLOR ffffff00]SOLUTION:[/COLOR] This node is dead. Please update regions or choose another country."
            )
            if has_kodi and ui_module:
                xbmc.executebuiltin("ActivateWindow(home)")
                ui_module.Dialog().ok(title, msg)
        else:
            engine.enforce_cooldown(600.0)
            threading.Thread(target=launch_async_cooldown_notifier, args=(600.0,), daemon=True).start()
            title = "[B]≡ [ CONNECTION FAILURE ] ≡[/B]"
            msg = (
                "[COLOR ffff0000]VPN Handshake Failed to Establish![/COLOR]\n\n"
                f"System Error: [COLOR ffffff00]{err_str}[/COLOR]\n"
                "The manager was unable to reach the PIA authorization nodes."
            )
            if "invalid credentials 401" in err_str.lower() or "token acquisition failed" in err_str.lower():
                title = "[B]≡ [ WRONG CREDENTIALS ] ≡[/B]"
                msg = (
                    "[COLOR ffff0000]PIA Authentication Denied (HTTP 401)![/COLOR]\n\n"
                    "Your username or password credentials are invalid.\n"
                    "[COLOR ffffff00]SOLUTION:[/COLOR] PIA locked this node for [B]10 minutes[/B]. Fix credentials."
                )
            if has_kodi and ui_module:
                xbmc.executebuiltin("ActivateWindow(home)")
                ui_module.Dialog().ok(title, msg)
                log_message("PIA 10 minutes Connection Background Cooldown initialized successfully.", 2)
        return False


def launch_async_cooldown_notifier(seconds):
    try:
        import xbmc
        monitor = xbmc.Monitor()
        if monitor.waitForAbort(int(seconds)):
            return
        ui_module = sys.modules.get('xbmcgui')
        if ui_module:
            addon_path = kodi_env.ADDON_DIR
            icon_info = os.path.join(addon_path, 'resources', 'media', 'icon.png')
            title = "[B][COLOR FFE6E6FA]≡ [ WG MANAGER ] ≡[/COLOR][/B]"
            msg = "[COLOR FFFFFF00]PIA API Blockade over you can connect to PIA again.[/COLOR]"
            ui_module.Dialog().notification(title, msg, icon_info, 5000)
    except Exception:
        pass

    finally:
        kodi_env.clear_script_globals()
