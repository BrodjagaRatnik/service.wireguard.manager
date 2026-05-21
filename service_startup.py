''' ./service_startup.py '''
import os
import sys

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

service_launcher = __import__('resources.lib.service_launcher', fromlist=['service_launcher'])

if __name__ == '__main__':
    service_launcher.start()
