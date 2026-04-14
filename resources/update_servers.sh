#!/bin/bash
<<'COMMENT'
 JSON_USER=.... https://api.nordvpn.com/v1/users/services/credentials ...

 RAW_JSON=... https://api.nordvpn.com/v1/servers/recommendations?filters\[servers_ ...
 
 NordVPN's Linux client and NordLynx protocol (based on WireGuard) generally prioritize IPv4 traffic and often do not support IPv6 natively, 
 leading to potential IPv6 leaks or connectivity issues, with some reports suggesting IPv6 support is limited to specific servers using NAT66. 
 While the client attempts to prevent leaks by blocking IPv6 traffic, it is often recommended to manually disable IPv6 on the Linux machine to ensure no leaks occur when using NordLynx.

curl -s -u "token:YOUR_TOKEN_HERE" "https://api.nordvpn.com/v1/users/services/credentials" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('username', 'Unauthorized'))"
read -sp "Paste Token: " MY_TOKEN && echo "" && curl -s -o /dev/null -w "%{http_code}" -u "token:$MY_TOKEN" "https://api.nordvpn.com/v1/users/services/credentials"
COMMENT
ADDON_ID="service.wireguard.manager"
ADDON_VER=$(grep '<addon' /storage/.kodi/addons/$ADDON_ID/addon.xml | grep -o 'version="[^"]*"' | cut -d'"' -f2)
[ -z "$ADDON_VER" ] && ADDON_VER="?.?.?"
LOG_PATH="/storage/.kodi/temp/kodi.log"

log_kodi() {
    local msg="$1"
    local level="${2:-info}" # Default to info
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S.%3N")
    local pid=$$ # Script Process ID to look like a Kodi Thread ID
    local lvl_pad="    info"
    [[ "$level" == "error" ]] && lvl_pad="   error"
    [[ "$level" == "warning" ]] && lvl_pad=" warning"

    local formatted_line="${timestamp} T:${pid}${lvl_pad} <general>: ${ADDON_ID} v${ADDON_VER}: ${msg}"

    echo "$msg"
    echo "$formatted_line" >> "$LOG_PATH"
}

TOKEN=$1
# Default to BE(21), DE(81), UK(227), NL(153) if no IDs provided in settings
INPUT_IDS=${2:-"21,81,227,153"}

TOKEN=$(echo "$TOKEN" | tr -d '\r\n ')
COUNTRY_LIST=$(echo "$INPUT_IDS" | tr -d '\r\n ' | tr ',' ' ')

log_kodi "--- NordVPN WireGuard Regen ---"
log_kodi "Target Countries: $COUNTRIES"

JSON_USER=$(curl -s -u "token:$TOKEN" "https://api.nordvpn.com/v1/users/services/credentials")
PRIV_KEY=$(echo "$JSON_USER" | python3 -c "import sys, json; print(json.load(sys.stdin).get('nordlynx_private_key', ''))" 2>/dev/null)

if [ -z "$PRIV_KEY" ] || [ "$PRIV_KEY" == "None" ]; then
    log_kodi "Error: Private Key fetch failed. Check your Token." "error"
	log_kodi "API Response: $JSON_USER" "error"
    exit 1
fi

log_kodi "Cleaning up old NordVPN configs..."
rm -f /storage/.config/wireguard/nord_*.config

for id in $COUNTRY_LIST; do
    log_kodi "Fetching best server for Country ID: $id"

    RAW_JSON=$(curl -s "https://api.nordvpn.com/v1/servers/recommendations?filters\[servers_technologies\]\[identifier\]=wireguard_udp&filters\[country_id\]=$id&limit=1")

    python3 -c "
import sys, json, socket
try:
    resp = json.loads(sys.stdin.read())
    if not resp:
        print(f'No servers found for ID {sys.argv[2]}')
        sys.exit(0)

    data = resp[0]
    hostname = data.get('hostname')
    ip = socket.gethostbyname(hostname)
    country = data['locations'][0]['country']['name'].replace(' ', '_')
    
    wg_tech = next(t for t in data.get('technologies', []) if t.get('identifier') == 'wireguard_udp')
    meta = wg_tech.get('metadata', [])
    pub_key = next((m['value'] for m in meta if m['name'] == 'public_key'), 'None')
    port = next((m['value'] for m in meta if m['name'] == 'port'), '51820')

    config = f'[provider_wireguard]\n'
    config += f'Type = WireGuard\n'
    config += f'Name = NordVPN_{country}\n'
    config += f'Host = {ip}\n'
    config += f'WireGuard.Address = 10.5.0.2/32\n'
    config += f'WireGuard.ListenPort = 51820\n'
    config += f'WireGuard.MTU = 1420\n'
    config += f'WireGuard.PrivateKey = {sys.argv[1]}\n'
    config += f'WireGuard.PublicKey = {pub_key}\n'
    config += f'WireGuard.DNS = 103.86.96.100, 103.86.99.100\n'
    config += f'WireGuard.AllowedIPs = 0.0.0.0/0\n'
    config += f'WireGuard.EndpointPort = {port}\n'
    config += f'WireGuard.PersistentKeepalive = 25\n'

    filename = f'/storage/.config/wireguard/nord_{country.lower()}.config'
    with open(filename, 'w') as f:
        f.write(config)
    print(f'Successfully created {filename}')
except Exception as e:
    print(f'Error processing ID {sys.argv[2]}: {e}')
" "$PRIV_KEY" "$id" <<EOF
$RAW_JSON
EOF
done

log_kodi "Finalizing: Setting permissions and restarting Connman..."
chmod 600 /storage/.config/wireguard/*.config
systemctl restart connman-vpn
log_kodi "--- NordVPN WireGuard Regen Complete ---"
