''' resources/lib/vpn_config.py '''
import os

def is_pi5():
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return 'raspberry pi 5' in f.read().lower()
    except:
        return False

PI5 = is_pi5()

if PI5:
    print("VPN Manager: Raspberry Pi 5 detected. Loading high-speed timings.")
else:
    print("VPN Manager: Raspberry Pi 4 (or unknown) detected. Loading stable-speed timings.")

# --- vpn_ops.py ---
PROP_SYNC_DELAY = 100
PROP_SYNC_PURPOSE = "Stops Kodi from getting confused if two updates happen at once"

OS_RELEASE_DELAY = 1000 if PI5 else 1500
OS_RELEASE_PURPOSE = "Gives the system time to completely kill the old VPN tunnel"

CONN_POLL_INTERVAL = 300 if PI5 else 350
CONN_POLL_PURPOSE = "Fast-check to catch the exact second the VPN connects"

ROUTE_PROP_DELAY = 200 if PI5 else 250
ROUTE_PROP_PURPOSE = "Waiting for the internet path to be ready for use"

'''
 --- vpn_ops.py & reconnect_helper.py ---

When the Pi is "awake" but it doesn't have an IP address yet. This constant tells the script how long to wait for 
Router to assign a local IP (DHCP) before it tries to restart the VPN. If this is too fast, the VPN fails because the Pi has no "exit" to the internet.

If the Reconnect fails immediately after plugging the cable back in, increase the DHCP Recovery.
'''
DHCP_RECOVERY_DELAY = 2000 if PI5 else 2500
DHCP_RECOVERY_PURPOSE = "Waiting for DHCP server to assign local IP"

'''
 --- service_launcher.py & service.py ---

Every 1 second, the script checks if eth0 or wlan0 still have a physical link. If cable to wifi, internet down, the script knows within a maximum of 1000ms.

If the Blackout UI (the red error) takes too long to appear when you pull the cable, lower the Heartbeat.
'''
WATCHDOG_HEARTBEAT = 2000 if PI5 else 2000
WATCHDOG_HEARTBEAT_PURPOSE = "The heartbeat that checks if your internet cable is plugged in"
'''
When a cable is pulled and pushed back in, the network often "flaps" (goes up and down several times in a few seconds). 
This 20-25 second timer forces the script to sit still after a fix is triggered. It prevents the "Watchdog" from trying to start 
the VPN 50 times in a row while the router is still rebooting.

If the VPN restarts in a loop during a network crash, increase the Settle Delay.
'''
WATCHDOG_SETTLE_DELAY = 30000 if PI5 else 35000
WATCHDOG_SETTLE_PURPOSE = "Stops the script from restarting the VPN too fast during a network crash"
# --- service_launcher.py & service.py & reconnect_helper.py ---
WATCHDOG_RECOVERY_DELAY = 2000 if PI5 else 2500
WATCHDOG_RECOVERY_PURPOSE = "Prevents a restart if the VPN tunnel just blips for a second"

'''
 --- service.py ---

How long the Watchdog waits when the Reconnect Helper is working. Prevents the Watchdog from "waking up" too fast and fighting the Helper.
'''
SHIELD_SLEEP_DELAY = 5000 if PI5 else 5000

# --- service_control.py ---
SYSTEMD_POLL_DELAY = 300 if PI5 else 400
SYSTEMD_POLL_PURPOSE = "Wait for Linux to finish the Start/Stop command"


# --- vpn_core.py ---
SERVICE_INIT_DELAY = 400 if PI5 else 600
SERVICE_INIT_PURPOSE = "Wait for the system to fully 'birth' the new VPN process"
