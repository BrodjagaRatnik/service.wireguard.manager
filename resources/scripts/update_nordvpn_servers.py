''' .resources/scripts/update_nordvpn_servers.py 

user_data = fetch_url("https://api.nordvpn.com/v1/users/services/credentials", TOKEN)

url = f"https://api.nordvpn.com/v1/servers/recommendations?filters[servers_technologies][identifier]=wireguard_udp&filters[country_id]={c_id}&limit=1"
'''
import sys, os

lib_path = os.path.join(os.path.dirname(__file__), '..', 'lib')
sys.path.append(os.path.normpath(lib_path))

from logger import log_message

import json
import socket
import subprocess
import urllib.request
import urllib.error
import base64

if len(sys.argv) < 3:
    log_message(f"Update: Missing arguments (Token or Country IDs)", 3)
    sys.exit(1)

TOKEN = sys.argv[1]
COUNTRY_IDS = sys.argv[2]
CONFIG_DIR = '/storage/.config/wireguard/'

def fetch_url(url, token=None):
    headers = {'User-Agent': 'Mozilla/5.0'}
    if token:
        auth = base64.b64encode(f"token:{token}".encode()).decode()
        headers['Authorization'] = f"Basic {auth}"
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        log_message(f"Update: API Fetch Error: {e}", 3)
        return None

def main():
    user_data = fetch_url("https://api.nordvpn.com/v1/users/services/credentials", TOKEN)
    if not user_data or 'nordlynx_private_key' not in user_data:
        log_message("Update: Private Key fetch failed. Check Token.", 3)
        sys.exit(1)
    
    priv_key = user_data['nordlynx_private_key']
    ids = [i.strip() for i in COUNTRY_IDS.split(',')]
    success_count = 0

    for c_id in ids:
        url = f"https://api.nordvpn.com/v1/servers/recommendations?filters[servers_technologies][identifier]=wireguard_udp&filters[country_id]={c_id}&limit=1"
        servers = fetch_url(url)

        if not servers or not isinstance(servers, list) or len(servers) == 0:
            continue

        data = servers[0] 
        try:
            hostname = data.get('hostname')
            ip = socket.gethostbyname(hostname)
            country_name = data['locations'][0]['country']['name'].replace(' ', '_')
            wg_tech = next(t for t in data.get('technologies', []) if t.get('identifier') == 'wireguard_udp')
            meta = wg_tech.get('metadata', [])
            pub_key = next((m['value'] for m in meta if m['name'] == 'public_key'), 'None')
            port = next((m['value'] for m in meta if m['name'] == 'port'), '51820')

            config = (
                "[provider_wireguard]\n"
                "Type = WireGuard\n"
                f"Name = NordVPN_{country_name}\n"
                f"Host = {ip}\n"
                "WireGuard.Address = 10.5.0.2/32\n"
                "WireGuard.ListenPort = 51820\n"
                "WireGuard.MTU = 1420\n"
                f"WireGuard.PrivateKey = {priv_key}\n"
                f"WireGuard.PublicKey = {pub_key}\n"
                "WireGuard.DNS = 103.86.96.100, 103.86.99.100\n"
                "WireGuard.AllowedIPs = 0.0.0.0/0\n"
                f"WireGuard.EndpointPort = {port}\n"
                "WireGuard.PersistentKeepalive = 25\n"
            )

            file_path = os.path.join(CONFIG_DIR, f"nord_{country_name.lower()}.config")
            with open(file_path, 'w') as f:
                f.write(config)
            
            success_count += 1

        except Exception:
            continue

    try:
        files = [os.path.join(CONFIG_DIR, f) for f in os.listdir(CONFIG_DIR) if f.startswith("nord_")]
        if files:
            subprocess.run(["chmod", "600"] + files, check=False)
            subprocess.run(["systemctl", "restart", "connman-vpn"], check=False)

            if success_count > 0:
                log_message("Update: Server configs regenerated successfully.", 1)
        else:
            log_message("Update: No configs found to update.", 2)
    except Exception:
        log_message("Update: Finalization failed.", 3)

if __name__ == "__main__":
    main()
