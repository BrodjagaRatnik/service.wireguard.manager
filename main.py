""" ./main.py """
import os
import sys


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))
    import kodi_env
    try:
        __import__("main_launcher").run(sys.argv)
    finally:
        kodi_env.clear_script_globals()


if __name__ == "__main__":
    main()
