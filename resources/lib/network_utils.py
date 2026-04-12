import os, re, subprocess, xbmc
from logger import log_message

def get_dns_from_config(vpn_name):
    config_dir = "/storage/.config/wireguard/"
    dns_list = []
    variations = [
        f"{vpn_name}.config", 
        f"{vpn_name.lower()}.config", 
        f"{vpn_name.lower().replace('nordvpn', 'nord')}.config"
    ]
    target_path = next((os.path.join(config_dir, v) for v in variations if os.path.exists(os.path.join(config_dir, v))), None)
    
    if target_path:
        try:
            with open(target_path, 'r') as f:
                content = f.read()
                match = re.search(r"(?:WireGuard\.)?DNS\s*=\s*(.*)", content, re.IGNORECASE)
                if match:
                    dns_list = [d.strip() for d in match.group(1).split(",")]
        except: pass

    # Fallback to NordVPN Public DNS if parsing fails
    return dns_list if dns_list else ["103.86.96.100", "103.86.99.100"]

def set_secure_dns(vpn_name=None, vpn_active=True):
    """Overrides DNS for ALL physical interfaces to ensure no leaks."""
    dns_servers = get_dns_from_config(vpn_name) if vpn_active else []
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            if "ethernet_" in line or "wifi_" in line:
                service_id = line.split()[-1]
                subprocess.run(["connmanctl", "config", service_id, "--nameservers"] + dns_servers, check=False)
                
        state = f"VPN DNS {dns_servers}" if vpn_active else "DHCP/Auto"
        log_message(f"Network: DNS locked to {state} for all hardware.")
    except Exception as e:
        log_message(f"Network Error: DNS Override failed: {e}", xbmc.LOGERROR)

def disable_connman_ipv6():
    """Forces IPv6 off for all physical interfaces."""
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                subprocess.run(["connmanctl", "config", service_id, "--ipv6", "off"], check=False)
        log_message("Network: IPv6 disabled on physical interfaces", xbmc.LOGINFO)
    except Exception as e:
        log_message(f"Network Error: IPv6 Disable failed: {e}", xbmc.LOGERROR)

def enable_connman_ipv6():
    """Restores IPv6 to auto mode for physical interfaces."""
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                subprocess.run(["connmanctl", "config", service_id, "--ipv6", "auto"], check=False)
        log_message("Network: IPv6 restored to auto", xbmc.LOGINFO)
    except Exception as e:
        log_message(f"Network Error: IPv6 Restore failed: {e}", xbmc.LOGERROR)
