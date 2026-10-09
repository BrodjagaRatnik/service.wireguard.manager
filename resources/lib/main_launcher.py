""" ./resources/lib/main_launcher.py """
import kodi_env
import builtins
import os
import sys
import time
from logger import log_message
from providers import custom
from vpn_config import PROVIDER_MAP
from vpn_core import run_update, install_service
from state_manager import get_file_path, CONFIG_DIR, SYSTEMD_DIR
import dialog

try:
    import xbmcgui
    import xbmcvfs
    HAS_GUI_IMPORTS = True
except ImportError:
    HAS_GUI_IMPORTS = False

builtins.log_event = log_message

_ACTION_REQUIRED_TITLE = "[B][COLOR ffffff00]ACTION REQUIRED!!![/COLOR][/B]"
_ACTION_REQUIRED_MESSAGE = "Selection cached. You [B]MUST[/B] press [B]'OK'[/B] in settings menu!"


def _write_notification_lock():
    notification_lock = get_file_path("notif_lock")
    if notification_lock is None or os.path.exists(notification_lock):
        return False
    try:
        lock_dir = os.path.dirname(notification_lock)
        if not os.path.exists(lock_dir):
            os.makedirs(lock_dir)
        with open(notification_lock, "w") as f:
            f.write("locked")
        return True
    except Exception as e:
        log_message(f"Main Launcher: Failed to create notification lock: {e}", 3)
        return False


def _run_custom_directory_import(addon_obj, source_dir):
    if not source_dir:
        log_message("Main Launcher: Custom directory import cancelled by user", 0)
        return

    progress = dialog.TaskProgress("Custom Import", "Scanning folder for WireGuard profiles...")

    def _batch_progress(position, total_profiles, profile_label):
        percent_value = 5 + int((position / total_profiles) * 90) if total_profiles else 95
        progress.update(percent_value, f"Importing {position}/{total_profiles}: {profile_label}...")

    try:
        summary = custom.update_directory(source_dir, CONFIG_DIR, progress_callback=_batch_progress)
        progress.update(100, "Import complete")
    finally:
        progress.close()

    addon_obj.setSetting("custom_path", source_dir)

    if summary["imported"] > 0:
        title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
        msg = f"[COLOR FFFFFF00]Imported {summary['imported']} profiles.[/COLOR]\n"
        if summary["skipped"] > 0:
            msg += f"Skipped {summary['skipped']} invalid or duplicate files."
        dialog.show_ok(title, msg)
        dialog.notify_custom(_ACTION_REQUIRED_TITLE, _ACTION_REQUIRED_MESSAGE, "icon.png", 1500)
    else:
        title = "[B]≡ [ WireGuard MANAGER ERROR ] ≡[/B]"
        msg = "[COLOR FFFFFF00]No valid WireGuard profiles found in the selected folder.[/COLOR]"
        dialog.show_ok(title, msg)


def run(argv):
    addon_obj = kodi_env.get_addon_instance()

    if not addon_obj or not HAS_GUI_IMPORTS:
        log_message("Main Launcher: Environment missing Kodi abstractions. Execution stopped.", 2)
        return

    try:
        addon_path = kodi_env.ADDON_DIR
        lib_path = os.path.join(addon_path, "resources", "lib")
        media_path = os.path.join(addon_path, "resources", "media")

        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)

        args_str = "|".join(argv).lower()

        commands = [
            "status", "restart", "clear", "regen",
            "choose_countries", "mode=country_selector", "mode=list_assets",
            "mode=dnsleaktest", "cleanup", "mode=tos", "mode=disclaimer",
            "mode=import_token", "mode=import_creds", "mode=import_custom_browser",
            "mode=import_custom_dir",
            "show_codes", "mode=net_reset", "mode=import_mullvad",
            "blackout"
        ]

        if any(cmd in args_str for cmd in commands):

            if ",0" in args_str:
                provider = 0
            elif ",1" in args_str:
                provider = 1
            elif ",99" in args_str:
                provider = 99
            else:
                provider = addon_obj.getSettingInt("vpn_provider")

            if provider == -1:
                provider = 0

            if "reinstall" in args_str:
                src_svc = os.path.join(addon_path, "resources", "data", "vpn-watchdog.service.txt")
                dst_svc = os.path.join(SYSTEMD_DIR, "vpn-watchdog.service")
                install_service(src_svc, dst_svc, "vpn-watchdog.service", media_path)

            elif any(cmd in args_str for cmd in ["status", "restart", "clear"]):
                import service_control
                service_control.control_service()

            elif "regen" in args_str:
                if run_update() is True:
                    title = "[B][COLOR FFE6E6FA]≡ [ WireGuard Manager ] ≡[/COLOR][/B]"
                    msg = "[COLOR FFFFFF00]Server countries updated.[/COLOR]"
                    dialog.notify_custom(title, msg, "update_ok.png", 3000)

            elif any(cmd in args_str for cmd in ["choose_countries", "mode=country_selector"]):
                scripts_path = os.path.join(addon_path, "resources", "scripts")
                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)
                import country_selector
                country_selector.run()

            elif "mode=list_assets" in args_str:
                scripts_path = os.path.join(addon_path, "resources", "scripts")
                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)
                import list_assets
                list_assets.run_wizard()

            elif "import_token" in args_str:
                p_data = PROVIDER_MAP.get(provider)

                if not p_data or "setting" not in p_data or "user_setting" in p_data:
                    try:
                        time.sleep(0.1)
                    except Exception as e:
                        log_message(f"Main Launcher: Token import pause failure: {e}", 3)
                    dialog.notify_custom(
                        _ACTION_REQUIRED_TITLE,
                        "Selection cached. You MUST press 'OK' in the main settings menu to apply changes!",
                        "icon.png", 1500
                    )
                else:
                    token_file = xbmcgui.Dialog().browse(1, "Select Token", "local", ".txt|.key")
                    if token_file:
                        f = xbmcvfs.File(token_file, "r")
                        content = f.read()
                        f.close()

                        if isinstance(content, bytes):
                            content = content.decode("utf-8")
                            content = content.strip()

                        addon_obj.setSetting(p_data["setting"], content)
                        log_message("Imported Token", 0)
                        run_update(direct_token=content)

                        if _write_notification_lock():
                            dialog.notify_custom(_ACTION_REQUIRED_TITLE, _ACTION_REQUIRED_MESSAGE, "icon.png", 1500)
                    else:
                        log_message("Main Launcher: Token import cancelled by user", 0)

            elif "import_creds" in args_str:
                p_user_setting = "pia_user"
                p_setting = "pia_pass"

                has_gls = hasattr(addon_obj, "getLocalizedString")
                heading = addon_obj.getLocalizedString(32048) if has_gls else "Select Credentials File"
                token_file = xbmcgui.Dialog().browse(1, heading, "local", ".txt")
                if token_file:
                    f = xbmcvfs.File(token_file, "r")
                    content = f.read()
                    f.close()

                    if isinstance(content, bytes):
                        content = content.decode("utf-8")

                    lines = [line.strip() for line in content.splitlines() if line.strip()]

                    if len(lines) >= 2:
                        import base64
                        user = lines[0]
                        pwd = lines[1]

                        try:
                            base64.b64decode(pwd, validate=True)
                            encoded_pwd = pwd
                        except Exception:
                            enc_bytes = base64.b64encode(pwd.encode("utf-8"))
                            encoded_pwd = enc_bytes.decode("utf-8")

                        addon_obj.setSetting(p_user_setting, user)
                        addon_obj.setSetting(p_setting, encoded_pwd)

                        log_msg = f"Credentials saved for {user}. Starting update..."
                        log_message(log_msg, 1)

                        run_update(direct_token=encoded_pwd)

                        dialog.notify_custom(_ACTION_REQUIRED_TITLE, _ACTION_REQUIRED_MESSAGE, "icon.png", 1500)
                    else:
                        dialog.show_ok("[B]≡ ERROR ≡[/B]", "File must have 2 lines:\nUser and Pass")
                else:
                    log_message("Main Launcher: Import cancelled by user", 0)

            elif "import_custom_browser" in args_str:
                opts = [
                    "[B]Import Single File (.conf/.config)[/B]",
                    "[B]Import Whole Folder (Bulk Import)[/B]"
                ]
                choice = xbmcgui.Dialog().select("Import Type", opts)

                if choice == 0:
                    source_path = xbmcgui.Dialog().browse(
                        1, "Select WireGuard Config", "local", ".conf|.config"
                    )
                    if source_path:
                        if custom.update(source_path, CONFIG_DIR) is True:
                            country = os.path.basename(source_path).lower().replace(".config", "")
                            country = country.replace(".conf", "").replace("custom_", "").capitalize()
                            addon_obj.setSetting("custom_path", source_path)
                            addon_obj.setSetting("vpn_token", country)

                            title = "[B]≡ [ WireGuard Manager ] ≡[/B]"
                            msg = f"Please Save Settings before you continue...\n\nImported: {country}."
                            dialog.show_ok(title, msg)

                            dialog.notify_custom(
                                _ACTION_REQUIRED_TITLE, _ACTION_REQUIRED_MESSAGE, "icon.png", 1500
                            )

                elif choice == 1:
                    source_dir = xbmcgui.Dialog().browse(0, "Select WireGuard Config Folder", "local")
                    _run_custom_directory_import(addon_obj, source_dir)

            elif "import_custom_dir" in args_str:
                source_dir = xbmcgui.Dialog().browse(0, "Select WireGuard Config Folder", "local")
                _run_custom_directory_import(addon_obj, source_dir)

            elif "mode=dnsleaktest" in args_str:
                scripts_path = os.path.join(addon_path, "resources", "scripts")
                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)
                import dnsleaktest
                dnsleaktest.main()

            elif "cleanup" in args_str:
                import setup_helper
                setup_helper.perform_cleanup()

            elif "mode=tos" in args_str:
                scripts_path = os.path.join(addon_path, "resources", "scripts")
                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)
                import show_terms_of_service
                show_terms_of_service.show_tos()

            elif "mode=disclaimer" in args_str:
                scripts_path = os.path.join(addon_path, "resources", "scripts")
                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)
                import show_disclaimer
                show_disclaimer.show_disclaimer()

            elif "mode=show_codes" in args_str:
                scripts_path = os.path.join(addon_path, "resources", "scripts")
                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)
                import show_codes
                show_codes.run_viewer(args_str)

            elif "mode=net_reset" in args_str:
                scripts_path = os.path.join(addon_path, "resources", "scripts")
                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)
                import network
                network.run_network_cleanup()

            elif "import_mullvad" in args_str:
                p_data = PROVIDER_MAP.get(2)

                if not p_data or "setting" not in p_data:
                    dialog.notify_custom(
                        _ACTION_REQUIRED_TITLE,
                        "Selection cached. You MUST press 'OK' in the main settings menu to apply changes!",
                        "icon.png", 1500
                    )
                else:
                    account_file = xbmcgui.Dialog().browse(1, "Select Account File", "local", ".txt")
                    if account_file:
                        f = xbmcvfs.File(account_file, "r")
                        content = f.read()
                        f.close()

                        if isinstance(content, bytes):
                            content = content.decode("utf-8")

                        clean_account = "".join(content.split()).strip()

                        if clean_account.isdigit() and len(clean_account) == 16:
                            addon_obj.setSetting(p_data["setting"], clean_account)
                            log_message(
                                f"Imported Mullvad Account to dynamic target setting: {p_data['setting']}", 0
                            )

                            owned_val = addon_obj.getSetting("wg_owned").lower() == "true"

                            import providers.mullvad_utils as m_utils
                            m_utils.generate_mullvad_configs(
                                account_id=clean_account,
                                country_filter=addon_obj.getSetting(p_data.get("countries_setting", "filter")),
                                mtu_setting=1380,
                                owned=owned_val
                            )

                            if _write_notification_lock():
                                dialog.notify_custom(
                                    _ACTION_REQUIRED_TITLE, _ACTION_REQUIRED_MESSAGE, "icon.png", 1500
                                )
                        else:
                            log_message("Main Launcher: Invalid Mullvad account token length or format rejected", 2)
                            dialog.show_ok(
                                "[B]≡ [ WireGuard MANAGER ERROR ] ≡[/B]",
                                "[COLOR FFFFFF00]Selected file does not contain a valid 16-digit Mullvad account.[/COLOR]"
                            )
                    else:
                        log_message("Main Launcher: Mullvad account import cancelled by user", 0)

            elif "blackout" in args_str:
                import wm_utils
                wm_utils.show_blackout_ui_in_kodi()

        else:
            try:
                provider = addon_obj.getSettingInt("vpn_provider")
            except Exception as e:
                log_message(f"Main Launcher: Failed to read vpn_provider setting: {e}", 3)
                provider = 0

            import vpn_menu
            vpn_menu.show_menu(media_path, provider)

    except Exception as master_fault:
        log_message(f"Main Launcher: Fatal routing interception breakdown: {master_fault}", 3)

    finally:
        kodi_env.clear_script_globals()
