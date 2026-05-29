''' ./resources/lib/setup_helper.py '''
import os
import shutil
import subprocess
import sys
from logger import log_message
from vpn_config import PROVIDER_MAP

try:
    import xbmc
    import xbmcgui
    import xbmcaddon
    import xbmcvfs
except ImportError:
    pass


def _setup_paths():
    try:
        addon_handle = xbmcaddon.Addon('service.wireguard.manager')
        addon_path = xbmcvfs.translatePath(addon_handle.getAddonInfo('path'))
        local_lib = os.path.join(addon_path, 'resources', 'lib')

        if local_lib not in sys.path:
            sys.path.insert(0, local_lib)

        if 'utils' in sys.modules:
            m = sys.modules['utils']
            if hasattr(m, '__file__') and 'service.wireguard.manager' not in m.__file__:
                del sys.modules['utils']
    except Exception as e:
        log_message(f"Path setup critical failure: {e}", 3)


_setup_paths()


def perform_cleanup(silent=False):
    """Factory reset: Removes all configs, services, and temporary files."""
    ADDON = xbmcaddon.Addon('service.wireguard.manager')
    wg_config_path = '/storage/.config/wireguard/'

    try:
        log_message("Cleanup: Starting factory reset...", 1)

        service_file = '/storage/.config/system.d/vpn-watchdog.service'
        if os.path.exists(service_file):
            subprocess.run(["systemctl", "stop", "vpn-watchdog.service"], check=False)
            subprocess.run(["systemctl", "disable", "vpn-watchdog.service"], check=False)
            os.remove(service_file)
            subprocess.run(["systemctl", "daemon-reload"], check=False)

        if os.path.exists(wg_config_path):

            cmd = "rm -f /storage/.config/wireguard/*_*.config"
            subprocess.run(cmd, shell=True, check=False)
            log_message("Cleanup: WireGuard configs wiped via shell.", 1)

        ADDON.setSetting('selected_countries', '')
        ADDON.setSetting('selected_countries_pia', '')
        ADDON.setSetting('first_run', 'false')

        for f in [
            xbmcvfs.translatePath(
                'special://userdata/keymaps/wireguard_manager_key.xml'
            ),
            '/storage/.config/connman_main.conf'
        ]:

            if os.path.exists(f):
                os.remove(f)

        for tf in [
            "/tmp/vpn_manager_active.txt",
            "/tmp/vpn_manual_active.txt",
            "/tmp/vpn_reconnect_count.txt",
            "/tmp/vpn_intentional_disconnect.txt"
        ]:

            if os.path.exists(tf):
                try:
                    os.remove(tf)
                except Exception as e:
                    log_message(f"Reset error removing {tf}: {e}", 3)

        log_message("Cleanup: Reset complete.", 1)
        if not silent:
            title = "[B]≡ [ CLEANUP COMPLETE ] ≡[/B]"
            msg = "[COLOR FFFFFF00]Cleanup successful. All files removed.[/COLOR]"
            xbmcgui.Dialog().ok(title, msg)

    except Exception as e:
        log_message(f"Cleanup Error: {e}", 3)


def ensure_setup(addon_path, silent=False):
    ADDON = xbmcaddon.Addon('service.wireguard.manager')
    keymap_dest = xbmcvfs.translatePath('special://userdata/keymaps/wireguard_manager_key.xml')
    keymap_source = os.path.join(addon_path, 'resources', 'keymaps', 'wireguard_manager_key.xml')
    wg_config_path = '/storage/.config/wireguard/'
    template_dest = os.path.join(wg_config_path, 'placeholder_template.config')
    template_source = os.path.join(addon_path, 'resources', 'data', 'template.config.txt')
    service_dest = '/storage/.config/system.d/vpn-watchdog.service'
    service_source = os.path.join(addon_path, 'resources', 'data', 'vpn-watchdog.service.txt')
    connman_dest = '/storage/.config/connman_main.conf'
    connman_source = os.path.join(addon_path, 'resources', 'data', 'connman_main.conf.txt')
    cert_source = os.path.join(addon_path, 'resources', 'data', 'ca.rsa.4096.txt')
    cert_dest = os.path.join(addon_path, 'resources', 'lib', 'providers', 'ca.rsa.4096.crt')

    setup_updated = False

    progress = xbmcgui.DialogProgress()
    progress.create("WireGuard Manager", "Starting system check...")

    progress.update(10, "Checking Keymaps...")
    if not os.path.exists(keymap_dest):
        try:
            os.makedirs(os.path.dirname(keymap_dest), exist_ok=True)
            shutil.copy2(keymap_source, keymap_dest)
            log_message("Setup: Keymap installed.", 1)
            xbmc.executebuiltin('Action(ReloadKeymaps)')
            log_message("Setup: Keymaps reloaded in Kodi.", 1)
        except Exception as e:
            log_message(f"Setup Error (Keymap): {e}", 3)

    progress.update(20, "Checking network configuration...")
    if not os.path.exists(connman_dest):
        try:
            shutil.copy2(connman_source, connman_dest)
            subprocess.run(["systemctl", "restart", "connman"], check=False)
            log_message("Setup: Connman config installed.", 1)
            setup_updated = True
        except Exception as e:
            log_message(f"Setup Error (Connman): {e}", 3)

    progress.update(30, "Installing VPN Watchdog...")
    if not os.path.exists(service_dest):
        try:
            os.makedirs(os.path.dirname(service_dest), exist_ok=True)
            shutil.copy2(service_source, service_dest)
            subprocess.run(["systemctl", "daemon-reload"], check=False)
            subprocess.run(["systemctl", "enable", "vpn-watchdog.service"], check=False)
            subprocess.run(["systemctl", "start", "vpn-watchdog.service"], check=False)
            log_message("Setup: Watchdog service installed.", 1)
            setup_updated = True
        except Exception as e:
            log_message(f"Setup Error (Service): {e}", 3)

    progress.update(40, "Checking WireGuard templates...")
    if not os.path.exists(template_dest):
        try:
            os.makedirs(wg_config_path, exist_ok=True)
            shutil.copy2(template_source, template_dest)
        except Exception as e:
            log_message(f"Template deployment failure: {e}", 3)

    progress.update(60, "Deploying provider certificates...")
    if not os.path.exists(cert_dest):
        try:
            os.makedirs(os.path.dirname(cert_dest), exist_ok=True)
            shutil.copy2(cert_source, cert_dest)
            log_message("Setup: Secure verification certificate deployed.", 1)
        except Exception as e:
            log_message(f"Setup Error (Certificate Copy): {e}", 3)

    progress.update(80, "Verifying VPN credentials...")
    current_p_id = ADDON.getSettingInt("vpn_provider")
    has_creds = False
    if current_p_id == -1:
        log_message("First-time setup: No VPN provider selected yet. Skipping credential check.", 1)
    else:
        p_data = PROVIDER_MAP.get(current_p_id, {"name": "Unknown", "prefix": "unknown_"})
        token_setting = p_data.get("setting")
        if token_setting:
            has_creds = bool(ADDON.getSetting(token_setting).strip())
        if current_p_id == 99 or not has_creds:
            prefix = p_data["prefix"]
            if os.path.exists(wg_config_path):
                has_files = any(f.startswith((prefix, 'custom_')) for f in os.listdir(wg_config_path))
                has_creds = has_creds or has_files

    progress.update(100, "Setup Complete.")
    if setup_updated:
        log_message("Setup: All system checks completed successfully.", 0)
    progress.close()

    wg_config_path = '/storage/.config/wireguard/'
    has_configs = False
    if os.path.exists(wg_config_path):
        has_configs = any(f.endswith(('.config', '.conf')) for f in os.listdir(wg_config_path))

    if setup_updated and has_configs:
        log_message("Setup: Success! System services and configurations installed. WireGuard manager active.", 1)

        addon_handle = xbmcaddon.Addon('service.wireguard.manager')
        path_fixed = xbmcvfs.translatePath(addon_handle.getAddonInfo('path'))
        ICON_INFO = os.path.join(path_fixed, 'resources', 'media', 'icon.png')
        title = "[B][COLOR FFEEFFEE]≡ [ SETUP SUCCESS ] ≡[/COLOR][/B]"
        message = (
            "[COLOR FFE6E6FA]System services installed.[/COLOR]\n"
            "[COLOR FFFFFF00]WireGuard manager is now active.[/COLOR]"
        )
        xbmcgui.Dialog().notification(title, message, ICON_INFO, 6000)


if __name__ == '__main__':
    if len(sys.argv) > 1 and "cleanup" in sys.argv:
        perform_cleanup()
