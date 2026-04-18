''' VPN Timing Constants Optimized for Pi 5 All values in milliseconds (ms) '''

''' vpn_ops.py '''
# Tiny pause after writing a status change to Kodi’s internal memory (Properties).
PROP_SYNC_DELAY = 100
PROP_SYNC_PURPOSE = "Syncing Kodi properties to prevent service conflict"
# The "Letting Go" timer. It waits 1 full second after telling the system to shut down the VPN.
OS_RELEASE_DELAY = 1000
OS_RELEASE_PURPOSE = "Waiting for Kernel to destroy wg0 interface"
# Instead of one long 5-second sleep while waiting for the VPN to connect, the script uses a loop that checks the status every 0.3 seconds.
CONN_POLL_INTERVAL = 300
CONN_POLL_PURPOSE = "Polling Connman for WireGuard handshake"

''' service.py '''
# Creates a tiny gap between the command to "Start VPN" and the next command to "Test VPN."
ROUTE_PROP_DELAY = 200
ROUTE_PROP_PURPOSE = "Waiting for routing table/DNS propagation"
# Every 2 seconds, the script wakes up, checks if Ethernet is plugged in, and checks if the VPN is alive.
WATCHDOG_HEARTBEAT = 2000
# When you plug/unplug Ethernet, the script triggers the HELPER_SCRIPT and then freezes for 4 seconds.
WATCHDOG_SETTLE_DELAY = 4000
WATCHDOG_SETTLE_PURPOSE = "Physical interface swap/priority cooling"
# If the script sees the internet is fine but the VPN tunnel (wg0) is missing, it triggers a recovery and freezes for 3 seconds.
WATCHDOG_RECOVERY_DELAY = 1500
WATCHDOG_RECOVERY_PURPOSE = "Anti-flap tunnel recovery buffer"

''' service_control.py '''
# The gap between asking Systemd (the OS service manager) to do something and checking if it actually did it.
SYSTEMD_POLL_DELAY = 300
SYSTEMD_POLL_PURPOSE = "Systemd state transition wait"

''' reconnect_helper.py '''
'''  If a connection fails, the network stack (Connman/Kernel) can get messy. 
This 3s cooling period ensures all sockets are closed and the hardware is "quiet" before the helper script tries to build the tunnel again. 
It prevents the system from getting stuck in a high-speed crash loop. '''
CLEANUP_COOLING_DELAY = 3000
CLEANUP_COOLING_PURPOSE = "Network stack cooling before reconnect"

''' vpn_core.py '''
''' When the script starts a system process, the Pi 5 needs a fraction of a second to assign a PID (Process ID) and allocate resources. 
This wait prevents the script from trying to interact with a process that isn't fully "born" yet. '''
SERVICE_INIT_DELAY = 400
SERVICE_INIT_PURPOSE = "Systemd PID spawning buffer"
# These delays keep a notification on screen or a menu open just long enough to read "Connected" or "Disconnected" before the screen changes. 
UI_BUFFER_DELAY = 800
UI_BUFFER_PURPOSE = "Visual confirmation hold for user"

''' menu_vpn.py Visual/System confirmation buffer for manual menu actions '''
UI_BUFFER_DELAY_MENU = 500 
UI_BUFFER_PURPOSE = "Visual confirmation hold for user / Property sink"

''' NordVPN Default DNS '''
DNS_FALLBACK = ["103.86.96.100", "103.86.99.100"]

''' Fallback Gateway '''
GATEWAY_FALLBACK = "192.168.178.1"
