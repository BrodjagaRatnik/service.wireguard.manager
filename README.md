![Last Commit](https://shields.io/github/last-commit/BrodjagaRatnik/service.wireguard.manager)
![License](https://img.shields.io/github/license/BrodjagaRatnik/service.wireguard.manager)
## ⚡ WireGuard VPN Manager Development Testing Staging
### 🧪 Staging Area & Test Deployments
Welcome to the development and staging repository for the **Kodi WireGuard VPN Manager**. This staging area handles active routing optimizations, core network stability patches, and dynamic IPv6 DNS leak protections specifically tailored for LibreELEC 12/13 environments on Raspberry Pi 4 and Raspberry Pi 5 hardware.

---
### 📥 Download Testing Folders
To test the upcoming development changes, download or sync the respective testing directory based on your current validation environment:
```text
📁 service.wireguard.manager
├── 📂 alpha/         <-- Raw system engine tracking. Highly volatile. Expect tracebacks.
├── 📂 beta/          <-- Feature-complete binaries targeting native NetworkManager implementations.
└── 📂 going_silver/  <-- Polished release candidates before mainline master deployment.
```
---
### 📟 Real-Time Diagnostics, Log Submission & Shell Verification
If you are deploying standalone builds from this branch onto a live runtime environment, do not submit surface-level bug reports. Inspect the interface behavior via the terminal and isolate the routing faults before logging an issue:
```bash
# Stream watchdog service mutations live from point-of-execution
journalctl -u vpn-watchdog.service -f -n 0
```
```bash
# Intercept and isolate active addon logs inside the Kodi runtime environment
tail -f /storage/.kodi/temp/kodi.log | grep -iE "service.wireguard.manager"
```
#### How to submit logs:
```bash
# Compile system + application logs sequentially and generate a paste link
(journalctl -u vpn-watchdog.service -n 50; grep -i "service.wireguard.manager" /storage/.kodi/temp/kodi.log) | pastebinit
```
When logging a routing collision or unhandled exception, do not paste raw terminal walls. Execute **Diagnostics & Log Submission** to dump your combined watchdog journal and Kodi runtime logs straight to `pastebinit`. Drop the resulting URL directly into the issue tracker, in private [Doemela](https://forum.libreelec.tv/core/user/33834-doemela/) or on our [forum](https://forum.libreelec.tv/thread/30422-wireguard-vpn-manager/).

---
*Created by Doemela*
