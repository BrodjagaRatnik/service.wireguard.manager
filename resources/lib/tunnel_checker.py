""" ./resources/lib/tunnel_checker.py """
import kodi_env
import os
import subprocess
import time

try:
    import xbmcgui
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

try:
    import xbmc
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

from logger import log_message
from vpn_utils import is_interface_active, get_active_interface, fetch_vpn_metadata
from state_manager import get_active_vpn, write_state
from vpn_config import PI5, PI4, PI3, PI2, SANITY_POLL_INTERVAL, SANITY_SETTLE_DELAY


def run_tunnel_sanity_check():
    addon_obj = kodi_env.get_addon_instance()
    if not addon_obj:
        kodi_env.clear_script_globals()
        return

    is_playing_stream = False
    if HAS_KODI and xbmc.Player().isPlaying():
        playing_file = xbmc.Player().getPlayingFile()
        stream_protocols = ["http://", "https://", "rtmp://", "pvr://"]
        is_playing_stream = any(playing_file.startswith(p) for p in stream_protocols)

    if is_playing_stream:
        log_message("Tunnel Check: Active stream detected. Postponing health check.", 0)
        return

    addon_path = kodi_env.ADDON_DIR
    icon_con = os.path.join(addon_path, "resources", "media", "vpn_connected.png")

    if not is_interface_active("wg0"):
        return

    try:
        current_default_iface = get_active_interface()
        tunnel_is_broken = False

        if current_default_iface != "wg0":
            tunnel_is_broken = True
        else:
            try:
                res = subprocess.run(
                    ["ping", "-c", "1", "-W", "2", "1.1.1.1"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=3.0
                )
                if res.returncode != 0:
                    log_message("Tunnel Check: Interface up but end-to-end routing ping failed.", 0)
                    tunnel_is_broken = True
            except subprocess.TimeoutExpired:
                log_message("Tunnel Check: Process execution timed out.", 0)
                tunnel_is_broken = True
            except Exception as ping_err:
                log_message(f"Tunnel Check: Connection verification exception: {ping_err}", 3)
                tunnel_is_broken = True

        if tunnel_is_broken:
            log_message("Tunnel Check: Dead link confirmed. Forcing reconnect sequence...", 2)
            boot_target = get_active_vpn()
            import vpn_ops
            teardown_start = time.perf_counter()
            vpn_ops.disconnect_vpn(silent=True, flush_dns=True)

            while is_interface_active("wg0"):
                time.sleep(SANITY_POLL_INTERVAL / 1000.0)
            time.sleep(SANITY_SETTLE_DELAY / 1000.0)

            elapsed_ms = (time.perf_counter() - teardown_start) * 1000
            hw_name = (
                "Raspberry Pi 5" if PI5 else
                "Raspberry Pi 4" if PI4 else
                "Raspberry Pi 3" if PI3 else
                "Raspberry Pi 2" if PI2 else "Generic Device"
            )
            log_message(
                f"Timing Tracker: Interface teardown completed. "
                f"Hardware Matrix: {hw_name} | "
                f"Teardown Release Time: {elapsed_ms:.2f}ms", 0
            )

            try:
                from vpn_core import check_for_updates
                check_for_updates("")
            except Exception as update_err:
                log_message(f"Tunnel Check: Inline update invocation failed: {update_err}", 3)

            if boot_target:
                from service_launcher import resolve_service_id
                sid = resolve_service_id(addon_obj, boot_target.replace(" ", "_"))
                if not sid:
                    sid = resolve_service_id(addon_obj, boot_target)

                if sid:
                    log_message("Tunnel Check: Registering fallback session state protection.", 0)
                    write_state('manual', 'true')
                    if HAS_GUI:
                        xbmcgui.Window(10000).setProperty('vpn_manual_session', 'true')

                    log_message(f"Tunnel Check: Re-establishing profile link [{boot_target}] safely.", 1)
                    vpn_ops.connect_vpn(str(boot_target), str(sid), silent=True)

                    if HAS_GUI:
                        ip, country = fetch_vpn_metadata()
                        title = "[B][COLOR FF00FF00]▄■ [ TUNNEL RESTORED ] ■▄[/COLOR][/B]"
                        msg = f"[B][COLOR FF32CD32]{boot_target}[/COLOR] • ({country})[/B]"
                        xbmcgui.Dialog().notification(title, msg, icon_con, 4500)
                else:
                    log_message(f"Tunnel Check: Service ID lookup dropped for {boot_target}", 3)
            else:
                log_message("Tunnel Check: No active link cached in configuration text. Recovery dropped.", 2)
        else:
            log_message("Tunnel Check: Link health verification successfully. Tunnel is clear.", 0)

    except Exception as e:
        log_message(f"Tunnel Check: Monitoring framework tracking exception: {e}", 3)
    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    run_tunnel_sanity_check()
