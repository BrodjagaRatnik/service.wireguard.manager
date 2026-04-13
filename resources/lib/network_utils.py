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

    return dns_list if dns_list else ["103.86.96.100", "103.86.99.100"]

def set_secure_dns(vpn_name=None, vpn_active=True):
    dns_servers = get_dns_from_config(vpn_name) if vpn_active else []
    
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            if "ethernet_" in line or "wifi_" in line:
                sid = line.split()[-1]
                if vpn_active:
                    subprocess.run(["connmanctl", "config", sid, "--nameservers"], check=False)
                    subprocess.run(["connmanctl", "config", sid, "--nameservers"] + dns_servers, check=False)
                    subprocess.run(["connmanctl", "config", sid, "--domains", "."], check=False)
                    subprocess.run(["connmanctl", "config", sid, "--ipv6", "off"], check=False)
                else:
                    subprocess.run(["connmanctl", "config", sid, "--nameservers"], check=False)
                    subprocess.run(["connmanctl", "config", sid, "--domains"], check=False)
                    subprocess.run(["connmanctl", "config", sid, "--ipv6", "auto"], check=False)

        if vpn_active and dns_servers:
            log_message("Network: Forcing manual resolv.conf overwrite for absolute privacy.")
            with open("/etc/resolv.conf", "w") as f:
                f.write("# Hardened DNS by WG Manager\n")
                f.write("options timeout:2 attempts:1\n")
                for dns in dns_servers:
                    f.write(f"nameserver {dns}\n")
        
        log_message(f"Network: DNS {'Hardened & Flushed' if vpn_active else 'Restored'}")
    except Exception as e:
        log_message(f"DNS Error: {e}", xbmc.LOGERROR)

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
