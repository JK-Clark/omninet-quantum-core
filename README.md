# OmniNet Quantum-Core

```
  ██████╗ ███╗   ███╗███╗   ██╗██╗███╗   ██╗███████╗████████╗
  ██╔═══██╗████╗ ████║████╗  ██║██║████╗  ██║██╔════╝╚══██╔══╝
  ██║   ██║██╔████╔██║██╔██╗ ██║██║██╔██╗ ██║█████╗     ██║
  ██║   ██║██║╚██╔╝██║██║╚██╗██║██║██║╚██╗██║██╔══╝     ██║
  ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║██║ ╚████║███████╗   ██║
   ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝
                  Quantum-Core Network Orchestrator
```

**Universal Network Orchestrator** targeting the banking sector and SMEs — with post-quantum cryptography, AI failure prediction, and zero-touch topology discovery.

---

## Quick Start

```bash
git clone https://github.com/JK-Clark/omninet-quantum-core.git
cd omninet-quantum-core
docker-compose up --build -d
```

Then open **http://localhost** and follow the 5-step setup wizard.

---

## Architecture

```
Internet
    │
    ▼
┌─────────┐      ┌────────────┐      ┌──────────────┐
│  Nginx  │─────▶│  Frontend  │      │   Grafana    │
│ (proxy) │      │ React+Vite │      │  Prometheus  │
└────┬────┘      └────────────┘      └──────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│                FastAPI Backend                       │
│  ┌───────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Quantum   │  │  AI      │  │  License         │ │
│  │ Engine    │  │ Predictor│  │  Manager         │ │
│  │ (Kyber)   │  │ (IsoForest│  │  (TRIAL/COM/BANK│ │
│  └───────────┘  └──────────┘  └──────────────────┘ │
│  ┌───────────┐  ┌──────────┐                        │
│  │ Network   │  │  WebSocket│                       │
│  │ Discovery │  │  /ws/topo │                       │
│  │ (Netmiko) │  └──────────┘                        │
│  └───────────┘                                      │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         ▼                            ▼
    ┌──────────┐                ┌──────────┐
    │PostgreSQL│                │  Redis   │
    └──────────┘                └──────────┘
```

---

## Feature Matrix

| Feature                    | Trial       | Community   | Bank        |
|---------------------------|-------------|-------------|-------------|
| Device limit              | 10          | Unlimited   | Unlimited   |
| Access duration           | 7 days      | Perpetual   | Perpetual   |
| Topology auto-discovery   | ✓           | ✓           | ✓           |
| Real-time topology map    | ✓           | ✓           | ✓           |
| Alerts                    | ✗           | ✓           | ✓           |
| AI failure prediction     | ✗           | ✗           | ✓           |
| Post-quantum AAA          | ✗           | ✗           | ✓           |
| Priority support          | ✗           | ✗           | ✓           |

---

## API Reference

| Method | Endpoint                        | Description                      |
|--------|---------------------------------|----------------------------------|
| POST   | `/api/auth/register`            | Register new user                |
| POST   | `/api/auth/login`               | Login, receive JWT tokens        |
| POST   | `/api/auth/refresh`             | Refresh access token             |
| GET    | `/api/devices`                  | List all devices                 |
| POST   | `/api/devices`                  | Manually add device              |
| GET    | `/api/devices/{id}`             | Get device detail                |
| DELETE | `/api/devices/{id}`             | Remove device                    |
| POST   | `/api/topology/discover`        | Trigger LLDP/CDP auto-discovery  |
| GET    | `/api/topology/map`             | Get full topology graph          |
| GET    | `/api/ai/predict/{device_id}`   | AI failure prediction [Bank]     |
| POST   | `/api/ai/train/{device_id}`     | Train model on history [Bank]    |
| POST   | `/api/license/activate`         | Activate license key             |
| GET    | `/api/license/status`           | Check current license status     |
| WS     | `/ws/topology`                  | Real-time topology stream        |
| GET    | `/metrics`                      | Prometheus metrics               |

All REST responses use the envelope format:
```json
{ "status": "ok", "data": { ... }, "meta": { ... } }
```

---

## Security — Post-Quantum Cryptography

OmniNet implements a **Kyber-512 simulation** for AAA (Authentication, Authorization, Accounting) using NaCl (libsodium) primitives:

- **Key Encapsulation (KEM)**: X25519 Curve25519 DH simulates Kyber-512 lattice KEM
- **Signing**: Ed25519 simulates Dilithium post-quantum signatures
- **AAA Token**: HMAC-SHA256 binding of shared secret to user identity
- **Upgrade path**: Swap `quantum_engine.py` for a native `liboqs` binding when available

---

## Internationalization

Language is selectable from the UI (persisted in localStorage):
- 🇬🇧 English (`en`)
- 🇫🇷 Français (`fr`)
- 🇮🇳 हिन्दी (`hi`)
- 🇰🇷 한국어 (`ko`)

---

## Supported Network Vendors

| Vendor      | Device Type     | Protocol   |
|-------------|-----------------|------------|
| Cisco       | `cisco_ios`     | LLDP + CDP |
| Cisco NX-OS | `cisco_nxos`    | LLDP + CDP |
| Arista      | `arista_eos`    | LLDP       |
| Juniper     | `juniper_junos` | LLDP       |

---

## Roadmap

- [ ] Native `liboqs` Kyber-512 integration (when stable Python bindings released)
- [ ] SNMP trap ingestion for real-time fault alerts
- [ ] Multi-tenant enterprise mode with RBAC
- [ ] Kubernetes Helm chart deployment
- [ ] REST API v2 with GraphQL gateway

---

## License

Proprietary — OmniNet Quantum-Core. All rights reserved.
