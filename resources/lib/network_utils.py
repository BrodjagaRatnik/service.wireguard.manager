import os, re, subprocess, xbmc

def get_dns_from_config(vpn_name):
    """Parses the WireGuard .config file for DNS servers."""
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

def set_secure_dns(vpn_name=None, vpn_active=True, log_cb=None):
    """Overrides DNS for ALL physical interfaces to ensure no leaks."""
    dns_servers = get_dns_from_config(vpn_name) if vpn_active else []
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            if "ethernet_" in line or "wifi_" in line:
                service_id = line.split()[-1]

                subprocess.run(["connmanctl", "config", service_id, "--nameservers"] + dns_servers, check=False)
                
        if log_cb:
            state = f"VPN DNS {dns_servers}" if vpn_active else "DHCP/Auto"
            log_cb(f"DNS locked to {state} for all hardware.")
    except Exception as e:
        if log_cb: log_cb(f"DNS Override Error: {e}", xbmc.LOGERROR)

def disable_connman_ipv6(log_cb=None):
    """Forces IPv6 off for all physical interfaces."""
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                subprocess.run(["connmanctl", "config", service_id, "--ipv6", "off"], check=False)
        if log_cb: log_cb("IPv6 disabled on physical interfaces")
    except Exception as e:
        if log_cb: log_cb(f"IPv6 Disable Error: {e}", xbmc.LOGERROR)

def enable_connman_ipv6(log_cb=None):
    """Restores IPv6 to auto mode for physical interfaces."""
    try:
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                subprocess.run(["connmanctl", "config", service_id, "--ipv6", "auto"], check=False)
        if log_cb: log_cb("IPv6 restored to auto")
    except Exception as e:
        if log_cb: log_cb(f"IPv6 Restore Error: {e}", xbmc.LOGERROR)
