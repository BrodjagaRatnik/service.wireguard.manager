""" From: https://github.com/mullvad/wg-tools

HOST = 'https://api.mullvad.net'
        url = "https://api.mullvad.net/public/relays/wireguard/v1/"
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

    def new_device(self, public_key, hijack_dns=False):
        body = {
            "pubkey": public_key,
            "hijack_dns": hijack_dns,
        }
        return self._api(f"{MullvadApi.HOST}/accounts/v1/devices", body)

    def list_devices(self):
        return self._api(f"{MullvadApi.HOST}/accounts/v1/devices")

    @functools.cached_property
    def web_token(self) -> str:
        from wm_utils import safe_decrypt_password
        body = {
            "account_number": safe_decrypt_password(self.account_number),
        }
        req = urllib.request.Request(f"{MullvadApi.HOST}/auth/v1/webtoken")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        try:
            with urllib.request.urlopen(req, json.dumps(body).encode(), timeout=10) as response:
                data = json.load(response)
            return data["access_token"]
        except urllib.error.HTTPError as e:
            error_data = MullvadApi.get_response(e)
            detail = error_data.get("detail", "Unknown authentication error")
            log_message(f"Mullvad API authentication token rejected: {detail}", 3)
            raise
        except Exception as e:
            log_message(f"Unexpected connection error while fetching Mullvad web token: {e}", 3)
            raise

    def _api(self, url, body=None):
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.web_token}")
            req.add_header("Accept-Encoding", "gzip")
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            if body:
                req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, data=json.dumps(body).encode() if body else None, timeout=10) as response:
                return self.get_response(response)
        except urllib.error.HTTPError as e:
            raise e
        except Exception as e:
            log_message(f"Network backend subsystem failure accessing Mullvad endpoint {url}: {e}", 3)
            raise

    @staticmethod
    def default_dns_servers() -> str:
        return "10.64.0.1"

    @functools.cache
    @staticmethod
    def all_wireguard_relays():
        url = "https://api.mullvad.net/public/relays/wireguard/v1/"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw_data = json.loads(response.read().decode("utf-8"))

            flat_relays = []
            if isinstance(raw_data, dict) and "countries" in raw_data:
                for country in raw_data["countries"]:
                    c_name = country.get("name", "")
                    c_code = country.get("code", "")
                    if "cities" in country:
                        for city in country["cities"]:
                            city_name = city.get("name", "")
                            if "relays" in city:
                                for r in city["relays"]:
                                    if isinstance(r, dict):
                                        r["country_name"] = c_name
                                        r["country_code"] = c_code
                                        r["city_name"] = city_name

                                        h_name = str(r.get("hostname", "")).lower()
                                        srv_part = h_name.split("-")[-1] if "-" in h_name else ""
                                        r["owned"] = (srv_part.startswith("0") if srv_part else False)

                                        flat_relays.append(r)
            return flat_relays
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
            target_countries = [c.strip().lower() for c in location_prefix.split(",") if c.strip()]
            if target_countries:
                filtered_relays = []
                for r in relays:
                    host = str(r.get("hostname", "")).lower()
                    country_text = str(r.get("country", "")).lower()
                    match_found = False
                    for tc in target_countries:
                        if host.startswith(f"{tc}-") or tc in country_text:
                            match_found = True
                            break
                    if match_found:
                        filtered_relays.append(r)
                relays = filtered_relays

        if kwargs.get("active", False):
            relays = [r for r in relays if r.get("active", True)]

        if kwargs.get("owned", False):
            relays = [r for r in relays if r.get("owned", False)]

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

    def create_wg_configs(self, relays, device, privatekey, dns_str, multihop_server) -> None:
        try:
            output_dir = pathlib.Path(self.output_dir).expanduser()
            output_dir.mkdir(exist_ok=True, parents=True)
        except Exception as e:
            log_message(f"Failed to instantiate target configuration directory path structural entities: {e}", 3)
            raise

        try:
            for old_file in output_dir.glob("mullvad_*.config"):
                old_file.unlink()
        except Exception as clean_err:
            log_message(f"Failed to purge existing Mullvad platform assets from target layout: {clean_err}", 2)

        for relay in relays:
            try:
                self.create_connman_config(output_dir, relay, device, privatekey, dns_str, multihop_server)
            except Exception as e:
                log_message(
                    f"Skipping corrupt configuration block rendering pass for target host "
                    f"{relay.get('hostname')}: {e}", 2
                )

    def create_connman_config(self, output_dir, relay, device, privatekey, dns_str, multihop_server=None) -> None:
        hostname = relay["hostname"]
        if multihop_server:
            server_name = multihop_server["hostname"]
            dest_filename = f"mullvad_{hostname}-via-{server_name}.config"
            remote_server = multihop_server
            remote_port = relay["multihop_port"]
        else:
            dest_filename = f"mullvad_{hostname}.config"
            remote_server = relay
            remote_port = self.wg_relay_port

        file_path = output_dir / dest_filename

        try:
            file_path.touch(mode=0o600, exist_ok=True)
        except Exception as e:
            log_message(f"Permission fault while reserving lock descriptors for path {file_path}: {e}", 3)
            raise

        host = remote_server["ipv4_addr_in"]
        raw_address = device["ipv4_address"]
        clean_address = raw_address.split("/")[0].strip()

        c_name = str(relay.get("country_name", "VPN")).strip().replace(" ", "")
        raw_city = relay.get("city_name", "")
        city_str = f"-{str(raw_city).strip().replace(' ', '')}" if raw_city else ""
        srv_num = hostname.split("-")[-1] if "-" in hostname else hostname
        display_name = f"Mullvad_{c_name}{city_str}-{srv_num}"

        dest_lines = [
            "[provider_wireguard]",
            "Type = WireGuard",
            f"Name = {display_name}",
            f"Host = {host}",
            f"WireGuard.Address = {clean_address}/32",
            "WireGuard.ListenPort = 51820",
            f"WireGuard.MTU = {self.mtu}",
            f"WireGuard.PrivateKey = {privatekey}",
            f"WireGuard.PublicKey = {relay['public_key']}",
            f"WireGuard.DNS = {dns_str}",
            "WireGuard.AllowedIPs = 0.0.0.0/0, ::/0",
            f"WireGuard.EndpointPort = {remote_port}",
            "WireGuard.PersistentKeepalive = 25"
        ]

        try:
            with file_path.open("w") as target_file:
                target_file.write("\n".join(dest_lines) + "\n")
        except Exception as e:
            log_message(f"Failed writing localized ConnMan profile transformation asset to node {file_path}: {e}", 3)
            raise


class Mullvad:
    def __init__(self, args):
        from wm_utils import safe_decrypt_password
        clean_account = safe_decrypt_password(args.account_number)
        self.mullvad_api = MullvadApi(clean_account)
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

            if self.mullvad_config.wg_dns:
                dns_str = ", ".join([str(x) for x in self.mullvad_config.wg_dns])
            else:
                dns_str = "100.64.0.63, 100.64.0.7"

            if device:
                self.mullvad_config.create_wg_configs(relays, device, private_key, dns_str, multihop_server)
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
                if not self._config.has_section("Interface"):
                    self._config.add_section("Interface")
                self._config.set("Interface", "privatekey", privatekey)
                self._config.write(_file)
            log_message(f"Mullvad System Registry: Key written to {self._settings_file}", 1)
            return True
        except configparser.DuplicateSectionError as d_err:
            log_message(f"Mullvad Configuration Conflict: Interface sector structurally persistent: {d_err}", 3)
            raise
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
            response = self.mullvad_api.new_device(publickey, hijack_dns=False)
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
        try:
            error_message = MullvadApi.get_response(err)
            error_code = error_message.get("code")
            detail_message = error_message.get("detail", "API communication failure")

            if error_code == "PUBKEY_IN_USE":
                log_message("Mullvad error: Cryptographic device key is already registered elsewhere", 3)
            elif error_code == "INVALID_ACCOUNT":
                log_message("Mullvad error: Provided account token identification is unrecognized", 3)
            else:
                log_message(f"Mullvad API constraint occurred: {detail_message}", 3)
        except Exception:
            log_message(f"Mullvad service gateway dropped packet transaction with failure code: {err.code}", 3)
        sys.exit(1)
