""" ./resources/scripts/network.py """
import os
import subprocess
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'lib'))
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


def _shell_run(command):
    subprocess.run(
        command, shell=True, check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def run_network_cleanup():
    from logger import log_message
    from dialog import TaskProgress, show_ok
    from state_manager import CONFIG_DIR

    vpn_services_dir = os.path.join(os.path.dirname(CONFIG_DIR), "vpn-services")

    progress = TaskProgress("Network Reset", "Starting network subsystem reset...")
    routes = ""

    try:
        progress.update(15, "Disengaging firewall killswitch...")
        _shell_run(
            'iptables -D OUTPUT -j LE_WG_KILLSWITCH 2>/dev/null; '
            'iptables -F LE_WG_KILLSWITCH 2>/dev/null; '
            'iptables -X LE_WG_KILLSWITCH 2>/dev/null'
        )

        progress.update(35, "Disconnecting VPN services...")
        _shell_run(
            'connmanctl services | grep vpn_ | grep -E "\\* |R " | '
            'awk \'{print $NF}\' | xargs -I {} connmanctl disconnect {}'
        )

        progress.update(55, "Purging service profiles...")
        _shell_run(f'rm -f "{vpn_services_dir}"/*')

        progress.update(70, "Flushing route caches...")
        _shell_run('ip route flush cache')

        progress.update(85, "Restarting network manager...")
        _shell_run('systemctl restart connman')

        import xbmc
        xbmc.sleep(500)

        progress.update(95, "Verifying default routes...")
        result = subprocess.run(
            'ip route show match 0.0.0.0/0',
            shell=True, capture_output=True, text=True, check=False
        )
        routes = result.stdout.strip() if result.stdout else ""

        progress.update(100, "Cleanup complete")

    except Exception as reset_fault:
        log_message(f"Network: Cleanup stage failed: {reset_fault}", 3)

    finally:
        progress.close()

    if routes:
        log_message(f"Network: Cleanup Route Check {routes}", 1)
        line1 = "The network subsystem has been successfully reset."
        line2 = "Your routing tables and ConnMan caches are cleared."
        line3 = "Firewall killswitch successfully disengaged."
        show_ok("Network Reset", f"{line1}\n{line2}\n{line3}\n\n{routes}")
    else:
        log_message("Network: Cleanup Route Check No active default routes found.", 3)
        error_msg = "No active default routes found. Connection could not be re-established."
        show_ok("Network Reset Error", error_msg)


if __name__ == "__main__":
    run_network_cleanup()
