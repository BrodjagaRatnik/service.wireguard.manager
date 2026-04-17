# WireGuard Manager for NordVPN (LibreELEC)

A lightweight, high-performance Kodi service addon for **LibreELEC 12+ (Kodi 21 Omega)**. This tool manages WireGuard connections natively via `connmanctl`, providing a faster and more stable experience than traditional OpenVPN-based addons.

## 🚀 Features
*   **Native WireGuard**: Interfaces directly with LibreELEC's network stack for maximum speed.
*   **Raspberry Pi 5 Optimized**: Aggressive timing profile reduces VPN switching time to ~1.0s.
*   **VPN Watchdog**: A standalone background `systemd` service ensures your connection stays alive and auto-reconnects on drops.
*   **Ethernet/Wi-Fi Failover**: Refined logic to seamlessly transition the VPN tunnel and physical interface priority if a cable is pulled.
*   **IPv6 Leak Protection**: Kernel-level hardening and manual `resolv.conf` management prevent DNS leaks.
*   **Remote Optimized**: Automatically maps **F11** to trigger the VPN menu from anywhere in Kodi.
*   **Smart Auto-Mappings**: Connects to specific countries automatically based on the addon or folder you are currently browsing.
*   **SSH Monitoring**: Detailed `PURPOSE` logging for all wait states, visible via standard system logs.

---

## 📂 Project Structure


| File/Folder | Description |
| :--- | :--- |
| **`main.py`** | Primary entry point for the GUI and menu logic. |
| **`service_startup.py`** | Kodi Monitor service handling auto-mappings and UI context checks. |
| **`resources/lib/vpn_config.py`** | **[NEW]** Centralized configuration for all wait times, paths, and DNS fallbacks. |
| **`resources/lib/service.py`** | Bulletproof, standalone background watchdog running at the OS level. |
| **`resources/lib/reconnect_helper.py`** | Bridge script allowing the OS watchdog to trigger Kodi-aware VPN actions. |
| **`resources/lib/vpn_ops.py`** | Core engine for Connect/Disconnect/Status logic with dependency-safe imports. |
| **`resources/lib/setup_helper.py`** | Manages installation of systemd services, keymaps, and configs. |
| **`resources/lib/network_utils.py`** | Hardens system DNS and manages IPv6 kernel states. |
| **`resources/lib/logger.py`** | Centralized logging utility with dynamic version tagging. |
| **`resources/data/`** | Contains `vpn-watchdog.service`, `connman_main.conf`, and tunnel templates. |
| **`resources/update_servers.sh`** | Bash script utilizing NordVPN APIs to fetch and resolve the latest server IPs. |

---

## 🛠 Advanced Tuning
All performance timings are centralized in `resources/lib/vpn_config.py`. Users on high-performance hardware like the **Raspberry Pi 5** can adjust variables like `PROP_SYNC_DELAY` and `OS_RELEASE_DELAY` to achieve near-instantaneous connection swaps.

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

<img src="resources/media/screenshot00002.png" alt="Alt text" width="800">

---

*Created by Doemela*
