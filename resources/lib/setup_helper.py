""" ./resources/lib/setup_helper.py """
import kodi_env
import os
import shutil
import subprocess
import sys
import configparser
from logger import log_message
from vpn_config import PROVIDER_MAP

try:
    import xbmc
    import xbmcgui
    import xbmcvfs
    HAS_KODI = True
except ImportError:
    HAS_KODI = False


def _setup_paths():
    try:
        addon_path = kodi_env.ADDON_DIR
        local_lib = os.path.join(addon_path, "resources", "lib")

        if local_lib not in sys.path:
            sys.path.insert(0, local_lib)

    except Exception as e:
        sys.stderr.write(f"Setup Helper: Path setup critical failure: {e}\n")


_setup_paths()


def perform_cleanup(silent=False):
    addon = kodi_env.get_addon_instance()
    wg_config_path = "/storage/.config/wireguard/"
    connman_override_dir = "/storage/.config/system.d/connman.service.d"
    connman_main_conf = "/storage/.config/connman_main.conf"

    try:
        log_message("Setup Helper: Cleanup Starting factory reset...", 1)

        service_file = "/storage/.config/system.d/vpn-watchdog.service"
        if os.path.exists(service_file) is True:
            subprocess.run(["systemctl", "stop", "vpn-watchdog.service"], check=False)
            subprocess.run(["systemctl", "disable", "vpn-watchdog.service"], check=False)
            os.remove(service_file)
            subprocess.run(["systemctl", "daemon-reload"], check=False)

        if os.path.exists(connman_override_dir) is True:
            try:
                shutil.rmtree(connman_override_dir)
                log_message("Setup Helper: Cleanup Connman DNS override configuration removed.", 1)
            except Exception as ce:
                log_message(f"Setup Helper: Cleanup Error removing Connman override folder: {ce}", 3)

        if os.path.exists(connman_main_conf) is True:
            try:
                os.remove(connman_main_conf)
                log_message("Setup Helper: Cleanup Global connman_main.conf removed.", 1)
            except Exception as me:
                log_message(f"Setup Helper: Cleanup Error removing connman_main.conf: {me}", 3)

        if os.path.exists(connman_override_dir) is True or os.path.exists(connman_main_conf) is True:
            subprocess.run(["systemctl", "daemon-reload"], check=False)
            subprocess.run(["systemctl", "restart", "connman"], check=False)

        if os.path.exists(wg_config_path) is True:
            cmd = "rm -f /storage/.config/wireguard/*_*.config"
            subprocess.run(cmd, shell=True, check=False)
            log_message("Setup Helper: Cleanup WireGuard configs wiped via shell.", 1)

        if addon:
            addon.setSetting("selected_countries", "")
            addon.setSetting("selected_countries_pia", "")
            addon.setSetting("first_run", "false")

        keymap_file = xbmcvfs.translatePath("special://userdata/keymaps/wireguard_manager_key.xml")
        if os.path.exists(keymap_file) is True:
            os.remove(keymap_file)

        from state_manager import FILE_MAP, get_file_path
        for key in FILE_MAP:
            tf = get_file_path(key)
            if tf is not None and os.path.exists(tf) is True:
                try:
                    os.remove(tf)
                except Exception as e:
                    log_message(f"Setup Helper: Reset error removing {tf}: {e}", 3)

        log_message("Setup Helper: Cleanup Reset complete.", 1)
        if silent is False and HAS_KODI:
            title = "[B]≡ [ CLEANUP COMPLETE ] ≡[/B]"
            msg = (
                "[COLOR FFFFFF00]Cleanup successful.[/COLOR]\n"
                "All WireGuard configs, vpn-watchdog.service, ... "
                "are removed from your device. You can now uninstall WireGuard VPN Manager."
            )
            xbmc.executebuiltin("Dialog.Close(all, true)")
            xbmc.sleep(200)
            xbmcgui.Dialog().ok(title, msg)

    except Exception as e:
        log_message(f"Setup Helper: Cleanup Error: {e}", 3)

    finally:
        kodi_env.clear_script_globals()


def ensure_setup(addon_path, silent=False):
    try:
        ADDON = kodi_env.get_addon_instance()

        if not ADDON or not HAS_KODI:
            log_message("Setup Helper: Abstractions missing. Skipping interface orchestration.", 2)
            return

        keymap_dest = xbmcvfs.translatePath("special://userdata/keymaps/wireguard_manager_key.xml")
        keymap_source = os.path.join(addon_path, "resources", "keymaps", "wireguard_manager_key.xml")
        wg_config_path = "/storage/.config/wireguard/"
        service_dest = "/storage/.config/system.d/vpn-watchdog.service"
        service_source = os.path.join(addon_path, "resources", "data", "vpn-watchdog.service.txt")
        connman_dest = '/storage/.config/connman_main.conf'
        connman_source = os.path.join(addon_path, 'resources', 'data', 'connman_main.conf.txt')
        cert_source = os.path.join(addon_path, "resources", "data", "ca.rsa.4096.txt")
        cert_dest = os.path.join(addon_path, "resources", "lib", "providers", "ca.rsa.4096.crt")
        setup_updated = False
        progress = xbmcgui.DialogProgress()
        progress.create("WireGuard Manager", "Starting system check...")
        progress.update(15, "Checking Keymaps...")
        if not os.path.exists(keymap_dest):
            try:
                os.makedirs(os.path.dirname(keymap_dest), exist_ok=True)
                shutil.copy2(keymap_source, keymap_dest)
                log_message("Setup Helper: Keymap installed.", 1)
                xbmc.executebuiltin("Action(ReloadKeymaps)")
                log_message("Setup Helper: Keymaps reloaded in Kodi.", 1)
            except Exception as e:
                log_message(f"Setup Helper: Setup Error (Keymap): {e}", 3)

        progress.update(25, "Checking network configuration...")
        if not os.path.exists(connman_dest):
            try:
                shutil.copy2(connman_source, connman_dest)
                subprocess.run(["systemctl", "restart", "connman"], check=False)
                log_message("Setup Helper: Connman config installed.", 1)
                setup_updated = True
            except Exception as e:
                log_message(f"Setup Helper: Setup Error (Connman): {e}", 3)
        else:
            try:
                src_parser = configparser.ConfigParser(strict=False, empty_lines_in_values=False)
                dst_parser = configparser.ConfigParser(strict=False, empty_lines_in_values=False)
                src_parser.read(connman_source)
                dst_parser.read(connman_dest)
                changes_made = False
                for sec in src_parser.sections():
                    if not dst_parser.has_section(sec):
                        dst_parser.add_section(sec)
                        changes_made = True
                    for opt, val in src_parser.items(sec):
                        if not dst_parser.has_option(sec, opt) or dst_parser.get(sec, opt) != val:
                            dst_parser.set(sec, opt, val)
                            changes_made = True
                if changes_made:
                    with open(connman_dest, "w") as config_out:
                        dst_parser.write(config_out)
                    subprocess.run(["systemctl", "restart", "connman"], check=False)
                    log_message("Setup Helper: Connman config merged and updated.", 1)
                    setup_updated = True
            except Exception as e:
                log_message(f"Setup Helper: Setup Error (Connman Update): {e}", 3)

        connman_override_dest = '/storage/.config/system.d/connman.service.d/override.conf'
        progress.update(45, "Checking DNS override configuration...")
        if not os.path.exists(connman_override_dest):
            try:
                dest_dir = os.path.dirname(connman_override_dest)
                os.makedirs(dest_dir, exist_ok=True)

                config_data = (
                    "[Service]\n"
                    "ExecStartPre=\n"
                    "ExecStart=\n"
                    "ExecStart=/usr/sbin/connmand -nr "
                    "--config=/storage/.config/connman_main.conf --nodnsproxy\n"
                    "ExecStartPost=/bin/sh -c \"sleep 2; "
                    "if ! grep -q 'Method=manual' "
                    "/storage/.cache/connman/*/settings 2>/dev/null; "
                    "then echo -e 'nameserver 1.1.1.1"
                    "\nnameserver 9.9.9.9' >> /etc/resolv.conf; fi\"\n"
                    "LimitNOFILE=512\n"
                    "LogRateLimitIntervalSec=0\n"
                )
                with open(connman_override_dest, "w") as f:
                    f.write(config_data)

                subprocess.run(["systemctl", "daemon-reload"], check=False)
                subprocess.run(["systemctl", "restart", "connman"], check=False)
                log_message("Setup Helper: Connman dynamic override installed.", 1)
                setup_updated = True
            except Exception as e:
                log_message(f"Setup Helper: Setup Error (Connman dns override): {e}", 3)

        progress.update(60, "Installing VPN Watchdog...")
        if not os.path.exists(service_dest):
            try:
                os.makedirs(os.path.dirname(service_dest), exist_ok=True)
                shutil.copy2(service_source, service_dest)
                subprocess.run(["systemctl", "daemon-reload"], check=False)
                subprocess.run(["systemctl", "enable", "vpn-watchdog.service"], check=False)
                subprocess.run(["systemctl", "start", "vpn-watchdog.service"], check=False)
                log_message("Setup Helper: Watchdog service installed.", 1)
                setup_updated = True
            except Exception as e:
                log_message(f"Setup Helper: Setup Error (Service): {e}", 3)

        progress.update(75, "Deploying PIA provider certificates...")
        if not os.path.exists(cert_dest):
            try:
                os.makedirs(os.path.dirname(cert_dest), exist_ok=True)
                shutil.copy2(cert_source, cert_dest)
                log_message("Setup Helper: Secure verification certificate deployed.", 1)
            except Exception as e:
                log_message(f"Setup Helper: Setup Error (Certificate Copy): {e}", 3)

        progress.update(90, "Verifying VPN credentials...")
        current_p_id = ADDON.getSettingInt("vpn_provider")
        has_creds = False
        if current_p_id == -1:
            log_message("Setup Helper: No VPN provider selected yet. Skipping credential check.", 1)
        else:
            p_data = PROVIDER_MAP.get(current_p_id, {"name": "Unknown", "prefix": "unknown_"})
            token_setting = p_data.get("setting")
            if token_setting:
                has_creds = bool(ADDON.getSetting(token_setting).strip())
            if current_p_id == 99 or not has_creds:
                prefix = p_data["prefix"]
                if os.path.exists(wg_config_path):
                    has_files = any(f.startswith((prefix, "custom_")) for f in os.listdir(wg_config_path))
                    has_creds = has_creds or has_files

        progress.update(100, "Setup Complete.")
        if setup_updated:
            log_message("Setup Helper: All system checks completed successfully.", 0)
        progress.close()

        if setup_updated:
            log_message("Setup Helper: Success! System services installed. WireGuard manager active.", 1)

            path_fixed = kodi_env.ADDON_DIR
            ICON_INFO = os.path.join(path_fixed, "resources", "media", "icon.png")
            title = "[B][COLOR FFEEFFEE]≡[ SETUP SUCCESS ]≡[/COLOR][/B]"
            message = "[COLOR FFFFFF00]WireGuard manager is now active.[/COLOR]"
            xbmcgui.Dialog().notification(title, message, ICON_INFO, 6000)

    except Exception as major_err:
        log_message(f"Setup Helper: Orchestration master failure: {major_err}", 3)

    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    if len(sys.argv) > 1 and "cleanup" in sys.argv:
        perform_cleanup()
