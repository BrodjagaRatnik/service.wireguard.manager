""" ./main.py """
import sys


def main():
    lib_path = "/storage/.kodi/addons/service.wireguard.manager/resources/lib"
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)
    import kodi_env
    try:
        __import__("main_launcher").run(sys.argv)
    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    main()
