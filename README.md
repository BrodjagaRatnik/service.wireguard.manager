[![Kodi Addon Checker](https://github.com/BrodjagaRatnik/service.wireguard.manager/actions/workflows/kodi-check.yml/badge.svg)](https://github.com/BrodjagaRatnik/service.wireguard.manager/actions)
# WireGuard Manager for NordVPN (LibreELEC)

A lightweight, high-performance Kodi service addon for **LibreELEC 12+ (Kodi 21 Omega)**. This tool manages WireGuard connections natively via `connmanctl`, providing a faster and more stable experience than traditional OpenVPN-based addons.

## 🚀 Features
*   **Native WireGuard**: Interfaces directly with LibreELEC's network stack.
*   **VPN Watchdog**: Background `systemd` service ensures your connection stays alive and auto-reconnects on drops.
*   **Remote Optimized**: Automatically maps the **F11** to trigger the VPN menu from anywhere in Kodi.
*   **Fast Configuration**: Includes a shell script to fetch and regenerate the latest NordVPN server lists via API.
*   **Smart Recovery**: Built-in logic to restore default gateways if a connection is interrupted.

## 📂 Project Structure
*   `main.py`: The primary GUI and logic controller.
*   `resources/lib/setup_helper.py`: Manages keymap installation and system configuration.
*   `resources/lib/vpn_core.py`: Shared logic for systemd services and updates.
*   `resources/lib/service.py`: The "pure" Python background watchdog (OS level).
*   `resources/update_servers.sh`: API helper script for fetching NordVPN configurations.

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
