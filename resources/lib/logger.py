import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_VER = ADDON.getAddonInfo('version')

def log_message(msg, level=xbmc.LOGINFO):
    xbmc.log(f"{ADDON_ID} v{ADDON_VER}: {msg}", level)

if __name__ == "__main__":
    log_message("--- Logger Utility Started Directly ---")
