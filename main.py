''' ./main.py '''
import os
import sys

ADDON_DIR = '/storage/.kodi/addons/service.wireguard.manager'
LIB_PATH = os.path.join(ADDON_DIR, 'resources', 'lib')

if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

main_launcher = __import__('resources.lib.main_launcher', fromlist=['main_launcher'])

if __name__ == '__main__':
    main_launcher.run(sys.argv)
