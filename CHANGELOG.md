# Changelog

All notable changes to GXNT Traefik Manager are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2025-02-26

### ✨ Initial Release

This is the first public release of GXNT Traefik Manager.

#### Added

**Core Features**

- ✅ HTTP routing (routers, services, middlewares, domains)
- ✅ TCP routing (routers, services, middlewares)
- ✅ UDP routing (routers, services)
- ✅ TLS configuration (options, certificate stores)
- ✅ Multi-protocol orchestration with unified UI
- ✅ etcd v3 backend integration
- ✅ Multi-etcd connection profiles (manage multiple Traefik instances)
- ✅ Configuration import/export (full + incremental backups)

**User Interface**

- ✅ Responsive web interface (Bootstrap 5.3.2)
- ✅ Light/Dark theme toggle
- ✅ Sidebar navigation with collapsible sections
- ✅ Breadcrumb navigation
- ✅ Real-time etcd connection status indicator
- ✅ Flash notifications for success/error messages
- ✅ Form validation and error handling
- ✅ Loading states for long operations

**Authentication & Authorization**

- ✅ Local user authentication (SQLite backend)
- ✅ Password hashing (werkzeug.security)
- ✅ Forced password change on first login
- ✅ Session management with CSRF protection
- ✅ etcd connection profile management (UI)

**Configuration Management**

- ✅ HTTP routers with 20+ middleware types
  - RateLimit, Auth (Basic/Digest/Bearer), Compress, JWT
  - CORS, Headers, Redirect, RedirectRegex, StripPrefix
  - StripPrefixRegex, AddPrefix, ReplacePath, ReplacePathRegex
  - AccessLog, ErrorPage, Plugin, PassTLSClientCert, HTTPS Redirect
- ✅ Service load balancing (weighted, sticky, mirror, failover)
- ✅ Health checks (interval, timeout, unhealthy threshold)
- ✅ TLS resolver configuration (Let's Encrypt, self-signed)
- ✅ Domain management with certificate binding
- ✅ Servers transport for upstream TLS

**Deployment**

- ✅ Docker image (lightweight, ~150MB)
- ✅ Docker Compose setup (includes etcd)
- ✅ Kubernetes-ready (StatefulSet example provided)
- ✅ Health check endpoint (`/api/health`)
- ✅ Graceful shutdown

**Documentation**

- ✅ README.md (quick start)
- ✅ ARCHITECTURE.md (system design, 40+ pages)
- ✅ DEPLOYMENT_GUIDE.md (Docker, Kubernetes, scaling)
- ✅ DEVELOPER_GUIDE.md (local setup, development patterns)
- ✅ CONTRIBUTING.md (contribution guidelines)
- ✅ This CHANGELOG.md

**Developer Experience**

- ✅ Feature-based Flask Blueprint architecture
- ✅ Type hints with Pydantic models
- ✅ Comprehensive input validation
- ✅ Modular code organization (easy to extend)
- ✅ Clear separation of concerns

#### Technical Stack

- **Backend**: Python 3.9+, Flask 2.x
- **Frontend**: HTML5, CSS3, Bootstrap 5.3.2, Vanilla JavaScript
- **Data Storage**: etcd v3 (config), SQLite (auth/profiles)
- **Container**: Docker, Docker Compose
- **Orchestration**: Kubernetes-ready

#### Known Limitations

- ⚠️ Single-user authentication (multi-user in v1.1)
- ⚠️ No role-based access control (RBAC in v1.1)
- ⚠️ No audit trail / configuration history (v1.1+)
- ⚠️ SQLite only (PostgreSQL option in v1.2)
- ⚠️ No REST API (planned for v1.1)
- ⚠️ No automated tests (suite in v1.1)

#### Bug Fixes

- ✅ Export full backup now retrieves all traefik keys (fixed: limit=0 in etcd query)
- ✅ Template path standardization (index.html, create.html, edit.html)
- ✅ Feature-based code organization with co-located templates

#### Migration

N/A — First release, no migration needed.

---

## [Unreleased]

### Planned for v1.1 (Q1 2025)

#### Features

- REST API (for automation, CLI tools)
- Role-based access control (RBAC)
- Audit logging (who, what, when)
- Configuration revision history (git-like)
- Webhook integrations (notify on changes)
- Advanced search & filtering
- Bulk operations (import multiple routers at once)

#### Improvements

- Automated test suite (>80% coverage)
- GitHub Actions CI/CD pipeline
- Performance metrics (Prometheus)
- Improved error messages & troubleshooting logs
- Multi-language support (i18n)

#### Fixes

- PostgreSQL backend option (replace SQLite for production)
- Better handling of large configurations (100+ routers)

### Planned for v1.2 (Q2 2025)

- GitOps mode (config-as-code in git repository)
- Advanced middleware composition
- Traffic mirroring (canary deployments)
- Rate limiting improvements (per-user, per-IP)
- Service mesh integration (Istio/Linkerd preview)

### Planned for v2.0 (Q3 2025+)

- Distributed deployment across multiple Traefik clusters
- Advanced analytics and traffic insights
- Machine learning-based traffic routing
- Native Kubernetes CRD support
- GraphQL API
- Real-time collaboration (multi-user editing)

---

## Version History

| Version | Release Date | Status    | Downloads                                                                 |
| ------- | ------------ | --------- | ------------------------------------------------------------------------- |
| 1.0.0   | 2025-02-26   | ✅ Stable | [GitHub](https://github.com/genxnext/traefik-manager/releases/tag/v1.0.0) |

---

## Upgrade Guide

### From 0.x to 1.0.0

**Breaking Changes**:

- Flask app restructured (webui.py now thin entry point, app/ manages features)
- Requires Python 3.9+ (was 3.8+)
- Database schema unchanged (SQLite compatible)
- etcd key structure unchanged (backward compatible)

**Migration Steps**:

1. Backup current database: `cp ./data/traefik_manager.db ./data/traefik_manager.db.backup`
2. Export configuration: Download full backup from old version
3. Stop old container/service
4. Deploy new version (1.0.0)
5. Import configuration: Upload backup from step 2
6. Verify: Check all routers/services load correctly

**Rollback**:
If issues occur, restore previous version:

```bash
docker pull genxnext/traefik-manager:0.x  # Specify version
docker compose up -d
```

---

## Support

- **Issues**: [GitHub Issues](https://github.com/genxnext/traefik-manager/issues)
- **Discussions**: [GitHub Discussions](https://github.com/genxnext/traefik-manager/discussions)
- **Security Issues**: samirm@genxnext.com (do not open public issues)
- **Documentation**: [ARCHITECTURE.md](ARCHITECTURE.md), [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

## Contributors

**GXNT TECH PVT LTD**

- Website: https://www.genxnext.com
- Email: samirm@genxnext.com

---

## License

MIT License — See [LICENSE](LICENSE) file

---

## Release Notes Format

For each release, we follow this format:

```markdown
## [X.Y.Z] — YYYY-MM-DD

### Added

- New feature descriptions

### Changed

- Behavior changes, breaking changes

### Fixed

- Bug fixes

### Removed

- Deprecated features that were removed

### Security

- Security fixes and updates

### Upgrade Notes

- Special instructions for upgrading
```

---

**Last Updated**: February 2025  
**Maintainer**: GXNT TECH PVT LTD  
**Repository**: https://github.com/genxnext/traefik-manager
