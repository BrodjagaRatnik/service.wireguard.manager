""" From: https://github.com/mullvad/wg-tools .resources/lib/providers/mullvad_utils.py """
import collections
import ipaddress
import os
import subprocess
import sys
from logger import log_message
from providers.mullvad import Mullvad, MullvadPipelineFailure
from state_manager import get_file_path, CONFIG_DIR

MullvadArgs = collections.namedtuple("MullvadArgs", [
    "account_number", "settings_file", "output_dir", "wg_relay_port",
    "wg_dns", "filter", "wg_active", "mtu", "wg_multihop_server",
    "wg_owned", "wg_min_network_port_speed"
])


def _profile_host_map():
    hosts = {}
    try:
        for file_name in sorted(os.listdir(CONFIG_DIR)):
            if not file_name.startswith("mullvad_") or not file_name.endswith(".config"):
                continue
            stem = file_name[:-len(".config")]
            host_value = None
            try:
                with open(os.path.join(CONFIG_DIR, file_name), "r", encoding="utf-8") as conf_reader:
                    for line in conf_reader:
                        if line.startswith("Host ="):
                            host_value = line.split("=", 1)[-1].strip()
                            break
            except Exception:
                continue
            if host_value:
                hosts[stem] = host_value
    except Exception as scan_fault:
        log_message(f"Mullvad Utils: Profile host map scan failure: {scan_fault}", 3)
    return hosts


def _sid_to_host_ip(candidate):
    base = str(candidate).strip().lower()
    if not base.startswith("vpn_"):
        return None
    octets = base[4:].split("_")
    if len(octets) == 4 and all(o.isdigit() for o in octets):
        return ".".join(octets)
    return None


def find_siblings_by_country(profile_id):
    base = str(profile_id).strip().lower().replace(".config", "").replace(".conf", "")
    host_map = _profile_host_map()
    origin_stem = None

    if base.startswith("mullvad_"):
        origin_stem = base if base in host_map else None
    if origin_stem is None:
        host_ip = _sid_to_host_ip(base)
        if host_ip:
            for stem, host_value in host_map.items():
                if host_value == host_ip:
                    origin_stem = stem
                    break

    if origin_stem is None:
        return []

    country_code = origin_stem[len("mullvad_"):].split("-")[0]
    if not country_code:
        return []

    sibling_sids = []
    for stem, host_value in host_map.items():
        if stem.startswith(f"mullvad_{country_code}-") and stem != origin_stem:
            sibling_sids.append("vpn_" + host_value.replace(".", "_"))
    return sibling_sids


def generate_mullvad_configs(account_id, country_filter, mtu_setting=1380, multihop=None, owned=False, speed=0):
    output_dir = CONFIG_DIR
    settings_file = get_file_path("mullvad_settings")

    if not settings_file:
        log_message("Unable to resolve centralized storage path for Mullvad state configuration registries", 3)
        raise MullvadPipelineFailure("Centralized Mullvad settings registry path could not be resolved")

    dns_servers = [
        ipaddress.ip_address("10.64.0.1")
    ]

    args = MullvadArgs(
        account_number=str(account_id),
        settings_file=settings_file,
        output_dir=output_dir,
        wg_relay_port=51820,
        wg_dns=dns_servers,
        filter=str(country_filter),
        wg_active=True,
        mtu=int(mtu_setting),
        wg_multihop_server=multihop,
        wg_owned=bool(owned),
        wg_min_network_port_speed=int(speed)
    )

    try:
        mullvad = Mullvad(args)
        mullvad.run()
    except SystemExit as exit_signal:
        log_err = f"Mullvad pipeline exit request intercepted and converted to controlled failure: {exit_signal.code}"
        log_message(log_err, 2)
        raise MullvadPipelineFailure("Mullvad generation pipeline terminated before completion") from exit_signal
    except Exception as e:
        log_message(f"Mullvad configuration generation pipeline crashed: {e}", 3)
        raise MullvadPipelineFailure(f"Mullvad configuration generation pipeline failed: {e}") from e


def generate_publickey(privatekey: str) -> str:
    try:
        pk_bytes = privatekey.encode("utf-8")
        out = subprocess.check_output(["wg", "pubkey"], input=pk_bytes).decode().strip()
        return out
    except Exception as e:
        log_message(f"Failed to derive public key from private key material: {e}", 3)
        sys.exit(1)


def generate_privatekey() -> str:
    try:
        out = subprocess.check_output(["wg", "genkey"]).decode().strip()
        return out
    except Exception as e:
        log_message(f"Failed to generate secure Curve25519 key pair: {e}", 3)
        sys.exit(1)
