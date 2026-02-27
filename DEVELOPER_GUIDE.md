# GXNT Traefik Manager - Developer Quick Reference

## 🚀 Quick Start

### Local Development

```bash
# Clone & enter project
cd traefik_manager

---

### Option 1: Using uv (Recommended)
# Create virtual environment
uv venv
# Activate environment (Linux/macOS)
source .venv/bin/activate
# Install dependencies
uv sync

---

### Option 2: Using pip + venv
# Create virtual environment
python -m venv .venv
# Activate environment (Linux/macOS)
source .venv/bin/activate
# Upgrade pip (recommended)
pip install --upgrade pip
# Install dependencies
pip install -r requirements.txt

---

# Set environment variables
export ETCD_URL=http://localhost:2379
export FLASK_SECRET_KEY=dev-secret-key
export FLASK_DEBUG=true

# Run development server
python webui.py
# Opens http://0.0.0.0:8090
```

### Docker

```bash
cp .env.example .env
# Edit .env: set ETCD_URL to your etcd instance
docker compose up --build -d
# Opens http://localhost:8090
```

### Login

- **Username**: `admin`
- **Password**: `admin` (forced change on first login)

---

## 📁 Project Structure Overview

```
app/                — Web application (Flask Blueprints)
├── __init__.py     — App factory & template auto-discovery
├── globals.py      — Global state (etcd_client, config_manager)
├── utils.py        — Shared helpers (auth, validation)
├── auth/           — Authentication routes
├── common/         — Dashboard, settings, connections
├── http/           — HTTP module (routers, services, middlewares, domains, servers_transports)
├── tcp/            — TCP module (routers, services, middlewares)
├── udp/            — UDP module (routers, services)
├── tls/            — TLS module (options, stores)
├── config/         — Import/Export & backup operations
├── health/         — Health check endpoint
└── templates/      — Global Jinja2 templates

core/              — Business logic
├── etcd_client.py  — etcd v3 REST API client (2,237 LOC)
├── config_manager.py — Validation & caching layer (1,122 LOC)
├── models.py       — Dataclass models (791 LOC)
└── __init__.py

auth_db.py         — SQLite authentication & connection management (204 LOC)
webui.py           — Flask app entry point (thin wrapper)
requirements.txt   — Dependencies (Flask, requests, gunicorn)
```

---

## 🔑 Key Concepts

### Modular Architecture

- Each feature (HTTP, TCP, UDP, TLS) is a **Flask Blueprint**
- Routes live in `views.py` files
- Templates auto-discovered from `templates/` subdirectories
- State is global (`app/globals.py`) for easy etcd client access

### Data Flow

```
Browser Request
    ↓
Flask Route (views.py)
    ↓
Validation + Form Processing
    ↓
config_manager (ConfigManager)
    ↓
Validation (checks constraints, dropdown values)
    ↓
etcd_client (ETCDClient)
    ↓
etcd v3 HTTP REST API (base64 encoded keys/values)
    ↓
etcd Server
    ↓
Response back through layers
    ↓
Jinja2 Template → Browser
```

### Triple-Layer Model

1. **Application Layer** (`app/*/views.py`)
   - Route handlers
   - Form parsing
   - Template rendering
   - User-facing error messages

2. **Business Logic** (`core/config_manager.py`)
   - Validation & constraints
   - Caching
   - High-level operations

3. **Data Access** (`core/etcd_client.py`)
   - etcd v3 API
   - Base64 encoding/decoding
   - Low-level CRUD

---

## 📊 Database Schema

### SQLite (`traefik_manager.db`)

**Users Table**

```sql
CREATE TABLE users (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  username             TEXT UNIQUE NOT NULL,
  password_hash        TEXT NOT NULL,
  must_change_password INTEGER NOT NULL DEFAULT 1,
  created_at           TEXT DEFAULT (datetime('now'))
);
```

**etcd Connections Table**

```sql
CREATE TABLE etcd_connections (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  url         TEXT NOT NULL,
  description TEXT DEFAULT '',
  is_active   INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT DEFAULT (datetime('now'))
);
```

### etcd v3 Key Structure

```
traefik/
├── http/
│   ├── routers/<name>/<field>                 # e.g., "priority", "rule", "service"
│   ├── services/<name>/<field>                # e.g., "loadBalancer", "mirrors"
│   ├── middlewares/<name>/<field>             # e.g., "basicAuth", "rateLimit"
│   ├── domains/default/<field>
│   └── serversTransports/<name>/<field>
├── tcp/
│   ├── routers/<name>/<field>
│   ├── services/<name>/<field>
│   └── middlewares/<name>/<field>
├── udp/
│   ├── routers/<name>/<field>
│   └── services/<name>/<field>
└── tls/
    ├── options/<name>/<field>
    └── stores/<name>/<field>
```

**Note**: All keys/values are **base64-encoded** in etcd API calls.

---

## 🔐 Authentication & Authorization

### Session-Based Auth

- Flask sessions (secure cookies)
- Login via `/login` route
- Logout clears session
- Decorator: `@login_required` protects routes

### Password Hashing

```python
# auth_db.py
def hash_password(password: str) -> str:
    """Return a salt:sha256hash string."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode('utf-8')).hexdigest()
    return f"{salt}:{h}"
```

### Multi-Connection Support

- User can add multiple etcd endpoints
- Mark one as "active"
- Global etcd client switches when active connection changes
- Other users unaffected (no session sharing)

---

## 🧩 Adding a New Feature (Example: New Middleware Type)

### 1. Define Data Model

**File**: `core/models.py`

```python
class MiddlewareType(Enum):
    # ... existing types ...
    MY_NEW_MIDDLEWARE = "myNewMiddleware"  # Add here

# Add dataclass for config (if needed)
@dataclass
class MyNewMiddlewareConfig:
    enabled: bool
    option1: str
    option2: int
```

### 2. Add Handler in etcd_client

**File**: `core/etcd_client.py`

```python
def middleware_to_dict(middleware):
    # ... existing logic ...
    if middleware.type == MiddlewareType.MY_NEW_MIDDLEWARE:
        return {"myNewMiddleware": {"enabled": middleware.enabled, ...}}
```

### 3. Add Route & Form

**File**: `app/http/middlewares/views.py`

```python
@bp.route('/middlewares/create', methods=['GET', 'POST'])
@login_required
def create_middleware():
    # Handle GET: render form
    # Handle POST: validate & save to etcd via config_manager
```

### 4. Create Template

**File**: `app/http/middlewares/templates/http/middlewares/my_middleware_form.html`

```html
<form method="POST">
  {% include "components/text_input.html" with name="option1" label="Option 1"
  %}
  <button type="submit">Create Middleware</button>
</form>
```

### 5. Add Tests

**File**: `tests/test_http_middlewares.py`

```python
def test_create_my_middleware(client, mock_etcd):
    response = client.post('/middlewares/create', {
        'name': 'my-middleware',
        'option1': 'value1',
        'option2': 123,
    })
    assert response.status_code == 302  # Redirect on success
```

---

## 🧪 Testing Patterns

### Unit Test Template

```python
import pytest
from core.config_manager import ConfigManager, ValidationError

@pytest.fixture
def config_manager(mock_etcd):
    return ConfigManager(mock_etcd)

def test_validation(config_manager):
    with pytest.raises(ValidationError):
        config_manager.create_router({
            'name': 'invalid-name-with-spaces',  # Invalid
        })
```

### Mock etcd Responses

```python
import responses

@responses.activate
def test_list_routers(client):
    # Mock etcd response
    responses.add(
        responses.POST,
        'http://localhost:2379/v3/kv/range',
        json={
            'kvs': [
                {
                    'key': base64.b64encode(b'traefik/http/routers/my-router/rule').decode(),
                    'value': base64.b64encode(b'Host(`example.com`)').decode(),
                }
            ]
        }
    )
    # Test endpoint
    response = client.get('/routers')
    assert response.status_code == 200
```

---

## 🛠 Common Development Tasks

### Debugging etcd Queries

```python
# In any view or manager, before etcd call:
import json
from app import globals as state

print("Current etcd URL:", state.etcd_url)
print("Available routers:", state.config_manager.list_routers())
```

### Enable Flask Debug Logging

```bash
export FLASK_DEBUG=true
export FLASK_ENV=development
python webui.py
# See detailed request/response logs in console
```

### Inspect SQLite Database

```bash
sqlite3 traefik_manager.db
> .schema
> SELECT * FROM users;
> SELECT * FROM etcd_connections;
```

### Test Docker Build Locally

```bash
docker build -t traefik-manager:test .
docker run -p 8090:8090 -e ETCD_URL=http://host.docker.internal:2379 traefik-manager:test
```

---

## 📝 Code Style & Conventions

### Python

- **PEP 8**: Use `black` formatter or follow standard Python style
- **Type Hints**: Add for function parameters & returns (dataclasses do this automatically)
- **Docstrings**: Module-level docstrings for all `.py` files; function docstrings for complex logic
- **Naming**:
  - Classes: `PascalCase` (e.g., `Router`, `ConfigManager`)
  - Functions/Variables: `snake_case` (e.g., `list_routers`, `etcd_client`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `VALID_HTTP_ENTRYPOINTS`)
  - Private: prefix with `_` (e.g., `_internal_helper`)

### Templates (Jinja2)

- **File location**: `app/<module>/templates/<module>/<resource>/<action>.html`
- **Example**: `app/http/routers/templates/http/routers/create.html`
- **Extend**: `{% extends "base.html" %}`
- **Include**: `{% include "components/form_group.html" %}`

### Commits

```
feat: add new middleware type
fix: correct validation logic in config_manager
docs: update ARCHITECTURE.md with etcd schema
test: add unit tests for etcd_client
refactor: simplify router form rendering
```

---

## ⚠️ Common Pitfalls

1. **Forgetting to sync etcd client**
   - When switching active connection, call `state._reinit_etcd(url)`
   - Otherwise, stale etcd_client is used

2. **Not base64-encoding etcd keys/values**
   - etcd v3 API requires base64; automatically handled in `etcd_client.py`
   - Don't manually base64-encode; the client does it

3. **SQL injection in auth_db**
   - **Always** use parameterized queries: `conn.execute(sql, (params,))`
   - Never: `f"SELECT WHERE username='{user}'"`

4. **Missing @login_required decorator**
   - Any route accessible without auth is a security issue
   - Add: `@bp.route(...)\n@login_required\ndef my_view():`

5. **Templates finding wrong namespace**
   - Multiple modules have same template names (e.g., `create.html`)
   - Flask template loader searches in order; ensure no collisions
   - Use full paths: `app/http/routers/templates/http/routers/create.html`

6. **etcd connection timeouts**
   - Default timeout: 5 seconds
   - Increase if etcd is slow: `self.timeout = 10` in `ETCDClient.__init__`
   - But don't make it too long (slow UI)

---

## 🔗 Important Links & References

### Traefik Documentation

- [Traefik v2+ Overview](https://doc.traefik.io/)
- [Configuration via etcd](https://doc.traefik.io/traefik/providers/file/)
- [Router Rules](https://doc.traefik.io/traefik/routing/routers/)
- [Middlewares Reference](https://doc.traefik.io/traefik/middlewares/overview/)

### etcd v3 API

- [etcd API Documentation](https://etcd.io/docs/v3.5/dev-guide/api_reference_v3/)
- [gRPC to JSON Mapping](https://etcd.io/docs/v3.5/dev-guide/grpc_gateway/)

### Flask

- [Flask Official Docs](https://flask.palletsprojects.com/)
- [Blueprints](https://flask.palletsprojects.com/blueprints/)
- [Session Management](https://flask.palletsprojects.com/sessions/)

### Python

- [dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [enum](https://docs.python.org/3/library/enum.html)
- [requests Library](https://requests.readthedocs.io/)

---

## 📞 Support & Community

### Reporting Issues

- GitHub Issues: [link to be added]
- Security Issues: samirm@genxnext.com (confidential)

### Contributing

- See `CONTRIBUTING.md` (to be written)
- Coding standards, PR process, testing requirements

### Roadmap

- See `CHANGELOG.md` (to be written)
- Planned features, known limitations, v1.1+ features

---

**Last Updated**: 2026-02-26  
**For**: Developers, contributors, maintainers
