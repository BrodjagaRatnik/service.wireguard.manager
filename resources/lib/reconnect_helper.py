import xbmc, xbmcgui, xbmcaddon, os, sys, time, subprocess

addon = xbmcaddon.Addon('service.wireguard.manager')
addon_path = addon.getAddonInfo('path')
sys.path.append(os.path.join(addon_path, 'resources', 'lib'))

from vpn_ops import disconnect_vpn, connect_vpn
from logger import log_message

state_path = "/tmp/vpn_manager_active.txt"
vpn_name = None

if os.path.exists(state_path):
    with open(state_path, "r") as f:
        vpn_name = f.read().strip()

if not vpn_name or vpn_name.lower() == "true":
    vpn_name = xbmcgui.Window(10000).getProperty('vpn_manual_session')

if not vpn_name or vpn_name.lower() == "true":
    log_message(f"Helper: Invalid VPN name '{vpn_name}'. Stopping.")
    sys.exit()

log_message(f"Helper: Failover for {vpn_name} started. Cleaning up...")

disconnect_vpn(silent=True)

time.sleep(4)

try:
    out = subprocess.check_output(["connmanctl", "services"], text=True)
    search_name = vpn_name.replace(' ', '_')
    
    target_sid = None
    for line in out.splitlines():
        if "vpn_" in line and (search_name.lower() in line.lower() or vpn_name.lower() in line.lower()):
            target_sid = line.split()[-1]
            break

    if target_sid:
        log_message(f"Helper: Reconnecting to {vpn_name} via {target_sid}")
        xbmcgui.Window(10000).setProperty('vpn_manual_session', 'true')
        connect_vpn(vpn_name, target_sid)
    else:
        log_message(f"Helper: Could not find SID for {vpn_name}")

except Exception as e:
    log_message(f"Helper Error: {e}")
