''' ./resources/lib/main_launcher.py '''
import builtins
import os
import sys
import time
import xbmcgui
import xbmcaddon
import xbmcvfs
from logger import log_message
from providers import custom
from vpn_config import PROVIDER_MAP
from vpn_core import run_update, install_service

builtins.log_event = log_message

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

ADDON = xbmcaddon.Addon('service.wireguard.manager')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
ICON_UPDATE_OK = os.path.join(ADDON_PATH, 'resources', 'media', 'update_ok.png')


def run(argv):
    args_str = "|".join(argv).lower()

    commands = [
        "status", "restart", "clear", "reinstall", "regen",
        "choose_countries", "import_token", "import_creds",
        "import_custom_browser"
    ]

    if any(cmd in args_str for cmd in commands):

        if ",0" in args_str:
            PROVIDER = 0
        elif ",1" in args_str:
            PROVIDER = 1
        elif ",99" in args_str:
            PROVIDER = 99
        else:
            PROVIDER = ADDON.getSettingInt("vpn_provider")

        if PROVIDER == -1:
            PROVIDER = 0

        try:
            if "reinstall" in args_str:
                src_svc = os.path.join(
                    ADDON_PATH, 'resources', 'data', 'vpn-watchdog.service.txt'
                )
                dst_svc = os.path.join(
                    '/storage/.config/system.d/', 'vpn-watchdog.service'
                )
                install_service(
                    src_svc, dst_svc, 'vpn-watchdog.service', MEDIA_PATH
                )

            elif any(cmd in args_str for cmd in ["status", "restart", "clear"]):
                import service_control
                service_control.control_service()

            elif "regen" in args_str:
                if run_update():
                    title = "[B][COLOR FFE6E6FA]≡ [ WireGuard Manager ] ≡[/COLOR][/B]"
                    msg = "[COLOR FFFFFF00]Server countries updated.[/COLOR]"
                    xbmcgui.Dialog().notification(title, msg, ICON_UPDATE_OK, 3000)

            elif "choose_countries" in args_str:
                import country_selector
                country_selector.run()

            elif "import_token" in args_str:
                p_data = PROVIDER_MAP.get(PROVIDER)

                if not p_data or "setting" not in p_data or "user_setting" in p_data:
                    try:
                        time.sleep(0.1)
                    except Exception as e:
                        log_message(f"Token import pause failure: {e}", 3)
                    ICON_INFO = os.path.join(
                        ADDON_PATH, 'resources', 'media', 'icon.png'
                    )
                    title = "[B][COLOR ffffff00]ACTION REQUIRED!!![/COLOR][/B]"
                    message = (
                        "Selection cached. You MUST press 'OK' in the "
                        "main settings menu to apply changes!"
                    )
                    xbmcgui.Dialog().notification(title, message, ICON_INFO, 1500)
                    return

                token_file = xbmcgui.Dialog().browse(
                    1, "Select Token", "local", ".txt|.key"
                )
                if token_file:
                    f = xbmcvfs.File(token_file, 'r')
                    content = f.read()
                    f.close()

                    if isinstance(content, bytes):
                        content = content.decode('utf-8')
                        content = content.strip()

                    ADDON.setSetting(p_data['setting'], content)
                    log_message("Imported Token", 0)
                    run_update(direct_token=content)

                    notification_lock = '/tmp/vpn_notif_sent.lock'
                    if not os.path.exists(notification_lock):
                        with open(notification_lock, 'w') as f:
                            f.write('locked')
                        ICON_INFO = os.path.join(
                            ADDON_PATH, 'resources', 'media', 'icon.png'
                        )
                        title = "[B][COLOR ffffff00]ACTION REQUIRED!!![/COLOR][/B]"
                        message = (
                            "Selection cached. You [B]MUST[/B] press "
                            "[B]'OK'[/B] in the main settings menu to "
                            "apply changes!"
                        )
                        xbmcgui.Dialog().notification(
                            title, message, ICON_INFO, 1500
                        )
                else:
                    log_message("Token import cancelled by user", 0)

            elif "import_creds" in args_str:
                p_user_setting = "pia_user"
                p_setting = "pia_pass"

                has_gls = hasattr(ADDON, 'getLocalizedString')
                heading = (
                    ADDON.getLocalizedString(32048) if has_gls
                    else "Select Credentials File"
                )
                token_file = xbmcgui.Dialog().browse(
                    1, heading, "local", ".txt"
                )
                if token_file:
                    f = xbmcvfs.File(token_file, 'r')
                    content = f.read()
                    f.close()

                    if isinstance(content, bytes):
                        content = content.decode('utf-8')

                    lines = [
                        line.strip() for line in content.splitlines()
                        if line.strip()
                    ]

                    if len(lines) >= 2:
                        import base64
                        user = lines[0]
                        pwd = lines[1]

                        try:
                            base64.b64decode(pwd, validate=True)
                            encoded_pwd = pwd
                        except Exception:
                            enc_bytes = base64.b64encode(pwd.encode('utf-8'))
                            encoded_pwd = enc_bytes.decode('utf-8')

                        ADDON.setSetting(p_user_setting, user)
                        ADDON.setSetting(p_setting, encoded_pwd)

                        log_msg = f"Credentials saved for {user}. Starting update..."
                        log_message(log_msg, 1)

                        run_update(direct_token=encoded_pwd)

                        ICON_INFO = os.path.join(
                            ADDON_PATH, 'resources', 'media', 'icon.png'
                        )
                        title = "[B][COLOR ffffff00]ACTION REQUIRED!!![/COLOR][/B]"
                        message = (
                            "Selection cached. You [B]MUST[/B] press "
                            "[B]'OK'[/B] in the main settings menu to "
                            "apply changes!"
                        )
                        xbmcgui.Dialog().notification(
                            title, message, ICON_INFO, 1500
                        )
                    else:
                        title = "[B]≡ ERROR ≡[/B]"
                        msg = (
                            "[COLOR FFFFFF00]File must have 2 lines:\n"
                            "User and Pass[/COLOR]"
                        )
                        xbmcgui.Dialog().ok(title, msg)
                else:
                    log_message("Import cancelled by user", 0)

            elif "import_custom_browser" in args_str:
                source_path = xbmcgui.Dialog().browse(
                    1, "Select WireGuard Config", "local", ".conf|.config"
                )
                if source_path:
                    if custom.update(source_path, '/storage/.config/wireguard'):
                        country = os.path.basename(source_path).lower().replace(
                            '.config', ''
                        ).replace('.conf', '').replace(
                            'custom_', ''
                        ).capitalize()
                        ADDON.setSetting("custom_path", source_path)
                        ADDON.setSetting("vpn_token", country)

                        title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
                        msg = (
                            "[COLOR FFFFFF00]Please Save Settings before you "
                            f"continue next...\n\nImported: {country}.\n"
                            "Note: Ensure you click 'OK' in Settings.[/COLOR]"
                        )
                        xbmcgui.Dialog().ok(title, msg)

                        ICON_INFO = os.path.join(
                            ADDON_PATH, 'resources', 'media', 'icon.png'
                        )
                        title = "[B][COLOR ffffff00]ACTION REQUIRED!!![/COLOR][/B]"
                        message = (
                            "Selection cached. You [B]MUST[/B] press "
                            "[B]'OK'[/B] in the main settings menu to "
                            "apply changes!"
                        )
                        xbmcgui.Dialog().notification(
                            title, message, ICON_INFO, 1500
                        )

        except Exception as e:
            log_message(f"Main Launcher Error: {str(e)}", 3)
        return

    try:
        PROVIDER = ADDON.getSettingInt("vpn_provider")

    except Exception as e:
        log_message(f"Failed to read vpn_provider setting: {e}", 3)
        PROVIDER = 0

    import vpn_menu
    vpn_menu.show_menu(MEDIA_PATH, PROVIDER)
