# WireGuard Manager for NordVPN (LibreELEC)

A lightweight, high-performance Kodi service addon for **LibreELEC 12+ (Kodi 21 Omega)**. This tool manages WireGuard connections natively via `connmanctl`, providing a faster and more stable experience than traditional OpenVPN-based addons.

## 🚀 Features
*   **Native WireGuard**: Interfaces directly with LibreELEC's network stack.
*   **VPN Watchdog**: Background `systemd` service ensures your connection stays alive and auto-reconnects on drops.
*   **Remote Optimized**: Automatically maps the **Blue Button** and **F11** to trigger the VPN menu from anywhere in Kodi.
*   **Fast Configuration**: Includes a shell script to fetch and regenerate the latest NordVPN server lists via API.
*   **Smart Recovery**: Built-in logic to restore default gateways if a connection is interrupted.

## 📂 Project Structure
*   `main.py`: The primary GUI and logic controller.
*   `resources/lib/setup_helper.py`: Manages keymap installation and system configuration.
*   `resources/lib/vpn_core.py`: Shared logic for systemd services and updates.
*   `resources/lib/service.py`: The "pure" Python background watchdog (OS level).
*   `resources/update_servers.sh`: API helper script for fetching NordVPN configurations.

## 🛠 Installation & Uninstallation
1.  **Install**: Zip the `service.wireguard.manager` folder and use **Install from zip file** in Kodi.
2.  **Setup**: Enter your **NordVPN Token** in settings and run **Update/Regenerate VPN Configs**.
3.  **Uninstall**: ⚠️ **IMPORTANT**: Because the background watchdog runs at the OS level (Systemd), Kodi cannot remove it automatically during a standard uninstall. **You must use the "Factory Reset" button in the addon settings before uninstalling** to fully remove the systemd service and remote keymaps.

## ⌨️ Shortcuts
*   **Blue Button / Teletext Blue**: Opens the VPN Manager menu.
*   **F11**: Opens the VPN Manager menu (for keyboards).
*   **Note**: A **reboot** is required after the first installation to activate these buttons.

## 🛠 Troubleshooting

### 1. Watchdog Status: "Initializing"
If the status check stays on "Initializing," the service is waiting for your router to assign an IP address. It will switch to "Active" automatically once the network is ready.

### 2. Blue Button, F11 does not open the menu
*   **Reboot**: Ensure you have restarted the device after the initial setup dialog.
*   **File Check**: Verify the keymap exists at:  
    `/storage/.kodi/userdata/keymaps/wireguard_manager_key.xml`

### 3. Monitoring Logs (SSH)
Since LibreELEC uses BusyBox, use `awk` for real-time log filtering:
```bash
tail -f /storage/.kodi/temp/kodi.log | awk '/service.wireguard.manager/ {print; fflush()}'

### 4. Manual Cleanup (SSH)
If you uninstalled the addon without performing a **Factory Reset** in the settings, run these commands via SSH to clean your system:
```bash
systemctl stop vpn-watchdog.service
systemctl disable vpn-watchdog.service
rm /storage/.config/system.d/vpn-watchdog.service
rm /storage/.kodi/userdata/keymaps/wireguard_manager_key.xml
systemctl daemon-reload
