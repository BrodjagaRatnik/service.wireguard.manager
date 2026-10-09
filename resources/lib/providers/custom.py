''' .resources/lib/providers/custom.py '''
import os
import sys

try:
    import xbmc
    HAS_KODI = True
except ImportError:
    HAS_KODI = False


def _dispatch_log(message, error_level):
    if HAS_KODI:
        xbmc.log(message, error_level)
    else:
        stream = sys.stderr if error_level == xbmc.LOGERROR else sys.stdout
        stream.write(f"{message}\n")
        stream.flush()


def _is_wireguard_config(file_path):
    try:
        with open(file_path, 'r') as probe:
            head_block = probe.read(4096)
        lowered_head = head_block.lower()
        return '[interface]' in lowered_head or '[provider_wireguard]' in lowered_head
    except Exception:
        return False


def discover_configs(source_dir):
    discovered = []
    try:
        for entry in sorted(os.listdir(source_dir)):
            if not entry.lower().endswith(('.conf', '.config')):
                continue
            candidate_path = os.path.join(source_dir, entry)
            if not os.path.isfile(candidate_path):
                continue
            if _is_wireguard_config(candidate_path):
                discovered.append(candidate_path)
    except Exception as discovery_fault:
        _dispatch_log(f"Custom Provider Error: {discovery_fault}", xbmc.LOGERROR)
    return discovered


def _import_file(source_path, config_dir):
    try:
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
                new_lines.append(line)
                name_found = True
            else:
                new_lines.append(line)

        if not name_found:
            if clean_name.lower().startswith('custom'):
                new_lines.insert(1, f"Name = {clean_name}\n")
            else:
                new_lines.insert(1, f"Name = Custom_{clean_name}\n")

        with open(dest_path, 'w') as f:
            f.writelines(new_lines)

        os.chmod(dest_path, 0o600)

        _dispatch_log(f"Custom Provider: Imported {clean_name} and updated internal Name.", xbmc.LOGINFO)
        return True, clean_name

    except Exception as import_fault:
        _dispatch_log(f"Custom Provider Error: {import_fault}", xbmc.LOGERROR)
        return False, None


def update_directory(source_dir, config_dir, progress_callback=None):
    summary = {"total": 0, "imported": 0, "skipped": 0}
    if not os.path.isdir(source_dir):
        return summary

    candidates = [entry for entry in sorted(os.listdir(source_dir))
                  if entry.lower().endswith(('.conf', '.config'))]
    valid_files = discover_configs(source_dir)
    summary["total"] = len(candidates)
    summary["skipped"] = max(len(candidates) - len(valid_files), 0)

    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)

    for position, file_path in enumerate(valid_files, start=1):
        stem = os.path.basename(file_path)
        progress_label = stem.lower().replace('.config', '').replace('.conf', '').replace('custom_', '').capitalize()
        if progress_callback is not None:
            try:
                progress_callback(position, len(valid_files), progress_label)
            except Exception:
                pass
        success, _ = _import_file(file_path, config_dir)
        if success is True:
            summary["imported"] += 1
        else:
            summary["skipped"] += 1

    return summary


def update(source_path, config_dir):
    if os.path.isdir(source_path):
        batch_summary = update_directory(source_path, config_dir)
        return batch_summary["imported"] > 0

    success, _ = _import_file(source_path, config_dir)
    return success
