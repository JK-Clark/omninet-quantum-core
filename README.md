# OmniNet Quantum-Core

## Universal Network Orchestrator for Banking & SMEs

OmniNet Quantum-Core is a cutting-edge, production-ready network management platform designed specifically for the banking sector and small-to-medium enterprises (SMEs). Leveraging advanced technologies like post-quantum cryptography, predictive AI, and automated topology discovery, it provides secure, intelligent, and scalable network orchestration with zero manual configuration.

### Key Features

#### 🌐 Multi-Language Support (i18n)
- **Default Language**: English
- **Supported Languages**: French (fr), Hindi (hi), Korean (ko)
- Seamless language switching via an intuitive UI selector
- Fully localized interface and documentation

#### 🔍 Auto-Discovery & Real-Time Topology
- **Protocol Support**: LLDP/CDP auto-discovery using Netmiko
- **Visualization**: Interactive, real-time network topology maps built with React Flow
- **Zero Configuration**: Automatically detects and maps network devices without manual input

#### 🔒 Post-Quantum Security & AI-Powered Insights
- **Cryptography**: Simulates Kyber-512 post-quantum encryption for AAA (Authentication, Authorization, Accounting)
- **Predictive AI**: Uses time-series analysis (scikit-learn + statsmodels) to anticipate network failures before they occur
- **Proactive Monitoring**: Alerts and recommendations based on AI-driven predictions

#### 💼 Tiered Licensing System
- **Trial Tier**: 7-day access, max 10 devices, basic topology view
- **Community Tier**: Unlimited devices, topology + alerts, no AI/quantum features
- **Bank Tier**: Full access – AI predictions, post-quantum crypto, priority support
- License validation stored securely in PostgreSQL

### Architecture Overview

OmniNet Quantum-Core runs as a fully containerized microservices architecture:

- **Database**: PostgreSQL 15 for data persistence
- **Backend**: FastAPI (Python) with Uvicorn server, handling API routes, models, and business logic
- **Frontend**: React 18 with Vite, Tailwind CSS, and React Flow for the UI
- **Reverse Proxy**: Nginx for SSL termination and load balancing
- **Monitoring**: Prometheus + Grafana for metrics and dashboards
- **Cache**: Redis for session and data caching
- **Orchestration**: Docker Compose for local development and deployment

All services include health checks, named volumes for persistence, and environment variable injection for configuration.

### Quick Start

#### Prerequisites
- Docker & Docker Compose (latest versions recommended)
- Git

#### Installation & Deployment
1. Clone the repository:
   ```bash
   git clone https://github.com/JK-Clark/omninet-quantum-core.git
   cd omninet-quantum-core
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your production settings (database passwords, secrets, etc.)
   ```

3. Deploy with one command:
   ```bash
   docker-compose up --build -d
   ```

4. Access the application:
   - **Frontend**: http://localhost
   - **API Docs**: http://localhost/api/docs (Swagger UI)
   - **Monitoring**: http://localhost:9090 (Prometheus), http://localhost:3000 (Grafana)

### Configuration

#### Environment Variables (.env)
All configurable settings are documented in `.env.example`. Key variables include:
- Database connection strings
- Redis password and URL
- Secret keys for JWT and crypto
- License tier settings
- Monitoring endpoints

#### Licensing
Activate your license via the in-app License Manager. Keys are validated against the PostgreSQL database.

### API Endpoints

- `GET /api/health` - Health check
- `GET /api/devices` - List discovered devices
- `POST /api/topology` - Trigger topology scan
- `GET /api/predictions` - AI failure predictions
- `POST /api/license/activate` - Activate license

Full API documentation available at `/api/docs` when running.

### Monitoring & Observability

- **Prometheus**: Scrapes metrics from all services
- **Grafana**: Pre-built dashboards for network health, AI predictions, and system performance
- **Logs**: Centralized via Docker Compose logging

### Security Features

- Post-quantum cryptography simulation for secure communications
- JWT-based authentication with bcrypt hashing
- Role-based access control (RBAC) enforced per license tier
- SSL/TLS termination at Nginx level
- Environment-based secrets management

### Development

#### Local Setup
Follow the Quick Start, but use development targets in Dockerfiles for hot-reloading.

#### Testing
Run tests with:
```bash
docker-compose exec backend pytest
```

#### Contributing
1. Fork the repo
2. Create a feature branch
3. Submit a PR with detailed description
4. Ensure all builds pass and documentation is updated

### Troubleshooting

#### Common Issues
- **Build Failures**: Ensure Docker has sufficient resources and no stale artifacts (clear `node_modules`, `venv`, etc.)
- **Database Connection**: Verify `.env` variables and PostgreSQL health
- **Topology Not Loading**: Check network permissions for LLDP/CDP discovery

#### Logs
View logs with:
```bash
docker-compose logs -f [service_name]
```

### Roadmap

- Enhanced AI models for more accurate predictions
- Support for additional discovery protocols (SNMP, BGP)
- Kubernetes deployment manifests
- Multi-cluster support

### License

This project is proprietary. Licensing details in the in-app manager.

### Support

For issues or questions:
- GitHub Issues: https://github.com/JK-Clark/omninet-quantum-core/issues
- Email: support@omninet-core.com (placeholder)

---

*OmniNet Quantum-Core: Secure, Intelligent Networking for the Future.*