![Last Commit](https://shields.io/github/last-commit/BrodjagaRatnik/service.wireguard.manager)
![License](https://img.shields.io/github/license/BrodjagaRatnik/service.wireguard.manager)
# WireGuard VPN Manager [LE13-DEV]
## ⚡ LibreELEC 13 Development Staging
LibreELEC 13 drops the old `ConnMan` D-Bus layers and migrates the base system infrastructure over to `NetworkManager` (`nmcli`). This architecture shift directly impacts our virtual interface allocation, routing tables, and hooks. To prevent breaking functional production deployments on LE12, all development builds tracking these core system mutations are isolated here.
```text
📁 service.wireguard.manager (Branch: LE13)
├── 📂 alpha/         <-- Raw system engine tracking. Highly volatile. Expect tracebacks.
├── 📂 beta/          <-- Feature-complete binaries targeting native NetworkManager implementations.
└── 📂 going_silver/  <-- Polished release candidates before mainline master deployment.
```
### 📟 Real-Time Diagnostics, Log Submission & Shell Verification
If you are deploying standalone builds from this branch onto a live LE13 runtime environment, do not submit surface-level bug reports. Inspect the interface behavior via the terminal and isolate the routing faults before logging an issue:
```bash
# Monitor the system network engine logging live
journalctl -u NetworkManager -f
```
```bash
# Verify active topology and interface mapping
nmcli connection show --active
```
```bash
# Inspect interface state if a DHCP lease or key rotation drops the tunnel
nmcli device status
```
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
(journalctl -u vpn-watchdog.service -n 50; journalctl -u NetworkManager -n 50; nmcli connection show --active; grep -i "service.wireguard.manager" /storage/.kodi/temp/kodi.log) | pastebinit
```
When logging a routing collision or unhandled exception, do not paste raw terminal walls. Execute **Diagnostics & Log Submission** to dump your combined watchdog journal and Kodi runtime logs straight to `pastebinit`. Drop the resulting URL directly into the issue tracker, in private [Doemela](https://forum.libreelec.tv/core/user/33834-doemela/) or on our [forum](https://forum.libreelec.tv/thread/30422-wireguard-vpn-manager/).

---
*Created by Doemela*
