""" ./resources/lib/kodi_env.py """
import os

ADDON_ID = "service.wireguard.manager"

try:
    import xbmcaddon
    import xbmcvfs
    HAS_KODI_IMPORTS = True
except ImportError:
    HAS_KODI_IMPORTS = False

_ADDON_INSTANCE = None


def get_addon_instance():
    global _ADDON_INSTANCE
    if _ADDON_INSTANCE is None and HAS_KODI_IMPORTS:
        try:
            _ADDON_INSTANCE = xbmcaddon.Addon(ADDON_ID)
        except Exception:
            _ADDON_INSTANCE = None
    return _ADDON_INSTANCE


def get_addon_dir():
    fallback_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if not HAS_KODI_IMPORTS:
        return fallback_path
    addon_obj = get_addon_instance()
    addon_path_dyn = addon_obj.getAddonInfo("path") if addon_obj else None
    if addon_path_dyn:
        return xbmcvfs.translatePath(addon_path_dyn)
    return fallback_path


def clear_script_globals():
    global _ADDON_INSTANCE
    _ADDON_INSTANCE = None
    import gc
    gc.collect()


ADDON_DIR = get_addon_dir()
