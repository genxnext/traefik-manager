# GXNT Traefik Manager — Architecture & Design

**Version:** 1.0  
**Last Updated:** February 2025  
**Audience:** Developers, DevOps Engineers, Architects

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Core Components](#core-components)
5. [Data Flow](#data-flow)
6. [Security Model](#security-model)
7. [Scalability & Performance](#scalability--performance)
8. [Extension Points](#extension-points)
9. [Development Patterns](#development-patterns)

---

## Overview

**GXNT Traefik Manager** is a production-grade web interface for managing Traefik v2.x routing configurations. It provides a **safe, validated, multi-protocol configuration UI** backed by **etcd v3** as the primary data store.

### Key Principles

- **Safety First**: All inputs validated; invalid requests rejected (even crafted ones)
- **Multi-Protocol**: HTTP, TCP, UDP, TLS protocols with unified orchestration
- **Multi-Tenant Ready**: Support multiple etcd connections (profiles) from single UI
- **Stateless**: Horizontal scalable; authentication state in SQLite, routing config in etcd
- **Developer-Friendly**: Modular Flask Blueprints, clear separation of concerns

### Use Cases

1. **Enterprise Routing**: Manage 100+ HTTP routes with middleware chains
2. **Microservices Ingress**: Control TCP/UDP ingress for Kubernetes-like environments
3. **Multi-Cloud Load Balancing**: Centralized TLS + certificate resolver management
4. **DevOps Automation**: API-friendly configuration (future REST API in v1.1)

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                       Web Browser / Client                      │
└────────────────┬───────────────────────────────────────────────┘
                 │ HTTPS (TLS recommended)
                 ▼
┌────────────────────────────────────────────────────────────────┐
│              Flask Web Server (webui.py entry)                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  app/ (Feature-based packages)                           │  │
│  │  ├─ auth/: Login, password management                    │  │
│  │  ├─ common/: Home, help, etcd connection settings        │  │
│  │  ├─ config/: Export/import (full + incremental)          │  │
│  │  ├─ http/: HTTP routing (routers, services, etc.)        │  │
│  │  │   ├─ routers/: HTTP router CRUD                       │  │
│  │  │   ├─ services/: HTTP service CRUD                     │  │
│  │  │   ├─ middlewares/: HTTP middleware CRUD               │  │
│  │  │   ├─ domains/: Global domains & cert config           │  │
│  │  │   └─ servers_transports/: Upstream TLS config         │  │
│  │  ├─ tcp/: TCP (routers, services, middlewares)           │  │
│  │  ├─ udp/: UDP (routers, services)                        │  │
│  │  ├─ tls/: TLS options & certificate stores              │  │
│  │  └─ health/: Liveness probe (/api/health)               │  │
│  │                                                           │  │
│  │  core/ (Data & etcd layer)                              │  │
│  │  ├─ etcd_client.py: etcd v3 API wrapper                 │  │
│  │  ├─ config_manager.py: High-level config orchestration   │  │
│  │  └─ models.py: Dataclasses for all entity types         │  │
│  │                                                           │  │
│  │  auth_db.py: SQLite auth + etcd connection profiles      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Static Assets: design tokens, icons, styles (Bootstrap 5.3)  │
│  Templates: 68+ Jinja2 templates (feature-based co-location)   │
└────────────┬──────────────────────────────────────────────────┘
             │
             ├─────────────┬─────────────┐
             ▼             ▼             ▼
        ┌─────────┐   ┌─────────┐   ┌─────────┐
        │  etcd   │   │ SQLite  │   │ Traefik │
        │ v3 API  │   │ (auth)  │   │ (reads) │
        │ (config)│   └─────────┘   └─────────┘
        └─────────┘
            │
            └─→ Traefik v2.x (listens to /traefik/* keys)
                Manages actual routing / forwarding
```

---

## Technology Stack

### Frontend

- **Framework**: Flask 2.x with Jinja2 templating
- **UI Components**: Bootstrap 5.3.2
- **Icons**: Bootstrap Icons
- **Styling**: CSS Grid + Flexbox with design tokens
- **Interactivity**: Vanilla JavaScript (Babel/build-free)
- **Theme**: Light/Dark mode (localStorage-backed)
- **Accessibility**: WCAG 2.1 AAA compliant

### Backend

- **Language**: Python 3.9+
- **Framework**: Flask 2.x
- **Architecture**: Blueprint-based (feature domains)
- **Config Storage**: etcd v3
- **State Storage**: SQLite (auth, connection profiles)
- **Validation**: Pydantic and custom validators
- **Serialization**: JSON (with custom encoder for uncommon types)

### Infrastructure

- **Containerization**: Docker + Docker Compose
- **Logs**: stdout/stderr (12-factor app compatible)
- **Signals**: systemd/Docker managed graceful shutdown
- **Config**: Environment variables (.env file)

### Dependencies (Core)

- `flask` — Web framework
- `requests` — etcd v3 HTTP API client
- `pydantic` — Data validation
- (See `requirements.txt` for complete list)

---

## Core Components

### 1. ETCDClient (`core/etcd_client.py`)

**Responsibility**: Abstract etcd v3 HTTP REST API.

**Key Methods**:

- `put(key, value)` — Write a key-value pair
- `get(key)` — Fetch single key
- `get_prefix(prefix)` — Fetch all keys under a prefix (with pagination support via `limit: 0`)
- `delete(key)` — Remove a key
- `delete_prefix(prefix)` — Remove all keys under prefix
- `health_check()` — Verify etcd reachability

**Design Decisions**:

- Uses base64 encoding/decoding (etcd v3 API requirement)
- Implements timeout & exception handling
- Range queries for prefix-based operations
- No caching layer (fresh reads on every request)

**Scaling Impact**: Direct etcd client; latency scales with etcd distance/network.

---

### 2. ConfigManager (`core/config_manager.py`)

**Responsibility**: High-level orchestration of router, service, middleware CRUD.

**Key Features**:

- Lazy loading with in-memory cache (list\* methods populate caches)
- Validation before write (prevents invalid configs reaching etcd)
- Transactions (atomic multi-key operations where possible)
- Error handling & recovery patterns

**Cache Strategy**:

```
User clicks "Save Router"
  → ConfigManager.update_router(Router object)
    → Validate against service/middleware/domain lists (cache)
    → Split Router into ~5 etcd keys (entrypoint, rule, service, tls, priority)
    → WriteTo etcd via ETCDClient.put()
    → Update internal cache
    → Return success
```

**Limitations**:

- No distributed transaction support (eventual consistency possible)
- Cache invalidation relies on list-refresh (no pub/sub)

---

### 3. Models (`core/models.py`)

**Responsibility**: Type safety for all Traefik entities.

**Key Dataclasses**:

- `Router` — HTTP routing rule + service binding
- `Service` — Load balancer pool + health checks
- `MiddlewareType` (Enum) — 20+ middleware types (RateLimit, Auth, Compress, etc.)
- `TCPRouter`, `UDPRouter` — Layer 4 routing
- `TLSOptions`, `TLSStore` — Certificate config
- `ServersTransport` — Upstream TLS settings

**Validation**:

- Pydantic `model_validate()` for deep validation
- Custom validators for complex rules (e.g., regex syntax)
- Enum enforcement for known fields (no free text for cert resolvers)

---

### 4. Flask Blueprints (Feature Modules)

**Architecture**: Feature-based, not MVC-based.

```
app/
├─ auth/: Authentication feature
├─ common/: Home, help, connection management
├─ config/: Backup/restore feature
├─ http/: HTTP protocol family
│  ├─ routers/: Router CRUD
│  ├─ services/: Service CRUD
│  ├─ middlewares/: Middleware CRUD
│  ├─ domains/: Domain config
│  └─ servers_transports/: Upstream transport config
├─ tcp/: TCP protocol family
├─ udp/: UDP protocol family
└─ tls/: TLS config family
```

**Each feature package**:

- `__init__.py` — Blueprint registration + imports
- `views.py` — Route handlers (list, create, edit, delete)
- `templates/<feature>/` — HTML templates (co-located with logic)

**Example: HTTP Router Feature**:

```python
# app/http/routers/__init__.py
bp = Blueprint('http.routers', __name__, template_folder='templates')
# (register views via endpoint decorators)

# app/http/routers/views.py
@bp.route('/routers')
def list_routers():
    routers = config_manager.list_routers()
    return render_template('http/routers/index.html', routers=routers)
```

**Benefits**:

- Self-contained features (no global dependencies)
- Easy to add new protocol (copy `/tcp` → `/new_proto`)
- Clear ownership (one team → one feature)
- Scalable testing (unit test per feature)

---

### 5. Authentication & Authorization

**SQLite Layer** (`auth_db.py`):

- Stores user credentials (hashed passwords via `werkzeug.security`)
- Manages etcd connection profiles (name, URL, description)
- Login session management

**Flask Session**:

- Server-side session storage (in-memory for v1.0, Redis for v2.0)
- CSRF protection enabled
- Secure cookie flags (HttpOnly, Secure when TLS)

**Access Control**:

- Simple: Authenticated → Full access (no RBAC in v1.0)
- v1.1 Roadmap: Role-based access control (admin, viewer, editor)

---

### 6. Templates & UI Layer

**Structure**:

- `app/templates/base.html` — Master layout (sidebar, topbar, flash messages)
- `app/<feature>/templates/<feature>/*.html` — Feature templates

**Template Naming Convention**:

- `index.html` — List all entities
- `create.html` — Form to create new entity
- `edit.html` — Form to edit existing entity
- `detail.html` — Read-only detail view

**Design System**:

- CSS variables for colors, spacing, typography (light/dark modes)
- Bootstrap 5.3.2 for responsive grid
- JS utilities for form validation, loading states, alerts

---

## Data Flow

### A. User Creates a New HTTP Router

```
1. User navigates to /routers
   → Flask renders http/routers/index.html with list of routers

2. User clicks "Create" button
   → Browser GET /routers/create
   → Served form (create.html) with dropdowns for services/middlewares

3. User submits form
   → Browser POST /routers/create with form data
   → Flask view validates inputs (checks service exists, rule syntax)
   → ConfigManager.create_router(Router(...))
     → Splits into 5 etcd keys:
        - traefik/http/routers/myrouter/entrypoints/0 → "web"
        - traefik/http/routers/myrouter/rule → "Host(`example.com`)"
        - traefik/http/routers/myrouter/service → "mysvc"
        - traefik/http/routers/myrouter/priority → "10"
        - traefik/http/routers/myrouter/tls → "1"
   → ETCDClient.put() each key
   → Traefik watches /traefik/* keys, detects changes → reloads config

4. User redirected to /routers with success flash
```

### B. System Exports Full Backup

```
1. User clicks "Export Full Backup" on /config/export

2. Flask view export_full_backup():
   → Calls ETCDClient.get_prefix('traefik/') → returns 27+ keys
   → JSON structure:
      {
        "version": "1.0",
        "exported_at": "2025-02-26T10:30:00Z",
        "etcd_prefix": "traefik/",
        "etcd_kvs": { "traefik/http/routers/...": "...", ... },
        "connections": [ { "name": "prod", "url": "http://etcd:2379" } ]
      }
   → Response with Content-Disposition: attachment; filename=traefik-backup-*.json

3. Browser downloads traefik-backup-20250226-103000.json
```

### C. System Imports Backup

```
1. User selects backup file on /config/import

2. Flask view import_full_backup():
   → Reads JSON file
   → Validate structure (must have "etcd_kvs" key)
   → Iterate over etcd_kvs, call ETCDClient.put(key, value) for each
   → Optionally restore connection profiles
   → Redirect with summary (20 keys restored, 3 skipped)

3. Traefik detects new keys → reloads config
```

---

## Security Model

### Input Validation

**Three Layers**:

1. **Form Layer**: HTML5 `required`, `pattern` attributes
2. **Python Layer**: Pydantic validators + custom logic
3. **Traefik Layer**: Traefik validates actual routing rules (safe fallibility)

**Example: Router Creation**:

```python
# Validate entrypoint is in predefined list
if entrypoint not in ['web', 'websecure', 'custom']:
    raise ValidationError("Invalid entrypoint")

# Validate rule syntax (regex check for common mistakes)
if not _validate_rule_syntax(rule):
    raise ValidationError("Invalid routing rule syntax")

# Validate service exists in current config
if service not in config_manager.list_services():
    raise ValidationError("Referenced service does not exist")
```

### Authentication & Authorization

- **Single-User Focus**: v1.0 single admin account (multi-user in v1.1)
- **Password Storage**: werkzeug.security.pbkdf2_sha256 (industry standard)
- **Session Management**: Secure cookies (HttpOnly, SameSite=Lax)
- **CSRF Protection**: Flask-WTF CSRF tokens on all POST/PUT/DELETE

### Secrets Management

- **etcd URL**: Via environment variable (not hardcoded)
- **Flask Secret Key**: Via environment variable (`FLASK_SECRET_KEY`)
- **Credentials**: SQLite local storage (encrypted via werkzeug if deployed)

### Audit Trail (v1.1+)

- Planned: Log all config changes (who, what, when)
- Planned: Git-like revision history in etcd

---

## Scalability & Performance

### Horizontal Scaling

**Current**: Stateless Flask app (can run multiple instances).

```
Load Balancer
  ├─→ Flask Instance 1 (port 8090)
  ├─→ Flask Instance 2 (port 8090)
  └─→ Flask Instance 3 (port 8090)
         ↓↓↓ (all share)
       etcd v3 (single source of truth)
       SQLite (via network mount or shared storage)
```

**Bottle Necks**:

- SQLite locking on writes (v1.1 → PostgreSQL option)
- etcd throughput (typical: 1k-10k ops/sec per node)
- Cache invalidation latency (eventual consistency, not immediate)

### Performance Characteristics

| Operation                | Latency    | Scalability         |
| ------------------------ | ---------- | ------------------- |
| List 100 routers         | 100–500ms  | O(n) etcd keys      |
| Create 1 router          | 50–200ms   | 5 etcd writes       |
| Edit config              | 50–200ms   | etcd + SQLite write |
| Export backup (100 keys) | 500–2000ms | O(n) etcd keys      |
| Import backup (100 keys) | 1–5s       | O(n) etcd writes    |

**Optimization Tips**:

- Use LocalDB (or co-located etcd) for <100ms latency
- Batch export/import to reduce round trips
- Consider etcd cluster for resilience (multi-node)

---

## Extension Points

### Adding a New Protocol

**Example: QUIC Protocol Support (hypothetical)**

1. Create directory: `app/quic/`
2. Create `__init__.py` with Blueprint:
   ```python
   bp = Blueprint('quic', __name__)
   ```
3. Create `routers/views.py` with CRUD endpoints
4. Add models in `core/models.py` (QUICRouter, etc.)
5. Register in main `app/__init__.py`:
   ```python
   from app.quic import bp as quic_bp
   app.register_blueprint(quic_bp, url_prefix='/quic')
   ```

### Adding a New Middleware Type

1. Update `MiddlewareType` enum in `core/models.py`
2. Add builder logic in `ConfigManager.create_middleware()`
3. Add form field in `app/http/middlewares/views.py`
4. Update template `app/http/middlewares/templates/http/middlewares/create.html`

### Custom Validators

Add to `core/models.py`:

```python
@field_validator('rule')
@classmethod
def validate_rule(cls, v):
    if not v or len(v) > 500:
        raise ValueError('Rule too long')
    return v
```

---

## Development Patterns

### Adding a Feature

**Step 1: Model** → Define dataclass in `core/models.py`
**Step 2: Views** → Create `app/myfeature/views.py` with CRUD routes
**Step 3: Templates** → Add `app/myfeature/templates/myfeature/`
**Step 4: Register** → Import in `app/__init__.py`

### Testing Pattern (v1.1)

```python
# tests/test_http_routers.py
def test_create_router():
    client = app.test_client()
    response = client.post('/routers/create', data={...})
    assert response.status_code == 302  # Redirect
    assert config_manager.list_routers()[-1].name == 'test-router'
```

### Common Pitfalls

1. **Forgetting to cache-bust**: After etcd write, old cache may be stale
2. **Hardcoding etcd prefix**: Always use `state.etcd_client.get_prefix('traefik/')`
3. **Skipping validation**: All user input goes through validators
4. **Not handling exceptions**: etcd can be down; implement fallback UI

---

## Roadmap

### v1.0 (Current)

- ✅ HTTP/TCP/UDP/TLS routing
- ✅ Multi-etcd connections (UI)
- ✅ Backup/restore
- ✅ Light/dark theme

### v1.1 (Q1 2025)

- 🔲 REST API (for automation)
- 🔲 Role-based access control (RBAC)
- 🔲 Audit logging
- 🔲 Test coverage (>80%)

### v1.2 (Q2 2025)

- 🔲 PostgreSQL backend (replace SQLite)
- 🔲 Metrics export (Prometheus)
- 🔲 Webhook integrations
- 🔲 GitOps mode (config-as-code)

---

## References

- [Traefik Documentation](https://doc.traefik.io/traefik/v2.10/)
- [etcd v3 API](https://etcd.io/docs/v3.4/api-grpc-gateway/)
- [Flask Blueprints](https://flask.palletsprojects.com/en/2.3.x/blueprints/)
- [Python Dataclasses](https://docs.python.org/3/library/dataclasses.html)

---

**Questions?** See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) or open an issue on GitHub.
