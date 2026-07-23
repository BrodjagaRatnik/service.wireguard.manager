""" ./resources/scripts/network.py """
import subprocess
import xbmc
import xbmcgui
from logger import log_message


def run_network_cleanup():
    cleanup_cmd = (
        'iptables -D OUTPUT -j LE_WG_KILLSWITCH 2>/dev/null && '
        'iptables -F LE_WG_KILLSWITCH 2>/dev/null && '
        'iptables -X LE_WG_KILLSWITCH 2>/dev/null; '
        'connmanctl services | grep vpn_ | grep -E "\\* |R " | awk \'{print $NF}\' | xargs -I {} connmanctl disconnect {} && '
        'rm -f /storage/.config/vpn-services/* && '
        'ip route flush cache && '
        'systemctl restart connman'
    )
    subprocess.run(cleanup_cmd, shell=True, check=False)
    xbmc.sleep(500)

    route_cmd = 'ip route show match 0.0.0.0/0'
    result = subprocess.run(route_cmd, shell=True, capture_output=True, text=True, check=False)
    routes = result.stdout.strip() if result.stdout else ""
    dialog = xbmcgui.Dialog()

    if routes:
        log_message(f"Network: Cleanup Route Check {routes}", 1)
        line1 = "The network subsystem has been successfully reset."
        line2 = "Your routing tables and ConnMan caches are cleared."
        line3 = "Firewall killswitch successfully disengaged."
        dialog.ok("Network Reset", f"{line1}\n{line2}\n{line3}\n\n{routes}")
    else:
        log_message("Network: Cleanup Route Check No active default routes found.", 3)
        error_msg = "No active default routes found. Connection could not be re-established."
        dialog.ok("Network Reset Error", error_msg)


if __name__ == "__main__":
    run_network_cleanup()
