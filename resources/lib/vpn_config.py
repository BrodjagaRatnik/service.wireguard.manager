''' VPN Timing Constants Optimized for Pi 5 All values in milliseconds (ms) '''

''' vpn_ops.py '''
PROP_SYNC_DELAY = 100
PROP_SYNC_PURPOSE = "Syncing Kodi properties to prevent service conflict"
OS_RELEASE_DELAY = 500
OS_RELEASE_PURPOSE = "Waiting for Kernel to destroy wg0 interface"
CONN_POLL_INTERVAL = 300
CONN_POLL_PURPOSE = "Polling Connman for WireGuard handshake"
''' service.py (will be divided by 1000 for time.sleep) '''
ROUTE_PROP_DELAY = 200
ROUTE_PROP_PURPOSE = "Waiting for routing table/DNS propagation"
WATCHDOG_HEARTBEAT = 2000
WATCHDOG_SETTLE_DELAY = 4000
WATCHDOG_SETTLE_PURPOSE = "Physical interface swap/priority cooling"
WATCHDOG_RECOVERY_DELAY = 3000
WATCHDOG_RECOVERY_PURPOSE = "Anti-flap tunnel recovery buffer"
''' service_control.py '''
SYSTEMD_POLL_DELAY = 300
SYSTEMD_POLL_PURPOSE = "Systemd state transition wait"
''' reconnect_helper.py '''
CLEANUP_COOLING_DELAY = 3000
CLEANUP_COOLING_PURPOSE = "Network stack cooling before reconnect"
''' vpn_core.py '''
SERVICE_INIT_DELAY = 400
SERVICE_INIT_PURPOSE = "Systemd PID spawning buffer"
UI_BUFFER_DELAY = 800
UI_BUFFER_PURPOSE = "Visual confirmation hold for user"
''' NordVPN Default DNS (Anycast) Only used if the specific .config file cannot be read. '''
DNS_FALLBACK = ["103.86.96.100", "103.86.99.100"]
