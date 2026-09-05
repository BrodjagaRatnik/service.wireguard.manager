[![CodeQL Advanced](https://github.com/BrodjagaRatnik/service.wireguard.manager/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/BrodjagaRatnik/service.wireguard.manager/actions/workflows/codeql.yml)
![Last Commit](https://shields.io/github/last-commit/BrodjagaRatnik/service.wireguard.manager)
![Build Status](https://github.com/BrodjagaRatnik/service.wireguard.manager/actions/workflows/test_addon.yml/badge.svg)
---
# WireGuard VPN Manager
![Release](https://img.shields.io/github/v/release/BrodjagaRatnik/service.wireguard.manager)
![Size](https://img.shields.io/github/repo-size/BrodjagaRatnik/service.wireguard.manager)
![License](https://img.shields.io/github/license/BrodjagaRatnik/service.wireguard.manager)
---

A lightweight, high-performance Kodi service addon for **LibreELEC 11, 12, and 13+**. Built entirely in pure Python with a memory-isolated, lazy-loaded architecture, this tool manages WireGuard connections natively via `connmanctl`. It features a zero-leak, kernel-level firewall **killswitch** with automatic LAN whitelisting to guarantee complete data privacy if the tunnel drops. Fully architecture-independent, it provides a rock-solid experience that runs flawlessly on everything from legacy **Raspberry Pi 2 / 3b** hardware to modern **Raspberry Pi 4 / 5** and **x86 HTPC** systems.

> [!IMPORTANT]
> ### 🐧 Looking for the Linux Version?
> If you are running a standalone Linux distribution (Debian, Mint, Ubuntu, LMDE), use the dedicated repository here:  
> 👉 **[service.wireguard.manager.linux](https://github.com/BrodjagaRatnik/service.wireguard.manager.linux)**  
> *(Note: The standalone Linux edition is currently in an active debugging stage. Distro testers are welcome!)*

## 📖 Quick Links
For detailed instructions for this Add-on, please visit our **[Wiki](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki)**:
*   **[🚀 Features](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Features)**
*   **[🔑 How to get your NordVPN Token](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/How-to-get-your-NordVPN-Token)**
*   **[🛠️ How‐To Importing Custom WireGuard Configurations](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/How%E2%80%90To-Importing-Custom-WireGuard-Configurations)**
*   **[🇨🇭 Importing ProtonVPN via Custom Mode](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Importing-ProtonVPN-via-Custom-Mode)**
*   **[🛠 Installation & Setup](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Installation-&-Setup)**
*   **[📟 Live-Terminal-Diagnostics](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Live-Terminal-Diagnostics)**
*   **[💻 Manual Commands, Cleanup](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Manual-Commands%2C-Cleanup)**
*   **[📂 Project Structure](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Project-Structure)**
*   **[⚙️ Settings-Explained](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Settings-Explained)**
*   **[⌨️ Shortcuts & Logs](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Shortcuts-&-Logs)**
*   **[🆘 Troubleshooting & Manual Cleanup](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Troubleshooting-&-Manual-Cleanup)**
*   **[🛑 Upstream ConnMan FD Leak & Automated Mitigation Guide](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Upstream-ConnMan-FD-Leak-%26-Automated-Mitigation-Guide)**
*   **[📘 VPN Provider Integration Policy](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/VPN-Provider-Integration-Policy)**
*   **[🔀 WireGuard Dual Bucket Routing Optimization](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/WireGuard-Dual-Bucket-Routing-Optimization)**
*   **[📡 WireGuard Provider Architecture & Video Mapping Constraints](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/WireGuard-Provider-Architecture-&-Constraints)**

## 📥 Fast Installation (via Doemela Repo)
If you already know what you're doing, grab the repository installer here:  
**[📦 Download Doemela Repo ZIP](https://github.com/BrodjagaRatnik/doemela-kodi-repo/tree/main/zips/repository.doemela)**

> **Tip:** Installing via the Repository is the recommended method. It ensures you receive **automatic updates** for bug fixes and new Raspberry Pi 5 performance optimizations as soon as they are released.

<img src="resources/media/screenshot00002.jpg" alt="Alt text" width="800">

---
*Created by Doemela*
