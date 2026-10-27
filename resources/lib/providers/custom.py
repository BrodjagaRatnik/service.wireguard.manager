""" LibreELEC .resources/lib/providers/custom.py """
import os
import sys

try:
    import xbmc
    HAS_KODI = True
except ImportError:
    HAS_KODI = False


def _dispatch_log(message, severity):
    if HAS_KODI:
        resolved_level = getattr(xbmc, severity, xbmc.LOGINFO)
        xbmc.log(message, resolved_level)
    else:
        stream = sys.stderr if 'ERROR' in severity else sys.stdout
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


def _is_standard_layout(raw_lines):
    for raw_line in raw_lines:
        stripped = raw_line.strip().lower()
        if stripped == '[provider_wireguard]':
            return False
        if stripped == '[interface]' or stripped == '[peer]':
            return True
    return False


def _split_endpoint(endpoint_value):
    candidate = endpoint_value.strip()
    if candidate.startswith('[') and ']' in candidate:
        host_part, separator, port_part = candidate.rpartition(']:')
        if separator:
            return host_part.lstrip('['), port_part
        return candidate.strip('[]'), ''
    host_part, separator, port_part = candidate.rpartition(':')
    if separator and host_part.count(':') == 0:
        return host_part, port_part
    return candidate, ''


def _collect_section_values(raw_lines):
    interface_values = {}
    peer_values = {}
    current_section = None
    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith(';'):
            continue
        if stripped.startswith('[') and stripped.endswith(']'):
            current_section = stripped[1:-1].strip().lower()
            continue
        if '=' not in stripped:
            continue
        key, _, value = stripped.partition('=')
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        if current_section == 'interface':
            interface_values.setdefault(key, value)
        elif current_section == 'peer':
            peer_values.setdefault(key, value)
    return interface_values, peer_values


CONNMAN_DEFAULT_LISTEN_PORT = '51820'
CONNMAN_DEFAULT_MTU = '1420'


def _convert_wireguard_standard(raw_lines):
    interface_values, peer_values = _collect_section_values(raw_lines)
    host_address, endpoint_port = _split_endpoint(peer_values.get('Endpoint', ''))
    endpoint_port = endpoint_port or CONNMAN_DEFAULT_LISTEN_PORT
    ordered_fields = [
        ('Host', host_address),
        ('WireGuard.Address', interface_values.get('Address', '')),
        ('WireGuard.ListenPort', interface_values.get('ListenPort', CONNMAN_DEFAULT_LISTEN_PORT)),
        ('WireGuard.MTU', interface_values.get('MTU', CONNMAN_DEFAULT_MTU)),
        ('WireGuard.PrivateKey', interface_values.get('PrivateKey', '')),
        ('WireGuard.PublicKey', peer_values.get('PublicKey', '')),
        ('WireGuard.DNS', interface_values.get('DNS', '')),
        ('WireGuard.AllowedIPs', peer_values.get('AllowedIPs', '')),
        ('WireGuard.EndpointPort', endpoint_port),
        ('WireGuard.PersistentKeepalive', peer_values.get('PersistentKeepalive', '')),
    ]
    converted = ['[provider_wireguard]\n', 'Type = WireGuard\n']
    for field_name, field_value in ordered_fields:
        if field_value:
            converted.append(f"{field_name} = {field_value}\n")
    return converted


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
        _dispatch_log(f"Custom Provider Error: {discovery_fault}", "LOGERROR")
    return discovered


def _import_file(source_path, config_dir):
    try:
        base = os.path.basename(source_path)
        clean_name = base.lower().replace('.config', '').replace('.conf', '').replace('custom_', '').capitalize()
        dest_name = f"custom_{clean_name.lower()}.config"
        dest_path = os.path.join(config_dir, dest_name)

        with open(source_path, 'r') as f:
            lines = f.readlines()

        if _is_standard_layout(lines):
            lines = _convert_wireguard_standard(lines)
            _dispatch_log(f"Custom Provider: Converted standard WireGuard layout to ConnMan for {clean_name}.",
                          "LOGINFO")

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

        _dispatch_log(f"Custom Provider: Imported {clean_name} and updated internal Name.", "LOGINFO")
        return True, clean_name

    except Exception as import_fault:
        _dispatch_log(f"Custom Provider Error: {import_fault}", "LOGERROR")
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
