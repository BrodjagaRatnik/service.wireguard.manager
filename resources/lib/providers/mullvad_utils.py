""" From: https://github.com/mullvad/wg-tools .resources/lib/providers/mullvad_utils.py """
import collections
import configparser
import ipaddress
import os
import pathlib
import subprocess
import sys
from logger import log_message
from providers.mullvad import Mullvad

MullvadArgs = collections.namedtuple("MullvadArgs", [
    "account_number", "settings_file", "output_dir", "wg_relay_port",
    "wg_dns", "filter", "wg_active", "mtu", "wg_multihop_server",
    "wg_owned", "wg_min_network_port_speed"
])


def generate_mullvad_configs(account_id, country_filter, mtu_setting=1380, multihop=None, owned=False, speed=0):
    from state_manager import PROFILE_DIR
    output_dir = os.path.join(PROFILE_DIR, "mullvad_configs", "")
    settings_file = os.path.join(PROFILE_DIR, "mullvad_settings.ini")

    dns_servers = [
        ipaddress.ip_address("10.64.0.1"),
        ipaddress.ip_address("100.64.0.7")
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


def convert_to_connman_configs():
    from state_manager import PROFILE_DIR
    input_dir = pathlib.Path(os.path.join(PROFILE_DIR, "mullvad_configs")).expanduser()
    output_dir = pathlib.Path("/storage/.config/wireguard")

    try:
        output_dir.mkdir(exist_ok=True, parents=True)
    except Exception as e:
        log_message(f"Failed to create target ConnMan platform configuration directory {output_dir}: {e}", 3)
        sys.exit(1)

    if not input_dir.exists():
        log_message(f"Target extraction runtime interrupted: missing source file system entities at {input_dir}", 3)
        sys.exit(1)

    for conf_file in input_dir.glob("*.conf"):
        try:
            src_config = configparser.ConfigParser(delimiters=("=",))
            src_config.optionxform = str
            src_config.read(conf_file)

            private_key = src_config.get("Interface", "privateKey")
            address = src_config.get("Interface", "address")
            mtu = src_config.get("Interface", "MTU")
            dns = src_config.get("Interface", "dns")

            public_key = src_config.get("Peer", "publickey")
            allowed_ips = src_config.get("Peer", "allowedips")
            endpoint = src_config.get("Peer", "endpoint")

            host, port = endpoint.rsplit(":", 1)
            dest_filename = f"mullvad_{conf_file.stem}.config"
            dest_path = output_dir / dest_filename

            dest_lines = [
                "[provider_wireguard]",
                "Type = WireGuard",
                f"Name = Mullvad_{conf_file.stem}",
                f"Host = {host}",
                f"WireGuard.Address = {address}/32",
                "WireGuard.ListenPort = 51820",
                f"WireGuard.MTU = {mtu}",
                f"WireGuard.PrivateKey = {private_key}",
                f"WireGuard.PublicKey = {public_key}",
                f"WireGuard.DNS = {dns}",
                f"WireGuard.AllowedIPs = {allowed_ips}",
                f"WireGuard.EndpointPort = {port}",
                "WireGuard.PersistentKeepalive = 25\n"
            ]

            dest_path.touch(mode=0o600, exist_ok=True)
            with dest_path.open("w") as target_file:
                target_file.write("\n".join(dest_lines))
        except (configparser.NoOptionError, configparser.NoSectionError) as e:
            log_message(f"Skipping corrupt or malformed source wireguard config file {conf_file.name}: {e}", 2)
        except Exception as e:
            log_message(f"Failed parsing or writing ConnMan profile transformation asset for node {conf_file.name}: {e}", 3)
