''' .resources/lib/providers/custom.py '''
import os
import sys

try:
    import xbmc
    HAS_KODI = True
except ImportError:
    HAS_KODI = False


def update(source_path, config_dir):
    try:
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

        """ Clean the name (e.g., 'belgium.conf' -> 'Belgium') """
        base = os.path.basename(source_path)
        clean_name = base.lower().replace('.config', '').replace('.conf', '').replace('custom_', '').capitalize()
        dest_name = f"custom_{clean_name.lower()}.config"
        dest_path = os.path.join(config_dir, dest_name)

        with open(source_path, 'r') as f:
            lines = f.readlines()

        new_lines = []
        name_found = False
        for line in lines:
            if line.strip().startswith('Name ='):
                new_lines.append(f"Name = Custom_{clean_name}\n")
                name_found = True
            else:
                new_lines.append(line)

        if not name_found:
            new_lines.insert(1, f"Name = Custom_{clean_name}\n")

        with open(dest_path, 'w') as f:
            f.writelines(new_lines)

        os.chmod(dest_path, 0o600)

        msg = f"Custom Provider: Imported {clean_name} and updated internal Name."
        if HAS_KODI:
            xbmc.log(msg, xbmc.LOGINFO)
        else:
            sys.stdout.write(f"{msg}\n")
            sys.stdout.flush()

        return True

    except Exception as e:
        err_msg = f"Custom Provider Error: {str(e)}"
        if HAS_KODI:
            xbmc.log(err_msg, xbmc.LOGERROR)
        else:
            sys.stderr.write(f"{err_msg}\n")
            sys.stderr.flush()
        return False
