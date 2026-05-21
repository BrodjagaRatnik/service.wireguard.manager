''' ./resources/lib/service_launcher.py '''
import base64
import os
import re
import subprocess
import sys
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from logger import log_message
from vpn_config import (
    PI5,
    WATCHDOG_HEARTBEAT,
)
import vpn_ops

try:
    from setup_helper import ensure_setup
except ImportError:
    from setup_utils import ensure_setup

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


class WGManagerService(xbmc.Monitor):

    def __init__(self, addon, vpn_ops_mod):
        super().__init__()
        self._ADDON = addon
        self.vpn_ops = vpn_ops_mod
        self.cleanup_count = 0

        hardware = "Raspberry Pi 5" if PI5 else "Raspberry Pi 4"
        log_message(f"Hardware timings loaded for {hardware}", 1)
        log_message("Monitor Service Initialized & Ready", 1)

    def onSettingsChanged(self):
        if os.path.exists('/tmp/vpn_notif_sent.lock'):
            try:
                os.remove('/tmp/vpn_notif_sent.lock')
            except Exception:
                pass

        if not self._ADDON.getSettingBool("first_run"):
            return

        provider_id = self._ADDON.getSettingInt("vpn_provider")
        config_dir = "/storage/.config/wireguard/"
        if provider_id < 0:
            return

        if provider_id == 1:
            try:
                from providers import pia
                user = self._ADDON.getSetting("pia_user").strip()
                raw_pw = self._ADDON.getSetting("pia_pass").strip()
                ids = self._ADDON.getSetting("selected_countries_pia").strip()

                if user and raw_pw and ids:
                    try:
                        clean_pw = str(raw_pw).strip()
                        missing_padding = len(clean_pw) % 4
                        if missing_padding:
                            clean_pw += '=' * (4 - missing_padding)
                        pw = base64.b64decode(clean_pw).decode('utf-8').strip()
                    except Exception:
                        pw = raw_pw

                    pia.update(user, pw, ids, config_dir)
            except Exception as e:
                log_message(f"PIA update failed: {e}", 3)

        elif provider_id == 0:
            try:
                from providers import nordvpn
                token = self._ADDON.getSetting("vpn_token")
                ids = self._ADDON.getSetting("selected_countries").strip()
                if token and ids:
                    nordvpn.update(token, ids, config_dir)
            except Exception as e:
                log_message(f"Nord update failed: {e}", 3)

    def get_service_id_by_name(self, name):
        try:
            search_name = name
            provider_id = self._ADDON.getSettingInt("vpn_provider")

            if provider_id in [0, 99] and name:
                conf_dir = '/storage/.config/wireguard/'
                p_prefix = "nord_" if provider_id == 0 else "custom_"
                clean_target = (
                    name.lower()
                    .replace('nordvpn', '')
                    .replace('custom', '')
                    .replace('_', '')
                    .replace('-', '')
                    .strip()
                )

                if os.path.exists(conf_dir):
                    for filename in os.listdir(conf_dir):
                        if (filename.startswith(p_prefix) and
                                filename.endswith((".config", ".conf"))):
                            full_path = os.path.join(conf_dir, filename)

                            try:
                                with open(full_path, 'r') as f:
                                    content = f.read()

                                name_match = re.search(r'^\s*Name\s*=\s*(.*)', content, re.MULTILINE)
                                if name_match:
                                    actual_config_name = name_match.group(1).strip()
                                    clean_config_name = (
                                        actual_config_name.lower()
                                        .replace('nordvpn', '')
                                        .replace('custom', '')
                                        .replace('_', '')
                                        .replace('-', '')
                                        .strip()
                                    )

                                    if (clean_target == clean_config_name or
                                            clean_config_name in clean_target or
                                            clean_target in clean_config_name):
                                        search_name = actual_config_name
                                        break
                            except Exception:
                                pass

            out = subprocess.check_output(["connmanctl", "services"], text=True)
            for line in out.splitlines():
                if search_name in line:
                    return line.split()[-1]

        except Exception as e:
            log_message(f"Service lookup error for {name}: {e}", 3)
            return None

    def run_loop(self):
        if os.path.exists('/tmp/vpn_intentional_disconnect.txt'):
            self.cleanup_count = 0
            return

        if xbmc.Player().isPlayingVideo():
            self.cleanup_count = 0
            return

        active_now = self.vpn_ops.get_active_vpn()

        if not active_now:
            try:
                if os.path.exists('/sys/class/net/'):
                    interfaces = os.listdir('/sys/class/net/')
                    wg_ifs = [
                        i for i in interfaces
                        if i.startswith(('wg', 'pia', 'wireguard'))
                    ]

                    if wg_ifs:
                        config_dir = '/storage/.config/wireguard/'
                        if os.path.exists(config_dir):
                            configs = [
                                c.replace('.config', '').replace('.conf', '')
                                for c in os.listdir(config_dir)
                                if c.endswith(('.config', '.conf'))
                            ]
                            for c in configs:
                                if any(c in iface or iface in c for iface in wg_ifs):
                                    active_now = c
                                    break

                        if not active_now:
                            active_now = wg_ifs[0]

            except Exception as e:
                log_msg = f"Monitor: Kernel interface scan failed: {e}"
                log_message(log_msg, 0)

        is_manual = (
            xbmcgui.Window(10000)
            .getProperty('vpn_manual_session')
            .lower() == 'true'
            or os.path.exists('/tmp/vpn_manual_active.txt')
        )
        is_home = xbmc.getCondVisibility(
            "Window.IsActive(home) | Window.IsActive(10000)"
        )
        plugin = xbmc.getInfoLabel("Container.PluginName")
        folder = xbmc.getInfoLabel("Container.FolderPath")

        is_manual_file = os.path.exists('/tmp/vpn_manual_active.txt')
        is_manual_prop = xbmcgui.Window(10000).getProperty('vpn_manual_session').lower() == 'true'

        if is_home and (is_manual_file or is_manual_prop):
            self.cleanup_count = 0
            return

        match_found = False
        if not is_home and plugin.startswith("plugin.video."):
            provider_id = self._ADDON.getSettingInt("vpn_provider")

            if provider_id != 1:
                for i in range(1, 9):
                    target = self._ADDON.getSetting(f"map_{i}_addon")
                    vpn_target = self._ADDON.getSetting(f"vpn_{i}_name")
                    if target and (target in folder or target == plugin):

                        v_clean = (
                            "" if not vpn_target else
                            vpn_target.lower().replace(' ', '').strip()
                        )
                        a_clean = (
                            "" if not active_now else
                            active_now.lower().replace(' ', '').strip()
                        )

                        if not active_now:
                            log_msg = f"Monitor: Connecting to profile: {vpn_target}"
                            log_message(log_msg, 0)
                            is_match = False
                        else:
                            is_match = (
                                (v_clean == a_clean) or
                                (v_clean in a_clean) or
                                (a_clean in v_clean) or
                                (v_clean.replace('_', '') in
                                 a_clean.replace('_', ''))
                            )

                        if is_match:
                            match_found = True
                        else:
                            match_found = True
                            log_msg = f"Switching location map path to target: {vpn_target}."
                            log_message(log_msg, 1)

                            xbmcgui.Window(10000).setProperty('vpn_manual_session', 'false')
                            if os.path.exists('/tmp/vpn_manual_active.txt'):
                                try:
                                    os.remove('/tmp/vpn_manual_active.txt')
                                except Exception:
                                    pass

                            self.vpn_ops.disconnect_vpn(silent=True)
                            time.sleep(1.0)

                            sid = self.get_service_id_by_name(vpn_target)
                            if sid:
                                self.vpn_ops.connect_vpn(str(vpn_target), str(sid))
                                time.sleep(1.0)
                            else:
                                err_msg = (
                                    "Monitor Error: Connection tracking target ID "
                                    f"for profile {vpn_target} not found."
                                )
                                log_message(err_msg, 3)
                        break

        if not match_found and active_now and not is_manual:
            self.cleanup_count += 1

            try:
                import xbmcaddon
                fresh_addon = xbmcaddon.Addon('service.wireguard.manager')
                user_timeout_sec = float(fresh_addon.getSettingInt("home_timeout_sec") or 5)
            except Exception:
                user_timeout_sec = 5.0

            elapsed_time_sec = self.cleanup_count * (WATCHDOG_HEARTBEAT / 1000.0)

            if elapsed_time_sec >= user_timeout_sec:
                self.cleanup_count = 0

                log_msg = (
                    f"Home timeout ({user_timeout_sec}s) reached. "
                    f"Disconnecting active profile [{active_now}]."
                )
                log_message(log_msg, 1)

                xbmcgui.Window(10000).setProperty('vpn_manual_session', 'false')
                if os.path.exists('/tmp/vpn_manual_active.txt'):
                    try:
                        os.remove('/tmp/vpn_manual_active.txt')
                    except Exception:
                        pass

                self.vpn_ops.disconnect_vpn(silent=False)
                time.sleep(1.0)

        else:
            self.cleanup_count = 0


def start():
    addon = xbmcaddon.Addon('service.wireguard.manager')
    path = xbmcvfs.translatePath(addon.getAddonInfo('path'))

    if not addon.getSettingBool("first_run"):
        if ensure_setup(path, silent=True) is True:
            addon.setSettingBool("first_run", True)
            xbmc.executebuiltin('UpdateAddonByReadme()')

    try:
        monitor = WGManagerService(addon, vpn_ops)
    except Exception as e:
        log_message(f"CRITICAL: Monitor failed to start: {e}", 3)
        return

    try:
        is_enabled = addon.getSetting('disconnect_on_start').lower() == 'true'
        log_msg = f"Startup Cleaner: Verified configuration [Enabled: {is_enabled}]"
        log_message(log_msg, 0)

        if is_enabled:
            pre_active = monitor.vpn_ops.get_active_vpn()

            for f in ['/tmp/vpn_manager_active.txt', '/tmp/vpn_reconnect_count.txt']:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as e:
                        log_message(f"Cleanup error removing {f}: {e}", 3)

            with open('/tmp/vpn_intentional_disconnect.txt', 'w') as f:
                f.write('startup_clean')

            if pre_active:
                log_msg = f"Startup Cleaner: Actively disconnecting live tunnel profile: {pre_active}"
                log_message(log_msg, 1)
            else:
                log_message("Startup Cleaner: Disconnect instruction sent (No active tunnel connection found)", 0)

            monitor.vpn_ops.disconnect_vpn(silent=True)

    except Exception as e:
        log_message(f"Startup Cleaner Error: {e}", 3)

    try:
        hb = WATCHDOG_HEARTBEAT / 1000.0

    except Exception as e:
        log_message(f"Watchdog interval calculation failure: {e}", 3)
        hb = 1.0

    while not monitor.abortRequested():
        monitor.run_loop()
        if monitor.waitForAbort(hb):
            break


if __name__ == '__main__':
    start()
