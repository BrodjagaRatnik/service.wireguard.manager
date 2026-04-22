''' ./resources/lib/vpn_config.py '''
''' VPN Timing Constants Optimized for Pi 5 - All values in milliseconds (ms) '''
# --- vpn_ops.py ---
# Tiny pause after writing a status change to Kodi’s internal memory (Properties).
PROP_SYNC_DELAY = 100
PROP_SYNC_PURPOSE = "Syncing Kodi properties to prevent service conflict"
# The "Letting Go" timer. It waits 1 full second after telling the system to shut down the VPN. ~600-1000ms (Interface cleanup)
OS_RELEASE_DELAY = 1000
OS_RELEASE_PURPOSE = "Waiting for Kernel to destroy wg0 interface"
# Loop interval for checking VPN status (checks every 0.3s instead of a single long sleep).
CONN_POLL_INTERVAL = 300
CONN_POLL_PURPOSE = "Polling Connman for WireGuard handshake"

# --- service.py ---
# Gap between "Start VPN" command and the first "Test VPN" command.
ROUTE_PROP_DELAY = 200
ROUTE_PROP_PURPOSE = "Waiting for routing table/DNS propagation"
# Detection Speed: Check hardware state every 1 second. (How often to check link)
WATCHDOG_HEARTBEAT = 1000
# Cooling period after a physical change or recovery trigger to prevent double-starts. (Cooldown after a fix)
WATCHDOG_SETTLE_DELAY = 15000
WATCHDOG_SETTLE_PURPOSE = "Physical interface swap/priority cooling"
# Anti-flap buffer if only the tunnel (wg0) is missing but internet is fine.
WATCHDOG_RECOVERY_DELAY = 1500
WATCHDOG_RECOVERY_PURPOSE = "Anti-flap tunnel recovery buffer"

# --- reconnect_helper.py ---
# Time to wait for the DHCP server to assign a local IP after a network reset. (Network restoration)
DHCP_RECOVERY_DELAY = 2000
DHCP_RECOVERY_PURPOSE = "Waiting for DHCP server to assign local IP"

# --- service_control.py ---
# Gap between asking Systemd for a state change and verifying it.
SYSTEMD_POLL_DELAY = 300
SYSTEMD_POLL_PURPOSE = "Systemd state transition wait"

# --- vpn_core.py ---
# Buffer to allow Systemd to allocate a PID for a new process.
SERVICE_INIT_DELAY = 400
SERVICE_INIT_PURPOSE = "Systemd PID spawning buffer"
# Visual confirmation delay for notifications.
UI_BUFFER_DELAY = 800
UI_BUFFER_PURPOSE = "Visual confirmation hold for user"

# --- menu_vpn.py ---
# Visual/System confirmation buffer specifically for manual menu actions.
UI_BUFFER_DELAY_MENU = 500 
UI_BUFFER_PURPOSE_MENU = "Visual confirmation hold for user / Property sink"
