# SECURITY — OmniNet Quantum-Core

> (c) 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.

---

## Vulnerability Disclosure Policy

We take the security of OmniNet Quantum-Core seriously.
If you discover a security vulnerability, please **do not** open a public GitHub issue.
Instead, report it privately:

- **Email:** security@genio-elite.com
- **Subject:** `[SECURITY] OmniNet Quantum-Core — <brief description>`
- **PGP:** Available on request

We will acknowledge receipt within **48 hours** and provide an estimated timeline for remediation within **7 business days**.
Public disclosure is coordinated after a patch is available (responsible disclosure).

---

## Targeted Compliance Standards

| Standard | Status | Notes |
|---|---|---|
| **DORA** (EU Digital Operational Resilience Act) | ✅ In progress | Incident response, integrity monitoring, audit trails |
| **PCI-DSS v4.0** | ✅ In progress | TLS 1.2+, lockout, audit log, no default credentials in prod |
| **ISO 27001:2022** | ✅ In progress | ISMS controls: access management, crypto, logging |
| **NIST FIPS 203** | ✅ Implemented | CRYSTALS-Kyber-512 via `kyber-py` library |
| **OWASP Top 10** | ✅ Implemented | Security headers, rate limiting, CORS, input validation |

---

## Security Architecture

```
Internet
   │
   ▼
[Nginx TLS 1.2/1.3]  ← Port 443 (HTTP→HTTPS redirect on port 80)
   │  Security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
   ▼
[FastAPI + Uvicorn]  ← Port 8000 (internal only)
   │  JWT auth, bcrypt, rate limiting (SlowAPI), security headers middleware
   │  Account lockout (Redis, 5 attempts / 15 min TTL)
   │  Audit log (all auth events, device changes)
   ▼
[PostgreSQL 15]      ← Encrypted credentials, license HMAC integrity
[Redis 7]            ← Session cache, lockout counters
```

### Cryptographic components

| Component | Algorithm | Library |
|---|---|---|
| Post-quantum key exchange | CRYSTALS-Kyber-512 (NIST FIPS 203) | `kyber-py` 1.2.0 |
| JWT signing | HMAC-SHA256 (HS256) | `python-jose` |
| Password hashing | bcrypt (cost factor 12) | `passlib[bcrypt]` |
| License integrity | HMAC-SHA256 | Python `hmac` stdlib |
| File integrity | SHA-256 | Python `hashlib` stdlib |
| TLS | TLS 1.2 / TLS 1.3 | Nginx + OpenSSL |

---

## Key Rotation Procedure

### JWT Secret Key (`SECRET_KEY`)

1. Generate a new key: `python3 -c "import secrets; print(secrets.token_hex(64))"`
2. Update `SECRET_KEY` in `.env`
3. Restart the backend: `docker compose restart app`
4. All existing tokens are immediately invalidated — users must log in again.

### License HMAC Secret (`LICENSE_SECRET`)

1. Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"`
2. Update `LICENSE_SECRET` in `.env`
3. **Re-generate all license HMAC hashes** via the admin API before restarting.
4. Restart: `docker compose restart app`

### TLS Certificates

#### Self-signed (development / staging)
Certificates are auto-generated at container start in `/etc/nginx/certs/`.
They are valid for 365 days. Regenerate by removing the Docker volume:
```bash
docker compose down
docker volume rm omninet-quantum-core_nginx_certs
docker compose up -d
```

#### Let's Encrypt (production)
```bash
# Mount real certificates via docker-compose.yml override:
# volumes:
#   - /etc/letsencrypt/live/yourdomain.com/fullchain.pem:/etc/nginx/certs/server.crt:ro
#   - /etc/letsencrypt/live/yourdomain.com/privkey.pem:/etc/nginx/certs/server.key:ro
#
# Renew with Certbot (example):
certbot renew --quiet
docker compose restart nginx
```

### Admin Password

1. Log in as admin and navigate to **Settings → Change Password**.
2. Or update `ADMIN_DEFAULT_PASSWORD` in `.env` and restart.
3. If the admin account already exists, use the API:
   `PATCH /api/users/{id}` with `{"password": "<new_password>"}` (admin token required).

---

## Security Controls Summary

| Control | Implementation |
|---|---|
| Authentication | JWT Bearer tokens (24h expiry), bcrypt passwords |
| Account lockout | 5 failed attempts → 15-minute lockout (Redis) |
| User enumeration prevention | Generic `"Invalid credentials"` response for login failures |
| Rate limiting | SlowAPI: 5 req/min on `/api/license/activate` |
| HTTPS / TLS | Nginx TLS 1.2+, self-signed certs in dev, Let's Encrypt in prod |
| Security headers | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection |
| Audit trail | All auth events and resource mutations logged to PostgreSQL |
| File integrity | SHA-256 manifest generated at first boot, verified on subsequent boots |
| License integrity | HMAC-SHA256 per-record integrity hashes |
| Secrets management | All secrets via environment variables, no hardcoded secrets in prod |
| Dependency scanning | `pip-audit` + `npm audit` via weekly GitHub Actions workflow |
| Secret scanning | Gitleaks via GitHub Actions on every push to `main` |
| SAST | Bandit static analysis on Python code via CI |

---

## Security Contact

**Genio Elite — Security Team**
Email: security@genio-elite.com
