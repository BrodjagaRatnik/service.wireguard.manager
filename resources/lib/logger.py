import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime

def get_version_from_xml():
    try:
        xml_path = '/storage/.kodi/addons/service.wireguard.manager/addon.xml'
        if os.path.exists(xml_path):
            tree = ET.parse(xml_path)
            return tree.getroot().get('version')
    except: pass
    return "Unknown"

try:
    import xbmc
    import xbmcaddon
    ADDON = xbmcaddon.Addon('service.wireguard.manager')
    ADDON_ID = ADDON.getAddonInfo('id')
    ADDON_VER = ADDON.getAddonInfo('version')
    KODI_MODE = True
except:
    KODI_MODE = False
    ADDON_ID = "service.wireguard.manager"
    ADDON_VER = get_version_from_xml()

def log_message(msg, level=None):
    formatted_msg = f"{ADDON_ID} v{ADDON_VER}: {msg}"
    
    if KODI_MODE:
        import xbmc
        xbmc.log(formatted_msg, level if level is not None else 1)
    else:
        print(formatted_msg)
        sys.stdout.flush()

        try:
            log_path = '/storage/.kodi/temp/kodi.log'
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            pid = os.getpid()
            
            if level == 2:
                lvl_line = "    warning <general>:"
            elif level == 3:
                lvl_line = "    error <general>:"
            else:
                lvl_line = "    info <general>:"

            log_line = f"{now} T:{pid}{lvl_line} {formatted_msg}\n"
            
            with open(log_path, 'a') as f:
                f.write(log_line)
        except:
            pass
