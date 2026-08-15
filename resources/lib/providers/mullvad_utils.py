""" From: https://github.com/mullvad/wg-tools .resources/lib/providers/mullvad_utils.py """
import collections
import ipaddress
import subprocess
import sys
from logger import log_message
from providers.mullvad import Mullvad
from state_manager import get_file_path

MullvadArgs = collections.namedtuple("MullvadArgs", [
    "account_number", "settings_file", "output_dir", "wg_relay_port",
    "wg_dns", "filter", "wg_active", "mtu", "wg_multihop_server",
    "wg_owned", "wg_min_network_port_speed"
])


def generate_mullvad_configs(account_id, country_filter, mtu_setting=1380, multihop=None, owned=False, speed=0):
    output_dir = "/storage/.config/wireguard"
    settings_file = get_file_path("mullvad_settings")

    if not settings_file:
        log_message("Unable to resolve centralized storage path for Mullvad state configuration registries", 3)
        sys.exit(1)

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
    except Exception as e:
        log_message(f"Mullvad configuration generation pipeline crashed: {e}", 3)
        sys.exit(1)


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
