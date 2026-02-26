# Contributing to GXNT Traefik Manager

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Commit Guidelines](#commit-guidelines)
6. [Pull Request Process](#pull-request-process)
7. [Testing](#testing)
8. [Documentation](#documentation)
9. [Reporting Issues](#reporting-issues)

---

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors.

- Be respectful and constructive
- Welcome diverse perspectives
- Focus on the issue, not the person
- Assume good intent

---

## Getting Started

### Prerequisites

- Python 3.9+
- Docker (optional, for containerized development)
- Git
- etcd v3.4+ (for testing)

### Setup Development Environment

```bash
# 1. Clone the repository
git clone https://github.com/genxnext/traefik-manager.git
cd traefik-manager

# 2. Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
uv sync

# 4. Set environment variables
cp .env.example .env
export ETCD_URL=http://localhost:2379  # Point to your etcd
export FLASK_SECRET_KEY=dev-key

# 5. Run locally
python webui.py

# 6. Access at http://localhost:8090
```

### Docker Development

```bash
# Build dev image
docker build -f Dockerfile.dev -t traefik-manager:dev .

# Run with hot-reload
docker compose -f docker-compose.dev.yml up
```

---

## Development Workflow

### 1. Create a Feature Branch

```bash
# Update main first
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name
# Or for bug fixes: fix/issue-description
# Or for docs: docs/topic-description
```

### 2. Make Changes

Follow the project structure:

```
app/
├─ <feature>/
│  ├─ __init__.py          # Blueprint registration
│  ├─ views.py             # Route handlers
│  └─ templates/           # HTML templates (co-located)
```

### 3. Commit Early, Commit Often

```bash
git add .
git commit -m "feat: add new middleware type - RateLimitV2"
```

### 4. Push to GitHub

```bash
git push origin feature/your-feature-name
```

### 5. Create a Pull Request

- Go to GitHub repo
- Click "New Pull Request"
- Fill out PR template with description, linked issues, testing notes

---

## Coding Standards

### Python Conventions

```python
# ✅ Good: Clear, documented, type hints
def create_http_router(
    name: str,
    rule: str,
    service: str,
    entrypoint: str = 'web'
) -> bool:
    """
    Create a new HTTP router.

    Args:
        name: Router identifier (must be unique)
        rule: Traefik routing rule (e.g., Host(`example.com`))
        service: Reference to existing service
        entrypoint: Entrypoint to bind to

    Returns:
        True if successful, False otherwise

    Raises:
        ValueError: If rule syntax is invalid
    """
    if not _validate_rule_syntax(rule):
        raise ValueError(f"Invalid rule: {rule}")

    # Implementation
    return state.config_manager.create_router(Router(...))

# ❌ Bad: Unclear, no documentation
def create_router(name, rule, svc, ep):
    # Some logic here
    return something
```

### Style Guide

- **PEP 8**: Use `black` for formatting
- **Line length**: 100 characters max
- **Imports**: Group standard, third-party, local (isort)
- **Type hints**: Always use for function signatures

```bash
# Format code
black app/ core/

# Check style
flake8 app/ core/
isort --check-only app/ core/
```

### Comments & Docstrings

```python
# Bad: Obvious comments
x = x + 1  # Add 1 to x

# Good: Why, not what
# Reset attempt counter after successful auth
attempt_count = 0

# TODO/FIXME must include issue number
# TODO(issue#42): Implement role-based access control
```

---

## Commit Guidelines

### Message Format

```
feat(<scope>): <subject>

<body>

Fixes #<issue-number>

<footer>
```

### Examples

```
feat(http-routers): add priority field to router creation
  Add optional priority field to HTTP router form
  Allows manual route precedence control
  Fixes #123

fix(backup): retrieve all traefik keys with limit=0
  Root cause: etcd limit defaults to 1000
  Now uses limit: 0 for unlimited results
  Fixes #456

docs(deployment): add Kubernetes manifest examples
  Adds example k8s deployment, service, ingress
  Includes PVC for SQLite persistence
  Fixes #789

refactor(models): split large dataclass into smaller ones
  Improves readability and type safety
  No functional changes
```

### Scope Options

- `http-routers`, `http-services`, `http-middlewares`, `http-domains`
- `tcp-routers`, `tcp-services`
- `udp-routers`, `udp-services`
- `tls-options`, `tls-stores`
- `auth`, `backup`, `config`, `ui`, `docs`

### Type Options

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code reorganization (no functional change)
- `test`: Test additions/modifications
- `perf`: Performance improvements
- `ci`: CI/CD configuration
- `chore`: Maintenance, dependency updates

---

## Pull Request Process

### Before Submitting

1. **Test locally**:

   ```bash
   python -m pytest tests/
   black --check app/ core/
   flake8 app/ core/
   ```

2. **Update documentation**:
   - Update `README.md` if needed
   - Update `ARCHITECTURE.md` for structural changes
   - Add docstrings to new functions

3. **Run manual tests**:
   - Test feature works as intended
   - Test edge cases (empty input, invalid data)
   - Test in both light and dark themes

### PR Checklist

```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing Done

- [ ] Local testing complete
- [ ] Edge cases tested
- [ ] No new warnings/errors

## Checklist

- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] No new TODO comments without issue reference
- [ ] Commits are well-formed

## Related Issues

Fixes #<issue-number>
```

### Review Process

1. **Automated checks** (GitHub Actions):
   - Linting
   - Type checking
   - Build verification

2. **Human review**:
   - Code quality
   - Architecture alignment
   - Performance impact
   - Security concerns

3. **Approval & Merge**:
   - Pull request requires 1+ approval from maintainers
   - Automatic merge on approved + passing checks

---

## Testing

### Running Tests

```bash
# Install dev dependencies
uv sync

# Run all tests
pytest

# Run specific test
pytest tests/test_http_routers.py::test_create_router

# With coverage
pytest --cov=app --cov=core tests/
```

### Writing Tests

```python
# tests/test_http_routers.py

import pytest
from flask import Flask
from app import create_app

@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_list_routers(client):
    """Test listing HTTP routers"""
    response = client.get('/routers')
    assert response.status_code == 302  # Redirect to login

def test_list_routers_authenticated(client, auth):
    """Test listing routers when authenticated"""
    auth.login()
    response = client.get('/routers')
    assert response.status_code == 200
    assert b'Routers' in response.data

def test_create_router_validation(client, auth):
    """Test router creation validates input"""
    auth.login()

    # Missing required fields
    response = client.post('/routers/create', data={})
    assert response.status_code == 400
    assert b'required' in response.data.lower()

    # Invalid rule syntax
    response = client.post('/routers/create', data={
        'name': 'test',
        'rule': 'INVALID-RULE',
        'service': 'existing-service'
    })
    assert response.status_code == 400
```

### Mocking etcd

```python
from unittest.mock import patch, MagicMock

@patch('core.etcd_client.ETCDClient.get_prefix')
def test_export_backup(mock_get_prefix):
    """Test backup export with mocked etcd"""
    mock_get_prefix.return_value = {
        'traefik/http/routers/test/rule': 'Host(`test.com`)',
        'traefik/http/services/test/url': 'http://backend:80'
    }

    # Your test here
    assert len(result) == 2
```

---

## Documentation

### When to Update Docs

- **New feature**: Update `ARCHITECTURE.md` and `DEVELOPER_GUIDE.md`
- **API change**: Update docstrings and README
- **New protocol support**: Update architecture diagrams
- **Deployment changes**: Update `DEPLOYMENT_GUIDE.md`

### Documentation Format

```markdown
# Section Title

Introductory paragraph.

## Subsection

### Code Example

\`\`\`python

# Code here

\`\`\`

### Diagram

\`\`\`
ASCII diagram or link to image
\`\`\`

## Related Links

- [Other doc](OTHER.md)
- [External resource](https://example.com)
```

---

## Reporting Issues

### Security Issues

⚠️ **Do not open GitHub issues for security vulnerabilities!**

Email: samirm@genxnext.com with details.

### Bug Reports

```markdown
## Description

Brief description of the bug

## Steps to Reproduce

1. Step one
2. Step two
3. ...

## Expected Behavior

What should happen

## Actual Behavior

What actually happens

## Environment

- OS: macOS/Linux/Windows
- Python version: 3.9/3.10/3.11
- Docker version (if applicable): 20.10+
- etcd version: v3.4/3.5

## Screenshots (if applicable)

Attach images

## Additional Context

Any other relevant information
```

### Feature Requests

```markdown
## Summary

Brief summary of the feature

## Motivation

Why is this needed?

## Proposed Solution

How would you solve it?

## Alternatives Considered

Are there other approaches?

## Additional Context

Examples, links, references
```

---

## Development Tips

### Useful Commands

```bash
# View current changes
git diff

# Stage interactively
git add -p

# Amend last commit
git commit --amend

# Rebase on main (clean history)
git rebase -i origin/main

# View commit history
git log --oneline --graph --all
```

### Debugging

```python
# Using Flask shell
flask shell

# Using pudb (better than pdb)
uv add pudb
# Then: set_trace()  # or breakpoint()

# Inspect etcd
etcdctl get /traefik/ --prefix
```

### Common Issues

**Issue**: Import errors when running locally

**Solution**:

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
python webui.py
```

**Issue**: etcd connection timeout

**Solution**:

```bash
# Verify etcd running
docker ps | grep etcd
# Or start with compose
docker compose up etcd -d
```

**Issue**: SQLite locked (file is being used)

**Solution**:

```bash
# Close all connections
pkill -f "webui.py"
# Remove lock file if present
rm -f ./data/traefik_manager.db-wal
```

---

## Questions?

- Read [ARCHITECTURE.md](ARCHITECTURE.md)
- Check [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- Open a discussion on GitHub
- Email: samirm@genxnext.com

---

Thank you for contributing! 🎉

---

**Last Updated**: February 2026  
**Maintainer**: GXNT TECH PVT LTD
