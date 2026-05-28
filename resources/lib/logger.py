''' ./resources/lib/logger.py '''
import builtins
import os
import sys
import xml.etree.ElementTree as ET

try:
    import xbmc
    import xbmcaddon
    _ADDON = xbmcaddon.Addon('service.wireguard.manager')
    ADDON_ID = _ADDON.getAddonInfo('id')
    ADDON_VER = _ADDON.getAddonInfo('version')
    HAS_KODI = True
except Exception:
    HAS_KODI = False

    try:
        _addon_xml_path = '/storage/.kodi/addons/service.wireguard.manager/addon.xml'
        _tree = ET.parse(_addon_xml_path)
        _root = _tree.getroot()
        ADDON_ID = _root.get('id')
        ADDON_VER = _root.get('version')
    except Exception:
        ADDON_ID = 'service.wireguard.manager'
        ADDON_VER = 'unknown'


def log_message(msg, level=1):
    if level is None:
        level = 1

    formatted_msg = f"{ADDON_ID} v{ADDON_VER}: {msg}"

    if HAS_KODI:
        xbmc.log(formatted_msg, level)
    else:
        _is_debug_active = False
        try:
            _gui_xml = '/storage/.kodi/userdata/guisettings.xml'
            if os.path.exists(_gui_xml):
                _tree = ET.parse(_gui_xml)
                _setting = _tree.find(".//setting[@id='core.logging.enabledebug']")
                if _setting is not None and _setting.text:
                    _is_debug_active = _setting.text.lower() == 'true'
        except Exception:
            pass

        if level == 0 and not _is_debug_active:
            return

        lvl_name = {0: "Debug", 1: "Info", 2: "Warning", 3: "Error"}.get(level, "Info")
        console_msg = f"[{lvl_name}] {formatted_msg}\n"

        if level in (2, 3):
            sys.stderr.write(console_msg)
            sys.stderr.flush()
        else:
            sys.stdout.write(console_msg)
            sys.stdout.flush()


if HAS_KODI:
    builtins.log_event = lambda msg, lvl=0: xbmc.log(
        f"service.wireguard.manager fallback: {msg}",
        level=xbmc.LOGERROR if lvl >= 2 else xbmc.LOGINFO
    )
else:
    builtins.log_event = lambda msg, lvl=0: (
        sys.stderr.write(f"service.wireguard.manager fallback: {msg}\n") if lvl >= 2
        else sys.stdout.write(f"service.wireguard.manager fallback: {msg}\n")
    )

if not HAS_KODI:
    import types

    mock_xbmc = types.ModuleType('xbmc')

    mock_xbmc.LOGDEBUG = 0
    mock_xbmc.LOGINFO = 1
    mock_xbmc.LOGWARNING = 2
    mock_xbmc.LOGERROR = 3

    mock_xbmc.log = log_message

    mock_xbmc.getCondVisibility = lambda cond: False
    mock_xbmc.executebuiltin = lambda cmd: sys.stderr.write(f"EXEC: {cmd}\n") or sys.stderr.flush()
    mock_xbmc.getInfoLabel = lambda infotag: ""

    sys.modules['xbmc'] = mock_xbmc
