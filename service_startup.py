import xbmc
import xbmcaddon
import os
import sys

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
LIB_PATH = os.path.join(ADDON_PATH, 'resources', 'lib')
sys.path.append(LIB_PATH)

from vpn_core import install_service, check_for_updates
from setup_helper import ensure_setup

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    for _ in range(30):
        if monitor.waitForAbort(1): break
        if xbmc.getCondVisibility("Window.IsVisible(home)"):
            break

    MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
    SERVICE_NAME = "vpn-watchdog.service"
    SOURCE_SERVICE = os.path.join(ADDON_PATH, 'resources', 'data', SERVICE_NAME)
    DEST_SERVICE = '/storage/.config/system.d/' + SERVICE_NAME

    try:
        ensure_setup(ADDON_PATH, MEDIA_PATH)
        install_service(SOURCE_SERVICE, DEST_SERVICE, SERVICE_NAME, MEDIA_PATH)
        check_for_updates(MEDIA_PATH)
    except Exception as e:
        xbmc.log(f"[service.wireguard.manager] Startup Error: {e}", xbmc.LOGERROR)
