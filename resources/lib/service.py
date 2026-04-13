import time, subprocess, os, sys
try:
    import xbmc, xbmcaddon
    ADDON = xbmcaddon.Addon('service.wireguard.manager')
    sys.path.append(os.path.join(ADDON.getAddonInfo('path'), 'resources', 'lib'))
    from logger import log_message
    KODI_MODE = True
except: KODI_MODE = False

SAVED_GATEWAY = None

def get_default_gateway():
    global SAVED_GATEWAY
    try:
        out = subprocess.check_output(["ip", "-4", "route", "show", "default"], text=True)
        if "default" in out:
            parts = out.split()
            SAVED_GATEWAY = parts[parts.index("via") + 1]
            return SAVED_GATEWAY
    except: pass
    return SAVED_GATEWAY

def watchdog_logic():
    try:
        routes = subprocess.check_output(["ip", "route"], text=True)
        if "wg0" in routes: return
        if "default" not in routes and SAVED_GATEWAY:
            subprocess.run(["route", "add", "default", "gw", SAVED_GATEWAY, "eth0"], check=False)
    except: pass

if __name__ == "__main__":
    while SAVED_GATEWAY is None:
        get_default_gateway()
        time.sleep(2)
    while True:
        watchdog_logic()
        time.sleep(5)
