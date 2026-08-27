# WireGuard VPN Manager — Roadmap

> **Current Version:** v1.5.3+ | **Last Updated:** August 2026
> **Maintainer:** @BrodjagaRatnik (Doemela)

---

## ✅ Completed (Q3 2026)

### Core Features
| Item | Status | Verwijzing |
|------|--------|------------|
| Full Kodi GUI implementation | ✅ Done | Wiki Home |
| ConnMan FD leak mitigation (systemd + upstream patch) | ✅ Done | [Mitigation Guide](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Upstream-ConnMan-FD-Leak-%26-Automated-Mitigation-Guide) |
| LibreELEC 11/12/13+ certification | ✅ Done | Wiki Home |
| Hardware testing (Pi 2/3b/4/5 + x86 HTPC) | ✅ Done | Community testers |
| Auto-update system via Doemela Repo | ✅ Done | [Installation & Setup](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Installation-%26-Setup) |
| Backup/restore via Kodi system backups | ✅ Done | Native Kodi feature |
| Universal custom mode (all providers) | ✅ Done | [VPN Provider Policy](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/VPN-Provider-Integration-Policy) |

### Documentation
| Item | Status | Verwijzing |
|------|--------|------------|
| ProtonVPN custom mode guide | ✅ Done | [Importing ProtonVPN via Custom Mode](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/Importing-ProtonVPN-via-Custom-Mode) |
| Architecture & hardening documentation | ✅ Done | Discussion #5 |
| Troubleshooting & cleanup guides | ✅ Done | Wiki |

---

## 🚀 Medium-Term (Q4 2026 – Q1 2027)

### Dual Backend Architecture (Priority #1)
- [ ] **LMDE (Linux Mint Debian Edition) support** — Alpha release
- [ ] Shared core module extraction (platform-agnostic WireGuard logic)
- [ ] Platform-specific service adapters (ConnMan vs. NetworkManager)
- [ ] Cross-platform build pipeline setup
- [ ] Documentation for dual-backend deployment

### Upstream Engagement
- [ ] Track ConnMan FD leak patch status (patchwork.kernel.org)
- [ ] Follow-up with ConnMan maintainers if needed (connman@lists.linux.dev)
- [ ] Submit additional improvements if discovered

### Community Growth
- [ ] Monitor Discussion requests for feature expansions
- [ ] Collect feedback on Dual Backend beta releases
- [ ] Optional: Community translations (NL/DE/FR/etc.)

---

## ⚪ On-Demand (Depends on User/Provider Requests)

### Provider Integrations
- ⚪ **Native provider integration** — Only if:
  - Significant user demand (multiple requests in Discussions)
  - Provider partnership request
  - Provider-specific API requires special handling

> **Current Philosophy:** Universal custom mode works for all providers without per-provider maintenance. Native integrations are considered only if specifically requested.

### Platform Expansion
- ⚪ Android TV / Fire TV assessment — Only if community shows interest
- ⚪ Generic Linux desktop support — Only if LMDE proves successful

---

## 📊 Milestone Tracking

| Milestone | Target | Status | Notes |
|-----------|--------|--------|-------|
| LibreELEC Full Certification | Q3 2026 | ✅ Done | All versions tested |
| Dual Backend (LMDE) Alpha | Q4 2026/Q1 2027 | ⚪ Planned | Time-dependent (single maintainer) |
| Upstream Patch Merge | TBD | ⏳ Pending | ConnMan review cycle |
| Native Provider Integration | TBD | ⚪ On-Demand | No current requests |

---

## 💡 Developer Notes

### Priority Philosophy

Stability → Features → Expansion

> Security patches > Performance improvements > New features

### Time Allocation
- Single maintainer — feature development depends on available time
- Critical security/stability patches take precedence
- Dual Backend development is time-dependent (not scheduled)

### Community Feedback
- Discussion board drives feature prioritization
- Repeated requests influence roadmap adjustments
- No guaranteed timelines for on-demand features

---

## 🔧 Technical Context

### ConnMan FD Leak Mitigation
- **Workaround:** Active in v1.5.3+ via systemd LimitNOFILE=512 ceiling
- **Upstream:** Patch submitted (August 2026, kasuta@riseup.net)
- **Status:** Forward-compatible — workaround remains useful even after upstream fix

### Provider Support Model
- **Custom Mode:** All providers via standard WireGuard configs
- **Native Integration:** No planned development unless requested
- **Policy Documented:** [VPN Provider Integration Policy](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki/VPN-Provider-Integration-Policy)

---

## 🤝 Contributing

Interested in helping? Check out:

| Resource | Link |
|----------|------|
| Discussion Board (Q&A, Ideas) | [Discussions](https://github.com/BrodjagaRatnik/service.wireguard.manager/discussions) |
| Documentation Wiki | [Wiki](https://github.com/BrodjagaRatnik/service.wireguard.manager/wiki) |
| Issues & Bugs | [Issues](https://github.com/BrodjagaRatnik/service.wireguard.manager/issues) |
| Code of Conduct | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |

> **Note:** Single-maintainer project — responses may be delayed. Community contributions welcome!

---

**License:** [See LICENSE](LICENSE)
**Contact:** Discussions tab or project email
**Downloads:** [Doemela Repo](https://github.com/BrodjagaRatnik/doemela-kodi-repo)
