""" ./resources/lib/dialog.py """
import os
import kodi_env
from logger import log_message

try:
    import xbmc
    import xbmcgui
    HAS_KODI = True
except ImportError:
    HAS_KODI = False

_ICON_CONNECTED = "vpn_connected.png"
_ICON_DISCONNECTED = "vpn_disconnected.png"
_ICON_FORCE = "force.png"
_ICON_ERROR = "error.png"
_ICON_UPDATE_OK = "update_ok.png"
_ICON_ADDON = "icon.png"

_failure_dialog_active = False


class ConnectProgress(object):

    def __init__(self, vpn_name, enabled):
        self._enabled = enabled is True and HAS_KODI is True
        self._progress = None
        if self._enabled is True:
            try:
                self._progress = xbmcgui.DialogProgressBG()
                self._progress.create("VPN Manager", f"Connecting to {vpn_name}...")
            except Exception as dialog_fault:
                log_message(f"Dialog: Progress bar creation failed: {dialog_fault}", 3)
                self._progress = None
                self._enabled = False

    def update(self, percent, message):
        if self._progress is not None:
            try:
                self._progress.update(int(percent), message=message)
            except Exception:
                pass

    def close(self):
        if self._progress is not None:
            try:
                self._progress.close()
            except Exception:
                pass
            self._progress = None
            self._enabled = False


class TaskProgress(object):

    def __init__(self, heading, initial_message="", enabled=True):
        self._enabled = enabled is True and HAS_KODI is True
        self._progress = None
        if self._enabled is True:
            try:
                self._progress = xbmcgui.DialogProgress()
                self._progress.create(heading, initial_message)
            except Exception as dialog_fault:
                log_message(f"Dialog: Task progress creation failed: {dialog_fault}", 3)
                self._progress = None
                self._enabled = False

    def update(self, percent, message):
        if self._progress is not None:
            try:
                self._progress.update(int(percent), message)
            except Exception:
                pass

    def iscanceled(self):
        if self._progress is None:
            return False
        try:
            return self._progress.iscanceled()
        except Exception:
            return False

    def close(self):
        if self._progress is not None:
            try:
                self._progress.close()
            except Exception:
                pass
            self._progress = None
            self._enabled = False


def _icon_path(icon_file_name):
    addon_path = kodi_env.ADDON_DIR
    return os.path.join(addon_path, "resources", "media", icon_file_name)


def _notify(title, message, icon_file_name, duration_ms, sound=True):
    if HAS_KODI is False:
        return
    icon_full_path = _icon_path(icon_file_name)
    safe_title = str(title).replace(",", ";")
    safe_message = str(message).replace(",", ";")
    try:
        builtin_cmd = "Notification({}, {}, {}, {})".format(
            safe_title, safe_message, int(duration_ms), icon_full_path
        )
        xbmc.executebuiltin(builtin_cmd)
    except Exception as builtin_fault:
        log_message(f"Dialog: Notification builtin dispatch failure: {builtin_fault}", 3)
        try:
            xbmcgui.Dialog().notification(title, message, icon_full_path, int(duration_ms), sound)
        except Exception as dialog_fault:
            log_message(f"Dialog: Notification dispatch failure: {dialog_fault}", 3)


def clear_failure_dialogs():
    global _failure_dialog_active
    _failure_dialog_active = False


def notify_custom(title, message, icon_file_name, duration_ms, sound=True):
    _notify(title, message, icon_file_name, duration_ms, sound)


def notify_tunnelling(vpn_name, duration_ms=1500):
    title = "[B][COLOR FFFFFF00]▄■ [ TUNNELLING ] ■▄[/COLOR][/B]"
    msg = f" [B]═≡═ [COLOR FFFFFF00]{vpn_name}[/COLOR] ═≡═[/B]\n[B]Syncing kernel routing state...[/B]"
    _notify(title, msg, _ICON_FORCE, duration_ms)


def notify_connected(vpn_name, ip, country, context="normal"):
    if context == "tunnel_checker":
        title = "[B][COLOR FF00FFFF]▄■ [ SYSTEM RESTART ] ■▄[/COLOR][/B]"
    elif context == "service_loop":
        title = "[B][COLOR FF00FFFF]▄■ [ MAPPED CONNECT ] ■▄[/COLOR][/B]"
    elif context == "service_launcher":
        title = "[B][COLOR FF00FFFF]▄■ [ SYSTEM REBOOT ] ■▄[/COLOR][/B]"
    else:
        title = "[B][COLOR FF00FF00]▄■ [ CONNECTED ] ■▄[/COLOR][/B]"
    msg = (
        f" [B]═≡═ [COLOR FF32CD32]{vpn_name}[/COLOR] ═≡═[/B]\n"
        f"[B]IP [COLOR FFFFFF00]{ip}[/COLOR] • [COLOR FFFF8C00]({country})[/COLOR] •[/B]"
    )
    _notify(title, msg, _ICON_CONNECTED, 4500)


def notify_tunnel_restored(vpn_name, country):
    title = "[B][COLOR FF00FFFF]▄■ [ SYSTEM RESTARTED ] ■▄[/COLOR][/B]"
    if country and country != "Unknown":
        msg = (
            f" [B]═≡═ [COLOR FFFFFF00]Tunnel Restored[/COLOR] ═≡═[/B]\n"
            f"[B][COLOR FF32CD32]{vpn_name}[/COLOR] • ({country}) •[/B]"
        )
    else:
        msg = (
            f" [B]═≡═ [COLOR FFFFFF00]Tunnel Restored[/COLOR] ═≡═[/B]\n[B] • "
            f"[COLOR FF32CD32]{vpn_name}[/COLOR] •[/B]"
        )
    _notify(title, msg, _ICON_CONNECTED, 4500)


def notify_connection_failed(vpn_name):
    global _failure_dialog_active
    if _failure_dialog_active is True:
        return
    _failure_dialog_active = True
    title = "[B][COLOR FFFF0000]▄■ [ CONNECTION FAILED ] ■▄[/COLOR][/B]"
    msg = f" [B]═≡═ [COLOR FFFFFF00]{vpn_name}[/COLOR] ═≡═[/B]\n[B]No routing / Tunnel offline[/B]"
    _notify(title, msg, _ICON_ERROR, 5000)


def notify_vpn_failure(error_message):
    title = "[B][COLOR ffff0000]▀■▄ VPN FAILURE ▄■▀[/COLOR][/B]"
    _notify(title, error_message, _ICON_ERROR, 5000)


def notify_disconnected():
    title = "[B][COLOR FFDF00FF]▄■ [ VPN Network ] ■▄[/COLOR][/B]"
    msg = "[B]╠══ [COLOR FFDF00FF][ DISCONNECTED ][/COLOR] ══╣[/B]"
    _notify(title, msg, _ICON_DISCONNECTED, 4500)


def notify_killswitch_not_active():
    title = "[B][COLOR FFFF8C00]▄■ [ KILLSWITCH OFFLINE ] ■▄[/COLOR][/B]"
    msg = "[B]The firewall killswitch could not be engaged.[/B]"
    _notify(title, msg, _ICON_ERROR, 5000)


def show_ok(title, message):
    if HAS_KODI is False:
        return
    try:
        xbmcgui.Dialog().ok(title, message)
    except Exception as dialog_fault:
        log_message(f"Dialog: OK dialog dispatch failure: {dialog_fault}", 3)


def confirm_yes_no(title, message):
    if HAS_KODI is False:
        return False
    try:
        return xbmcgui.Dialog().yesno(title, message)
    except Exception as dialog_fault:
        log_message(f"Dialog: Confirmation dispatch failure: {dialog_fault}", 3)
        return False


def show_text(title, message):
    if HAS_KODI is False:
        return
    try:
        xbmcgui.Dialog().textviewer(title, message)
    except Exception as dialog_fault:
        log_message(f"Dialog: Text viewer dispatch failure: {dialog_fault}", 3)
