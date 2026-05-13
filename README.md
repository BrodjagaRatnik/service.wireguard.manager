![Release](https://img.shields.io/github/v/release/BrodjagaRatnik/service.wireguard.manager)
![Size](https://img.shields.io/github/repo-size/BrodjagaRatnik/service.wireguard.manager)
![Last Commit](https://img.shields.io/github/last-commit/BrodjagaRatnik/service.wireguard.manager)
![Build Status](https://github.com/BrodjagaRatnik/service.wireguard.manager/actions/workflows/test_addon.yml/badge.svg)
---
# WireGuard VPN Manager (LibreELEC)
![Kodi](https://img.shields.io/badge/Kodi-21.3%20(Omega)-blue?logo=kodi)
![Python](https://img.shields.io/badge/python-3.12-blue?logo=python)
![LibreELEC](https://img.shields.io/badge/LibreELEC-12.2.1-blue)
![Linux Kernel](https://img.shields.io/badge/Linux-6.16-blue?logo=linux&logoColor=white)
![License](https://img.shields.io/github/license/BrodjagaRatnik/service.wireguard.manager)
---
A lightweight, high-performance Kodi service addon for **LibreELEC 12+ (Kodi 21 Omega)**. This tool manages WireGuard connections natively via `connmanctl`, providing a faster and more stable experience than traditional OpenVPN-based addons.

## 🚀 Features
*   **Multi-Provider Architecture**: Native, integrated routing support across NordVPN, Private Internet Access (PIA), and Custom manual profile frameworks.
*   **Dynamic PIA WireGuard Handshake**: Features an authenticated API endpoint handshake layer that automatically registers keys and parses split PGP signature tokens live.
*   **Native WireGuard Integration**: Interfaces directly with LibreELEC's network stack for maximum speed and minimal routing overhead.
*   **Raspberry Pi 5 & 4 Optimized**: Specifically tuned timing profiles and platform-specific network delay detection reduce VPN switching and recovery times for both Pi 4 and Pi 5.
*   **Live API Country Selector**: Replaced manual configuration ID inputs with a live, provider-driven multi-select context menu interface.
*   **Space-Safe Service Matching**: Space-to-underscore string normalization ensures 100% accurate tracking searches against complex ConnMan network names.
*   **Automated Credential Ingest**: Separate, validated import loops read plaintext `.txt` or `.key` data files, execute instant Base64 encryption processing, and run auto-updates.
*   **Asynchronous State Shield**: Centralized tracking flags inside `/tmp` prevent racing conditions and separate automated video plugin mapping sessions from manual menu overrides.
*   **Smart Auto-Mappings**: Dynamically switches VPN locations based on the specific Kodi addon or folder currently being browsed.
*   **1Hz Physical Watchdog**: A standalone `systemd` service monitors hardware carrier status every second for near-instant detection of cable pulls or link loss.
*   **Auto-Healing Failover**: Detects physical interface changes (Ethernet ⇆ Wi-Fi) and automatically resets retry budgets to ensure seamless recovery.
*   **Stabilized Watchdog Settle**: Fine-tuned delay metrics stop infinite connection loops during profile switches by allowing the interface routing table to normalize.
*   **Silent Transition Engine**: Seamless background profile switching handles link changes quietly to prevent stream stuttering or player window failures.
*   **Aggressive Stream Recovery**: Automatically kills "frozen" video players during network blackouts to prevent UI hangs and provide immediate error feedback.
*   **Intelligent Throttling**: Implements a "Safety Fuse" logic that stands down after 10 failed reconnection attempts to preserve system resources and API provider query limits.
*   **High-Visibility Alerts**: Enhanced Kodi notifications featuring art assets, ARGB color formatting, custom audio cues (`networkerror.wav`), and persistent on-screen menu saving reminders.
*   **IPv6 Leak Protection**: Kernel-level hardening and dynamic DNS management prevent data leaks during VPN transitions.
*   **Remote Optimized**: Automatically maps **F11** to trigger the VPN menu instantly from anywhere inside Kodi.

## 📂 Project Structure
| File/Folder | Description |
| :--- | :--- |
| **`main.py`** | Primary entry point for executing user-triggered GUI configurations and settings hooks. |
| **`service_startup.py`** | Background system listener initializing standard service routines. |
| **`resources/settings.xml`** | Storage schema defining provider profiles, mapping settings, and credential parameters. |
| **`resources/keymaps/`** | Contains custom XML structural actions mapping global remote key inputs (F11) directly to the GUI menu. |
| **`resources/language/`** | Core internationalization module managing clean layout strings and dynamic labels (`strings.po`). |
| **`resources/lib/list_assets.py`** | Slot manager wizard pairing active ConnMan connection handles directly to target video plugins. |
| **`resources/lib/service_launcher.py`** | The "Brain": Manages the background monitor thread loop, auto-mapping tracking, and Home window escape focus. |
| **`resources/lib/vpn_ops.py`** | Core engine coordinating system handshakes, active profile caching, and dynamic connection sequences. |
| **`resources/lib/vpn_config.py`** | Centralized constants mapping provider metadata dictionaries, timeouts, delay timers, and layout constants. |
| **`resources/lib/network_utils.py`** | Network controller toggling ConnMan kernel states to secure DNS paths and prevent IPv6 leak issues. |
| **`resources/lib/logger.py`** | High-visibility debugging output processor using dynamic version tags and standalone system execution compatibility. |
| **`resources/lib/providers/`** | Isolated package handling provider logic: `nordvpn.py` (Tokens), `pia.py` (Credentials/Handshakes), and `custom.py` (.config file parser). |
| **`resources/scripts/update_vpn.py`** | **[UPDATED]** Unified standalone update automation pipeline querying endpoint server lists and writing active WireGuard layouts. |
| **`resources/data/`** | Contains static core configurations for `vpn-watchdog.service`, `connman_main.conf`, and profile setup templates. |
| **`resources/media/`** | Repository asset bank for UI design elements, visual indicators, error warning popups, and custom warning wave sounds. |

## 🛠 Advanced Tuning
All performance timings are centralized in `resources/lib/vpn_config.py`. Users on high-performance hardware like the **Raspberry Pi 5** can adjust variables like `PROP_SYNC_DELAY` and `OS_RELEASE_DELAY` to achieve near-instantaneous connection swaps.

## 📖 Quick Links
For detailed instructions for this Add-on, please visit our **[Wiki](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki)**:
*   **[🔑 How to get your NordVPN Token](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/How-to-get-your-NordVPN-Token)**
*   **[🛠 Editing Installation & Setup](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Installation-&-Setup)**
*   **[📟 Live-Terminal-Diagnostics](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Live-Terminal-Diagnostics).**
*   **[⚙️ Settings-Explained](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Settings-Explained)**
*   **[⌨️ Shortcuts & Logs](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Shortcuts-&-Logs)**
*   **[🆘 Troubleshooting & Manual Cleanup](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Troubleshooting-&-Manual-Cleanup)**

## 📥 Fast Installation (via Doemela Repo)
If you already know what you're doing, grab the repository installer here:  
**[📦 Download Doemela Repo ZIP](https://github.com/BrodjagaRatnik/doemela-kodi-repo/tree/main/zips/repository.doemela)**

### Step 1: Install the Repository
1. Download the **Doemela Repo ZIP** file to your device (or use a USB stick).
2. Open Kodi and navigate to **Add-ons**.
3. Click the **Box Icon** (Add-on Browser) in the top-left corner.
4. Select **Install from zip file**.
   * *If prompted, click 'Settings' and enable 'Unknown Sources', then go back.*
5. Locate and select the `repository.doemela-x.x.x.zip` file.
6. Wait for the **"Add-on installed"** notification.

### Step 2: Install WireGuard VPN Manager
1. While still in the Add-on Browser, select **Install from repository**.
2. Choose the **Doemela Repo**.
3. Navigate to **Program add-ons** > **WireGuard VPN Manager**.
4. Select **Install**.
5. Once the installation is complete, the **Setup Wizard** will launch automatically to guide you through the initial configuration and token import.
> **Tip:** Installing via the Repository is the recommended method. It ensures you receive **automatic updates** for bug fixes and new Raspberry Pi 5 performance optimizations as soon as they are released.
---
<img src="resources/media/screenshot00002.jpg" alt="Alt text" width="800">

---
*Created by Doemela*
