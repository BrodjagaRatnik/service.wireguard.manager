""" ./resources/lib/logger.py """
import kodi_env
import builtins
import os
import sys
import xml.etree.ElementTree as ET

try:
    import xbmc
    HAS_KODI_LOGGING = True
except ImportError:
    HAS_KODI_LOGGING = False


def get_addon_metadata():
    if kodi_env.HAS_KODI_IMPORTS:
        addon_obj = kodi_env.get_addon_instance()
        if addon_obj:
            try:
                return addon_obj.getAddonInfo("id"), addon_obj.getAddonInfo("version")
            except Exception:
                pass

    script_path = os.path.dirname(__file__)
    addon_xml_path = os.path.normpath(os.path.join(script_path, "..", "..", "addon.xml"))
    try:
        tree = ET.parse(addon_xml_path)
        root = tree.getroot()
        return root.get("id"), root.get("version")
    except Exception:
        return "service.wireguard.manager", "unknown"


def log_message(msg, level=1):
    if level is None:
        level = 1

    addon_id, addon_ver = get_addon_metadata()
    formatted_msg = f"{addon_id} v{addon_ver}: {msg}"

    if HAS_KODI_LOGGING and kodi_env.HAS_KODI_IMPORTS:
        xbmc.log(formatted_msg, level)
    else:
        is_debug_active = False
        script_path = os.path.dirname(__file__)
        gui_xml = os.path.normpath(
            os.path.join(script_path, "..", "..", "..", "..", "userdata", "guisettings.xml")
        )
        try:
            if os.path.exists(gui_xml):
                tree = ET.parse(gui_xml)
                setting = tree.find(".//setting[@id='core.logging.enabledebug']")
                if setting is not None and setting.text:
                    is_debug_active = setting.text.lower() == "true"
        except Exception:
            pass

        if level == 0 and not is_debug_active:
            kodi_env.clear_script_globals()
            return

        lvl_name = {0: "Debug", 1: "Info", 2: "Warning", 3: "Error"}.get(level, "Info")
        console_msg = f"[{lvl_name}] {formatted_msg}\n"

        if level in (2, 3):
            sys.stderr.write(console_msg)
            sys.stderr.flush()
        else:
            sys.stdout.write(console_msg)
            sys.stdout.flush()

    kodi_env.clear_script_globals()


if HAS_KODI_LOGGING and kodi_env.HAS_KODI_IMPORTS:
    builtins.log_event = lambda msg, lvl=0: xbmc.log(
        f"service.wireguard.manager fallback: {msg}",
        level=xbmc.LOGERROR if lvl >= 2 else xbmc.LOGINFO
    )
else:
    builtins.log_event = lambda msg, lvl=0: (
        sys.stderr.write(f"service.wireguard.manager fallback: {msg}\n") if lvl >= 2
        else sys.stdout.write(f"service.wireguard.manager fallback: {msg}\n")
    )

if not HAS_KODI_LOGGING or not kodi_env.HAS_KODI_IMPORTS:
    import types

    mock_xbmc = types.ModuleType("xbmc")

    mock_xbmc.LOGDEBUG = 0
    mock_xbmc.LOGINFO = 1
    mock_xbmc.LOGWARNING = 2
    mock_xbmc.LOGERROR = 3

    mock_xbmc.log = log_message

    mock_xbmc.getCondVisibility = lambda cond: False
    mock_xbmc.executebuiltin = lambda cmd: sys.stderr.write(f"EXEC: {cmd}\n") or sys.stderr.flush()
    mock_xbmc.getInfoLabel = lambda infotag: ""

    sys.modules["xbmc"] = mock_xbmc
