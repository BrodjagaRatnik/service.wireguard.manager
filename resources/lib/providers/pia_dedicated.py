""" resources/lib/providers/pia_dedicated.py """
import os
import ssl
import json
import base64
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from logger import log_message


def execute_basic_auth_handshake(dip_token, server_ip, hostname, config_dir="/storage/.config/wireguard/"):
    try:
        pk = subprocess.check_output(["wg", "genkey"]).decode().strip()
        pub = subprocess.check_output(["wg", "pubkey"], input=pk.encode()).decode().strip()
    except Exception:
        log_message("PIA Dedicated: Failed to generate temporary local WireGuard cryptographic keypair", 3)
        return False

    auth_payload = "dedicated_ip_" + str(dip_token).strip() + ":" + str(server_ip).strip()
    encoded_auth = base64.b64encode(auth_payload.encode("utf-8")).decode("ascii")
    request_headers = {
        "User-Agent": "PIA-VPN/3.5.0 (Linux)",
        "Host": str(hostname).strip(),
        "Accept": "application/json",
        "Authorization": "Basic " + encoded_auth
    }

    handshake_url = "https://" + str(server_ip).strip() + ":1337/addKey?pubkey=" + str(pub)
    return _process_api_handshake(handshake_url, request_headers, pk, server_ip, hostname, config_dir)


def execute_url_param_handshake(pia_token, server_ip, hostname, config_dir="/storage/.config/wireguard/"):
    try:
        pk = subprocess.check_output(["wg", "genkey"]).decode().strip()
        pub = subprocess.check_output(["wg", "pubkey"], input=pk.encode()).decode().strip()
    except Exception:
        log_message("PIA Dedicated: Failed to generate temporary local WireGuard cryptographic keypair", 3)
        return False

    request_headers = {
        "User-Agent": "PIA-VPN/3.5.0 (Linux)",
        "Host": str(hostname).strip(),
        "Accept": "application/json"
    }

    query_parameters = urllib.parse.urlencode({"pt": str(pia_token).strip(), "pubkey": str(pub)})
    handshake_url = "https://" + str(server_ip).strip() + ":1337/addKey?" + query_parameters
    return _process_api_handshake(handshake_url, request_headers, pk, server_ip, hostname, config_dir)


def _process_api_handshake(handshake_url, request_headers, pk, server_ip, hostname, config_dir):
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_REQUIRED
    except Exception:
        ssl_context = ssl._create_unverified_context()

    api_request = urllib.request.Request(handshake_url, headers=request_headers)
    log_message("PIA Dedicated: Dispatching localized registration packet to target endpoint", 1)

    try:
        with urllib.request.urlopen(api_request, timeout=10, context=ssl_context) as secure_response:
            json_response = json.loads(secure_response.read().decode("utf-8"))
    except urllib.error.URLError as connection_error:
        if "CERTIFICATE_VERIFY_FAILED" in str(connection_error):
            log_message("PIA Dedicated: Core validation failure encountered, shifting to emergency context bypass", 2)
            unverified_context = ssl._create_unverified_context()
            try:
                with urllib.request.urlopen(api_request, timeout=10, context=unverified_context) as bypass_response:
                    json_response = json.loads(bypass_response.read().decode("utf-8"))
            except Exception:
                log_message("PIA Dedicated: Downstream registration failed following security context mitigation", 3)
                return False
        else:
            log_message("PIA Dedicated: Remote endpoint network socket transport timed out or failed to resolve", 3)
            return False
    except Exception:
        log_message("PIA Dedicated: General execution exception logged during remote network operation", 3)
        return False

    if json_response.get("status") != "OK":
        log_message("PIA Dedicated: Upstream authorization gateway rejected packet signature validation", 3)
        return False

    try:
        os.makedirs(config_dir, exist_ok=True)
        safe_ip_string = str(server_ip).strip().replace(".", "_")
        destination_path = os.path.join(config_dir, "pia_dedicated_" + safe_ip_string + ".config")
        assigned_ip = json_response["peer_ip"] + "/32"
        endpoint_port = str(json_response.get("server_port", "1337"))
        remote_public_key = json_response["server_key"]
        default_routing_table = "0.0.0.0/0"
        default_interface_mtu = "1420"
        primary_dns_cluster = "10.0.0.243, 10.0.0.241"
        blueprint_structure = (
            "[provider_wireguard]\n"
            "Type = WireGuard\n"
            "Name = " + str(hostname).strip() + "\n"
            "Host = " + str(server_ip).strip() + "\n"
            "WireGuard.MTU = " + str(default_interface_mtu) + "\n"
            "WireGuard.Address = " + str(assigned_ip) + "\n"
            "WireGuard.PrivateKey = " + str(pk) + "\n"
            "WireGuard.PublicKey = " + str(remote_public_key) + "\n"
            "WireGuard.DNS = " + str(primary_dns_cluster) + "\n"
            "WireGuard.EndpointPort = " + str(endpoint_port) + "\n"
            "WireGuard.AllowedIPs = " + str(default_routing_table) + "\n"
            "WireGuard.PersistentKeepalive = 25\n"
        )

        with open(destination_path, "w") as storage_file:
            storage_file.write(blueprint_structure)

        log_message("PIA Dedicated: Runtime configuration deployment script compiled successfully to storage", 1)
        return True

    except Exception:
        log_message("PIA Dedicated: Internal disk I/O exception blocking localized file write procedure", 3)
        return False
