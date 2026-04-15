============================================================
   WireGuard Manager for NordVPN (LibreELEC / Pi 5)
============================================================

A lightweight, high-performance Kodi service addon for LibreELEC 12+ (Kodi 21).
This tool manages WireGuard connections natively via the ConnMan network stack.

------------------------------------------------------------
 CORE FEATURES
------------------------------------------------------------
* Native WireGuard: Direct interface with the OS network stack.
* VPN Watchdog: Background systemd service ensures persistence.
* Failover Support: Seamlessly switches VPN between Ethernet and Wi-Fi.
* IPv6 Hardening: Kernel-level blocking to prevent Fritz!Box DNS leaks.
* Remote Optimized: Global F11 keymap for instant menu access.
* Smart Recovery: Automatic gateway restoration on connection drops.

------------------------------------------------------------
 PROJECT STRUCTURE
------------------------------------------------------------
ROOT DIRECTORY

|-- main.py              : Primary GUI and logic controller.
|-- service_startup.py   : Kodi Monitor service (Addon context & Auto-mappings).
|-- addon.xml            : Addon metadata and dependencies.

|-- LICENSE.txt          : Licensing information.
|-- README.txt           : You are here.

RESOURCES/DATA

|-- connman_main.conf    : Network priority config (Ethernet > Wi-Fi).
|-- vpn-watchdog.service : Systemd unit for the background monitor.
|-- template.config      : Base configuration for WireGuard tunnels.

RESOURCES/LIB

|-- service.py           : The "pure" Python OS-level watchdog logic.
|-- reconnect_helper.py  : Bridge script to run vpn_ops inside Kodi.
|-- vpn_ops.py           : Core VPN actions (Connect/Disconnect/State).

|-- network_utils.py     : DNS hardening and IPv6 management.
|-- setup_helper.py      : Automated installation of system files.
|-- logger.py            : Centralized logging for both OS and Kodi.

|-- vpn_menu.py          : UI generation for server lists.
|-- vpn_core.py          : Shared backend logic for API interactions.
|-- service_control.py   : Controls for the background systemd service.

|-- show_codes.py        : Handles NordVPN OAuth2 device pairing.

RESOURCES/SCRIPTS
|-- update_servers.sh    : Shell helper for NordVPN API server fetching.

RESOURCES/KEYMAPS

|-- wireguard_manager_key.xml : Global keymap for F11 remote access.

RESOURCES/MEDIA
|-- icon.png / fanart.jpg     : Addon artwork.
|-- vpn_connected.png         : Status notification icons.

|-- force.png / update.png    : Menu action icons.

------------------------------------------------------------
 MANUAL COMMANDS (SSH)
------------------------------------------------------------
# View Logs:
tail -f /storage/.kodi/temp/kodi.log | grep -iE "wireguard.manager"

# Check Watchdog Status:
systemctl status vpn-watchdog.service

# Check Network Priority:
cat /storage/.config/connman_main.conf

# Check Routing Table:
route -n
============================================================
