# 🚀 GXNT Traefik Manager

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version: 1.0.0](https://img.shields.io/badge/Version-1.0.0-blue)](CHANGELOG.md)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-green)](requirements.txt)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](Dockerfile)

_A production-grade, open-source web interface for managing Traefik routing configurations._

**Company**: [GXNT TECH PVT LTD](https://www.genxnext.com) | **Docs**: [Documentation](#-documentation) | **Issues**: [GitHub](https://github.com/genxnext/traefik-manager/issues)

---

## ✨ Key Features

- 🔀 **Multi-Protocol**: HTTP, TCP, UDP, TLS routing (unified UI)
- 🛡️ **Safe & Validated**: 3-layer input validation
- 🔐 **Multi-Tenant**: Manage multiple etcd instances
- 💾 **Backup/Restore**: Complete configuration backup & recovery
- 🎨 **Modern UI**: Responsive design, light/dark theme
- 🚀 **Production-Ready**: Docker, Kubernetes, scalable
- 📚 **20+ Middleware Types**: RateLimit, Auth, CORS, JWT, and more

---

## 🚀 Quick Start (Docker)

```bash
# Clone & configure
git clone https://github.com/genxnext/traefik-manager.git
cd traefik-manager
cp .env.example .env

# Edit .env with your secrets
cat .env  # Set FLASK_SECRET_KEY and ETCD_URL

# Run
docker compose up --build -d

# Access
open http://localhost:8090
# Login: admin / admin (change password immediately!)
```

---

## 📚 Documentation

| Document                                       | Purpose                               |
| ---------------------------------------------- | ------------------------------------- |
| **[ARCHITECTURE.md](ARCHITECTURE.md)**         | System design, data flow, scalability |
| **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** | Docker, Kubernetes, troubleshooting   |
| **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)**   | Local setup, development patterns     |
| **[CONTRIBUTING.md](CONTRIBUTING.md)**         | Code guidelines, PR process           |
| **[CHANGELOG.md](CHANGELOG.md)**               | Version history, roadmap              |

**Choose based on your role**:

- 🚀 **Deploying?** → [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- 👨‍💻 **Contributing?** → [CONTRIBUTING.md](CONTRIBUTING.md)
- 🏗️ **Understanding architecture?** → [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 🏗️ System Overview

```
Web UI (Flask 8090) → etcd v3 (config) → Traefik (routing)
                   ↓
            SQLite (authentication)
```

**Features**:

- Feature-based Flask Blueprints (clean architecture)
- Type-safe models (Pydantic validation)
- Multi-protocol support (HTTP/TCP/UDP/TLS)
- 20+ middleware types
- Health checks, load balancing, sticky sessions
- Backup/restore functionality

---

## 🔐 Security

✅ **Input validation** (form, Python, Traefik layers)  
✅ **Secure authentication** (password hashing)  
✅ **Session protection** (CSRF tokens)  
✅ **HTTPS-ready** (reverse proxy recommended)  
✅ **Secrets management** (environment variables)

---

## 📦 Deployment

### Docker Compose

```bash
docker compose up --build -d
```

### Kubernetes

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for full manifests and setup.

### Manual

```bash
uv sync
export ETCD_URL=http://localhost:2379 FLASK_SECRET_KEY=your-key
python webui.py
```

---

## 🧑‍💻 Development

```bash
uv venv
source .venv/bin/activate
uv sync
export ETCD_URL=http://localhost:2379 FLASK_SECRET_KEY=dev-key
python webui.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for patterns.

---

## 🐛 Common Issues

| Issue                  | Solution                                                     |
| ---------------------- | ------------------------------------------------------------ |
| Cannot connect to etcd | Verify `ETCD_URL` and check: `curl http://etcd:2379/version` |
| Login fails            | Check `FLASK_SECRET_KEY` is set; clear cookies               |
| Invalid Configuration  | Check Traefik rule syntax                                    |

See [DEPLOYMENT_GUIDE.md — Troubleshooting](DEPLOYMENT_GUIDE.md#troubleshooting) for more.

---

## 📈 Roadmap

- **v1.0** (Current) ✅ HTTP/TCP/UDP/TLS, multi-etcd, UI
- **v1.1** (Q1 2026) REST API, RBAC, audit logging
- **v1.2** (Q2 2026) PostgreSQL, metrics, webhooks
- **v2.0+** (Future) GitOps, analytics, service mesh

---

## 📄 License

MIT License — See [LICENSE](LICENSE)

**Issues & Support**:

- 🐛 [GitHub Issues](https://github.com/genxnext/traefik-manager/issues)
- 📧 samirm@genxnext.com
- 🔒 Security: samirm@genxnext.com

---

Built by [GXNT TECH PVT LTD](https://www.genxnext.com) | v1.0.0 | Production Ready ✅
