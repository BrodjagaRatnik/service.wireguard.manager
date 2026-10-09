""" ./resources/lib/vpn_connector.py """
import json
import kodi_env
import os
import subprocess
import sys
import time
from logger import log_message
from vpn_config import (
    CONNMAN_SETTLE_DELAY,
    DHCP_RECOVERY_DELAY,
    PROVIDER_MAP,
    ROUTE_PROP_DELAY,
    VPN_CONNECTION_TIMEOUT,
)
from network_utils import (
    set_secure_dns,
    get_default_gateway,
    disable_connman_ipv6
)
from vpn_utils import (
    flush_connman_dns_cache,
    is_interface_active,
    fetch_vpn_metadata,
    setup_pia_handshake
)
from state_manager import get_file_path
from providers.routing import setup_vpn_routing
from resources.scripts.killswitch import ZeroHardcodeKillSwitch
import dialog

try:
    import xbmc
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

MAX_CONNECT_ATTEMPTS = 3
CYCLE_FAIL_LIMIT = MAX_CONNECT_ATTEMPTS * 2
CYCLE_FAIL_STALE_S = 3600
_CYCLE_STATE_NAME = "cycle_fail_state"


def _cycle_state_path():
    return get_file_path(_CYCLE_STATE_NAME)


def _load_cycle_state():
    now = time.time()
    fresh = {"count": 0, "ts": now, "name": ""}
    path = _cycle_state_path()
    if path is None or not os.path.exists(path):
        return fresh
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return fresh
        if now - float(data.get("ts", 0)) > CYCLE_FAIL_STALE_S:
            return fresh
        return {
            "count": int(data.get("count", 0)),
            "ts": float(data.get("ts", now)),
            "name": str(data.get("name", "")),
        }
    except Exception:
        return fresh


def _save_cycle_state(state):
    path = _cycle_state_path()
    if path is None:
        return
    try:
        with open(path, "w") as f:
            json.dump(state, f)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass


def _reset_cycle_state():
    _save_cycle_state({"count": 0, "ts": time.time(), "name": ""})


def _bump_cycle_state(vpn_name):
    state = _load_cycle_state()
    state = {"count": state["count"] + 1, "ts": time.time(), "name": vpn_name}
    _save_cycle_state(state)
    return state["count"]


def _strip_candidate_suffix(profile_stem):
    if len(profile_stem) > 2 and profile_stem[-2:].isdigit():
        return profile_stem[:-2]
    return profile_stem


def _find_sibling_profiles(profile_id, p_name=""):
    if p_name == "mullvad":
        try:
            from providers.mullvad_utils import find_siblings_by_country
            return find_siblings_by_country(profile_id)
        except Exception as sibling_fault:
            log_message(f"VPN Connector: Mullvad sibling discovery failed: {sibling_fault}", 3)
            return []
    matched = []
    try:
        from state_manager import CONFIG_DIR
        group_prefix = _strip_candidate_suffix(profile_id)
        for file_name in sorted(os.listdir(CONFIG_DIR)):
            if not file_name.endswith(".config"):
                continue
            stem = file_name[:-len(".config")]
            if _strip_candidate_suffix(stem) == group_prefix and stem != profile_id:
                matched.append(stem)
    except Exception:
        pass
    return matched


def _next_untried_sibling(profile_id, tried_profiles, p_name=""):
    if len(tried_profiles) >= MAX_CONNECT_ATTEMPTS:
        return None
    for sibling in _find_sibling_profiles(profile_id, p_name):
        if sibling not in tried_profiles:
            return sibling
    return None


def _detect_silent_context():
    frame_trace = ""
    try:
        curr_frame = sys._getframe()
        while curr_frame:
            f_name = curr_frame.f_code.co_filename
            if f_name:
                frame_trace += f"|{os.path.basename(f_name)}"
            curr_frame = curr_frame.f_back
    except Exception:
        pass

    for key in ("tunnel_checker", "service_loop", "service_launcher"):
        if key in frame_trace:
            return key
    return "normal"


def _extract_server_ip(sid):
    if sid and sid.startswith("vpn_"):
        return sid[4:].replace("_", ".")
    try:
        from state_manager import CONFIG_DIR
        target_conf = os.path.join(CONFIG_DIR, f"{sid}.config")
        if os.path.exists(target_conf):
            with open(target_conf, "r") as conf_reader:
                for line in conf_reader:
                    if line.startswith("Host ="):
                        return line.split("=")[-1].strip()
    except Exception:
        pass
    return None


def _display_name_from_sid(candidate_sid):
    try:
        from state_manager import CONFIG_DIR
        if not (candidate_sid and candidate_sid.startswith("vpn_")):
            return None
        host_ip = candidate_sid[4:].replace("_", ".")
        for file_name in sorted(os.listdir(CONFIG_DIR)):
            if not file_name.endswith(".config"):
                continue
            file_path = os.path.join(CONFIG_DIR, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as name_reader:
                    host_value = None
                    display_value = None
                    for line in name_reader:
                        if line.startswith("Host =") and host_value is None:
                            host_value = line.split("=", 1)[-1].strip()
                        elif line.startswith("Name =") and display_value is None:
                            display_value = line.split("=", 1)[-1].strip()
                        if host_value and display_value:
                            break
                    if host_value == host_ip and display_value:
                        return display_value
            except Exception:
                continue
    except Exception:
        pass
    return None


def connect_vpn(vpn_name, sid, instance, silent=False, tried_profiles=None, display_name=None):
    tried_profiles = tried_profiles if tried_profiles is not None else set()
    lock_path = get_file_path("connector_lock")
    killswitch = None

    try:
        if lock_path is not None and os.path.exists(lock_path):
            try:
                with open(lock_path, "r") as f:
                    prev_pid = int(f.read().strip() or "0")
                if prev_pid == os.getpid():
                    log_message(
                        "VPN Connector: Lock held by own retry chain (pid %d), continuing." % prev_pid, 0
                    )
                elif os.path.exists("/proc/%d" % prev_pid):
                    log_message(
                        "VPN Connector: connect already in progress (pid %d), "
                        "debouncing this invocation" % prev_pid, 0
                    )
                    return False
                else:
                    log_message(
                        "VPN Connector: removing stale connector lock (dead pid %d)" % prev_pid, 0
                    )
            except (ValueError, OSError):
                pass

        try:
            if lock_path is not None:
                with open(lock_path, "w") as f:
                    f.write(str(os.getpid()))
                    f.flush()
                    os.fsync(f.fileno())
        except Exception:
            pass

        cycle_state = _load_cycle_state()
        if silent is True and cycle_state["count"] >= CYCLE_FAIL_LIMIT:
            if cycle_state["name"] and vpn_name and cycle_state["name"] != vpn_name:
                _reset_cycle_state()
            else:
                log_message(
                    "VPN Connector: Cycle-fail breaker open (%d consecutive failures on "
                    "'%s'). Deferring silent retry until manual reconnect or profile "
                    "switch." % (cycle_state["count"], cycle_state["name"]), 2
                )
                return False
        elif silent is False:
            _reset_cycle_state()
            dialog.clear_failure_dialogs()

        addon_obj = kodi_env.get_addon_instance()
        provider_id = addon_obj.getSettingInt("vpn_provider") if (HAS_KODI and addon_obj) else 0
        p_data = PROVIDER_MAP.get(provider_id, {})
        p_name = p_data.get("name", "").lower()

        if p_name == "pia":
            log_message("VPN Connector: PIA route detected. Triggering API handshake...", 0)
            if setup_pia_handshake(sid, p_data, addon_obj, HAS_KODI) is False:
                return False

        log_message(f"VPN Connector: Connecting to {vpn_name}", 0)
        if silent is True:
            dialog.notify_tunnelling(vpn_name, duration_ms=4000)

        tried_profiles.add(sid)

        ks_enabled = addon_obj.getSettingBool("enable_killswitch") if (HAS_KODI and addon_obj) else False
        server_ip = _extract_server_ip(sid)

        if ks_enabled:
            if server_ip:
                killswitch = ZeroHardcodeKillSwitch(vpn_server_ip=server_ip)
                if killswitch.enable():
                    log_message(f"VPN Connector: Killswitch Firewall engaged for IP {server_ip}", 1)
                else:
                    reason = getattr(killswitch, "last_error", "") or "unknown cause"
                    log_message(f"VPN Connector: Killswitch could not be engaged ({reason})", 3)
                    killswitch = None
                    dialog.notify_killswitch_not_active()
            else:
                log_message(
                    f"VPN Connector: Killswitch Firewall enabled but could not extract IP from SID '{sid}'", 2
                )
                dialog.notify_killswitch_not_active()

        pbg = dialog.ConnectProgress(vpn_name, silent is False and HAS_KODI is True)

        subprocess.run(
            ["connmanctl", "connect", sid],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if CONNMAN_SETTLE_DELAY > 0:
            if HAS_KODI is True:
                xbmc.sleep(CONNMAN_SETTLE_DELAY)
            else:
                time.sleep(CONNMAN_SETTLE_DELAY / 1000.0)

        connected = False
        max_steps = int(VPN_CONNECTION_TIMEOUT / DHCP_RECOVERY_DELAY)
        step_percent = 100.0 / max_steps

        for i in range(1, max_steps + 1):
            if pbg is not None:
                msg_str = f"Verifying... ({int((i * DHCP_RECOVERY_DELAY) / 1000)}s)"
                pbg.update(int(i * step_percent), msg_str)
            if is_interface_active("wg0") is True:
                connected = True
                break
            if HAS_KODI is True:
                xbmc.sleep(DHCP_RECOVERY_DELAY)
            else:
                time.sleep(DHCP_RECOVERY_DELAY / 1000.0)

        if pbg is not None:
            pbg.close()

        if connected is True:
            log_message(f"VPN Connector: Successfully connected to {vpn_name}", 1)
            setup_vpn_routing(sid, bool(p_data.get("requires_endpoint_route")))
            subprocess.run(["ip", "route", "flush", "cache"], check=False)
            instance.set_active_vpn(vpn_name)

            try:
                disable_connman_ipv6()
            except Exception:
                pass

            if HAS_KODI is True:
                xbmc.sleep(ROUTE_PROP_DELAY)
            else:
                time.sleep(ROUTE_PROP_DELAY / 1000.0)

            set_secure_dns(vpn_name, vpn_active=True, sid=sid)

            if HAS_KODI is True:
                ip, country = fetch_vpn_metadata()

                if not ip or ip == "Unknown":
                    tunnel_reachable = False
                    try:
                        ping_res = subprocess.run(
                            ["ping", "-c", "1", "-W", "2", "-I", "wg0", "1.1.1.1"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                            timeout=4.0
                        )
                        tunnel_reachable = ping_res.returncode == 0
                    except Exception:
                        tunnel_reachable = False

                    if tunnel_reachable is True:
                        ip = "Tunnel Active (Protected)"
                        country = "Unknown"

                if ip and ip != "Unknown":
                    toast_name = display_name if display_name else vpn_name
                    context = _detect_silent_context() if silent is True else "normal"
                    log_message(f"VPN Connector: Dispatching connected toast for {toast_name} ({ip})", 0)
                    dialog.notify_connected(toast_name, ip, country, context=context)
                    log_message("VPN Connector: Connected toast dispatch returned", 0)
                    _reset_cycle_state()
                    return True

                log_message(
                    f"VPN Connector: {sid} tunnel up but data path verification failed. "
                    f"Treating as failed connection.", 2
                )

                if killswitch:
                    killswitch.disable()

                subprocess.run(
                    ["connmanctl", "disconnect", sid],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                next_profile = _next_untried_sibling(sid, tried_profiles, p_name)
                if next_profile:
                    log_message(
                        f"VPN Connector: {sid} connected but data path verification failed, "
                        f"trying alternate candidate {next_profile} "
                        f"(attempt {len(tried_profiles) + 1}/{MAX_CONNECT_ATTEMPTS})", 2
                    )
                    return connect_vpn(
                        vpn_name, next_profile, instance, silent=silent,
                        tried_profiles=tried_profiles,
                        display_name=_display_name_from_sid(next_profile) or display_name
                    )

                if silent is True:
                    fail_count = _bump_cycle_state(vpn_name)
                    if fail_count >= CYCLE_FAIL_LIMIT:
                        log_message(
                            "VPN Connector: Repeated data-path failure (%d consecutive attempts on "
                            "'%s'). Opening breaker and executing full teardown." % (fail_count, vpn_name), 2
                        )
                        dialog.notify_connection_failed(vpn_name)
                        instance.disconnect_vpn(silent=True, flush_dns=True)
                        flush_connman_dns_cache()
                        return False
                    log_message(
                        "VPN Connector: Tunnel up but not passing traffic. Retrying... (%d/%d)"
                        % (fail_count, CYCLE_FAIL_LIMIT), 1
                    )
                    dialog.notify_tunnelling(vpn_name, duration_ms=4000)
                else:
                    dialog.notify_connection_failed(vpn_name)

                instance.disconnect_vpn(silent=True, flush_dns=False)
                flush_connman_dns_cache()
                return False

            return True

        if killswitch:
            killswitch.disable()

        subprocess.run(
            ["connmanctl", "disconnect", sid],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        next_profile = _next_untried_sibling(sid, tried_profiles, p_name)
        if next_profile:
            log_message(
                f"VPN Connector: {sid} failed to connect, trying alternate candidate "
                f"{next_profile} (attempt {len(tried_profiles) + 1}/{MAX_CONNECT_ATTEMPTS})", 2
            )
            return connect_vpn(vpn_name, next_profile, instance, silent=silent, tried_profiles=tried_profiles)

        err_msg = "Internet lost."
        if get_default_gateway():
            err_msg = "Handshake failed. Refused, rate-limited, or unreachable."

        if silent is True:
            fail_count = _bump_cycle_state(vpn_name)
            if fail_count >= CYCLE_FAIL_LIMIT:
                log_message(
                    "VPN Connector: Repeated connect-cycle failure (%d consecutive attempts on "
                    "'%s'). Opening breaker and executing full teardown." % (fail_count, vpn_name), 2
                )
                dialog.notify_connection_failed(vpn_name)
                instance.disconnect_vpn(silent=True, flush_dns=True)
                flush_connman_dns_cache()
                return False
            log_message(
                "VPN Connector: Routing profile transition in progress. Retrying step... (%d/%d)"
                % (fail_count, CYCLE_FAIL_LIMIT), 1
            )
            dialog.notify_tunnelling(vpn_name, duration_ms=4000)
        else:
            log_message(f"VPN Connector: {err_msg}", 3)
            dialog.notify_vpn_failure(err_msg)

        instance.disconnect_vpn(silent=True, flush_dns=False)
        flush_connman_dns_cache()
        return False

    except Exception as connector_fault:
        log_message(f"VPN Connector: Critical framework core failure: {connector_fault}", 3)
        if killswitch:
            killswitch.disable()
        return False

    finally:
        if lock_path is not None and os.path.exists(lock_path) is True:
            try:
                os.remove(lock_path)
            except Exception:
                pass
        try:
            kodi_env.clear_script_globals()
        except Exception:
            pass
