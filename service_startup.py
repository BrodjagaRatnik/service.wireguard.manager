""" ./service_startup.py """
import os
import sys


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))
    import kodi_env
    try:
        __import__("service_launcher").start()
    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    main()
