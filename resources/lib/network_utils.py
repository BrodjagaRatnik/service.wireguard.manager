''' ./resources/lib/network_utils.py '''
import os, re, subprocess

try:
    import xbmc
    KODI_AVAILABLE = True
except ImportError:
    KODI_AVAILABLE = False

CONFIG_DIR = "/storage/.config/wireguard/"

def log_message(msg, level=None):
    if KODI_AVAILABLE:
        xbmc.log(f"NetworkUtils: {msg}", level if level is not None else 1)
    else:
        print(f"NetworkUtils: {msg}", flush=True)

def get_default_gateway(ignore_vpn=True):
    try:
        out = subprocess.check_output(["ip", "-4", "route", "show", "default"], text=True)
        for line in out.splitlines():
            if "via" in line:
                if ignore_vpn and "wg0" in line: continue
                parts = line.split()
                return parts[parts.index("via") + 1]
    except: pass
    return None

def get_dns_from_config(vpn_name):
    dns_list = []
    variations = [
        f"{vpn_name}.config", 
        f"{vpn_name.lower()}.config", 
        f"{vpn_name.lower().replace('nordvpn', 'nord')}.config"
    ]
    
    target_path = next((os.path.join(CONFIG_DIR, v) for v in variations if os.path.exists(os.path.join(CONFIG_DIR, v))), None)
    
    if target_path:
        try:
            with open(target_path, 'r') as f:
                content = f.read()
                match = re.search(r"(?:WireGuard\.)?DNS\s*=\s*(.*)", content, re.IGNORECASE)
                if match:
                    dns_list = [d.strip() for d in match.group(1).split(",")]
        except Exception as e:
            log_message(f"NetworkUtils: Error reading DNS from config: {e}", xbmc.LOGERROR)

    return dns_list

def set_secure_dns(vpn_name=None, vpn_active=True):
    dns_servers = get_dns_from_config(vpn_name) if vpn_active else []
    
    try:
        ipv6_val = "1" if vpn_active else "0"
        subprocess.run(["sysctl", "-w", f"net.ipv6.conf.all.disable_ipv6={ipv6_val}"], check=False)
        subprocess.run(["sysctl", "-w", f"net.ipv6.conf.default.disable_ipv6={ipv6_val}"], check=False)

        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            if "ethernet_" in line or "wifi_" in line:
                sid = line.split()[-1]
                if vpn_active:
                    subprocess.run(["connmanctl", "config", sid, "--nameservers"], check=False)
                    if dns_servers:
                        subprocess.run(["connmanctl", "config", sid, "--nameservers"] + dns_servers, check=False)
                        subprocess.run(["connmanctl", "config", sid, "--domains", "."], check=False)
                        subprocess.run(["connmanctl", "config", sid, "--ipv6", "off"], check=False)

                else:
                    subprocess.run(["connmanctl", "config", sid, "--nameservers"], check=False)
                    subprocess.run(["connmanctl", "config", sid, "--domains"], check=False)
                    subprocess.run(["connmanctl", "config", sid, "--ipv6", "auto"], check=False)

        if vpn_active and dns_servers:
            log_message("NetworkUtils: Forcing manual resolv.conf overwrite for absolute privacy.", xbmc.LOGDEBUG)
            with open("/etc/resolv.conf", "w") as f:
                f.write("# Hardened DNS by WireGuard Manager\n")
                f.write("options timeout:2 attempts:1\n")
                for dns in dns_servers:
                    f.write(f"nameserver {dns}\n")
        
        log_message(f"NetworkUtils: DNS & IPv6 {'Hardened' if vpn_active else 'Restored'}", xbmc.LOGDEBUG)
    except Exception as e:
        log_message(f"NetworkUtils: DNS hardening failed: {e}", xbmc.LOGERROR)

def disable_connman_ipv6():
    """Forces IPv6 off for all physical interfaces and Kernel."""
    try:
        subprocess.run(["sysctl", "-w", "net.ipv6.conf.all.disable_ipv6=1"], check=False)
        subprocess.run(["sysctl", "-w", "net.ipv6.conf.default.disable_ipv6=1"], check=False)
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                subprocess.run(["connmanctl", "config", service_id, "--ipv6", "off"], check=False)
        
        log_message("NetworkUtils: IPv6 disabled globally and on interfaces", xbmc.LOGDEBUG)
    except Exception as e:
        log_message(f"NetworkUtils: IPv6 Disable failed: {e}", xbmc.LOGERROR)

def enable_connman_ipv6():
    """Restores IPv6 to auto mode for physical interfaces and Kernel."""
    try:
        subprocess.run(["sysctl", "-w", "net.ipv6.conf.all.disable_ipv6=0"], check=False)
        subprocess.run(["sysctl", "-w", "net.ipv6.conf.default.disable_ipv6=0"], check=False)
        result = subprocess.check_output(["connmanctl", "services"], text=True)
        for line in result.splitlines():
            parts = line.split()
            if not parts: continue           
            service_id = parts[-1]
            if service_id.startswith(("ethernet_", "wifi_")):
                subprocess.run(["connmanctl", "config", service_id, "--ipv6", "auto"], check=False)
                
        log_message("NetworkUtils: IPv6 restored to auto", xbmc.LOGDEBUG)
    except Exception as e:
        log_message(f"NetworkUtils: IPv6 Restore failed: {e}", xbmc.LOGERROR)

def is_physically_connected(interface):
    """Checks the physical carrier status of a network interface (1=Connected, 0=Unplugged)."""
    try:
        path = f"/sys/class/net/{interface}/carrier"
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read().strip() == '1'
    except:
        pass
    return False
