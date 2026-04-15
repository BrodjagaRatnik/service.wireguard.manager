# WireGuard Manager for NordVPN (LibreELEC)

A lightweight, high-performance Kodi service addon for **LibreELEC 12+ (Kodi 21 Omega)**. This tool manages WireGuard connections natively via `connmanctl`, providing a faster and more stable experience than traditional OpenVPN-based addons.

## 🚀 Features
*   **Native WireGuard**: Interfaces directly with LibreELEC's network stack for maximum speed.
*   **VPN Watchdog**: A background `systemd` service ensures your connection stays alive and auto-reconnects on drops.
*   **Ethernet/Wi-Fi Failover**: Built-in logic to seamlessly transition the VPN tunnel if a cable is pulled.
*   **IPv6 Leak Protection**: Kernel-level hardening prevents DNS leaks.
*   **Remote Optimized**: Automatically maps **F11** to trigger the VPN menu from anywhere in Kodi.
*   **Smart Auto-Mappings**: Connects to specific countries automatically based on the addon you are currently browsing.

---

## 📂 Project Structure
| File/Folder | Description |
| :--- | :--- |
| **`main.py`** | Primary entry point for the GUI and menu logic. |
| **`service_startup.py`** | Kodi Monitor service handling auto-mappings and UI context checks. |
| **`resources/lib/service.py`** | The "pure" Python background watchdog running at the OS level. |
| **`resources/lib/reconnect_helper.py`** | Bridge script allowing the OS watchdog to trigger Kodi-aware VPN actions. |
| **`resources/lib/vpn_ops.py`** | Core engine for Connect/Disconnect/Status logic. |
| **`resources/lib/setup_helper.py`** | Manages installation of systemd services, keymaps, and configs. |
| **`resources/lib/network_utils.py`** | Hardens system DNS and manages IPv6 kernel states. |
| **`resources/lib/logger.py`** | Centralized logging utility compatible with both Kodi and Systemd. |
| **`resources/data/`** | Contains `vpn-watchdog.service`, `connman_main.conf`, and tunnel templates. |
| **`resources/update_servers.sh`** | Bash script utilizing NordVPN APIs to fetch the latest server configurations. |

---

## 📖 Quick Links
For detailed instructions for this Add-on, please visit our **[Wiki](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki)**:

*   **[🛠 Editing Installation & Setup](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Installation-&-Setup)**
*   **[⌨️ Shortcuts & Logs](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Shortcuts-&-Logs)**
*   **[🆘 Troubleshooting & Manual Cleanup](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Troubleshooting-&-Manual-Cleanup)**

---

## 📦 Quick Download
If you already know what you're doing, grab the installer here:
[**Download Doemela Repo ZIP**](https://github.com/BrodjagaRatnik/doemela-kodi-repo/tree/main/zips/repository.doemela).

---
*Created by Doemela*
