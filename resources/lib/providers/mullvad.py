""" From: https://github.com/mullvad/wg-tools

HOST = 'https://api.mullvad.net'

.resources/lib/providers/mullvad.py """
import configparser
import functools
import gzip
import json
import pathlib
import sys
import urllib.request

from logger import log_message


class MullvadApi:
    HOST = 'https://api.mullvad.net'

    def __init__(self, account_number):
        self.account_number = account_number

    def new_device(self, public_key):
        body = {
            "pubkey": public_key,
            "hijack_dns": False,
        }
        return self._api(f"{MullvadApi.HOST}/accounts/v1/devices", body)

    def list_devices(self):
        return self._api(f"{MullvadApi.HOST}/accounts/v1/devices")

    @functools.cached_property
    def web_token(self) -> str:
        body = {
            "account_number": self.account_number,
        }
        req = urllib.request.Request(f"{MullvadApi.HOST}/auth/v1/webtoken")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, json.dumps(body).encode()) as response:
                data = json.load(response)
            return data["access_token"]
        except urllib.error.HTTPError as e:
            if e.code == 401:
                log_message(
                    f"Mullvad API authentication token request rejected: Invalid account "
                    f"number {self.account_number}", 3
                )
            else:
                log_message(f"Mullvad API token request failed with HTTP Error {e.code}", 3)
            raise
        except Exception as e:
            log_message(f"Unexpected connection error while fetching Mullvad web token: {e}", 3)
            raise

    def _api(self, url, body=None):
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.web_token}")
            req.add_header("Accept-Encoding", "gzip")

            if body:
                req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, data=json.dumps(body).encode() if body else None) as response:
                return self.get_response(response)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                log_message(f"Mullvad API operational constraint reached: {e.reason} (Device limit or key clash likely)", 2)
            else:
                log_message(f"Mullvad API communication failure on {url} with HTTP Error {e.code}", 3)
            raise
        except Exception as e:
            log_message(f"Network backend subsystem failure accessing Mullvad endpoint {url}: {e}", 3)
            raise

    @staticmethod
    def default_dns_servers() -> str:
        return "10.64.0.1,100.64.0.7"

    @functools.cache
    @staticmethod
    def all_wireguard_relays():
        req = urllib.request.Request(f"{MullvadApi.HOST}/www/relays/all")
        req.add_header("Accept-Encoding", "gzip")
        try:
            with urllib.request.urlopen(req) as response:
                data = MullvadApi.get_response(response)
            return [i for i in data if i["type"] == "wireguard"]
        except Exception as e:
            log_message(f"Failed to fetch global WireGuard infrastructure lists from Mullvad servers: {e}", 3)
            raise

    @staticmethod
    def wireguard_relays(**kwargs):
        try:
            relays = MullvadApi.all_wireguard_relays()
        except Exception:
            return []

        location_prefix = kwargs.get("location_prefix", "")
        if location_prefix:
            relays = [r for r in relays if r["hostname"].startswith(location_prefix)]

        if kwargs.get("active", False):
            relays = [r for r in relays if r["active"]]

        if kwargs.get("owned", False):
            relays = [r for r in relays if r["owned"]]

        min_speed = kwargs.get("min_network_port_speed", 0)
        relays = [r for r in relays if r["network_port_speed"] >= min_speed]

        if not relays:
            log_message("Mullvad relay filter query executed successfully but yielded empty results", 2)

        return relays

    @staticmethod
    def get_response(response):
        try:
            if response.headers.get("Content-Encoding") == "gzip":
                return json.loads(gzip.decompress(response.read()))
            else:
                return json.load(response)
        except Exception as e:
            log_message(f"Failed to decompress or parse JSON payload from API server: {e}", 3)
            raise


class MullvadConfig:
    def __init__(self, output_dir, wg_dns, wg_relay_port, mtu):
        self.output_dir = output_dir
        self.wg_dns = wg_dns
        self.wg_relay_port = wg_relay_port
        self.mtu = mtu

    def create_wg_configs(self, relays, device, privatekey, multihop_server) -> None:
        try:
            output_dir = pathlib.Path(self.output_dir).expanduser()
            output_dir.mkdir(exist_ok=True, parents=True)
        except Exception as e:
            log_message(f"Failed to instantiate target configuration directory path structural entities: {e}", 3)
            raise

        config = configparser.ConfigParser()
        config.add_section("Interface")
        config.set("Interface", "#device", device["name"])
        config.set("Interface", "privateKey", privatekey)
        config.set("Interface", "address", device["ipv4_address"])
        config.set("Interface", "MTU", str(self.mtu))

        if self.wg_dns:
            config.set("Interface", "dns", ",".join([str(x) for x in self.wg_dns]))
        else:
            config.set("Interface", "dns", MullvadApi.default_dns_servers())
        config.add_section("Peer")

        for relay in relays:
            try:
                self.create_wg_config(config, relay, multihop_server)
            except Exception as e:
                log_message(
                    f"Skipping corrupt configuration block rendering pass for target host "
                    f"{relay.get('hostname')}: {e}", 2
                )

    def create_wg_config(self, config, relay, multihop_server=None) -> None:
        output_dir = pathlib.Path(self.output_dir).expanduser()
        hostname = relay["hostname"]
        if multihop_server:
            server_name = multihop_server["hostname"]
            file_path = pathlib.Path.joinpath(output_dir, f"{hostname}-via-{server_name}.conf")
        else:
            file_path = pathlib.Path.joinpath(output_dir, f"{hostname}.conf")

        try:
            file_path.touch(mode=0o600, exist_ok=True)
        except Exception as e:
            log_message(f"Permission fault while reserving lock descriptors for path {file_path}: {e}", 3)
            raise

        if multihop_server:
            remote_server = multihop_server
            remote_port = relay["multihop_port"]
        else:
            remote_server = relay
            remote_port = self.wg_relay_port

        wg_relay_address = remote_server["ipv4_addr_in"]

        try:
            with file_path.open("w") as _file:
                config.set("Peer", "#owned", str(relay["owned"]))
                config.set("Peer", "#provider", relay["provider"])
                config.set("Peer", "publickey", relay["pubkey"])
                config.set("Peer", "allowedips", "0.0.0.0/0, ::/0")
                config.set("Peer", "endpoint", f"{wg_relay_address}:{remote_port}")
                config.write(_file)
        except Exception as e:
            log_message(
                f"Failed writing localized WireGuard configuration descriptors to target "
                f"file system node {file_path}: {e}", 3
            )
            raise


class Mullvad:
    def __init__(self, args):
        self.mullvad_api = MullvadApi(args.account_number)
        self.mullvad_config = MullvadConfig(args.output_dir, args.wg_dns, args.wg_relay_port, args.mtu)

        self._settings_file = args.settings_file
        self._wg_multihop_server = args.wg_multihop_server
        self._wg_relays_filter = {
            "location_prefix": args.filter,
            "active": args.wg_active,
            "owned": args.wg_owned,
            "min_network_port_speed": args.wg_min_network_port_speed,
        }

        self._config = configparser.ConfigParser()
        self._settings_file = pathlib.Path(self._settings_file).expanduser()

    def run(self):
        try:
            multihop_server = self.get_multihop_server()
            relays = self.get_relays()
            private_key, public_key = self.get_key_pair()
            device = self.get_device(public_key) or self.create_device(public_key)
            if device:
                self.mullvad_config.create_wg_configs(relays, device, private_key, multihop_server)
        except Exception as e:
            log_message(f"Execution runtime failed within the main processing execution block: {e}", 3)
            sys.exit(1)

    def get_privatekey(self) -> str:
        self._config.read(self._settings_file)
        try:
            return self._config.get("Interface", "privatekey")
        except (configparser.NoOptionError, configparser.NoSectionError) as e:
            log_message(
                f"Required configuration parameter 'privatekey' missing from section 'Interface' "
                f"inside {self._settings_file}: {e}", 3
            )
            sys.exit(1)

    def save_privatekey(self, privatekey) -> bool:
        try:
            self._settings_file.parent.mkdir(parents=True, exist_ok=True)
            self._settings_file.touch(mode=0o600, exist_ok=True)
            with self._settings_file.open("w") as _file:
                self._config.add_section("Interface")
                self._config.set("Interface", "privatekey", privatekey)
                self._config.write(_file)
            return True
        except Exception as e:
            log_message(
                f"Failed to record state variables onto permanent local platform registers "
                f"{self._settings_file}: {e}", 3
            )
            raise

    def get_device(self, publickey):
        try:
            for device in self.mullvad_api.list_devices():
                if publickey == device["pubkey"]:
                    return device
            return None
        except urllib.error.HTTPError as e:
            self.handle_mullvad_api_error(e)

    def create_device(self, publickey):
        try:
            response = self.mullvad_api.new_device(publickey)
            return response
        except urllib.error.HTTPError as e:
            self.handle_mullvad_api_error(e)

    def get_key_pair(self):
        import providers.mullvad_utils as local_utils
        if self._settings_file.is_file():
            private_key = self.get_privatekey()
        else:
            private_key = local_utils.generate_privatekey()
            self.save_privatekey(private_key)

        public_key = local_utils.generate_publickey(private_key)
        return (private_key, public_key)

    def get_multihop_server(self):
        if not self._wg_multihop_server or str(self._wg_multihop_server).strip() == "":
            return None

        try:
            multihop_servers = [
                r for r in MullvadApi.all_wireguard_relays()
                if r["hostname"].startswith(self._wg_multihop_server)
            ]
        except Exception:
            log_message("Aborting multihop node assessment: Could not acquire downstream server directories", 3)
            sys.exit(1)

        if len(multihop_servers) == 1:
            return multihop_servers
        else:
            log_message(
                f"Multihop node selection conflict: Expected exactly 1 match for prefix '{self._wg_multihop_server}', "
                f"found {len(multihop_servers)} matching profiles", 3
            )
            sys.exit(1)

    def get_relays(self):
        relays = MullvadApi.wireguard_relays(**self._wg_relays_filter)
        if not relays:
            log_message("No valid endpoint nodes survived the filtering criteria matrices", 3)
            sys.exit(1)
        return relays

    def handle_mullvad_api_error(self, err):
        if err.code == 401:
            log_message("Mullvad transaction dropped: Account authorization failed (HTTP 401)", 3)
        elif err.code == 403:
            log_message("Mullvad connection rejected: Resource access forbidden (HTTP 403)", 3)
        elif err.code == 429:
            log_message("Mullvad transaction throttled: Request frequency exceeded limitations (HTTP 429)", 2)
        else:
            log_message(f"Mullvad service gateway dropped packet transaction with failure code: {err.code}", 3)
        sys.exit(1)
